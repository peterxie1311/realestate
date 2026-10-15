import os
from dotenv import load_dotenv
import tempfile
import pandas as pd
import psycopg2
import psycopg2.pool
from psycopg2.extras import Json
from psycopg2 import sql

#New DB handelling for postgresql 

#---- DB CONSTANTS!----
result_type_dict         = 1 
result_type_array        = 2
result_type_rows         = 3
result_type_jsontocsv    = 4
result_type_boolean      = 5
result_type_rows_columns = 6
column_name = "columns"
row_name    = "rows"



load_dotenv()

min_con = 1
max_con = 5 
dbuser = os.environ["dbuser"]
dbpassword = os.environ["dbpassword"]
dbhost=os.environ["dbhost"]
dbport=os.environ["dbport"]
dbname=os.environ["dbname"]

connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=min_con,  # minimum number of connections in the pool
    maxconn=max_con,  # maximum number of connections in the pool
    dbname=dbname, 
    user=dbuser, 
    password=dbpassword, 
    host=dbhost, 
    port=dbport
)
def get_db_connection():
    return connection_pool.getconn()
def release_db_connection(conn):
    connection_pool.putconn(conn)


#----------------------------------------------------------------------
# transformResults
# Private function only for python to jsonify our results for typescript
# ---------------------------------------------------------------------   

# SQL ROUTES !! --------------------------
# def transformResults(cursor, rows):
#     columns = [desc[0] for desc in cursor.description]
#     results = [dict(zip(columns, row)) for row in rows]
#     return jsonify(results)

def transformResultsnoJson(cursor, rows):
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in rows]
    return results

def transformResultsDict(cursor, rows):
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in rows]
    return results

# def transformResultsArray(rows):
#     results = [row[0] for row in rows]
#     return jsonify(results)

def transformResultsArrayNoJson(rows):
    return [row[0] for row in rows]

def getColumns(dict):
    return dict[column_name]
def getRows(dict):
    return dict[row_name]

#----------------------------------------------------------------------
# Execute query
# This function executes a query without commit and returns a dict
# result_typ 1 = dict 2 = dict
# ---------------------------------------------------------------------   

def executeQueryAll(query,inparameters,result_type,conn=None):
    try:
        external_conn = conn is not None
        if conn is None:
            conn    = get_db_connection()
        cursor  = conn.cursor()
        if inparameters:
            cursor.execute(query,inparameters)
        else:
            cursor.execute(query)
        rows    = cursor.fetchall()
        
        if result_type == result_type_dict:
            result  = transformResultsnoJson(cursor, rows)
        elif result_type    == result_type_array:
            result  = transformResultsArrayNoJson(rows)
        elif result_type == result_type_rows:
            result  = rows
        elif result_type == result_type_rows_columns:
            columns = [desc[0] for desc in cursor.description]
            result = {
                column_name: columns,
                row_name: rows
            }
        elif result_type == result_type_jsontocsv:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            tmp_path = tmp.name
            tmp.close()
            if len(rows) == 1:
                if isinstance(rows[0][0],dict):
                    df = pd.DataFrame([rows[0][0]]) 
                    df.to_csv(tmp_path,index=False)
            else:
                df = pd.DataFrame(transformResultsnoJson(cursor,rows))
                df.to_csv(tmp_path,index=False)
            result = tmp_path
        cursor.close()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}")
        # logging.error(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}")
        # insertError(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}",' ',' ')
        raise e
        # return jsonify({"message": f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}"}), 400
    finally:
        # Ensure the connection is always released back to the pool
        if conn and not external_conn:
            release_db_connection(conn)   
#----------------------------------------------------------------------
# Execute procedure or changes tables
# This function executes a query without commit and returns a dict
# result_typ 1 = dict 2 = dict
# ---------------------------------------------------------------------   

def executeProcedure(query,inparameters,result_type=result_type_boolean):
    try:
        conn    = get_db_connection()
        cursor  = conn.cursor()
        cursor.execute(query,inparameters)
        rows    = None 
        result  = None
        if result_type != result_type_boolean:
            rows = cursor.fetchall()
            if result_type == result_type_dict:
                result  = transformResultsnoJson(cursor, rows)
            elif result_type    == result_type_array:
                result  = transformResultsArrayNoJson(rows)
            elif result_type == result_type_rows:
                result  = rows
        conn.commit()
        cursor.close()
        if result_type == result_type_boolean:
            return True
        else:
            return result
    except Exception as e:
        print(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}")
        # logging.error(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}")
        # insertError(f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}",' ',' ')
        conn.rollback()
        raise e
        # return jsonify({"message": f"error in executeQueryAll() => {e} => Query : {query} inparameters :{inparameters}"}), 400
    finally:
        # Ensure the connection is always released back to the pool
        if conn:
            release_db_connection(conn) 
    

def insert_links(links: list[str]):
    query = """
        INSERT INTO propertylinks (link)
        VALUES (%s)
        ON CONFLICT (link) DO NOTHING
    """

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.executemany(query, [(link,) for link in links])

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(e)
        raise

    finally:
        release_db_connection(conn)


def get_links() -> list[str]:
    query = """
        SELECT pl.link
        FROM propertylinks pl
        WHERE NOT EXISTS (
            SELECT 1
            FROM properties p
            WHERE p.listing_url = pl.link
        )
    """

    return executeQueryAll(
        query,
        None,
        result_type_array
    )

def get_propertydata():
    query = """
        SELECT *
          from properties
    """

    return executeQueryAll(
        query,
        None,
        result_type_dict
    )

# def get_propertydata():
#     all_data = []
#     batch_size = 10
#     start = 0

#     while True:
#         response = (
#             supabase
#             .table("properties")
#             .select("*")
#             .range(start, start + batch_size - 1)
#             .execute()
#         )

#         data = response.data
#         all_data.extend(data)

#         print(f"Fetched {len(all_data)} properties")

#         if len(data) < batch_size:
#             break

#         start += batch_size

#     return all_data

def insert_property(data: dict):
    columns = list(data.keys())

    column_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    # update everything except listing_url
    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in columns
        if column != "listing_url"
    )

    query = f"""
        INSERT INTO properties ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT (listing_url)
        DO UPDATE SET {update_sql}
    """

    executeProcedure(
        query,
          tuple(
        Json(data[column]) if column == "features" else data[column]
        for column in columns
    )
    )

# def insertStuff (data:dict,table:str,conflict:str=""):
#     row = data.copy()
#     response = (supabase.table(table).upsert(row,on_conflict=conflict).execute())
#     return response.data

def update_property(data: dict):
    if data.get("id") is not None:
        where_column = "id"
    elif data.get("listing_id") is not None:
        where_column = "listing_id"
    else:
        raise ValueError("Missing id or listing_id")

    update_data = {
        key: value
        for key, value in data.items()
        if key not in ("id", "listing_id")
    }

    if not update_data:
        return False

    query = sql.SQL("""
        UPDATE properties
        SET {}
        WHERE {} = %s
    """).format(
        sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(key))
            for key in update_data
        ),
        sql.Identifier(where_column)
    )

    params = [
        Json(value) if isinstance(value, (dict, list)) else value
        for value in update_data.values()
    ]

    return executeProcedure(
        query,
        tuple(params + [data[where_column]])
    )