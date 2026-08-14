"""
Enhanced Business Insights - AI-generated recommendations with detailed explanations for all roles
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_segments, get_cached_rfm11, get_cached_sentiment, get_cached_value_tiers
from utils.ml_engine import (
    segment_customers, build_rfm, apply_sentiment_to_feedback,
    segment_customers_rfm11, RFM_SEGMENT_COLORS, compute_health_score, health_score_band,
)


def render(data, user):
    ui.page_header("💡 Business Insights & Analytics", "HOME &nbsp;›&nbsp; BUSINESS INSIGHTS")
    
    # Role-based header
    role_messages = {
        "Admin": "Complete business overview with all metrics and recommendations",
        "Vendor": "Insights scoped to your own brand's customers and products",
        "Viewer": "Essential dashboards and key performance indicators"
    }
    
    role_msg = role_messages.get(user.get("role", "Viewer"), "Business insights dashboard")
    
    st.markdown(f"""
    <div style='background:linear-gradient(135deg, #6c5ce7 0%, #ff9f86 100%); 
                padding:16px; border-radius:12px; color:white; margin-bottom:20px;'>
        <div style='font-size:13px; font-weight:600;'>👤 {user.get('name', 'User')} ({user.get('role', 'Viewer')})</div>
        <div style='font-size:12px; color:rgba(255,255,255,0.85); margin-top:4px;'>
            {role_msg}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data
    merged = get_merged_orders(data)
    customers = data.get("customers", pd.DataFrame())
    products = data.get("products", pd.DataFrame())
    feedback = data.get("feedback", pd.DataFrame())
    
    if merged.empty or customers.empty or products.empty:
        st.warning("📊 Not enough data to generate insights yet. Please upload data first.")
        return
    
    # ============= COMPUTE ALL INSIGHTS =============
    top_products = merged.groupby(["ProductID", "ProductName"])["TotalAmount"].sum().nlargest(3).reset_index() if not merged.empty else pd.DataFrame()
    
    rfm = build_rfm(merged) if not merged.empty else pd.DataFrame()
    avg_recency = rfm["Recency"].mean() if not rfm.empty else 0
    churn_risk = rfm[rfm["Recency"] > avg_recency * 1.5] if not rfm.empty else pd.DataFrame()
    churn_count = len(churn_risk)
    churn_pct = round((churn_count / len(rfm)) * 100, 1) if len(rfm) > 0 else 0
    
    low_stock = products[products["Stock"] < 20] if not products.empty else pd.DataFrame()
    
    segments = get_cached_segments(merged) if not merged.empty else pd.DataFrame()
    gold_count = len(segments[segments["Segment"] == "Gold"]) if not segments.empty else 0
    gold_pct = round((gold_count / len(segments)) * 100, 1) if len(segments) > 0 else 0
    
    fb_scored = get_cached_sentiment(feedback) if not feedback.empty else pd.DataFrame()
    neg_reviews = fb_scored[fb_scored["Sentiment"] == "Negative"] if not fb_scored.empty else pd.DataFrame()
    neg_pct = round((len(neg_reviews) / len(feedback)) * 100, 1) if len(feedback) > 0 else 0
    
    # Monthly trend
    monthly = merged.copy() if not merged.empty else pd.DataFrame()
    if not monthly.empty:
        monthly["Date"] = pd.to_datetime(monthly["Date"], errors="coerce")
        monthly["Month"] = monthly["Date"].dt.to_period("M")
        monthly_sales = monthly.groupby("Month")["TotalAmount"].sum()
        sales_trend_pct = (monthly_sales.iloc[-1] - monthly_sales.iloc[-2]) / monthly_sales.iloc[-2] * 100 if len(monthly_sales) > 1 else 0
    else:
        monthly_sales = pd.Series()
        sales_trend_pct = 0
    
    # ============= KPI SECTION =============
    st.markdown("<h3 style='color:#161029; margin:0 0 16px 0;'>📈 Key Performance Indicators</h3>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4, gap="small")
    
    with m1:
        ui.card_open()
        top_product = top_products.iloc[0]["ProductName"] if not top_products.empty else "—"
        top_revenue = top_products.iloc[0]["TotalAmount"] if not top_products.empty else 0
        st.markdown(f"""
        <div style='display:flex; align-items:flex-start; gap:12px;'>
            <div style='font-size:28px;'>💰</div>
            <div style='flex:1;'>
                <div style='font-size:10px; color:#8b8fb3; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>
                    Top Revenue Driver
                </div>
                <div style='font-size:16px; font-weight:800; color:#161029; margin:8px 0 6px 0;'>
                    {top_product}
                </div>
                <div style='font-size:12px; color:#FF7F66; font-weight:600;'>
                    ₹{top_revenue:,.0f}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        ui.card_close()
    
    with m2:
        ui.card_open()
        st.markdown(f"""
        <div style='display:flex; align-items:flex-start; gap:12px;'>
            <div style='font-size:28px;'>⚠️</div>
            <div style='flex:1;'>
                <div style='font-size:10px; color:#8b8fb3; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>
                    Churn Risk
                </div>
                <div style='font-size:16px; font-weight:800; color:#161029; margin:8px 0 6px 0;'>
                    {churn_count:,}
                </div>
                <div style='font-size:12px; color:#FFA500; font-weight:600;'>
                    {churn_pct:.1f}% at risk
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        ui.card_close()
    
    with m3:
        ui.card_open()
        st.markdown(f"""
        <div style='display:flex; align-items:flex-start; gap:12px;'>
            <div style='font-size:28px;'>👑</div>
            <div style='flex:1;'>
                <div style='font-size:10px; color:#8b8fb3; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>
                    VIP Gold Tier
                </div>
                <div style='font-size:16px; font-weight:800; color:#161029; margin:8px 0 6px 0;'>
                    {gold_count:,}
                </div>
                <div style='font-size:12px; color:#2EC4B6; font-weight:600;'>
                    {gold_pct:.1f}% of base
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        ui.card_close()
    
    with m4:
        ui.card_open()
        low_count = len(low_stock)
        st.markdown(f"""
        <div style='display:flex; align-items:flex-start; gap:12px;'>
            <div style='font-size:28px;'>📦</div>
            <div style='flex:1;'>
                <div style='font-size:10px; color:#8b8fb3; font-weight:700; text-transform:uppercase; letter-spacing:1px;'>
                    Low Stock Items
                </div>
                <div style='font-size:16px; font-weight:800; color:#161029; margin:8px 0 6px 0;'>
                    {low_count}
                </div>
                <div style='font-size:12px; color:#C4B92E; font-weight:600;'>
                    Need reorder
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        ui.card_close()
    
    # ============= CHARTS SECTION =============
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#161029; margin:0 0 16px 0;'>📊 Detailed Analysis</h3>", unsafe_allow_html=True)
    
    chart_l, chart_r = st.columns([1.3, 1], gap="medium")
    
    # Revenue Trend
    with chart_l:
        ui.card_open()
        st.markdown("<h4 style='color:#161029; font-size:14px; font-weight:800; margin:0 0 12px 0;'>📈 Monthly Revenue Trend</h4>", unsafe_allow_html=True)
        
        if len(monthly_sales) > 0:
            monthly_sales_reset = monthly_sales.reset_index()
            monthly_sales_reset.columns = ["Month", "Revenue"]
            monthly_sales_reset["Month"] = monthly_sales_reset["Month"].astype(str)
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=monthly_sales_reset["Month"],
                y=monthly_sales_reset["Revenue"],
                mode="lines+markers",
                name="Revenue",
                line=dict(color="#FF7F66", width=3),
                marker=dict(size=6),
                fill="tozeroy",
                fillcolor="rgba(255, 127, 102, 0.1)",
                hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>",
            ))
            fig_trend.update_layout(
                height=280, margin=dict(l=0, r=0, t=0, b=0),
                hovermode="x", plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)", xaxis_showgrid=False,
                yaxis_showgrid=True, yaxis_gridwidth=1, yaxis_gridcolor="rgba(0,0,0,0.05)",
                font=dict(family="sans-serif", size=11, color="#8b8fb3"),
                xaxis=dict(showline=False), yaxis=dict(showline=False),
            )
            st.plotly_chart(fig_trend, width="stretch")
            
            if sales_trend_pct < -10:
                st.warning(f"📉 Sales declined {abs(sales_trend_pct):.1f}% — investigate causes")
        else:
            st.info("No sales trend data available")
        
        ui.card_close()
        
        # Explanation
        st.markdown("""
        <div style='background:#f5f7fb; padding:12px; border-radius:8px; font-size:11px; margin-top:8px; color:#555;'>
        <strong>📋 What This Chart Shows:</strong> Monthly revenue trend helps identify seasonal patterns and growth/decline periods. 
        Use this to plan promotions, inventory, and staffing.
        </div>
        """, unsafe_allow_html=True)
    
    # Customer Segments
    with chart_r:
        ui.card_open()
        st.markdown("<h4 style='color:#161029; font-size:14px; font-weight:800; margin:0 0 12px 0;'>👥 Customer Segments</h4>", unsafe_allow_html=True)
        
        if not segments.empty:
            seg_counts = segments["Segment"].value_counts()
            colors_map = {"Gold": "#FFD700", "Silver": "#C0C0C0", "Bronze": "#CD7F32"}
            colors = [colors_map.get(seg, "#95a5a6") for seg in seg_counts.index]
            
            fig_seg = go.Figure(data=[go.Pie(
                labels=seg_counts.index,
                values=seg_counts.values,
                hole=0.55,
                marker=dict(colors=colors),
                textposition="inside",
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>%{value:,} customers<extra></extra>",
            )])
            fig_seg.update_layout(
                height=280, margin=dict(l=0, r=0, t=0, b=0),
                font=dict(family="sans-serif", size=11, color="#8b8fb3"),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_seg, width="stretch")
        else:
            st.info("No segment data available")
        
        ui.card_close()
        
        # Explanation
        st.markdown("""
        <div style='background:#f5f7fb; padding:12px; border-radius:8px; font-size:11px; margin-top:8px; color:#555;'>
        <strong>📋 What This Chart Shows:</strong> Customer distribution across segments. Gold tier generates most revenue. 
        Focus retention efforts on top segments.
        </div>
        """, unsafe_allow_html=True)
    
    # ============= DETAILED TABLES SECTION =============
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#161029; margin:0 0 16px 0;'>📋 Detailed Data Tables</h3>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs([
        "🏆 Top Products",
        "⚠️ At-Risk Customers",
        "📦 Low Stock Items"
    ])
    
    # Top Products Table
    with tab1:
        if not top_products.empty:
            display_df = top_products.copy()
            display_df.columns = ["Product ID", "Product Name", "Total Revenue (₹)"]
            display_df["Total Revenue (₹)"] = display_df["Total Revenue (₹)"].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(display_df, width="stretch", hide_index=True)
            
            st.markdown("""
            <div style='background:#fff5f3; padding:12px; border-radius:8px; font-size:11px; margin-top:12px; color:#555;'>
            <strong>💡 Insight:</strong> These are your best-performing products. Ensure adequate stock, promote effectively, 
            and consider bundling with slower-moving items. Monitor competitor pricing.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No product data available")
    
    # Churn Risk Table
    with tab2:
        if not churn_risk.empty:
            churn_display = churn_risk.copy()
            churn_display = churn_display.sort_values("Recency", ascending=False).head(15)
            st.dataframe(churn_display[["CustomerID", "Recency", "Frequency", "Monetary"]], 
                        width="stretch", hide_index=True)
            
            st.markdown(f"""
            <div style='background:#fff5f3; padding:12px; border-radius:8px; font-size:11px; margin-top:12px; color:#555;'>
            <strong>💡 Action Items:</strong> {churn_count} customers haven't purchased in {avg_recency*1.5:.0f}+ days. 
            <ul style='margin:6px 0; padding-left:20px;'>
                <li>Send personalized re-engagement emails</li>
                <li>Offer exclusive comeback discounts</li>
                <li>Conduct customer feedback surveys</li>
                <li>Target with relevant product recommendations</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No churn risk data available")
    
    # Low Stock Items
    with tab3:
        if not low_stock.empty:
            stock_display = low_stock[["ProductID", "ProductName", "Stock", "Price"]].copy()
            stock_display.columns = ["Product ID", "Product Name", "Current Stock", "Price (₹)"]
            st.dataframe(stock_display, width="stretch", hide_index=True)
            
            st.markdown(f"""
            <div style='background:#fffdf5; padding:12px; border-radius:8px; font-size:11px; margin-top:12px; color:#555;'>
            <strong>💡 Recommendation:</strong> {low_count} items below safety stock of 20 units. 
            <ul style='margin:6px 0; padding-left:20px;'>
                <li>Initiate purchase orders immediately</li>
                <li>Consider expedited delivery for high-demand items</li>
                <li>Notify customers of stock status</li>
                <li>Review inventory turnover rates</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("All items well-stocked")
    
    # ============= ACTIONABLE INSIGHTS =============
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#161029; margin:0 0 16px 0;'>🎯 Recommended Actions</h3>", unsafe_allow_html=True)
    
    insight_cols = st.columns(3, gap="medium")
    
    with insight_cols[0]:
        st.markdown("""
        <div style='background:#f0f9f7; border-radius:12px; padding:16px; border-left:4px solid #2EC4B6;'>
            <div style='font-size:13px; font-weight:700; color:#161029; margin-bottom:8px;'>
                👑 VIP Retention Program
            </div>
            <div style='font-size:12px; color:#555; line-height:1.6;'>
                <strong>Why:</strong> Gold tier drives ~70% of revenue<br>
                <strong>Action:</strong>
                <ul style='margin:6px 0; padding-left:16px;'>
                    <li>Launch loyalty rewards</li>
                    <li>Exclusive early access</li>
                    <li>Dedicated support</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with insight_cols[1]:
        st.markdown("""
        <div style='background:#fff5f3; border-radius:12px; padding:16px; border-left:4px solid #FF7F66;'>
            <div style='font-size:13px; font-weight:700; color:#161029; margin-bottom:8px;'>
                🎣 Churn Prevention
            </div>
            <div style='font-size:12px; color:#555; line-height:1.6;'>
                <strong>Why:</strong> Prevent revenue loss<br>
                <strong>Action:</strong>
                <ul style='margin:6px 0; padding-left:16px;'>
                    <li>Re-engagement campaigns</li>
                    <li>Personalized offers</li>
                    <li>Feedback surveys</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with insight_cols[2]:
        st.markdown(f"""
        <div style='background:#fffdf5; border-radius:12px; padding:16px; border-left:4px solid #C4B92E;'>
            <div style='font-size:13px; font-weight:700; color:#161029; margin-bottom:8px;'>
                📦 Inventory Management
            </div>
            <div style='font-size:12px; color:#555; line-height:1.6;'>
                <strong>Why:</strong> Prevent stockouts & lost sales<br>
                <strong>Action:</strong>
                <ul style='margin:6px 0; padding-left:16px;'>
                    <li>Urgent reorders ({low_count} items)</li>
                    <li>Set auto-reorder points</li>
                    <li>Forecast demand</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ============= ACTION CENTER (real customer-level lists, 11-tier RFM) =============
    _render_action_center(data, merged, customers)


def _render_action_center(data, merged, customers):
    """
    AI Recommendation Center / Action Center — concrete, named-customer
    action lists (not generic advice) built from the 11-tier RFM
    segmentation + health score engine shared with Customer 360.
    """
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#161029; margin:0 0 4px 0;'>🎯 AI Action Center</h3>", unsafe_allow_html=True)
    st.caption("Concrete, customer-level recommendations generated from RFM segmentation and health scores — refreshed automatically as new data is uploaded.")

    if merged.empty or customers.empty:
        st.info("Upload order history to populate the Action Center.")
        return

    rfm11 = get_cached_rfm11(merged)
    if rfm11.empty:
        st.info("Not enough order history yet to compute action lists.")
        return

    tiered, tier_stats = get_cached_value_tiers(merged)
    tier_lookup = tiered.set_index("CustomerID")["ValueTier"] if not tiered.empty else pd.Series(dtype=str)

    name_lookup = customers.set_index("CustomerID")["Name"] if "Name" in customers.columns else pd.Series(dtype=str)
    rfm11 = rfm11.copy()
    rfm11["Name"] = rfm11["CustomerID"].map(name_lookup).fillna("—")
    rfm11["ValueTier"] = rfm11["CustomerID"].map(tier_lookup).fillna("Mid")
    rfm11["HealthScore"] = rfm11.apply(
        lambda r: compute_health_score(r["Recency"], r["Frequency"], r["Monetary"]), axis=1
    )

    def _table(df, cols_map, n=8):
        if df.empty:
            st.caption("None found in the current dataset.")
            return
        d = df.head(n)[list(cols_map.keys())].copy()
        d.columns = list(cols_map.values())
        st.dataframe(d, width="stretch", hide_index=True)

    cols_show = {"CustomerID": "Customer ID", "Name": "Name", "Recency": "Days Since Purchase",
                 "Frequency": "Orders", "Monetary": "Total Spend (₹)", "HealthScore": "Health Score"}

    tabs = st.tabs([
        "💎 Top vs Low Value", "🔴 High Risk", "🎁 Reward", "📣 Re-engage",
        "⭐ Premium-Ready", "🔁 Likely to Buy Again", "📋 Campaigns & Priorities",
    ])

    with tabs[0]:
        st.markdown("**Customers split by spend, kept in separate lists so each group is easy to analyze on its own.**")
        if tier_stats:
            top_s, mid_s, low_s = tier_stats.get("Top", {}), tier_stats.get("Mid", {}), tier_stats.get("Low", {})
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Top 20% Revenue Share", f"{top_s.get('revenue_pct', 0)}%", f"{top_s.get('count', 0):,} customers")
            with c2:
                st.metric("Middle 60% Revenue Share", f"{mid_s.get('revenue_pct', 0)}%", f"{mid_s.get('count', 0):,} customers")
            with c3:
                st.metric("Bottom 20% Revenue Share", f"{low_s.get('revenue_pct', 0)}%", f"{low_s.get('count', 0):,} customers")
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        col_top, col_low = st.columns(2)
        with col_top:
            st.markdown("**🏆 Top Value Customers**")
            top_tbl = rfm11[rfm11["ValueTier"] == "Top"].sort_values("Monetary", ascending=False)
            _table(top_tbl, cols_show, n=10)
        with col_low:
            st.markdown("**⚠️ Low Value Customers**")
            low_tbl = rfm11[rfm11["ValueTier"] == "Low"].sort_values("Monetary")
            _table(low_tbl, cols_show, n=10)

    with tabs[1]:
        st.markdown("**Customers to prioritize for retention — highest value at greatest churn risk.**")
        high_risk = rfm11[rfm11["Segment"].isin(["At Risk", "Lost Customers"])].sort_values("Monetary", ascending=False)
        _table(high_risk, cols_show)

    with tabs[2]:
        st.markdown("**Champions — reward these customers to reinforce loyalty.**")
        reward = rfm11[rfm11["Segment"] == "Champions"].sort_values("Monetary", ascending=False)
        _table(reward, cols_show)

    with tabs[3]:
        st.markdown("**Cooling-off customers who need a nudge before they disengage further.**")
        reengage = rfm11[rfm11["Segment"].isin(["Need Attention", "Price Sensitive"])].sort_values("Recency", ascending=False)
        _table(reengage, cols_show)

    with tabs[4]:
        st.markdown("**Strong engagement and spend — good candidates for a premium/VIP membership upsell.**")
        premium_ready = rfm11[rfm11["Segment"].isin(["Loyal Customers", "Potential Loyalists"])].sort_values("Monetary", ascending=False)
        _table(premium_ready, cols_show)

    with tabs[5]:
        st.markdown("**Recently active, high-frequency customers most likely to purchase again soon.**")
        likely_again = rfm11[rfm11["Segment"].isin(["Champions", "Loyal Customers", "Promising Customers"])].sort_values("Recency")
        _table(likely_again, cols_show)

    with tabs[6]:
        seg_counts = rfm11["Segment"].value_counts()
        total = len(rfm11)
        st.markdown("**Suggested Marketing Campaigns**")
        campaigns = []
        if seg_counts.get("Champions", 0) > 0:
            campaigns.append(f"🏆 **VIP Loyalty Drop** — {seg_counts['Champions']} Champions ready for an exclusive early-access reward.")
        if seg_counts.get("At Risk", 0) + seg_counts.get("Lost Customers", 0) > 0:
            campaigns.append(f"🎯 **Win-Back Offer** — {seg_counts.get('At Risk', 0) + seg_counts.get('Lost Customers', 0)} at-risk/lost customers targeted with a time-limited discount.")
        if seg_counts.get("New Customers", 0) > 0:
            campaigns.append(f"👋 **Welcome Series** — {seg_counts['New Customers']} new customers onboarded with a 3-email welcome sequence.")
        if seg_counts.get("Price Sensitive", 0) > 0:
            campaigns.append(f"💸 **Value Bundle Promo** — {seg_counts['Price Sensitive']} price-sensitive customers offered bundle discounts.")
        if seg_counts.get("Potential Loyalists", 0) > 0:
            campaigns.append(f"⭐ **Membership Upgrade Nudge** — {seg_counts['Potential Loyalists']} potential loyalists invited to join a premium tier.")
        for c in campaigns:
            st.markdown(f"- {c}")

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown("**Priority Actions This Week**")
        high_risk_n = len(rfm11[rfm11["Segment"].isin(["At Risk", "Lost Customers"])])
        champions_n = seg_counts.get("Champions", 0)
        st.markdown(f"""
        1. **Retention outreach** to the {high_risk_n} highest-value At Risk / Lost customers ({(high_risk_n/total*100 if total else 0):.1f}% of base).
        2. **Loyalty rewards** for {champions_n} Champions to protect the segment driving the most revenue.
        3. **Re-engagement emails** for Need Attention / Price Sensitive segments before they slip further.
        4. Review the **Customer 360** page for any individual account flagged "High Risk" health score.
        """)