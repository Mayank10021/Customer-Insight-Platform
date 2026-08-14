"""
Vendor 360° (a.k.a. Company 360°) — a full single-vendor profile:
Revenue, Profit, Orders, Inventory, Customer Count, Growth, Ratings,
Best/Weak Products, Forecast, and a composite Vendor Score.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_vendor_performance, get_cached_inventory_forecast, load_platform_data
from utils import vendor_store


@ui.safe_page
def render(data, user):
    is_vendor = user["role"] == "Vendor"
    ui.page_header("🏢 Vendor 360°", "HOME &nbsp;›&nbsp; VENDOR 360")

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)
    feedback = data.get("feedback", pd.DataFrame())
    inventory = data.get("inventory", pd.DataFrame())

    if products.empty or "Brand" not in products.columns:
        st.warning("No product/brand data available.")
        return

    brands = sorted(products["Brand"].dropna().unique().tolist())
    if not brands:
        st.info("No brands found in the current dataset.")
        return

    if is_vendor:
        brand = user.get("vendor_brand") or brands[0]
        if brand not in brands:
            brand = brands[0]
        st.caption(f"Showing your own vendor profile: **{brand}**")
    else:
        brand = st.selectbox("Select Vendor / Company", brands, key="v360_brand")

    perf = get_cached_vendor_performance(merged, feedback) if not merged.empty else pd.DataFrame()
    row = perf[perf["Brand"] == brand].iloc[0] if not perf.empty and brand in perf["Brand"].values else None

    vinfo = vendor_store.get_vendor(brand)

    # ---------------- Header KPIs ----------------
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        ui.kpi_card("Revenue", f"₹{row['Revenue']:,.0f}" if row is not None else "₹0", "all time", "💰", "#00c2d1")
    with c2:
        ui.kpi_card("Profit", f"₹{row['Profit']:,.0f}" if row is not None else "₹0", "all time", "📈", "#5b6ee1")
    with c3:
        ui.kpi_card("Orders", f"{int(row['Orders']):,}" if row is not None else "0", "fulfilled", "🧾", "#6c5ce7")
    with c4:
        ui.kpi_card("Growth (MoM)", f"{row['GrowthPct']:+.1f}%" if row is not None else "0%", "vs prior month", "📊", "#161029")
    with c5:
        score = row["VendorScore"] if row is not None else 0
        grade = row["ScoreGrade"] if row is not None else "—"
        ui.kpi_card("Vendor Score", f"{score:.0f}/100", grade, "🏅", "#c1121f")

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    brand_products = products[products["Brand"] == brand]
    brand_merged = merged[merged["Brand"] == brand] if not merged.empty and "Brand" in merged.columns else pd.DataFrame()
    customer_count = brand_merged["CustomerID"].nunique() if not brand_merged.empty and "CustomerID" in brand_merged.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ui.kpi_card("Products", f"{len(brand_products)}", "in catalog", "📦", "#00c2d1")
    with col2:
        ui.kpi_card("Customers", f"{customer_count:,}", "unique buyers", "👥", "#5b6ee1")
    with col3:
        low_stock = int(((brand_products["Stock"] > 0) & (brand_products["Stock"] < 20)).sum()) if "Stock" in brand_products.columns else 0
        ui.kpi_card("Low Stock Items", f"{low_stock}", "need reorder", "⚠️", "#6c5ce7")
    with col4:
        avg_rating = brand_products["Rating"].mean() if "Rating" in brand_products.columns and not brand_products.empty else 0
        ui.kpi_card("Avg Rating", f"{avg_rating:.2f} ★", "across products", "⭐", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    tab_names = ["📈 Trends", "🏆 Best / Weak Products", "🏭 Inventory", "🔮 Forecast"]
    if is_vendor:
        tab_names.append("⚔️ Compare vs Other Vendors")
    tabs = st.tabs(tab_names)
    tab1, tab2, tab3, tab4 = tabs[0], tabs[1], tabs[2], tabs[3]

    with tab1:
        colt1, colt2 = st.columns(2)
        with colt1:
            ui.card_open("Monthly Revenue Trend")
            if not brand_merged.empty and "Date" in brand_merged.columns:
                m = brand_merged.copy()
                m["Month"] = pd.to_datetime(m["Date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
                trend = m.groupby("Month")["TotalAmount"].sum().reset_index()
                fig = px.line(trend, x="Month", y="TotalAmount", markers=True)
                fig.update_traces(line_color="#00c2d1")
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No sales history yet.")
            ui.card_close()
        with colt2:
            ui.card_open("Revenue by Category")
            if not brand_merged.empty and "Category" in brand_merged.columns:
                by_cat = brand_merged.groupby("Category")["TotalAmount"].sum().reset_index()
                fig = px.pie(by_cat, names="Category", values="TotalAmount", hole=0.45)
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No category data yet.")
            ui.card_close()

    with tab2:
        colb1, colb2 = st.columns(2)
        with colb1:
            ui.card_open("🏆 Best Products (by Revenue)")
            if not brand_merged.empty:
                best = brand_merged.groupby(["ProductID", "ProductName"])["TotalAmount"].sum().reset_index()
                best = best.sort_values("TotalAmount", ascending=False).head(8)
                fig = px.bar(best, x="TotalAmount", y="ProductName", orientation="h", color_discrete_sequence=["#00c2d1"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                   yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No sales yet.")
            ui.card_close()
        with colb2:
            ui.card_open("🐌 Weakest Products (by Revenue)")
            if not brand_merged.empty:
                weak_ids = set(brand_merged["ProductID"])
                sales = brand_merged.groupby(["ProductID", "ProductName"])["TotalAmount"].sum().reset_index()
                all_ids = set(brand_products["ProductID"]) if "ProductID" in brand_products.columns else set()
                zero_ids = all_ids - weak_ids
                zero_rows = brand_products[brand_products["ProductID"].isin(zero_ids)][["ProductID", "ProductName"]].copy()
                zero_rows["TotalAmount"] = 0
                weakest = pd.concat([sales, zero_rows], ignore_index=True).sort_values("TotalAmount").head(8)
                fig = px.bar(weakest, x="TotalAmount", y="ProductName", orientation="h", color_discrete_sequence=["#e74c3c"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                   yaxis={"categoryorder": "total descending"})
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No sales yet.")
            ui.card_close()

    with tab3:
        ui.card_open("Inventory Snapshot")
        show_cols = [c for c in ["ProductID", "ProductName", "Category", "Stock", "Price", "Rating"]
                     if c in brand_products.columns]
        st.dataframe(brand_products[show_cols].sort_values("Stock"), width="stretch", hide_index=True, height=340)
        ui.card_close()

    with tab4:
        ui.card_open("Demand Forecast (this vendor's products)")
        if merged.empty:
            st.info("No order history to forecast from yet.")
        else:
            fc = get_cached_inventory_forecast(merged, products, inventory, months_ahead=1)
            fc_brand = fc[fc["Brand"] == brand] if not fc.empty and "Brand" in fc.columns else pd.DataFrame()
            if fc_brand.empty:
                st.info("Not enough sales volume for this brand to forecast individually yet.")
            else:
                cols = [c for c in ["ProductName", "CurrentStock", "PredictedDemand", "RecommendedReorderQty", "RiskLevel"]
                        if c in fc_brand.columns]
                st.dataframe(fc_brand[cols], width="stretch", hide_index=True, height=300)
        ui.card_close()

    if is_vendor:
        with tabs[4]:
            ui.card_open("⚔️ How You Compare to Other Vendors")
            st.caption("This is a **separate benchmark area** — it uses the shared platform-wide sales ledger "
                        "(aggregate numbers only) to show where you rank. It never shows you another vendor's "
                        "raw products, orders, or customers — only the same kind of summary numbers Admin sees "
                        "in Vendor Management.")
            shared = load_platform_data()
            if not shared:
                st.info("No shared platform ledger is available yet — ask an Admin to upload one so cross-vendor "
                         "benchmarking can work. (Your own dashboard above is unaffected either way.)")
            else:
                shared_products = shared.get("products", pd.DataFrame())
                if shared_products.empty or "Brand" not in shared_products.columns:
                    st.info("Shared platform data doesn't have brand information to benchmark against yet.")
                else:
                    shared_merged = get_merged_orders(shared)
                    shared_feedback = shared.get("feedback", pd.DataFrame())
                    bench = get_cached_vendor_performance(shared_merged, shared_feedback) if not shared_merged.empty else pd.DataFrame()
                    if bench.empty or brand not in bench["Brand"].values:
                        st.info("Not enough shared sales history to benchmark yet.")
                    else:
                        my_rank = int(bench[bench["Brand"] == brand]["Rank"].iloc[0])
                        total_vendors = len(bench)
                        my_score = float(bench[bench["Brand"] == brand]["VendorScore"].iloc[0])
                        industry_avg_score = float(bench["VendorScore"].mean())

                        colx1, colx2, colx3 = st.columns(3)
                        with colx1:
                            ui.kpi_card("Your Rank", f"#{my_rank} of {total_vendors}", "by revenue", "🏅", "#c1121f")
                        with colx2:
                            ui.kpi_card("Your Vendor Score", f"{my_score:.0f}/100", "vs 0-100 scale", "📊", "#5b6ee1")
                        with colx3:
                            delta = my_score - industry_avg_score
                            ui.kpi_card("vs Industry Average", f"{delta:+.1f} pts", f"avg is {industry_avg_score:.0f}", "📈", "#00c2d1")

                        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                        bench_sorted = bench.sort_values("VendorScore", ascending=False)
                        bench_sorted["_highlight"] = bench_sorted["Brand"].apply(lambda b: "You" if b == brand else "Other Vendors")
                        fig = px.bar(bench_sorted, x="Brand", y="VendorScore", color="_highlight",
                                      color_discrete_map={"You": "#c1121f", "Other Vendors": "#c9cbe0"})
                        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                           legend_title_text="", xaxis_title="", yaxis_title="Vendor Score")
                        st.plotly_chart(fig, width="stretch")

                        st.dataframe(
                            bench_sorted[["Rank", "Brand", "Revenue", "GrowthPct", "AvgRating", "VendorScore", "ScoreGrade"]]
                            .rename(columns={"GrowthPct": "Growth %", "AvgRating": "Avg Rating"}),
                            width="stretch", hide_index=True, height=300,
                        )
            ui.card_close()

    if vinfo:
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("👤 Vendor Business Profile")
        colp1, colp2 = st.columns(2)
        with colp1:
            st.markdown(f"**Business Name:** {vinfo.get('business_name') or '—'}")
            st.markdown(f"**GST Number:** {vinfo.get('gst_number') or '—'}")
            st.markdown(f"**Status:** {vinfo.get('status')}")
        with colp2:
            st.markdown(f"**Commission:** {vinfo.get('commission_pct')}%")
            st.markdown(f"**Contact Email:** {vinfo.get('contact_email') or '—'}")
            st.markdown(f"**Contact Phone:** {vinfo.get('contact_phone') or '—'}")
        ui.card_close()
