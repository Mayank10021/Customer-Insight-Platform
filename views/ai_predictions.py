"""AI Prediction Page - Segmentation, Churn, Recommendations, Forecasting, Sentiment."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_churn_model, get_cached_segments, get_cached_sentiment
from utils.ml_engine import (
    segment_customers, build_rfm, train_churn_model, predict_churn,
    build_recommendation_model, recommend_products, forecast_next_month_sales,
    estimate_clv, apply_sentiment_to_feedback,
    content_based_recommendations, get_trending_products,
)


@st.cache_resource(show_spinner=False)
def _get_recommendation_model(data_hash, _merged):
    return build_recommendation_model(_merged)


def render(data, user):
    ui.page_header("AI Predictions", "HOME &nbsp;›&nbsp; AI PREDICTIONS")

    merged = get_merged_orders(data)
    products = data.get("products", pd.DataFrame())
    feedback = data.get("feedback", pd.DataFrame())

    if merged.empty:
        st.warning("No order data available — AI models need order history to train.")
        return

    data_hash = len(merged)  # cheap cache key; changes when dataset size changes

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧩 Customer Segmentation", "⚠️ Churn Prediction", "🎁 Recommendations",
        "📈 Sales Forecast", "💬 Review Sentiment"
    ])

    # ---------------- Segmentation ----------------
    with tab1:
        seg = get_cached_segments(merged)

        ui.card_open("Segment Overview")
        colA, colB = st.columns([1, 2])
        with colA:
            seg_counts = seg["Segment"].value_counts().reset_index()
            seg_counts.columns = ["Segment", "Customers"]
            color_map = {"Gold": "#e6b800", "Silver": "#a6a6a6", "Bronze": "#b5651d"}
            fig_pie = px.pie(seg_counts, names="Segment", values="Customers", hole=0.55,
                              color="Segment", color_discrete_map=color_map)
            fig_pie.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280)
            st.plotly_chart(fig_pie, width="stretch")
        with colB:
            fig_scatter = px.scatter(
                seg, x="Frequency", y="Monetary", color="Segment",
                color_discrete_map=color_map, size="Monetary", hover_data=["CustomerID", "Recency"],
                title=None,
            )
            fig_scatter.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_scatter, width="stretch")
        st.caption("Segments are computed via K-Means clustering on Recency, Frequency, and "
                    "Monetary (RFM) value — Gold customers spend the most, Bronze the least.")
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("Look up a customer's segment & lifetime value")
        st.caption(f"{len(seg):,} customers segmented — type an ID to narrow the list instead of scrolling all of them.")
        seg_query = st.text_input("Search Customer ID", key="seg_cust_search", placeholder="e.g. CUST00123")
        filtered_ids = seg["CustomerID"].astype(str)
        if seg_query.strip():
            filtered_ids = filtered_ids[filtered_ids.str.contains(seg_query.strip(), case=False)]
        options = filtered_ids.head(200).tolist()
        if not options:
            st.info("No matching Customer ID.")
        else:
            selected = st.selectbox(f"Select Customer ID ({len(options)} shown)", options, key="seg_cust")
            if selected:
                row = seg[seg["CustomerID"] == selected].iloc[0]
                clv = estimate_clv(row)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Segment", row["Segment"])
                c2.metric("Recency (days)", int(row["Recency"]))
                c3.metric("Frequency", int(row["Frequency"]))
                c4.metric("Est. Lifetime Value", f"₹{clv:,.0f}")
        ui.card_close()

    # ---------------- Churn ----------------
    with tab2:
        ui.card_open("Predict churn risk for a customer")
        st.caption("This model automatically drops duplicate orders and rows with missing "
                    "Customer ID / Date / Order ID / Amount before training. For deeper cleaning "
                    "of an uploaded file (custom missing-value strategies, full duplicate removal), "
                    "use the **🧹 Data Studio** page.")
        model, feature_cols = get_cached_churn_model(merged)
        if model is None:
            st.info("Not enough order history to train a churn model yet.")
        else:
            rfm = build_rfm(merged)
            churn_query = st.text_input("Search Customer ID", key="churn_cust_search", placeholder="e.g. CUST00123")
            filtered_churn_ids = rfm["CustomerID"].astype(str)
            if churn_query.strip():
                filtered_churn_ids = filtered_churn_ids[filtered_churn_ids.str.contains(churn_query.strip(), case=False)]
            churn_options = filtered_churn_ids.head(200).tolist()
            if not churn_options:
                st.info("No matching Customer ID.")
            else:
                selected2 = st.selectbox(f"Select Customer ID ({len(churn_options)} shown)", churn_options, key="churn_cust")
                if selected2:
                    row = rfm[rfm["CustomerID"] == selected2].iloc[0]
                    risk_value = predict_churn(
                        model,
                        feature_cols,
                        row["Recency"],
                        row["Frequency"],
                        row["Monetary"],
                    )

                    if risk_value is None:
                        st.warning("Unable to calculate churn risk for this customer.")
                    else:
                        risk = float(risk_value)

                        c1, c2, c3 = st.columns(3)

                        c1.metric(
                            "Days Since Last Purchase",
                            int(row["Recency"])
                        )

                        c2.metric(
                            "Total Orders",
                            int(row["Frequency"])
                        )

                        c3.metric(
                            "Churn Risk",
                            f"{risk:.0f}%"
                        )

                        if risk >= 60:
                            st.error(
                                "🔴 High risk — this customer is likely to churn. "
                                "Consider a retention offer."
                            )
                        elif risk >= 30:
                            st.warning(
                                "🟠 Moderate risk — keep an eye on engagement."
                            )
                        else:
                            st.success(
                                "🟢 Low risk — customer looks active and engaged."
                            )
        ui.card_close()

    # ---------------- Recommendations ----------------
    with tab3:
        ui.card_open("🎁 Recommended Products — Collaborative Filtering")
        st.caption("Based on co-purchase patterns: customers who bought this product also bought these.")
        rec_model, item_matrix = _get_recommendation_model(data_hash, merged)
        prod_options = products[["ProductID", "ProductName"]].drop_duplicates()
        prod_options["label"] = prod_options["ProductID"] + " — " + prod_options["ProductName"]
        choice = st.selectbox("Customer bought:", prod_options["label"].tolist(), key="rec_choice")
        chosen_id = choice.split(" — ")[0]

        if rec_model is None:
            st.info("Not enough purchase variety to build collaborative-filtering recommendations yet.")
        else:
            recs = recommend_products(rec_model, item_matrix, chosen_id, products, top_n=5)
            if recs.empty:
                st.info("No strong recommendations found for this product.")
            else:
                st.dataframe(recs, width="stretch", hide_index=True)
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("🧩 Similar Products — Content-Based Filtering")
        st.caption("Works even with no purchase history: scores products by matching Category, Brand, and Price.")
        similar = content_based_recommendations(products, chosen_id, top_n=5)
        if similar.empty:
            st.info("No similar products found.")
        else:
            st.dataframe(similar, width="stretch", hide_index=True)
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("🔥 Trending Products")
        st.caption("Highest unit sales in the most recent 30 days of order history.")
        trending = get_trending_products(merged, products, days=30, top_n=10)
        if trending.empty:
            st.info("Not enough recent order history to compute trending products.")
        else:
            st.dataframe(trending, width="stretch", hide_index=True)
        ui.card_close()

    # ---------------- Forecasting ----------------
    with tab4:
        ui.card_open("Sales forecast (next 3 months) — Linear Regression")
        months_ahead = st.slider("Months to forecast", 1, 6, 3)
        history, forecast = forecast_next_month_sales(merged, months_ahead=months_ahead)
        if forecast.empty:
            st.info("Not enough monthly history to forecast yet.")
        else:
            history["Type"] = "Actual"
            forecast["Type"] = "Forecast"
            combined = pd.concat([history, forecast], ignore_index=True)
            fig = px.line(combined, x="Month", y="TotalAmount", color="Type", markers=True,
                          color_discrete_map={"Actual": "#161029", "Forecast": "#6c5ce7"})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(forecast.rename(columns={"TotalAmount": "Forecasted Sales (₹)"}),
                         width="stretch", hide_index=True)
        ui.card_close()

    # ---------------- Sentiment ----------------
    with tab5:
        ui.card_open("Customer review sentiment analysis")
        if feedback.empty:
            st.info("No feedback data available.")
        else:
            fb = get_cached_sentiment(feedback)
            counts = fb["Sentiment"].value_counts().reset_index()
            counts.columns = ["Sentiment", "Count"]
            color_map = {"Positive": "#00c2d1", "Neutral": "#a7abd1", "Negative": "#e74c3c"}
            colA, colB = st.columns([1, 2])
            with colA:
                fig = px.pie(counts, names="Sentiment", values="Count", hole=0.55,
                             color="Sentiment", color_discrete_map=color_map)
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280)
                st.plotly_chart(fig, width="stretch")
            with colB:
                st.markdown("**Sample analyzed reviews:**")
                st.dataframe(
                    fb[["Review", "Sentiment", "Polarity", "Rating"]].sample(min(8, len(fb)), random_state=1),
                    width="stretch", hide_index=True
                )

            st.markdown("**Try it yourself:**")
            custom_text = st.text_area("Type or paste a review to analyze", placeholder="e.g. The delivery was fast and the product quality was great!")
            if st.button("Analyze Sentiment"):
                from utils.ml_engine import analyze_sentiment
                label, score = analyze_sentiment(custom_text)
                st.info(f"**Sentiment:** {label} &nbsp;|&nbsp; **Polarity score:** {score}")
        ui.card_close()
