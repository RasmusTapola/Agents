"""Run a synthetic email-to-work-order field-service workflow."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RUN_DIR = BASE_DIR / "runs"


@dataclass
class Email:
    id: str
    sender: str
    subject: str
    body: str


@dataclass
class ServiceRequest:
    email_id: str
    customer_number: str | None
    customer_name: str
    site_code: str
    address: str
    category: str
    problem: str
    requested_time: str | None
    priority: str
    confidence: float
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class WorkOrder:
    id: str
    customer_name: str
    site_code: str
    address: str
    category: str
    problem: str
    priority: str
    status: str
    source_email_id: str


class EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def add(self, agent: str, event: str, data: dict | None = None) -> None:
        self.events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "agent": agent,
                "event": event,
                "data": data or {},
            }
        )


class SimulatedInbox:
    def receive(self) -> Email:
        return Email(
            id="email-1001",
            sender="maintenance@northwind.example",
            subject="Urgent: ventilation unit making noise at Hämeentie 12",
            body=(
                "Hello, the ventilation unit in our office at Hämeentie 12 is making "
                "an unusual noise and the temperature has dropped. Could someone visit "
                "tomorrow morning? Customer number NW-001. Regards, Anna"
            ),
        )


class SimulatedERP:
    customers = {
        "NW-001": {
            "customer_name": "Northwind Facilities Oy",
            "site_code": "NW-HAM-01",
            "address": "Hämeentie 12, Helsinki",
        }
    }

    def find_customer(self, customer_number: str) -> dict | None:
        return self.customers.get(customer_number)

    def create_work_order(self, request: ServiceRequest) -> WorkOrder:
        return WorkOrder(
            id=f"WO-{uuid.uuid4().hex[:8].upper()}",
            customer_name=request.customer_name,
            site_code=request.site_code,
            address=request.address,
            category=request.category,
            problem=request.problem,
            priority=request.priority,
            status="Scheduled",
            source_email_id=request.email_id,
        )


class IntakeAgent:
    """Extracts a proposal from untrusted email text; it does not perform actions."""

    def run(self, email: Email, log: EventLog) -> ServiceRequest:
        customer_number = self._capture(r"customer number\s+([A-Z]{2}-\d{3})", email.body)
        address = self._capture(r"at\s+([^\.]+?)(?=\s+is making|\.)", email.body) or ""
        requested_time = "tomorrow morning" if "tomorrow morning" in email.body.lower() else None
        problem = "Unusual ventilation-unit noise and temperature drop"
        priority = "high" if any(word in email.body.lower() for word in ("urgent", "dropped")) else "normal"
        request = ServiceRequest(
            email_id=email.id,
            customer_number=customer_number,
            customer_name="",
            site_code="",
            address=address.strip(),
            category="HVAC",
            problem=problem,
            requested_time=requested_time,
            priority=priority,
            confidence=0.94 if customer_number and address else 0.60,
        )
        request.missing_fields = [] if customer_number else ["customer_number"]
        request.missing_fields += [] if address else ["address"]
        log.add("IntakeAgent", "request_extracted", asdict(request))
        return request

    @staticmethod
    def _capture(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None


class ValidationAgent:
    def run(self, request: ServiceRequest, erp: SimulatedERP, log: EventLog) -> ServiceRequest:
        customer = erp.find_customer(request.customer_number or "")
        if not customer:
            request.missing_fields.append("known_customer")
            log.add("ValidationAgent", "validation_failed", {"missing_fields": request.missing_fields})
            return request
        request.customer_name = customer["customer_name"]
        request.site_code = customer["site_code"]
        request.address = customer["address"]
        log.add("ValidationAgent", "request_validated", {"customer": customer, "confidence": request.confidence})
        return request


class ApprovalAgent:
    def run(self, request: ServiceRequest, log: EventLog, approved: bool) -> bool:
        decision = "approved" if approved else "rejected"
        log.add("ApprovalAgent", decision, {"priority": request.priority, "reason": "synthetic training decision"})
        return approved


class ReportingAgent:
    def run(self, work_order: WorkOrder, log: EventLog) -> dict:
        report = {
            "work_order_id": work_order.id,
            "completed_work": "Inspected ventilation unit and replaced worn fan belt.",
            "measurements": {"vibration_mm_s": 2.1, "temperature_c": 21.5},
            "follow_up": "Schedule inspection in six months.",
        }
        log.add("ReportingAgent", "technician_report_created", report)
        return report


class BillingAgent:
    def run(self, work_order: WorkOrder, report: dict, log: EventLog) -> dict:
        invoice = {
            "customer": work_order.customer_name,
            "work_order_id": work_order.id,
            "status": "Draft",
            "lines": [
                {"description": "Service visit and fan-belt replacement", "quantity": 1, "unit_price": 185.00},
                {"description": "Travel and materials", "quantity": 1, "unit_price": 65.00},
            ],
            "total_excl_vat": 250.00,
        }
        log.add("BillingAgent", "invoice_draft_created", invoice)
        return invoice


def run(approved: bool = True) -> dict:
    log = EventLog()
    inbox = SimulatedInbox()
    erp = SimulatedERP()
    email = inbox.receive()
    log.add("SimulatedInbox", "email_received", asdict(email))

    request = IntakeAgent().run(email, log)
    request = ValidationAgent().run(request, erp, log)
    if request.missing_fields:
        log.add("Orchestrator", "workflow_stopped", {"reason": "missing or invalid data", "missing_fields": request.missing_fields})
        return {"status": "blocked", "request": asdict(request), "events": log.events}
    if not ApprovalAgent().run(request, log, approved):
        log.add("Orchestrator", "workflow_stopped", {"reason": "human approval denied"})
        return {"status": "rejected", "request": asdict(request), "events": log.events}

    work_order = erp.create_work_order(request)
    log.add("SimulatedERP", "work_order_created", asdict(work_order))
    report = ReportingAgent().run(work_order, log)
    invoice = BillingAgent().run(work_order, report, log)
    log.add("Orchestrator", "workflow_completed", {"work_order_id": work_order.id})
    return {"status": "completed", "email": asdict(email), "request": asdict(request), "work_order": asdict(work_order), "report": report, "invoice": invoice, "events": log.events}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reject", action="store_true", help="Simulate a human rejecting the work-order draft")
    args = parser.parse_args()
    result = run(approved=not args.reject)
    RUN_DIR.mkdir(exist_ok=True)
    output = RUN_DIR / "latest.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Workflow status: {result['status']}")
    print(f"Events recorded: {len(result['events'])}")
    print(f"Run written to: {output}")


if __name__ == "__main__":
    main()
