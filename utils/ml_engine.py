"""
ML Engine - Customer Segmentation, Churn Prediction, Product Recommendation,
Sales Forecasting, and Review Sentiment Analysis.

All models are trained on-the-fly from the loaded CustomerLens datasets and
cached in Streamlit's session via st.cache_resource by the caller, so the
app stays fast even though nothing is pre-pickled to disk.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Any, cast
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import NearestNeighbors

try:
    from textblob import TextBlob
    _HAS_TEXTBLOB = True
except Exception:
    _HAS_TEXTBLOB = False


# =====================================================================
# 1. CUSTOMER SEGMENTATION (K-Means on RFM features)
# =====================================================================

def build_rfm(merged_orders, reference_date=None):
    """Build Recency, Frequency, Monetary table per customer.
    Defensively drops duplicate order rows and rows missing the columns
    RFM depends on, so upstream data-quality issues don't break the model."""
    if merged_orders.empty:
        return pd.DataFrame(columns=["CustomerID", "Recency", "Frequency", "Monetary"])

    required = ["CustomerID", "Date", "OrderID", "TotalAmount"]
    clean = merged_orders.dropna(subset=[c for c in required if c in merged_orders.columns])
    clean = clean.drop_duplicates(subset=["OrderID"]) if "OrderID" in clean.columns else clean.drop_duplicates()

    if clean.empty:
        return pd.DataFrame(columns=["CustomerID", "Recency", "Frequency", "Monetary"])

    if reference_date is None:
        reference_date = clean["Date"].max()

    grouped = clean.groupby("CustomerID").agg(
        Recency=("Date", lambda x: (reference_date - x.max()).days),
        Frequency=("OrderID", "count"),
        Monetary=("TotalAmount", "sum"),
    ).reset_index()
    return grouped


def segment_customers(merged_orders, n_clusters=3):
    """
    KMeans clustering on RFM -> maps clusters to Gold / Silver / Bronze
    based on average Monetary value (highest spend = Gold).
    Returns a DataFrame: CustomerID, Recency, Frequency, Monetary, Segment
    """
    rfm = build_rfm(merged_orders)
    if rfm.empty or len(rfm) < n_clusters:
        rfm["Segment"] = "Bronze"
        return rfm

    features = rfm[["Recency", "Frequency", "Monetary"]].copy()
    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    rfm["Cluster"] = km.fit_predict(X)

    # Rank clusters by average monetary value (desc) -> Gold, Silver, Bronze
    cluster_rank = rfm.groupby("Cluster")["Monetary"].mean().sort_values(ascending=False)
    labels = ["Gold", "Silver", "Bronze"]
    label_map = {cluster: labels[i] if i < len(labels) else f"Tier{i+1}"
                 for i, cluster in enumerate(cluster_rank.index)}
    rfm["Segment"] = rfm["Cluster"].map(label_map)
    return rfm.drop(columns=["Cluster"])


# =====================================================================
# 1B. FULL RFM SEGMENTATION (11-tier, quantile-score based)
# =====================================================================
# This complements segment_customers() (3-tier Gold/Silver/Bronze used by
# the existing Customers page). It is additive — nothing above is changed —
# and is used by the new Customer 360 / Segmentation modules for the
# richer, industry-standard RFM taxonomy.

RFM_SEGMENT_ORDER = [
    "Champions", "Loyal Customers", "Potential Loyalists", "Promising Customers",
    "New Customers", "Regular Customers", "Need Attention", "Price Sensitive",
    "At Risk", "Lost Customers",
]

RFM_SEGMENT_COLORS = {
    "Champions": "#00c2d1", "Loyal Customers": "#5b6ee1", "Potential Loyalists": "#7bd389",
    "Promising Customers": "#d8fff0", "New Customers": "#8ecae6", "Regular Customers": "#8b8fb3",
    "Need Attention": "#f4a261", "Price Sensitive": "#e9c46a",
    "At Risk": "#6c5ce7", "Lost Customers": "#c1121f",
}


def _score_quintile(series, reverse=False):
    """Score a numeric series 1-5 by quantile. reverse=True means a LOWER raw
    value is BETTER (used for Recency, where fewer days-since-last-order is best)."""
    try:
        ranks = pd.qcut(series.rank(method="first"), 5, labels=False, duplicates="drop") + 1
    except Exception:
        try:
            n_bins = max(series.nunique(), 1)
            ranks = pd.qcut(series.rank(method="first"), n_bins, labels=False, duplicates="drop") + 1
            ranks = ranks.reindex(series.index).fillna(1)
        except Exception:
            return pd.Series(3, index=series.index)
    if reverse:
        ranks = (ranks.max() + 1) - ranks
    return ranks


def build_rfm_scores(merged_orders, reference_date=None):
    """Build RFM table with 1-5 R/F/M scores per customer, plus RFM_Sum."""
    rfm = build_rfm(merged_orders, reference_date=reference_date)
    if rfm.empty:
        return rfm
    rfm = rfm.copy()
    rfm["R_Score"] = _score_quintile(rfm["Recency"], reverse=True).astype(int)
    rfm["F_Score"] = _score_quintile(rfm["Frequency"]).astype(int)
    rfm["M_Score"] = _score_quintile(rfm["Monetary"]).astype(int)
    rfm["RFM_Sum"] = rfm["R_Score"] + rfm["F_Score"] + rfm["M_Score"]
    return rfm


def _classify_rfm_row(r, f, m):
    """Map R/F/M scores (1-5 each) to one of the 11 business segments."""
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 4 and m >= 3:
        return "Loyal Customers"
    if r >= 4 and f <= 2 and m >= 3:
        return "Potential Loyalists"
    if r >= 4 and f <= 2 and m <= 2:
        return "New Customers"
    if r >= 3 and f >= 2 and m >= 2 and (r + f + m) >= 8:
        return "Promising Customers"
    if r <= 2 and f >= 4 and m >= 4:
        return "At Risk"
    if r <= 2 and f <= 2 and m <= 2:
        return "Lost Customers"
    if r <= 2 and (f >= 3 or m >= 3):
        return "Need Attention"
    if m <= 2 and f >= 3:
        return "Price Sensitive"
    if 3 <= r <= 4 and 2 <= f <= 3:
        return "Regular Customers"
    return "Regular Customers"


def segment_customers_rfm11(merged_orders, reference_date=None):
    """
    Full 11-segment RFM classification (Champions, Loyal Customers,
    Potential Loyalists, Promising Customers, New Customers,
    Regular Customers, Need Attention, Price Sensitive, At Risk, Lost
    Customers). Returns CustomerID, Recency, Frequency, Monetary,
    R_Score, F_Score, M_Score, RFM_Sum, Segment.
    """
    rfm = build_rfm_scores(merged_orders, reference_date=reference_date)
    if rfm.empty:
        rfm["Segment"] = pd.Series(dtype=str)
        return rfm
    rfm["Segment"] = rfm.apply(lambda row: _classify_rfm_row(row["R_Score"], row["F_Score"], row["M_Score"]), axis=1)
    return rfm


# =====================================================================
# 2. CHURN PREDICTION (Random Forest)
# =====================================================================

def _churn_label(recency, avg_recency):
    """Heuristic ground truth for training: customers inactive far longer
    than average are considered churned. This lets us train a supervised
    model without needing manually labelled churn history."""
    return 1 if recency > avg_recency * 1.5 else 0


def train_churn_model(merged_orders):
    """Train a RandomForestClassifier to predict churn probability
    from Recency, Frequency, Monetary. Returns (model, feature_cols)."""
    rfm = build_rfm(merged_orders)
    if rfm.empty or len(rfm) < 10:
        return None, None

    avg_recency = rfm["Recency"].mean()
    rfm["Churned"] = rfm["Recency"].apply(lambda r: _churn_label(r, avg_recency))

    X = rfm[["Recency", "Frequency", "Monetary"]]
    y = rfm["Churned"]

    if y.nunique() < 2:
        return None, None

    model = RandomForestClassifier(n_estimators=150, max_depth=6, random_state=42)
    model.fit(X, y)
    return model, ["Recency", "Frequency", "Monetary"]


def predict_churn(model, feature_cols, recency, frequency, monetary):
    if model is None:
        return None
    X = pd.DataFrame([[recency, frequency, monetary]], columns=feature_cols)
    proba = model.predict_proba(X)[0]
    classes = list(model.classes_)
    churn_idx = classes.index(1) if 1 in classes else -1
    churn_prob = proba[churn_idx] if churn_idx >= 0 else 0.0
    return round(float(churn_prob) * 100, 1)


# =====================================================================
# 3. PRODUCT RECOMMENDATION (Nearest Neighbors, item co-purchase)
# =====================================================================

def build_recommendation_model(merged_orders, min_orders=5):
    """
    Builds a customer x product purchase matrix and fits Nearest Neighbors
    over products (item-item similarity based on co-purchase patterns).
    """
    if merged_orders.empty:
        return None, None

    pivot = merged_orders.pivot_table(
        index="CustomerID", columns="ProductID", values="Quantity",
        aggfunc="sum", fill_value=0
    )
    if pivot.shape[1] < 2:
        return None, None

    item_matrix = pivot.T  # rows = products, cols = customers
    n_neighbors = min(6, item_matrix.shape[0])
    model = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=n_neighbors)
    model.fit(item_matrix)
    return model, item_matrix


def recommend_products(model, item_matrix, product_id, products_df, top_n=5):
    """Given a product a customer bought, recommend similar/co-purchased products."""
    if model is None or item_matrix is None or product_id not in item_matrix.index:
        return pd.DataFrame()

    idx = item_matrix.index.get_loc(product_id)
    distances, indices = model.kneighbors(item_matrix.iloc[[idx]], n_neighbors=min(top_n + 1, item_matrix.shape[0]))

    rec_product_ids = [item_matrix.index[i] for i in indices[0] if item_matrix.index[i] != product_id]
    rec_product_ids = rec_product_ids[:top_n]

    if products_df.empty:
        return pd.DataFrame({"ProductID": rec_product_ids})

    return products_df[products_df["ProductID"].isin(rec_product_ids)][
        ["ProductID", "ProductName", "Category", "Brand", "Price", "Rating"]
    ]


# =====================================================================
# 4. SALES FORECASTING (Linear Regression on monthly trend)
# =====================================================================

def forecast_next_month_sales(merged_orders, months_ahead=1):
    """
    Aggregates historical monthly sales and fits a simple Linear Regression
    over the time index to project sales for the next N months.
    Returns (history_df, forecast_df).
    """
    if merged_orders.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = merged_orders.copy()
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = df.groupby("Month")["TotalAmount"].sum().reset_index()
    monthly = monthly.sort_values("Month")

    if len(monthly) < 2:
        return monthly, pd.DataFrame()

    monthly["t"] = np.arange(len(monthly))
    model = LinearRegression()
    model.fit(monthly[["t"]], monthly["TotalAmount"])

    future_t = np.arange(len(monthly), len(monthly) + months_ahead)
    future_df = pd.DataFrame({"t": future_t})
    future_sales = model.predict(future_df)

    last_month = monthly["Month"].max()
    future_months = pd.date_range(last_month + pd.offsets.MonthBegin(1), periods=months_ahead, freq="MS")

    forecast = pd.DataFrame({"Month": future_months, "TotalAmount": future_sales})
    return monthly[["Month", "TotalAmount"]], forecast


# =====================================================================
# 5. CUSTOMER LIFETIME VALUE (simple projection)
# =====================================================================

def estimate_clv(rfm_row, lifespan_months=24):
    """
    Simple CLV estimate: average order value * expected purchase frequency
    per month * projected lifespan in months.
    """
    monetary = rfm_row.get("Monetary", 0)
    frequency = max(rfm_row.get("Frequency", 1), 1)
    avg_order_value = monetary / frequency
    monthly_frequency = frequency / 24  # assume history spans ~24 months
    clv = avg_order_value * monthly_frequency * lifespan_months
    return round(clv, 2)


# =====================================================================
# 5B. VALUE TIERS — Top vs Low customers, and business impact on sales
# =====================================================================

def classify_value_tiers(rfm_df, top_pct=0.2, low_pct=0.2):
    """
    Splits customers into Top / Mid / Low value tiers by total spend
    (Monetary) — the metric that actually answers "who drives our sales".
    Returns (df_with_ValueTier_column, stats_dict) where stats_dict gives
    each tier's customer count, total revenue, % share of total revenue,
    and average spend — this is what powers "Top 20% of customers drive
    X% of revenue" style comparisons across the app.
    """
    df = rfm_df.copy()
    if df.empty:
        df["ValueTier"] = pd.Series(dtype=str)
        return df, {}

    df = df.sort_values("Monetary", ascending=False).reset_index(drop=True)
    n = len(df)
    top_cut = max(int(round(n * top_pct)), 1)
    low_cut = max(int(round(n * low_pct)), 1)

    tiers = np.array(["Mid"] * n, dtype=object)
    tiers[:top_cut] = "Top"
    if low_cut > 0:
        tiers[-low_cut:] = "Low"
    df["ValueTier"] = tiers

    total_revenue = float(df["Monetary"].sum())
    stats = {}
    for tier in ["Top", "Mid", "Low"]:
        sub = df[df["ValueTier"] == tier]
        tier_revenue = float(sub["Monetary"].sum())
        stats[tier] = {
            "count": int(len(sub)),
            "revenue": tier_revenue,
            "revenue_pct": round(tier_revenue / total_revenue * 100, 1) if total_revenue else 0.0,
            "avg_spend": float(sub["Monetary"].mean()) if len(sub) else 0.0,
        }
    return df, stats


def classify_customer_type(row):
    """Business-friendly label combining segment, recency, and frequency."""
    segment = row.get("Segment", "")
    freq = row.get("Frequency", 0) or 0
    recency = row.get("Recency", 999) or 999
    value_tier = row.get("ValueTier", "Mid")

    if value_tier == "Top" and segment in ("Champions", "Loyal Customers"):
        return "VIP"
    if freq >= 8:
        return "Repeat Customer"
    if recency <= 30:
        return "Recent Customer"
    if segment in ("Champions", "Loyal Customers", "Potential Loyalists"):
        return "Loyal Customer"
    return "Regular Customer"


def loyalty_tier(row):
    """Platinum/Gold/Silver/Bronze — driven by spend and order frequency together."""
    freq = row.get("Frequency", 0) or 0
    monetary = row.get("Monetary", 0) or 0
    if freq >= 15 or monetary >= 30000:
        return "Platinum"
    if freq >= 8 or monetary >= 15000:
        return "Gold"
    if freq >= 3 or monetary >= 5000:
        return "Silver"
    return "Bronze"


def is_vip(row):
    return row.get("ValueTier") == "Top" and row.get("Segment") in ("Champions", "Loyal Customers", "Potential Loyalists")


def generate_ai_recommendations(profile):
    """
    Concrete next-best-actions for a customer — only meant to be shown for
    important/high-value customers, per business rule (low-value customers
    don't get premium/upsell recommendations, they'd get re-engagement
    instead, which the Action Center already covers separately).
    """
    recs = []
    segment = profile.get("Segment", "")
    value_tier = profile.get("ValueTier", "Mid")
    churn = profile.get("ChurnRisk") or 0
    health = profile.get("HealthScore", 50)

    if segment == "Champions" or value_tier == "Top":
        recs.append("🎁 Reward this customer — they're among your highest-value accounts.")
        recs.append("⭐ Offer loyalty benefits (priority support, early access, points multiplier).")
    if value_tier == "Top" and churn < 30:
        recs.append("💎 Recommend premium products or a higher-tier subscription/membership.")
    if churn >= 30 and value_tier in ("Top", "Mid"):
        recs.append("🛟 Retain this customer — offer a personalized discount before they disengage further.")
    if profile.get("FavoriteCategories"):
        recs.append(f"🔁 Cross-sell complementary products in {profile['FavoriteCategories'][0]}.")
    if value_tier == "Top" and profile.get("AvgOrderValue", 0) > 0:
        recs.append("📈 Upsell — this customer's basket size suggests room for a bigger-ticket item.")
    if not recs:
        recs.append("👀 Monitor — not currently flagged for a specific action.")
    return recs


# =====================================================================
# 6. SENTIMENT ANALYSIS (TextBlob, with lexicon fallback)
# =====================================================================

# Expanded lexicon so the fast bulk path stays reasonably accurate even
# without TextBlob's NLP parsing.
_POS_WORDS = {"amazing", "great", "excellent", "good", "love", "loved", "superb",
              "satisfied", "happy", "fresh", "fast", "value", "wonderful", "perfect",
              "quality", "recommend", "best", "awesome", "nice", "quick", "friendly"}
_NEG_WORDS = {"bad", "terrible", "poor", "damaged", "late", "disappointed",
              "expired", "spoiled", "worst", "slow", "broken", "rude", "awful",
              "horrible", "waste", "never", "refund", "complaint", "delay", "wrong"}


def analyze_sentiment(text):
    """Returns ('Positive'|'Neutral'|'Negative', polarity_score). Uses TextBlob
    when available — fine for a single ad-hoc query (the "Try it yourself" box),
    but see apply_sentiment_to_feedback() for why bulk processing doesn't use it."""
    if not isinstance(text, str) or not text.strip():
        return "Neutral", 0.0

    if _HAS_TEXTBLOB:
        blob = cast(Any, TextBlob(text))
        polarity = blob.sentiment.polarity
    else:
        words = set(text.lower().split())
        polarity = (len(words & _POS_WORDS) - len(words & _NEG_WORDS)) / max(len(words), 1)

    if polarity > 0.1:
        return "Positive", round(polarity, 2)
    elif polarity < -0.1:
        return "Negative", round(polarity, 2)
    return "Neutral", round(polarity, 2)


def _fast_lexicon_sentiment(text):
    """Lexicon-only scoring — no TextBlob object creation/parsing per row.
    Used for bulk dataframe processing where TextBlob's per-call NLP cost
    (tokenizing + POS-tagging every review) adds up to minutes at real
    dataset sizes, even though it's fine for a single one-off string."""
    if not isinstance(text, str) or not text.strip():
        return "Neutral", 0.0
    words = set(text.lower().split())
    polarity = (len(words & _POS_WORDS) - len(words & _NEG_WORDS)) / max(len(words), 1)
    if polarity > 0.1:
        return "Positive", round(polarity, 2)
    elif polarity < -0.1:
        return "Negative", round(polarity, 2)
    return "Neutral", round(polarity, 2)


def apply_sentiment_to_feedback(feedback_df, fast=True):
    """
    Scores every review's sentiment. fast=True (default) uses the lightweight
    lexicon method instead of TextBlob — TextBlob is noticeably higher
    quality per review, but its per-call NLP overhead makes it genuinely
    slow across tens of thousands of rows (this was the actual cause of
    AI Predictions / Insights feeling stuck). Pass fast=False if you
    specifically want TextBlob-quality scoring and can accept the wait.
    """
    if feedback_df.empty or "Review" not in feedback_df.columns:
        return feedback_df
    scorer = _fast_lexicon_sentiment if fast else analyze_sentiment
    feedback_df = feedback_df.copy()

    # Reviews are often highly repetitive (a handful of template strings
    # repeated across thousands of rows), so score each unique review once
    # and map the result back — faster, and also sidesteps a pandas issue
    # where .apply() returning tuples on a categorical Series can crash.
    reviews_as_str = feedback_df["Review"].astype(str)
    unique_reviews = reviews_as_str.unique()
    score_map = {r: scorer(r) for r in unique_reviews}
    mapped = reviews_as_str.map(score_map)

    feedback_df["Sentiment"] = mapped.map(lambda x: x[0])
    feedback_df["Polarity"] = mapped.map(lambda x: x[1])
    return feedback_df


# =====================================================================
# 7. CUSTOMER HEALTH SCORE (0-100, used by Customer 360 / Action Center)
# =====================================================================

def compute_health_score(recency_days, frequency, monetary, avg_rating=None,
                          return_rate=0.0, max_recency=180, ref_frequency=20,
                          ref_monetary=50000):
    """
    Blend of Recency (30%), Frequency (25%), Monetary (25%), Satisfaction (10%),
    and Return-rate penalty (10%) into a single 0-100 health score.
    All sub-scores are normalized 0-1 before weighting so the result is
    stable across datasets of very different scale.
    """
    recency_score = max(0.0, 1 - (min(recency_days, max_recency) / max_recency))
    frequency_score = min(frequency / max(ref_frequency, 1), 1.0)
    monetary_score = min(monetary / max(ref_monetary, 1), 1.0)
    satisfaction_score = (avg_rating / 5.0) if avg_rating is not None and not pd.isna(avg_rating) else 0.6
    return_penalty = min(return_rate, 1.0)

    score = (
        recency_score * 30 +
        frequency_score * 25 +
        monetary_score * 25 +
        satisfaction_score * 10 +
        (1 - return_penalty) * 10
    )
    return round(max(0, min(100, score)), 1)


def health_score_band(score):
    """Returns (label, hex_color) for a health score."""
    if score >= 70:
        return "Healthy", "#00c2d1"
    if score >= 40:
        return "Needs Attention", "#f4a261"
    return "High Risk", "#ff4d4d"


def generate_customer_ai_summary(profile):
    """
    Rule-based 'AI-style' executive summary paragraph for a single customer,
    built entirely from the customer's own computed stats (no external LLM
    call needed — keeps Customer 360 fast and dependency-free).
    `profile` is a dict as produced by data_handler.get_customer_profile().
    """
    name = profile.get("Name", "This customer")
    segment = profile.get("Segment", "Regular Customers")
    health = profile.get("HealthScore", 50)
    health_label, _ = health_score_band(health)
    churn = profile.get("ChurnRisk")
    days_since = profile.get("DaysSinceLastPurchase")
    total_orders = profile.get("TotalOrders", 0)
    clv = profile.get("CLV", 0)
    fav_category = profile.get("FavoriteCategory", "N/A")
    sentiment = profile.get("SentimentSummary", "neutral")

    lines = []
    lines.append(
        f"**{name}** is currently classified as **{segment}** with a health score of "
        f"**{health}/100 ({health_label})**."
    )
    if total_orders:
        lines.append(
            f"They have placed **{total_orders} order(s)** worth an estimated lifetime value of "
            f"**₹{clv:,.0f}**, most frequently purchasing from the **{fav_category}** category."
        )
    if days_since is not None:
        if days_since <= 30:
            lines.append(f"Last purchase was **{int(days_since)} days ago** — an actively engaged customer.")
        elif days_since <= 90:
            lines.append(f"Last purchase was **{int(days_since)} days ago** — engagement is starting to cool.")
        else:
            lines.append(f"Last purchase was **{int(days_since)} days ago** — a strong signal of disengagement.")
    if churn is not None:
        if churn >= 60:
            lines.append(f"Predicted churn probability is **{churn}%**, recommending an immediate retention offer.")
        elif churn >= 30:
            lines.append(f"Predicted churn probability is **{churn}%** — worth a proactive check-in.")
        else:
            lines.append(f"Predicted churn probability is low ({churn}%), indicating a stable relationship.")
    lines.append(f"Overall feedback sentiment trends **{sentiment}**.")

    return " ".join(lines)


def with_profit(merged_orders):
    """Adds a Profit column ((Price - Cost) * Quantity) to a merged-orders frame, if possible."""
    if merged_orders.empty or "Price" not in merged_orders.columns or "Cost" not in merged_orders.columns:
        return merged_orders
    df = merged_orders.copy()
    df["Profit"] = (df["Price"] - df["Cost"]) * df["Quantity"]
    return df


def compare_products_in_category(merged_orders, products_df, category, feedback_df=None):
    """
    'Similar Product Mapping': for one Category (e.g. 'Dairy'), returns every
    product in it side by side — Price, Units Sold, Revenue, Profit, Avg
    Rating — so the same kind of product across different brands (Samsung
    Galaxy vs iPhone-adjacent lines, etc.) can be compared directly.
    """
    if products_df.empty or "Category" not in products_df.columns:
        return pd.DataFrame()
    cat_products = products_df[products_df["Category"] == category].copy()
    if cat_products.empty:
        return cat_products

    if not merged_orders.empty:
        sales = merged_orders[merged_orders["ProductID"].isin(cat_products["ProductID"])].copy()
        if "Cost" in sales.columns and "Price" in sales.columns:
            sales["_line_profit"] = (sales["Price"] - sales["Cost"]) * sales["Quantity"]
        else:
            sales["_line_profit"] = 0
        agg = sales.groupby("ProductID").agg(
            UnitsSold=("Quantity", "sum"), Revenue=("TotalAmount", "sum"), Profit=("_line_profit", "sum"),
        ).reset_index()
        cat_products = cat_products.merge(agg, on="ProductID", how="left")
    for col in ["UnitsSold", "Revenue", "Profit"]:
        if col not in cat_products.columns:
            cat_products[col] = 0
        cat_products[col] = cat_products[col].fillna(0)

    cols = [c for c in ["ProductID", "ProductName", "Brand", "Price", "UnitsSold", "Revenue", "Profit", "Rating"]
            if c in cat_products.columns]
    return cat_products[cols].sort_values("Revenue", ascending=False).reset_index(drop=True)


def product_performance_tiers(merged_orders, products_df):
    """
    Splits every product into Top / Medium / Least performance tiers based
    on units sold (top ~20% / middle ~60% / bottom ~20%), the basis for the
    Top-Selling, Medium-Selling, and Least-Selling / Dead-Stock dashboards.
    """
    if merged_orders.empty or products_df.empty:
        return pd.DataFrame()

    sold = merged_orders.groupby(["ProductID", "ProductName"])["Quantity"].sum().rename("UnitsSold").reset_index()
    revenue = merged_orders.groupby("ProductID")["TotalAmount"].sum().rename("Revenue")
    sold = sold.merge(revenue, on="ProductID", how="left")

    cols = [c for c in ["ProductID", "Category", "Brand", "Stock", "Rating", "Price"] if c in products_df.columns]
    sold = sold.merge(products_df[cols], on="ProductID", how="left")

    # Any catalog product with zero sales is automatically "Least" (dead stock candidate)
    all_products = products_df[cols + [c for c in ["ProductName"] if c in products_df.columns]].copy()
    drop_cols = [c for c in cols + ["ProductName"] if c in sold.columns and c != "ProductID"]
    sold_full = all_products.merge(sold.drop(columns=drop_cols, errors="ignore"),
                                    on="ProductID", how="left")
    sold_full["UnitsSold"] = sold_full["UnitsSold"].fillna(0)
    sold_full["Revenue"] = sold_full["Revenue"].fillna(0)

    q80 = sold_full["UnitsSold"].quantile(0.8)
    q20 = sold_full["UnitsSold"].quantile(0.2)

    def _tier(units):
        if units >= q80 and units > 0:
            return "Top"
        elif units <= q20:
            return "Least"
        return "Medium"

    sold_full["Tier"] = sold_full["UnitsSold"].apply(_tier)
    sold_full = sold_full.sort_values("UnitsSold", ascending=False).reset_index(drop=True)
    return sold_full


def forecast_single_product_demand(merged_orders, product_id, months_ahead=1):
    """
    Same Random Forest approach as forecast_inventory_demand, but for one
    product only — used by Product 360° so looking at a single item doesn't
    require training a model for the whole top-N catalog.
    Returns {"predicted_demand": float, "history": DataFrame(Month, Quantity)} or None.
    """
    if merged_orders.empty or "Date" not in merged_orders.columns:
        return None
    df = merged_orders[merged_orders["ProductID"] == product_id].copy()
    if df.empty:
        return None
    df["Month"] = pd.to_datetime(df["Date"], errors="coerce").dt.to_period("M")
    df = df.dropna(subset=["Month"])
    monthly = df.groupby("Month")["Quantity"].sum().reset_index().sort_values("Month")
    if monthly.empty:
        return None

    if len(monthly) < 3:
        predicted = round(monthly["Quantity"].tail(3).mean(), 1)
    else:
        g = monthly.copy()
        g["t"] = np.arange(len(g))
        g["month_of_year"] = g["Month"].dt.month.astype(int)
        g["lag1"] = g["Quantity"].shift(1).fillna(g["Quantity"].iloc[0])
        X = g[["t", "month_of_year", "lag1"]]
        y = g["Quantity"]
        model = RandomForestRegressor(n_estimators=80, max_depth=4, random_state=42)
        model.fit(X, y)
        next_t = len(g) + months_ahead - 1
        next_month = (g["Month"].iloc[-1] + months_ahead).month
        next_lag = g["Quantity"].iloc[-1]
        pred = model.predict(pd.DataFrame({"t": [next_t], "month_of_year": [next_month], "lag1": [next_lag]}))
        predicted = max(round(float(pred[0]), 1), 0.0)

    monthly["Month"] = monthly["Month"].dt.to_timestamp()
    return {"predicted_demand": predicted, "history": monthly}


def get_top_customers_for_product(merged_orders, product_id, top_n=10):
    """Customers who've spent the most on one specific product — for Product 360°."""
    if merged_orders.empty:
        return pd.DataFrame()
    df = merged_orders[merged_orders["ProductID"] == product_id]
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in ["CustomerID", "Name", "City", "State"] if c in df.columns]
    agg = df.groupby(cols if cols else ["CustomerID"]).agg(
        TotalSpent=("TotalAmount", "sum"), TimesPurchased=("OrderID", "nunique"),
    ).reset_index().sort_values("TotalSpent", ascending=False).head(top_n)
    return agg


# =====================================================================
# 8. INVENTORY FORECASTING (Random Forest on monthly per-product demand)
# =====================================================================

def forecast_inventory_demand(merged_orders, products_df, inventory_df=None,
                               months_ahead=1, top_n_products=25):
    """
    Trains a small Random Forest regressor per top-selling product on
    monthly demand (features: month-of-year, a linear time index, and
    last month's quantity as a lag feature) and projects demand for the
    next `months_ahead` month(s). Falls back to a simple recent-average
    for products with too little history for a model to be meaningful.

    Returns a DataFrame: ProductID, ProductName, Category, Brand,
    CurrentStock, PredictedDemand, ReorderLevel, RecommendedReorderQty,
    RiskLevel (Low/Medium/High based on predicted stockout).
    """
    if merged_orders is None or merged_orders.empty or "Date" not in merged_orders.columns:
        return pd.DataFrame()

    df = merged_orders.copy()
    df["Month"] = pd.to_datetime(df["Date"], errors="coerce").dt.to_period("M")
    df = df.dropna(subset=["Month"])

    monthly = df.groupby(["ProductID", "Month"])["Quantity"].sum().reset_index()
    monthly = monthly.sort_values(["ProductID", "Month"])

    # Focus compute on the top-selling products by total historical volume —
    # training a per-product model for every single SKU isn't necessary to
    # give a useful, fast reorder recommendation.
    top_products = (
        monthly.groupby("ProductID")["Quantity"].sum().sort_values(ascending=False).head(top_n_products).index
    )

    results = []
    for pid in top_products:
        g = monthly[monthly["ProductID"] == pid].reset_index(drop=True)
        if len(g) < 3:
            # Not enough history for a model — use the recent average as the forecast.
            predicted = round(g["Quantity"].tail(3).mean(), 1) if len(g) else 0.0
        else:
            g["t"] = np.arange(len(g))
            g["month_of_year"] = g["Month"].dt.month.astype(int)
            g["lag1"] = g["Quantity"].shift(1).fillna(g["Quantity"].iloc[0])
            X = g[["t", "month_of_year", "lag1"]]
            y = g["Quantity"]
            model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
            model.fit(X, y)
            next_t = len(g) + months_ahead - 1
            next_month = (g["Month"].iloc[-1] + months_ahead).month
            next_lag = g["Quantity"].iloc[-1]
            pred = model.predict(pd.DataFrame({"t": [next_t], "month_of_year": [next_month], "lag1": [next_lag]}))
            predicted = max(round(float(pred[0]), 1), 0.0)
        results.append({"ProductID": pid, "PredictedDemand": predicted})

    forecast_df = pd.DataFrame(results)
    if forecast_df.empty:
        return forecast_df

    if not products_df.empty:
        cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "Stock"] if c in products_df.columns]
        forecast_df = forecast_df.merge(products_df[cols], on="ProductID", how="left")
        forecast_df = forecast_df.rename(columns={"Stock": "CurrentStock"})

    reorder_map = {}
    if inventory_df is not None and not inventory_df.empty and "ProductID" in inventory_df.columns:
        reorder_map = inventory_df.groupby("ProductID")["ReorderLevel"].mean().to_dict()
    forecast_df["ReorderLevel"] = forecast_df["ProductID"].map(reorder_map)
    forecast_df["ReorderLevel"] = forecast_df["ReorderLevel"].fillna(forecast_df["PredictedDemand"] * 0.5).round(0)

    if "CurrentStock" not in forecast_df.columns:
        forecast_df["CurrentStock"] = 0

    forecast_df["RecommendedReorderQty"] = (
        (forecast_df["PredictedDemand"] + forecast_df["ReorderLevel"] - forecast_df["CurrentStock"])
        .clip(lower=0).round(0)
    )

    def _risk(row):
        if row["CurrentStock"] <= row["PredictedDemand"] * 0.5:
            return "🔴 High"
        elif row["CurrentStock"] <= row["PredictedDemand"]:
            return "🟠 Medium"
        return "🟢 Low"

    forecast_df["RiskLevel"] = forecast_df.apply(_risk, axis=1)
    forecast_df = forecast_df.sort_values("PredictedDemand", ascending=False).reset_index(drop=True)
    return forecast_df


def compute_inventory_turnover(merged_orders, products_df):
    """
    Inventory turnover = Units Sold / Average Stock on hand, per product —
    the standard retail KPI for how quickly stock is cycling. Higher is
    better (fast-moving); values near 0 flag slow-moving / dead stock.
    """
    if merged_orders.empty or products_df.empty:
        return pd.DataFrame()

    sold = merged_orders.groupby("ProductID")["Quantity"].sum().rename("UnitsSold")
    cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "Stock"] if c in products_df.columns]
    out = products_df[cols].merge(sold, on="ProductID", how="left")
    out["UnitsSold"] = out["UnitsSold"].fillna(0)
    out["Turnover"] = (out["UnitsSold"] / out["Stock"].replace(0, np.nan)).round(2).fillna(0)
    out = out.sort_values("Turnover", ascending=False).reset_index(drop=True)
    return out


# =====================================================================
# 9. RECOMMENDATION SYSTEM — Content-Based Filtering + Trending Products
# =====================================================================

def content_based_recommendations(products_df, product_id, top_n=5):
    """
    Cold-start-friendly recommendations that don't need any purchase
    history: scores every other product by similarity to `product_id` on
    Category (exact match), Brand (exact match), and normalized Price
    closeness, then returns the top N. This complements the existing
    co-purchase (collaborative filtering) recommendations in
    `recommend_products`, which need order history to work.
    """
    if products_df.empty or product_id not in products_df["ProductID"].values:
        return pd.DataFrame()

    base = products_df[products_df["ProductID"] == product_id].iloc[0]
    candidates = products_df[products_df["ProductID"] != product_id].copy()
    if candidates.empty:
        return candidates

    price_range = max(products_df["Price"].max() - products_df["Price"].min(), 1e-9)
    candidates["_price_sim"] = 1 - (abs(candidates["Price"] - base["Price"]) / price_range)
    candidates["_cat_sim"] = (candidates["Category"] == base["Category"]).astype(float)
    candidates["_brand_sim"] = (candidates["Brand"] == base["Brand"]).astype(float)
    candidates["SimilarityScore"] = (
        candidates["_cat_sim"] * 0.5 + candidates["_brand_sim"] * 0.3 + candidates["_price_sim"] * 0.2
    ).round(3)

    top = candidates.sort_values("SimilarityScore", ascending=False).head(top_n)
    cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "Price", "Rating", "SimilarityScore"]
            if c in top.columns]
    return top[cols]


def get_trending_products(merged_orders, products_df, days=30, top_n=10):
    """
    'Trending' = highest unit sales in the most recent `days`-day window of
    order history — a simple, robust recency-weighted popularity signal.
    """
    if merged_orders.empty or "Date" not in merged_orders.columns:
        return pd.DataFrame()

    df = merged_orders.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    cutoff = df["Date"].max() - pd.Timedelta(days=days)
    recent = df[df["Date"] >= cutoff]
    if recent.empty:
        recent = df  # fall back to all-time if the dataset doesn't span `days`

    trending = recent.groupby(["ProductID", "ProductName"])["Quantity"].sum().reset_index()
    trending = trending.sort_values("Quantity", ascending=False).head(top_n)
    trending = trending.rename(columns={"Quantity": "UnitsSold (recent)"})

    if not products_df.empty:
        cols = [c for c in ["ProductID", "Category", "Brand", "Price", "Rating"] if c in products_df.columns]
        trending = trending.merge(products_df[cols], on="ProductID", how="left")

    return trending
