"""Probe INSEE Sirene v3.11 query syntax to find what works.

Run: uv run probe.py
"""
import os
import sys
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.insee.fr/api-sirene/3.11/siret"


def try_query(client: httpx.Client, label: str, q: str, api_key: str) -> None:
    resp = client.get(
        BASE_URL,
        headers={
            "X-INSEE-Api-Key-Integration": api_key,
            "Accept": "application/json",
        },
        params={"q": q, "nombre": 1, "curseur": "*"},
    )
    if resp.is_success:
        total = resp.json().get("header", {}).get("total", "?")
        print(f"  [OK  {resp.status_code}] total={total}  ::  {label}")
    elif resp.status_code == 404:
        print(f"  [OK  404 zero] :: {label}")
    else:
        msg = resp.json().get("header", {}).get("message", resp.text[:120])
        print(f"  [FAIL {resp.status_code}] {msg}  ::  {label}")
        print(f"       q = {q}")


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("INSEE_API_KEY")
    if not api_key:
        sys.exit("INSEE_API_KEY manquante")

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    d = f"[{monday} TO {today}]"

    cases = [
        ("date seule", f"dateCreationEtablissement:{d}"),
        ("date + commune wildcard", f"dateCreationEtablissement:{d} AND codeCommuneEtablissement:76*"),
        ("date + commune via periode()", f"dateCreationEtablissement:{d} AND periode(codeCommuneEtablissement:76*)"),
        ("date + NAF direct (avec point, sans quotes)", f"dateCreationEtablissement:{d} AND activitePrincipaleEtablissement:69.10Z"),
        ("date + NAF direct (avec quotes)", f'dateCreationEtablissement:{d} AND activitePrincipaleEtablissement:"69.10Z"'),
        ("date + NAF via periode() sans quotes", f"dateCreationEtablissement:{d} AND periode(activitePrincipaleEtablissement:69.10Z)"),
        ("date + NAF via periode() avec quotes", f'dateCreationEtablissement:{d} AND periode(activitePrincipaleEtablissement:"69.10Z")'),
        ("date + NAF sans point", f"dateCreationEtablissement:{d} AND periode(activitePrincipaleEtablissement:6910Z)"),
        ("tout combiné (periode wrappers)", f"dateCreationEtablissement:{d} AND periode(codeCommuneEtablissement:76*) AND periode(activitePrincipaleEtablissement:69.10Z)"),
    ]

    with httpx.Client(timeout=30.0) as client:
        for label, q in cases:
            try_query(client, label, q, api_key)


if __name__ == "__main__":
    main()
