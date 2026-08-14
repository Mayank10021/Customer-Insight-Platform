"""
Forecast Dashboard - one place for every predictive model in the platform:
Sales Forecast (Linear Regression), Inventory / Demand Forecast (Random
Forest), and Category-level Demand Prediction.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_inventory_forecast
from utils.ml_engine import forecast_next_month_sales


@ui.safe_page
def render(data, user):
    ui.page_header("📈 Forecast Dashboard", "HOME &nbsp;›&nbsp; FORECAST")

    merged = get_merged_orders(data)
    products = data.get("products", pd.DataFrame())
    inventory = data.get("inventory", pd.DataFrame())

    if merged.empty:
        st.warning("No order history available — forecasting needs sales history to train on.")
        return

    tab1, tab2, tab3 = st.tabs(["💰 Sales Forecast", "📦 Inventory / Demand Forecast", "🗂️ Demand by Category"])

    # ---------------- Sales forecast ----------------
    with tab1:
        ui.card_open("Revenue Forecast (Linear Regression on monthly trend)")
        months_ahead = st.slider("Months to forecast", 1, 6, 3, key="fc_sales_months")
        history, forecast = forecast_next_month_sales(merged, months_ahead=months_ahead)
        if forecast.empty:
            st.info("Not enough monthly history to forecast yet.")
        else:
            history = history.copy()
            forecast = forecast.copy()
            history["Type"] = "Actual"
            forecast["Type"] = "Forecast"
            combined = pd.concat([history, forecast], ignore_index=True)
            fig = px.line(combined, x="Month", y="TotalAmount", color="Type", markers=True,
                          color_discrete_map={"Actual": "#161029", "Forecast": "#6c5ce7"})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(forecast.rename(columns={"TotalAmount": "Forecasted Revenue (₹)"}),
                         width="stretch", hide_index=True)
        ui.card_close()

    # ---------------- Inventory / demand forecast ----------------
    with tab2:
        ui.card_open("Per-Product Demand Forecast (Random Forest)")
        months_ahead2 = st.slider("Months ahead", 1, 3, 1, key="fc_inv_months")
        inv_forecast = get_cached_inventory_forecast(merged, products, inventory, months_ahead=months_ahead2)
        if inv_forecast.empty:
            st.info("Not enough order history to forecast product demand yet.")
        else:
            cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "CurrentStock",
                                 "PredictedDemand", "ReorderLevel", "RecommendedReorderQty", "RiskLevel"]
                    if c in inv_forecast.columns]
            st.dataframe(inv_forecast[cols], width="stretch", hide_index=True, height=380)
            high_risk = inv_forecast[inv_forecast["RiskLevel"] == "🔴 High"]
            if not high_risk.empty:
                st.error(f"🔴 {len(high_risk)} product(s) are projected to run out before next reorder — see Inventory page to act.")
        ui.card_close()

    # ---------------- Category demand ----------------
    with tab3:
        ui.card_open("Demand Prediction by Category")
        st.caption("Aggregates the per-product Random Forest forecast up to Category level, so you can see "
                    "which categories will need the most restocking next period.")
        inv_forecast2 = get_cached_inventory_forecast(merged, products, inventory, months_ahead=1)
        if inv_forecast2.empty or "Category" not in inv_forecast2.columns:
            st.info("Not enough order history to forecast category demand yet.")
        else:
            by_cat = inv_forecast2.groupby("Category").agg(
                PredictedDemand=("PredictedDemand", "sum"),
                CurrentStock=("CurrentStock", "sum"),
            ).reset_index().sort_values("PredictedDemand", ascending=False)
            fig = px.bar(by_cat, x="Category", y=["PredictedDemand", "CurrentStock"], barmode="group",
                          color_discrete_sequence=["#6c5ce7", "#5b6ee1"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=350,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(by_cat, width="stretch", hide_index=True)
        ui.card_close()
