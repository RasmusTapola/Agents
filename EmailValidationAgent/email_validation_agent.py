"""Validate Gmail work-order candidates before any downstream business action."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR.parent / "GmailAgent" / "reports"
RUN_DIR = BASE_DIR / "runs"


def newest_candidate_file() -> Path:
    files = sorted(DEFAULT_INPUT_DIR.glob("work_order_candidates_*.json"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No work-order candidate file found in {DEFAULT_INPUT_DIR}")
    return files[-1]


def validate_candidate(item: dict) -> dict:
    work_order = item.get("work_order", {})
    message = item.get("message", {})
    # Customer numbers and scheduling details are intentionally not required at
    # intake. CRM lookup and resource planning happen in later stages.
    optional_fields = {"customer_number", "requested_date", "requested_time", "date", "time"}
    missing = [item for item in (work_order.get("missing_information") or []) if item not in optional_fields]
    organization = (work_order.get("organization_name") or "").strip()
    site = (work_order.get("site_or_address") or "").strip()
    problem = (work_order.get("problem_or_request") or "").strip()
    confidence = float(work_order.get("confidence") or 0)
    priority = work_order.get("priority", "unknown")

    if work_order.get("contact_phone_number"):
        missing = [item for item in missing if item != "contact_phone_number"]

    if not organization:
        missing.append("organization_name")
    if not site or site.lower() in {"production facilities", "the site", "onsite", "on site"}:
        missing.append("specific_site_address")
    if not problem:
        missing.append("problem_or_request")

    # Keep the output stable and readable if the extraction model repeated a field.
    missing = list(dict.fromkeys(missing))
    high_risk = priority == "high" or any(word in problem.lower() for word in ("fire", "gas leak", "injury", "danger"))

    if high_risk and missing:
        decision = "escalate_to_human"
        reason = "Potentially high-risk request has missing information."
    elif missing or confidence < 0.75:
        decision = "request_clarification"
        reason = "Required information is missing or extraction confidence is below the approval threshold."
    else:
        decision = "approved_for_next_stage"
        reason = "Required fields are present and confidence meets the approval threshold."

    clarification = None
    if decision == "request_clarification":
        questions = []
        if "organization_name" in missing:
            questions.append("the company or customer organization name")
        if "specific_site_address" in missing:
            questions.append("the exact service address or site identifier")
        if "contact_phone_number" in missing:
            questions.append("a phone number for the site contact")
        clarification = {
            "to": message.get("from", ""),
            "subject": f"Re: {message.get('subject', 'service request')}",
            "body": "Before we create a work order, could you please provide " + ", ".join(questions) + "?",
            "status": "draft_not_sent",
        }

    return {
        "email_id": message.get("id"),
        "sender": message.get("from"),
        "subject": message.get("subject"),
        "decision": decision,
        "reason": reason,
        "missing_information": missing,
        "confidence": confidence,
        "priority": priority,
        "work_order": work_order,
        "clarification_email": clarification,
    }


def run(input_path: Path) -> dict:
    candidates = json.loads(input_path.read_text(encoding="utf-8"))
    results = [validate_candidate(item) for item in candidates]
    counts = {}
    for result in results:
        counts[result["decision"]] = counts.get(result["decision"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": str(input_path),
        "candidate_count": len(candidates),
        "decision_counts": counts,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Candidate JSON produced by GmailAgent")
    args = parser.parse_args()
    input_path = args.input or newest_candidate_file()
    result = run(input_path)
    RUN_DIR.mkdir(exist_ok=True)
    output_path = RUN_DIR / "latest.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Validated candidates: {result['candidate_count']}")
    print(f"Decisions: {result['decision_counts']}")
    print(f"Validation report: {output_path}")


if __name__ == "__main__":
    main()
