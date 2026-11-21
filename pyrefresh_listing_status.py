"""Refresh non-sold listing statuses and confirmed sold prices from listing pages."""
from __future__ import annotations

import argparse
import re
import time

from playwright.sync_api import sync_playwright
import pyBrowser
import pyDB
import pyparser
import pyscraper


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.delay < 0:
        parser.error("--delay must not be negative")

    rows = pyDB.executeQueryAll(
        """SELECT id, listing_url FROM public.properties
           WHERE listing_url IS NOT NULL
             AND COALESCE(listing_status, '') <> 'sold'
           ORDER BY id LIMIT %s""",
        (args.limit,), pyDB.result_type_dict,
    )
    changed = failed = 0
    with sync_playwright() as playwright:
        if not pyBrowser.is_port_open() and not pyBrowser.initBrowser(20):
            raise RuntimeError("Could not start Chrome debugging on port 9222")
        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
        try:
            for index, row in enumerate(rows, 1):
                try:
                    pyscraper.goto_listing(page, row["listing_url"])
                    text = page.locator("body").inner_text()
                    parsed = pyparser.parse_realestate_top_block(text)
                    # Only mark sold if the page itself clearly identifies a sale.
                    # A redirect to a sold URL is also a strong indicator.
                    # /sold/property- is a literal URL prefix; re.I ignores case.
                    sold = (
                        parsed.get("listing_status") == "sold"
                        or bool(re.search(r"/sold/property-", page.url, re.I))
                    )
                    status = "sold" if sold else parsed.get("listing_status")
                    if status not in ("sold", "under_contract", "under_offer"):
                        continue
                    fields = {"listing_status": status}
                    if sold:
                        # Never substitute asking price for an undisclosed sale price.
                        price = parsed.get("sold_price")
                        if isinstance(price, int) and price > 0:
                            fields["sold_price"] = price
                        if parsed.get("sold_date"):
                            fields["sold_date"] = parsed["sold_date"]
                    if not args.dry_run:
                        pyDB.update_property({"id": row["id"], **fields})
                    changed += 1
                    print(f"[{index}/{len(rows)}] {'Would update' if args.dry_run else 'Updated'} {row['listing_url']}: {fields}")
                except Exception as exc:
                    failed += 1
                    print(f"[{index}/{len(rows)}] Failed {row['listing_url']}: {exc}")
                finally:
                    if index < len(rows):
                        time.sleep(args.delay)
        finally:
            page.close()
    print(f"Finished: changed={changed}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
