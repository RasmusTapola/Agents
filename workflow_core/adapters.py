"""Adapter boundary for future ERP integrations."""

from __future__ import annotations

from typing import Protocol


class ERPAdapter(Protocol):
    def create_work_order(self, work_order: dict) -> dict: ...


class SimulatedERPAdapter:
    """Development adapter; replace this with a test ERP adapter later."""

    def __init__(self, create_record):
        self._create_record = create_record

    def create_work_order(self, work_order: dict) -> dict:
        return self._create_record(work_order)
