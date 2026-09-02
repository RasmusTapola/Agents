"""Create simulated ERP work orders from approved workflow decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))
from workflow_core.adapters import ERPNextAdapter  # noqa: E402
DEFAULT_INPUT = BASE_DIR.parent / "ApprovalAgent" / "runs" / "latest.json"
RUN_DIR = BASE_DIR / "runs"
ERP_PATH = RUN_DIR / "simulated_erp_work_orders.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def work_order_id(item: dict) -> str:
    value = str(item.get("email_id", ""))
    return "SIM-WO-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:10].upper()


def load_records() -> list[dict]:
    if not ERP_PATH.exists():
        return []
    return json.loads(ERP_PATH.read_text(encoding="utf-8"))


def save_records(records: list[dict]) -> None:
    RUN_DIR.mkdir(exist_ok=True)
    ERP_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def create_record(item: dict) -> dict:
    work_order = item.get("work_order", {})
    return {
        "work_order_id": work_order_id(item),
        "created_at": now(),
        "source_email_id": item.get("email_id"),
        "external_id": item.get("workflow_id") or f"email:{item.get('email_id', '')}",
        "customer": work_order.get("organization_name") or work_order.get("customer_name"),
        "contact": work_order.get("contact_name"),
        "contact_details": work_order.get("contact_details"),
        "site_or_address": work_order.get("site_or_address"),
        "request_type": work_order.get("request_type"),
        "problem_or_request": work_order.get("problem_or_request"),
        "equipment_or_asset": work_order.get("equipment_or_asset"),
        "priority": work_order.get("priority", "unknown"),
        "requested_date": work_order.get("requested_date") or None,
        "requested_time": work_order.get("requested_time") or None,
        "status": "created_in_simulated_erp",
        "next_stage": "scheduling_pending",
        "source_approval": "approved",
    }


def run(input_path: Path, dry_run: bool = False, erpnext: bool = False) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    records = load_records()
    known = {record["work_order_id"] for record in records}
    created = []
    skipped = []
    failures = []
    adapter = ERPNextAdapter() if erpnext and not dry_run else None
    for item in source.get("results", []):
        if item.get("decision") != "approved":
            continue
        try:
            record = create_record(item)
            if record["work_order_id"] in known and not erpnext:
                skipped.append(record["work_order_id"])
                continue
            if adapter:
                external_id = record["external_id"]
                existing = adapter.find_by_external_id(external_id)
                if existing:
                    skipped.append(existing.get("name", external_id))
                    continue
                erp_record = adapter.create_work_order(record)
                record["erpnext_name"] = erp_record.get("name")
                record["erpnext_status"] = erp_record.get("status")
                record["erpnext_customer"] = next((x.get("name") for x in adapter.find_customer(record["customer"])[:1]), None) if record.get("customer") else None
                record["erpnext_contact"] = next((x.get("name") for x in adapter.find_contact(record["contact_details"])[:1]), None) if record.get("contact_details") and "@" in record["contact_details"] else None
            if not dry_run:
                records.append(record)
                known.add(record["work_order_id"])
            created.append(record)
        except Exception as exc:
            failures.append({"external_id": item.get("workflow_id") or item.get("email_id"), "error": str(exc)})
    if not dry_run:
        save_records(records)
    report = {
        "generated_at": now(),
        "input_file": str(input_path),
        "created_count": len(created),
        "skipped_duplicate_count": len(skipped),
        "failure_count": len(failures),
        "failures": failures,
        "created_work_orders": created,
        "dry_run": dry_run,
        "target_erp": "erpnext" if erpnext else "simulated",
        "reconciliation": [
            {"external_id": item.get("external_id"), "simulated_work_order_id": item["work_order_id"], "erpnext_name": item.get("erpnext_name"),
             "action": "would_create" if dry_run else "created"}
            for item in created
        ],
        "simulated_erp_file": str(ERP_PATH),
    }
    RUN_DIR.mkdir(exist_ok=True)
    (RUN_DIR / "latest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dry-run", action="store_true", help="Show ERP payloads without writing records")
    parser.add_argument("--erpnext", action="store_true", help="Create an Issue in ERPNext instead of only using the simulated ERP")
    args = parser.parse_args()
    report = run(args.input, dry_run=args.dry_run, erpnext=args.erpnext)
    print(f"Created simulated work orders: {report['created_count']}")
    print(f"Skipped duplicates: {report['skipped_duplicate_count']}")
    print(f"Report: {RUN_DIR / 'latest.json'}")


if __name__ == "__main__":
    main()
