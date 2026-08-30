"""Persist and process human approval requests produced by ApprovalAgent."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR.parent / "ApprovalAgent" / "runs" / "latest.json"
RUN_DIR = BASE_DIR / "runs"
QUEUE_PATH = RUN_DIR / "approval_queue.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def approval_id(item: dict) -> str:
    source = f"{item.get('email_id', '')}:{item.get('approval_request', {}).get('type', 'review')}"
    return "APR-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:10].upper()


def load_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(queue: list[dict]) -> None:
    RUN_DIR.mkdir(exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


def sync(input_path: Path) -> list[dict]:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    queue = load_queue()
    by_id = {item["approval_id"]: item for item in queue}
    added = 0
    for result in source.get("results", []):
        if result.get("decision") != "requires_human_approval":
            continue
        item_id = approval_id(result)
        if item_id in by_id:
            continue
        by_id[item_id] = {
            "approval_id": item_id,
            "status": "pending",
            "created_at": now(),
            "decided_at": None,
            "decision": None,
            "reviewer_note": None,
            "type": (result.get("approval_request") or {}).get("type", "human_review"),
            "reason": result.get("reason", ""),
            "email_id": result.get("email_id"),
            "subject": result.get("subject"),
            "work_order": result.get("work_order", {}),
        }
        added += 1
    queue = list(by_id.values())
    save_queue(queue)
    print(f"Added {added} new approval request(s). Total queue items: {len(queue)}")
    print(f"Queue: {QUEUE_PATH}")
    return queue


def list_queue() -> None:
    queue = load_queue()
    if not queue:
        print("Approval queue is empty.")
        return
    for item in queue:
        print(f"{item['approval_id']} | {item['status']} | {item['type']} | {item.get('subject', '')}")


def decide(item_id: str, decision: str, note: str | None) -> None:
    queue = load_queue()
    item = next((item for item in queue if item["approval_id"] == item_id), None)
    if item is None:
        raise SystemExit(f"Approval item not found: {item_id}")
    if item["status"] != "pending":
        raise SystemExit(f"Approval item is already {item['status']}: {item_id}")
    item["decision"] = decision
    item["status"] = {"approve": "approved_by_human", "reject": "rejected_by_human", "clarification": "clarification_requested"}[decision]
    item["decided_at"] = now()
    item["reviewer_note"] = note
    save_queue(queue)
    print(f"Recorded {item['status']} for {item_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    sub.add_parser("list")
    decision = sub.add_parser("decide")
    decision.add_argument("approval_id")
    modes = decision.add_mutually_exclusive_group()
    modes.add_argument("--reject", action="store_true")
    modes.add_argument("--clarification", action="store_true")
    decision.add_argument("--note")
    args = parser.parse_args()
    if args.command == "sync":
        sync(args.input)
    elif args.command == "list":
        list_queue()
    else:
        choice = "clarification" if args.clarification else "reject" if args.reject else "approve"
        decide(args.approval_id, choice, args.note)


if __name__ == "__main__":
    main()
