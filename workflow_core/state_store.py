"""Small JSON state store used while the project has no database."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class WorkflowStateStore:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict:
        if not self.path.exists():
            return {"workflows": {}, "events": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def transition(self, workflow_id: str, state: str, data: dict | None = None) -> None:
        record = self._read()
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record["workflows"].setdefault(workflow_id, {"workflow_id": workflow_id, "history": []})
        workflow = record["workflows"][workflow_id]
        workflow["state"] = state
        workflow["updated_at"] = timestamp
        workflow["history"].append({"timestamp": timestamp, "state": state, "data": data or {}})
        self._write(record)

    def event(self, workflow_id: str, agent: str, event: str, data: dict | None = None) -> None:
        record = self._read()
        record["events"].append({
            "workflow_id": workflow_id, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agent": agent, "event": event, "data": data or {},
        })
        self._write(record)
