import streamlit as st
from pyscraper import *
from pyYieldImporter import *


st.set_page_config(page_title="Real Estate App", layout="wide")

st.title("🏡 Real Estate Finder")

url = st.text_area("paste your shit",height=400)

# if st.button("Analyse property"):
#     if not url:
#         st.error("Paste a URL first")
#     else:
#         st.session_state["data"] = fetchPageData(url)

# if st.button("test get links"):
#         st.session_state["data"] = parse_links()

if st.button("test"):
    st.session_state["data"] = fetchPageData(url)

if st.button("testFixProperties"):
    st.session_state["data"] = fixUpPropertyData()

if st.button("pyYIeld"):
    readandImportYield()


if "data" in st.session_state:
    data = st.session_state["data"]

    st.subheader("Scraped Data")
    st.json(data)

    price = st.number_input(
        "Purchase price",
        value=float(data.get("price") or 0)
    )

    rent = st.number_input(
        "Estimated rent per week",
        value=0.0
    )

    if price > 0 and rent > 0:
        yield_percent = (rent * 52 / price) * 100
        st.metric("Gross rental yield", f"{yield_percent:.2f}%")