"""
Platform Feedback - star-rating + text testimonials that users of the
CustomerLens *platform itself* leave (not to be confused with feedback.csv,
which is mobile-store customers reviewing phones). Viewers, Analysts, and
Vendors can leave one; Admins can show/hide or delete any of them. Visible
ones surface as testimonials on the public landing page.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join("database", "platform_feedback.db")


def _connect():
    os.makedirs("database", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            role TEXT,
            rating INTEGER,
            text TEXT,
            visible INTEGER DEFAULT 1,
            created_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_feedback(user_id, name, role, rating, text):
    if not text or not text.strip():
        return False, "Please write a few words along with your rating."
    rating = max(1, min(5, int(rating)))
    init_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO platform_feedback (user_id, name, role, rating, text, visible, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (user_id, name, role, rating, text.strip(), datetime.now()))
    conn.commit()
    conn.close()
    return True, "Thanks for the feedback!"


def list_feedback(visible_only=False, user_id=None):
    init_db()
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT * FROM platform_feedback"
    conditions, params = [], []
    if visible_only:
        conditions.append("visible = 1")
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def set_visibility(feedback_id, visible: bool):
    init_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE platform_feedback SET visible = ? WHERE id = ?", (1 if visible else 0, feedback_id))
    conn.commit()
    conn.close()


def delete_feedback(feedback_id):
    init_db()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM platform_feedback WHERE id = ?", (feedback_id,))
    conn.commit()
    conn.close()


def seed_sample_feedback():
    """Populates a handful of realistic sample testimonials so the landing
    page and the moderation panel aren't empty on a fresh install. No-ops
    if feedback already exists."""
    init_db()
    if list_feedback():
        return
    samples = [
        (None, "Rohan Malhotra", "Vendor", 5,
         "The brand-wise dashboard makes it so easy to track how our Samsung listings are doing store by store. Cut our stock-out incidents in half."),
        (None, "Ayesha Khan", "Analyst", 5,
         "Uploading our own dataset and getting churn + segmentation back in seconds is a huge time-saver over what we used to do in spreadsheets."),
        (None, "Karan Mehta", "Vendor", 4,
         "Warranty claims tracking finally gives us visibility we never had before. Would love a mobile app version next!"),
        (None, "Priya Nair", "Viewer", 5,
         "Clean, fast, and the forecast numbers have been spot on for our festive season planning."),
        (None, "Sameer Bhatt", "Analyst", 4,
         "Great platform overall — the inventory heatmap is genuinely useful for spotting slow-moving stock across stores."),
    ]
    conn = _connect()
    cursor = conn.cursor()
    now = datetime.now()
    for user_id, name, role, rating, text in samples:
        cursor.execute("""
            INSERT INTO platform_feedback (user_id, name, role, rating, text, visible, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (user_id, name, role, rating, text, now))
    conn.commit()
    conn.close()
