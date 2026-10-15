import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from playwright.sync_api import Page, sync_playwright,Playwright
import time
from urllib.parse import urljoin,urlencode
import pyparser
import pandas 
import pyBrowser
import pyDB

def reParseDb(bodyText:str):
        
        top_data = pyparser.parse_realestate_top_block(bodyText)
        # address_data = pyparser.extract_address_parts(title)
        extra_data = pyparser.parse_extra_fields(bodyText)
        # location = pyparser.extract_coordinates(html_text)
        buildingandland = pyparser.getBuildingAndLand(bodyText)
        data = {
            **top_data,
            **extra_data,
            # **location,
            **buildingandland
        }
        return data

def fetchPageDataBatch(url: str,is_init:bool,shouldClose:bool,oldPage:Page,p:Playwright) -> tuple[dict,Page]:
   now = datetime.now().isoformat()
   if not pyBrowser.is_port_open():
       pyBrowser.initBrowser(3)
   if is_init ==  False:
       browser = p.chromium.connect_over_cdp("http://localhost:9222")
       context = browser.contexts[0]
       page = context.new_page()
   else:
       page = oldPage
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
   # data["raw_json"] = data.copy()
   if shouldClose:
       page.close()
   
   return data,page


def fetchPageData(url: str,is_init:bool,shouldClose:bool,oldPage:Page) -> tuple[dict,Page]:
    now = datetime.now().isoformat()

    with sync_playwright() as p:
        if not pyBrowser.is_port_open():
            pyBrowser.initBrowser(3)

        if is_init ==  False:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.new_page()
        else:
            page = oldPage

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

        if shouldClose:
            page.close()

        return data,page
    
def searchPropertyInfo(address:str):
    query = f'site:property.com.au "{address}"'
    url = "https://www.google.com/search?" + urlencode({"q": query})
    with sync_playwright() as p:
        if not pyBrowser.is_port_open():
            pyBrowser.initBrowser(3)
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        links = page.eval_on_selector_all(
            'a[href*="property.com.au"]',
            """
            els => els.map(a => ({
                href: a.href.split("#")[0],
                text: a.innerText.trim()
            }))
            """,
        )
        print(links)

def fetch_listing_links(search_url: str,is_sold:bool,maxpagenum:int) -> list[str]:
    with sync_playwright() as p:
        if not pyBrowser.is_port_open():
            pyBrowser.initBrowser(3)
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()

        listing_links = []

        searchString = ""
        if is_sold == True:
            searchString = r"realestate\.com\.au/sold/property-"
        else:
            searchString = r"realestate\.com\.au/property-"


        for page_num in range(1, maxpagenum):
            new_url = re.sub(r"list-\d+", f"list-{page_num}", search_url)
            time.sleep(1)
            page.goto(new_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            hrefs = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(a => a.href)"
            )
            
            for href in hrefs:
                if re.search(searchString, href):# for sold properties
                    clean_url = href.split("?")[0]

                    if clean_url not in listing_links:
                        listing_links.append(clean_url)
        # print(listing_links)
        pyDB.insert_links(listing_links)
        # browser.close()
        #--- now insert all of the links to a db 


    return listing_links

def parse_links():
    links = pyDB.get_links()
    results = []
    oldPage = None
    j=1

    with sync_playwright() as p:
        for i, link in enumerate(links, start=1):
            print(f"Scraping {i}/{len(links)}: {link}")

            try:
                is_init = oldPage is not None
                shouldClose = j == 2 or i == len(links)
                # print(shouldClose)
                if j == 2:
                    j=1

                data, page = fetchPageDataBatch(
                    link, is_init, shouldClose, oldPage, p
                )
                if data["latitude"] is None:
                    raise ValueError("Missing latitude")

                # data,Page fetchPageData(link,)

                oldPage = None if shouldClose else page

                pyDB.insert_property(data)
                # results.append(data)
                time.sleep(1)
                j=j+1

            except Exception as e:
                print(f"Failed {link}: {e}")
                parse_links()
                break
                

    return results








