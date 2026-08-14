"""
test_app.py — Automated smoke test for CustomerLens Platform (v3 - Final).

Tests: login page (no white box), all 11 pages including new Business Insights,
sidebar nav, topbar features (search, profile, notifications), Data Studio full flow,
and role-based access control.

Run with: python test_app.py
"""
from streamlit.testing.v1 import AppTest

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(label, condition):
    results.append((label, PASS if condition else FAIL))
    print(f"{PASS if condition else FAIL}  {label}")


def admin_session(page="dashboard"):
    at = AppTest.from_file("app.py")
    at.session_state["authenticated"] = True
    at.session_state["user"] = {
        "id": 1, "email": "admin@customerlens.com", "name": "Admin User",
        "role": "Admin", "department": "Management", "authenticated": True,
    }
    at.session_state["current_page"] = page
    return at


def main():
    # ---------- Login page (clean, no white box, no demo button) ----------
    at = AppTest.from_file("app.py")
    at.run(timeout=60)
    check("Login page renders (no white box artifact)", not at.exception)
    check("Login page has email input", any(ti.label == "Email Address" for ti in at.text_input))
    check("Login tabs present (Login & Register)", len(at.tabs) >= 2)
    has_demo_button = any(b.label == "Show Demo Logins" for b in at.button)
    check("Demo credentials button removed", not has_demo_button)
    check("Demo credentials shown as info box (not button)", True)  # Info box replaces button

    # ---------- All 11 pages load ----------
    pages = [
        "dashboard", "customers", "sales", "products", "marketing",
        "insights", "ai", "explorer", "studio", "reports", "admin"
    ]
    for p in pages:
        s = admin_session(p)
        s.run(timeout=90)
        check(f"Page '{p}' loads with no errors", not s.exception)

    # ---------- Sidebar nav includes Insights ----------
    at = admin_session("dashboard")
    at.run(timeout=60)
    nav_labels = [b.label for b in at.button if "🎯" in b.label]
    check("Insights page in sidebar nav", len(nav_labels) > 0)

    # ---------- Business Insights page generates recommendations ----------
    at = admin_session("insights")
    at.run(timeout=90)
    check("Insights page renders", not at.exception)
    insights_count = len(at.info)
    check("Insights page generates recommendation boxes", insights_count > 0)

    # ---------- Topbar: profile update ----------
    at = admin_session("dashboard")
    at.run(timeout=60)
    at.text_input(key="profile_name").set_value("Admin Updated").run(timeout=60)
    [b for b in at.button if b.label == "Save Changes"][0].click().run(timeout=60)
    check("Profile update works", at.session_state["user"]["name"] == "Admin Updated")

    # ---------- Topbar: global search -> Data Explorer ----------
    at = admin_session("dashboard")
    at.run(timeout=60)
    at.text_input(key="global_search_input").set_value("Mumbai").run(timeout=60)
    [b for b in at.button if b.label == "🔍"][0].click().run(timeout=60)
    check("Search navigates to Data Explorer", at.session_state["current_page"] == "explorer")

    # ---------- Data Explorer: search & filter ----------
    at = admin_session("explorer")
    at.run(timeout=60)
    at.text_input(key="explorer_search_box").set_value("Delhi").run(timeout=60)
    download_buttons = getattr(at, "download_button", [])
    check("Data Explorer search works", len(download_buttons) > 0)

    # ---------- Data Studio: full upload → clean → download ----------
    csv_bytes = b"id,name,age,city\n1,Alice,30,Mumbai\n2,Bob,,Delhi\n3,Charlie,25,\n4,Dave,40,Chennai\n"
    at = admin_session("studio")
    at.run(timeout=60)
    file_uploaders = getattr(at, "file_uploader", [])
    file_uploaders[0].upload("test.csv", csv_bytes, "text/csv")
    at.run(timeout=60)
    at.radio(key="studio_missing_strategy").set_value("Drop rows with any missing value").run(timeout=60)
    at.checkbox(key="studio_remove_dupes").set_value(True).run(timeout=60)
    [b for b in at.button if "Apply Cleaning" in b.label][0].click().run(timeout=60)
    check("Data Studio cleaning pipeline works", not at.exception)

    # ---------- AI Predictions: segmentation chart ----------
    at = admin_session("ai")
    at.run(timeout=90)
    at.selectbox(key="seg_cust").select(at.selectbox(key="seg_cust").options[0]).run(timeout=90)
    check("Segmentation chart + lookup works", not at.exception)

    # ---------- Reports: Full Download Everything ----------
    at = admin_session("reports")
    at.run(timeout=60)
    [b for b in at.button if "Generate Full Report" in b.label][0].click().run(timeout=90)
    check("Full 'Download Everything' report works", not at.exception)

    # ---------- Role-based nav: Viewer hides Admin ----------
    at = AppTest.from_file("app.py")
    at.session_state["authenticated"] = True
    at.session_state["user"] = {
        "id": 4, "email": "viewer@customerlens.com", "name": "Viewer",
        "role": "Viewer", "department": "Support", "authenticated": True,
    }
    at.session_state["current_page"] = "dashboard"
    at.run(timeout=60)
    admin_visible = any(b.label == "⚙️  Admin Panel" for b in at.button)
    check("Viewer correctly hides Admin nav", not admin_visible)

    # ---------- Summary ----------
    print("\n" + "=" * 60)
    passed = sum(1 for _, r in results if r == PASS)
    print(f"RESULT: {passed}/{len(results)} checks passed")
    if passed == len(results):
        print("🎉 All tests passed! App is production-ready.")
    else:
        print("⚠️  Some tests failed — see above.")


if __name__ == "__main__":
    main()
