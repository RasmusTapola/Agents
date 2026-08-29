# Local Gmail reader agent

This prototype reads a small, recent batch of Gmail messages, sends their text to a local Ollama model, and writes a Markdown attention report.

It is intentionally read-only. It does not modify Gmail in any way.

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

## Safety

The app uses the `gmail.readonly` OAuth scope. Keep `credentials.json` and `token.json` private. Start with a small query and review the generated report before adding any write capability.

