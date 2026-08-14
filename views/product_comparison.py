"""
Product Comparison — 'Similar Product Mapping': pick a category (e.g. Dairy,
Beverages, Snacks) and see every brand's equivalent product side by side —
Price, Units Sold, Revenue, Profit, Rating — plus a head-to-head radar
comparison for any two specific products.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import ui
from utils.data_handler import get_merged_orders
from utils.ml_engine import compare_products_in_category


@ui.safe_page
def render(data, user):
    is_vendor = user["role"] == "Vendor"
    ui.page_header("🧮 Product Comparison", "HOME &nbsp;›&nbsp; PRODUCT COMPARISON")

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)

    if products.empty or "Category" not in products.columns:
        st.warning("No product data available.")
        return

    if is_vendor:
        st.info("🏬 As a Vendor you're comparing your own products against each other within a category. "
                 "Cross-brand comparison is an Admin/Viewer view.")

    categories = sorted(products["Category"].dropna().unique().tolist())
    category = st.selectbox("Category", categories, key="pc_category")

    comp = compare_products_in_category(merged, products, category, data.get("feedback"))
    if comp.empty:
        st.info(f"No products found in '{category}'.")
        return

    ui.card_open(f"📊 {category} — Every Product Side by Side")
    st.dataframe(
        comp.rename(columns={"UnitsSold": "Units Sold", "Revenue": "Revenue (₹)", "Profit": "Profit (₹)"}),
        width="stretch", hide_index=True, height=360,
    )
    ui.card_close()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("💰 Revenue by Product")
        top20 = comp.head(20)
        fig = px.bar(top20, x="Revenue", y="ProductName", color="Brand", orientation="h")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
        ui.card_close()
    with col2:
        ui.card_open("🏷️ Revenue Share by Brand (this category)")
        by_brand = comp.groupby("Brand")["Revenue"].sum().reset_index()
        fig = px.pie(by_brand, names="Brand", values="Revenue", hole=0.45)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420)
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ---------------- Head-to-head comparison ----------------
    ui.card_open("⚔️ Head-to-Head: Compare Two Products")
    comp["ProductName"] = comp["ProductName"].astype(str)
    comp["Brand"] = comp["Brand"].astype(str)

    options = comp["ProductName"] + " (" + comp["Brand"] + ")"
    label_map = dict(zip(options, comp["ProductID"]))
    colp1, colp2 = st.columns(2)
    with colp1:
        prod_a_label = st.selectbox("Product A", options.tolist(), key="pc_prod_a")
    with colp2:
        default_b_idx = 1 if len(options) > 1 else 0
        prod_b_label = st.selectbox("Product B", options.tolist(), index=default_b_idx, key="pc_prod_b")

    row_a = comp[comp["ProductID"] == label_map[prod_a_label]].iloc[0]
    row_b = comp[comp["ProductID"] == label_map[prod_b_label]].iloc[0]

    metrics = ["Price", "UnitsSold", "Revenue", "Profit", "Rating"]
    metrics = [m for m in metrics if m in comp.columns]

    if not metrics:
        st.info("Not enough comparable metrics for these two products.")
        ui.card_close()
        return

    max_vals = {}
    for m in metrics:
        col_max = comp[m].max()
        max_vals[m] = float(col_max) if pd.notna(col_max) and col_max > 0 else 1e-9

    def _safe_val(row, m):
        v = row[m]
        return float(v) if pd.notna(v) else 0.0

    a_vals = {m: _safe_val(row_a, m) for m in metrics}
    b_vals = {m: _safe_val(row_b, m) for m in metrics}
    a_norm = [a_vals[m] / max_vals[m] for m in metrics]
    b_norm = [b_vals[m] / max_vals[m] for m in metrics]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=a_norm + [a_norm[0]], theta=metrics + [metrics[0]],
                                    fill="toself", name=str(row_a["ProductName"]), line_color="#5b6ee1"))
    fig.add_trace(go.Scatterpolar(r=b_norm + [b_norm[0]], theta=metrics + [metrics[0]],
                                    fill="toself", name=str(row_b["ProductName"]), line_color="#6c5ce7"))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True,
                       margin=dict(l=30, r=30, t=30, b=30), height=420)
    st.plotly_chart(fig, width="stretch")

    colr1, colr2 = st.columns(2)
    with colr1:
        st.markdown(f"**{row_a['ProductName']}** ({row_a['Brand']})")
        for m in metrics:
            st.metric(m, f"{a_vals[m]:,.1f}")
    with colr2:
        st.markdown(f"**{row_b['ProductName']}** ({row_b['Brand']})")
        for m in metrics:
            st.metric(m, f"{b_vals[m]:,.1f}")
    ui.card_close()
