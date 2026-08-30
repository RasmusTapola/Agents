# Approved work-order workflow

This is the execution stage for ordinary requests approved by `ApprovalAgent`.
It writes a simulated ERP work-order record and leaves scheduling for a later stage.

```text
ApprovalAgent: approved
  → simulated ERP work order
  → scheduling_pending
```

It ignores `requires_human_approval` and `request_clarification` results. It does not connect to a real ERP, send email, or assign a technician.

## Run

```powershell
python ApprovedWorkOrderWorkflow\approved_work_order_workflow.py
```

The input defaults to `ApprovalAgent/runs/latest.json`. The simulated ERP records are stored in:

```text
ApprovedWorkOrderWorkflow/runs/simulated_erp_work_orders.json
```

The workflow report is written to:

```text
ApprovedWorkOrderWorkflow/runs/latest.json
```

Repeated runs are idempotent and do not create duplicate simulated work orders.
