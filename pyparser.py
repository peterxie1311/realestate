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

# this should be the file where all the text gets parsed

def clean_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(re.sub(r"[^\d]", "", value))
    except ValueError:
        return None


def extract_listing_id(url: str, text: str) -> str | None:
    match = re.search(r"Property ID:\s*(\d+)", text, re.I)
    if match:
        return match.group(1)

    url_match = re.search(r"-(\d+)$", url)
    if url_match:
        return url_match.group(1)

    return None


def extract_address_parts(title: str | None) -> dict:
    if not title:
        return {}

    address = title.split(" - ")[0].strip()
    parts = [p.strip() for p in address.split(",")]

    result = {
        "address": address,
        "suburb": None,
        "state": None,
        "postcode": None,
        "street_number": None,
        "street_name": None,
    }

    if len(parts) >= 2:
        result["suburb"] = parts[1]

    if len(parts) >= 3:
        state_postcode = parts[2]
        match = re.search(r"([A-Za-z]+)\s+(\d{4})", state_postcode)
        if match:
            result["state"] = match.group(1).upper()
            result["postcode"] = match.group(2)

    street_match = re.match(r"^(\d+[A-Za-z]?/?\d*)\s+(.+)$", parts[0])
    if street_match:
        result["street_number"] = street_match.group(1)
        result["street_name"] = street_match.group(2)

    return result


def parse_price(price_text: str | None) -> dict:
    result = {
        "price": None,
        "price_min": None,
        "price_max": None,
    }

    if not price_text:
        return result

    prices = re.findall(r"\$[\d,.]+(?:m|M|k|K)?", price_text)

    parsed = []
    for price in prices:
        raw = price.replace("$", "").replace(",", "").lower()

        multiplier = 1
        if raw.endswith("m"):
            multiplier = 1_000_000
            raw = raw[:-1]
        elif raw.endswith("k"):
            multiplier = 1_000
            raw = raw[:-1]

        try:
            parsed.append(int(float(raw) * multiplier))
        except ValueError:
            pass

    if len(parsed) == 1:
        result["price"] = parsed[0]
        result["price_min"] = parsed[0]
    elif len(parsed) >= 2:
        result["price_min"] = parsed[0]
        result["price_max"] = parsed[1]
        result["price"] = parsed[0]

    return result


def parse_land_size(value: str | None) -> int | None:
    if not value:
        return None

    text = value.lower().replace(",", "").strip()

    try:
        if text.endswith("ha"):
            return int(float(text.removesuffix("ha")) * 10_000)

        if text.endswith("m²"):
            return int(float(text.removesuffix("m²")))

        if text.endswith("sqm"):
            return int(float(text.removesuffix("sqm")))
    except ValueError:
        return None

    return None


def is_plain_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d+", value.strip()))


def parse_realestate_top_block(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    result = {
        "bedrooms": None,
        "bathrooms": None,
        "car_spaces": None,
        "land_size_sqm": None,
        "property_type": None,
        "price_text": None,
        "listing_status": None,
    }

    property_types = {
        "house",
        "townhouse",
        "apartment",
        "unit",
        "villa",
        "duplex",
        "residential land",
        "acreage/semi-rural",
        "retirement living",
    }

    for i, line in enumerate(lines):
        if line != "•":
            continue

        property_type = lines[i + 1] if i + 1 < len(lines) else None

        if not property_type or property_type.lower() not in property_types:
            continue

        result["property_type"] = property_type
        result["price_text"] = lines[i + 2] if i + 2 < len(lines) else None

        previous = lines[:i]
        last_line = previous[-1] if previous else ""

        land_size = parse_land_size(last_line)

        if land_size is not None:
            result["land_size_sqm"] = land_size
            previous = previous[:-1]

        numeric_values = [
            clean_int(value)
            for value in previous[-3:]
            if is_plain_number(value)
        ]

        if len(numeric_values) >= 1:
            result["bedrooms"] = numeric_values[0]

        if len(numeric_values) >= 2:
            result["bathrooms"] = numeric_values[1]

        if len(numeric_values) >= 3:
            result["car_spaces"] = numeric_values[2]

        break

    price_text = result["price_text"] or ""

    top_section = "\n".join(lines[:50]).lower()

    if "under contract" in top_section:
        result["listing_status"] = "under_contract"
    elif "under offer" in top_section:
        result["listing_status"] = "under_offer"
    elif re.search(r"\bsold\b", top_section):
        result["listing_status"] = "sold"
    elif "auction" in price_text.lower():
        result["listing_status"] = "auction"
    elif "for sale" in price_text.lower():
        result["listing_status"] = "for_sale"
    elif price_text:
        result["listing_status"] = "active"

    result.update(parse_price(price_text))

    return result

# def parse_realestate_top_block(text: str) -> dict:
#     lines = [line.strip() for line in text.splitlines() if line.strip()]

#     result = {
#         "bedrooms": None,
#         "bathrooms": None,
#         "car_spaces": None,
#         "land_size_sqm": None,
#         "property_type": None,
#         "price_text": None,
#         "listing_status": None,
#     }

#     for i, line in enumerate(lines):
#         print(line)
#         if line == "•":
#             if i >= 4 and lines[i - 1].endswith("m²") or i >= 4 and lines[i - 1].endswith("ha"):
#                 result["bedrooms"] = clean_int(lines[i - 4])
#                 result["bathrooms"] = clean_int(lines[i - 3])
#                 result["car_spaces"] = clean_int(lines[i - 2])
#                 result["land_size_sqm"] = clean_int(lines[i - 1])

#             elif i >= 3:
#                 result["bedrooms"] = clean_int(lines[i - 3])
#                 result["bathrooms"] = clean_int(lines[i - 2])
#                 result["car_spaces"] = clean_int(lines[i - 1])

#             result["property_type"] = lines[i + 1] if i + 1 < len(lines) else None
#             result["price_text"] = lines[i + 2] if i + 2 < len(lines) else None
#             break

#     price_text = result["price_text"] or ""
#     lower_price_text = price_text.lower()

#     if "under contract" in lower_price_text:
#         result["listing_status"] = "under_contract"
#     elif "under offer" in lower_price_text:
#         result["listing_status"] = "under_offer"
#     elif "sold" in lower_price_text:
#         result["listing_status"] = "sold"
#     elif "for sale" in lower_price_text:
#         result["listing_status"] = "for_sale"
#     elif price_text:
#         result["listing_status"] = "active"

#     result.update(parse_price(price_text))

#     return result


def parse_extra_fields(text: str) -> dict:
    result = {
        "year_built": None,
        "council_area": None,
        "council_rates_year": None,
        "body_corp_year": None,
        "water_rates_year": None,
        "features": {},
    }

    year_match = re.search(r"Year Built\s*/\s*(\d{4})", text, re.I)
    if year_match:
        result["year_built"] = int(year_match.group(1))

    council_match = re.search(r"Council\s*/\s*([^\n]+)", text, re.I)
    if council_match:
        result["council_area"] = council_match.group(1).strip()

    council_rates_match = re.search(r"Council Rates\s*/\s*\$([\d,]+)\s*PQ", text, re.I)
    if council_rates_match:
        quarterly = clean_int(council_rates_match.group(1))
        result["council_rates_year"] = quarterly * 4 if quarterly else None

    body_corp_match = re.search(r"Body Corporate.*?\$([\d,]+).*?(?:year|annum|pa|p\.a)", text, re.I)
    if body_corp_match:
        result["body_corp_year"] = clean_int(body_corp_match.group(1))

    feature_keywords = {
        "air_conditioning": "air conditioning",
        "pool": "pool",
        "dishwasher": "dishwasher",
        "built_in_wardrobes": "built-in wardrobes",
        "solar": "solar",
        "garage": "garage",
        "balcony": "balcony",
        "courtyard": "courtyard",
        "nbn": "nbn",
    }

    lower_text = text.lower()

    features = re.search(
    r"(Property features.*)",
    text,
    re.DOTALL ,  
)
    features_text = features.group(1) if features else ""
    # print(features)
    # print(features_text)
    for key, keyword in feature_keywords.items():
        print(keyword)
        result["features"][key] = keyword in features_text.lower()

    return result

import re


def extract_coordinates(html: str) -> dict:
    latitude_match = re.search(
        r'latitude\\*"\s*:\s*(-?\d+(?:\.\d+)?)',
        html,
        re.IGNORECASE,
    )

    longitude_match = re.search(
        r'longitude\\*"\s*:\s*(-?\d+(?:\.\d+)?)',
        html,
        re.IGNORECASE,
    )

    return {
        "latitude": (
            float(latitude_match.group(1))
            if latitude_match
            else None
        ),
        "longitude": (
            float(longitude_match.group(1))
            if longitude_match
            else None
        ),
    }