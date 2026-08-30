# Workflow orchestrator

The orchestrator runs the current agents as one workflow:

```text
GmailAgent
  -> EmailValidationAgent
  -> ApprovalAgent
```

It passes JSON files between stages and writes a workflow manifest containing the status and output of each stage. No ERP record is created and no email is sent by this workflow.

## Replay an existing candidate

This is the safest development mode:

```powershell
python WorkflowOrchestrator\workflow_orchestrator.py --skip-gmail
```

## Run a new Gmail scan

The Gmail virtual environment is used automatically when available:

```powershell
python WorkflowOrchestrator\workflow_orchestrator.py --query "in:inbox newer_than:2d" --limit 5
```

Use `--reprocess` only when intentionally rescanning messages already handled by `GmailAgent`.

The combined manifest is written to:

```text
WorkflowOrchestrator/runs/latest.json
```
