"""Run the Gmail, validation, and approval agents as one controlled workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workflow_core.state_store import WorkflowStateStore


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
GMAIL_DIR = ROOT_DIR / "GmailAgent"
VALIDATION_DIR = ROOT_DIR / "EmailValidationAgent"
APPROVAL_DIR = ROOT_DIR / "ApprovalAgent"
APPROVED_WORK_ORDER_DIR = ROOT_DIR / "ApprovedWorkOrderWorkflow"
HUMAN_APPROVAL_DIR = ROOT_DIR / "HumanApprovalWorkflow"
CLARIFICATION_DIR = ROOT_DIR / "ClarificationWorkflow"
CRM_DIR = ROOT_DIR / "CRMResolutionAgent"
RUN_DIR = BASE_DIR / "runs"
STATE_STORE = WorkflowStateStore(RUN_DIR / "workflow_state.json")


def newest_candidate_file() -> Path:
    candidates = sorted((GMAIL_DIR / "reports").glob("work_order_candidates_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError("No Gmail work-order candidate file exists. Run without --skip-gmail first.")
    return candidates[-1]


def run_command(command: list[str], cwd: Path) -> str:
    last_output = ""
    for attempt in range(1, 3):
        completed = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
        last_output = (completed.stdout + completed.stderr).strip()
        if completed.returncode == 0:
            return last_output
        if attempt < 2:
            time.sleep(1)
    raise RuntimeError(f"Command failed after 2 attempts ({completed.returncode}): {' '.join(command)}\n{last_output}")


def stage_record(name: str, path: Path, output: str) -> dict:
    return {"agent": name, "status": "completed", "output_file": str(path), "console_output": output}


def run_workflow(skip_gmail: bool, query: str, limit: int, model: str, reprocess: bool, erpnext: bool = False) -> dict:
    workflow_id = datetime.now(timezone.utc).strftime("workflow-%Y%m%dT%H%M%SZ")
    stages = []
    STATE_STORE.transition(workflow_id, "received", {"skip_gmail": skip_gmail})
    if skip_gmail:
        candidate_path = newest_candidate_file()
        stages.append({"agent": "GmailAgent", "status": "skipped", "output_file": str(candidate_path), "reason": "replay mode"})
    else:
        gmail_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
        interpreter = str(gmail_python) if gmail_python.exists() else sys.executable
        command = [interpreter, "gmail_agent.py", "--query", query, "--limit", str(limit), "--model", model]
        if reprocess:
            command.append("--reprocess")
        output = run_command(command, GMAIL_DIR)
        candidate_path = newest_candidate_file()
        stages.append(stage_record("GmailAgent", candidate_path, output))
    STATE_STORE.transition(workflow_id, "extracted", {"candidate_file": str(candidate_path)})

    validation_output = VALIDATION_DIR / "runs" / "latest.json"
    output = run_command([sys.executable, "email_validation_agent.py", "--input", str(candidate_path)], VALIDATION_DIR)
    stages.append(stage_record("EmailValidationAgent", validation_output, output))
    STATE_STORE.transition(workflow_id, "validated", {"output_file": str(validation_output)})

    crm_output = CRM_DIR / "runs" / "latest.json"
    crm_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    crm_interpreter = str(crm_python) if crm_python.exists() else sys.executable
    output = run_command(
        [crm_interpreter, "crm_enrichment_agent.py", "--input", str(validation_output)],
        CRM_DIR,
    )
    stages.append(stage_record("CRMResolutionAgent", crm_output, output))
    STATE_STORE.transition(workflow_id, "crm_lookup_completed", {"output_file": str(crm_output)})

    approval_output = APPROVAL_DIR / "runs" / "latest.json"
    output = run_command([sys.executable, "approval_agent.py", "--input", str(crm_output)], APPROVAL_DIR)
    stages.append(stage_record("ApprovalAgent", approval_output, output))

    approval_data = json.loads(approval_output.read_text(encoding="utf-8"))
    counts = approval_data.get("decision_counts", {})
    if counts.get("requires_human_approval"):
        STATE_STORE.transition(workflow_id, "approval_needed", {"output_file": str(approval_output), "count": counts["requires_human_approval"]})
    elif counts.get("request_clarification"):
        STATE_STORE.transition(workflow_id, "clarification_needed", {"output_file": str(approval_output), "count": counts["request_clarification"]})
    elif counts.get("approved"):
        STATE_STORE.transition(workflow_id, "approved", {"output_file": str(approval_output), "count": counts["approved"]})
    simulated_erp_output = APPROVED_WORK_ORDER_DIR / "runs" / "latest.json"
    erp_command = [sys.executable, "approved_work_order_workflow.py", "--input", str(approval_output)]
    if erpnext:
        erp_command.append("--erpnext")
    output = run_command(
        erp_command,
        APPROVED_WORK_ORDER_DIR,
    )
    stages.append(stage_record("ApprovedWorkOrderWorkflow", simulated_erp_output, output))

    human_approval_output = HUMAN_APPROVAL_DIR / "runs" / "approval_queue.json"
    output = run_command(
        [sys.executable, "human_approval_workflow.py", "sync", "--input", str(approval_output)],
        HUMAN_APPROVAL_DIR,
    )
    stages.append(stage_record("HumanApprovalWorkflow", human_approval_output, output))

    clarification_output = CLARIFICATION_DIR / "runs" / "clarification_queue.json"
    output = run_command(
        [sys.executable, "clarification_workflow.py", "--input", str(validation_output)],
        CLARIFICATION_DIR,
    )
    stages.append(stage_record("ClarificationWorkflow", clarification_output, output))
    erp_data = json.loads(simulated_erp_output.read_text(encoding="utf-8"))
    if erp_data.get("created_count", 0) or erp_data.get("skipped_duplicate_count", 0):
        STATE_STORE.transition(workflow_id, "erp_created", {
            "output_file": str(simulated_erp_output),
            "created_count": erp_data.get("created_count", 0),
            "skipped_duplicate_count": erp_data.get("skipped_duplicate_count", 0),
        })
    return {
        "workflow_id": workflow_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "completed",
        "stages": stages,
        "decision_counts": counts,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-gmail", action="store_true", help="Replay the newest existing Gmail candidate file")
    parser.add_argument("--query", default="in:inbox newer_than:7d")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--model", default="qwen3")
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument("--erpnext", action="store_true", help="Create approved requests in ERPNext")
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        raise SystemExit("--limit must be between 1 and 50")

    result = run_workflow(args.skip_gmail, args.query, args.limit, args.model, args.reprocess, args.erpnext)
    RUN_DIR.mkdir(exist_ok=True)
    output_path = RUN_DIR / "latest.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Workflow status: {result['status']}")
    print(f"Decision counts: {result['decision_counts']}")
    print(f"Workflow manifest: {output_path}")


if __name__ == "__main__":
    main()
