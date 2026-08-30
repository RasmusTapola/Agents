# Agents workspace

The project uses one shared development virtual environment for all local agents:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The orchestrator and CRM integration use this root environment. Agent-specific deployment environments can be introduced later when the services are containerized.
