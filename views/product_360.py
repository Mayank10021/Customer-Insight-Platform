"""
Product 360° — a full single-product profile: Sales Trend, Monthly Sales,
Revenue, Profit, Demand Forecast, Inventory, Similar Products, Reviews,
Top Customers.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders
from utils.ml_engine import (
    content_based_recommendations, forecast_single_product_demand, get_top_customers_for_product,
)


@ui.safe_page
def render(data, user):
    ui.page_header("📦 Product 360°", "HOME &nbsp;›&nbsp; PRODUCT 360")

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)
    feedback = data.get("feedback", pd.DataFrame())

    if products.empty:
        st.warning("No product data available.")
        return

    if "Brand" in products.columns:
        options = (
            products["ProductName"].astype(str)
            + " ("
            + products["Brand"].astype(str)
            + ")"
        )
    else:
        options = products["ProductName"].astype(str)
    label_map = dict(zip(options, products["ProductID"]))
    search = st.selectbox("Search / Select a Product", options.tolist(), key="p360_select")
    product_id = label_map[search]
    prod = products[products["ProductID"] == product_id].iloc[0]

    prod_orders = merged[merged["ProductID"] == product_id] if not merged.empty else pd.DataFrame()
    revenue = prod_orders["TotalAmount"].sum() if not prod_orders.empty else 0
    units_sold = prod_orders["Quantity"].sum() if not prod_orders.empty else 0
    profit = ((prod_orders["Price"] - prod_orders["Cost"]) * prod_orders["Quantity"]).sum() \
        if not prod_orders.empty and "Cost" in prod_orders.columns and "Price" in prod_orders.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        ui.kpi_card("Revenue", f"₹{revenue:,.0f}", "all time", "💰", "#00c2d1")
    with c2:
        ui.kpi_card("Profit", f"₹{profit:,.0f}", "all time", "📈", "#5b6ee1")
    with c3:
        ui.kpi_card("Units Sold", f"{int(units_sold):,}", "all time", "📦", "#6c5ce7")
    with c4:
        ui.kpi_card("Current Stock", f"{int(prod.get('Stock', 0)):,}" if "Stock" in prod else "—", "on hand", "🏭", "#161029")
    with c5:
        ui.kpi_card("Rating", f"{prod.get('Rating', 0):.1f} ★" if "Rating" in prod else "—", "avg customer rating", "⭐", "#c1121f")

    st.markdown(f"**Category:** {prod.get('Category', '—')} &nbsp;|&nbsp; **Brand:** {prod.get('Brand', '—')} "
                 f"&nbsp;|&nbsp; **Price:** ₹{prod.get('Price', 0):,.2f}", unsafe_allow_html=True)
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    has_specs = "RAM_GB" in products.columns
    tab_labels = ["📈 Sales Trend & Forecast", "🧩 Similar Products", "💬 Reviews", "👥 Top Customers"]
    if has_specs:
        tab_labels.insert(1, "📱 Specs & Warranty")
    tabs = st.tabs(tab_labels)
    tab1 = tabs[0]
    if has_specs:
        tab2, tab3, tab4 = tabs[2], tabs[3], tabs[4]
    else:
        tab2, tab3, tab4 = tabs[1], tabs[2], tabs[3]

    with tab1:
        forecast = forecast_single_product_demand(merged, product_id, months_ahead=1) if not merged.empty else None
        ui.card_open("Monthly Sales Trend")
        if forecast and not forecast["history"].empty:
            hist = forecast["history"].copy()
            hist["Type"] = "Actual"
            fig = px.line(hist, x="Month", y="Quantity", markers=True, color="Type",
                          color_discrete_map={"Actual": "#5b6ee1"})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
            st.metric("Next Month Predicted Demand", f"{forecast['predicted_demand']:.0f} units")
        else:
            st.info("Not enough order history for this product to chart a trend or forecast yet.")
        ui.card_close()

    if has_specs:
        with tabs[1]:
            ui.card_open("📱 Full Specifications")
            spec_rows = [
                ("RAM", f"{prod.get('RAM_GB', '—')} GB"),
                ("Storage", f"{prod.get('Storage_GB', '—')} GB"),
                ("Battery", f"{prod.get('Battery_mAh', '—')} mAh"),
                ("Main Camera", f"{prod.get('CameraMP', '—')} MP"),
                ("Screen Size", f"{prod.get('ScreenSize_in', '—')}\""),
                ("Processor", prod.get("Processor", "—")),
                ("Color", prod.get("Color", "—")),
                ("Network", prod.get("Network", "—")),
            ]
            spec_cols = st.columns(4)
            for i, (label, value) in enumerate(spec_rows):
                with spec_cols[i % 4]:
                    ui.mini_item("📱", label, str(value))
            ui.card_close()

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("🛡️ Warranty")
            warranty_months = prod.get("WarrantyMonths")
            if pd.notna(warranty_months):
                st.metric("Standard Warranty", f"{int(warranty_months)} months")
                claims = data.get("warranty_claims", pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
                if not claims.empty and "ProductID" in claims.columns:
                    prod_claims = claims[claims["ProductID"] == product_id]
                    if not prod_claims.empty:
                        resolved = prod_claims["Status"].isin(["Resolved", "Replaced"]).sum() if "Status" in prod_claims.columns else 0
                        st.caption(f"{len(prod_claims)} warranty claim(s) filed for this model — "
                                   f"{resolved} resolved/replaced.")
                        if "Issue" in prod_claims.columns:
                            st.dataframe(prod_claims["Issue"].value_counts().reset_index().rename(
                                columns={"index": "Issue", "Issue": "Count"}).head(5),
                                width="stretch", hide_index=True)
                    else:
                        st.caption("No warranty claims filed for this model yet.")
            else:
                st.info("No warranty info available for this product.")
            ui.card_close()

            # ---------------- EMI Calculator ----------------
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("🧮 EMI Calculator")
            st.caption("Estimate a monthly installment for this phone at a chosen tenure and interest rate.")
            price = float(prod.get("Price", 0) or 0)
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                down_payment = st.number_input("Down Payment (₹)", min_value=0.0,
                                                max_value=max(price, 0.0), value=round(price * 0.1, -2),
                                                step=500.0, key="emi_down")
            with ec2:
                tenure_months = st.selectbox("Tenure (months)", [3, 6, 9, 12, 18, 24], index=3, key="emi_tenure")
            with ec3:
                interest_rate = st.slider("Annual Interest Rate (%)", 0.0, 24.0, 12.0, step=0.5, key="emi_rate")

            principal = max(price - down_payment, 0.0)
            if principal <= 0:
                st.success("Down payment covers the full price — no EMI needed!")
            else:
                if interest_rate == 0:
                    emi = principal / tenure_months
                else:
                    r = (interest_rate / 12) / 100
                    emi = principal * r * (1 + r) ** tenure_months / (((1 + r) ** tenure_months) - 1)
                total_payment = emi * tenure_months
                total_interest = total_payment - principal

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    ui.kpi_card("Monthly EMI", f"₹{emi:,.0f}", f"for {tenure_months} months", "🧮", "#5b6ee1")
                with mc2:
                    ui.kpi_card("Total Interest", f"₹{total_interest:,.0f}", "over tenure", "📈", "#6c5ce7")
                with mc3:
                    ui.kpi_card("Total Payable", f"₹{(total_payment + down_payment):,.0f}", "incl. down payment", "💰", "#161029")
            ui.card_close()

    with tab2:
        ui.card_open("🧩 Similar Products (Content-Based)")
        similar = content_based_recommendations(products, product_id, top_n=6)
        if similar.empty:
            st.info("No similar products found.")
        else:
            st.dataframe(similar, width="stretch", hide_index=True)
            fig = px.bar(similar, x="SimilarityScore", y="ProductName", orientation="h", color="Brand")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with tab3:
        ui.card_open("💬 Customer Reviews")
        if feedback.empty or "ProductID" not in feedback.columns:
            st.info("No feedback data available.")
        else:
            prod_feedback = feedback[feedback["ProductID"] == product_id]
            if prod_feedback.empty:
                st.info("No reviews yet for this product.")
            else:
                avg_r = prod_feedback["Rating"].mean()
                st.metric("Average Review Rating", f"{avg_r:.2f} ★ ({len(prod_feedback)} reviews)")
                dist = prod_feedback["Rating"].value_counts().sort_index().reset_index()
                dist.columns = ["Rating", "Count"]
                fig = px.bar(dist, x="Rating", y="Count", color_discrete_sequence=["#5b6ee1"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
                show_cols = [c for c in ["CustomerID", "Rating", "Review", "Date"] if c in prod_feedback.columns]
                st.dataframe(prod_feedback[show_cols].sort_values("Date", ascending=False).head(20),
                             width="stretch", hide_index=True, height=300)
        ui.card_close()

    with tab4:
        ui.card_open("👥 Top Customers for This Product")
        top_customers = get_top_customers_for_product(merged, product_id, top_n=10) if not merged.empty else pd.DataFrame()
        if top_customers.empty:
            st.info("No purchase history for this product yet.")
        else:
            st.dataframe(top_customers, width="stretch", hide_index=True, height=340)
        ui.card_close()
