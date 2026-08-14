"""Sales Dashboard - daily/monthly/yearly trends, category performance, profit/loss."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders


def render(data, user):
    ui.page_header("Sales Dashboard", "HOME &nbsp;›&nbsp; SALES")

    merged = get_merged_orders(data)
    if merged.empty:
        st.warning("No sales data available.")
        return

    merged["Profit"] = (merged["Price"] - merged.get("Cost", 0)) * merged["Quantity"]

    total_sales = merged["TotalAmount"].sum()
    total_profit = merged["Profit"].sum()
    total_orders = merged["OrderID"].nunique()
    avg_order_value = merged["TotalAmount"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Revenue", f"₹{total_sales/1e5:,.1f}L", "All-time", "💰", "#00c2d1")
    with c2:
        ui.kpi_card("Total Profit", f"₹{total_profit/1e5:,.1f}L", "Est. margin", "📊", "#6c5ce7")
    with c3:
        ui.kpi_card("Orders", f"{total_orders:,}", "Completed", "🧾", "#5b6ee1")
    with c4:
        ui.kpi_card("Avg Order Value", f"₹{avg_order_value:,.0f}", "Per order", "🛍️", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    period = st.radio("View trend by:", ["Daily", "Monthly", "Yearly"], horizontal=True, index=1)

    ui.card_open(f"{period} Sales Trend")
    df = merged.copy()
    if period == "Daily":
        df["Period"] = df["Date"].dt.date
    elif period == "Monthly":
        df["Period"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    else:
        df["Period"] = df["Date"].dt.year

    trend = df.groupby("Period")["TotalAmount"].sum().reset_index()
    fig = px.line(trend, x="Period", y="TotalAmount", markers=True)
    fig.update_traces(line_color="#6c5ce7")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("Sales by Category")
        cat_sales = merged.groupby("Category")["TotalAmount"].sum().reset_index().sort_values("TotalAmount", ascending=False)
        fig = px.bar(cat_sales, x="Category", y="TotalAmount", color_discrete_sequence=["#161029"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col2:
        ui.card_open("Profit vs Cost by Category")
        cat_profit = merged.groupby("Category").agg(
            Profit=("Profit", "sum"),
            Cost=("Cost", lambda x: (x * merged.loc[x.index, "Quantity"]).sum())
        ).reset_index()
        fig = px.bar(cat_profit, x="Category", y=["Profit", "Cost"], barmode="group",
                     color_discrete_sequence=["#00c2d1", "#6c5ce7"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    ui.card_open("Sales by Store City")
    city_sales = merged.groupby("City")["TotalAmount"].sum().reset_index().sort_values("TotalAmount", ascending=False)
    fig = px.bar(city_sales, x="City", y="TotalAmount", color_discrete_sequence=["#5b6ee1"])
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
    ui.card_close()
