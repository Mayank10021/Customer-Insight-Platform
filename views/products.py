"""Product Analytics - top/worst products, stock, category analysis, ratings."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders


def render(data, user):
    ui.page_header("Product Analytics", "HOME &nbsp;›&nbsp; PRODUCTS")

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)

    if products.empty:
        st.warning("No product data available.")
        return

    out_of_stock = products[products["Stock"] == 0].shape[0]
    avg_rating = products["Rating"].mean()
    total_products = len(products)
    total_categories = products["Category"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Products", f"{total_products:,}", f"{total_categories} categories", "📦", "#00c2d1")
    with c2:
        ui.kpi_card("Avg Rating", f"{avg_rating:.2f} ★", "across catalog", "⭐", "#6c5ce7")
    with c3:
        ui.kpi_card("Out of Stock", f"{out_of_stock}", "products", "🚫", "#e74c3c")
    with c4:
        low_stock = products[(products["Stock"] > 0) & (products["Stock"] < 20)].shape[0]
        ui.kpi_card("Low Stock Alerts", f"{low_stock}", "below 20 units", "⚠️", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("🏆 Top 10 Best-Selling Products")
        if not merged.empty:
            top = merged.groupby(["ProductID", "ProductName"])["Quantity"].sum().reset_index()
            top = top.sort_values("Quantity", ascending=False).head(10)
            fig = px.bar(top, x="Quantity", y="ProductName", orientation="h",
                         color_discrete_sequence=["#00c2d1"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sales data yet.")
        ui.card_close()

    with col2:
        ui.card_open("📉 Worst-Selling Products")
        if not merged.empty:
            worst = merged.groupby(["ProductID", "ProductName"])["Quantity"].sum().reset_index()
            worst = worst.sort_values("Quantity", ascending=True).head(10)
            fig = px.bar(worst, x="Quantity", y="ProductName", orientation="h",
                         color_discrete_sequence=["#6c5ce7"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis={"categoryorder": "total descending"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sales data yet.")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        ui.card_open("Category-wise Product Count")
        cat_count = products["Category"].value_counts().reset_index()
        cat_count.columns = ["Category", "Count"]
        fig = px.pie(cat_count, names="Category", values="Count", hole=0.5)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col4:
        ui.card_open("Rating Distribution")
        fig = px.histogram(products, x="Rating", nbins=15, color_discrete_sequence=["#5b6ee1"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    ui.card_open("🚨 Out-of-Stock / Low-Stock Products")
    low = products[products["Stock"] < 20][["ProductID", "ProductName", "Category", "Brand", "Stock", "Price"]]
    low = low.sort_values("Stock")
    st.dataframe(low, width="stretch", hide_index=True, height=280)
    ui.card_close()

    if "RAM_GB" in products.columns:
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        ui.card_open("📱 Full Catalog — Models & Specs")
        st.caption("Every phone model in the catalog with its key specs and current stock.")
        spec_cols = [c for c in ["ProductID", "Brand", "ProductName", "Category", "Price", "Stock",
                                  "RAM_GB", "Storage_GB", "Battery_mAh", "CameraMP", "ScreenSize_in",
                                  "Processor", "Network", "WarrantyMonths", "Rating"] if c in products.columns]
        bc1, bc2 = st.columns(2)
        with bc1:
            brand_pick = st.multiselect("Filter by Brand", sorted(products["Brand"].dropna().unique().tolist()),
                                         default=[], key="prod_catalog_brand", placeholder="All brands")
        with bc2:
            cat_pick = st.multiselect("Filter by Category", sorted(products["Category"].dropna().unique().tolist()),
                                       default=[], key="prod_catalog_cat", placeholder="All categories")
        catalog = products[spec_cols].copy()
        if brand_pick:
            catalog = catalog[catalog["Brand"].isin(brand_pick)]
        if cat_pick:
            catalog = catalog[catalog["Category"].isin(cat_pick)]
        st.dataframe(catalog.sort_values(["Brand", "ProductName"]), width="stretch", hide_index=True, height=420)
        ui.card_close()
