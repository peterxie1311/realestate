"""Reparse previously stored listing text without revisiting realestate.com.au."""
from __future__ import annotations

import argparse

import pyDB
import pyscraper

# Never overwrite listing identity, status, or scraped timestamps during a reparse.
PROTECTED = {
    "id", "listing_id", "listing_url", "listing_status", "status",
    "first_seen_at", "last_seen_at", "scraped_at", "raw_text",
    "html_content", "ai_predicted_fields", "ai_confidence",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without database writes")
    parser.add_argument("--limit", type=int, default=None, help="Maximum rows to process")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    rows = pyDB.get_propertydata()
    total = min(len(rows), args.limit) if args.limit else len(rows)
    updated = skipped = failed = 0

    for index, row in enumerate(rows[:total], 1):
        identity = row.get("id") or row.get("listing_id")
        raw_text = row.get("raw_text")
        if not identity or not isinstance(raw_text, str) or not raw_text.strip():
            skipped += 1
            print(f"[{index}/{total}] Skipped missing identity/raw_text")
            continue
        try:
            parsed = pyscraper.reParseDb(raw_text)
            # Keep existing values when a parser cannot extract a field.
            changes = {
                key: value for key, value in parsed.items()
                if key not in PROTECTED and value is not None
                and key in row and row[key] != value
            }
            if not changes:
                skipped += 1
                continue
            if not args.dry_run:
                selector = {"id": row["id"]} if row.get("id") is not None else {"listing_id": row["listing_id"]}
                pyDB.update_property({**selector, **changes})
            updated += 1
            print(f"[{index}/{total}] {'Would update' if args.dry_run else 'Updated'} {identity}: {', '.join(changes)}")
        except Exception as exc:
            failed += 1
            print(f"[{index}/{total}] Failed {identity}: {exc}")

    print(f"Finished: {'would_update' if args.dry_run else 'updated'}={updated}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
