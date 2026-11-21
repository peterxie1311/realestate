"""Browser scraping and text extraction for realestate.com.au.

Responsibilities:
  * Navigate pages with Playwright and retry blank pages.
  * Convert page text/HTML into a property dictionary using pyparser.
  * Offer compatibility entry points used by existing scripts.

Database writes belong to pyDB; the batch orchestrator calls it explicitly.
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime
from urllib.parse import urlencode

from playwright.sync_api import Page, Playwright, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import pyBrowser
import pyDB
import pyparser

CDP_URL = "http://localhost:9222"
HOME_URL = "https://www.realestate.com.au/"


def _open_page(playwright: Playwright) -> Page:
    """Open a tab in the shared Chrome/Chromium debugging session."""
    if not pyBrowser.is_port_open() and not pyBrowser.initBrowser(20):
        raise RuntimeError("Could not start Chrome/Chromium on port 9222")
    browser = playwright.chromium.connect_over_cdp(CDP_URL)
    return browser.contexts[0].new_page()


def _page_has_content(page: Page) -> bool:
    """Wait for JavaScript-rendered body text; return False if still blank."""
    try:
        page.wait_for_function(
            "() => document.body && document.body.innerText.trim().length > 0",
            timeout=5000,
        )
        return True
    except PlaywrightTimeoutError:
        return False


def goto_listing(page: Page, url: str) -> None:
    """Navigate once, then reload up to three times if the body is blank."""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if _page_has_content(page):
        return

    for attempt in range(1, 4):
        print(f"Blank page; refreshing {attempt}/3: {url}")
        page.reload(wait_until="domcontentloaded", timeout=10000)
        if _page_has_content(page):
            return

    raise RuntimeError(f"Page stayed blank after three refreshes: {url}")


def _extract_property(page: Page, url: str) -> dict:
    """Read a loaded page and build the database-ready property dictionary."""
    now = datetime.now().isoformat()
    text = page.locator("body").inner_text()
    title = page.title()
    html = page.content()

    return {
        "source": "realestate" if "realestate.com.au" in url else "unknown",
        "listing_url": url,
        "listing_id": pyparser.extract_listing_id(url, text),
        "first_seen_at": now,
        "last_seen_at": now,
        "scraped_at": now,
        "title": title,
        "description": None,
        **pyparser.extract_address_parts(title),
        **pyparser.parse_realestate_top_block(text),
        **pyparser.parse_extra_fields(text),
        **pyparser.extract_coordinates(html),
        "status": "watching",
        "raw_text": text,
        "html_content": html,
    }


def reParseDb(bodyText: str) -> dict:
    """Reparse already-stored text without opening a browser."""
    return {
        **pyparser.parse_realestate_top_block(bodyText),
        **pyparser.parse_extra_fields(bodyText),
        **pyparser.getBuildingAndLand(bodyText),
    }


def fetchPageDataBatch(
    url: str,
    is_init: bool,
    shouldClose: bool,
    oldPage: Page | None,
    p: Playwright,
) -> tuple[dict, Page]:
    """Compatibility API for the existing batch scraper.

    is_init=True reuses oldPage. shouldClose=True closes it after extraction.
    The returned page can be reused on the next call when left open.
    """
    if is_init and (oldPage is None or oldPage.is_closed()):
        raise ValueError("is_init=True requires an open oldPage")

    page = oldPage if is_init else _open_page(p)
    try:
        goto_listing(page, url)
        return _extract_property(page, url), page
    except Exception:
        if not page.is_closed():
            page.close()
        raise
    finally:
        if shouldClose and not page.is_closed():
            page.close()


def fetchPageData(url: str, is_init: bool = False, isJustVisitng: bool = False) -> dict | None:
    """Fetch a single property. Legacy flags are retained for callers."""
    with sync_playwright() as playwright:
        page = _open_page(playwright)
        try:
            goto_listing(page, url)
            if isJustVisitng:
                return None
            return _extract_property(page, url)
        finally:
            page.close()


def searchPropertyInfo(address: str) -> list[dict]:
    """Find property.com.au search-result links for an address."""
    query = f'site:property.com.au "{address}"'
    url = "https://www.google.com/search?" + urlencode({"q": query})
    with sync_playwright() as playwright:
        page = _open_page(playwright)
        try:
            goto_listing(page, url)
            return page.eval_on_selector_all(
                'a[href*="property.com.au"]',
                """links => links.map(a => ({
                    href: a.href.split("#")[0],
                    text: a.innerText.trim()
                }))""",
            )
        finally:
            page.close()


def fetch_listing_links(search_url: str, is_sold: bool, maxpagenum: int) -> list[str]:
    """Collect links from a legacy paginated list search, then save them."""
    # Escaped dots match literal dots in the domain name.
    # /sold/property- distinguishes sold listings from active listings.
    pattern = (
        r"realestate\.com\.au/sold/property-"
        if is_sold else r"realestate\.com\.au/property-"
    )
    links: list[str] = []
    seen: set[str] = set()

    with sync_playwright() as playwright:
        page = _open_page(playwright)
        try:
            for page_number in range(1, maxpagenum):
                # Replace 'list-' followed by one or more digits with the new page.
                url = re.sub(r"list-\d+", f"list-{page_number}", search_url)
                goto_listing(page, url)
                page.wait_for_timeout(3000)
                hrefs = page.eval_on_selector_all(
                    "a[href]", "links => links.map(a => a.href)"
                )
                for href in hrefs:
                    if re.search(pattern, href):
                        clean_url = href.split("?", 1)[0]
                        if clean_url not in seen:
                            seen.add(clean_url)
                            links.append(clean_url)
        finally:
            page.close()

    pyDB.insert_links(links)
    return links


def parse_links(tries: int = 0) -> list[dict]:
    """Scrape missing saved links; retry each failed link up to three times."""
    results: list[dict] = []
    links = pyDB.get_links()
    for index, link in enumerate(links, 1):
        for attempt in range(tries, 3):
            try:
                print(f"Scraping {index}/{len(links)}: {link}")
                data = fetchPageData(link)
                pyDB.insert_property(data)
                results.append(data)
                break
            except Exception as exc:
                print(f"Failed {link} (attempt {attempt + 1}/3): {exc}")
                if attempt == 2:
                    print(f"Giving up on {link} for this run")
                else:
                    time.sleep(3)
        time.sleep(random.uniform(2, 5))
        if index % 50 == 0 and index < len(links):
            print("Taking a two-minute break...")
            time.sleep(120)
    return results
