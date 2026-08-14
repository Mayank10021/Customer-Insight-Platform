"""
Product Performance Tiers — Top Selling, Medium Selling, and Least
Selling / Dead Stock, all computed from the same Units Sold distribution
(top ~20% / middle ~60% / bottom ~20%), so the three dashboards are always
mutually consistent.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders
from utils.ml_engine import product_performance_tiers


@ui.safe_page
def render(data, user):
    ui.page_header("🏆 Product Performance Tiers", "HOME &nbsp;›&nbsp; PRODUCT PERFORMANCE")

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)

    if products.empty:
        st.warning("No product data available.")
        return
    if merged.empty:
        st.info("No order history available to rank products by yet.")
        return

    tiers = product_performance_tiers(merged, products)
    if tiers.empty:
        st.info("Not enough data to build performance tiers.")
        return

    top_n = tiers[tiers["Tier"] == "Top"]
    med_n = tiers[tiers["Tier"] == "Medium"]
    least_n = tiers[tiers["Tier"] == "Least"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Top Sellers", f"{len(top_n)}", "top ~20% by units", "🏆", "#00c2d1")
    with c2:
        ui.kpi_card("Medium Sellers", f"{len(med_n)}", "stable performers", "⚖️", "#5b6ee1")
    with c3:
        ui.kpi_card("Least / Dead Stock", f"{len(least_n)}", "bottom ~20% by units", "🐌", "#e74c3c")
    with c4:
        zero_sales = int((tiers["UnitsSold"] == 0).sum())
        ui.kpi_card("Zero Sales", f"{zero_sales}", "never sold — discontinue?", "🚫", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🏆 Top Selling", "⚖️ Medium Selling", "🐌 Least Selling / Dead Stock"])

    with tab1:
        ui.card_open("Top 20 Products — Highest Revenue")
        top_by_rev = top_n.sort_values("Revenue", ascending=False).head(20)
        fig = px.bar(top_by_rev, x="Revenue", y="ProductName", color="Brand", orientation="h")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=460,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        colt1, colt2 = st.columns(2)
        with colt1:
            ui.card_open("Highest Quantity Sold")
            st.dataframe(top_n.sort_values("UnitsSold", ascending=False).head(10)
                         [["ProductName", "Brand", "UnitsSold", "Revenue"]],
                         width="stretch", hide_index=True, height=300)
            ui.card_close()
        with colt2:
            ui.card_open("Best Rated (within Top Sellers)")
            if "Rating" in top_n.columns:
                st.dataframe(top_n.sort_values("Rating", ascending=False).head(10)
                             [["ProductName", "Brand", "Rating", "UnitsSold"]],
                             width="stretch", hide_index=True, height=300)
            ui.card_close()

    with tab2:
        ui.card_open("Medium Sellers — Stable, Average Performers")
        st.caption("Products with steady but unremarkable demand — the bulk of the catalog. "
                    "Good candidates for cross-sell / bundling to push them into the Top tier.")
        st.dataframe(med_n.sort_values("Revenue", ascending=False)
                     [["ProductName", "Brand", "Category", "UnitsSold", "Revenue", "Stock"]],
                     width="stretch", hide_index=True, height=380)
        fig = px.histogram(med_n, x="UnitsSold", nbins=25, color_discrete_sequence=["#5b6ee1"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with tab3:
        ui.card_open("🐌 Least Selling — Dead Stock / Slow-Moving Inventory")
        st.caption("Bottom ~20% by units sold, including anything never ordered. Candidates for "
                    "promotion, markdown, or discontinuation.")
        show_cols = [c for c in ["ProductName", "Brand", "Category", "UnitsSold", "Revenue", "Stock", "Price"]
                     if c in least_n.columns]
        st.dataframe(least_n.sort_values("UnitsSold")[show_cols], width="stretch", hide_index=True, height=380)

        never_sold = least_n[least_n["UnitsSold"] == 0]
        if not never_sold.empty:
            st.error(f"🚫 {len(never_sold)} product(s) have **never sold a single unit** — strong "
                     f"candidates to discontinue or deep-discount.")

        fig = px.bar(least_n.sort_values("Stock", ascending=False).head(15), x="Stock", y="ProductName",
                      color="Brand", orientation="h", title=None)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=400,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis={"categoryorder": "total ascending"})
        st.caption("Stock tied up in slow-moving products (highest stock among the Least tier):")
        st.plotly_chart(fig, width="stretch")
        ui.card_close()
