import pyscraper as ps 
import pyparser  as pp
import pyDB as pd
import pandas


def fixuptopfields():
    to_update = []

    query = """select id,raw_text from properties"""

    listings = pd.executeQueryAll(query,(),pd.result_type_dict)

    for i in listings:
        raw_text = i["raw_text"]
        id       = i["id"]

        topPart = pp.parse_realestate_top_block(raw_text)

        data = {
            "id":id,
            **topPart

        }
        to_update.append(data)
    for i in to_update:
        pd.update_property(i)
    print("finished!")
    print(len(to_update))

# def fixuptopfields():
#     query = "SELECT id, raw_text FROM properties WHERE raw_text IS NOT NULL"

#     listings = pd.executeQueryAll(query, (), pd.result_type_dict)

#     for i in listings:
#         raw_text = i["raw_text"]
#         id = i["id"]

#         try:
#             topPart = pp.parse_realestate_top_block(raw_text)

#             data = {
#                 "id": id,
#                 **topPart
#             }

#             pd.update_property(data)

#             print(f"Updated property {id}")

#         except Exception as e:
#             print(f"Failed property {id}: {e}")


    # print(listings[0]["id"])

# def parse_links():
#     links = pyDB.get_links()
#     results = []
#     oldPage = None
#     is_init = False
#     shouldClose = False
#     j=1
    
#     with sync_playwright() as p:
#         for i, link in enumerate(links, start=1):
#             print(f"Scraping {i}/{len(links)}: {link}")
#             try:
#                 if i != 1 and not is_init and oldPage is not None:
#                     is_init = True

#                 if i == len(links):
#                     shouldClose = True
#                 data,page = fetchPageDataBatch(link,is_init,shouldClose,oldPage,p)
#                 oldPage = page
#                 if j == 99:
#                     j=1
#                     shouldClose = True
#                     is_init = False
#                     oldPage = None
#                 else:
#                     shouldClose = False
#                 pyDB.insert_property(data)
#                 results.append(data)
#                 j = j + 1
#                 time.sleep(1)

#             except Exception as e:
                
#                 print(f"Failed {link}: {e}")
#                 break

#             # time.sleep(random.uniform(2, 5))

#     return results



# def fixupwronglyparsedrows():
#     response = (
#         supabase.table("properties").select("id,raw_text").execute()
#     )
#     to_update = []
#     for row in response.data:

#         d = reParseDb(row['raw_text'])
#         to_updateData = {**d,'id':row['id']}
#         to_update.append(to_updateData)
    

#     batch_size = 10

#     for start in range(0, len(to_update), batch_size):
#         batch = to_update[start:start + batch_size]

#         (
#             supabase.table("properties")
#             .upsert(batch, on_conflict="id")
#             .execute()
#         )

#         print(f"Updated {start + len(batch)}/{len(to_update)}")


# def fixUpPropertyData(limit: int = 20):
#     response = (
#         supabase
#         .table("properties")
#         .select("id, listing_url")
#         .is_("longitude", "null")
#         # .limit(limit)
#         .execute()
#     )

#     updated = []
#     failed = []

#     for row in response.data:
#         try:
         
#             parsed = fetchPageData(row["listing_url"])

#             update_data = {
#                 **parsed,
            
#                 "updated_at": datetime.now(timezone.utc).isoformat(),
#             }
#             print("done")

#             (
#                 supabase
#                 .table("properties")
#                 .update(update_data)
#                 .eq("id", row["id"])
#                 .execute()
#             )

#             updated.append(row["id"])
#             # time.sleep(1)

#         except Exception as exc:
#             failed.append({
#                 "id": row["id"],
#                 "error": str(exc),
#             })

#     return {
#         "updated": len(updated),
#         "failed": failed,
#     }


def savePropertyData():
    data = pd.get_propertydata()
    df = pandas.DataFrame(data)
    df.to_csv("properties.csv", index=False)