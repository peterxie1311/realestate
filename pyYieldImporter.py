import pandas as pd
import re
from pyscraper import *
def readandImportYield():
    file_path = "/Users/peterxie/Desktop/pythonScraper/rta-bond-statistics.xlsx"
    workbook = pd.ExcelFile(file_path)
    print(workbook.sheet_names)
    df = pd.read_excel(
    "rta-bond-statistics.xlsx",
    sheet_name="1 pc-rents",
    header=None,
)

    latest_rent_column = df.columns[-1]

    rows = []

    for _, row in df.iloc[8:].iterrows():
        postcode = row.iloc[2]
        dwelling = row.iloc[3]
        median_rent = row.iloc[latest_rent_column]

        if pd.isna(postcode) or pd.isna(dwelling) or pd.isna(median_rent):
            continue

        match = re.match(r"(Flat|House|Townhouse)\s+(\d+)", str(dwelling))

        if not match:
            continue

        rows.append({
            "quarter_end": "2026-03-31",
            "postcode": str(int(postcode)),
            "dwelling_type": match.group(1),
            "bedrooms": int(match.group(2)),
            "median_rent_week": float(median_rent),
            "source": "qld_rta",
        })
        response = insertStuff(rows,"rental_market_data","quarter_end,postcode,dwelling_type,bedrooms")

# supabase.table("rental_market_data").upsert(
#     rows,
#     on_conflict="quarter_end,postcode,dwelling_type,bedrooms",
# ).execute()

    print(f"Uploaded {len(response)} rows")