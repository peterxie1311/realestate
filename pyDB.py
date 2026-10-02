from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_ANON_KEY"]
)

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

def get_propertydata():
    return supabase.table("properties").select("*").execute().data

def get_propertydata():
    all_data = []
    batch_size = 10
    start = 0

    while True:
        response = (
            supabase
            .table("properties")
            .select("*")
            .range(start, start + batch_size - 1)
            .execute()
        )

        data = response.data
        all_data.extend(data)

        print(f"Fetched {len(all_data)} properties")

        if len(data) < batch_size:
            break

        start += batch_size

    return all_data

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