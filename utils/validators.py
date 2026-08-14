"""
Data validation & intelligent dataset detection.

- detect_dataset_type(): looks at an uploaded file's columns and guesses
  which entity it represents (customers/orders/products/payments/feedback/
  returns/loyalty/employees/stores/inventory) using column-signature
  matching, so new files "just work" without any backend/code change.
- validate_dataset(): runs a battery of non-crashing checks (missing
  columns, duplicate IDs, duplicate rows, missing values, invalid dates,
  invalid emails/phones, wrong dtypes, negative sales, invalid order IDs)
  and returns a structured report instead of raising.
"""
import re
import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+]?[\d\s\-()]{7,15}$")

# Column signatures used for auto-detection. Order matters — first match
# above the threshold wins. Extend this dict to support new dataset types
# with zero other code changes (Returns, Loyalty, etc. are already here
# even though the bundled demo data doesn't include them yet).
DATASET_SIGNATURES = {
    "customers": {"id": "CustomerID", "columns": ["CustomerID", "Name", "Age", "Gender", "City", "State"]},
    "orders": {"id": "OrderID", "columns": ["OrderID", "CustomerID", "Date", "ProductID", "Quantity", "TotalAmount"]},
    "products": {"id": "ProductID", "columns": ["ProductID", "ProductName", "Category", "Price"]},
    "payments": {"id": "PaymentID", "columns": ["PaymentID", "OrderID", "CustomerID", "Amount", "Method"]},
    "feedback": {"id": "FeedbackID", "columns": ["FeedbackID", "CustomerID", "Rating", "Review"]},
    "returns": {"id": "ReturnID", "columns": ["ReturnID", "OrderID", "CustomerID", "Reason"]},
    "loyalty": {"id": "CustomerID", "columns": ["CustomerID", "LoyaltyPoints", "MembershipLevel"]},
    "employees": {"id": "EmployeeID", "columns": ["EmployeeID", "Name", "Role", "StoreID"]},
    "stores": {"id": "StoreID", "columns": ["StoreID", "StoreName", "City", "State"]},
    "inventory": {"id": "StockLevel", "columns": ["StoreID", "ProductID", "StockLevel"]},
    "warranty_claims": {"id": "ClaimID", "columns": ["ClaimID", "ProductID", "CustomerID", "Issue", "Status"]},
}

DATE_COLUMNS = {"Date", "SignupDate", "JoinDate", "OpeningDate", "ReturnDate", "PurchaseDate", "ClaimDate"}
MONEY_COLUMNS = {"TotalAmount", "Amount", "Price", "Cost", "Salary"}
ID_LIKE_COLUMNS = {"CustomerID", "OrderID", "ProductID", "PaymentID", "FeedbackID", "StoreID", "EmployeeID"}


def detect_dataset_type(df, min_match_ratio=0.5):
    """Guess which entity a raw uploaded DataFrame represents by comparing
    its columns against known signatures. Returns the type name (str) or
    'unknown' if nothing matches well enough."""
    cols = set(df.columns)
    best_type, best_score = "unknown", 0.0
    for dtype, sig in DATASET_SIGNATURES.items():
        sig_cols = set(sig["columns"])
        overlap = len(cols & sig_cols)
        score = overlap / len(sig_cols)
        # Require the primary ID column to be present for a confident match
        if sig["id"] not in cols:
            score *= 0.5
        if score > best_score:
            best_type, best_score = dtype, score
    return best_type if best_score >= min_match_ratio else "unknown"


def validate_dataset(df, dataset_type):
    """
    Runs a battery of data-quality checks and returns
    {"errors": [...], "warnings": [...], "info": [...]} — never raises,
    so a messy upload degrades gracefully instead of crashing the app.
    """
    report = {"errors": [], "warnings": [], "info": []}
    if df is None or df.empty:
        report["errors"].append("File is empty or could not be read.")
        return report

    sig = DATASET_SIGNATURES.get(dataset_type)

    # 1. Missing required columns
    if sig:
        missing_cols = [c for c in sig["columns"] if c not in df.columns]
        if missing_cols:
            report["warnings"].append(f"Missing expected column(s) for '{dataset_type}': {', '.join(missing_cols)}.")

    # 2. Duplicate primary IDs
    id_col = sig["id"] if sig else None
    if id_col and id_col in df.columns:
        dupe_count = int(df[id_col].duplicated().sum())
        if dupe_count:
            report["warnings"].append(f"{dupe_count} duplicate {id_col} value(s) found.")

    # 3. Duplicate rows
    dupe_rows = int(df.duplicated().sum())
    if dupe_rows:
        report["warnings"].append(f"{dupe_rows} fully duplicate row(s) found.")

    # 4. Missing values
    missing_total = int(df.isna().sum().sum())
    if missing_total:
        worst_cols = df.isna().sum()
        worst_cols = worst_cols[worst_cols > 0].sort_values(ascending=False).head(3)
        detail = ", ".join(f"{c} ({n})" for c, n in worst_cols.items())
        report["warnings"].append(f"{missing_total} missing value(s) overall — worst columns: {detail}.")

    # 5. Invalid dates
    for col in DATE_COLUMNS & set(df.columns):
        parsed = pd.to_datetime(df[col], errors="coerce")
        invalid = int(parsed.isna().sum() - df[col].isna().sum())
        if invalid > 0:
            report["warnings"].append(f"{invalid} unparseable date value(s) in '{col}'.")

    # 6. Invalid emails
    if "Email" in df.columns:
        non_null = df["Email"].dropna().astype(str)
        invalid = int((~non_null.str.match(EMAIL_RE)).sum())
        if invalid:
            report["warnings"].append(f"{invalid} invalid email address(es) found.")

    # 7. Invalid phone numbers
    if "Phone" in df.columns:
        non_null = df["Phone"].dropna().astype(str)
        invalid = int((~non_null.str.match(PHONE_RE)).sum())
        if invalid:
            report["warnings"].append(f"{invalid} invalid phone number(s) found.")

    # 8. Wrong data types on numeric-looking columns
    for col in MONEY_COLUMNS & set(df.columns):
        coerced = pd.to_numeric(df[col], errors="coerce")
        bad = int(coerced.isna().sum() - df[col].isna().sum())
        if bad > 0:
            report["warnings"].append(f"{bad} non-numeric value(s) found in '{col}'.")

    # 9. Negative sales / amounts
    for col in MONEY_COLUMNS & set(df.columns):
        coerced = pd.to_numeric(df[col], errors="coerce")
        neg = int((coerced < 0).sum())
        if neg:
            report["errors"].append(f"{neg} negative value(s) found in '{col}' — these rows need review.")

    # 10. Invalid / malformed order IDs (orders dataset only)
    if dataset_type == "orders" and "OrderID" in df.columns:
        malformed = int((~df["OrderID"].astype(str).str.match(r"^[A-Za-z0-9\-_]+$")).sum())
        if malformed:
            report["warnings"].append(f"{malformed} malformed OrderID value(s) found.")

    if not report["errors"] and not report["warnings"]:
        report["info"].append("No data quality issues detected.")

    return report
