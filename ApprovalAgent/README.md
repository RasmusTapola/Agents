# Approval agent

`ApprovalAgent` is the policy gate after `EmailValidationAgent`. It does not send messages or create ERP records.

It produces three outcomes:

- `approved`: complete, ordinary request that may proceed to the next controlled stage
- `request_clarification`: required information is missing
- `requires_human_approval`: safety-sensitive or commercial/offer-related request

Safety-related requests and offer/extension requests always require human approval, regardless of model confidence.

## Run

```powershell
python ApprovalAgent\approval_agent.py
```

Or specify an input explicitly:

```powershell
python ApprovalAgent\approval_agent.py --input EmailValidationAgent\runs\latest.json
```

Output:

```text
ApprovalAgent/runs/latest.json
```
