"""Read-only EspoCRM account and contact resolution."""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

import requests


DEFAULT_URL = "http://localhost:8080"
DEFAULT_KEY_FILE = Path(__file__).resolve().parent.parent / "key.txt"


def normalize_text(value: str | None) -> str:
    """Normalize human-entered CRM names for safe comparison."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


class EspoCRMClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 15):
        self.base_url = (base_url or os.environ.get("ESPOCRM_URL", DEFAULT_URL)).rstrip("/")
        self.api_key = api_key or os.environ.get("ESPOCRM_API_KEY")
        if not self.api_key:
            key_file = Path(os.environ.get("ESPOCRM_API_KEY_FILE", str(DEFAULT_KEY_FILE)))
            if key_file.exists():
                raw_key = key_file.read_text(encoding="utf-8").strip()
                # Accept either a raw key or a copied PowerShell assignment.
                match = re.match(r"^\$env:ESPOCRM_API_KEY\s*=\s*[\"']?(.*?)[\"']?$", raw_key)
                self.api_key = match.group(1).strip() if match else raw_key
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("ESPOCRM_API_KEY is not set")

    def get(self, entity: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{self.base_url}/api/v1/{quote(entity, safe='')}",
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
            params=params or {},
            timeout=self.timeout,
        )
        if response.status_code in (401, 403):
            reason = response.headers.get("X-Status-Reason", "No reason returned")
            raise RuntimeError(
                f"EspoCRM rejected the request with HTTP {response.status_code}. "
                f"Check the API user's authentication method and role permissions. "
                f"EspoCRM reason: {reason}"
            )
        response.raise_for_status()
        return response.json()

    def find_account_by_name(self, name: str) -> dict:
        return self.get("Account", {
            "select": "id,name,phoneNumber,emailAddress,billingAddressStreet,billingAddressCity",
            "maxSize": 10,
            "where": json.dumps([{"type": "equals", "attribute": "name", "value": name}]),
        })

    def find_contact_by_email(self, email: str) -> dict:
        return self.get("Contact", {
            "select": "id,name,firstName,lastName,emailAddress,phoneNumber,accountId,accountName",
            "maxSize": 10,
            "where": json.dumps([{"type": "equals", "attribute": "emailAddress", "value": email}]),
        })

    def resolve_account(self, name: str) -> dict:
        response = self.find_account_by_name(name)
        records = response.get("list", [])
        if len(records) == 1:
            return {"status": "matched", "confidence": 1.0, "records": records}
        # Espo's contains search gives the resolver a useful fallback for
        # punctuation, accents, and legal-name variations.
        fallback = self.get("Account", {
            "select": "id,name,phoneNumber,emailAddress,billingAddressStreet,billingAddressCity",
            "maxSize": 20,
            "where": json.dumps([{"type": "contains", "attribute": "name", "value": name}]),
        })
        candidates = [r for r in fallback.get("list", []) if normalize_text(r.get("name")) == normalize_text(name)]
        if len(candidates) == 1:
            return {"status": "matched", "confidence": 0.95, "records": candidates}
        if len(candidates) > 1:
            return {"status": "ambiguous", "confidence": 0.0, "records": candidates}
        return {"status": "not_found", "confidence": 0.0, "records": []}

    def resolve_contact(self, email: str) -> dict:
        response = self.find_contact_by_email(email)
        records = response.get("list", [])
        if len(records) == 1:
            return {"status": "matched", "confidence": 1.0, "records": records}
        if len(records) > 1:
            return {"status": "ambiguous", "confidence": 0.0, "records": records}
        return {"status": "not_found", "confidence": 0.0, "records": []}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="entity", required=True)
    account = sub.add_parser("account")
    account.add_argument("name")
    contact = sub.add_parser("contact")
    contact.add_argument("email")
    args = parser.parse_args()
    client = EspoCRMClient()
    result = client.find_account_by_name(args.name) if args.entity == "account" else client.find_contact_by_email(args.email)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
