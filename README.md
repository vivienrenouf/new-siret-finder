# new-siret-finder

Petit script Python qui interroge l'**API Sirene de l'INSEE (v3.11)** pour récupérer les SIRET créés cette semaine dans les départements de ton choix, filtrés par codes NAF, et exporte le tout en fichier Excel.

Pré-rempli pour : **départements 76 & 27**, périmètre **professions libérales**.

---

## Pré-requis

1. **Python 3.14** — si tu n'as pas Python à jour, le plus simple est d'installer `uv` qui s'occupera de tout :
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Une clé API INSEE** — gratuite, à créer ici : https://portail-api.insee.fr/
   - Crée un compte
   - Souscris à l'API "Sirene - V3.11"
   - Récupère ta clé (champ "Clé d'intégration" / `X-INSEE-Api-Key-Integration`)

---

## Installation

```bash
git clone https://github.com/<ton-user>/new-siret-finder.git
cd new-siret-finder
uv sync
```

`uv sync` télécharge automatiquement Python 3.14 si besoin et installe les dépendances (`httpx`, `pandas`, `openpyxl`, `python-dotenv`).

---

## Configuration

Copie le template d'environnement et remplis-le :

```bash
cp .env.example .env
```

Puis ouvre `.env` et :
- Colle ta clé INSEE dans `INSEE_API_KEY`
- Ajuste `DEPARTMENTS` (codes INSEE, séparés par virgules — ex : `76,27,14`)
- Ajuste `NAF_CODES` si tu veux un autre périmètre métier

Le fichier `.env` est dans le `.gitignore` — il ne sera **jamais** poussé sur GitHub.

---

## Utilisation

```bash
uv run main.py
```

Tu verras s'afficher :
```
Fenêtre : 2026-05-18 → 2026-05-22 | départements 76,27 | 24 codes NAF
  page 1: 32 résultats (total 32)
32 SIRET trouvés → output/siret_76-27_2026-05-18_2026-05-22.xlsx
```

Le fichier Excel atterrit dans `output/`, nommé avec les départements et la fenêtre de dates.

---

## Colonnes de l'Excel

| Colonne | Description |
|---|---|
| `siret` | Numéro SIRET (14 chiffres) |
| `denomination` | Nom de l'entreprise (ou nom/prénom pour les personnes physiques) |
| `enseigne` | Enseigne commerciale (si différente) |
| `adresse` | Adresse de l'établissement |
| `code_postal` | Code postal |
| `commune` | Commune |
| `date_creation` | Date de création de l'établissement |
| `type_creation` | `Nouvelle entreprise` (SIREN tout neuf) ou `Nouvel établissement` (entreprise existante) |
| `date_creation_entreprise` | Date de création du SIREN |
| `naf` | Code NAF Rev. 2 |
| `naf_libelle` | Libellé du code NAF |

⚠️ **Note sur les `[ND]`** : certains entrepreneurs individuels exercent leur droit à la non-diffusion. Pour ces SIRET, le nom, l'adresse et l'enseigne apparaissent en `[ND]` (Non Diffusable). Seuls SIRET, commune, date et NAF restent visibles. C'est une protection RGPD côté INSEE.

⚠️ **Note sur le téléphone** : la base Sirene **ne contient pas** de numéros de téléphone ni d'emails. Pour enrichir avec des contacts, il faut une source tierce (Pages Jaunes, Pappers, etc.).

---

## Personnaliser les codes NAF

Si tu ajoutes des codes NAF dans `.env`, pense aussi à ajouter leur libellé dans le dict `NAF_LABELS` en haut de [main.py](main.py) — sinon la colonne `naf_libelle` sera vide pour ces codes.

---

## Dépannage

**`INSEE_API_KEY manquante`** → tu n'as pas créé `.env` ou la variable est vide.

**`400 - Erreur de syntaxe dans le paramètre q`** → généralement un code NAF mal formaté (utiliser le format `69.10Z` avec le point). Lance `uv run probe.py` pour tester la syntaxe.

**Aucun résultat** → c'est probablement normal en début de semaine (lundi/mardi), peu d'établissements ont eu le temps d'être créés. Vérifie en élargissant la fenêtre.
