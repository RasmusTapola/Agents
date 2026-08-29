# Business process simulator

This is a safe, local training environment for learning how an AI-assisted field-service workflow could operate.

It simulates:

```text
customer email
  -> intake agent
  -> structured request
  -> customer/site validation
  -> work-order draft
  -> human approval
  -> simulated ERP work order
  -> technician report
  -> customer report and invoice draft
```

All records are synthetic. Nothing is sent to Gmail, an ERP, a customer, or a technician.

## Run it

From the repository root:

```powershell
python BusinessProcessSimulator\simulate_workflow.py
```

To inspect the generated event log:

```powershell
Get-Content BusinessProcessSimulator\runs\latest.json
```

The simulator deliberately keeps AI decisions bounded. The agents extract and propose; validation, approval, and ERP actions are handled by ordinary program logic.

## What to change next

1. Add more synthetic emails, including incomplete or ambiguous requests.
2. Add a simulated approval rejection and correction loop.
3. Replace the deterministic intake agent with the local Ollama model used by `GmailAgent`.
4. Replace the simulated ERP adapter with a test API adapter.
5. Add metrics such as processing time, confidence, exception rate, and human-touch rate.
