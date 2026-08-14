"""
Inventory Analytics - current stock, turnover, low-stock alerts, monthly
usage, and ML-based inventory / demand forecasting (Random Forest).
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_inventory_forecast
from utils.ml_engine import compute_inventory_turnover


@ui.safe_page
def render(data, user):
    is_vendor = user["role"] == "Vendor"
    title = "🏭 My Inventory" if is_vendor else "🏭 Inventory Analytics"
    ui.page_header(title, "HOME &nbsp;›&nbsp; INVENTORY")

    products = data.get("products", pd.DataFrame())
    inventory = data.get("inventory", pd.DataFrame())
    stores = data.get("stores", pd.DataFrame())
    merged = get_merged_orders(data)

    if products.empty:
        st.warning("No product data available." + (" Ask an Admin to add your catalog." if is_vendor else ""))
        return

    # ---------------- KPIs ----------------
    total_stock = products["Stock"].sum() if "Stock" in products.columns else 0
    out_of_stock = int((products["Stock"] == 0).sum()) if "Stock" in products.columns else 0
    low_stock = int(((products["Stock"] > 0) & (products["Stock"] < 20)).sum()) if "Stock" in products.columns else 0

    units_sold = merged["Quantity"].sum() if not merged.empty else 0
    turnover_df = compute_inventory_turnover(merged, products)
    avg_turnover = turnover_df["Turnover"].mean() if not turnover_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Current Stock (units)", f"{int(total_stock):,}", "across catalog", "📦", "#00c2d1")
    with c2:
        ui.kpi_card("Out of Stock", f"{out_of_stock}", "products", "🚫", "#e74c3c")
    with c3:
        ui.kpi_card("Low Stock (<20)", f"{low_stock}", "need reorder soon", "⚠️", "#6c5ce7")
    with c4:
        ui.kpi_card("Avg Inventory Turnover", f"{avg_turnover:.2f}x", "units sold / stock", "🔄", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Stock Overview", "🏬 Store × Brand Breakdown", "🔄 Turnover & Monthly Usage",
        "🚨 Stock Alerts", "🤖 Inventory Forecast",
    ])

    # ---------------- Stock overview ----------------
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            ui.card_open("Stock Level Distribution")
            if "Stock" in products.columns:
                fig = px.histogram(products, x="Stock", nbins=25, color_discrete_sequence=["#5b6ee1"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            ui.card_close()
        with col2:
            ui.card_open("Stock by Category")
            if "Stock" in products.columns and "Category" in products.columns:
                by_cat = products.groupby("Category")["Stock"].sum().reset_index().sort_values("Stock", ascending=False)
                fig = px.bar(by_cat, x="Category", y="Stock", color_discrete_sequence=["#00c2d1"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            ui.card_close()

        if not inventory.empty:
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("Stock by Store (from Inventory dataset)")
            if "StoreID" in inventory.columns:
                by_store = inventory.groupby("StoreID")["StockLevel"].sum().reset_index().sort_values(
                    "StockLevel", ascending=False).head(20)
                fig = px.bar(by_store, x="StoreID", y="StockLevel", color_discrete_sequence=["#6c5ce7"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            ui.card_close()

    # ---------------- Store x Brand breakdown (full inventory view) ----------------
    with tab2:
        if inventory.empty or "StoreID" not in inventory.columns or "ProductID" not in inventory.columns:
            st.info("No store-level inventory dataset available. Upload an `inventory` file "
                    "(StoreID, ProductID, StockLevel, ReorderLevel) to see the full store × brand breakdown.")
        else:
            inv = inventory.merge(
                products[[c for c in ["ProductID", "ProductName", "Brand", "Category"] if c in products.columns]],
                on="ProductID", how="left",
            )
            if not stores.empty and "StoreID" in stores.columns:
                store_cols = [c for c in ["StoreID", "StoreName", "City", "State"] if c in stores.columns]
                inv = inv.merge(stores[store_cols], on="StoreID", how="left")

            brand_options = sorted(inv["Brand"].dropna().unique().tolist()) if "Brand" in inv.columns else []
            store_label_col = "StoreName" if "StoreName" in inv.columns else "StoreID"

            fc1, fc2 = st.columns(2)
            with fc1:
                brand_filter = st.multiselect("Filter by Brand", brand_options,
                                               default=[], key="inv_brand_filter",
                                               placeholder="All brands")
            with fc2:
                store_options = sorted(inv[store_label_col].dropna().unique().tolist())
                store_filter = st.multiselect("Filter by Store", store_options,
                                               default=[], key="inv_store_filter",
                                               placeholder="All stores")

            filtered = inv.copy()
            if brand_filter:
                filtered = filtered[filtered["Brand"].isin(brand_filter)]
            if store_filter:
                filtered = filtered[filtered[store_label_col].isin(store_filter)]

            total_units = int(filtered["StockLevel"].sum()) if "StockLevel" in filtered.columns else 0
            n_stores_shown = filtered["StoreID"].nunique()
            n_brands_shown = filtered["Brand"].nunique() if "Brand" in filtered.columns else 0

            kc1, kc2, kc3 = st.columns(3)
            with kc1:
                ui.kpi_card("Total Units (filtered)", f"{total_units:,}", "in stores", "📦", "#00c2d1")
            with kc2:
                ui.kpi_card("Stores Shown", f"{n_stores_shown}", "locations", "🏬", "#5b6ee1")
            with kc3:
                ui.kpi_card("Brands Shown", f"{n_brands_shown}", "brands", "🏷️", "#6c5ce7")

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            ui.card_open("🗺️ Stock Heatmap — Store × Brand")
            if "Brand" in filtered.columns and not filtered.empty:
                pivot = filtered.pivot_table(index=store_label_col, columns="Brand",
                                              values="StockLevel", aggfunc="sum", fill_value=0)
                # Keep the heatmap readable: top 25 stores by total stock
                pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).head(25).index]
                fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Teal",
                                 labels=dict(color="Units in Stock"))
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=560)
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No brand data to build a heatmap from.")
            ui.card_close()

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                ui.card_open("🏷️ Total Stock by Brand")
                if "Brand" in filtered.columns:
                    by_brand = filtered.groupby("Brand")["StockLevel"].sum().reset_index().sort_values(
                        "StockLevel", ascending=False)
                    fig = px.bar(by_brand, x="Brand", y="StockLevel", color_discrete_sequence=["#00c2d1"])
                    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, width="stretch")
                ui.card_close()
            with col_b:
                ui.card_open("🏬 Total Stock by Store (Top 15)")
                by_store_name = filtered.groupby(store_label_col)["StockLevel"].sum().reset_index().sort_values(
                    "StockLevel", ascending=False).head(15)
                fig = px.bar(by_store_name, x=store_label_col, y="StockLevel", color_discrete_sequence=["#5b6ee1"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-35)
                st.plotly_chart(fig, width="stretch")
                ui.card_close()

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("📋 Full Store × Brand Inventory Table")
            table_cols = [c for c in [store_label_col, "City", "Brand", "ProductName", "Category",
                                       "StockLevel", "ReorderLevel"] if c in filtered.columns]
            st.dataframe(
                filtered[table_cols].sort_values([store_label_col, "Brand"]),
                width="stretch", hide_index=True, height=420,
            )
            csv = filtered[table_cols].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download this breakdown (CSV)", csv,
                                "store_brand_inventory.csv", "text/csv", key="inv_breakdown_dl")
            ui.card_close()

    # ---------------- Turnover & monthly usage ----------------
    with tab3:
        ui.card_open("Inventory Turnover (Units Sold ÷ Current Stock)")
        st.caption("Higher = faster-moving stock. Values near 0 flag slow-moving / dead stock worth a markdown or delisting review.")
        if turnover_df.empty:
            st.info("Not enough sales history to compute turnover yet.")
        else:
            cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "Stock", "UnitsSold", "Turnover"]
                    if c in turnover_df.columns]
            st.dataframe(turnover_df[cols].head(50), width="stretch", hide_index=True, height=320)
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("Monthly Usage (Units Sold Over Time)")
        if not merged.empty and "Date" in merged.columns:
            m = merged.copy()
            m["Month"] = pd.to_datetime(m["Date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
            monthly_usage = m.groupby("Month")["Quantity"].sum().reset_index()
            fig = px.area(monthly_usage, x="Month", y="Quantity", color_discrete_sequence=["#5b6ee1"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No order history available yet.")
        ui.card_close()

    # ---------------- Alerts ----------------
    with tab4:
        ui.card_open("🚨 Out-of-Stock / Low-Stock Alerts")
        if "Stock" in products.columns:
            low = products[products["Stock"] < 20][
                [c for c in ["ProductID", "ProductName", "Category", "Brand", "Stock", "Price"] if c in products.columns]
            ].sort_values("Stock")
            if low.empty:
                st.success("✅ Nothing below the low-stock threshold (20 units) right now.")
            else:
                st.dataframe(low, width="stretch", hide_index=True, height=340)
        ui.card_close()

        if not inventory.empty and "ReorderLevel" in inventory.columns and "StockLevel" in inventory.columns:
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("Below Reorder Level (Store-level Inventory)")
            below = inventory[inventory["StockLevel"] < inventory["ReorderLevel"]]
            if below.empty:
                st.success("✅ No store-level items are below their reorder level.")
            else:
                st.dataframe(below.sort_values("StockLevel"), width="stretch", hide_index=True, height=280)
            ui.card_close()

    # ---------------- ML forecast ----------------
    with tab5:
        ui.card_open("🤖 Inventory Demand Forecast (Random Forest)")
        st.caption("Trains a small Random Forest per top-selling product on monthly demand (time trend, "
                    "month-of-year seasonality, and last month's volume) to project next month's demand and "
                    "recommend a reorder quantity against each product's reorder level.")
        months_ahead = st.slider("Months ahead", 1, 3, 1, key="inv_forecast_months")
        if merged.empty:
            st.info("Not enough order history to forecast demand yet.")
        else:
            forecast = get_cached_inventory_forecast(merged, products, inventory, months_ahead=months_ahead)
            if forecast.empty:
                st.info("Not enough order history to forecast demand yet.")
            else:
                cols = [c for c in ["ProductID", "ProductName", "Category", "Brand", "CurrentStock",
                                     "PredictedDemand", "ReorderLevel", "RecommendedReorderQty", "RiskLevel"]
                        if c in forecast.columns]
                st.dataframe(forecast[cols], width="stretch", hide_index=True, height=380)

                fig = px.bar(forecast.head(15), x="ProductName", y="PredictedDemand", color="RiskLevel",
                              color_discrete_map={"🔴 High": "#e74c3c", "🟠 Medium": "#6c5ce7", "🟢 Low": "#00c2d1"})
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-40)
                st.plotly_chart(fig, width="stretch")
        ui.card_close()
