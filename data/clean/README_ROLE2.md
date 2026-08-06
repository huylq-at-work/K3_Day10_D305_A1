# Role 2 clean schema and CP1 validation

## Stable ID and parsing

- `paper_id`: normalized Crossref DOI (lowercase, with `doi:` / `https://doi.org/` removed).
- Required raw fields: `paper_id`, `title`, `summary`, and a valid `published` date. Invalid records are dropped.
- Crossref JATS/XML is stripped from `abstract` before it becomes `summary`.
- Date priority is `published -> issued -> created`; a missing month/day becomes `01`.
- `updated` uses `deposited`, falling back to `published`.
- Optional string fields (`abs_url`, `pdf_url`, `comment`) use `""`, never null.

## Clean rules

- Text whitespace is normalized; authors/categories are ordered and deduplicated case-insensitively.
- Missing authors/categories become `["Unknown"]` so downstream metadata never receives null.
- Category priority is `subject -> container-title -> type`. This fallback is needed because the CP1 payload has no `subject` values.
- Duplicate records are identified by normalized `paper_id`. Keep the newest `updated` row, then the longest summary.
- `published` and `updated` are ISO `YYYY-MM-DD` strings.
- `age_days = run_date_utc.date() - published.date()`.
- `text_for_embedding` contains labeled `title`, `authors_joined`, `categories_joined`, and `summary` (abstract). IDs, URLs, dates, and comments are metadata, not embedding text.

The fixed column order is defined by `ingestion.cleaning.CLEAN_COLUMNS`.

## Run CP1 sample validation

From the project root:

```bash
python script/validate_role2.py --run-date 2026-08-06
```

This reads `data/raw/crossref_response.json`, writes parsed raw records and clean CSV/JSON, then writes `data/clean/cp1_validation.json`. A failed contract check exits non-zero.
