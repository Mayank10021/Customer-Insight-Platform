"""
Enhanced Data Studio - Multi-file upload, merge, clean, and analyze with data quality tracking
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from utils import ui
from utils.data_handler import (
    merge_multiple_files, add_data_quality_column, get_data_quality_report,
    clear_platform_data, get_platform_data_updated_at, save_platform_data, CORE_FILES,
    get_platform_metadata, rename_columns, convert_column_dtype, get_full_data_preview,
    add_record, delete_records, get_dataset_history, activate_history_version,
)
from utils.validators import detect_dataset_type, validate_dataset
from utils.report_generator import build_excel_report


def _profile(df):
    """Generate a detailed data quality profile"""
    profile = pd.DataFrame({
        "Column": df.columns,
        "Data Type": [str(t) for t in df.dtypes],
        "Missing Values": df.isna().sum().values,
        "Missing %": (df.isna().mean() * 100).round(1).values,
        "Unique Values": [df[c].nunique() for c in df.columns],
        "Data Quality": ["✅ Good" if df[c].isna().sum() == 0 else "⚠️ Needs Review" for c in df.columns],
    })
    return profile


def render(data, user):
    ui.page_header("📊 Advanced Data Studio", "HOME &nbsp;›&nbsp; DATA STUDIO")
    
    st.markdown("""
    <div style='background:linear-gradient(135deg, #00c2d1 0%, #2ebcd8 100%); 
                padding:16px; border-radius:12px; color:white; margin-bottom:20px;'>
        <div style='font-size:13px; font-weight:600;'>🎯 Upload, merge, clean, and analyze your data in one place</div>
        <div style='font-size:12px; color:rgba(255,255,255,0.8); margin-top:6px;'>
            Support for single or multiple CSV files. Automatic data quality detection and cleaning options.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ============= TAB STRUCTURE =============
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Upload & Merge", 
        "🔍 Analyze Data Quality", 
        "🧹 Clean Data", 
        "📥 Download Results",
        "🗂️ Data Manager",
    ])
    
    # ============= TAB 1: UPLOAD & MERGE =============
    with tab1:
        if user["role"] == "Viewer":
            st.info("🔒 Viewer accounts have read-only access and cannot upload or replace data. "
                     "Ask an Admin to manage datasets.")
        else:
            st.markdown("<h4 style='margin-top:0;'>Step 1️⃣: Upload Your Files</h4>", unsafe_allow_html=True)

            upload_mode = st.radio(
                "Choose upload mode:",
                ["Single File", "Multiple Files (Merge)"],
                horizontal=True
            )

            if upload_mode == "Single File":
                st.markdown("**Upload one CSV file for cleaning and analysis**")
                uploaded = st.file_uploader("Upload CSV file", type=["csv"], key="studio_upload_single")

                if uploaded is not None:
                    if st.session_state.get("studio_filename") != uploaded.name:
                        st.session_state["studio_raw_df"] = pd.read_csv(uploaded)
                        st.session_state["studio_filename"] = uploaded.name
                        st.session_state["studio_upload_mode"] = "single"

                    st.success(f"✅ Loaded: {uploaded.name}")

            else:  # Multiple files
                st.markdown("**Upload multiple CSV files to merge them together**")
                uploaded_files = st.file_uploader(
                    "Upload multiple CSV files", 
                    type=["csv"], 
                    accept_multiple_files=True,
                    key="studio_upload_multi"
                )

                if uploaded_files:
                    st.markdown(f"📁 **{len(uploaded_files)} file(s) selected:**")
                    for i, f in enumerate(uploaded_files, 1):
                        st.caption(f"{i}. {f.name}")

                    merge_name = st.text_input(
                        "Name for merged dataset",
                        value=f"merged_dataset_{pd.Timestamp.now().strftime('%Y%m%d')}",
                        key="merge_name"
                    )

                    if st.button("🔗 Merge Files", width="stretch"):
                        with st.spinner("Merging files..."):
                            success, result = merge_multiple_files(uploaded_files, merge_name, user["email"])

                            if success:
                                st.session_state["studio_raw_df"] = pd.read_csv(
                                    f"uploads/{result['filename']}"
                                )
                                st.session_state["studio_filename"] = result["filename"]
                                st.session_state["studio_upload_mode"] = "multi"
                                st.success(f"✅ Merged {len(uploaded_files)} files → {result['rows']:,} rows")
                            else:
                                st.error(f"❌ {result['error']}")

            # Show upload summary
            if st.session_state.get("studio_raw_df") is not None:
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                raw_df = st.session_state["studio_raw_df"]
                col1, col2, col3 = st.columns(3)
                col1.metric("📊 Rows", f"{len(raw_df):,}")
                col2.metric("📋 Columns", f"{len(raw_df.columns)}")
                col3.metric("⚠️ Missing Cells", f"{int(raw_df.isna().sum().sum()):,}")

                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                st.caption("This file is only in this cleaning workspace so far — it won't show up on the "
                           "Dashboard, Customer 360, or Analytics pages until you send it to the platform.")
                if st.button("📊 Send This Data to the Platform (all pages, all users)",
                             width="stretch", key="studio_send_platform"):
                    dtype = detect_dataset_type(raw_df)
                    if dtype == "unknown":
                        st.error("Couldn't confidently identify this as Customers/Orders/Products/Payments/"
                                  "Feedback/etc. Check that column names match (e.g. CustomerID, OrderID), "
                                  "or use the multi-file uploader on the main Upload screen instead.")
                    else:
                        quality = validate_dataset(raw_df, dtype)
                        df_to_merge = raw_df.copy()
                        for date_col in {"Date", "SignupDate", "JoinDate", "OpeningDate", "ReturnDate"} & set(df_to_merge.columns):
                            df_to_merge[date_col] = pd.to_datetime(df_to_merge[date_col], errors="coerce")

                        platform_data = dict(st.session_state.get("custom_data") or {})
                        for key in CORE_FILES.keys():
                            platform_data.setdefault(key, pd.DataFrame())
                        platform_data[dtype] = df_to_merge

                        save_platform_data(platform_data, dataset_meta={dtype: {"uploaded_by": user["name"]}})
                        st.session_state["custom_data"] = platform_data
                        reports = st.session_state.get("upload_reports") or {}
                        reports[dtype] = [{
                            "filename": st.session_state.get("studio_filename", "uploaded.csv"),
                            "rows": len(df_to_merge), "columns": len(df_to_merge.columns), "report": quality,
                        }]
                        st.session_state["upload_reports"] = reports
                        st.success(f"✅ Detected as **{dtype.capitalize()}** and pushed to the platform — "
                                    f"now visible on Dashboard, Customer 360, Analytics, and Reports for every user.")
                        st.rerun()

    # ============= TAB 2: DATA QUALITY ANALYSIS =============
    with tab2:
        if st.session_state.get("studio_raw_df") is None:
            st.info("👆 Upload a file in Tab 1 first")
        else:
            raw_df = st.session_state["studio_raw_df"]

            st.markdown("<h4 style='margin-top:0;'>📊 Data Quality Report</h4>", unsafe_allow_html=True)

            # Quality metrics
            quality_report = get_data_quality_report(raw_df)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Total Records",
                f"{quality_report['total_rows']:,}",
                delta=None
            )
            col2.metric(
                "Total Fields",
                f"{quality_report['total_columns']}",
                delta=None
            )
            col3.metric(
                "Missing Data",
                f"{quality_report['missing_cells']:,} cells",
                delta=f"{round((quality_report['missing_cells']/quality_report['total_cells'])*100, 2)}%"
            )
            col4.metric(
                "Duplicate Rows",
                f"{quality_report['duplicate_rows']:,}",
                delta=None
            )

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

            # Detailed column profile
            st.markdown("**📋 Column-by-Column Analysis**")
            profile_df = _profile(raw_df)
            st.dataframe(profile_df, width="stretch", height=350)

            st.markdown("""
            <div style='background:#f5f7fb; padding:12px; border-radius:8px; font-size:12px; margin-top:12px;'>
            <strong>💡 What This Means:</strong>
            <ul style='margin:8px 0; padding-left:20px;'>
                <li><strong>Missing %:</strong> Percentage of empty values in the column</li>
                <li><strong>Unique Values:</strong> Number of distinct values (lower might indicate duplicates)</li>
                <li><strong>Data Quality:</strong> Automatic assessment based on data completeness</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # ============= TAB 3: DATA CLEANING =============
    with tab3:
        if st.session_state.get("studio_raw_df") is None:
            st.info("👆 Upload a file in Tab 1 first")
        else:
            raw_df = st.session_state["studio_raw_df"]

            st.markdown("<h4 style='margin-top:0;'>🧹 Data Cleaning Options</h4>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Missing Values Strategy**")
                missing_strategy = st.selectbox(
                    "How should missing values be handled?",
                    [
                        "Leave as is",
                        "Drop rows with any missing value",
                        "Fill numeric with mean / text with mode",
                        "Fill with default values"
                    ],
                    key="studio_missing_strategy",
                    label_visibility="collapsed"
                )

            with col2:
                st.markdown("**Duplicate Rows**")
                remove_dupes = st.checkbox(
                    f"Remove {int(raw_df.duplicated().sum())} duplicate row(s)",
                    key="studio_remove_dupes"
                )

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

            # Additional cleaning options
            st.markdown("**Additional Options**")
            col3, col4 = st.columns(2)

            with col3:
                remove_spaces = st.checkbox("Remove leading/trailing spaces", key="remove_spaces")
            with col4:
                standardize_case = st.checkbox("Standardize text to lowercase", key="standardize_case")

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            if st.button("🧹 Apply Cleaning", key="studio_apply_clean", width="stretch"):
                cleaned = raw_df.copy()
                rows_before = len(cleaned)

                # Handle missing values
                if missing_strategy == "Drop rows with any missing value":
                    cleaned = cleaned.dropna()
                elif missing_strategy == "Fill numeric with mean / text with mode":
                    for col in cleaned.columns:
                        if cleaned[col].isna().any():
                            if pd.api.types.is_numeric_dtype(cleaned[col]):
                                cleaned[col] = cleaned[col].fillna(cleaned[col].mean())
                            else:
                                mode_vals = cleaned[col].mode()
                                fill_val = mode_vals[0] if not mode_vals.empty else ""
                                cleaned[col] = cleaned[col].fillna(fill_val)

                # Remove duplicates
                if remove_dupes:
                    cleaned = cleaned.drop_duplicates()

                # Remove spaces
                if remove_spaces:
                    for col in cleaned.select_dtypes(include=['object']).columns:
                        cleaned[col] = cleaned[col].str.strip()

                # Standardize case
                if standardize_case:
                    for col in cleaned.select_dtypes(include=['object']).columns:
                        cleaned[col] = cleaned[col].str.lower()

                # Add data quality column
                cleaned = add_data_quality_column(cleaned)

                st.session_state["studio_cleaned_df"] = cleaned
                rows_after = len(cleaned)
                rows_removed = rows_before - rows_after

                st.success(f"✅ Cleaned! {rows_before:,} → {rows_after:,} rows ({rows_removed:,} removed)")

    # ============= TAB 4: DOWNLOAD RESULTS =============
    with tab4:
        cleaned_df = st.session_state.get("studio_cleaned_df")

        if cleaned_df is None:
            st.info("👆 Complete cleaning in Tab 3 first, or skip cleaning to download raw data")

            # Option to download raw data
            if st.session_state.get("studio_raw_df") is not None:
                raw_df = st.session_state["studio_raw_df"]
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    csv_bytes = raw_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Download Raw CSV",
                        csv_bytes,
                        file_name=f"raw_{st.session_state.get('studio_filename', 'data.csv')}",
                        mime="text/csv",
                        width="stretch",
                    )
                with col2:
                    excel_bytes = build_excel_report({
                        "Raw Data": raw_df,
                        "Data Profile": _profile(raw_df),
                    })
                    st.download_button(
                        "⬇️ Download Analysis Report (Excel)",
                        excel_bytes,
                        file_name=f"analysis_{st.session_state.get('studio_filename', 'data.csv').replace('.csv', '')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                    )
        else:
            st.markdown("<h4 style='margin-top:0;'>✅ Ready to Download</h4>", unsafe_allow_html=True)

            # Preview cleaned data
            st.markdown("**Preview of Cleaned Data (First 50 rows)**")
            st.dataframe(cleaned_df.head(50), width="stretch", height=350)

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            # Download options
            st.markdown("**Download Options**")
            col1, col2 = st.columns(2)

            with col1:
                csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download Cleaned CSV",
                    csv_bytes,
                    file_name=f"cleaned_{st.session_state.get('studio_filename', 'data.csv')}",
                    mime="text/csv",
                    width="stretch",
                )

            with col2:
                # Create comparison report
                raw_df = st.session_state.get("studio_raw_df")
                excel_bytes = build_excel_report({
                    "Cleaned Data": cleaned_df,
                    "Before Cleaning Profile": _profile(raw_df),
                    "After Cleaning Profile": _profile(cleaned_df),
                })
                st.download_button(
                    "⬇️ Download Full Report (Excel)",
                    excel_bytes,
                    file_name=f"report_{st.session_state.get('studio_filename', 'data.csv').replace('.csv', '')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )

            # Summary of changes
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            st.markdown("**📊 Cleaning Summary**")

            raw_df = st.session_state.get("studio_raw_df")

            if isinstance(raw_df, pd.DataFrame) and isinstance(cleaned_df, pd.DataFrame):
                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Rows Before",
                    f"{len(raw_df):,}"
                )

                col2.metric(
                    "Rows After",
                    f"{len(cleaned_df):,}"
                )

                col3.metric(
                    "Rows Removed",
                    f"{len(raw_df) - len(cleaned_df):,}"
                )

        # Reset button for the single-file cleaning workflow — shown whenever
        # there's something loaded, regardless of which branch above rendered.
        if st.session_state.get("studio_raw_df") is not None:
            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Start Over with New File", width="stretch", key="studio_reset"):
                for k in ["studio_raw_df", "studio_filename", "studio_cleaned_df", "studio_upload_mode"]:
                    st.session_state.pop(k, None)
                st.rerun()
    
    # ============= TAB 5: DATA MANAGER (platform-wide datasets) =============
    with tab5:
        st.markdown("<h4 style='margin-top:0;'>🗂️ Platform Datasets</h4>", unsafe_allow_html=True)
        st.caption("These are the datasets currently powering every module — Dashboard, Customer 360, Analytics, Forecasting, and Reports — shared with every user, not just this browser.")

        last_updated = get_platform_data_updated_at()
        if last_updated:
            st.caption(f"🕒 Last updated: {last_updated.strftime('%d %b %Y, %I:%M %p')}")

        rows = []
        platform_meta = get_platform_metadata()
        for key, df in data.items():
            status = "✅ Loaded" if not df.empty else "⚪ Empty"
            meta = platform_meta.get(key, {})
            uploaded_at = meta.get("uploaded_at", "")
            if uploaded_at:
                try:
                    uploaded_at = datetime.fromisoformat(uploaded_at).strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    pass
            file_size = meta.get("file_size")
            file_size_str = f"{file_size / 1024:.1f} KB" if file_size else "—"
            rows.append({
                "Dataset Name": key.capitalize(),
                "Uploaded By": meta.get("uploaded_by", "—") if not df.empty else "—",
                "Upload Date & Time": uploaded_at if not df.empty else "—",
                "Rows": len(df),
                "Columns": len(df.columns) if not df.empty else 0,
                "File Size": file_size_str if not df.empty else "—",
                "Status": status,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        upload_reports = st.session_state.get("upload_reports") or {}
        if upload_reports:
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            st.markdown("**📋 Last Upload Validation Report**")
            for dtype, items in upload_reports.items():
                for item in items:
                    rep = item["report"]
                    status = "🟢" if not rep["errors"] and not rep["warnings"] else ("🔴" if rep["errors"] else "🟡")
                    with st.expander(f"{status} {item['filename']} → **{dtype}** ({item['rows']:,} rows)"):
                        for e in rep["errors"]:
                            st.error(e)
                        for w in rep["warnings"]:
                            st.warning(w)
                        for i in rep["info"]:
                            st.success(i)

        st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
        if user["role"] == "Admin":
            st.markdown("**🔁 Update a Specific Dataset**")
            st.caption("Missed a file, or need to fix just one dataset (e.g. only Products)? "
                       "Replace it here directly — everything else on the platform stays untouched.")

            dm_col1, dm_col2 = st.columns([1, 2])
            with dm_col1:
                target_key = st.selectbox(
                    "Which dataset?", list(CORE_FILES.keys()),
                    format_func=lambda k: k.capitalize(), key="dm_target_dataset",
                )
            with dm_col2:
                replace_file = st.file_uploader(
                    f"Upload a replacement CSV for '{target_key.capitalize()}'",
                    type=["csv"], key=f"dm_replace_uploader_{target_key}",
                )
            if replace_file is not None:
                if st.button(f"✅ Replace '{target_key.capitalize()}' Dataset",
                             key="dm_replace_confirm", width="stretch"):
                    try:
                        new_df = pd.read_csv(replace_file)
                    except Exception as e:
                        st.error(f"Could not read file: {e}")
                    else:
                        quality = validate_dataset(new_df, target_key)
                        for date_col in {"Date", "SignupDate", "JoinDate", "OpeningDate", "ReturnDate"} & set(new_df.columns):
                            new_df[date_col] = pd.to_datetime(new_df[date_col], errors="coerce")
                        platform_data = dict(data)
                        platform_data[target_key] = new_df
                        save_platform_data(platform_data, dataset_meta={target_key: {"uploaded_by": user["name"]}})
                        st.session_state["custom_data"] = platform_data
                        reports = st.session_state.get("upload_reports") or {}
                        reports[target_key] = [{
                            "filename": replace_file.name, "rows": len(new_df),
                            "columns": len(new_df.columns), "report": quality,
                        }]
                        st.session_state["upload_reports"] = reports
                        st.success(f"✅ '{target_key.capitalize()}' dataset replaced — "
                                    f"{len(new_df):,} rows now live for every user.")
                        if quality["errors"] or quality["warnings"]:
                            for e in quality["errors"]:
                                st.error(e)
                            for w in quality["warnings"]:
                                st.warning(w)
                        st.rerun()

            st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
            st.markdown("**➕ Add a Custom / Extra Dataset**")
            st.caption("Uploading something that isn't Customers/Orders/Products/etc.? It's auto-detected if it "
                       "matches a known type — otherwise it's still saved under its own name and made "
                       "browsable in Data Explorer, instead of just disappearing.")
            custom_file = st.file_uploader("Upload any other CSV", type=["csv"], key="dm_custom_uploader")
            if custom_file is not None:
                default_name = custom_file.name.rsplit(".", 1)[0].lower().replace(" ", "_")
                custom_key = st.text_input("Save this dataset as (used only if it isn't auto-detected)",
                                            value=default_name, key="dm_custom_key")
                if st.button("✅ Add This Dataset", key="dm_custom_confirm", width="stretch"):
                    try:
                        new_df = pd.read_csv(custom_file)
                    except Exception as e:
                        st.error(f"Could not read file: {e}")
                    else:
                        detected = detect_dataset_type(new_df)
                        quality = validate_dataset(new_df, detected)
                        key_to_use = (
                            detected
                            if detected != "unknown"
                            else ((custom_key or "").strip() or default_name)
                        )
                        for date_col in {"Date", "SignupDate", "JoinDate", "OpeningDate", "ReturnDate"} & set(new_df.columns):
                            new_df[date_col] = pd.to_datetime(new_df[date_col], errors="coerce")
                        platform_data = dict(data)
                        platform_data[key_to_use] = new_df
                        save_platform_data(platform_data, dataset_meta={key_to_use: {"uploaded_by": user["name"]}})
                        st.session_state["custom_data"] = platform_data
                        if detected != "unknown":
                            st.success(f"✅ Detected as **{detected.capitalize()}** and merged into that dataset.")
                        else:
                            st.success(f"✅ Saved as a new dataset called **'{key_to_use}'** — now browsable "
                                        f"and downloadable from Data Explorer.")
                        st.rerun()

            st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
            editable_keys = [k for k in data.keys() if not data[k].empty]

            # ---------------- Column Rename ----------------
            with st.expander("✏️ Rename Columns"):
                if not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    rn_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="rn_target")
                    rn_df = data[rn_target]
                    rn_col1, rn_col2 = st.columns(2)
                    with rn_col1:
                        rn_old = st.selectbox("Column to rename", rn_df.columns.tolist(), key="rn_old_col")
                    with rn_col2:
                        rn_new = st.text_input("New column name", value=rn_old, key="rn_new_name")
                    st.caption(f"e.g. Cust_ID → Customer ID — renamed columns update everywhere this dataset is used.")
                    if st.button("Apply Rename", key="rn_apply"):
                        if not (rn_new or "").strip() or rn_new == rn_old:
                            st.warning("Enter a different, non-empty column name.")
                        elif rn_new in rn_df.columns:
                            st.error(f"'{rn_new}' already exists in this dataset.")
                        else:
                            new_df = rename_columns(rn_df, {rn_old: rn_new})
                            platform_data = dict(data)
                            platform_data[rn_target] = new_df
                            save_platform_data(platform_data, dataset_meta={rn_target: {"uploaded_by": user["name"]}})
                            st.session_state["custom_data"] = platform_data
                            st.success(f"✅ Renamed '{rn_old}' → '{rn_new}' in {str(rn_target).capitalize()}.")
                            st.rerun()

            # ---------------- Data Type Manager ----------------
            with st.expander("🔧 Data Type Manager"):
                if not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    dt_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="dt_target")
                    dt_df = data[dt_target]
                    dt_col1, dt_col2 = st.columns(2)
                    with dt_col1:
                        dt_col = st.selectbox("Column", dt_df.columns.tolist(), key="dt_col_select")
                        st.caption(f"Current type: `{dt_df[dt_col].dtype}`")
                    with dt_col2:
                        dt_new_type = st.selectbox(
                            "Convert to", ["String", "Integer", "Float", "Boolean", "Date", "DateTime", "Category"],
                            key="dt_new_type",
                        )
                    if st.button("Apply Conversion", key="dt_apply"):
                        ok, new_df, msg = convert_column_dtype(dt_df, dt_col, dt_new_type)
                        if not ok:
                            st.error(f"❌ {msg}")
                        else:
                            platform_data = dict(data)
                            platform_data[dt_target] = new_df
                            save_platform_data(platform_data, dataset_meta={dt_target: {"uploaded_by": user["name"]}})
                            st.session_state["custom_data"] = platform_data
                            st.success(f"✅ {msg}")
                            st.rerun()

            # ---------------- Data Preview ----------------
            with st.expander("🔍 Data Preview"):
                if not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    pv_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="pv_target")
                    pv_df = data[pv_target]
                    preview = get_full_data_preview(pv_df)

                    pv1, pv2, pv3, pv4 = st.columns(4)
                    pv1.metric("Total Rows", f"{preview['total_rows']:,}")
                    pv2.metric("Total Columns", preview["total_columns"])
                    pv3.metric("Missing Values", f"{preview['missing_values']:,}")
                    pv4.metric("Duplicate Rows", f"{preview['duplicate_rows']:,}")
                    st.caption(f"Memory usage: {preview['memory_usage_mb']} MB")

                    st.markdown("**Column Summary**")
                    st.dataframe(preview["column_summary"], width="stretch", hide_index=True)

                    pv_search = st.text_input("Search within this dataset", key="pv_search", placeholder="Type to filter any column...")
                    st.markdown("**First 20 Rows**")
                    head_df = preview["head"]
                    if pv_search.strip():
                        mask = head_df.astype(str).apply(lambda col: col.str.contains(pv_search, case=False, na=False)).any(axis=1)
                        head_df = head_df[mask]
                    st.dataframe(head_df, width="stretch", hide_index=True)
                    st.markdown("**Last 20 Rows**")
                    st.dataframe(preview["tail"], width="stretch", hide_index=True)

            # ---------------- Add New Record ----------------
            with st.expander("➕ Add New Record"):
                if not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    ar_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="ar_target")
                    ar_df = data[ar_target]
                    st.caption("Fill in the fields below — required columns must be non-empty before saving.")
                    new_record = {}
                    n_cols = 3
                    cols_widgets = st.columns(n_cols)
                    for i, col in enumerate(ar_df.columns):
                        with cols_widgets[i % n_cols]:
                            new_record[col] = st.text_input(col, key=f"ar_field_{ar_target}_{col}")
                    if st.button("Save New Record", key="ar_save"):
                        missing = [c for c in ar_df.columns if not str(new_record.get(c, "")).strip()]
                        if missing:
                            st.error(f"Please fill in: {', '.join(missing)}")
                        else:
                            ok, new_df, msg = add_record(ar_df, new_record)
                            if ok:
                                platform_data = dict(data)
                                platform_data[ar_target] = new_df
                                save_platform_data(platform_data, dataset_meta={ar_target: {"uploaded_by": user["name"]}})
                                st.session_state["custom_data"] = platform_data
                                st.session_state.setdefault("session_added_ids", {}).setdefault(ar_target, []).append(
                                    new_record.get(ar_df.columns[0])
                                )
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)

            # ---------------- Delete Records ----------------
            with st.expander("🗑️ Delete Records"):
                if user["role"] == "Viewer":
                    st.caption("🔒 Viewers have read-only access and cannot delete records.")
                elif not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    del_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="del_target")
                    del_df = data[del_target]
                    id_col = del_df.columns[0]  # first column is the ID column by convention (CustomerID, OrderID, etc.)

                    if user["role"] == "Vendor":
                        allowed_ids = st.session_state.get("session_added_ids", {}).get(del_target, [])
                        st.caption(f"🔒 As a Vendor, you can only delete records you added this session "
                                   f"({len(allowed_ids)} eligible).")
                        id_options = allowed_ids
                    else:
                        st.caption(f"Deleting by '{id_col}'. Admin can delete any record.")
                        id_options = del_df[id_col].astype(str).tolist()

                    ids_to_delete = st.multiselect(f"Select {id_col}(s) to delete", id_options, key="del_ids")
                    if ids_to_delete:
                        st.warning(f"⚠️ You're about to permanently delete {len(ids_to_delete)} record(s). This cannot be undone.")
                        if st.button("Confirm Delete", key="del_confirm"):
                            ok, new_df, n_deleted, msg = delete_records(del_df, id_col, ids_to_delete)
                            if ok:
                                platform_data = dict(data)
                                platform_data[del_target] = new_df
                                save_platform_data(platform_data, dataset_meta={del_target: {"uploaded_by": user["name"]}})
                                st.session_state["custom_data"] = platform_data
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)

            # ---------------- Uploaded Dataset History ----------------
            with st.expander("🕐 Dataset History — switch versions without re-uploading"):
                if not editable_keys:
                    st.caption("No datasets loaded yet.")
                else:
                    hist_target = st.selectbox("Dataset", editable_keys, format_func=lambda k: k.capitalize(), key="hist_target")
                    history = get_dataset_history(hist_target)
                    current_meta = get_platform_metadata().get(hist_target, {})
                    current_uploaded_at = current_meta.get("uploaded_at", "")
                    if current_uploaded_at:
                        try:
                            current_uploaded_at = datetime.fromisoformat(current_uploaded_at).strftime("%d %b %Y, %I:%M %p")
                        except Exception:
                            pass
                    st.markdown(f"**🟢 Active version** — uploaded by {current_meta.get('uploaded_by', '—')} "
                                f"on {current_uploaded_at or '—'} ({current_meta.get('rows', 0):,} rows)")

                    if not history:
                        st.caption("No earlier versions yet — history builds up as this dataset gets replaced, renamed, or edited.")
                    else:
                        st.markdown("**Earlier versions:**")
                        for h in history:
                            uploaded_at = h.get("uploaded_at", "")
                            try:
                                uploaded_at = datetime.fromisoformat(uploaded_at).strftime("%d %b %Y, %I:%M %p")
                            except Exception:
                                pass
                            hcol1, hcol2 = st.columns([4, 1])
                            with hcol1:
                                st.caption(f"📄 Uploaded by **{h.get('uploaded_by', '—')}** on {uploaded_at} "
                                           f"— {h.get('rows', 0):,} rows, {h.get('columns', 0)} columns")
                            with hcol2:
                                if user["role"] == "Admin":
                                    if st.button("↩️ Restore", key=f"restore_{hist_target}_{h['version_file']}"):
                                        ok, msg = activate_history_version(hist_target, h["version_file"], uploaded_by=user["name"])
                                        if ok:
                                            st.session_state.pop("custom_data", None)
                                            st.success(f"✅ {msg}")
                                            st.rerun()
                                        else:
                                            st.error(msg)

            st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 Replace Platform Data", width="stretch", key="dm_refresh",
                             help="Takes you back to the upload screen so you can swap in a new dataset for everyone."):
                    st.session_state["force_upload_screen"] = True
                    st.session_state.pop("custom_data", None)
                    st.rerun()
            with col_b:
                if user["role"] == "Admin":
                    if st.button("🗑️ Delete All Uploaded Data (Admin)", width="stretch", key="dm_delete",
                                 help="Wipes the shared dataset for every user — cannot be undone."):
                        clear_platform_data()
                        for k in ["custom_data", "upload_reports", "unknown_files", "force_upload_screen"]:
                            st.session_state.pop(k, None)
                        st.rerun()
        else:
            st.caption("🔒 Only the Admin role can replace or delete platform data.")