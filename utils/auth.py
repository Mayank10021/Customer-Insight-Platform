"""
Authentication Module - Login, Registration, Role & Session Management
"""
import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join("database", "users.db")

# Roles that must upload (and isolate) their own dataset every login —
# Admin and Viewer both use the shared platform dataset instead.
MANDATORY_UPLOAD_ROLES = {"Vendor", "Analyst"}

# Multiple demo Vendor logins across different brands, so different
# vendor scenarios can be tested side by side (all use password 'vendor123').
# (email, password, display name, role, department, vendor_brand)
DEMO_VENDOR_ACCOUNTS = [
    ("vendor.samsung@customerlens.com", "vendor123", "Samsung Vendor Partner", "Vendor", "Vendor Ops", "Samsung"),
    ("vendor.apple@customerlens.com", "vendor123", "Apple Vendor Partner", "Vendor", "Vendor Ops", "Apple"),
    ("vendor.xiaomi@customerlens.com", "vendor123", "Xiaomi Vendor Partner", "Vendor", "Vendor Ops", "Xiaomi"),
    ("vendor.oneplus@customerlens.com", "vendor123", "OnePlus Vendor Partner", "Vendor", "Vendor Ops", "OnePlus"),
    ("vendor.vivo@customerlens.com", "vendor123", "Vivo Vendor Partner", "Vendor", "Vendor Ops", "Vivo"),
]

DEMO_ANALYST_ACCOUNTS = [
    ("analyst@customerlens.com", "analyst123", "Senior Data Analyst", "Analyst", "Analytics", None),
    ("analyst.rina@customerlens.com", "analyst123", "Rina Kapoor (Analyst)", "Analyst", "Analytics", None),
]


def _connect():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_user_db():
    """Create tables and seed default accounts if empty."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            name TEXT,
            role TEXT,
            department TEXT,
            created_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            login_time TIMESTAMP,
            status TEXT
        )
    """)

    # Tombstone table: tracks emails that were permanently deleted by an
    # Admin, so the demo-account backfill below (and the empty-table reseed)
    # never resurrects them. Without this, deleting a demo Vendor/Analyst
    # account just came back on the next app load/login.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_accounts (
            email TEXT PRIMARY KEY,
            deleted_at TIMESTAMP
        )
    """)

    # Migration: older databases won't have this column yet. SQLite has no
    # "ADD COLUMN IF NOT EXISTS", so we probe and add it defensively.
    cursor.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "vendor_brand" not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN vendor_brand TEXT")

    # NOTE: earlier versions of this platform only had Admin/Vendor/Viewer
    # and auto-migrated any 'Analyst'/'Manager' row to 'Vendor'. Analyst is
    # now a real role again, so that migration no longer runs — any account
    # already migrated to Vendor stays Vendor (an Admin can change it back
    # via the Admin Panel if needed).

    cursor.execute("SELECT email FROM deleted_accounts")
    deleted_emails = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Four roles: Admin, Vendor, Analyst, Viewer. A Vendor account is
        # scoped to one Brand and must upload its own isolated dataset each
        # login (see utils/data_handler.py's per-user data store); an
        # Analyst does the same but isn't tied to any single brand.
        default_users = [
            ("admin@customerlens.com", "admin123", "Admin User", "Admin", "Management", None),
            ("viewer@customerlens.com", "viewer123", "Business Viewer", "Viewer", "Support", None),
        ] + DEMO_VENDOR_ACCOUNTS + DEMO_ANALYST_ACCOUNTS
        for email, pwd, name, role, dept, vendor_brand in default_users:
            if email in deleted_emails:
                continue
            pwd_hash = hash_password(pwd)
            cursor.execute("""
                INSERT INTO users (email, password, name, role, department, created_at, vendor_brand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email, pwd_hash, name, role, dept, datetime.now(), vendor_brand))
    else:
        # Existing database: add any demo accounts that aren't there yet,
        # without touching real accounts a user may have already created/edited.
        cursor.execute("SELECT email FROM users")
        existing_emails = {row[0] for row in cursor.fetchall()}
        for email, pwd, name, role, dept, vendor_brand in DEMO_VENDOR_ACCOUNTS + DEMO_ANALYST_ACCOUNTS:
            if email not in existing_emails and email not in deleted_emails:
                cursor.execute("""
                    INSERT INTO users (email, password, name, role, department, created_at, vendor_brand)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (email, hash_password(pwd), name, role, dept, datetime.now(), vendor_brand))

    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate_user(email, password):
    conn = _connect()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    cursor.execute("""
        SELECT id, email, name, role, department, vendor_brand FROM users
        WHERE email = ? AND password = ? AND is_active = 1
    """, (email, pwd_hash))
    result = cursor.fetchone()

    if result:
        conn.close()
        return {
            "id": result[0], "email": result[1], "name": result[2],
            "role": result[3], "department": result[4], "vendor_brand": result[5],
            "authenticated": True,
        }

    # Login failed with is_active=1 filter above — check separately whether
    # the email/password are actually correct but the account is deactivated,
    # so the person gets a clear reason instead of a generic "invalid" error.
    cursor.execute("""
        SELECT is_active FROM users WHERE email = ? AND password = ?
    """, (email, pwd_hash))
    row = cursor.fetchone()
    conn.close()
    if row is not None and row[0] == 0:
        return {"authenticated": False, "reason": "deactivated"}
    return {"authenticated": False, "reason": "invalid"}


def register_user(email, password, name, role="Viewer", department="General", vendor_brand=None):
    conn = _connect()
    cursor = conn.cursor()
    try:
        pwd_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (email, password, name, role, department, created_at, vendor_brand)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (email, pwd_hash, name, role, department, datetime.now(), vendor_brand))
        # If this email was previously deleted and someone is deliberately
        # signing up with it again, that's a fresh registration — clear the
        # tombstone so it doesn't get treated as "still deleted" anywhere.
        cursor.execute("DELETE FROM deleted_accounts WHERE email = ?", (email,))
        conn.commit()
        return True, "Registration successful!"
    except sqlite3.IntegrityError:
        return False, "Email already registered!"
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()


def log_user_activity(email, status="success"):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO login_history (email, login_time, status) VALUES (?, ?, ?)
    """, (email, datetime.now(), status))
    conn.commit()
    conn.close()


def get_login_history(limit=50):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, login_time, status FROM login_history
        ORDER BY login_time DESC LIMIT ?
    """, (limit,))
    results = cursor.fetchall()
    conn.close()
    return results


def get_all_users():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, email, name, role, department, created_at, is_active, vendor_brand
        FROM users ORDER BY created_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def update_user(user_id, **kwargs):
    allowed = ["name", "role", "department", "is_active", "vendor_brand"]
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    conn = _connect()
    cursor = conn.cursor()
    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    values = list(updates.values()) + [user_id]
    cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_user(user_id):
    """Soft delete — deactivates the account (used by the 'Deactivate' button).
    The user's row stays in the DB (login history, audit trail, etc. stay intact)
    but they can no longer log in."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_user_permanently(user_id):
    """Hard delete — permanently removes the user row from the database and
    records a tombstone so init_user_db()'s demo-account backfill (or the
    empty-table reseed) can never silently recreate this email again on the
    next app start/login. This cannot be undone (unlike delete_user/
    'Deactivate', which can be reversed by re-activating the account).
    Refuses to delete the last remaining Admin, so you can't lock yourself
    out of the Admin panel entirely."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT email, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return False, "User not found."
    email, role = row

    if role == "Admin":
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Admin'")
        if cursor.fetchone()[0] <= 1:
            conn.close()
            return False, "Can't delete the last remaining Admin account."

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    cursor.execute(
        "INSERT OR REPLACE INTO deleted_accounts (email, deleted_at) VALUES (?, ?)",
        (email, datetime.now()),
    )
    conn.commit()
    conn.close()
    return True, "User permanently deleted."
    conn.commit()
    conn.close()


init_user_db()
