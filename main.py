import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

BASE_URL = "https://api.insee.fr/api-sirene/3.11/siret"
PAGE_SIZE = 1000
TIMEOUT = httpx.Timeout(30.0)
OUTPUT_DIR = Path(__file__).parent / "output"

NAF_LABELS = {
    "69.10Z": "Activités juridiques",
    "69.20Z": "Activités comptables",
    "70.21Z": "Conseil en relations publiques et communication",
    "70.22Z": "Conseil pour les affaires et autres conseils de gestion",
    "71.11Z": "Activités d'architecture",
    "71.12A": "Activité des géomètres",
    "71.12B": "Ingénierie, études techniques",
    "71.20B": "Analyses, essais et inspections techniques",
    "74.10Z": "Activités spécialisées de design",
    "74.20Z": "Activités photographiques",
    "74.30Z": "Traduction et interprétation",
    "74.90A": "Activité des économistes de la construction",
    "74.90B": "Activités spécialisées, scientifiques et techniques diverses",
    "75.00Z": "Activités vétérinaires",
    "85.59A": "Formation continue d'adultes",
    "85.59B": "Autres enseignements",
    "86.21Z": "Activité des médecins généralistes",
    "86.22A": "Activités de radiodiagnostic et de radiothérapie",
    "86.22B": "Activités chirurgicales",
    "86.22C": "Autres activités des médecins spécialistes",
    "86.23Z": "Pratique dentaire",
    "86.90D": "Activités des infirmiers et des sages-femmes",
    "86.90E": "Activités des professionnels de la rééducation, de l'appareillage et des pédicures-podologues",
    "86.90F": "Activités de santé humaine non classées ailleurs",
}


def week_window(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, today


def _parse_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_query(start: date, end: date, departments: list[str], naf_codes: list[str]) -> str:
    date_clause = f"dateCreationEtablissement:[{start} TO {end}]"
    dept_clause = " OR ".join(f"codeCommuneEtablissement:{d}*" for d in departments)
    naf_inner = " OR ".join(f"activitePrincipaleEtablissement:{n}" for n in naf_codes)
    naf_clause = f"periode({naf_inner})"
    return f"{date_clause} AND ({dept_clause}) AND {naf_clause}"


def fetch_all_siret(query: str, api_key: str) -> list[dict]:
    headers = {
        "X-INSEE-Api-Key-Integration": api_key,
        "Accept": "application/json",
    }
    etablissements: list[dict] = []
    cursor = "*"
    page = 0

    with httpx.Client(timeout=TIMEOUT) as client:
        while True:
            page += 1
            resp = client.get(
                BASE_URL,
                headers=headers,
                params={"q": query, "nombre": PAGE_SIZE, "curseur": cursor},
            )
            if resp.status_code == 404:
                # INSEE returns 404 when zero results match.
                break
            if resp.is_error:
                sys.exit(
                    f"INSEE {resp.status_code} sur la requête:\n"
                    f"  q = {query}\n"
                    f"  réponse = {resp.text}"
                )
            payload = resp.json()
            batch = payload.get("etablissements", [])
            etablissements.extend(batch)
            next_cursor = payload.get("header", {}).get("curseurSuivant")
            print(
                f"  page {page}: {len(batch)} résultats (total {len(etablissements)})",
                file=sys.stderr,
            )
            if not next_cursor or next_cursor == cursor or not batch:
                break
            cursor = next_cursor

    return etablissements


def _denomination(unite: dict) -> str:
    nom = unite.get("denominationUniteLegale")
    if nom:
        return nom
    prenom = unite.get("prenom1UniteLegale") or ""
    nom_personne = unite.get("nomUniteLegale") or ""
    return f"{prenom} {nom_personne}".strip()


def _latest_periode(etab: dict) -> dict:
    periodes = etab.get("periodesEtablissement") or []
    return periodes[0] if periodes else {}


def _adresse(adr: dict) -> str:
    parts = [
        adr.get("numeroVoieEtablissement"),
        adr.get("typeVoieEtablissement"),
        adr.get("libelleVoieEtablissement"),
    ]
    return " ".join(p for p in parts if p)


def _departement(adr: dict) -> str | None:
    code = adr.get("codeCommuneEtablissement")
    if not code:
        return None
    if code.startswith(("2A", "2B")):
        return code[:2]
    if code.startswith(("97", "98")):
        return code[:3]
    return code[:2]


def flatten(etab: dict) -> dict:
    unite = etab.get("uniteLegale", {})
    adr = etab.get("adresseEtablissement", {})
    periode = _latest_periode(etab)
    date_etab = etab.get("dateCreationEtablissement")
    date_unite = unite.get("dateCreationUniteLegale")
    if date_etab and date_unite:
        type_creation = "Nouvelle entreprise" if date_etab == date_unite else "Nouvel établissement"
    else:
        type_creation = None
    return {
        "siret": etab.get("siret"),
        "denomination": _denomination(unite),
        "enseigne": periode.get("enseigne1Etablissement"),
        "adresse": _adresse(adr),
        "code_postal": adr.get("codePostalEtablissement"),
        "commune": adr.get("libelleCommuneEtablissement"),
        "departement": _departement(adr),
        "date_creation": date_etab,
        "type_creation": type_creation,
        "date_creation_entreprise": date_unite,
        "naf": periode.get("activitePrincipaleEtablissement"),
        "naf_libelle": NAF_LABELS.get(periode.get("activitePrincipaleEtablissement", "")),
    }


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("INSEE_API_KEY")
    if not api_key:
        sys.exit("INSEE_API_KEY manquante (définir dans .env)")
    departments = _parse_csv_env("DEPARTMENTS")
    if not departments:
        sys.exit("DEPARTMENTS manquant (définir dans .env, ex: 76,27)")
    naf_codes = _parse_csv_env("NAF_CODES")
    if not naf_codes:
        sys.exit("NAF_CODES manquant (définir dans .env)")

    start, end = week_window(date.today())
    print(
        f"Fenêtre : {start} → {end} | départements {','.join(departments)} "
        f"| {len(naf_codes)} codes NAF",
        file=sys.stderr,
    )

    query = build_query(start, end, departments, naf_codes)
    etablissements = fetch_all_siret(query, api_key)
    rows = [flatten(e) for e in etablissements]
    df = pd.DataFrame(rows, columns=[
        "siret", "denomination", "enseigne", "adresse",
        "code_postal", "commune", "departement", "date_creation",
        "type_creation", "date_creation_entreprise", "naf", "naf_libelle",
    ])

    OUTPUT_DIR.mkdir(exist_ok=True)
    dept_tag = "-".join(departments)
    out = OUTPUT_DIR / f"siret_{dept_tag}_{start}_{end}.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for dept in departments:
            sub = df[df["departement"] == dept]
            sub.to_excel(writer, sheet_name=dept, index=False)
        others = df[~df["departement"].isin(departments)]
        if not others.empty:
            others.to_excel(writer, sheet_name="Autres", index=False)
    counts = ", ".join(f"{d}={len(df[df['departement'] == d])}" for d in departments)
    print(f"{len(df)} SIRET trouvés ({counts}) → {out}")


if __name__ == "__main__":
    main()
