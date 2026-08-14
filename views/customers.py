"""Customer Analytics - demographics, segments, top customers."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_segments, get_cached_value_tiers
from utils.ml_engine import segment_customers


def render(data, user):
    ui.page_header("Customer Analytics", "HOME &nbsp;›&nbsp; CUSTOMERS")

    customers = data.get("customers", pd.DataFrame())
    merged = get_merged_orders(data)

    if customers.empty:
        st.warning("No customer data available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Customers", f"{len(customers):,}", "Active base", "👥", "#00c2d1")
    with c2:
        repeat = merged.groupby("CustomerID")["OrderID"].count()
        repeat_pct = (repeat[repeat > 1].shape[0] / max(len(repeat), 1)) * 100 if not merged.empty else 0
        ui.kpi_card("Repeat Customers", f"{repeat_pct:.1f}%", "of active buyers", "🔁", "#6c5ce7")
    with c3:
        avg_age = customers["Age"].mean()
        ui.kpi_card("Average Age", f"{avg_age:.0f} yrs", "customer base", "🎂", "#5b6ee1")
    with c4:
        avg_income = customers["Income"].mean()
        ui.kpi_card("Average Income", f"₹{avg_income:,.0f}", "per year", "💵", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("Age Distribution")
        age_bins = [17, 24, 34, 44, 54, 64, 100]
        age_labels = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
        age_band = pd.cut(customers["Age"], bins=age_bins, labels=age_labels)
        age_dist = age_band.value_counts().reindex(age_labels).reset_index()
        age_dist.columns = ["Age Group", "Customers"]
        fig = px.bar(age_dist, x="Age Group", y="Customers", text="Customers",
                     color="Age Group", color_discrete_sequence=ui.CHART_COLORWAY)
        fig.update_traces(textposition="outside", marker_line_width=0, showlegend=False)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           bargap=0.35, showlegend=False,
                           yaxis=dict(showticklabels=False, showgrid=False, title=None))
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col2:
        ui.card_open("Gender Split")
        gender_counts = customers["Gender"].value_counts().reset_index()
        gender_counts.columns = ["Gender", "Count"]
        fig = px.pie(gender_counts, names="Gender", values="Count", hole=0.55,
                     color_discrete_sequence=["#161029", "#6c5ce7", "#00c2d1"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280)
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        ui.card_open("Customers by State")
        state_counts = customers["State"].value_counts().reset_index().head(10)
        state_counts.columns = ["State", "Count"]
        fig = px.bar(state_counts, x="Count", y="State", orientation="h",
                     color_discrete_sequence=["#5b6ee1"])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
        ui.card_close()

    with col4:
        ui.card_open("Customer Segments (K-Means)")
        if not merged.empty:
            seg = get_cached_segments(merged)
            seg_counts = seg["Segment"].value_counts().reset_index()
            seg_counts.columns = ["Segment", "Count"]
            color_map = {"Gold": "#e6b800", "Silver": "#a6a6a6", "Bronze": "#b5651d"}
            fig = px.pie(seg_counts, names="Segment", values="Count", hole=0.55,
                         color="Segment", color_discrete_map=color_map)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
            st.plotly_chart(fig, width="stretch")
            st.caption("Segments computed via K-Means clustering on Recency, Frequency, and Monetary (RFM) value.")
        else:
            st.info("No order history to compute segments yet.")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    tiered = pd.DataFrame()
    if not merged.empty:
        tiered, tier_stats = get_cached_value_tiers(merged)
        if tier_stats:
            top_s, low_s = tier_stats.get("Top", {}), tier_stats.get("Low", {})
            st.caption(
                f"💎 **Top 20%** of customers ({top_s.get('count', 0):,}) drive "
                f"**{top_s.get('revenue_pct', 0)}%** of revenue · **Bottom 20%** ({low_s.get('count', 0):,}) "
                f"drive only **{low_s.get('revenue_pct', 0)}%** — kept separate below so each group is easy to analyze."
            )

        name_lookup = customers.set_index("CustomerID")["Name"] if "Name" in customers.columns else pd.Series(dtype=str)
        tiered = tiered.copy()
        tiered["Name"] = tiered["CustomerID"].map(name_lookup).fillna("—")

    col_top, col_low = st.columns(2)
    with col_top:
        ui.card_open("🏆 Top Value Customers", accent="#00c2d1")
        if not merged.empty and not tiered.empty:
            top_tbl = tiered[tiered["ValueTier"] == "Top"].sort_values("Monetary", ascending=False).head(10)
            top_tbl = top_tbl[["CustomerID", "Name", "Segment", "Monetary"]].rename(columns={"Monetary": "Total Spend (₹)"})
            top_tbl["Total Spend (₹)"] = top_tbl["Total Spend (₹)"].round(0)
            st.dataframe(top_tbl, width="stretch", hide_index=True)
        else:
            st.info("No order data available.")
        ui.card_close()

    with col_low:
        ui.card_open("⚠️ Low Value / At-Risk Customers", accent="#8b8fb3")
        if not merged.empty and not tiered.empty:
            low_tbl = tiered[tiered["ValueTier"] == "Low"].sort_values("Monetary").head(10)
            low_tbl = low_tbl[["CustomerID", "Name", "Segment", "Monetary"]].rename(columns={"Monetary": "Total Spend (₹)"})
            low_tbl["Total Spend (₹)"] = low_tbl["Total Spend (₹)"].round(0)
            st.dataframe(low_tbl, width="stretch", hide_index=True)
            st.caption("Candidates for re-engagement campaigns — see the AI Action Center in Insights.")
        else:
            st.info("No order data available.")
        ui.card_close()
