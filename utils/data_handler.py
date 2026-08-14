"""
Enhanced Data Handler - Multi-file upload, merge, and data quality tracking
"""
import os
import json
import sqlite3
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st

DATA_DIR = "data"
UPLOAD_DIR = "uploads"
DB_PATH = os.path.join("database", "data.db")

CORE_FILES = {
    "customers": "customers.csv",
    "orders": "orders.csv",
    "products": "products.csv",
    "payments": "payments.csv",
    "feedback": "feedback.csv",
    "employees": "employees.csv",
    "stores": "stores.csv",
    "inventory": "inventory.csv",
    "warranty_claims": "warranty_claims.csv",
}


def ensure_directories():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs("database", exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs("exports", exist_ok=True)


def init_data_db():
    ensure_directories()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            upload_date TIMESTAMP,
            uploaded_by TEXT,
            row_count INTEGER,
            columns TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merged_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merge_name TEXT UNIQUE,
            created_date TIMESTAMP,
            source_files TEXT,
            row_count INTEGER,
            columns TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


def _optimize_dtypes(df):
    """
    Downcasts low-cardinality text columns (Category, Segment, Gender, City,
    State, Method, Role, etc.) to pandas 'category' dtype. This cuts memory
    use significantly and speeds up every groupby/value_counts/qcut call
    across the app (segmentation, dashboards, Action Center) since pandas
    can compare category codes instead of full strings.
    """
    if df.empty:
        return df
    for col in df.columns:
        if col.lower().endswith("id"):
            continue  # join keys stay as plain strings for safe, predictable merges
        # Version-agnostic string check: pandas < 3.0 uses 'object' dtype for
        # text columns, pandas >= 3.0 defaults to a new 'str' dtype instead.
        if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
            n_unique = df[col].nunique(dropna=True)
            if 0 < n_unique < max(len(df) * 0.5, 50):
                df[col] = df[col].astype("category")
    return df


def load_core_data():
    """Load all 8 CustomerLens core CSVs into a dict of DataFrames."""
    ensure_directories()
    result = {}
    for key, filename in CORE_FILES.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                if "SignupDate" in df.columns:
                    df["SignupDate"] = pd.to_datetime(df["SignupDate"], errors="coerce")
                result[key] = _optimize_dtypes(df)
            except Exception:
                result[key] = pd.DataFrame()
        else:
            result[key] = pd.DataFrame()
    return result


def add_data_quality_column(df):
    """Add a data quality indicator column showing missing data status"""
    missing_count = df.isna().sum(axis=1)
    df_copy = df.copy()
    
    def get_quality_status(count):
        if count == 0:
            return "✅ Complete"
        elif count <= 2:
            return "⚠️ Minor Issues"
        else:
            return "❌ Missing Data"
    
    df_copy["_Data_Quality"] = missing_count.apply(get_quality_status)
    return df_copy


@st.cache_data(show_spinner="🧮 Computing customer segments (RFM)...")
def get_cached_rfm11(merged):
    """
    Cached wrapper around ml_engine.segment_customers_rfm11(). At enterprise
    scale (100k+ customers) this computation takes real time — caching it
    means it only runs once per dataset instead of on every single rerun
    (which Streamlit triggers on every click/keystroke).
    """
    from utils import ml_engine
    return ml_engine.segment_customers_rfm11(merged)


@st.cache_data(show_spinner="🧮 Computing customer segments (Gold/Silver/Bronze)...")
def get_cached_segments(merged):
    """Cached wrapper around ml_engine.segment_customers() (3-tier KMeans)."""
    from utils import ml_engine
    return ml_engine.segment_customers(merged)


@st.cache_resource(show_spinner="🤖 Training churn prediction model...")
def get_cached_churn_model(merged):
    """
    Cached wrapper around ml_engine.train_churn_model(). Uses cache_resource
    (not cache_data) since the return value includes a fitted sklearn model.
    Shared across every page that needs churn predictions (Customer 360, AI
    Predictions, Action Center) so the model is trained only once per dataset.
    """
    from utils import ml_engine
    return ml_engine.train_churn_model(merged)


@st.cache_data(show_spinner="💬 Analyzing customer reviews...")
def get_cached_sentiment(feedback_df):
    """
    Cached wrapper around ml_engine.apply_sentiment_to_feedback(). Sentiment
    scoring (TextBlob) is genuinely slow per-row at real dataset sizes —
    tens of thousands of reviews can take a couple of minutes uncached.
    This was being run on the FULL feedback table on every single rerun
    of AI Predictions and Insights, which is what made those two pages
    feel stuck / like they weren't loading.
    """
    from utils import ml_engine
    return ml_engine.apply_sentiment_to_feedback(feedback_df)


@st.cache_data(show_spinner=False)
@st.cache_data(show_spinner="🧮 Computing Top/Low customer value tiers...")
def get_cached_value_tiers(merged, top_pct=0.2, low_pct=0.2):
    """
    Cached wrapper around ml_engine.classify_value_tiers(). Splits
    customers into Top / Mid / Low by spend and returns revenue-share
    stats — this is what powers the Top-vs-Low comparisons shown across
    Reports, Customer 360, Dashboard, and Business Insights.
    """
    from utils import ml_engine
    rfm11 = get_cached_rfm11(merged)
    if rfm11.empty:
        return rfm11, {}
    return ml_engine.classify_value_tiers(rfm11, top_pct=top_pct, low_pct=low_pct)


def scope_data_for_vendor(data, vendor_brand):
    """
    Filters the full platform dataset down to just one Vendor's own Brand —
    applied once, centrally, right after data is loaded and before any page
    routing happens. Because every existing view (Sales, Products, Inventory,
    Customer 360, Reports, AI Predictions, ...) simply reads whatever `data`
    dict it's handed, this one function is what makes "a Vendor can only see
    their own products / sales / inventory / customers" true everywhere,
    without editing every individual view.
    """
    if not vendor_brand:
        # No brand on file for this vendor account yet -> show nothing rather
        # than accidentally leaking every other vendor's data.
        return {k: pd.DataFrame() for k in data.keys()}

    scoped = dict(data)
    products = data.get("products", pd.DataFrame())
    if products.empty or "Brand" not in products.columns:
        return scoped

    products_v = products[products["Brand"] == vendor_brand].copy()
    scoped["products"] = products_v
    product_ids = set(products_v["ProductID"]) if "ProductID" in products_v.columns else set()

    orders = data.get("orders", pd.DataFrame())
    order_ids = set()
    customer_ids = set()
    if not orders.empty and "ProductID" in orders.columns:
        orders_v = orders[orders["ProductID"].isin(product_ids)].copy()
        scoped["orders"] = orders_v
        if "OrderID" in orders_v.columns:
            order_ids = set(orders_v["OrderID"])
        if "CustomerID" in orders_v.columns:
            customer_ids = set(orders_v["CustomerID"])
    else:
        scoped["orders"] = pd.DataFrame()

    feedback = data.get("feedback", pd.DataFrame())
    if not feedback.empty and "ProductID" in feedback.columns:
        scoped["feedback"] = feedback[feedback["ProductID"].isin(product_ids)].copy()

    payments = data.get("payments", pd.DataFrame())
    if not payments.empty and "OrderID" in payments.columns:
        scoped["payments"] = payments[payments["OrderID"].isin(order_ids)].copy()

    inventory = data.get("inventory", pd.DataFrame())
    if not inventory.empty and "ProductID" in inventory.columns:
        scoped["inventory"] = inventory[inventory["ProductID"].isin(product_ids)].copy()

    warranty_claims = data.get("warranty_claims", pd.DataFrame())
    if not warranty_claims.empty and "ProductID" in warranty_claims.columns:
        scoped["warranty_claims"] = warranty_claims[warranty_claims["ProductID"].isin(product_ids)].copy()

    customers = data.get("customers", pd.DataFrame())
    if not customers.empty and "CustomerID" in customers.columns:
        scoped["customers"] = customers[customers["CustomerID"].isin(customer_ids)].copy()

    return scoped


@st.cache_data(show_spinner="📦 Forecasting inventory demand (Random Forest)...")
def get_cached_inventory_forecast(merged, products, inventory, months_ahead=1):
    """Cached wrapper around ml_engine.forecast_inventory_demand()."""
    from utils import ml_engine
    return ml_engine.forecast_inventory_demand(merged, products, inventory, months_ahead=months_ahead)


@st.cache_data(show_spinner="🏷️ Ranking vendor performance...")
def get_cached_vendor_performance(merged, feedback):
    """Cached wrapper around vendor_store.compute_vendor_performance()."""
    from utils import vendor_store
    return vendor_store.compute_vendor_performance(merged, feedback)


def get_merged_orders(data):
    """Join orders + customers + products + stores into a single analysis-ready table.
    Cached: this gets called by nearly every page, and Streamlit reruns the
    whole script on every click/keystroke — without caching, a multi-way
    merge over a large orders table would redo the same join dozens of
    times per minute of normal use."""
    orders = data.get("orders", pd.DataFrame())
    customers = data.get("customers", pd.DataFrame())
    products = data.get("products", pd.DataFrame())
    stores = data.get("stores", pd.DataFrame())

    if orders.empty:
        return pd.DataFrame()

    df = orders.copy()
    if not customers.empty:
        df = df.merge(customers, on="CustomerID", how="left", suffixes=("", "_cust"))
    if not products.empty:
        df = df.merge(products, on="ProductID", how="left", suffixes=("", "_prod"))
    if not stores.empty:
        df = df.merge(stores, on="StoreID", how="left", suffixes=("", "_store"))
    return df


def merge_multiple_files(uploaded_files, merge_name, user_email):
    """
    Merge multiple uploaded CSV files with intelligent joining.
    Returns merged dataframe and metadata.
    """
    ensure_directories()
    init_data_db()
    
    try:
        dfs = []
        file_names = []
        
        for uploaded_file in uploaded_files:
            df = pd.read_csv(uploaded_file)
            dfs.append(df)
            file_names.append(uploaded_file.name)
        
        if not dfs:
            return False, {"error": "No files to merge"}

        # Start with first dataframe
        merged_df = dfs[0].copy()

        # Merge remaining dataframes. Instead of re-using the same fixed
        # suffixes on every round (which eventually collides once the
        # accumulated table already has an "_merged" column from an
        # earlier round — the exact bug that used to crash here), we pick
        # a sensible join key and then drop any overlapping columns from
        # the incoming file before merging, so there's never a name clash
        # to suffix in the first place.
        for df in dfs[1:]:
            common_cols = list(set(merged_df.columns) & set(df.columns))

            if common_cols:
                # Prefer an ID-like column as the join key over an
                # arbitrary shared column (e.g. "Date" or "Price")
                id_like = [c for c in common_cols if c.lower().endswith("id")]
                merge_key = id_like[0] if id_like else common_cols[0]

                # Guard against a many-to-many outer join silently
                # exploding into millions of rows (e.g. two large files
                # that both repeat the same key many times).
                left_dupe_factor = merged_df[merge_key].duplicated().sum()
                right_dupe_factor = df[merge_key].duplicated().sum()
                if left_dupe_factor > 0 and right_dupe_factor > 0:
                    est_rows = len(merged_df) * (right_dupe_factor + 1)
                    if est_rows > 5_000_000:
                        return False, {
                            "error": (
                                f"Merging on '{merge_key}' would explode into an estimated "
                                f"{est_rows:,}+ rows (both files repeat this key many times), "
                                f"which isn't a safe join. This tool is meant for simple "
                                f"two-or-three-file merges — for loading a full set of "
                                f"platform datasets (Customers, Orders, Products, etc.) use "
                                f"the main Upload screen or the Data Manager tab instead, "
                                f"which keeps each dataset separate rather than flattening "
                                f"everything into one giant table."
                            )
                        }

                # Drop columns from the incoming file that already exist
                # in the accumulated table (besides the join key itself) —
                # this is what actually prevents the suffix collision.
                cols_to_use = [merge_key] + [c for c in df.columns if c not in merged_df.columns]
                merged_df = merged_df.merge(df[cols_to_use], on=merge_key, how="outer")
            else:
                # If no common columns, concatenate horizontally
                merged_df = pd.concat([merged_df, df], axis=1)
        
        # Save merged dataset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"merged_{merge_name}_{timestamp}.csv"
        filepath = os.path.join(UPLOAD_DIR, filename)
        merged_df.to_csv(filepath, index=False)
        
        # Store in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO merged_datasets (merge_name, created_date, source_files, row_count, columns, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (merge_name, datetime.now(), ",".join(file_names), len(merged_df), 
              ",".join(merged_df.columns.tolist()), "Active"))
        conn.commit()
        conn.close()
        
        return True, {
            "filename": filename,
            "rows": len(merged_df),
            "columns": merged_df.columns.tolist(),
            "shape": merged_df.shape,
            "merge_name": merge_name,
            "source_files": file_names,
        }
    except Exception as e:
        return False, {"error": str(e)}


def save_uploaded_file(uploaded_file, user_email):
    """Save a user-uploaded CSV."""
    ensure_directories()
    init_data_db()
    try:
        df = pd.read_csv(uploaded_file)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = uploaded_file.name.replace(".csv", "")
        filename = f"{original_name}_{timestamp}.csv"
        filepath = os.path.join(UPLOAD_DIR, filename)
        df.to_csv(filepath, index=False)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO uploaded_files (filename, upload_date, uploaded_by, row_count, columns, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (filename, datetime.now(), user_email, len(df), ",".join(df.columns.tolist()), "Active"))
        conn.commit()
        conn.close()

        return True, {
            "filename": filename,
            "rows": len(df),
            "columns": df.columns.tolist(),
            "shape": df.shape,
        }
    except Exception as e:
        return False, {"error": str(e)}


def get_uploaded_files():
    ensure_directories()
    init_data_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, upload_date, uploaded_by, row_count, status
        FROM uploaded_files ORDER BY upload_date DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def get_merged_datasets():
    """Get all merged datasets"""
    ensure_directories()
    init_data_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, merge_name, created_date, source_files, row_count, status
        FROM merged_datasets ORDER BY created_date DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def delete_uploaded_file(file_id, filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM uploaded_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(path):
        os.remove(path)


def delete_merged_dataset(merge_id, filename):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM merged_datasets WHERE id = ?", (merge_id,))
    conn.commit()
    conn.close()
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(path):
        os.remove(path)


def overwrite_core_file(key, df):
    """Used by Admin panel to persist edits back to disk."""
    if key not in CORE_FILES:
        return False
    path = os.path.join(DATA_DIR, CORE_FILES[key])
    df.to_csv(path, index=False)
    return True


def generate_next_id(id_series, prefix="ID", digits=6):
    """
    Given an existing ID Series in a scheme like 'CUST000123', 'ORD0000456',
    or 'P0007', returns the next sequential ID in that same prefix +
    zero-padded-digit style (regardless of row order — takes the max, not
    the last row). Falls back to `{prefix}{1:0{digits}d}` if the series is
    empty/unusable. This is the shared building block behind every
    "add new ___" form in the app (Customer/Order/Product/Payment/Feedback),
    so ID generation only has to be gotten right once.
    """
    if id_series is not None and len(id_series) > 0:
        ids = id_series.dropna().astype(str)
        if len(ids) > 0:
            extracted = ids.str.extract(r"(\d+)\s*$")[0]
            numeric_part = pd.to_numeric(extracted, errors="coerce")
            max_num = numeric_part.max()
            if pd.notna(max_num):
                sample_id = ids.iloc[0]
                # Use the raw matched digit substring (not str(int(...)))
                # so leading zeros/width survive even if row 0 happens to
                # be a low number like "0001" — re-stringifying the int
                # would silently drop the padding and corrupt every ID
                # generated after it (e.g. 'P0001' -> 'P000601' instead
                # of the correct 'P0601').
                digit_str = extracted.iloc[0]
                if pd.notna(digit_str):
                    letters = sample_id[:len(sample_id) - len(digit_str)]
                    use_prefix = letters if letters else prefix
                    use_digits = len(digit_str)
                else:
                    use_prefix, use_digits = prefix, digits
                return f"{use_prefix}{int(max_num) + 1:0{use_digits}d}"
    return f"{prefix}{1:0{digits}d}"


def append_customer_record(customers_df, customer_data):
    """
    Appends one new customer to customers_df (does NOT write to disk — the
    caller persists via save_platform_data and updates session state).
    Auto-generates a CustomerID matching the existing scheme.

    If Email/Phone aren't yet real columns in the dataset, this
    permanently materializes them for EVERY existing customer first (using
    the same deterministic generator enrich_customers() already uses at
    render time) before adding the new customer's actually-entered values.
    Otherwise a fresh 'Email' column with only one real value would make
    enrich_customers() stop auto-generating it for the other rows, leaving
    them blank everywhere the column is read directly from disk.

    Returns (updated_df, new_customer_id).
    """
    df = customers_df.copy() if customers_df is not None else pd.DataFrame()
    if not df.empty:
        df = enrich_customers(df)

    id_series = df["CustomerID"] if "CustomerID" in df.columns else None
    new_id = generate_next_id(id_series, prefix="CUST", digits=6)

    row = dict(customer_data)
    row["CustomerID"] = new_id
    new_row_df = pd.DataFrame([row])

    updated = pd.concat([df, new_row_df], ignore_index=True) if not df.empty else new_row_df
    if "SignupDate" in updated.columns:
        updated["SignupDate"] = pd.to_datetime(updated["SignupDate"], errors="coerce")
    return updated, new_id


def append_product_record(products_df, product_data):
    """
    Appends one new product to products_df. Auto-generates a ProductID
    matching the existing 'P0001' style scheme. Any spec fields the caller
    leaves out (Cost, Rating, RAM_GB, etc.) get sensible defaults so
    downstream analytics never hit a NaN they don't expect.
    Returns (updated_df, new_product_id).
    """
    df = products_df.copy() if products_df is not None else pd.DataFrame()
    id_series = df["ProductID"] if "ProductID" in df.columns else None
    new_id = generate_next_id(id_series, prefix="P", digits=4)

    price = float(product_data.get("Price") or 0)
    defaults = {
        "Cost": round(price * 0.7, 2) if price else 0,
        "Stock": 0,
        "Rating": 4.0,
        "RAM_GB": None, "Storage_GB": None, "Battery_mAh": None,
        "CameraMP": None, "ScreenSize_in": None, "Processor": "",
        "Color": "", "Network": "4G", "WarrantyMonths": 12,
    }
    row = {**defaults, **product_data}
    row["ProductID"] = new_id
    new_row_df = pd.DataFrame([row])

    updated = pd.concat([df, new_row_df], ignore_index=True) if not df.empty else new_row_df
    return updated, new_id


def append_order_record(orders_df, payments_df, order_data):
    """
    Appends one new order (and its matching payment, since this dataset
    keeps a strict 1:1 Orders<->Payments split) to orders_df/payments_df.
    order_data expects: CustomerID, ProductID, Date, Quantity, Price
    (unit price), StoreID, OrderStatus, PaymentMethod.

    If 'OrderStatus' isn't yet a real column in orders_df, this backfills
    every existing order with 'Completed' first (same materialize-before-
    adding-a-real-value approach as Email/Phone on customers), so the
    column is fully populated instead of NaN for 250k historical rows.

    Returns (updated_orders_df, updated_payments_df, new_order_id).
    """
    orders = orders_df.copy() if orders_df is not None else pd.DataFrame()
    payments = payments_df.copy() if payments_df is not None else pd.DataFrame()

    if not orders.empty and "OrderStatus" not in orders.columns:
        orders["OrderStatus"] = "Completed"

    order_id = generate_next_id(orders["OrderID"] if "OrderID" in orders.columns else None,
                                 prefix="ORD", digits=7)
    payment_id = generate_next_id(payments["PaymentID"] if "PaymentID" in payments.columns else None,
                                   prefix="PAY", digits=7)

    qty = float(order_data.get("Quantity") or 1)
    unit_price = float(order_data.get("Price") or 0)
    total = order_data.get("TotalAmount")
    total = round(qty * unit_price, 2) if total in (None, "", 0) else round(float(total), 2)

    order_row = {
        "OrderID": order_id,
        "CustomerID": order_data.get("CustomerID"),
        "Date": order_data.get("Date"),
        "ProductID": order_data.get("ProductID"),
        "Quantity": qty,
        "Price": unit_price,
        "TotalAmount": total,
        "StoreID": order_data.get("StoreID"),
        "OrderStatus": order_data.get("OrderStatus", "Completed"),
    }
    new_order_df = pd.DataFrame([order_row])
    orders = pd.concat([orders, new_order_df], ignore_index=True) if not orders.empty else new_order_df
    if "Date" in orders.columns:
        orders["Date"] = pd.to_datetime(orders["Date"], errors="coerce")

    payment_row = {
        "PaymentID": payment_id,
        "OrderID": order_id,
        "CustomerID": order_data.get("CustomerID"),
        "Amount": total,
        "Method": order_data.get("PaymentMethod", "Cash"),
        "Date": order_data.get("Date"),
    }
    new_payment_df = pd.DataFrame([payment_row])
    payments = pd.concat([payments, new_payment_df], ignore_index=True) if not payments.empty else new_payment_df
    if "Date" in payments.columns:
        payments["Date"] = pd.to_datetime(payments["Date"], errors="coerce")

    return orders, payments, order_id


def append_feedback_record(feedback_df, feedback_data):
    """
    Appends one new feedback/review row. Auto-generates a FeedbackID
    matching the existing 'FB000001' style scheme.
    Returns (updated_df, new_feedback_id).
    """
    df = feedback_df.copy() if feedback_df is not None else pd.DataFrame()
    new_id = generate_next_id(df["FeedbackID"] if "FeedbackID" in df.columns else None,
                               prefix="FB", digits=6)
    row = dict(feedback_data)
    row["FeedbackID"] = new_id
    new_row_df = pd.DataFrame([row])
    updated = pd.concat([df, new_row_df], ignore_index=True) if not df.empty else new_row_df
    if "Date" in updated.columns:
        updated["Date"] = pd.to_datetime(updated["Date"], errors="coerce")
    return updated, new_id


@st.cache_data(show_spinner=False)
def enrich_customers(customers_df):
    """
    Adds Email and Phone columns if the uploaded/loaded customers dataset
    doesn't already have them, so Customer 360 search-by-email/phone always
    works. Deterministic (based on CustomerID/Name) so it's stable across
    reruns — this never overwrites real Email/Phone columns if present.
    """
    if customers_df.empty:
        return customers_df
    df = customers_df.copy()
    if "Email" not in df.columns:
        def _mk_email(row):
            base = str(row.get("Name", "customer")).lower().replace(" ", ".")
            base = "".join(ch for ch in base if ch.isalnum() or ch == ".")
            return f"{base}.{str(row.get('CustomerID', ''))[-4:].lower()}@mail.com"
        df["Email"] = df.apply(_mk_email, axis=1)
    if "Phone" not in df.columns:
        def _mk_phone(cid):
            digits = "".join(ch for ch in str(cid) if ch.isdigit()).rjust(9, "0")[-9:]
            return f"+91 9{digits}"
        df["Phone"] = df["CustomerID"].apply(_mk_phone)
    return df


def search_customers(data, query, limit=15):
    """Search customers by CustomerID, Name, Email, or Phone (case-insensitive,
    partial match). Returns a small DataFrame of matches for a picker UI."""
    customers = enrich_customers(data.get("customers", pd.DataFrame()))
    if customers.empty or not query or not query.strip():
        return pd.DataFrame()
    q = query.strip().lower()
    mask = (
        customers["CustomerID"].astype(str).str.lower().str.contains(q, na=False)
        | customers["Name"].astype(str).str.lower().str.contains(q, na=False)
        | customers["Email"].astype(str).str.lower().str.contains(q, na=False)
        | customers["Phone"].astype(str).str.lower().str.replace(" ", "").str.contains(q.replace(" ", ""), na=False)
    )
    return customers[mask].head(limit)


def get_important_customers(data, merged, filter_type="Top 50", limit=None):
    """
    Returns a DataFrame of only the "important" customers matching a
    business rule — Customer 360 is meant to focus on valuable customers,
    not browse every customer with equal weight. filter_type is one of:
    "VIP", "High Spending", "Frequent Buyers", "Repeat Customers",
    "Loyal Customers", "Recent Customers", "Top 10", "Top 50", "Top 100",
    "Highest CLV".
    """
    from utils import ml_engine

    if merged.empty:
        return pd.DataFrame()

    rfm11_tiered, _ = get_cached_value_tiers(merged)
    if rfm11_tiered.empty:
        return pd.DataFrame()

    customers = enrich_customers(data.get("customers", pd.DataFrame()))
    name_lookup = customers.set_index("CustomerID")["Name"] if "Name" in customers.columns else pd.Series(dtype=str)
    df = rfm11_tiered.copy()
    df["Name"] = df["CustomerID"].map(name_lookup).fillna("—")
    df["CLV"] = df.apply(lambda r: ml_engine.estimate_clv(r.to_dict()), axis=1)

    if filter_type == "VIP":
        df = df[(df["ValueTier"] == "Top") & (df["Segment"].isin(["Champions", "Loyal Customers", "Potential Loyalists"]))]
    elif filter_type == "High Spending":
        df = df[df["ValueTier"] == "Top"]
    elif filter_type == "Frequent Buyers":
        df = df[df["Frequency"] >= 8]
    elif filter_type == "Repeat Customers":
        df = df[df["Frequency"] >= 2]
    elif filter_type == "Loyal Customers":
        df = df[df["Segment"].isin(["Champions", "Loyal Customers", "Potential Loyalists"])]
    elif filter_type == "Recent Customers":
        df = df[df["Recency"] <= 30]
    elif filter_type == "Top 10":
        df = df.sort_values("Monetary", ascending=False).head(10)
    elif filter_type == "Top 50":
        df = df.sort_values("Monetary", ascending=False).head(50)
    elif filter_type == "Top 100":
        df = df.sort_values("Monetary", ascending=False).head(100)
    elif filter_type == "Highest CLV":
        df = df.sort_values("CLV", ascending=False)

    df = df.sort_values("Monetary", ascending=False)
    if limit:
        df = df.head(limit)
    return df


def rename_columns(df, rename_map):
    """Renames columns per {old_name: new_name}. Ignores unknown columns,
    never raises — returns the renamed DataFrame (a copy)."""
    valid_map = {k: v for k, v in rename_map.items() if k in df.columns and v and v != k}
    return df.rename(columns=valid_map)


def convert_column_dtype(df, column, target_type):
    """
    Attempts to convert `column` to `target_type` (one of: String, Integer,
    Float, Boolean, Date, DateTime, Category). Validates compatibility
    first and never raises — returns (success: bool, new_df_or_None,
    message: str) so the caller can show a clear error instead of crashing.
    """
    if column not in df.columns:
        return False, None, f"Column '{column}' not found."

    new_df = df.copy()
    series = new_df[column]

    try:
        if target_type == "String":
            new_df[column] = series.astype(str)
        elif target_type == "Integer":
            coerced = pd.to_numeric(series, errors="coerce")
            bad = int(coerced.isna().sum() - series.isna().sum())
            if bad > 0:
                return False, None, f"{bad} value(s) in '{column}' can't be converted to Integer (non-numeric)."
            new_df[column] = coerced.astype("Int64")
        elif target_type == "Float":
            coerced = pd.to_numeric(series, errors="coerce")
            bad = int(coerced.isna().sum() - series.isna().sum())
            if bad > 0:
                return False, None, f"{bad} value(s) in '{column}' can't be converted to Float (non-numeric)."
            new_df[column] = coerced.astype(float)
        elif target_type == "Boolean":
            truthy = {"true", "1", "yes", "y", "t"}
            falsy = {"false", "0", "no", "n", "f"}
            lowered = series.astype(str).str.strip().str.lower()
            unknown = ~lowered.isin(truthy | falsy | {"nan", "none", ""})
            bad = int(unknown.sum())
            if bad > 0:
                return False, None, f"{bad} value(s) in '{column}' aren't recognizable as True/False."
            new_df[column] = lowered.isin(truthy)
        elif target_type == "Date":
            coerced = pd.to_datetime(series, errors="coerce")
            bad = int(coerced.isna().sum() - series.isna().sum())
            if bad > 0:
                return False, None, f"{bad} value(s) in '{column}' aren't valid dates."
            new_df[column] = coerced.dt.date
        elif target_type == "DateTime":
            coerced = pd.to_datetime(series, errors="coerce")
            bad = int(coerced.isna().sum() - series.isna().sum())
            if bad > 0:
                return False, None, f"{bad} value(s) in '{column}' aren't valid datetimes."
            new_df[column] = coerced
        elif target_type == "Category":
            new_df[column] = series.astype("category")
        else:
            return False, None, f"Unknown target type '{target_type}'."
    except Exception as e:
        return False, None, f"Conversion failed: {e}"

    return True, new_df, f"'{column}' converted to {target_type}."


def get_full_data_preview(df):
    """
    Returns a dict with everything the Data Preview panel needs: first/last
    20 rows, row/column counts, missing values, duplicate rows, dtypes,
    memory usage, and a per-column summary (non-null count, unique count,
    sample value) — never raises on an empty/odd DataFrame.
    """
    if df.empty:
        return {
            "head": df, "tail": df, "total_rows": 0, "total_columns": 0,
            "missing_values": 0, "duplicate_rows": 0, "memory_usage_mb": 0.0,
            "dtypes": pd.DataFrame(), "column_summary": pd.DataFrame(),
        }

    dtypes_df = pd.DataFrame({"Column": df.columns, "Data Type": [str(t) for t in df.dtypes]})

    summary_rows = []
    for col in df.columns:
        summary_rows.append({
            "Column": col,
            "Non-Null Count": int(df[col].notna().sum()),
            "Unique Values": int(df[col].nunique(dropna=True)),
            "Sample Value": str(df[col].dropna().iloc[0]) if df[col].notna().any() else "",
        })

    return {
        "head": df.head(20), "tail": df.tail(20),
        "total_rows": len(df), "total_columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        "dtypes": dtypes_df, "column_summary": pd.DataFrame(summary_rows),
    }


def add_record(df, record: dict):
    """
    Appends a new row to df from a {column: value} dict. Any columns not
    provided are left as NaN. Returns (success, new_df_or_None, message).
    """
    try:
        new_row = {col: record.get(col) for col in df.columns}
        new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return True, new_df, "Record added."
    except Exception as e:
        return False, None, f"Couldn't add record: {e}"


def delete_records(df, id_column, ids_to_delete):
    """Removes rows where id_column is in ids_to_delete. Returns (success, new_df, n_deleted, message)."""
    if id_column not in df.columns:
        return False, df, 0, f"Column '{id_column}' not found."
    try:
        mask = df[id_column].astype(str).isin([str(i) for i in ids_to_delete])
        n_deleted = int(mask.sum())
        new_df = df[~mask].reset_index(drop=True)
        return True, new_df, n_deleted, f"{n_deleted} record(s) deleted."
    except Exception as e:
        return False, df, 0, f"Couldn't delete records: {e}"


def get_customer_profile(data, customer_id):
    """
    Builds the full Customer 360 profile dict for one CustomerID: identity,
    RFM/segment/health/churn scores, favorites, payment/feedback summary,
    and a recent-orders timeline. Pulls from ml_engine for the scoring so
    the same models power both the segmentation page and this profile.
    """
    from utils import ml_engine

    customers = enrich_customers(data.get("customers", pd.DataFrame()))
    if customers.empty or customer_id not in customers["CustomerID"].values:
        return None

    cust_row = customers[customers["CustomerID"] == customer_id].iloc[0].to_dict()
    merged = get_merged_orders(data)
    cust_orders = merged[merged["CustomerID"] == customer_id].copy() if not merged.empty else pd.DataFrame()

    profile = dict(cust_row)
    profile["TotalOrders"] = len(cust_orders)
    profile["TotalSpending"] = float(cust_orders["TotalAmount"].sum()) if not cust_orders.empty else 0.0
    profile["AvgOrderValue"] = float(cust_orders["TotalAmount"].mean()) if not cust_orders.empty else 0.0
    profile["AvgBasketSize"] = float(cust_orders["Quantity"].mean()) if not cust_orders.empty and "Quantity" in cust_orders else 0.0

    if not cust_orders.empty and "Category" in cust_orders.columns:
        cat_counts = cust_orders["Category"].value_counts()
        profile["FavoriteCategory"] = cat_counts.index[0] if len(cat_counts) else "N/A"
        profile["FavoriteCategories"] = cat_counts.head(3).index.tolist()
    else:
        profile["FavoriteCategory"] = "N/A"
        profile["FavoriteCategories"] = []

    if not cust_orders.empty and "ProductName" in cust_orders.columns:
        prod_counts = cust_orders["ProductName"].value_counts()
        profile["FavoriteProducts"] = prod_counts.head(5).index.tolist()
    else:
        profile["FavoriteProducts"] = []

    payments = data.get("payments", pd.DataFrame())
    if not payments.empty:
        cust_pay = payments[payments["CustomerID"] == customer_id]
        if not cust_pay.empty and "Method" in cust_pay.columns:
            profile["PreferredPaymentMethod"] = cust_pay["Method"].mode().iloc[0]
        else:
            profile["PreferredPaymentMethod"] = "N/A"
    else:
        profile["PreferredPaymentMethod"] = "N/A"

    if not cust_orders.empty and "Date" in cust_orders.columns:
        cust_orders = cust_orders.sort_values("Date")
        last_purchase = cust_orders["Date"].max()
        profile["LastPurchase"] = last_purchase
        profile["DaysSinceLastPurchase"] = (pd.Timestamp.now().normalize() - last_purchase).days
        profile["PreferredShoppingDay"] = cust_orders["Date"].dt.day_name().mode().iloc[0]
        span_days = max((cust_orders["Date"].max() - cust_orders["Date"].min()).days, 1)
        profile["PurchaseFrequency"] = round(len(cust_orders) / (span_days / 30), 2)  # orders/month
        profile["RecentOrders"] = cust_orders.tail(10).sort_values("Date", ascending=False)
    else:
        profile["LastPurchase"] = None
        profile["DaysSinceLastPurchase"] = None
        profile["PreferredShoppingDay"] = "N/A"
        profile["PurchaseFrequency"] = 0
        profile["RecentOrders"] = pd.DataFrame()

    feedback = data.get("feedback", pd.DataFrame())
    if not feedback.empty:
        cust_fb = feedback[feedback["CustomerID"] == customer_id]
        if not cust_fb.empty:
            cust_fb = ml_engine.apply_sentiment_to_feedback(cust_fb)
            profile["AvgRating"] = float(cust_fb["Rating"].mean())
            profile["FeedbackCount"] = len(cust_fb)
            top_sentiment = cust_fb["Sentiment"].mode().iloc[0] if "Sentiment" in cust_fb.columns else "Neutral"
            profile["SentimentSummary"] = top_sentiment.lower()
            profile["RecentFeedback"] = cust_fb.sort_values("Date", ascending=False).head(5)
        else:
            profile["AvgRating"] = None
            profile["FeedbackCount"] = 0
            profile["SentimentSummary"] = "no feedback yet"
            profile["RecentFeedback"] = pd.DataFrame()
    else:
        profile["AvgRating"] = None
        profile["FeedbackCount"] = 0
        profile["SentimentSummary"] = "no feedback yet"
        profile["RecentFeedback"] = pd.DataFrame()

    # RFM / segment / churn / CLV / health — reuse the shared, CACHED ML
    # engine so this doesn't retrain a model on every single search.
    rfm11 = get_cached_rfm11(merged) if not merged.empty else pd.DataFrame()
    rfm_row = rfm11[rfm11["CustomerID"] == customer_id] if not rfm11.empty else pd.DataFrame()
    if not rfm_row.empty:
        r = rfm_row.iloc[0]
        profile["Segment"] = r["Segment"]
        profile["RFM_Recency"] = int(r["Recency"])
        profile["RFM_Frequency"] = int(r["Frequency"])
        profile["RFM_Monetary"] = float(r["Monetary"])
        profile["CLV"] = ml_engine.estimate_clv(r.to_dict())

        churn_model, feat_cols = get_cached_churn_model(merged)
        profile["ChurnRisk"] = ml_engine.predict_churn(
            churn_model, feat_cols, r["Recency"], r["Frequency"], r["Monetary"]
        )
    else:
        profile["Segment"] = "New Customers"
        profile["RFM_Recency"] = profile.get("DaysSinceLastPurchase") or 0
        profile["RFM_Frequency"] = profile["TotalOrders"]
        profile["RFM_Monetary"] = profile["TotalSpending"]
        profile["CLV"] = 0
        profile["ChurnRisk"] = None

    profile["HealthScore"] = ml_engine.compute_health_score(
        recency_days=profile["RFM_Recency"] or 999,
        frequency=profile["RFM_Frequency"],
        monetary=profile["RFM_Monetary"],
        avg_rating=profile.get("AvgRating"),
        return_rate=0.0,
    )
    profile["RetentionScore"] = round(100 - (profile["ChurnRisk"] or 0), 1) if profile["ChurnRisk"] is not None else profile["HealthScore"]

    # Value tier (Top/Mid/Low by spend) + business-friendly classification —
    # this is what lets Customer 360 focus on "important" customers instead
    # of showing every customer with equal weight.
    if not merged.empty:
        rfm11_tiered, _ = get_cached_value_tiers(merged)
        tier_row = rfm11_tiered[rfm11_tiered["CustomerID"] == customer_id] if not rfm11_tiered.empty else pd.DataFrame()
        profile["ValueTier"] = tier_row.iloc[0]["ValueTier"] if not tier_row.empty else "Mid"
    else:
        profile["ValueTier"] = "Mid"

    tier_input = {
        "Segment": profile["Segment"], "Frequency": profile["RFM_Frequency"],
        "Recency": profile["RFM_Recency"], "Monetary": profile["RFM_Monetary"],
        "ValueTier": profile["ValueTier"],
    }
    profile["CustomerType"] = ml_engine.classify_customer_type(tier_input)
    profile["LoyaltyTier"] = ml_engine.loyalty_tier(tier_input)
    profile["IsVIP"] = ml_engine.is_vip(tier_input)

    profile["AISummary"] = ml_engine.generate_customer_ai_summary(profile)
    profile["AIRecommendations"] = ml_engine.generate_ai_recommendations(profile)
    return profile


PLATFORM_DATA_DIR = "platform_data"


USER_DATA_DIR = os.path.join("database", "user_data")


def _safe_user_key(user):
    """Turns a user's email into a filesystem-safe folder name."""
    import re
    email = (user.get("email") or f"user{user.get('id', 'unknown')}").lower()
    return re.sub(r"[^a-z0-9_.-]", "_", email)


def read_uploaded_file(f):
    """Reads an uploaded CSV or Excel file into a DataFrame (first sheet for Excel)."""
    name = f.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    return pd.read_csv(f)


def save_user_data(user, data, uploaded_by=None):
    """
    Persists one Vendor/Analyst's own uploaded dataset, fully isolated from
    both the shared platform dataset and every other user's own uploads.
    Overwrites whatever that user had before (no cross-session history —
    the whole point is they re-upload/re-confirm fresh each login).
    """
    key = _safe_user_key(user)
    folder = os.path.join(USER_DATA_DIR, key)
    os.makedirs(folder, exist_ok=True)

    for fname, df in data.items():
        path = os.path.join(folder, f"{fname}.csv")
        if df is not None and not df.empty:
            df.to_csv(path, index=False)
        elif os.path.exists(path):
            os.remove(path)

    meta = {
        "user_email": user.get("email"), "user_name": user.get("name"), "role": user.get("role"),
        "vendor_brand": user.get("vendor_brand"), "uploaded_by": uploaded_by or user.get("name"),
        "uploaded_at": datetime.now().isoformat(),
    }
    with open(os.path.join(folder, "_meta.json"), "w") as fp:
        json.dump(meta, fp)


def load_user_data(user):
    """Loads a Vendor/Analyst's own isolated dataset. Returns (data, meta) or (None, None)."""
    key = _safe_user_key(user)
    folder = os.path.join(USER_DATA_DIR, key)
    if not os.path.isdir(folder):
        return None, None

    data = {}
    for fname in os.listdir(folder):
        if not fname.endswith(".csv"):
            continue
        dtype = fname[:-4]
        try:
            df = pd.read_csv(os.path.join(folder, fname))
            for date_col in DATE_COLUMNS_TO_PARSE:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            data[dtype] = _optimize_dtypes(df)
        except Exception:
            data[dtype] = pd.DataFrame()

    for key_name in CORE_FILES.keys():
        data.setdefault(key_name, pd.DataFrame())

    meta = {}
    meta_path = os.path.join(folder, "_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as fp:
                meta = json.load(fp)
        except Exception:
            meta = {}
    return data, meta


def clear_user_data(user):
    key = _safe_user_key(user)
    folder = os.path.join(USER_DATA_DIR, key)
    if os.path.isdir(folder):
        import shutil
        try:
            shutil.rmtree(folder)
        except Exception:
            pass


def list_all_user_datasets():
    """
    Admin-facing: every Vendor/Analyst's isolated dataset, with metadata —
    the basis for "All Vendors / Combined Analytics" (Admin can see across
    isolated vendor uploads; vendors themselves never can).
    """
    if not os.path.isdir(USER_DATA_DIR):
        return []
    results = []
    for key in os.listdir(USER_DATA_DIR):
        meta_path = os.path.join(USER_DATA_DIR, key, "_meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path) as fp:
                meta = json.load(fp)
        except Exception:
            continue
        row_counts = {}
        for fname in os.listdir(os.path.join(USER_DATA_DIR, key)):
            if fname.endswith(".csv"):
                try:
                    row_counts[fname[:-4]] = sum(1 for _ in open(os.path.join(USER_DATA_DIR, key, fname))) - 1
                except Exception:
                    row_counts[fname[:-4]] = 0
        meta["_folder_key"] = key
        meta["_row_counts"] = row_counts
        results.append(meta)
    return sorted(results, key=lambda m: m.get("uploaded_at", ""), reverse=True)


def get_combined_vendor_data():
    """
    Concatenates every Vendor's isolated dataset into one dict, tagging each
    row with SourceVendor/SourceEmail — for Admin's "All Vendors / Combined
    Analytics" view. Analyst-role uploads are excluded (they're ad-hoc
    analysis datasets, not a vendor's actual business data).
    """
    datasets = [m for m in list_all_user_datasets() if m.get("role") == "Vendor"]
    if not datasets:
        return {k: pd.DataFrame() for k in CORE_FILES.keys()}

    combined = {k: [] for k in CORE_FILES.keys()}
    for meta in datasets:
        folder = os.path.join(USER_DATA_DIR, meta["_folder_key"])
        for key_name in CORE_FILES.keys():
            path = os.path.join(folder, f"{key_name}.csv")
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path)
                    df["SourceVendor"] = meta.get("vendor_brand") or meta.get("user_name")
                    combined[key_name].append(df)
                except Exception:
                    pass

    result = {}
    for key_name, frames in combined.items():
        result[key_name] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return result


def save_platform_data(data, uploaded_by=None, dataset_meta=None):
    """
    Persists the currently active dataset to disk so it is shared across
    every user session — not just the browser session that uploaded it.
    This is what makes "Analyst uploads → Viewer sees it" actually work.

    uploaded_by: name to stamp on every dataset touched by this save (used
    when a single user action replaces multiple datasets at once, e.g. the
    welcome-screen multi-upload).
    dataset_meta: optional {key: {"uploaded_by": ..., "uploaded_at": ...}}
    for per-dataset overrides (used when only one dataset changed, e.g. a
    single Data Manager replace) — existing metadata for untouched keys is
    preserved either way.
    """
    ensure_directories()
    os.makedirs(PLATFORM_DATA_DIR, exist_ok=True)

    meta_path = os.path.join(PLATFORM_DATA_DIR, "_metadata.json")
    existing_meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                existing_meta = json.load(f)
        except Exception:
            existing_meta = {}

    now_iso = datetime.now().isoformat()
    history_dir = os.path.join(PLATFORM_DATA_DIR, "history")
    history_index_path = os.path.join(PLATFORM_DATA_DIR, "_history_index.json")
    history_index = {}
    if os.path.exists(history_index_path):
        try:
            with open(history_index_path) as f:
                history_index = json.load(f)
        except Exception:
            history_index = {}

    for key, df in data.items():
        # Skip datasets that weren't actually touched by this save — without
        # this, renaming one column in Customers would also re-archive and
        # re-write Orders/Payments/etc. just because they were passed along
        # in the same dict. Only rewrite when this call explicitly flags the
        # key (single-dataset actions) or when dataset_meta is None entirely
        # (bulk saves like "Process & Analyze" / "Load Sample Data", where
        # everything is genuinely new).
        if dataset_meta is not None and key not in dataset_meta:
            continue

        path = os.path.join(PLATFORM_DATA_DIR, f"{key}.csv")

        # Archive whatever was previously live for this dataset before
        # overwriting it, so it can be switched back to later without
        # re-uploading (per "Uploaded Dataset History" requirement).
        if os.path.exists(path) and df is not None and not df.empty:
            os.makedirs(history_dir, exist_ok=True)
            old_meta = existing_meta.get(key, {})
            archive_name = f"{key}__{now_iso.replace(':', '-')}.csv"
            try:
                os.replace(path, os.path.join(history_dir, archive_name))
                history_index.setdefault(key, []).insert(0, {
                    "version_file": archive_name,
                    "uploaded_by": old_meta.get("uploaded_by", "Unknown"),
                    "uploaded_at": old_meta.get("uploaded_at", now_iso),
                    "archived_at": now_iso,
                    "rows": old_meta.get("rows", 0),
                    "columns": old_meta.get("columns", 0),
                })
                history_index[key] = history_index[key][:20]  # cap history depth
            except Exception:
                pass

        if df is not None and not df.empty:
            df.to_csv(path, index=False)
            file_size = os.path.getsize(path)
            override = (dataset_meta or {}).get(key, {})
            existing_meta[key] = {
                "uploaded_by": override.get("uploaded_by", uploaded_by or existing_meta.get(key, {}).get("uploaded_by", "Unknown")),
                "uploaded_at": override.get("uploaded_at", now_iso),
                "file_size": file_size,
                "rows": len(df),
                "columns": len(df.columns),
            }
        elif os.path.exists(path):
            os.remove(path)
            existing_meta.pop(key, None)

    with open(history_index_path, "w") as f:
        json.dump(history_index, f)
    with open(meta_path, "w") as f:
        json.dump(existing_meta, f)
    with open(os.path.join(PLATFORM_DATA_DIR, "_last_updated.txt"), "w") as f:
        f.write(now_iso)


def get_platform_metadata():
    """Returns {dataset_key: {uploaded_by, uploaded_at, file_size, rows, columns}}."""
    meta_path = os.path.join(PLATFORM_DATA_DIR, "_metadata.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path) as f:
            return json.load(f)
    except Exception:
        return {}


def get_dataset_history(key):
    """
    Returns the list of archived (previously-active) versions for one
    dataset type, most recent first — each with uploaded_by, uploaded_at,
    archived_at, rows, columns. This is what lets a user switch back to
    an earlier upload without re-uploading it.
    """
    history_index_path = os.path.join(PLATFORM_DATA_DIR, "_history_index.json")
    if not os.path.exists(history_index_path):
        return []
    try:
        with open(history_index_path) as f:
            index = json.load(f)
        return index.get(key, [])
    except Exception:
        return []


def activate_history_version(key, version_file, uploaded_by=None):
    """
    Restores an archived version as the current active dataset for `key`.
    The version that was active just before this call is itself archived
    first (via save_platform_data's normal history mechanism), so switching
    back and forth never loses data.
    Returns (success: bool, message: str).
    """
    history_dir = os.path.join(PLATFORM_DATA_DIR, "history")
    version_path = os.path.join(history_dir, version_file)
    if not os.path.exists(version_path):
        return False, "That version no longer exists."
    try:
        df = pd.read_csv(version_path)
        for date_col in DATE_COLUMNS_TO_PARSE:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = _optimize_dtypes(df)
    except Exception as e:
        return False, f"Couldn't load that version: {e}"

    current = load_platform_data() or {}
    current[key] = df
    save_platform_data(current, dataset_meta={key: {"uploaded_by": uploaded_by or "Unknown (restored)"}})
    return True, f"Restored {key} to the version from {version_file.split('__')[-1].replace('.csv', '')}."


def load_platform_data():
    """
    Loads whatever was last saved via save_platform_data(), for ANY user
    logging in. Returns None if nothing has ever been uploaded/persisted
    yet (so the welcome screen is only shown to the very first user).
    """
    if not os.path.isdir(PLATFORM_DATA_DIR):
        return None
    csv_files = [f for f in os.listdir(PLATFORM_DATA_DIR) if f.endswith(".csv")]
    if not csv_files:
        return None

    data = {}
    for fname in csv_files:
        key = fname[:-4]
        path = os.path.join(PLATFORM_DATA_DIR, fname)
        try:
            df = pd.read_csv(path)
            for date_col in DATE_COLUMNS_TO_PARSE:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            data[key] = _optimize_dtypes(df)
        except Exception:
            data[key] = pd.DataFrame()

    for key in CORE_FILES.keys():
        data.setdefault(key, pd.DataFrame())
    return data


def get_platform_data_updated_at():
    path = os.path.join(PLATFORM_DATA_DIR, "_last_updated.txt")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return datetime.fromisoformat(f.read().strip())
        except Exception:
            return None
    return None


def clear_platform_data():
    """Wipes the shared platform dataset (including version history) for every user (Admin-only action)."""
    if os.path.isdir(PLATFORM_DATA_DIR):
        import shutil
        try:
            shutil.rmtree(PLATFORM_DATA_DIR)
        except Exception:
            pass


DATE_COLUMNS_TO_PARSE = {"Date", "SignupDate", "JoinDate", "OpeningDate", "ReturnDate", "PurchaseDate", "ClaimDate"}


def process_uploaded_files(uploaded_files):
    """
    The heart of the upload-first flow: reads any number of CSVs, auto-
    detects each one's dataset type (customers/orders/products/payments/
    feedback/returns/loyalty/employees/stores/inventory) via intelligent
    column matching, validates each, and merges same-type files together.
    New/unrecognized files are kept under their own key instead of being
    dropped, so nothing is silently lost.

    Returns (data_dict, reports_dict, unknown_files):
        data_dict     -> same shape as load_core_data(), ready for every
                         existing view/module to consume unchanged.
        reports_dict  -> {dataset_type: {filename, rows, columns, report}}
        unknown_files -> list of filenames that couldn't be confidently typed
    """
    from utils.validators import detect_dataset_type, validate_dataset, DATASET_SIGNATURES

    buckets = {}       # dataset_type -> list of DataFrames
    reports = {}        # dataset_type -> list of per-file report dicts
    unknown_files = []

    for f in uploaded_files:
        try:
            df = read_uploaded_file(f)
        except Exception as e:
            unknown_files.append(f.name)
            reports.setdefault("unknown", []).append(
                {"filename": f.name, "rows": 0, "columns": 0,
                 "report": {"errors": [f"Could not read file: {e}"], "warnings": [], "info": []}}
            )
            continue

        dtype = detect_dataset_type(df)
        quality = validate_dataset(df, dtype)

        if dtype == "unknown":
            unknown_files.append(f.name)
            # Give each unrecognized file its own key (from its filename)
            # instead of merging every unrelated unknown file together —
            # so e.g. "returns.csv" and "loyalty_extra.csv" both stay
            # separately visible in Data Explorer instead of colliding.
            dtype = f.name.rsplit(".", 1)[0].lower().replace(" ", "_")

        buckets.setdefault(dtype, []).append(df)
        reports.setdefault(dtype, []).append({
            "filename": f.name, "rows": len(df), "columns": len(df.columns), "report": quality,
        })

    data = {}
    for dtype, frames in buckets.items():
        merged_df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        for date_col in DATE_COLUMNS_TO_PARSE:
            if date_col in merged_df.columns:
                merged_df[date_col] = pd.to_datetime(merged_df[date_col], errors="coerce")
        # De-duplicate on primary ID if we merged multiple files of the same type
        sig = DATASET_SIGNATURES.get(dtype)
        if len(frames) > 1 and sig and sig["id"] in merged_df.columns:
            merged_df = merged_df.drop_duplicates(subset=[sig["id"]], keep="last")
        data[dtype] = _optimize_dtypes(merged_df)

    # Ensure every key the rest of the app expects exists, even if empty,
    # so views written against load_core_data()'s shape don't KeyError.
    for key in CORE_FILES.keys():
        data.setdefault(key, pd.DataFrame())

    return data, reports, unknown_files


def auto_clean_datasets(data):
    """
    Lightweight, safe auto-clean for the mandatory upload workflow's
    'Clean Dataset' step: drops exact duplicate rows, fills missing numeric
    values with the column median, and fills missing text values with
    'Unknown'. Returns (cleaned_data, report) where report lists what
    changed per dataset, for the Data Quality Report to display.
    """
    cleaned = {}
    report = {}
    for key, df in data.items():
        if df is None or df.empty:
            cleaned[key] = df
            continue
        before_rows = len(df)
        d = df.drop_duplicates()
        dup_removed = before_rows - len(d)

        filled_numeric, filled_text = 0, 0
        for col in d.columns:
            if d[col].isna().any():
                if pd.api.types.is_numeric_dtype(d[col]):
                    filled_numeric += int(d[col].isna().sum())
                    d[col] = d[col].fillna(d[col].median())
                elif not pd.api.types.is_datetime64_any_dtype(d[col]):
                    filled_text += int(d[col].isna().sum())
                    d[col] = d[col].fillna("Unknown")

        cleaned[key] = d
        if dup_removed or filled_numeric or filled_text:
            report[key] = {
                "duplicate_rows_removed": dup_removed,
                "numeric_values_filled": filled_numeric,
                "text_values_filled": filled_text,
            }
    return cleaned, report


def get_data_quality_report(df):
    """Generate a data quality report for a dataframe"""
    report = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "total_cells": len(df) * len(df.columns),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "column_stats": []
    }
    
    for col in df.columns:
        missing = int(df[col].isna().sum())
        missing_pct = round((missing / len(df)) * 100, 2) if len(df) > 0 else 0
        report["column_stats"].append({
            "column": col,
            "dtype": str(df[col].dtype),
            "missing": missing,
            "missing_pct": missing_pct,
            "unique": int(df[col].nunique())
        })
    
    return report