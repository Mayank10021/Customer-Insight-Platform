"""Data Explorer - browse every dataset in full, with search, column filters,
and a download button for whatever the user is currently looking at."""
import streamlit as st
import pandas as pd
from utils import ui
from utils.data_handler import CORE_FILES


def _apply_search(df, query):
    if not query:
        return df
    query = query.lower()
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        try:
            mask = mask | df[col].astype(str).str.lower().str.contains(query, na=False)
        except Exception:
            continue
    return df[mask]


def render(data, user):
    ui.page_header("Data Explorer", "HOME &nbsp;›&nbsp; DATA EXPLORER")

    ui.card_open("Browse & Filter Any Dataset")

    # Known core datasets first, then any extra/custom ones the user has
    # uploaded that didn't match a known type — so nothing uploaded just
    # "disappears"; it's always browsable here under its own name.
    known_keys = [k for k in CORE_FILES.keys() if k in data]
    extra_keys = [k for k in data.keys() if k not in CORE_FILES]
    table_options = known_keys + extra_keys

    col1, col2 = st.columns([1, 2])
    with col1:
        table_choice = st.selectbox(
            "Select dataset", table_options, key="explorer_table",
            format_func=lambda k: f"{k.capitalize()} (custom)" if k in extra_keys else k.capitalize(),
        )

    df = data.get(table_choice, pd.DataFrame())

    with col2:
        pending_query = st.session_state.pop("explorer_search_query", None)
        if pending_query is not None:
            st.session_state["explorer_search_box"] = pending_query
        query = st.text_input(
            "Search across all columns",
            placeholder="e.g. a customer name, city, product, or ID",
            key="explorer_search_box",
        )

    if df.empty:
        st.info("No data in this table.")
        ui.card_close()
        return

    with st.expander("⚙️ Column Filters", expanded=False):
        filtered = df.copy()
        cols_to_filter = st.multiselect(
            "Add filters for specific columns", options=list(df.columns), key="explorer_filter_cols"
        )
        for col in cols_to_filter:
            if pd.api.types.is_numeric_dtype(df[col]):
                min_v, max_v = float(df[col].min()), float(df[col].max())
                if min_v == max_v:
                    st.caption(f"{col}: only one value ({min_v}) — no range to filter.")
                    continue
                lo, hi = st.slider(f"{col} range", min_v, max_v, (min_v, max_v), key=f"explorer_range_{col}")
                filtered = filtered[(filtered[col] >= lo) & (filtered[col] <= hi)]
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                min_d = df[col].min().date()
                max_d = df[col].max().date()

                date_range = st.date_input(
                    f"{col} range",
                    value=(min_d, max_d),
                    key=f"explorer_date_{col}",
                )

                if isinstance(date_range, tuple):
                    if len(date_range) == 2:
                        lo, hi = date_range
                    elif len(date_range) == 1:
                        lo = hi = date_range[0]
                    else:
                        lo, hi = min_d, max_d
                else:
                    lo = hi = date_range

                filtered = filtered[
                    (filtered[col] >= pd.Timestamp(lo))
                    & (filtered[col] <= pd.Timestamp(hi))
                ]
            else:
                options = sorted(df[col].dropna().astype(str).unique().tolist())
                chosen = st.multiselect(f"{col} values", options, key=f"explorer_cat_{col}")
                if chosen:
                    filtered = filtered[filtered[col].astype(str).isin(chosen)]

    result = _apply_search(filtered, query)

    st.markdown(f"**Showing {len(result):,} of {len(df):,} rows** in `{table_choice}`")
    st.dataframe(result, width="stretch", height=440)

    csv_bytes = result.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"⬇️ Download Filtered {table_choice}.csv", csv_bytes,
        file_name=f"{table_choice}_filtered.csv", mime="text/csv",
        width="stretch",
    )
    ui.card_close()
