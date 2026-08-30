# Human approval workflow

This workflow handles `requires_human_approval` results from `ApprovalAgent`.

```text
ApprovalAgent
  -> persistent approval queue
  -> reviewer decision
  -> approved / rejected / clarification_requested
```

It is intentionally local and safe: it does not send email, create ERP records, or dispatch technicians. It only records the human decision for the next workflow stage.

## Create or refresh the queue

```powershell
python HumanApprovalWorkflow\human_approval_workflow.py sync
```

## List pending items

```powershell
python HumanApprovalWorkflow\human_approval_workflow.py list
```

## Record a decision

First obtain an approval ID with `list`, then run one of:

```powershell
python HumanApprovalWorkflow\human_approval_workflow.py decide APR-...
python HumanApprovalWorkflow\human_approval_workflow.py decide APR-... --reject --note "Insufficient emergency details"
python HumanApprovalWorkflow\human_approval_workflow.py decide APR-... --clarification --note "Confirm responsible site contact"
```

The default decision is approval. Queue state is stored in `runs/approval_queue.json`.
