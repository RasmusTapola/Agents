"""Enrich validation results with read-only EspoCRM lookups."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crm_resolution_agent import EspoCRMClient  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR.parent / "EmailValidationAgent" / "runs" / "latest.json"
RUN_DIR = BASE_DIR / "runs"


def email_address(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value)
    return match.group(0) if match else None


def first_record(response: dict) -> dict | None:
    records = response.get("list", [])
    return records[0] if records else None


def enrich_result(result: dict, client: EspoCRMClient) -> dict:
    enriched = copy.deepcopy(result)
    work_order = enriched.setdefault("work_order", {})
    missing = [item for item in (enriched.get("missing_information") or []) if item not in {"customer_number", "requested_date", "requested_time", "date", "time"}]
    account = None
    organization = work_order.get("organization_name")
    if organization:
        account = first_record(client.find_account_by_name(organization))
    if account:
        work_order["organization_name"] = account.get("name") or organization
        work_order["customer_id"] = account.get("id")
        if not work_order.get("site_or_address"):
            street = account.get("billingAddressStreet")
            city = account.get("billingAddressCity")
            work_order["site_or_address"] = ", ".join(value for value in (street, city) if value)
        if work_order.get("site_or_address"):
            missing = [item for item in missing if item != "specific_site_address"]
    contact = first_record(client.find_contact_by_email(email_address(enriched.get("sender")) or "")) if enriched.get("sender") else None
    if contact:
        work_order["contact_id"] = contact.get("id")
        work_order["contact_name"] = contact.get("name") or work_order.get("contact_name")
        work_order["contact_details"] = contact.get("phoneNumber") or work_order.get("contact_details")
        if work_order.get("contact_details"):
            missing = [item for item in missing if item != "contact_phone_number"]

    enriched["missing_information"] = list(dict.fromkeys(missing))
    enriched["crm_status"] = "matched" if account or contact else "no_match"
    enriched["crm_matches"] = {"account": account, "contact": contact}
    if account or contact:
        if not enriched["missing_information"]:
            enriched["decision"] = "requires_human_approval"
            enriched["reason"] = "CRM supplied or confirmed request data; human review is required before any response or downstream action."
        else:
            enriched["reason"] = "CRM enrichment was attempted, but required information is still missing."
    return enriched


def run(input_path: Path) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    try:
        client = EspoCRMClient()
    except ValueError as exc:
        results = [dict(result, crm_status="not_configured", crm_error=str(exc)) for result in source.get("results", [])]
        return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input_file": str(input_path), "results": results}
    results = []
    for result in source.get("results", []):
        if result.get("decision") == "request_clarification":
            try:
                results.append(enrich_result(result, client))
            except Exception as exc:
                failed = copy.deepcopy(result)
                failed["crm_status"] = "lookup_failed"
                failed["crm_error"] = str(exc)
                results.append(failed)
        else:
            results.append(result)
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input_file": str(input_path), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    output = run(args.input)
    RUN_DIR.mkdir(exist_ok=True)
    path = RUN_DIR / "latest.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"CRM-enriched candidates: {len(output['results'])}")
    print(f"Output: {path}")


if __name__ == "__main__":
    main()
