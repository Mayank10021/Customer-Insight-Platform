"""
Vendor Management / Vendor Dashboard
- Admin sees: every vendor (Brand), performance ranking, register / edit /
  activate / suspend vendors.
- Vendor sees: their own scoped dashboard (data has already been filtered
  to their Brand by scope_data_for_vendor before this page renders) —
  own sales, own products, own inventory alerts, own recommendations.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import ui
from utils.data_handler import get_merged_orders, get_cached_vendor_performance
from utils import vendor_store


@ui.safe_page
def render(data, user):
    if user["role"] == "Vendor":
        _render_vendor_dashboard(data, user)
    else:
        _render_admin_vendor_management(data, user)


# =====================================================================
# ADMIN — Vendor Management
# =====================================================================
def _render_admin_vendor_management(data, user):
    ui.page_header("🏷️ Vendor Management", "HOME &nbsp;›&nbsp; VENDOR MANAGEMENT")

    # ---------------- Isolated Vendor/Analyst uploads (always visible) ----------------
    from utils.data_handler import list_all_user_datasets, get_combined_vendor_data
    user_datasets = list_all_user_datasets()
    ui.card_open("🗂️ Isolated Vendor & Analyst Uploads")
    st.caption("Every Vendor/Analyst uploads their own dataset each login, fully isolated from everyone "
                "else's — this is what they've each got loaded right now (metadata only; their data itself "
                "stays isolated even from you, except via the combined view below for Vendors specifically).")
    if not user_datasets:
        st.info("No Vendor or Analyst has uploaded a dataset yet in this environment.")
    else:
        rows = []
        for m in user_datasets:
            total_rows = sum(m.get("_row_counts", {}).values())
            rows.append({
                "User": m.get("user_name"), "Role": m.get("role"),
                "Brand": m.get("vendor_brand") or "—",
                "Datasets": ", ".join(m.get("_row_counts", {}).keys()) or "—",
                "Total Rows": total_rows,
                "Uploaded At": (m.get("uploaded_at") or "")[:19].replace("T", " "),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=min(300, 60 + 35 * len(rows)))

        if st.button("📊 View Combined Vendor Analytics (all Vendor uploads merged)", key="vm_combined_btn"):
            st.session_state["vm_show_combined"] = True
        if st.session_state.get("vm_show_combined"):
            combined = get_combined_vendor_data()
            combined_products = combined.get("products", pd.DataFrame())
            combined_orders = combined.get("orders", pd.DataFrame())
            if combined_products.empty and combined_orders.empty:
                st.info("No Vendor-role uploads to combine yet (Analyst uploads are excluded — they're ad-hoc analysis, not real vendor business data).")
            else:
                colc1, colc2 = st.columns(2)
                with colc1:
                    st.metric("Combined Products", f"{len(combined_products):,}")
                with colc2:
                    st.metric("Combined Orders", f"{len(combined_orders):,}")
                if "SourceVendor" in combined_products.columns:
                    by_source = combined_products.groupby("SourceVendor").size().reset_index(name="Products")
                    fig = px.bar(by_source, x="SourceVendor", y="Products", color="SourceVendor")
                    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
                    st.plotly_chart(fig, width="stretch")
    ui.card_close()
    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    products = data.get("products", pd.DataFrame())
    feedback = data.get("feedback", pd.DataFrame())
    merged = get_merged_orders(data)

    if products.empty or "Brand" not in products.columns:
        st.warning("No shared platform product data yet — upload data (with a 'Brand' column) via the "
                    "welcome screen or Data Studio to see cross-vendor performance ranking below.")
        return

    vendor_store.ensure_vendor_seed(products)
    vendors_df = vendor_store.list_vendors_df()

    _, top_row_r = st.columns([5, 1])
    with top_row_r:
        if st.button("🔄 Refresh Vendor Details", key="vm_refresh", width="stretch",
                      help="Fills in GST/email/phone/address for any vendor that's missing them"):
            vendor_store.ensure_vendor_seed(products)
            st.success("Vendor details refreshed.")
            st.rerun()

    perf = get_cached_vendor_performance(merged, feedback) if not merged.empty else pd.DataFrame()

    active_count = len(vendors_df[vendors_df["status"] == "Active"]) if not vendors_df.empty else 0
    suspended_count = len(vendors_df[vendors_df["status"] == "Suspended"]) if not vendors_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("Total Vendors", f"{len(vendors_df)}", "registered brands", "🏷️", "#5b6ee1")
    with c2:
        ui.kpi_card("Active Vendors", f"{active_count}", "currently selling", "✅", "#00c2d1")
    with c3:
        ui.kpi_card("Suspended", f"{suspended_count}", "on hold", "⛔", "#e74c3c")
    with c4:
        top_vendor = perf.iloc[0]["Brand"] if not perf.empty else "—"
        ui.kpi_card("Top Vendor", top_vendor, "by revenue", "🏆", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Performance Ranking", "🗂️ Manage Vendors", "➕ Register New Vendor"])

    # ---------------- Performance ranking ----------------
    with tab1:
        ui.card_open("Vendor Performance Ranking")
        if perf.empty:
            st.info("No order data yet — vendor performance needs sales history.")
        else:
            display = perf.merge(vendors_df[["brand_name", "status", "commission_pct"]],
                                  left_on="Brand", right_on="brand_name", how="left").drop(columns=["brand_name"])
            display["status"] = display["status"].fillna("Active")
            show_cols = ["Rank", "Brand", "status", "Revenue", "Profit", "Orders", "UnitsSold",
                         "AvgOrderValue", "AvgRating", "GrowthPct", "MarketSharePct", "commission_pct"]
            show_cols = [c for c in show_cols if c in display.columns]
            st.dataframe(
                display[show_cols].rename(columns={
                    "status": "Status", "commission_pct": "Commission %", "GrowthPct": "Growth % (MoM)",
                    "AvgOrderValue": "Avg Order Value", "MarketSharePct": "Market Share %",
                }),
                width="stretch", hide_index=True, height=340,
            )

            col1, col2 = st.columns(2)
            with col1:
                fig = px.treemap(perf.head(15), path=["Brand"], values="Revenue", color="Profit",
                                  color_continuous_scale="RdYlGn", title=None)
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340)
                st.plotly_chart(fig, width="stretch")
                st.caption("Box size = Revenue · Color = Profit (Treemap)")
            with col2:
                fig2 = px.scatter(perf.head(20), x="Orders", y="AvgRating", size="Revenue",
                                   color="Brand", hover_data=["GrowthPct", "MarketSharePct"])
                fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340,
                                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
                st.plotly_chart(fig2, width="stretch")

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            fig3 = px.bar(perf.sort_values("Revenue", ascending=False).head(10), x="Brand",
                           y=["Revenue", "Profit"], barmode="group",
                           color_discrete_sequence=["#5b6ee1", "#00c2d1"])
            fig3.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig3, width="stretch")
        ui.card_close()

    # ---------------- Manage vendors: activate / suspend / edit ----------------
    with tab2:
        ui.card_open("All Registered Vendors")
        if vendors_df.empty:
            st.info("No vendors registered yet.")
        else:
            st.dataframe(
                vendors_df.rename(columns={
                    "brand_name": "Brand / Vendor", "business_name": "Business Name",
                    "gst_number": "GST No.", "contact_email": "Email", "contact_phone": "Phone",
                    "commission_pct": "Commission %", "status": "Status",
                }),
                width="stretch", hide_index=True, height=280,
            )
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("Edit / Activate / Suspend a Vendor")
        if vendors_df.empty:
            st.info("Register a vendor first.")
        else:
            selected_brand = st.selectbox("Select vendor", vendors_df["brand_name"].tolist(), key="vm_select")
            v = vendor_store.get_vendor(selected_brand)
            if v:
                # Widget keys are namespaced per-brand (vm_biz_OnePlus vs
                # vm_biz_Apple, etc.) — with a static key like "vm_biz",
                # Streamlit keeps the *previous* vendor's typed-in value in
                # session_state and ignores the new `value=` on every rerun,
                # which is exactly what made switching the dropdown still
                # show the last vendor's details instead of the new one.
                ns = str(selected_brand or "").replace(" ", "_")
                col1, col2 = st.columns(2)
                with col1:
                    business_name = st.text_input("Business Name", value=v.get("business_name") or "",
                                                   key=f"vm_biz_{ns}")
                    gst = st.text_input("GST Number", value=v.get("gst_number") or "", key=f"vm_gst_{ns}")
                    email = st.text_input("Contact Email", value=v.get("contact_email") or "",
                                           key=f"vm_email_{ns}")
                with col2:
                    phone = st.text_input("Contact Phone", value=v.get("contact_phone") or "",
                                           key=f"vm_phone_{ns}")
                    address = st.text_input("Address", value=v.get("address") or "", key=f"vm_addr_{ns}")
                    commission = st.number_input("Commission %", min_value=0.0, max_value=100.0,
                                                  value=float(v.get("commission_pct") or 10.0), step=0.5,
                                                  key=f"vm_comm_{ns}")

                colA, colB, colC = st.columns(3)
                with colA:
                    if st.button("💾 Save Changes", key=f"vm_save_{ns}", width="stretch"):
                        vendor_store.update_vendor(selected_brand, business_name=business_name, gst_number=gst,
                                                    contact_email=email, contact_phone=phone, address=address,
                                                    commission_pct=commission)
                        st.success(f"Updated {selected_brand}.")
                        st.rerun()
                with colB:
                    if v.get("status") == "Active":
                        if st.button("⛔ Suspend Vendor", key=f"vm_suspend_{ns}", width="stretch"):
                            vendor_store.set_vendor_status(selected_brand, "Suspended")
                            st.warning(f"{selected_brand} suspended.")
                            st.rerun()
                    else:
                        if st.button("✅ Activate Vendor", key=f"vm_activate_{ns}", width="stretch"):
                            vendor_store.set_vendor_status(selected_brand, "Active")
                            st.success(f"{selected_brand} activated.")
                            st.rerun()
                with colC:
                    st.caption(f"Status: **{v.get('status')}**")

                st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
                st.caption("⚠️ Deleting removes this vendor's registry record (contact info, GST, "
                           "commission). Their products and past sales history stay untouched — "
                           "use Suspend instead if you just want to pause them temporarily.")
                confirm_del_vendor = st.checkbox(f"I understand — permanently delete '{selected_brand}' from the vendor registry",
                                                  key=f"vm_confirm_del_{ns}")
                if st.button("🗑️ Delete Vendor", key=f"vm_delete_{ns}", width="stretch",
                              disabled=not confirm_del_vendor, type="primary"):
                    vendor_store.delete_vendor(selected_brand)
                    st.success(f"{selected_brand} deleted from the vendor registry.")
                    st.rerun()
        ui.card_close()

    # ---------------- Register new vendor ----------------
    with tab3:
        ui.card_open("Register a New Vendor")
        st.caption("Registering a vendor here creates the business profile. To actually sell, products with "
                    "this Brand name need to exist in the Product catalog (Data Studio / Admin Panel upload).")
        col1, col2 = st.columns(2)
        with col1:
            new_brand = st.text_input("Brand / Vendor Name *", key="new_vendor_brand")
            new_business = st.text_input("Business Name", key="new_vendor_biz")
            new_gst = st.text_input("GST Number", key="new_vendor_gst")
        with col2:
            new_email = st.text_input("Contact Email", key="new_vendor_email")
            new_phone = st.text_input("Contact Phone", key="new_vendor_phone")
            new_commission = st.number_input("Commission %", min_value=0.0, max_value=100.0, value=10.0,
                                              step=0.5, key="new_vendor_comm")
        new_address = st.text_input("Address", key="new_vendor_addr")

        if st.button("➕ Register Vendor", key="new_vendor_btn", width="stretch"):
            if not new_brand.strip():
                st.warning("Brand / Vendor name is required.")
            else:
                ok, msg = vendor_store.register_vendor(
                    new_brand, business_name=new_business, gst_number=new_gst,
                    contact_email=new_email, contact_phone=new_phone, address=new_address,
                    commission_pct=new_commission,
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        ui.card_close()


# =====================================================================
# VENDOR — Own scoped dashboard
# =====================================================================
def _render_vendor_dashboard(data, user):
    brand = user.get("vendor_brand")
    ui.page_header(f"🏬 Vendor Dashboard — {brand or 'No Brand Assigned'}", "HOME &nbsp;›&nbsp; VENDOR DASHBOARD")

    if not brand:
        st.error("Your account isn't linked to a Brand yet. Ask an Admin to set your vendor_brand in "
                  "the Admin Panel so your dashboard can show your own data.")
        return

    products = data.get("products", pd.DataFrame())
    merged = get_merged_orders(data)
    inventory = data.get("inventory", pd.DataFrame())
    feedback = data.get("feedback", pd.DataFrame())

    vinfo = vendor_store.get_vendor(brand)
    if vinfo and vinfo.get("status") == "Suspended":
        st.error("⛔ Your vendor account is currently **suspended** by the Admin. "
                  "Contact platform support to resolve this.")

    if products.empty:
        st.info("No products found for your brand yet. Ask an Admin to add your catalog.")
        return

    total_revenue = merged["TotalAmount"].sum() if not merged.empty else 0
    total_orders = merged["OrderID"].nunique() if not merged.empty else 0
    total_products = len(products)
    avg_rating = products["Rating"].mean() if "Rating" in products.columns and not products.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.kpi_card("My Revenue", f"₹{total_revenue:,.0f}", "all time", "💰", "#00c2d1")
    with c2:
        ui.kpi_card("My Orders", f"{total_orders:,}", "fulfilled", "🧾", "#5b6ee1")
    with c3:
        ui.kpi_card("My Products", f"{total_products}", "in catalog", "📦", "#6c5ce7")
    with c4:
        ui.kpi_card("Avg Rating", f"{avg_rating:.2f} ★", "across products", "⭐", "#161029")

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        ui.card_open("📈 My Sales Trend (Monthly)")
        if not merged.empty and "Date" in merged.columns:
            m = merged.copy()
            m["Month"] = pd.to_datetime(m["Date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
            trend = m.groupby("Month")["TotalAmount"].sum().reset_index()
            fig = px.line(trend, x="Month", y="TotalAmount", markers=True)
            fig.update_traces(line_color="#00c2d1")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sales yet.")
        ui.card_close()

    with col2:
        ui.card_open("🏆 My Top Products")
        if not merged.empty:
            top = merged.groupby(["ProductID", "ProductName"])["Quantity"].sum().reset_index()
            top = top.sort_values("Quantity", ascending=False).head(8)
            fig = px.bar(top, x="Quantity", y="ProductName", orientation="h", color_discrete_sequence=["#6c5ce7"])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sales yet.")
        ui.card_close()

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    ui.card_open("🚨 My Stock Alerts")
    if "Stock" in products.columns:
        low = products[products["Stock"] < 20][["ProductID", "ProductName", "Category", "Stock", "Price"]]
        low = low.sort_values("Stock")
        if low.empty:
            st.success("✅ No low-stock products right now.")
        else:
            st.dataframe(low, width="stretch", hide_index=True, height=220)
    ui.card_close()

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    ui.card_open("👤 My Vendor Profile")
    if vinfo:
        colp1, colp2 = st.columns(2)
        with colp1:
            st.markdown(f"**Business Name:** {vinfo.get('business_name') or '—'}")
            st.markdown(f"**GST Number:** {vinfo.get('gst_number') or '—'}")
            st.markdown(f"**Status:** {vinfo.get('status')}")
        with colp2:
            st.markdown(f"**Commission:** {vinfo.get('commission_pct')}%")
            st.markdown(f"**Contact Email:** {vinfo.get('contact_email') or '—'}")
            st.markdown(f"**Contact Phone:** {vinfo.get('contact_phone') or '—'}")
        st.caption("Contact details are for Admin reference. Update your name/department from the profile menu "
                    "in the top bar; contact an Admin to change business/GST details or commission %.")
    else:
        st.info("No vendor profile on file yet — an Admin needs to register your brand in Vendor Management.")
    ui.card_close()
