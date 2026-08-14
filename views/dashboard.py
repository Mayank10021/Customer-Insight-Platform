"""Home Dashboard - company overview KPIs and trend charts."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_value_tiers


def render(data, user):
    ui.page_header("Home", "HOME &nbsp;›&nbsp; DASHBOARD")

    merged = get_merged_orders(data)
    customers = data.get("customers", pd.DataFrame())
    orders = data.get("orders", pd.DataFrame())

    total_sales = merged["TotalAmount"].sum() if not merged.empty else 0
    total_orders = len(orders) if not orders.empty else 0
    total_customers = len(customers) if not customers.empty else 0
    avg_order = merged["TotalAmount"].mean() if not merged.empty else 0
    profit = ((merged["Price"] - merged.get("Cost", 0)) * merged["Quantity"]).sum() if not merged.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Sales", f"₹{total_sales/1e5:,.1f}L", "+8.4% this month", "📈", "#00c2d1")
    with c2:
        ui.kpi_card("Total Customers", f"{total_customers:,}", "+5.1% this month", "👥", "#6c5ce7")
    with c3:
        ui.kpi_card("Total Orders", f"{total_orders:,}", "+3.9% this month", "🧾", "#5b6ee1")
    with c4:
        ui.kpi_card("Est. Profit", f"₹{profit/1e5:,.1f}L", "+6.2% this month", "💰", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 2])

    with col_a:
        ui.card_open("Quick Insights")
        top_city = merged.groupby("City")["TotalAmount"].sum().idxmax() if not merged.empty and "City" in merged.columns else "N/A"
        top_store = merged.groupby("StoreName")["TotalAmount"].sum().idxmax() if not merged.empty and "StoreName" in merged.columns else "N/A"
        ui.mini_item("🏙️", "Top City", str(top_city))
        ui.mini_item("🏬", "Top Performing Store", str(top_store)[:26])
        ui.mini_item("⭐", "Avg Order Value", f"₹{avg_order:,.0f}")
        ui.card_close()

    with col_b:
        ui.card_open("Monthly Sales Trend")
        if not merged.empty:
            monthly = merged.copy()
            monthly["Month"] = monthly["Date"].dt.to_period("M").dt.to_timestamp()
            monthly = monthly.groupby("Month")["TotalAmount"].sum().reset_index()
            fig = px.area(monthly, x="Month", y="TotalAmount")
            fig.update_traces(line_color="#6c5ce7", fillcolor="rgba(255,127,102,0.15)")
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=260,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="", yaxis_title="",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No order data available yet.")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    st.markdown(f"""<div class="fm-card-mint"><div class="fm-card-title">Category-wise Total Orders</div></div>""",
                unsafe_allow_html=True)
    if not merged.empty and "Category" in merged.columns:
        cat_orders = merged.groupby("Category")["OrderID"].count().reset_index().sort_values("OrderID", ascending=False)
        fig2 = go.Figure(go.Bar(x=cat_orders["Category"], y=cat_orders["OrderID"],
                                 marker_color="#161029"))
        fig2.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=280,
            plot_bgcolor="#d8fff0", paper_bgcolor="#d8fff0",
            xaxis_title="", yaxis_title="",
        )
        st.plotly_chart(fig2, width="stretch")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ---------------- Top vs Low Value Customers — impact on sales ----------------
    ui.card_open("💎 Top vs Low Value Customers")
    if not merged.empty:
        _, tier_stats = get_cached_value_tiers(merged)
        if tier_stats:
            top_s, mid_s, low_s = tier_stats.get("Top", {}), tier_stats.get("Mid", {}), tier_stats.get("Low", {})
            st.caption("Customers split into Top 20% / Middle 60% / Bottom 20% by total spend — "
                       "shows exactly how much each group contributes to total sales.")
            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                ui.kpi_card("Top 20% Customers", f"{top_s.get('revenue_pct', 0)}% of revenue",
                            f"{top_s.get('count', 0):,} customers · ₹{top_s.get('revenue', 0):,.0f}", "🏆", "#00c2d1")
            with tc2:
                ui.kpi_card("Middle 60% Customers", f"{mid_s.get('revenue_pct', 0)}% of revenue",
                            f"{mid_s.get('count', 0):,} customers · ₹{mid_s.get('revenue', 0):,.0f}", "📊", "#5b6ee1")
            with tc3:
                ui.kpi_card("Bottom 20% Customers", f"{low_s.get('revenue_pct', 0)}% of revenue",
                            f"{low_s.get('count', 0):,} customers · ₹{low_s.get('revenue', 0):,.0f}", "⚠️", "#8b8fb3")

            fig3 = go.Figure(go.Bar(
                x=["Top 20%", "Middle 60%", "Bottom 20%"],
                y=[top_s.get("revenue_pct", 0), mid_s.get("revenue_pct", 0), low_s.get("revenue_pct", 0)],
                marker_color=["#00c2d1", "#5b6ee1", "#8b8fb3"],
                text=[f"{top_s.get('revenue_pct',0)}%", f"{mid_s.get('revenue_pct',0)}%", f"{low_s.get('revenue_pct',0)}%"],
                textposition="outside",
            ))
            fig3.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=240,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                yaxis_title="% of Total Revenue", xaxis_title="",
            )
            st.plotly_chart(fig3, width="stretch")
    else:
        st.info("Upload order history to see the Top vs Low customer breakdown.")
    ui.card_close()
