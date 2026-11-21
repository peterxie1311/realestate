# Real estate scraping and enrichment

This project collects property listings, stores them in PostgreSQL, and adds AI-generated facts from their descriptions.

## Start here

The **four automatic jobs** are controlled by [run_all_continuously.sh](run_all_continuously.sh).

```text
run_all_continuously.sh
  ├── run_active.sh        → pyparserealestate.py       → discover active listings
  ├── run_sold.sh          → pyparsesoldrealestate.py   → discover sold listings
  ├── run_ai_enrichment.sh → pyenrich_properties_ai.py  → fill AI JSONB fields
  └── run_status_refresh.sh→ pyrefresh_listing_status.py → recheck non-sold listings
```

Each job starts immediately, runs independently, and waits **6 hours after its own run ends** before starting again. A failed job is retried in its next cycle. Logs are in `logs/active.log`, `logs/sold.log`, `logs/ai.log`, and `logs/status.log`.

> The jobs run **concurrently**, not in sequence. The AI job may not see listings discovered later in the same cycle; it will pick them up on a subsequent cycle.

## What each Python file does

| File | Responsibility |
| --- | --- |
| `pyparserealestate.py` | Find active property links on the map, parse and store them |
| `pyparsesoldrealestate.py` | Reuse the map scraper with sold listings and force status to `sold` |
| `pyrefresh_listing_status.py` | Revisit database rows not marked sold; update confirmed statuses and sale prices |
| `pyenrich_properties_ai.py` | Read saved listing text, ask the OpenAI API for supported facts, save JSONB predictions and confidence |
| `pyreparse_existing_db.py` | Reparse existing stored text **offline**, without visiting the website |
| `pyscraper.py` | Browser page fetching and text extraction |
| `pyparser.py` | Extract structured fields from text |
| `pyBrowser.py` | Find or launch Chrome/Chromium with remote debugging |
| `pyDB.py` | PostgreSQL queries, inserts and updates |

**Status refresh and sold discovery are different:** sold discovery starts from the sold-results map; status refresh revisits properties you already know about.

## First-time setup (Linux)

1. Install Python 3, Python venv, Chrome or Chromium, and PostgreSQL client dependencies.
2. Create a `.env` file in the project directory with `dbuser`, `dbpassword`, `dbhost`, `dbport`, `dbname`, and `OPENAI_API_KEY`. **Never commit this file.**
3. Run `bash install_ai_enrichment.sh` for the AI dependencies. Other scraper dependencies (including Playwright) must also be installed in the Python environment.
4. Apply [sql/add_ai_prediction_fields.sql](sql/add_ai_prediction_fields.sql) once to add `ai_predicted_fields` and `ai_confidence` to `properties`.
5. Test jobs individually before starting the continuous launcher.

The installation script currently sets up **AI dependencies only**, not the entire scraper environment.

## Run a job once

```bash
bash run_active.sh
bash run_sold.sh
bash run_status_refresh.sh --dry-run --limit 10
bash run_ai_enrichment.sh --dry-run --limit 5
bash run_reparse_db.sh --dry-run --limit 10
```

AI dry-run still **calls the paid API**; it only prevents database writes.

## Run continuously

```bash
bash run_all_continuously.sh
```

Change the cooldown to one hour for testing:

```bash
INTERVAL_SECONDS=3600 bash run_all_continuously.sh
```

To launch by double-clicking, configure your Linux file manager to **execute** shell scripts rather than open them in an editor. You may need `chmod +x run_all_continuously.sh` locally. GitHub-created files may not have the executable bit set. Keep the terminal session open while running.

## Important behaviour and limitations

- The scraper and status checker share a Chrome remote-debugging endpoint on port `9222`. Test concurrent runs before relying on unattended operation.
- Sold price is only saved when the parser extracts it; an undisclosed price is not estimated.
- AI fields are **predictions**, not verified property facts. They are stored in JSONB columns on `properties`, not in a separate AI table.
- A six-hour cooldown is **not** a fixed wall-clock schedule. A three-hour scrape followed by a six-hour sleep starts again nine hours after its previous start.
- The scripts have not been end-to-end tested here against your website, API account or database. Back up PostgreSQL before running bulk updates.

## Suggested reading order

Read `run_all_continuously.sh` first, then `pyparsesoldrealestate.py` (a small wrapper), then `pyparserealestate.py`, `pyscraper.py`, `pyparser.py`, and finally `pyDB.py`. Read the AI and status scripts separately after that.
