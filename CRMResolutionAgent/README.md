# CRM resolution agent

This is the first real EspoCRM integration. It performs read-only lookups for Accounts and Contacts.

## Configure

Create an EspoCRM API user with a role that has read access to Account and Contact. Copy its API key, then set:

```powershell
$env:ESPOCRM_URL = "http://localhost:8080"
$env:ESPOCRM_API_KEY = "paste-api-key-here"
```

For this local test project, the client also falls back to `C:\var\git\Agents\key.txt` when `ESPOCRM_API_KEY` is not set. Environment variables take precedence. Do not use this file-based fallback for production deployments, and never commit the key file.

EspoCRM uses the `X-Api-Key` header for API-key authentication, and its API root is `/api/v1/`. The official documentation recommends a separate API user with restricted permissions. See [EspoCRM API overview](https://docs.espocrm.com/development/api/).

## Test lookups

```powershell
python CRMResolutionAgent\crm_resolution_agent.py account "Mahtavat masiinat Oy"
python CRMResolutionAgent\crm_resolution_agent.py contact "rasmus.tapola@outlook.com"
```

The agent only issues GET requests. It does not create, update, or delete records.
