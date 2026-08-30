"""Read-only EspoCRM account and contact resolution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests


DEFAULT_URL = "http://localhost:8080"


class EspoCRMClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 15):
        self.base_url = (base_url or os.environ.get("ESPOCRM_URL", DEFAULT_URL)).rstrip("/")
        self.api_key = api_key or os.environ.get("ESPOCRM_API_KEY")
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
