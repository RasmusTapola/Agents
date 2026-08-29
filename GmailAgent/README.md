# Local Gmail reader agent

This prototype reads a small, recent batch of Gmail messages, sends their text to a local Ollama model, and writes a Markdown attention report with proposed Trash actions for likely advertisements, spam, or suspicious messages.

All credentials, tokens, reports, and application files are stored relative to this `GmailAgent` directory, so the program can be launched from any working directory.

The default run does not modify Gmail. A separate `--apply` command asks for confirmation for each proposed message before moving it to Trash.

## Setup

1. Create a Google Cloud project and enable the Gmail API.
2. Configure OAuth consent for a desktop application.
3. Create an OAuth client ID with application type **Desktop app**.
4. Download the JSON file and save it in this folder as `credentials.json`.
5. Install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

6. Start Ollama and make sure the model is available, for example:

   ```powershell
   ollama run qwen3
   ```

7. Run the reader:

   ```powershell
   python gmail_agent.py
   ```

The first run opens a browser for Google authorization and creates `token.json`. The report is written under `reports/`.

## Review and apply actions

Run the analysis/report step first:

```powershell
python gmail_agent.py --query "in:inbox newer_than:2d" --limit 5
```

Review the dated report, for example `reports\mail_report_2026-08-29.md`. If the proposed actions look correct, apply that day's proposals with:

```powershell
python gmail_agent.py --apply --date 2026-08-29
```

The program shows each proposed message from that date and moves it only when you type `yes`. Any other response keeps the message. Each scan also creates a separate `pending_actions_YYYY-MM-DD.json` file, so days can be handled independently.

## Safety

The app uses the `gmail.modify` OAuth scope because Gmail requires it for moving messages to Trash. Keep `credentials.json` and `token.json` private. Start with a small query and review the generated report before applying actions.
