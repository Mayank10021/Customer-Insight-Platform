"""
Customer 360 — focused on VALUABLE customers, not every customer.

Per business rule: this page identifies important customers automatically
(VIP, high spenders, frequent buyers, loyal customers, highest CLV, etc.)
and only shows those — browsing the entire customer base isn't the point
of this module; Data Explorer already covers that. Selecting a filter
shows how much of total revenue that group represents, then drills into
a full CRM-style profile with AI recommendations for any customer in it.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils import ui
from utils.data_handler import get_merged_orders, get_cached_value_tiers, get_important_customers, get_customer_profile
from utils.ml_engine import RFM_SEGMENT_COLORS, health_score_band

FILTER_OPTIONS = [
    "VIP", "High Spending", "Frequent Buyers", "Repeat Customers",
    "Loyal Customers", "Recent Customers", "Top 10", "Top 50", "Top 100", "Highest CLV",
]

FILTER_DESCRIPTIONS = {
    "VIP": "Top-tier spenders who are also Champions or Loyal Customers — your most valuable accounts.",
    "High Spending": "Top 20% of customers by total spend.",
    "Frequent Buyers": "Customers with 8 or more orders.",
    "Repeat Customers": "Customers with 2 or more orders.",
    "Loyal Customers": "Champions, Loyal Customers, and Potential Loyalists segments.",
    "Recent Customers": "Purchased within the last 30 days.",
    "Top 10": "The 10 highest-spending customers.",
    "Top 50": "The 50 highest-spending customers.",
    "Top 100": "The 100 highest-spending customers.",
    "Highest CLV": "Ranked by projected customer lifetime value.",
}


def _risk_color(score):
    if score is None:
        return "#8b8fb3"
    if score >= 60:
        return "#ff4d4d"
    if score >= 30:
        return "#f4a261"
    return "#00c2d1"


def _value_tier_color(tier):
    return {"Top": "#00c2d1", "Mid": "#5b6ee1", "Low": "#8b8fb3"}.get(tier, "#8b8fb3")


def render(data, user):
    ui.page_header("Customer 360", "HOME &nbsp;›&nbsp; CUSTOMER 360")

    customers = data.get("customers", pd.DataFrame())
    if customers.empty:
        st.info("📤 Upload your customer dataset to unlock Customer 360 profiles.")
        return

    # ---------------------------------------------------------------
    # DIRECT PROFILE DEEP-LINK — e.g. right after Add New Data creates a
    # customer, jump straight to their profile even if they wouldn't (yet)
    # qualify under any of the "important customers" filters below.
    # ---------------------------------------------------------------
    direct_id = st.session_state.get("c360_direct_customer_id")
    if direct_id:
        if st.button("← Back to filtered view"):
            st.session_state.pop("c360_direct_customer_id", None)
            st.rerun()
        profile = get_customer_profile(data, direct_id)
        if profile is None:
            st.error(f"Could not find a profile for customer {direct_id}.")
            st.session_state.pop("c360_direct_customer_id", None)
            return
        _render_profile(profile, data, user)
        return

    merged = get_merged_orders(data)
    if merged.empty:
        st.info("📤 Upload order history to identify your most valuable customers.")
        return

    # ---------------------------------------------------------------
    # REVENUE IMPACT BANNER — Top vs Mid vs Low contribution to sales
    # ---------------------------------------------------------------
    _, tier_stats = get_cached_value_tiers(merged)
    if tier_stats:
        top_s, mid_s, low_s = tier_stats.get("Top", {}), tier_stats.get("Mid", {}), tier_stats.get("Low", {})
        st.markdown(f"""
        <div style='background:linear-gradient(135deg, #161029 0%, #00c2d1 100%);
                    padding:16px 20px; border-radius:12px; color:white; margin-bottom:18px;'>
            <div style='font-size:13.5px; font-weight:700;'>📊 Revenue Impact: Top vs Low Value Customers</div>
            <div style='font-size:12px; color:rgba(255,255,255,0.9); margin-top:6px;'>
                Your <b>top 20% of customers</b> ({top_s.get('count', 0):,} people) drive
                <b>{top_s.get('revenue_pct', 0)}%</b> of total revenue (₹{top_s.get('revenue', 0):,.0f}) —
                while the <b>bottom 20%</b> ({low_s.get('count', 0):,} people) contribute only
                <b>{low_s.get('revenue_pct', 0)}%</b> (₹{low_s.get('revenue', 0):,.0f}).
                The middle 60% brings in {mid_s.get('revenue_pct', 0)}%.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # BUSINESS-RULE FILTER — pick which important customers to see
    # ---------------------------------------------------------------
    ui.card_open("🎯 Focus on Important Customers")
    st.caption("Customer 360 only analyzes customers who matter to the business — pick a rule below "
               "instead of browsing every customer.")

    filt_col, count_col = st.columns([2, 1])
    with filt_col:
        chosen_filter = st.selectbox("Business rule", FILTER_OPTIONS, index=6, key="c360_filter")
        st.caption(FILTER_DESCRIPTIONS.get(chosen_filter, ""))

    important = get_important_customers(data, merged, chosen_filter)

    with count_col:
        ui.kpi_card("Customers in this view", f"{len(important):,}", chosen_filter, "🎯", "#5b6ee1")

    if important.empty:
        st.info("No customers match this rule yet.")
        ui.card_close()
        return

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    show_cols = ["CustomerID", "Name", "Segment", "ValueTier", "Recency", "Frequency", "Monetary", "CLV"]
    display_df = important[show_cols].rename(columns={
        "Recency": "Days Since Purchase", "Frequency": "Orders", "Monetary": "Total Spend (₹)", "CLV": "Est. CLV (₹)",
    })
    st.dataframe(display_df.head(200), width="stretch", hide_index=True, height=280)

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    options = {f"{row.CustomerID} — {row.Name}": row.CustomerID for row in important.itertuples()}
    pick = st.selectbox(f"Open a profile from these {len(important):,} customers", list(options.keys()), key="c360_pick")
    selected_id = options[pick] if pick else None
    ui.card_close()

    if not selected_id:
        return

    profile = get_customer_profile(data, selected_id)
    if profile is None:
        st.error("Could not build a profile for that customer.")
        return

    _render_profile(profile, data, user)


def _render_profile(profile, data, user):
    # ---------------------------------------------------------------
    # PROFILE HEADER CARD
    # ---------------------------------------------------------------
    seg_color = RFM_SEGMENT_COLORS.get(profile["Segment"], "#8b8fb3")
    health_label, health_color = health_score_band(profile["HealthScore"])

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    ui.card_open()
    h1, h2 = st.columns([1, 4])
    with h1:
        st.markdown(f"""
        <div style="width:78px; height:78px; border-radius:50%; background:{seg_color};
                    display:flex; align-items:center; justify-content:center;
                    font-size:30px; color:white; font-weight:800;">
            {str(profile.get('Name','?'))[:1].upper()}
        </div>
        """, unsafe_allow_html=True)
    with h2:
        vip_badge = " &nbsp;👑 <b style='color:#6c5ce7;'>VIP</b>" if profile.get("IsVIP") else ""
        st.markdown(f"""
        <div style="font-size:20px; font-weight:800; color:#161029;">{profile.get('Name','Unknown')}{vip_badge}</div>
        <div style="font-size:12.5px; color:#8b8fb3; margin-bottom:6px;">
            {profile.get('CustomerID')} &nbsp;·&nbsp; {profile.get('Email','')} &nbsp;·&nbsp; {profile.get('Phone','')}
        </div>
        """, unsafe_allow_html=True)
        badge_cols = st.columns(5)
        with badge_cols[0]:
            ui.pill(profile["Segment"], seg_color)
        with badge_cols[1]:
            ui.pill(f"{profile.get('ValueTier','Mid')} Value", _value_tier_color(profile.get("ValueTier", "Mid")))
        with badge_cols[2]:
            ui.pill(profile.get("CustomerType", ""), "#161029")
        with badge_cols[3]:
            ui.pill(f"{profile.get('LoyaltyTier','')} Tier", "#6c5ce7")
        with badge_cols[4]:
            ui.pill(f"Health: {health_label}", health_color)
    ui.card_close()

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # KPI ROW
    # ---------------------------------------------------------------
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        ui.kpi_card("Total Orders", f"{profile['TotalOrders']:,}", "lifetime", "🧾", "#161029")
    with k2:
        ui.kpi_card("Total Spending", f"₹{profile['TotalSpending']:,.0f}", "lifetime", "💰", "#00c2d1")
    with k3:
        ui.kpi_card("Avg Order Value", f"₹{profile['AvgOrderValue']:,.0f}", "per order", "📱", "#6c5ce7")
    with k4:
        ui.kpi_card("Lifetime Value (CLV)", f"₹{profile['CLV']:,.0f}", "projected", "📈", "#5b6ee1")
    with k5:
        days = profile.get("DaysSinceLastPurchase")
        ui.kpi_card("Last Purchase", f"{days} days ago" if days is not None else "N/A", "recency", "🕒", "#8b8fb3")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # SCORES + AI SUMMARY + AI RECOMMENDATIONS
    # ---------------------------------------------------------------
    col_scores, col_ai = st.columns([1, 1.4])
    with col_scores:
        ui.card_open("📊 Scorecard")
        ui.score_bar("Customer Health Score", profile["HealthScore"], health_color)
        if profile.get("ChurnRisk") is not None:
            ui.score_bar("Churn Risk", profile["ChurnRisk"], _risk_color(profile["ChurnRisk"]))
        ui.score_bar("Retention Score", profile["RetentionScore"], "#00c2d1")
        st.caption(
            f"RFM → Recency: {profile['RFM_Recency']}d · Frequency: {profile['RFM_Frequency']} orders "
            f"· Monetary: ₹{profile['RFM_Monetary']:,.0f}"
        )
        ui.card_close()

    with col_ai:
        ui.card_open("🤖 AI-Generated Customer Summary")
        st.markdown(profile["AISummary"])
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.markdown("**Recommended Actions:**")
        for rec in profile.get("AIRecommendations", []):
            st.markdown(f"- {rec}")
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # PREFERENCES + FAVORITES
    # ---------------------------------------------------------------
    col_prefs, col_fav = st.columns(2)
    with col_prefs:
        ui.card_open("⚙️ Preferences & Behavior")
        ui.mini_item("💳", "Preferred Payment", profile.get("PreferredPaymentMethod", "N/A"))
        ui.mini_item("📅", "Preferred Shopping Day", profile.get("PreferredShoppingDay", "N/A"))
        ui.mini_item("📦", "Avg Basket Size", f"{profile.get('AvgBasketSize', 0):.1f} items")
        ui.mini_item("🔁", "Purchase Frequency", f"{profile.get('PurchaseFrequency', 0)} orders/month")
        ui.mini_item("⭐", "Avg Feedback Rating", f"{profile['AvgRating']:.1f} / 5" if profile.get("AvgRating") else "No ratings yet")
        ui.mini_item("💬", "Sentiment", profile.get("SentimentSummary", "N/A").title())
        ui.card_close()

    with col_fav:
        ui.card_open("❤️ Favorite Products & Categories")
        if profile.get("FavoriteProducts"):
            for p in profile["FavoriteProducts"]:
                st.markdown(f"- {p}")
        else:
            st.caption("No purchase history yet.")
        if profile.get("FavoriteCategories"):
            st.markdown("**Top Categories:** " + ", ".join(profile["FavoriteCategories"]))
        ui.card_close()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # PURCHASE TIMELINE
    # ---------------------------------------------------------------
    ui.card_open("🕐 Purchase Timeline")
    recent = profile.get("RecentOrders", pd.DataFrame())
    if not recent.empty:
        show_cols2 = [c for c in ["Date", "OrderID", "ProductName", "Category", "Quantity", "TotalAmount", "StoreID"] if c in recent.columns]
        st.dataframe(recent[show_cols2], width="stretch", hide_index=True)

        timeline = recent.sort_values("Date")
        fig = px.scatter(
            timeline, x="Date", y="TotalAmount", size="TotalAmount",
            color_discrete_sequence=["#5b6ee1"], hover_data=["ProductName"] if "ProductName" in timeline.columns else None,
        )
        fig.update_traces(mode="markers+lines", line=dict(color="#e9ecf5"))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260,
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No order history for this customer yet.")
    ui.card_close()

    # ---------------------------------------------------------------
    # RECENT FEEDBACK
    # ---------------------------------------------------------------
    recent_fb = profile.get("RecentFeedback", pd.DataFrame())
    if not recent_fb.empty:
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        ui.card_open("💬 Recent Feedback")
        show_cols3 = [c for c in ["Date", "ProductID", "Rating", "Sentiment", "Review"] if c in recent_fb.columns]
        st.dataframe(recent_fb[show_cols3], width="stretch", hide_index=True)
        ui.card_close()
