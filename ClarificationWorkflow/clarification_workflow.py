"""Create reviewable clarification-email drafts from validation results."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR.parent / "EmailValidationAgent" / "runs" / "latest.json"
RUN_DIR = BASE_DIR / "runs"
QUEUE_PATH = RUN_DIR / "clarification_queue.json"

FIELD_QUESTIONS = {
    "organization_name": "the company or customer organization name",
    "specific_site_address": "the exact service address or site identifier",
    "contact_phone_number": "a phone number for the site contact",
    "problem_or_request": "a short description of the requested work",
    "equipment_or_asset": "the equipment or asset that needs attention",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def draft_id(result: dict) -> str:
    return "CLR-" + hashlib.sha256(str(result.get("email_id", "")).encode("utf-8")).hexdigest()[:10].upper()


def load_queue() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(queue: list[dict]) -> None:
    RUN_DIR.mkdir(exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


def create_draft(result: dict) -> dict:
    missing = list(dict.fromkeys(result.get("missing_information") or []))
    questions = [FIELD_QUESTIONS.get(field, field.replace("_", " ")) for field in missing]
    if len(questions) == 1:
        request_text = questions[0]
    else:
        request_text = ", ".join(questions[:-1]) + ", and " + questions[-1]
    message = result.get("subject") or "your service request"
    return {
        "clarification_id": draft_id(result),
        "status": "draft_not_sent",
        "created_at": now(),
        "email_id": result.get("email_id"),
        "to": result.get("sender") or result.get("from") or "",
        "subject": f"Re: {message}",
        "missing_information": missing,
        "body": (
            "Hello,\n\n"
            "Thank you for your request. Before we can continue, could you please provide "
            + request_text
            + "?\n\n"
            "Once we have this information, we can continue processing your request.\n\n"
            "Best regards"
        ),
        "source_validation": result,
    }


def sync(input_path: Path) -> list[dict]:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    queue = load_queue()
    known = {item["clarification_id"] for item in queue}
    added = 0
    for result in source.get("results", []):
        if result.get("decision") != "request_clarification":
            continue

        # TODO(CRM): Before drafting a clarification email, call the CRM lookup
        # agent here using the organization/customer/contact information and
        # email/thread ID. Merge any confirmed customer, site, and contact data
        # into `result`, then recalculate the remaining missing_information.
        # If CRM supplies the missing fields, update the enriched request and
        # route it to `requires_human_approval` so a person can review the
        # recovered information before any response is sent. Only draft a
        # clarification after CRM enrichment still leaves required fields missing.
        draft = create_draft(result)
        if draft["clarification_id"] in known:
            continue
        queue.append(draft)
        known.add(draft["clarification_id"])
        added += 1
    save_queue(queue)
    print(f"Added {added} new clarification draft(s). Total drafts: {len(queue)}")
    print(f"Queue: {QUEUE_PATH}")
    return queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    sync(args.input)


if __name__ == "__main__":
    main()
