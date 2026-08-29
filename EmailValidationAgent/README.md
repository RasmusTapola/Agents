# Email validation agent

This agent consumes the review-only JSON handoff produced by `GmailAgent` and decides what should happen next.

It does not connect to Gmail, send email, create ERP records, or modify the source JSON.

## Run

From the repository root:

```powershell
python EmailValidationAgent\email_validation_agent.py --input GmailAgent\reports\work_order_candidates_2026-08-29.json
```

If `--input` is omitted, the newest `GmailAgent/reports/work_order_candidates_*.json` file is used.

The result is written to `EmailValidationAgent/runs/latest.json` and contains one of these decisions:

- `approved_for_next_stage`: enough information and confidence for a later controlled agent
- `request_clarification`: a draft question is generated, but not sent
- `escalate_to_human`: the request is too risky, ambiguous, or incomplete for automation

The current policy is intentionally conservative. It is a learning scaffold, not a production authorization policy.
