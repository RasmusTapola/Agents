"""Apply business approval policy to validated work-order candidates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR.parent / "EmailValidationAgent" / "runs" / "latest.json"
RUN_DIR = BASE_DIR / "runs"

SAFETY_TERMS = (
    "fire", "smoke", "gas leak", "gas leakage", "injury", "danger", "unsafe",
    "electrical hazard", "emergency", "risk of explosion", "spill",
)
OFFER_TERMS = (
    "offer", "quotation", "quote request", "new customer", "new installation",
    "extension", "extend existing", "upgrade", "additional system", "proposal",
)


def contains_term(text: str, terms: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    return next((term for term in terms if term in lowered), None)


def decide(result: dict) -> dict:
    work_order = result.get("work_order", {})
    message = result.get("subject", "") + " " + json.dumps(work_order, ensure_ascii=False)
    missing = list(result.get("missing_information") or [])
    validation_decision = result.get("decision")
    safety_term = contains_term(message, SAFETY_TERMS)
    offer_term = contains_term(message, OFFER_TERMS)

    # Safety and commercial requests take precedence over completeness. They
    # must reach an authorized human even when clarification is also needed.
    if validation_decision in {"escalate_to_human", "requires_human_approval"} or safety_term:
        decision = "requires_human_approval"
        reason = f"Safety-sensitive request detected{f' ({safety_term})' if safety_term else ''}."
        approval_request = {
            "type": "safety_review",
            "status": "pending",
            "required_from": "authorized_human_reviewer",
            "reason": reason,
        }
    elif offer_term or work_order.get("request_type") == "quote_request":
        decision = "requires_human_approval"
        reason = f"Commercial offer, new-customer, or system-extension request detected{f' ({offer_term})' if offer_term else ''}."
        approval_request = {
            "type": "commercial_approval",
            "status": "pending",
            "required_from": "authorized_human_reviewer",
            "reason": reason,
        }
    elif validation_decision == "request_clarification" or missing:
        decision = "request_clarification"
        reason = "The validation stage identified missing or insufficient information."
        approval_request = None
    else:
        decision = "approved"
        reason = "Validated ordinary service request meets the current automatic-processing policy."
        approval_request = None

    return {
        "email_id": result.get("email_id"),
        "subject": result.get("subject"),
        "decision": decision,
        "reason": reason,
        "source_validation_decision": validation_decision,
        "risk_signals": {"safety_term": safety_term, "offer_term": offer_term},
        "approval_request": approval_request,
        "work_order": work_order,
    }


def run(input_path: Path) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    results = [decide(item) for item in source.get("results", [])]
    counts: dict[str, int] = {}
    for item in results:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_file": str(input_path),
        "candidate_count": len(results),
        "decision_counts": counts,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    output = run(args.input)
    RUN_DIR.mkdir(exist_ok=True)
    output_path = RUN_DIR / "latest.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Candidates evaluated: {output['candidate_count']}")
    print(f"Decisions: {output['decision_counts']}")
    print(f"Approval report: {output_path}")


if __name__ == "__main__":
    main()
