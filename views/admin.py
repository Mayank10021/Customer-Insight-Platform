"""
Enhanced Admin Panel - User management, dataset upload, record management, and data quality monitoring
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from utils import ui
from utils.auth import get_all_users, get_login_history, update_user, delete_user, delete_user_permanently, register_user
from utils.data_handler import (
    save_uploaded_file, get_uploaded_files, delete_uploaded_file, overwrite_core_file, CORE_FILES
)
from utils.data_handler import get_data_quality_report
from utils import platform_feedback as pf


def _stars(n):
    n = int(n)
    return "★" * n + "☆" * (5 - n)


def render(data, user):
    ui.page_header("⚙️ Admin Control Center", "HOME &nbsp;›&nbsp; ADMIN")
    
    st.markdown("""
    <div style='background:linear-gradient(135deg, #5b6ee1 0%, #7d87f5 100%); 
                padding:16px; border-radius:12px; color:white; margin-bottom:20px;'>
        <div style='font-size:13px; font-weight:600;'>👑 Administrator Dashboard</div>
        <div style='font-size:12px; color:rgba(255,255,255,0.85); margin-top:4px;'>
            Manage users, upload datasets, monitor data quality, and add customer records
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "👥 Users", 
        "📤 Upload Data", 
        "➕ Add Customer",
        "📊 Data Quality",
        "🗑️ Manage Records",
        "📋 Activity",
        "💬 Feedback",
    ])
    
    # ============= TAB 1: USER MANAGEMENT =============
    with tab1:
        st.markdown("<h3 style='margin-top:0;'>Registered Users</h3>", unsafe_allow_html=True)
        
        users = get_all_users()
        if users:
            df_users = pd.DataFrame(users, columns=["ID", "Email", "Name", "Role", "Department", "Created", "Active", "Vendor Brand"])
            
            # User stats
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("👥 Total Users", len(df_users))
            col2.metric("👑 Admins", len(df_users[df_users['Role'] == 'Admin']))
            col3.metric("🏬 Vendors", len(df_users[df_users['Role'] == 'Vendor']))
            col4.metric("👁️ Viewers", len(df_users[df_users['Role'] == 'Viewer']))
            
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            st.dataframe(df_users, width="stretch", hide_index=True, height=300)
        else:
            st.info("No users found.")
        
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        # Add new user
        with col1:
            ui.card_open("➕ Create New User")
            with st.form("add_user_form", clear_on_submit=True):
                email = st.text_input("Email Address", placeholder="user@customerlens.com")
                name = st.text_input("Full Name", placeholder="John Doe")
                pwd = st.text_input("Password", type="password")
                role = st.selectbox("Role", ["Admin", "Vendor", "Viewer"])
                dept = st.text_input("Department", value="General")
                vendor_brand = st.text_input("Vendor Brand (required if role = Vendor)", placeholder="e.g. Samsung")
                submitted = st.form_submit_button("✅ Create User", width="stretch")
                
                if submitted:
                    if email and name and pwd and (role != "Vendor" or vendor_brand.strip()):
                        success, msg = register_user(email, pwd, name, role, dept,
                                                       vendor_brand=vendor_brand.strip() if role == "Vendor" else None)
                        if success:
                            if role == "Vendor" and vendor_brand.strip():
                                from utils import vendor_store
                                vendor_store.register_vendor(vendor_brand.strip(), business_name=name)
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                    else:
                        st.warning("Please fill all required fields (Vendor Brand is required for Vendor role).")
            ui.card_close()
        
        # Update user
        with col2:
            ui.card_open("✏️ Update User")
            if users:
                user_map = {f"{u[2]} ({u[1]})": u[0] for u in users}
                selected_label = st.selectbox("Select user", list(user_map.keys()), key="upd_user")
                selected_id = user_map[selected_label]
                new_role = st.selectbox("New Role", ["Admin", "Vendor", "Viewer"], key="upd_role")
                new_vendor_brand = st.text_input("Vendor Brand (if role = Vendor)", key="upd_vendor_brand")
                
                colx, coly = st.columns(2)
                with colx:
                    if st.button("🔄 Update Role", width="stretch"):
                        kwargs = {"role": new_role}
                        if new_role == "Vendor" and new_vendor_brand.strip():
                            kwargs["vendor_brand"] = new_vendor_brand.strip()
                        update_user(selected_id, **kwargs)
                        st.success("✅ Role updated")
                        st.rerun()
                with coly:
                    if st.button("🚫 Deactivate", width="stretch"):
                        delete_user(selected_id)
                        st.success("✅ User deactivated — they can no longer log in.")
                        st.rerun()

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                st.caption("⚠️ Permanent delete removes the account entirely and cannot be undone. "
                           "Use Deactivate if you might want to restore access later.")
                confirm_delete = st.checkbox(f"I understand — permanently delete '{selected_label}'", key="confirm_del_user")
                if st.button("🗑️ Delete Permanently", width="stretch", disabled=not confirm_delete, type="primary"):
                    ok, msg = delete_user_permanently(selected_id)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
            ui.card_close()
    
    # ============= TAB 2: UPLOAD DATA =============
    with tab2:
        st.markdown("<h3 style='margin-top:0;'>Dataset Upload & Management</h3>", unsafe_allow_html=True)
        
        ui.card_open("📤 Upload CSV Datasets")
        st.markdown("Upload additional CSV files for analysis. Multiple files can be uploaded at once.")
        uploaded_files = st.file_uploader(
            "Choose CSV files",
            type=["csv"],
            accept_multiple_files=True,
            key="admin_upload"
        )
        
        if uploaded_files:
            for f in uploaded_files:
                success, result = save_uploaded_file(f, user["email"])
                if success:
                    st.success(f"✅ {result['filename']} — {result['rows']:,} rows, {len(result['columns'])} columns")
                else:
                    st.error(f"❌ {result['error']}")
        ui.card_close()
        
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        
        ui.card_open("📋 Previously Uploaded Files")
        files = get_uploaded_files()
        if files:
            for f in files:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"""
                    <div style='padding:8px 0;'>
                        <strong>📄 {f[1]}</strong><br>
                        <span style='color:#8b8fb3; font-size:12px;'>
                            {f[4]:,} rows | Uploaded {str(f[2])[:16]} | By {f[3]}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    if st.button("🗑️ Delete", key=f"del_upload_{f[0]}", width="stretch"):
                        delete_uploaded_file(f[0], f[1])
                        st.rerun()
        else:
            st.info("No custom uploads yet.")
        ui.card_close()
    
    # ============= TAB 3: ADD CUSTOMER (now a guided wizard) =============
    with tab3:
        st.markdown("<h3 style='margin-top:0;'>➕ Add New Customer</h3>", unsafe_allow_html=True)
        ui.card_open("Use the guided Add New Data workflow")
        st.markdown("""
        Adding a customer here used to just insert one bare row — no order,
        no product link, and it didn't even touch the live dataset (so the
        customer count never moved and Customer 360 never saw them).

        That's been replaced by a proper step-by-step flow: **Create
        Customer → Add Order → Add/select Product → Add Feedback → Review**.
        Everything you enter is linked by CustomerID/OrderID/ProductID and
        updates the live dashboard immediately.
        """)
        if st.button("➕ Go to Add New Data", type="primary", width="stretch"):
            st.session_state["current_page"] = "add_data"
            st.rerun()
        ui.card_close()

    # ============= TAB 4: DATA QUALITY =============
    with tab4:
        st.markdown("<h3 style='margin-top:0;'>📊 Data Quality Monitor</h3>", unsafe_allow_html=True)
        
        selected_dataset = st.selectbox("Select Dataset to Analyze", list(CORE_FILES.keys()), key="quality_dataset")
        
        df = data.get(selected_dataset, pd.DataFrame())
        
        if df.empty:
            st.warning(f"No data available for {selected_dataset}")
        else:
            quality_report = get_data_quality_report(df)
            
            # Quality metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Records", f"{quality_report['total_rows']:,}")
            col2.metric("📋 Total Fields", f"{quality_report['total_columns']}")
            col3.metric("⚠️ Missing Cells", f"{quality_report['missing_cells']:,}")
            col4.metric("❌ Duplicates", f"{quality_report['duplicate_rows']:,}")
            
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            
            # Detailed report
            st.markdown("**Column Quality Breakdown**")
            
            quality_cols = []
            for stat in quality_report["column_stats"]:
                quality_cols.append({
                    "Column": stat["column"],
                    "Type": stat["dtype"],
                    "Missing": stat["missing"],
                    "Missing %": f"{stat['missing_pct']}%",
                    "Unique": stat["unique"],
                    "Status": "✅" if stat["missing_pct"] == 0 else "⚠️"
                })
            
            quality_df = pd.DataFrame(quality_cols)
            st.dataframe(quality_df, width="stretch", hide_index=True)
            
            st.markdown("""
            <div style='background:#f5f7fb; padding:12px; border-radius:8px; font-size:12px; margin-top:12px;'>
            <strong>📋 Quality Assessment:</strong>
            <ul style='margin:8px 0; padding-left:20px;'>
                <li><strong>✅ 0% missing:</strong> Column is complete</li>
                <li><strong>⚠️ 1-10% missing:</strong> Minor issues, can be ignored</li>
                <li><strong>❌ >10% missing:</strong> Significant gaps, may need attention</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # ============= TAB 5: MANAGE RECORDS =============
    with tab5:
        st.markdown("<h3 style='margin-top:0;'>🗑️ Manage Dataset Records</h3>", unsafe_allow_html=True)
        
        ui.card_open("Select & Delete Records")
        st.markdown("⚠️ Changes are saved directly to the CSV file. Be careful!")
        
        table_choice = st.selectbox("Select dataset", list(CORE_FILES.keys()), key="manage_dataset")
        df = data.get(table_choice, pd.DataFrame())
        
        if df.empty:
            st.warning("No data in this table.")
        else:
            st.markdown(f"**Showing first 200 records of {len(df):,} total**")
            st.dataframe(df.head(200), width="stretch", height=350)
            
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                id_col = df.columns[0]
                record_id = st.text_input(f"Enter {id_col} to delete")
            with col2:
                if st.button("🗑️ Delete Record", width="stretch"):
                    if record_id and record_id in df[id_col].astype(str).values:
                        new_df = df[df[id_col].astype(str) != record_id]
                        overwrite_core_file(table_choice, new_df)
                        st.success(f"✅ Deleted record {record_id}. Refresh page to see changes.")
                    else:
                        st.warning("⚠️ ID not found in this table.")
        
        ui.card_close()
    
    # ============= TAB 6: ACTIVITY LOG =============
    with tab6:
        st.markdown("<h3 style='margin-top:0;'>📋 Login Activity Log</h3>", unsafe_allow_html=True)
        
        ui.card_open("Recent User Activity")
        history = get_login_history(100)
        
        if history:
            df_history = pd.DataFrame(history, columns=["Email", "Login Time", "Status"])
            
            # Activity stats
            col1, col2 = st.columns(2)
            col1.metric("📊 Total Logins (Last 100)", len(df_history))
            col2.metric("✅ Successful", len(df_history[df_history['Status'] == 'Success']))
            
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            st.dataframe(df_history, width="stretch", hide_index=True, height=400)
        else:
            st.info("No login history yet.")
        
        ui.card_close()

    # ============= TAB 7: PLATFORM FEEDBACK MODERATION =============
    with tab7:
        st.markdown("<h3 style='margin-top:0;'>💬 Platform Feedback</h3>", unsafe_allow_html=True)
        st.caption("Reviews Viewers/Analysts/Vendors leave about the CustomerLens platform. "
                   "Visible ones appear as testimonials on the public landing page.")

        all_fb = pf.list_feedback()
        if not all_fb:
            st.info("No feedback submitted yet.")
        else:
            visible_count = sum(1 for r in all_fb if r["visible"])
            avg_rating = sum(r["rating"] for r in all_fb) / len(all_fb)

            c1, c2, c3 = st.columns(3)
            with c1:
                ui.kpi_card("Total Feedback", f"{len(all_fb)}", "all time", "💬", "#6c5ce7")
            with c2:
                ui.kpi_card("Visible on Landing Page", f"{visible_count}", "shown publicly", "🟢", "#00d68f")
            with c3:
                ui.kpi_card("Average Rating", f"{avg_rating:.1f} ★", f"{len(all_fb)} reviews", "⭐", "#f5a623")

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            ui.card_open("All Feedback")
            for row in all_fb:
                fc1, fc2, fc3 = st.columns([5, 1, 1])
                with fc1:
                    st.markdown(f"""
                    <div class="fm-mini-item" style="flex-direction:column; align-items:flex-start; gap:4px;">
                        <div style="display:flex; justify-content:space-between; width:100%;">
                            <span style="font-weight:700; color:#161029;">{row['name']} <span style="font-weight:400; color:#8a86a8; font-size:11px;">· {row['role']}</span></span>
                            <span style="color:#f5a623;">{_stars(row['rating'])}</span>
                        </div>
                        <div style="font-weight:400; color:#4b4768;">{row['text']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with fc2:
                    if row["visible"]:
                        if st.button("🙈 Hide", key=f"fb_hide_{row['id']}", width="stretch"):
                            pf.set_visibility(row["id"], False)
                            st.rerun()
                    else:
                        if st.button("👁️ Show", key=f"fb_show_{row['id']}", width="stretch"):
                            pf.set_visibility(row["id"], True)
                            st.rerun()
                with fc3:
                    if st.button("🗑️ Delete", key=f"fb_del_{row['id']}", width="stretch"):
                        pf.delete_feedback(row["id"])
                        st.rerun()
            ui.card_close()