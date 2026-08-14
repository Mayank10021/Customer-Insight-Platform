"""Marketing Dashboard - acquisition channels, payment method mix, simulated campaign ROI."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders


def render(data, user):
    ui.page_header("Marketing Dashboard", "HOME &nbsp;›&nbsp; MARKETING")

    payments = data.get("payments", pd.DataFrame())
    merged = get_merged_orders(data)
    customers = data.get("customers", pd.DataFrame())

    if payments.empty:
        st.warning("No payment data available.")
        return

    total_transactions = len(payments)
    top_method = payments["Method"].value_counts().idxmax()
    new_customers_30d = 0
    if not customers.empty:
        cutoff = customers["SignupDate"].max() - pd.Timedelta(days=30)
        new_customers_30d = customers[customers["SignupDate"] >= cutoff].shape[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Transactions", f"{total_transactions:,}", "Total processed", "💳", "#00c2d1")
    with c2:
        ui.kpi_card("Top Payment Method", top_method, "Most used", "⭐", "#6c5ce7")
    with c3:
        ui.kpi_card("New Customers", f"{new_customers_30d:,}", "Last 30 days", "🆕", "#5b6ee1")
    with c4:
        ui.kpi_card("Avg Basket Size", f"₹{merged['TotalAmount'].mean():,.0f}" if not merged.empty else "N/A",
                     "per transaction", "🧺", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("Payment Method Mix")
        method_counts = payments["Method"].value_counts().reset_index()
        method_counts.columns = ["Method", "Count"]
        fig = px.pie(method_counts, names="Method", values="Count", hole=0.55)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col2:
        ui.card_open("Customer Acquisition Trend")
        if not customers.empty:
            signup_trend = customers.copy()
            signup_trend["Month"] = signup_trend["SignupDate"].dt.to_period("M").dt.to_timestamp()
            trend = signup_trend.groupby("Month")["CustomerID"].count().reset_index()
            fig = px.area(trend, x="Month", y="CustomerID")
            fig.update_traces(line_color="#00c2d1", fillcolor="rgba(46,196,182,0.15)")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    st.caption("⚠️ No dedicated campaign/coupon dataset exists in the source data, so the panel below "
               "is a simulated illustration of what a campaign-performance view would show once real "
               "campaign data is connected.")

    rng = np.random.default_rng(7)
    campaigns = pd.DataFrame({
        "Campaign": ["Diwali Sale", "New Year Offer", "Summer Discount", "Referral Bonus", "App Install Offer"],
        "Spend (₹)": rng.integers(20000, 120000, 5),
        "Revenue Generated (₹)": rng.integers(80000, 400000, 5),
    })
    campaigns["ROI (%)"] = ((campaigns["Revenue Generated (₹)"] - campaigns["Spend (₹)"])
                            / campaigns["Spend (₹)"] * 100).round(1)

    ui.card_open("Simulated Campaign ROI")
    fig = px.bar(campaigns, x="Campaign", y="ROI (%)", color_discrete_sequence=["#161029"])
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(campaigns, width="stretch", hide_index=True)
    ui.card_close()
