"""Nightly entry point for parsing active realestate.com.au listings."""

from __future__ import annotations

import argparse
import random
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import Page, Playwright, sync_playwright

import pyBrowser
import pyDB
import pyscraper


DEFAULT_SEARCH_URL = (
    "https://www.realestate.com.au/buy/map-1?"
    "boundingBox=-27.281273773934707%2C152.60608176998488%2C"
    "-27.97357566406785%2C153.19659690670363"
    "&sourcePage=map&sourceElement=location-tile-search"
)

ACTIVE_PROPERTY_LINK_PATTERN = re.compile(
    r"^https://www\.realestate\.com\.au/property-[^?#]+$",
    re.IGNORECASE,
)

SOLD_PROPERTY_LINK_PATTERN = re.compile(
    r"^https://www\.realestate\.com\.au/sold/property-[^?#]+$",
    re.IGNORECASE,
)


@dataclass
class ParseSummary:
    discovered: int = 0
    parsed: int = 0
    failed: int = 0


def _normalise_listing_url(url: str, listing_kind: str) -> str | None:
    clean_url = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    pattern = (
        SOLD_PROPERTY_LINK_PATTERN
        if listing_kind == "sold"
        else ACTIVE_PROPERTY_LINK_PATTERN
    )
    if pattern.match(clean_url):
        return clean_url
    return None


def _links_on_page(page: Page, listing_kind: str) -> set[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(element => element.href)",
    )
    return {
        clean_url
        for href in hrefs
        if (clean_url := _normalise_listing_url(href, listing_kind)) is not None
    }


def _scroll_search_results(page: Page) -> None:
    """Scroll the window and any lazy-loaded results panels on the map page."""
    page.evaluate(
        """
        () => {
            window.scrollTo(0, document.body.scrollHeight);

            for (const element of document.querySelectorAll('*')) {
                const style = window.getComputedStyle(element);
                const scrollable = ['auto', 'scroll'].includes(style.overflowY);

                if (scrollable && element.scrollHeight > element.clientHeight) {
                    element.scrollTop = element.scrollHeight;
                }
            }
        }
        """
    )


def collect_listing_links(
    search_url: str = DEFAULT_SEARCH_URL,
    *,
    listing_kind: str = "active",
    max_scrolls: int = 100,
    stable_rounds: int = 5,
    wait_ms: int = 1_500,
) -> list[str]:
    """Collect every active property URL currently exposed by a map search."""
    if max_scrolls < 1:
        raise ValueError("max_scrolls must be at least 1")
    if stable_rounds < 1:
        raise ValueError("stable_rounds must be at least 1")
    if listing_kind not in {"active", "sold"}:
        raise ValueError("listing_kind must be 'active' or 'sold'")

    with sync_playwright() as playwright:
        if not pyBrowser.is_port_open():
            pyBrowser.initBrowser(3)

        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
        links: set[str] = set()
        unchanged_rounds = 0

        try:
            pyscraper.goto_listing(page, search_url)

            for scroll_number in range(1, max_scrolls + 1):
                previous_count = len(links)
                links.update(_links_on_page(page, listing_kind))

                print(
                    f"Map scan {scroll_number}/{max_scrolls}: "
                    f"{len(links)} unique listings"
                )

                if len(links) == previous_count:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0

                if unchanged_rounds >= stable_rounds:
                    break

                _scroll_search_results(page)
                page.wait_for_timeout(wait_ms)

            # Capture any cards loaded by the final scroll.
            links.update(_links_on_page(page, listing_kind))
        finally:
            page.close()

    return sorted(links)


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def mark_existing_listing_status(
    listing_urls: list[str],
    listing_status: str,
) -> None:
    """Apply the search's authoritative status to already-known rows."""
    if not listing_urls:
        return

    pyDB.executeProcedure(
        """
        UPDATE properties
           SET listing_status = %s,
               last_seen_at = %s
         WHERE listing_url = ANY(%s)
        """,
        (
            listing_status,
            datetime.now(timezone.utc),
            listing_urls,
        ),
    )


def _parse_batch(
    playwright: Playwright,
    listing_urls: list[str],
    summary: ParseSummary,
    *,
    listing_status: str,
    delay_min: float,
    delay_max: float,
) -> None:
    page: Page | None = None

    for index, listing_url in enumerate(listing_urls, start=1):
        close_page = index == len(listing_urls)

        try:
            data, returned_page = pyscraper.fetchPageDataBatch(
                listing_url,
                page is not None,
                close_page,
                page,
                playwright,
            )

            # The search URL is authoritative; never infer status from page text.
            data["listing_status"] = listing_status
            data["status"] = "watching"
            data["last_seen_at"] = datetime.now(timezone.utc).isoformat()

            pyDB.insert_property(data)
            summary.parsed += 1
            page = None if close_page else returned_page

            print(
                f"Parsed {summary.parsed + summary.failed}/{summary.discovered}: "
                f"{listing_url}"
            )
        except Exception as exc:
            summary.failed += 1
            print(f"Failed {listing_url}: {exc}")

            if page is not None and not page.is_closed():
                page.close()
            page = None

        if not close_page:
            time.sleep(random.uniform(delay_min, delay_max))

    if page is not None and not page.is_closed():
        page.close()


def parse_all_realestate(
    search_url: str = DEFAULT_SEARCH_URL,
    *,
    listing_kind: str = "active",
    listing_status: str = "active",
    batch_size: int = 25,
    max_scrolls: int = 100,
    stable_rounds: int = 5,
    delay_min: float = 2.0,
    delay_max: float = 5.0,
    batch_pause: float = 120.0,
) -> ParseSummary:
    """Discover, mark and refresh every listing in the supplied map search."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if delay_min < 0 or delay_max < delay_min:
        raise ValueError("delay range is invalid")

    listing_urls = collect_listing_links(
        search_url,
        listing_kind=listing_kind,
        max_scrolls=max_scrolls,
        stable_rounds=stable_rounds,
    )
    summary = ParseSummary(discovered=len(listing_urls))

    if not listing_urls:
        print("No property listing links were found; nothing was changed.")
        return summary

    pyDB.insert_links(listing_urls)
    mark_existing_listing_status(listing_urls, listing_status)

    batches = list(_chunks(listing_urls, batch_size))

    with sync_playwright() as playwright:
        for batch_number, batch in enumerate(batches, start=1):
            print(
                f"Starting batch {batch_number}/{len(batches)} "
                f"({len(batch)} listings)"
            )
            _parse_batch(
                playwright,
                batch,
                summary,
                listing_status=listing_status,
                delay_min=delay_min,
                delay_max=delay_max,
            )

            if batch_number < len(batches) and batch_pause > 0:
                print(f"Batch complete; pausing for {batch_pause:.0f} seconds")
                time.sleep(batch_pause)

    print(
        "Finished realestate parse: "
        f"discovered={summary.discovered}, "
        f"parsed={summary.parsed}, failed={summary.failed}"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse every active listing exposed by a realestate.com.au map search."
    )
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-scrolls", type=int, default=100)
    parser.add_argument("--stable-rounds", type=int, default=5)
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=5.0)
    parser.add_argument("--batch-pause", type=float, default=120.0)
    args = parser.parse_args()

    summary = parse_all_realestate(
        args.search_url,
        listing_kind="active",
        listing_status="active",
        batch_size=args.batch_size,
        max_scrolls=args.max_scrolls,
        stable_rounds=args.stable_rounds,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        batch_pause=args.batch_pause,
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
