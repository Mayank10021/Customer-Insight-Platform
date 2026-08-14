"""Warranty Claims - track device warranty status, open claims, issue trends, and per-brand warranty terms."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui


@ui.safe_page
def render(data, user):
    is_vendor = user["role"] == "Vendor"
    ui.page_header("🛡️ Warranty Claims", "HOME &nbsp;›&nbsp; WARRANTY")

    products = data.get("products", pd.DataFrame())
    claims = data.get("warranty_claims", pd.DataFrame())

    if is_vendor and not products.empty and "Brand" in products.columns:
        brand = user.get("vendor_brand")
        if brand:
            brand_products = products[products["Brand"] == brand]["ProductID"]
            if not claims.empty and "ProductID" in claims.columns:
                claims = claims[claims["ProductID"].isin(brand_products)]

    if claims.empty:
        st.info("No warranty claim data available yet. Upload a `warranty_claims` dataset "
                "(ClaimID, ProductID, CustomerID, Issue, Status, ClaimDate) to see this page populated.")
        return

    claims = claims.copy()
    if "ClaimDate" in claims.columns:
        claims["ClaimDate"] = pd.to_datetime(claims["ClaimDate"], errors="coerce")

    total_claims = len(claims)
    resolved = claims[claims["Status"].isin(["Resolved", "Replaced"])].shape[0] if "Status" in claims.columns else 0
    open_claims = claims[claims["Status"].isin(["In Progress", "Pending Pickup"])].shape[0] if "Status" in claims.columns else 0
    rejected = claims[claims["Status"] == "Rejected - Out of Warranty"].shape[0] if "Status" in claims.columns else 0
    resolve_rate = (resolved / total_claims * 100) if total_claims else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Claims", f"{total_claims:,}", "all time", "🛡️", "#5b6ee1")
    with c2:
        ui.kpi_card("Resolved / Replaced", f"{resolved:,}", f"{resolve_rate:.0f}% resolve rate", "✅", "#00c2d1")
    with c3:
        ui.kpi_card("Open Claims", f"{open_claims:,}", "in progress / pending", "⏳", "#6c5ce7")
    with c4:
        ui.kpi_card("Rejected", f"{rejected:,}", "out of warranty", "🚫", "#c1121f")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("📋 Claim Status Breakdown")
        if "Status" in claims.columns:
            status_count = claims["Status"].value_counts().reset_index()
            status_count.columns = ["Status", "Count"]
            fig = px.pie(status_count, names="Status", values="Count", hole=0.5)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
            st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col2:
        ui.card_open("🔧 Top Reported Issues")
        if "Issue" in claims.columns:
            issue_count = claims["Issue"].value_counts().reset_index().head(10)
            issue_count.columns = ["Issue", "Count"]
            fig = px.bar(issue_count, x="Count", y="Issue", orientation="h",
                         color_discrete_sequence=["#6c5ce7"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    if not products.empty and "Brand" in products.columns and "ProductID" in claims.columns:
        ui.card_open("🏷️ Claims by Brand")
        merged = claims.merge(products[["ProductID", "Brand", "ProductName", "WarrantyMonths"]],
                               on="ProductID", how="left")
        brand_claims = merged.groupby("Brand").agg(
            Claims=("ClaimID", "count"),
            Resolved=("Status", lambda s: s.isin(["Resolved", "Replaced"]).sum()),
        ).reset_index()
        brand_claims["ResolveRate%"] = (brand_claims["Resolved"] / brand_claims["Claims"] * 100).round(1)
        brand_claims = brand_claims.sort_values("Claims", ascending=False)
        fig = px.bar(brand_claims, x="Brand", y="Claims", color="ResolveRate%",
                     color_continuous_scale="RdYlGn", text="Claims")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(brand_claims, width="stretch", hide_index=True)
        ui.card_close()

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        ui.card_open("📅 Warranty Terms by Brand")
        terms = products.groupby("Brand").agg(
            AvgWarrantyMonths=("WarrantyMonths", "mean"),
            Models=("ProductID", "count"),
        ).reset_index().sort_values("AvgWarrantyMonths", ascending=False)
        terms["AvgWarrantyMonths"] = terms["AvgWarrantyMonths"].round(1)
        st.dataframe(terms, width="stretch", hide_index=True)
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    ui.card_open("🗂️ Recent Claims")
    show_cols = [c for c in ["ClaimID", "ProductID", "CustomerID", "StoreID", "Issue", "Status",
                              "PurchaseDate", "ClaimDate", "WarrantyMonths"] if c in claims.columns]
    recent = claims.sort_values("ClaimDate", ascending=False).head(200) if "ClaimDate" in claims.columns else claims.head(200)
    st.dataframe(recent[show_cols], width="stretch", hide_index=True, height=340)
    ui.card_close()
