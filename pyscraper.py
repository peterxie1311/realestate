# import re
# import socket
# import time
# from playwright.sync_api import sync_playwright, TimeoutError
# import subprocess
# import os

# urlGlobal = "https://www.realestate.com.au/sold/property-apartment-qld-south+brisbane-151354844"




# #--- Im just not too sure about how good this is but we will see.
# def parseRealEstateTopblock(text: str) -> dict:
#     lines = [line.strip() for line in text.splitlines() if line.strip()]

#     result = {
#         "bedrooms": None,
#         "bathrooms": None,
#         "car_spaces": None,
#         "land_size_sqm": None,
#         "property_type": None,
#         "price_text": None,
#         "price_min": None,
#         "price_max": None,
#         "listing_status": None,
#     }

#     for i, line in enumerate(lines):
#         if line == "•":
#             # With land size: 4, 2, 2, 5,195m², •, House, Price...
#             if i >= 4 and lines[i - 1].endswith("m²"):
#                 result["bedrooms"] = int(lines[i - 4])
#                 result["bathrooms"] = int(lines[i - 3])
#                 result["car_spaces"] = int(lines[i - 2])
#                 result["land_size_sqm"] = int(lines[i - 1].replace("m²", "").replace(",", ""))

#             # Without land size: 2, 2, 1, •, Apartment, For Sale
#             elif i >= 3:
#                 result["bedrooms"] = int(lines[i - 3])
#                 result["bathrooms"] = int(lines[i - 2])
#                 result["car_spaces"] = int(lines[i - 1])

#             result["property_type"] = lines[i + 1] if i + 1 < len(lines) else None
#             result["price_text"] = lines[i + 2] if i + 2 < len(lines) else None
#             break

#     price_text = result["price_text"] or ""

#     if "under contract" in price_text.lower():
#         result["listing_status"] = "under_contract"
#     elif "under offer" in price_text.lower():
#         result["listing_status"] = "under_offer"
#     elif "for sale" in price_text.lower():
#         result["listing_status"] = "for_sale"
#     elif price_text:
#         result["listing_status"] = "active"

#     return result

# def fetchPageData(url:str):
#     with sync_playwright() as p:
#         if not is_port_open():
#             initBrowser(3)
        
#         browser = p.chromium.connect_over_cdp("http://localhost:9222")
#         context = browser.contexts[0]

#         page = context.new_page()
#         page.goto(url, wait_until="domcontentloaded", timeout=30000)
#         try:
#             text = page.evaluate("document.body ? document.body.innerText : ''")
#             data = {}
#             if "realestate" in url:
#                 data = parseRealEstateTopblock(text)

#             return {
#                 "url": url,
#                 "title": page.title(),
#                 **data,
#                 "raw_text": text,
#                 "raw_text_preview": text[:3000],
#             }
#         except TimeoutError as e:
#             print("Could not read page text:", e)

import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import socket
import subprocess
import os
import time
from urllib.parse import urljoin
from dotenv import load_dotenv
from supabase import create_client
import random
import pyparser



load_dotenv()
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_ANON_KEY"]
)

def is_port_open(host="localhost", port=9222) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def initBrowser(checkPortOpenNum: int) -> bool:
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    args = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.expanduser('~/chrome-playwright-profile')}"
    ]
    subprocess.Popen(args)
    for _ in range(checkPortOpenNum):
        if is_port_open():
            return True
        time.sleep(0.5)
    return False





def fetchPageData(url: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        if not is_port_open():
            initBrowser(3)
        
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        text = page.locator("body").inner_text()
        title = page.title()
        html = page.content()

        top_data = pyparser.parse_realestate_top_block(text)
        address_data = pyparser.extract_address_parts(title)
        extra_data = pyparser.parse_extra_fields(text)
        location = pyparser.extract_coordinates(html)

        # page.close()

        data = {
            "source": "realestate" if "realestate.com.au" in url else "unknown",
            "listing_url": url,
            "listing_id": pyparser.extract_listing_id(url, text),
            "first_seen_at": now,
            "last_seen_at": now,
            "scraped_at": now,

            "title": title,
            "description": None,

            **address_data,
            **top_data,
            **extra_data,
            **location,

            "status": "watching",
            "raw_text": text,
            "html_content":html
        }

        data["raw_json"] = data.copy()
        page.close()

        

        return data

def fetch_listing_links(search_url: str) -> list[str]:
    with sync_playwright() as p:
        if not is_port_open():
            initBrowser(3)
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()

        listing_links = []
        for page_num in range(1, 23):
            new_url = re.sub(r"list-\d+", f"list-{page_num}", search_url)
            time.sleep(1)
            page.goto(new_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            hrefs = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(a => a.href)"
            )

            
            for href in hrefs:
                if re.search(r"realestate\.com\.au/property-", href):
                    clean_url = href.split("?")[0]

                    if clean_url not in listing_links:
                        listing_links.append(clean_url)
        insert_links(listing_links)
        # browser.close()
        #--- now insert all of the links to a db 


    return listing_links

def insert_links(links: list[str]):
    rows = [{"link": link} for link in links]

    response = (
        supabase
        .table("propertylinks")
        .insert(rows)
        .execute()
    )

    return response.data

def get_links()->list[str]:
    response = supabase.table("propertylinks").select("*").execute()
    links = [d["link"] for d in response.data]
    return links

def insert_property(data: dict):
    row = data.copy()
    # Supabase/Postgres jsonb field can hold this, but avoid circular/weird nested copies
    response = (
        supabase
        .table("properties")
        .upsert(row, on_conflict="listing_url")
        .execute()
    )

    return response.data
def insertStuff (data:dict,table:str,conflict:str=""):
    row = data.copy()
    response = (supabase.table(table).upsert(row,on_conflict=conflict).execute())
    return response.data

def fixUpPropertyData(limit: int = 20):
    response = (
        supabase
        .table("properties")
        .select("id, listing_url")
        .is_("longitude", "null")
        # .limit(limit)
        .execute()
    )

    updated = []
    failed = []

    for row in response.data:
        try:
         
            parsed = fetchPageData(row["listing_url"])

            update_data = {
                **parsed,
            
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            print("done")

            (
                supabase
                .table("properties")
                .update(update_data)
                .eq("id", row["id"])
                .execute()
            )

            updated.append(row["id"])
            # time.sleep(1)

        except Exception as exc:
            failed.append({
                "id": row["id"],
                "error": str(exc),
            })

    return {
        "updated": len(updated),
        "failed": failed,
    }



def parse_links():
    links = get_links()
    results = []

    for i, link in enumerate(links, start=1):
        print(f"Scraping {i}/{len(links)}: {link}")

        try:
            data = fetchPageData(link)
            insert_property(data)
            results.append(data)

        except Exception as e:
            print(f"Failed {link}: {e}")

        time.sleep(random.uniform(2, 5))

    return results
    

