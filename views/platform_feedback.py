"""Give Feedback - lets any signed-in user leave a star rating + written
review of the CustomerLens platform itself. Visible reviews surface as
testimonials on the public landing page; Admins can show/hide/delete any
of them from the Admin Panel."""
import streamlit as st
from datetime import datetime
from utils import ui, platform_feedback as pf

STAR_OPTIONS = ["★☆☆☆☆ (1)", "★★☆☆☆ (2)", "★★★☆☆ (3)", "★★★★☆ (4)", "★★★★★ (5)"]


def _stars(n):
    n = int(n)
    return "★" * n + "☆" * (5 - n)


@ui.safe_page
def render(data, user):
    ui.page_header("💬 Give Feedback", "HOME  ›  FEEDBACK")

    # Reset feedback textbox on the rerun after successful submission
    if "pf_clear" not in st.session_state:
        st.session_state["pf_clear"] = False

    if st.session_state["pf_clear"]:
        st.session_state["pf_text"] = ""
        st.session_state["pf_clear"] = False

    col1, col2 = st.columns([1.1, 1.4])

    with col1:
        ui.card_open("Share your experience")
        st.caption("Tell us what's working and what isn't — Admins review every submission, "
                   "and the best ones may be featured on the CustomerLens landing page.")
        rating_label = st.select_slider("Your rating", options=STAR_OPTIONS, value=STAR_OPTIONS[4],
                                         key="pf_rating")
        rating = STAR_OPTIONS.index(rating_label) + 1
        text = st.text_area("Your feedback", placeholder="What do you like? What could be better?",
                             height=130, key="pf_text")
        if st.button("Submit Feedback", key="pf_submit", width="stretch"):
            ok, msg = pf.add_feedback(user["id"], user["name"], user["role"], rating, text)
            if ok:
                st.success(f"✅ {msg}")
                st.session_state["pf_clear"] = True
                st.rerun()
            else:
                st.warning(msg)
        ui.card_close()

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        ui.card_open("Your past feedback")
        mine = pf.list_feedback(user_id=user["id"])
        if not mine:
            st.caption("You haven't submitted any feedback yet.")
        else:
            for row in mine:
                visible_tag = "🟢 Visible on landing page" if row["visible"] else "⚪ Hidden by admin"
                st.markdown(f"""
                <div class="fm-mini-item" style="flex-direction:column; align-items:flex-start; gap:4px;">
                    <div style="color:#f5a623; font-size:15px;">{_stars(row['rating'])}</div>
                    <div style="font-weight:500; color:#161029;">{row['text']}</div>
                    <div style="font-size:11px; color:#8a86a8;">{visible_tag}</div>
                </div>
                """, unsafe_allow_html=True)
        ui.card_close()

    with col2:
        ui.card_open("💭 What others are saying")
        others = [r for r in pf.list_feedback(visible_only=True) if r["user_id"] != user["id"]]
        if not others:
            st.caption("No public feedback yet — be the first!")
        else:
            for row in others[:12]:
                st.markdown(f"""
                <div class="fm-mini-item" style="flex-direction:column; align-items:flex-start; gap:5px;">
                    <div style="display:flex; justify-content:space-between; width:100%;">
                        <span style="font-weight:700; color:#161029;">{row['name']}</span>
                        <span style="color:#f5a623;">{_stars(row['rating'])}</span>
                    </div>
                    <div style="font-size:11px; color:#8a86a8;">{row['role']}</div>
                    <div style="font-weight:400; color:#4b4768;">{row['text']}</div>
                </div>
                """, unsafe_allow_html=True)
        ui.card_close()
