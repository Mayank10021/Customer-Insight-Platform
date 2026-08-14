"""
Vendor Registry - lightweight vendor management on top of the existing
Product 'Brand' column.

CustomerLens's product data doesn't carry a dedicated VendorID — every
product already has a `Brand`, which is exactly what a "vendor" is in a
multi-brand retail dataset like this one. So a Vendor == a Brand, and
this module stores the *business* side of that relationship (contact
info, GST number, commission %, active/suspended status) in SQLite,
while sales/inventory/rating performance is always computed live from
the real Brand-grouped data — never hardcoded.
"""
import sqlite3
import os
from datetime import datetime
import pandas as pd

DB_PATH = os.path.join("database", "vendors.db")


def _connect():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_vendor_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            brand_name TEXT PRIMARY KEY,
            business_name TEXT,
            gst_number TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            address TEXT,
            commission_pct REAL DEFAULT 10.0,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    # Tombstone table: tracks brands an Admin deliberately deleted, so
    # ensure_vendor_seed() below never silently re-registers them just
    # because their products are still in the catalog.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_vendors (
            brand_name TEXT PRIMARY KEY,
            deleted_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def register_vendor(brand_name, business_name="", gst_number="", contact_email="",
                     contact_phone="", address="", commission_pct=10.0, status="Active"):
    if not brand_name or not brand_name.strip():
        return False, "Brand / Vendor name is required."
    init_vendor_db()
    conn = _connect()
    cursor = conn.cursor()
    now = datetime.now()
    try:
        cursor.execute("""
            INSERT INTO vendors (brand_name, business_name, gst_number, contact_email,
                                  contact_phone, address, commission_pct, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (brand_name.strip(), business_name, gst_number, contact_email, contact_phone,
              address, commission_pct, status, now, now))
        # A deliberate (re-)registration clears any earlier tombstone for
        # this brand, so it's treated as a genuinely new vendor going forward.
        cursor.execute("DELETE FROM deleted_vendors WHERE brand_name = ?", (brand_name.strip(),))
        conn.commit()
        return True, f"Vendor '{brand_name}' registered."
    except sqlite3.IntegrityError:
        return False, f"A vendor for brand '{brand_name}' already exists."
    finally:
        conn.close()


_DEMO_CITIES = [
    ("Mumbai", "Maharashtra", "27"), ("Delhi", "Delhi", "07"), ("Bengaluru", "Karnataka", "29"),
    ("Pune", "Maharashtra", "27"), ("Chennai", "Tamil Nadu", "33"), ("Hyderabad", "Telangana", "36"),
    ("Kolkata", "West Bengal", "19"), ("Ahmedabad", "Gujarat", "24"), ("Jaipur", "Rajasthan", "08"),
    ("Lucknow", "Uttar Pradesh", "09"), ("Chandigarh", "Chandigarh", "04"), ("Indore", "Madhya Pradesh", "23"),
]
_BUSINESS_SUFFIXES = ["Distributors Pvt Ltd", "Foods & Retail Pvt Ltd", "Trading Co.", "India Pvt Ltd", "Enterprises"]


def _demo_details_for_brand(brand_name):
    """
    Deterministically generates a realistic-looking (but clearly synthetic,
    for demo purposes) vendor profile from the brand name alone — same
    brand always yields the same details, so re-running the seed never
    scrambles data an Admin already looked at.
    """
    import hashlib
    h = int(hashlib.md5(brand_name.encode()).hexdigest(), 16)
    city, state, state_code = _DEMO_CITIES[h % len(_DEMO_CITIES)]
    suffix = _BUSINESS_SUFFIXES[h % len(_BUSINESS_SUFFIXES)]

    # GST-shaped identifier (state code + PAN-like block + entity + 'Z' + checksum).
    # This is a realistic-looking placeholder for demo data, NOT a real GSTIN.
    pan_letters = "".join(chr(65 + ((h >> (i * 5)) % 26)) for i in range(5))
    pan_digits = f"{(h % 9000) + 1000}"
    gst_number = f"{state_code}{pan_letters}{pan_digits}{chr(65 + (h % 26))}1Z{h % 10}"

    phone = f"+91 9{(h % 900000000) + 100000000}"
    slug = brand_name.lower().replace(" ", "").replace(".", "")
    email = f"partner@{slug}.com"
    business_name = f"{brand_name} {suffix}"
    address = f"{(h % 199) + 1}, {brand_name} Industrial Estate, {city}, {state} - {110000 + (h % 89999)}"
    commission = round(5 + (h % 11) + 0.5 * ((h // 11) % 2), 1)  # 5.0 – 15.5%

    return {
        "business_name": business_name, "gst_number": gst_number, "contact_email": email,
        "contact_phone": phone, "address": address, "commission_pct": commission,
    }


def ensure_vendor_seed(products_df):
    """
    For every Brand in the product catalog: registers it with a full,
    realistic demo profile if it has no vendor record yet, AND backfills
    any *existing* vendor record that's missing GST/email/phone/address/a
    real business name (covers vendors that were seeded before this
    richer generator existed) — so Vendor Management always shows
    complete profiles, not just bare brand names.
    """
    if products_df is None or products_df.empty or "Brand" not in products_df.columns:
        return
    init_vendor_db()
    existing = {v["brand_name"]: v for v in list_vendors_raw()}

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT brand_name FROM deleted_vendors")
    deleted_brands = {row[0] for row in cursor.fetchall()}
    conn.close()

    brands = sorted(b for b in products_df["Brand"].dropna().unique().tolist() if str(b).strip())

    for brand in brands:
        if brand in deleted_brands:
            continue
        details = _demo_details_for_brand(brand)
        if brand not in existing:
            register_vendor(brand, status="Active", **details)
        else:
            v = existing[brand]
            missing = {}
            if not v.get("gst_number"):
                missing["gst_number"] = details["gst_number"]
            if not v.get("contact_email"):
                missing["contact_email"] = details["contact_email"]
            if not v.get("contact_phone"):
                missing["contact_phone"] = details["contact_phone"]
            if not v.get("address"):
                missing["address"] = details["address"]
            if not v.get("business_name") or v.get("business_name") == brand:
                missing["business_name"] = details["business_name"]
            if missing:
                update_vendor(brand, **missing)


def list_vendors_raw():
    init_vendor_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT brand_name, business_name, gst_number, contact_email, contact_phone,
               address, commission_pct, status, created_at, updated_at
        FROM vendors ORDER BY brand_name
    """)
    cols = ["brand_name", "business_name", "gst_number", "contact_email", "contact_phone",
            "address", "commission_pct", "status", "created_at", "updated_at"]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_vendors_df():
    rows = list_vendors_raw()
    if not rows:
        return pd.DataFrame(columns=["brand_name", "business_name", "gst_number", "contact_email",
                                      "contact_phone", "address", "commission_pct", "status"])
    return pd.DataFrame(rows)


def get_vendor(brand_name):
    for v in list_vendors_raw():
        if v["brand_name"] == brand_name:
            return v
    return None


def update_vendor(brand_name, **kwargs):
    allowed = {"business_name", "gst_number", "contact_email", "contact_phone",
               "address", "commission_pct", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    init_vendor_db()
    conn = _connect()
    cursor = conn.cursor()
    updates["updated_at"] = datetime.now()
    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    values = list(updates.values()) + [brand_name]
    cursor.execute(f"UPDATE vendors SET {set_clause} WHERE brand_name = ?", values)
    conn.commit()
    conn.close()


def set_vendor_status(brand_name, status):
    """status: 'Active' or 'Suspended'"""
    update_vendor(brand_name, status=status)


def delete_vendor(brand_name):
    """Permanently remove a vendor's business record (contact info, GST,
    commission %, status) from the registry, and record a tombstone so
    ensure_vendor_seed() (called on every Vendor Management page load)
    never silently re-registers this brand again just because its products
    are still in the catalog. Does NOT delete their products or past
    orders — sales/inventory history stays intact for reporting, same as
    how removing an employee doesn't erase past payroll records."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vendors WHERE brand_name = ?", (brand_name,))
    cursor.execute(
        "INSERT OR REPLACE INTO deleted_vendors (brand_name, deleted_at) VALUES (?, ?)",
        (brand_name, datetime.now()),
    )
    conn.commit()
    conn.close()


# =====================================================================
# PERFORMANCE — always computed live from real order/product/feedback data
# =====================================================================

def compute_vendor_performance(merged_orders, feedback_df=None, months_for_growth=1):
    """
    Groups the merged orders table by Brand and returns a DataFrame with:
    Revenue, Orders, Units Sold, Avg Order Value, Avg Rating, Growth %
    (latest full month vs. the one before it), ranked by Revenue.
    """
    if merged_orders is None or merged_orders.empty or "Brand" not in merged_orders.columns:
        return pd.DataFrame()

    df = merged_orders.copy()
    if "Cost" in df.columns and "Price" in df.columns:
        df["_line_profit"] = (df["Price"] - df["Cost"]) * df["Quantity"]
    else:
        df["_line_profit"] = 0

    perf = df.groupby("Brand", observed=True).agg(
        Revenue=("TotalAmount", "sum"),
        Profit=("_line_profit", "sum"),
        Orders=("OrderID", "nunique"),
        UnitsSold=("Quantity", "sum"),
    ).reset_index()
    perf["AvgOrderValue"] = (perf["Revenue"] / perf["Orders"].replace(0, pd.NA)).fillna(0).round(2)
    total_revenue = perf["Revenue"].sum()
    perf["MarketSharePct"] = (perf["Revenue"] / total_revenue * 100).round(1) if total_revenue else 0.0

    # Average rating per brand, from feedback joined via ProductID -> Brand
    if feedback_df is not None and not feedback_df.empty and "ProductID" in feedback_df.columns:
        prod_brand = df[["ProductID", "Brand"]].drop_duplicates()
        fb = feedback_df.merge(prod_brand, on="ProductID", how="left")
        rating_by_brand = fb.groupby("Brand", observed=True)["Rating"].mean().round(2)
        rating_by_brand.index = rating_by_brand.index.astype(str)
        # NOTE: Brand is often a pandas 'category' dtype (memory optimization
        # elsewhere in the app) — .map() on a categorical column can produce
        # a categorical-dtype *result* too, which silently breaks any later
        # numeric op (.clip(), comparisons, arithmetic). Force plain float.
        perf["AvgRating"] = pd.to_numeric(perf["Brand"].astype(str).map(rating_by_brand), errors="coerce").fillna(0.0)
    else:
        perf["AvgRating"] = 0.0

    # Month-over-month growth %
    if "Date" in df.columns:
        d = df.copy()
        d["Month"] = pd.to_datetime(d["Date"], errors="coerce").dt.to_period("M")
        max_date = pd.to_datetime(d["Date"], errors="coerce").max()
        # If the most recent month in the data is only partially covered
        # (dataset just "ends" mid-month), comparing it to a full prior
        # month produces a misleadingly large negative growth number —
        # so drop that trailing partial month from the comparison.
        if pd.notna(max_date) and max_date.day < 25:
            d = d[d["Month"] != d["Month"].max()]
        monthly = d.groupby(["Brand", "Month"], observed=True)["TotalAmount"].sum().reset_index()
        growth_map = {}
        for brand, g in monthly.groupby("Brand", observed=True):
            brand = str(brand)
            g = g.sort_values("Month")
            if len(g) >= 2:
                prev, last = g["TotalAmount"].iloc[-2], g["TotalAmount"].iloc[-1]
                growth_map[brand] = round(((last - prev) / prev) * 100, 1) if prev else 0.0
            else:
                growth_map[brand] = 0.0
        # Force plain float dtype — see AvgRating comment above on why a
        # .map() result can silently come back as 'category' dtype here.
        perf["GrowthPct"] = pd.to_numeric(perf["Brand"].astype(str).map(growth_map), errors="coerce").fillna(0.0)
    else:
        perf["GrowthPct"] = 0.0

    perf = perf.sort_values("Revenue", ascending=False).reset_index(drop=True)
    perf.insert(0, "Rank", range(1, len(perf) + 1))
    perf = compute_vendor_score(perf)
    return perf


def compute_vendor_score(perf_df):
    """
    Composite 'Vendor Score' (0-100) for Vendor 360°: 40% revenue share
    (rank-based, not absolute — so it's comparable across datasets of very
    different sizes), 30% growth (-20%..+20% mapped to 0..30), 30% rating
    (0..5 mapped to 0..30). Transparent and re-derivable, not a black box.
    """
    if perf_df.empty:
        return perf_df
    df = perf_df.copy()
    max_rev = max(df["Revenue"].max(), 1e-9)
    revenue_score = (df["Revenue"] / max_rev) * 40
    growth_clipped = df["GrowthPct"].clip(-20, 20) if "GrowthPct" in df.columns else 0
    growth_score = ((growth_clipped + 20) / 40) * 30
    rating_score = (df["AvgRating"].fillna(0) / 5) * 30 if "AvgRating" in df.columns else 0
    df["VendorScore"] = (revenue_score + growth_score + rating_score).round(1)

    def _grade(score):
        if score >= 80:
            return "A — Excellent"
        elif score >= 60:
            return "B — Good"
        elif score >= 40:
            return "C — Average"
        return "D — Needs Attention"

    df["ScoreGrade"] = df["VendorScore"].apply(_grade)
    return df
