"""Adapter boundary for future ERP integrations."""

from __future__ import annotations

from typing import Protocol
import csv
import os
from pathlib import Path

import requests
import time


class ERPAdapter(Protocol):
    def health_check(self) -> dict: ...

    def find_by_external_id(self, external_id: str) -> dict | None: ...

    def create_work_order(self, work_order: dict) -> dict: ...

    def update_work_order(self, external_id: str, work_order: dict) -> dict: ...


class SimulatedERPAdapter:
    """Development adapter; replace this with a test ERP adapter later."""

    def __init__(self, create_record, records=None):
        self._create_record = create_record
        self._records = records if records is not None else []

    def health_check(self) -> dict:
        return {"status": "ok", "adapter": "simulated_erp"}

    def find_by_external_id(self, external_id: str) -> dict | None:
        return next((r for r in self._records if r.get("external_id") == external_id), None)

    def create_work_order(self, work_order: dict) -> dict:
        return self._create_record(work_order)

    def update_work_order(self, external_id: str, work_order: dict) -> dict:
        record = self.find_by_external_id(external_id)
        if not record:
            raise KeyError(f"Work order not found: {external_id}")
        record.update(work_order)
        return record


class ERPNextAdapter:
    """Read-only ERPNext REST adapter for the local integration test."""

    def __init__(self, base_url: str | None = None, credentials_file: Path | None = None, timeout: int = 15):
        self.base_url = (base_url or os.environ.get("ERPNEXT_URL", "http://localhost:8081")).rstrip("/")
        path = credentials_file or Path(os.environ.get("ERPNEXT_CREDENTIALS_FILE", str(Path(__file__).resolve().parent.parent / "frappe_api_keys.csv")))
        with path.open(newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle), None)
        if not row or not row.get("api_key") or not row.get("api_secret"):
            raise ValueError("ERPNext credentials file must contain api_key and api_secret")
        self.headers = {
            "Authorization": f"token {row['api_key']}:{row['api_secret']}",
            "Accept": "application/json",
        }
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(f"{self.base_url}{path}", headers=self.headers, params=params or {}, timeout=self.timeout)
        if response.status_code in (401, 403):
            raise RuntimeError(f"ERPNext rejected the request with HTTP {response.status_code}; check API-user permissions")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> dict:
        data = self._get("/api/method/frappe.auth.get_logged_user")
        return {"status": "ok", "adapter": "erpnext", "user": data.get("message")}

    def find_by_external_id(self, external_id: str) -> dict | None:
        subject = f"[Agent {external_id}]"
        data = self._get("/api/resource/Issue", {"fields": '["name","subject","status"]', "filters": f'[["Issue","subject","like","%{subject}%"]]'} )
        rows = data.get("data", [])
        return rows[0] if rows else None

    def create_work_order(self, work_order: dict) -> dict:
        external_id = work_order.get("external_id") or work_order.get("source_email_id")
        subject = f"[Agent {external_id}] {work_order.get('request_type', 'service').replace('_', ' ').title()}"
        payload = {"subject": subject, "description": work_order.get("problem_or_request") or "Automated service request", "status": "Open", "priority": (work_order.get("priority") or "Medium").title()}
        if work_order.get("customer"):
            payload["customer"] = work_order["customer"]
        response = None
        for attempt in range(3):
            try:
                response = requests.post(f"{self.base_url}/api/resource/Issue", headers={**self.headers, "Content-Type": "application/json"}, json=payload, timeout=self.timeout)
                if response.status_code >= 500 and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        if response.status_code in (401, 403):
            raise RuntimeError(f"ERPNext rejected the request with HTTP {response.status_code}; check API-user permissions")
        response.raise_for_status()
        return response.json().get("data", {})

    def update_work_order(self, external_id: str, work_order: dict) -> dict:
        raise NotImplementedError("ERPNext updates are not implemented yet")

    def find_customer(self, customer_name: str) -> list[dict]:
        return self._get("/api/resource/Customer", {"fields": '["name","customer_name"]', "filters": f'[["Customer","customer_name","=","{customer_name}"]]'}).get("data", [])

    def find_contact(self, email: str) -> list[dict]:
        return self._get("/api/resource/Contact", {"fields": '["name","first_name","last_name","email_id"]', "filters": f'[["Contact","email_id","=","{email}"]]'}).get("data", [])

    def find_item(self, item_code: str) -> list[dict]:
        return self._get("/api/resource/Item", {"fields": '["name","item_name","stock_uom"]', "filters": f'[["Item","item_code","=","{item_code}"]]'}).get("data", [])
