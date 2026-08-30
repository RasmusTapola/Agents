# Clarification workflow

This workflow handles `request_clarification` results from `EmailValidationAgent`.
It creates a draft reply listing the missing information and keeps the draft in a persistent queue.

```text
EmailValidationAgent
  → clarification queue
  → draft clarification email
  → human review
  → future send step
```

Drafts are never sent by this component.

The draft-generation point contains a TODO for a future CRM lookup. The intended order is: validation result → CRM enrichment → recalculate missing fields. If CRM fills the missing fields, the enriched request should become `requires_human_approval` for review before sending anything. A clarification draft should only be created if information is still unavailable.

## Run

```powershell
python ClarificationWorkflow\clarification_workflow.py
```

Or provide a specific validation report:

```powershell
python ClarificationWorkflow\clarification_workflow.py --input EmailValidationAgent\runs\latest.json
```

Output:

```text
ClarificationWorkflow/runs/clarification_queue.json
```

Running the workflow again is idempotent and will not create duplicate drafts for the same Gmail message.
