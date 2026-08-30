"""Canonical workflow and work-order contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


WORKFLOW_STATES = {
    "received", "extracted", "validated", "clarification_needed",
    "approval_needed", "approved", "rejected", "erp_pending",
    "erp_created", "failed",
}


@dataclass
class WorkOrder:
    workflow_id: str
    source_email_id: str
    organization_name: str | None = None
    customer_id: str | None = None
    site_id: str | None = None
    site_or_address: str | None = None
    contact_name: str | None = None
    contact_details: str | None = None
    request_type: str = "other"
    problem_or_request: str | None = None
    equipment_or_asset: str | None = None
    priority: str = "unknown"
    requested_date: str | None = None
    requested_time: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def work_order_from_result(result: dict) -> WorkOrder:
    data = result.get("work_order", result)
    return WorkOrder(
        workflow_id=result.get("workflow_id") or f"email:{result.get('email_id', '')}",
        source_email_id=result.get("email_id") or data.get("source_email_id", ""),
        organization_name=data.get("organization_name"),
        customer_id=data.get("customer_id"),
        site_id=data.get("site_id"),
        site_or_address=data.get("site_or_address"),
        contact_name=data.get("contact_name"),
        contact_details=data.get("contact_details"),
        request_type=data.get("request_type", "other"),
        problem_or_request=data.get("problem_or_request"),
        equipment_or_asset=data.get("equipment_or_asset"),
        priority=data.get("priority", "unknown"),
        requested_date=data.get("requested_date") or None,
        requested_time=data.get("requested_time") or None,
        confidence=float(data.get("confidence") or result.get("confidence") or 0),
    )
