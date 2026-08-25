"""
UI - theme CSS, expanded icon+label sidebar, functional top bar
(working search / notifications / help / profile), KPI cards.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

NAVY = "#161029"          # ink — headings, body text, dark accents
NAVY_LIGHT = "#241c3f"    # unused tint retained for compatibility
CORAL = "#6c5ce7"         # primary brand accent — electric violet
MINT = "#d8fff0"          # soft mint tint for secondary cards
TEAL = "#00c2d1"          # secondary brand accent — cyan
BG = "#f6f7fb"            # app background — light cool gray (not pure white,
                           # so white cards visibly lift off the page)
DANGER = "#ff5d73"        # alerts / negative deltas
POSITIVE = "#00c48c"      # positive deltas / success
SIDEBAR_BG = "#ffffff"
BORDER = "#e9e9f3"
MUTED = "#8a86a8"


CHART_COLORWAY = [CORAL, TEAL, "#a29bfe", POSITIVE, DANGER, "#ffb454", "#5b6ee1", "#ff8fc7"]


def register_chart_theme():
    """Registers a 'customerlens' Plotly template and makes it the default
    for every px.*/go.* chart in the app — transparent background (so charts
    sit flush inside the white card containers), Inter/Sora fonts, soft
    gray gridlines, a consistent colorway, and a dark rounded hover
    tooltip instead of Plotly's default white box. Safe to call every rerun;
    registering the same template name twice is a no-op overwrite.
    """
    pio.templates["customerlens"] = go.layout.Template(
        layout=go.Layout(
            font=dict(family="Inter, -apple-system, sans-serif", color=NAVY, size=12),
            title=dict(font=dict(family="Sora, sans-serif", size=15, color=NAVY)),
            colorway=CHART_COLORWAY,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#f0f0f6", zerolinecolor="#e4e4ef", linecolor="#e4e4ef",
                       showgrid=True, tickfont=dict(size=11, color=MUTED)),
            yaxis=dict(gridcolor="#f0f0f6", zerolinecolor="#e4e4ef", linecolor="#e4e4ef",
                       showgrid=True, tickfont=dict(size=11, color=MUTED)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                        font=dict(size=11, color=NAVY), bgcolor="rgba(0,0,0,0)"),
            hoverlabel=dict(bgcolor=NAVY, font_color="white",
                             font_family="Inter, sans-serif", font_size=12,
                             bordercolor=NAVY),
            margin=dict(l=8, r=8, t=28, b=8),
        )
    )
    pio.templates.default = "customerlens"


register_chart_theme()


def inject_base_css():
    _reset_card_state()
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, sans-serif !important;
        }}

        /* Hide the hamburger menu, footer, and Deploy/toolbar buttons.
           NOTE: we deliberately do NOT hide the whole `header` element —
           Streamlit itself toggles that element's inline style whenever the
           sidebar expands/collapses, which was overriding a `header
           {{visibility:hidden}}` rule and made the toolbar randomly
           reappear after the first interaction. Targeting the specific
           testids below is stable across reruns. */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        [data-testid="stToolbar"] {{visibility: hidden; height: 0; position: fixed;}}
        [data-testid="stDecoration"] {{display: none;}}
        [data-testid="stStatusWidget"] {{visibility: hidden;}}
        [data-testid="stHeader"] {{background: transparent;}}

        .stApp {{
            background: {BG};
        }}

        h1, h2, h3, .fm-page-title, .fm-card-title, .fm-sidebar-brand,
        .fm-kpi .value, .fm-logo {{
            font-family: 'Sora', 'Inter', sans-serif !important;
        }}

        /* ---------------- sidebar ---------------- */
        [data-testid="stSidebar"] {{
            background: {SIDEBAR_BG};
            border-right: 1px solid {BORDER};
            min-width: 250px !important;
            max-width: 250px !important;
            transition: min-width 0.18s ease, max-width 0.18s ease;
        }}

        /* The app owns the sidebar toggle. Never expose Streamlit's native
           collapse controls because they completely remove the sidebar. */
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) {{
            min-width: 96px !important;
            max-width: 96px !important;
        }}

        /* Kill Streamlit's built-in top spacer. This is the part that was
           creating the large blank area above our custom toggle. */
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebar"] [data-testid="stSidebarContent"],
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
            padding-top: 0 !important;
            margin-top: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
            /* Streamlit leaves a header-sized spacer above sidebar content.
               Pull the actual app-owned content up so the toggle starts near
               the top edge, like ChatGPT. */
            margin-top: -52px !important;
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 8px !important;
            padding-bottom: 12px !important;
        }}
        /* Recent Streamlit builds can leave an internal spacer/header above
           user content; pull the actual content to the very top. */
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] > div:first-child {{
            padding-top: 0 !important;
            margin-top: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div:first-child {{
            margin-top: 0 !important;
            padding-top: 0 !important;
        }}
        [data-testid="stSidebar"] .st-key-sidebar_toggle {{
            margin-top: 0 !important;
            padding-top: 0 !important;
            margin-bottom: 10px !important;
        }}

        [data-testid="stSidebar"] button {{
            background: transparent !important;
            border: none !important;
            color: #5c5876 !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
            width: 100% !important;
            height: 40px !important;
            border-radius: 10px !important;
            margin-bottom: 2px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0 10px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            transition: all 0.15s ease;
        }}
        [data-testid="stSidebar"] button p {{
            text-align: left !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            margin: 0 !important;
        }}
        [data-testid="stSidebar"] button:hover {{
            background: #f3f2fb !important;
            color: {NAVY} !important;
        }}

        /* ---------------- Custom collapse / expand toggle ----------------
           One definition only. It stays flush with the LEFT edge in both
           expanded and collapsed states. */
        [data-testid="stSidebar"] .st-key-sidebar_toggle {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            margin: 0 0 8px 0 !important;
            padding: 0 !important;
            position: relative !important;
            left: 0 !important;
            top: 0 !important;
            transform: none !important;
            z-index: 10 !important;
        }}

        [data-testid="stSidebar"] .st-key-sidebar_toggle button {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            min-height: 44px !important;
            max-height: 44px !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            border-radius: 10px !important;
            background: #f3f2fb !important;
            color: #161029 !important;
            box-shadow: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 22px !important;
            font-weight: 600 !important;
            line-height: 1 !important;
        }}

        [data-testid="stSidebar"] .st-key-sidebar_toggle button p {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            font-size: 22px !important;
            line-height: 1 !important;
        }}

        [data-testid="stSidebar"] .st-key-sidebar_toggle button:hover {{
            background: #ebe9fa !important;
            color: #6c5ce7 !important;
        }}

        /* Collapsed state: EXACT same position and size. */
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            margin: 0 0 8px 0 !important;
            padding: 0 !important;
            left: 0 !important;
            top: 0 !important;
            transform: none !important;
        }}

        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle button {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            min-height: 44px !important;
            max-height: 44px !important;
            margin: 0 !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}

        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle button p {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            font-size: 22px !important;
            line-height: 1 !important;
        }}

        .fm-sidebar-brand {{
            position: relative; display:flex; align-items:center; gap:10px; color:{NAVY};
            font-weight:800; font-size:16px; padding: 4px 8px 14px 8px;
            letter-spacing: 0.2px; border-bottom: 1px solid {BORDER}; margin-bottom: 8px;
            white-space: nowrap; overflow: visible;
        }}
        .fm-sidebar-brand .brand-icon {{
            background: linear-gradient(135deg, {CORAL}, {TEAL});
            width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
            display:flex; align-items:center; justify-content:center;
            font-size: 15px; box-shadow: 0 4px 10px rgba(108,92,231,0.35);
        }}
        .fm-sidebar-brand .brand-short {{ display:none; }}
        .fm-sidebar-brand .brand-name {{ display:inline; }}
        .fm-sidebar-section {{
            color:{MUTED}; font-size:10px; font-weight:700; letter-spacing:1.2px;
            padding: 12px 10px 4px 10px; text-transform:uppercase;
            white-space: nowrap;
        }}

        /* Collapsed rail */
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand {{
            justify-content: center; padding: 4px 0 12px 0; cursor: default;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand .brand-icon,
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand .brand-name,
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-section {{
            display: none !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand .brand-short {{
            display:flex !important; align-items:center; justify-content:center;
            width: 42px; height: 42px; border-radius: 12px;
            background: linear-gradient(135deg, {CORAL}, {TEAL});
            color: white; font-size: 15px; font-weight: 800; letter-spacing: .3px;
            box-shadow: 0 4px 10px rgba(108,92,231,0.28);
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand:hover::after {{
            content: "CustomerLens Platform";
            position: absolute; left: 62px; top: 50%; transform: translateY(-50%);
            z-index: 99999; white-space: nowrap;
            background: {NAVY}; color: #fff; padding: 8px 11px;
            border-radius: 8px; font-size: 12px; font-weight: 600;
            box-shadow: 0 6px 18px rgba(22,16,41,.18);
            pointer-events: none;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .fm-sidebar-brand .brand-short {{
            cursor: default;
        }}
        /* Collapsed mode: keep the toggle exactly the same size and
           flush-left position as the expanded state. */
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            margin: 0 0 8px 0 !important;
            padding: 0 !important;
            left: 0 !important;
            top: 0 !important;
            transform: none !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle button {{
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            max-width: 44px !important;
            min-height: 44px !important;
            max-height: 44px !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            border-radius: 10px !important;
            background: #f3f2fb !important;
            color: #161029 !important;
            box-shadow: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            font-size: 22px !important;
            line-height: 1 !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle button p {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            font-size: 22px !important;
            line-height: 1 !important;
            transform: none !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) .st-key-sidebar_toggle button:hover {{
            background: #ebe9fa !important;
            color: {CORAL} !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) [class*="st-key-nav_"] button {{
            width: 44px !important;
            height: 44px !important;
            min-height: 44px !important;
            padding: 0 !important;
            margin: 0 auto 4px auto !important;
            justify-content: center !important;
            text-align: center !important;
            font-size: 17px !important;
            line-height: 1.05 !important;
        }}

        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) [class*="st-key-nav_"] button p {{
            font-size: 15px !important;
            line-height: 1.05 !important;
            text-align: center !important;
            margin: 0 !important;
        }} 
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) [class*="st-key-nav_"] button {{
            overflow: visible !important;
            line-height: 1.05 !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) [class*="st-key-nav_"] button p {{
            overflow: visible !important;
            white-space: nowrap !important;
            text-overflow: clip !important;
        }}

        div[data-testid="stMainBlockContainer"] {{
            padding-top: 1.4rem;
            max-width: 100%;
        }}

        /* ---- Slim top strip: just search / notifications / help / profile;
           navigation lives in the sidebar now. ---- */
        div[class*="st-key-topbar"] {{
            background: transparent !important;
            padding: 0 0 12px 0 !important;
            margin-bottom: 4px !important;
        }}
        div[class*="st-key-topbar"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        div[class*="st-key-topbar"] .stTextInput input {{
            background: white !important;
            border: 1px solid {BORDER} !important;
            border-radius: 10px !important;
        }}
        div[class*="st-key-topbar"] button {{
            border-radius: 9px !important;
            border: 1px solid {BORDER} !important;
            background: white !important;
            white-space: nowrap !important;
        }}

        /* The pill: search / notifications / help / profile all sit inside
           one rounded capsule instead of four separate boxes floating next
           to each other — reads as a single, tidier control cluster. */
        div[class*="st-key-topbar_pill"] {{
            background: white !important;
            border: 1px solid {BORDER} !important;
            border-radius: 999px !important;
            padding: 5px 6px !important;
            box-shadow: 0 1px 3px rgba(22,16,41,0.05);
        }}
        div[class*="st-key-topbar_pill"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        div[class*="st-key-topbar_pill"] button {{
            border: none !important;
            background: transparent !important;
            border-radius: 999px !important;
            height: 34px !important;
        }}
        div[class*="st-key-topbar_pill"] button:hover {{
            background: {BG} !important;
        }}
        /* A thin divider between the 3 icon buttons and the profile chip,
           so the profile section still reads as visually distinct. */
        div[class*="st-key-topbar_pill"] [data-testid="stHorizontalBlock"] > div:nth-child(4) {{
            border-left: 1px solid {BORDER};
            padding-left: 4px;
            margin-left: 2px;
        }}

        .fm-logo {{
            display:flex; align-items:center; gap:10px; font-weight:800;
            font-size: 16px; color:{NAVY}; height:44px;
        }}
        .fm-logo-badge {{
            background: linear-gradient(135deg, {CORAL}, {TEAL});
            color:white; width:34px; height:34px; border-radius:10px;
            display:flex; align-items:center; justify-content:center; font-size:16px;
        }}
        .fm-avatar {{
            background: linear-gradient(135deg, {CORAL}, #a29bfe);
            width:34px; height:34px; border-radius:10px;
            display:flex; align-items:center; justify-content:center; color:white; font-weight:700;
            font-size:13px;
        }}
        .fm-profile-name {{ font-weight:700; color:{NAVY}; font-size:12.5px; line-height:1.2; }}
        .fm-profile-role {{ font-weight:400; color:{MUTED}; font-size:10.5px; }}

        .fm-page-header {{
            display:flex; justify-content: space-between; align-items:baseline;
            margin-bottom: 20px;
        }}
        .fm-page-title {{ font-size: 27px; font-weight:800; color:{NAVY}; margin:0; letter-spacing:-0.4px; }}
        .fm-breadcrumb {{ font-size: 11px; color: {MUTED}; font-weight:700; letter-spacing:0.8px;}}

        /* ---------------- KPI cards ---------------- */
        .fm-kpi {{
            background: white;
            border-radius: 14px;
            padding: 18px 20px;
            color: {NAVY};
            position: relative;
            min-height: 112px;
            border: 1px solid {BORDER};
            box-shadow: 0 1px 3px rgba(22,16,41,0.04);
            overflow: hidden;
        }}
        .fm-kpi .label {{ font-size:11px; color:{MUTED}; font-weight:600; letter-spacing:0.4px; text-transform:uppercase; max-width: 75%; }}
        .fm-kpi .value {{ font-size:26px; font-weight:800; margin-top:10px; color:{NAVY}; }}
        .fm-kpi .delta {{ font-size:12px; margin-top:6px; font-weight:600; }}
        .fm-kpi .delta.up {{ color:{POSITIVE}; }}
        .fm-kpi .delta.down {{ color:{DANGER}; }}
        .fm-kpi .icon-badge {{
            position:absolute; top:16px; right:16px; width:34px; height:34px; border-radius:10px;
            display:flex; align-items:center; justify-content:center; font-size:15px;
        }}

        /* Real, working card containers (st.container(key=...)-based). Unlike a
           raw '<div class="fm-card">' opened in one st.markdown() call and closed
           in another, Streamlit renders each markdown call as an isolated HTML
           fragment, so an unclosed div is auto-closed immediately by the browser —
           that produced the empty white pill artifacts. A keyed container is a
           single real DOM node that everything placed inside it actually nests in. */
        div[class*="st-key-fm_card_"] {{
            background: white;
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid {BORDER};
            box-shadow: 0 1px 3px rgba(22,16,41,0.04);
        }}
        div[class*="st-key-fm_card_"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        .fm-pill {{
            display:inline-block; padding:3px 11px; border-radius:8px;
            font-size:10.5px; font-weight:700; color:white; letter-spacing:0.3px;
            vertical-align:middle;
        }}
        .fm-chart-caption {{
            font-size:11px; color:{MUTED}; text-align:center;
            margin-top:2px; font-weight:600;
        }}
        .fm-card-mint {{
            background: {MINT};
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid #c5f5e3;
        }}
        .fm-card-title {{
            font-size: 12.5px; font-weight:700; letter-spacing:0.2px; color:{NAVY};
            margin-bottom:14px; padding-bottom: 12px; border-bottom: 1px solid {BORDER};
        }}
        .fm-mini-item {{
            display:flex; align-items:center; gap:12px; background:{BG};
            border-radius:12px; padding:12px 14px; margin-bottom:12px;
            font-weight:700; color:{NAVY}; font-size:13px;
            border: 1px solid {BORDER};
        }}
        .fm-mini-icon {{
            background: linear-gradient(135deg, {CORAL}, {TEAL});
            width:32px; height:32px; border-radius:9px; flex-shrink: 0;
            display:flex; align-items:center; justify-content:center; font-size:15px;
        }}

        div[class*="st-key-login_card"] {{
            background: white; border-radius: 20px; padding: 42px 44px;
            box-shadow: 0 14px 38px rgba(22,16,41,0.08); min-height: 520px;
            border: 1px solid {BORDER};
        }}
        div[class*="st-key-login_card"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        div[class*="st-key-login_brand"] {{
            background: linear-gradient(150deg, {NAVY} 0%, {NAVY_LIGHT} 55%, #2a2050 100%);
            border-radius: 20px; padding: 42px 40px; min-height: 520px;
            box-shadow: 0 14px 38px rgba(22,16,41,0.18); position: relative; overflow: hidden;
        }}
        div[class*="st-key-login_brand"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        div[class*="st-key-login_brand"]::before {{
            content: ""; position: absolute; top: -70px; right: -70px;
            width: 240px; height: 240px; border-radius: 50%; pointer-events: none;
            background: radial-gradient(circle, rgba(0,194,209,0.35), transparent 70%);
        }}
        div[class*="st-key-login_brand"]::after {{
            content: ""; position: absolute; bottom: -90px; left: -60px;
            width: 220px; height: 220px; border-radius: 50%; pointer-events: none;
            background: radial-gradient(circle, rgba(108,92,231,0.30), transparent 70%);
        }}

        /* Decorative marketing top-strip above the login card (logo, pill
           nav, CTA) — purely visual, meant to read like a real product
           landing page rather than a bare login form. */
        .fm-landing-pill {{
            display:inline-block; padding:6px 14px; border-radius:999px;
            background:white; border:1px solid {BORDER}; color:#4b4768;
            font-size:12.5px; font-weight:600;
        }}
        .fm-landing-cta {{
            display:inline-block; padding:8px 16px; border-radius:999px;
            background:linear-gradient(135deg, {CORAL}, #8b7cf0); color:white;
            font-size:12.5px; font-weight:700; box-shadow:0 4px 12px rgba(108,92,231,0.3);
        }}

        /* Public landing page — hero visual mockup, stat/feature/testimonial
           cards, and the closing CTA banner. */
        .fm-brand-chip {{
            display:inline-block; padding:5px 12px; border-radius:8px;
            background:{BG}; border:1px solid {BORDER}; color:#4b4768;
            font-size:11.5px; font-weight:700;
        }}
        .fm-brand-chip-dark {{
            display:inline-block; padding:5px 12px; border-radius:8px;
            background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.14);
            color:#e6e4f7; font-size:11.5px; font-weight:700;
        }}

        /* Dark hero banner wrapping the headline/CTA/mockup */
        div[class*="st-key-landing_hero"] {{
            background:linear-gradient(120deg, {NAVY} 0%, #2a2050 55%, #1b3a52 100%);
            border-radius:26px; padding:36px 40px; position:relative; overflow:hidden;
        }}
        div[class*="st-key-landing_hero"] [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        div[class*="st-key-landing_hero"]::before {{
            content:""; position:absolute; top:-80px; right:-60px; width:260px; height:260px;
            border-radius:50%; pointer-events:none;
            background:radial-gradient(circle, rgba(0,194,209,0.30), transparent 70%);
        }}
        div[class*="st-key-landing_hero"]::after {{
            content:""; position:absolute; bottom:-100px; left:10%; width:220px; height:220px;
            border-radius:50%; pointer-events:none;
            background:radial-gradient(circle, rgba(108,92,231,0.28), transparent 70%);
        }}
        div[class*="st-key-hero_cta_wrap"] button {{
            border:1px solid rgba(255,255,255,0.25) !important;
        }}
        div[class*="st-key-hero_cta_wrap"] [data-testid="column"]:first-child button {{
            background:linear-gradient(135deg, {CORAL}, #8b7cf0) !important; color:white !important; border:none !important;
        }}
        div[class*="st-key-hero_cta_wrap"] [data-testid="column"]:nth-child(2) button {{
            background:rgba(255,255,255,0.08) !important; color:white !important;
        }}

        .fm-hero-mock {{
            background:white; border-radius:18px; border:1px solid {BORDER};
            box-shadow:0 20px 50px rgba(22,16,41,0.12); overflow:hidden;
            transform: rotate(1.2deg);
        }}
        .fm-hero-mock-topbar {{
            background:{BG}; padding:11px 16px; display:flex; align-items:center;
            border-bottom:1px solid {BORDER};
        }}
        .fm-hero-mock-topbar span {{
            width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:5px;
        }}
        .fm-hero-mock-body {{ padding:20px; }}
        .fm-hero-kpi-row {{ display:flex; gap:12px; margin-bottom:16px; }}
        .fm-hero-kpi {{
            flex:1; background:linear-gradient(155deg, {NAVY} 0%, #201a3a 100%);
            border-radius:12px; padding:12px 14px; color:white;
        }}
        .fm-hero-kpi .l {{ font-size:9.5px; color:#a29cd6; font-weight:700; letter-spacing:0.4px; text-transform:uppercase; }}
        .fm-hero-kpi .v {{ font-size:17px; font-weight:800; margin-top:5px; }}
        .fm-hero-kpi .d {{ font-size:10.5px; color:{POSITIVE}; margin-top:3px; font-weight:700; }}
        .fm-hero-chart {{
            display:flex; align-items:flex-end; gap:6px; height:64px;
            background:{BG}; border-radius:10px; padding:10px 12px; margin-bottom:14px;
        }}
        .fm-hero-chart .bar {{ flex:1; border-radius:4px 4px 0 0; }}
        .fm-hero-mock-row {{
            display:flex; align-items:center; gap:8px; padding:8px 2px;
            border-bottom:1px solid {BG}; font-size:12px; font-weight:600; color:{NAVY};
        }}
        .fm-hero-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}

        .fm-stat-card {{
            text-align:center; background:white; border:1px solid {BORDER}; border-radius:14px;
            padding:22px 12px; box-shadow:0 1px 3px rgba(22,16,41,0.04); transition: transform 0.15s ease;
        }}
        .fm-stat-icon {{
            width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center;
            font-size:19px; margin:0 auto 12px auto;
        }}
        .fm-stat-value {{ font-size:26px; font-weight:800; color:{NAVY}; }}
        .fm-stat-label {{ font-size:11.5px; color:#8a86a8; margin-top:3px; }}

        .fm-feature-card {{
            background:white; border:1px solid {BORDER}; border-radius:16px; padding:24px 20px;
            box-shadow:0 1px 3px rgba(22,16,41,0.04); height:100%;
        }}
        .fm-feature-icon {{
            width:46px; height:46px; border-radius:13px; display:flex; align-items:center; justify-content:center;
            font-size:21px; margin-bottom:16px; box-shadow:0 6px 14px rgba(108,92,231,0.25);
        }}
        .fm-feature-title {{ font-size:14.5px; font-weight:800; color:{NAVY}; margin-bottom:8px; }}
        .fm-feature-desc {{ font-size:12px; color:#8a86a8; line-height:1.6; }}

        .fm-testimonial-card {{
            position:relative; background:white; border:1px solid {BORDER}; border-radius:16px;
            padding:24px 20px 20px 20px; box-shadow:0 1px 3px rgba(22,16,41,0.04); margin-bottom:18px;
        }}
        .fm-testimonial-quote {{
            position:absolute; top:8px; right:18px; font-size:52px; font-weight:900;
            color:{CORAL}; opacity:0.12; font-family:Georgia, serif; line-height:1;
        }}
        .fm-testimonial-avatar {{
            width:34px; height:34px; border-radius:10px; flex-shrink:0;
            background:linear-gradient(135deg, {CORAL}, #a29bfe); color:white;
            display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700;
        }}

        .fm-cta-banner {{
            background:linear-gradient(120deg, {NAVY} 0%, #2a2050 60%, #1b3a52 100%);
            border-radius:22px; padding:44px 20px 70px 20px; text-align:center; color:white;
            position:relative; overflow:hidden;
        }}
        div[class*="st-key-cta_button_wrap"] {{
            margin-top: -56px;
        }}
        div[class*="st-key-cta_button_wrap"] button {{
            background:white !important; color:{NAVY} !important; border:none !important;
            font-weight:800 !important; box-shadow:0 8px 20px rgba(0,0,0,0.25) !important;
        }}

        /* Small dot-network flourish in the brand panel — echoes the kind
           of data-viz graphic a real analytics product's marketing page
           would use, instead of a bare gradient. */
        .fm-dot-network {{
            position: relative; width: 100%; height: 92px; margin-top: 6px;
        }}
        .fm-dot-network span {{
            position: absolute; width: 7px; height: 7px; border-radius: 50%;
            box-shadow: 0 0 8px currentColor;
        }}
        div[class*="st-key-login_info"] button {{
            width: 34px !important; height: 34px !important; min-height: 34px !important;
            border-radius: 9px !important; padding: 0 !important;
            font-size: 15px !important; font-weight: 800 !important;
            background: {BG} !important; color: {NAVY} !important;
            border: 1px solid {BORDER} !important;
        }}
        div[class*="st-key-login_card"] .stTextInput input {{
            border-radius: 10px !important; border: 1.5px solid {BORDER} !important;
            padding: 10px 14px !important; font-size: 14px !important;
        }}
        div[class*="st-key-login_card"] .stTextInput input:focus {{
            border-color: {CORAL} !important;
            box-shadow: 0 0 0 3px rgba(108,92,231,0.15) !important;
        }}
        div[class*="st-key-login_card"] .stButton button {{
            background: linear-gradient(135deg, {CORAL}, #8b7cf0) !important; color: white !important; border: none !important;
            border-radius: 10px !important; font-weight: 700 !important; height: 46px !important;
            transition: all 0.15s ease;
        }}
        div[class*="st-key-login_card"] .stButton button:hover {{
            filter: brightness(1.08);
        }}
        div[class*="st-key-login_card"] button[data-baseweb="tab"] {{
            font-weight: 700 !important;
        }}

        .fm-notif-item {{
            padding: 8px 4px; border-bottom: 1px solid {BORDER}; font-size:13px; color:{NAVY};
        }}

        [data-testid="stMetricValue"] {{ color: {NAVY}; }}

        /* Buttons app-wide: squared-off tech feel instead of soft pill shapes */
        .stButton button, .stDownloadButton button {{
            border-radius: 10px !important;
        }}

        /* Dataframes / tables: soften the default grid to match the light card look */
        [data-testid="stDataFrame"] {{
            border: 1px solid {BORDER} !important;
            border-radius: 10px !important;
            overflow: hidden;
        }}

    </style>
    """, unsafe_allow_html=True)


def safe_page(render_fn):
    """
    Decorator for a page's render(data, user): if anything inside raises an
    unexpected exception, show a friendly message (with the real traceback
    in an expander) instead of crashing the whole app. Login/session state
    are untouched either way — the person can just pick a different
    selection or navigate elsewhere.
    """
    import functools

    @functools.wraps(render_fn)
    def wrapper(data, user):
        try:
            return render_fn(data, user)
        except Exception:
            import traceback
            st.error("⚠️ This page hit an unexpected error while rendering. Your login and data are fine — "
                      "try a different selection, or use the sidebar to go to another page and come back.")
            with st.expander("🐛 Technical details (for debugging)"):
                st.code(traceback.format_exc())
    return wrapper


def page_header(title, breadcrumb):
    st.markdown(f"""
    <div class="fm-page-header">
        <p class="fm-page-title">{title}</p>
        <p class="fm-breadcrumb">{breadcrumb}</p>
    </div>
    """, unsafe_allow_html=True)


def kpi_card(label, value, delta_text, icon, icon_bg, delta_up=True):
    delta_class = "up" if delta_up else "down"
    arrow = "▲" if delta_up else "▼"
    st.markdown(f"""
    <div class="fm-kpi">
        <div class="icon-badge" style="background:{icon_bg};">{icon}</div>
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="delta {delta_class}">{arrow} {delta_text}</div>
    </div>
    """, unsafe_allow_html=True)


# Module-level card stack/counter. Reset once per script run (see
# _reset_card_state, called from inject_base_css) so a stray exception on a
# previous run can never leave a stale, unclosed container hanging around.
_card_stack = []
_card_counter = {"n": 0}


def _reset_card_state():
    _card_stack.clear()
    _card_counter["n"] = 0


def card_open(title=None, accent=None):
    """Opens a REAL card container (backed by st.container(key=...)) so that
    anything rendered inside it — columns, charts, dataframes, widgets — is
    actually visually contained. Must be paired with a matching card_close().
    `accent`, if given, draws a colored left border (e.g. a priority color).
    """
    _card_counter["n"] += 1
    key = f"fm_card_{_card_counter['n']}"
    cm = st.container(key=key)
    cm.__enter__()
    _card_stack.append(cm)
    if accent:
        st.markdown(f"""
        <style>
            div[class*="st-key-{key}"] {{ border-left: 5px solid {accent} !important; }}
        </style>
        """, unsafe_allow_html=True)
    if title:
        st.markdown(f'<div class="fm-card-title">{title}</div>', unsafe_allow_html=True)
    return cm


def card_close():
    if _card_stack:
        _card_stack.pop().__exit__(None, None, None)


def pill(text, color):
    """Small colored rounded badge — used for segment/health/risk labels."""
    st.markdown(
        f'<span class="fm-pill" style="background:{color};">{text}</span>',
        unsafe_allow_html=True,
    )


def score_bar(label, score, color):
    """A labeled 0-100 progress bar (health score, churn risk, retention, etc.)."""
    st.markdown(f"""
    <div style="margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; font-size:12.5px; font-weight:700; color:{NAVY};">
            <span>{label}</span><span>{score:.0f}/100</span>
        </div>
        <div style="background:#e9ecf5; border-radius:8px; height:8px; margin-top:4px;">
            <div style="background:{color}; width:{max(0,min(100,score))}%; height:8px; border-radius:8px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def mini_item(icon, label, value=""):
    st.markdown(f"""
    <div class="fm-mini-item">
        <div class="fm-mini-icon">{icon}</div>
        <div>{label}{f'<br><span style="font-weight:400;color:#9a9dc2;">{value}</span>' if value else ''}</div>
    </div>
    """, unsafe_allow_html=True)



# =====================================================================
# TOP NAVBAR — single horizontal bar: logo, grouped nav pills (a popover
# for any group with more than one page), search/notifications/help/profile
# on the right. Replaces the old collapsible left sidebar entirely, which
# both matches the requested look and sidesteps the classic Streamlit bug
# where a hard-coded sidebar min-width fights the native collapse control
# and leaves the page in a broken half-collapsed state.
# =====================================================================
NAV_ITEMS = [
    ("dashboard", "🏠", "Home"),
    ("customers", "👥", "Customers"),
    ("customer360", "🪪", "Customer 360"),
    ("sales", "💰", "Sales"),
    ("products", "📦", "Products"),
    ("product_tiers", "🏆", "Top/Least Sellers"),
    ("product_comparison", "🧮", "Compare Products"),
    ("product360", "🔎", "Product 360"),
    ("inventory", "🏭", "Inventory"),
    ("warranty", "🛡️", "Warranty Claims"),
    ("marketing", "📣", "Marketing"),
    ("insights", "🎯", "Insights"),
    ("ai", "🤖", "AI Predictions"),
    ("forecast", "📈", "Forecast"),
    ("explorer", "🔎", "Data Explorer"),
    ("studio", "🧹", "Data Studio"),
    ("reports", "📄", "Reports"),
    ("feedback", "💬", "Give Feedback"),
]

ADMIN_NAV_ITEMS = NAV_ITEMS + [("vendor", "🏷️", "Vendor Management"),
                                 ("vendor360", "🏢", "Vendor 360"), ("admin", "⚙️", "Admin Panel")]

# A Vendor's own scoped navigation — every page here reads from data that's
# already been filtered down to their own Brand (see
# data_handler.scope_data_for_vendor), so "Sales" here really is "My Sales", etc.
VENDOR_NAV_ITEMS = [
    ("vendor", "🏬", "Vendor Dashboard"),
    ("vendor360", "🏢", "My Vendor 360"),
    ("products", "📦", "My Products"),
    ("product_tiers", "🏆", "My Top/Least Sellers"),
    ("product_comparison", "🧮", "Compare Products"),
    ("product360", "🔎", "Product 360"),
    ("inventory", "🏭", "My Inventory"),
    ("warranty", "🛡️", "Warranty Claims"),
    ("sales", "💰", "My Sales"),
    ("ai", "🤖", "Recommendations"),
    ("forecast", "📈", "Forecast"),
    ("reports", "📄", "Reports"),
    ("feedback", "💬", "Give Feedback"),
]

# Analyst: full analytics suite on their own uploaded dataset — everything
# an Admin/Viewer gets except Vendor Management, Admin Panel, and Data
# Studio (Studio's replace/delete actions target the *shared* platform
# dataset, which doesn't apply to an Analyst's isolated per-login upload).
ANALYST_NAV_ITEMS = [item for item in NAV_ITEMS if item[0] != "studio"] + [("vendor360", "🏢", "Vendor 360")]

ROLE_BADGE_COLORS = {
    "Admin": "#c1121f", "Vendor": "#00c2d1", "Analyst": "#5b6ee1", "Viewer": "#8b8fb3",
}

# Page keys grouped into a handful of top-level nav pills so ~20 pages still
# fit in one clean horizontal bar. A group with one available page renders
# as a plain pill button; a group with several renders as a popover menu.
_GROUP_DEFS = [
    ("Home", "🏠", ["dashboard"]),
    ("Customers", "👥", ["customers", "customer360"]),
    ("Sales", "💰", ["sales"]),
    ("Products", "📦", ["products", "product_tiers", "product_comparison", "product360"]),
    ("Inventory", "🏭", ["inventory", "warranty"]),
    ("Growth", "🎯", ["marketing", "insights", "ai", "forecast", "explorer", "studio"]),
    ("Vendors", "🏬", ["vendor", "vendor360"]),
    ("Reports", "📄", ["reports"]),
    ("Feedback", "💬", ["feedback"]),
    ("Admin", "⚙️", ["admin"]),
]


def _grouped_nav(items):
    available = {k: (icon, label) for k, icon, label in items}
    # Vendor role has no "dashboard" page — their "vendor" dashboard page
    # stands in as Home instead, so it isn't *also* duplicated in Vendors.
    home_keys = ["dashboard"] if "dashboard" in available else ["vendor"]
    group_defs = [(g[0], g[1], home_keys if g[0] == "Home" else g[2]) for g in _GROUP_DEFS]

    used, groups = set(), []
    for group_label, group_icon, keys in group_defs:
        sub = []
        for k in keys:
            if k in available and k not in used:
                icon, label = available[k]
                sub.append((k, icon, label))
                used.add(k)
        if sub:
            groups.append((group_label, group_icon, sub))
    return groups


def _build_notifications(data):
    notes = []
    if data:
        products = data.get("products", pd.DataFrame())
        if not products.empty:
            oos = products[products["Stock"] == 0]
            low = products[(products["Stock"] > 0) & (products["Stock"] < 20)]
            if len(oos):
                notes.append(f"🚫 {len(oos)} product(s) are out of stock")
            if len(low):
                notes.append(f"⚠️ {len(low)} product(s) are running low (<20 units)")
        feedback = data.get("feedback", pd.DataFrame())
        if not feedback.empty:
            neg = feedback[feedback["Rating"] <= 2]
            if len(neg):
                notes.append(f"💬 {len(neg)} negative reviews (rating ≤ 2) need attention")
    if not notes:
        notes.append("✅ No urgent alerts right now.")
    return notes


def sidebar_nav(current_page, is_admin=False, role=None):
    """Render a persistent ChatGPT-style sidebar.

    The sidebar is always present: expanded (~250px) or collapsed (~96px).
    Streamlit's native collapse control is hidden and replaced by our own
    session-state toggle.
    """
    if is_admin:
        items = ADMIN_NAV_ITEMS
    elif role == "Vendor":
        items = VENDOR_NAV_ITEMS
    elif role == "Analyst":
        items = ANALYST_NAV_ITEMS
    else:
        items = NAV_ITEMS

    groups = _grouped_nav(items)
    clicked = current_page

    if "sidebar_collapsed" not in st.session_state:
        st.session_state.sidebar_collapsed = False

    collapsed = bool(st.session_state.sidebar_collapsed)

    with st.sidebar:
        # Marker used by CSS :has() to switch the sidebar between 250px and 72px.
        state_class = "fm-sidebar-collapsed" if collapsed else "fm-sidebar-expanded"
        st.markdown(f'<div class="{state_class}" aria-hidden="true"></div>', unsafe_allow_html=True)

        with st.container(key="sidebar_toggle"):
            toggle_text = "›" if collapsed else "‹"
            if st.button(toggle_text, key="sidebar_toggle_btn"):
                st.session_state.sidebar_collapsed = not collapsed
                st.rerun()

        st.markdown(
            '<div class="fm-sidebar-brand" title="CustomerLens Platform"><span class="brand-icon">📱</span><span class="brand-short">CL</span><span class="brand-name">CustomerLens</span></div>',
            unsafe_allow_html=True,
        )

        for group_label, group_icon, sub in groups:
            if len(sub) > 1:
                st.markdown(
                    f'<div class="fm-sidebar-section">{group_icon} {group_label}</div>',
                    unsafe_allow_html=True,
                )

            for key, icon, label in sub:
                # In collapsed mode use ONLY the icon. CSS cannot reliably hide
                # part of a Streamlit button's text, so the label is never sent.
                button_text = icon if collapsed else f"{icon}  {label}"
                with st.container(key=f"nav_{key}"):
                    if st.button(button_text, key=f"btn_{key}", width="stretch", help=label if collapsed else None):
                        clicked = key

    # Highlight the current page.
    st.markdown(f"""
    <style>
        div[class*="st-key-nav_{current_page}"] button {{
            background: {CORAL}1a !important;
            color: {CORAL} !important;
            font-weight: 700 !important;
            border-left: 3px solid {CORAL} !important;
        }}
        [data-testid="stSidebar"]:has(.fm-sidebar-collapsed) div[class*="st-key-nav_{current_page}"] button {{
            border-left: none !important;
            box-shadow: inset 0 0 0 1px {CORAL}55 !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    return clicked


def topbar(user, data=None):
    """
    Renders the slim top strip in the main content area: breadcrumb space
    on the left (filled by page_header below it) is left alone — this bar
    only carries search / notifications / help / profile on the right,
    since navigation now lives in the sidebar.
    Returns {"navigate_to": str|None, "logout": bool, "reupload_own_data": bool}.
    """
    result = {"navigate_to": None, "logout": False, "reupload_own_data": False}
    role = user["role"]
    initials = "".join([p[0] for p in user["name"].split()][:2]).upper()
    role_color = ROLE_BADGE_COLORS.get(role, "#8b8fb3")

    with st.container(key="topbar"):
        col_spacer, col_pill = st.columns([6.2, 3.2])

        with col_pill:
            with st.container(key="topbar_pill"):
                col_search, col_notif, col_help, col_profile = st.columns([0.55, 0.55, 0.55, 2.35])

                with col_search:
                    with st.popover("🔍", width="content"):
                        st.markdown("**Search**")
                        query = st.text_input("Search", placeholder="Customers, products, orders...",
                                               key="global_search_input", label_visibility="collapsed")
                        if st.button("Search", key="global_search_btn", width="stretch"):
                            if query.strip():
                                st.session_state["explorer_search_query"] = query.strip()
                                result["navigate_to"] = "explorer"

                with col_notif:
                    with st.popover("🔔", width="content"):
                        st.markdown("**Notifications**")
                        for n in _build_notifications(data):
                            st.markdown(f'<div class="fm-notif-item">{n}</div>', unsafe_allow_html=True)

                with col_help:
                    with st.popover("❓", width="content"):
                        st.markdown("**Quick Help**")
                        st.markdown("""
                        - **Home** — company-wide KPIs & trends
                        - **Analytics** — segmentation, churn, recommendations, forecast, sentiment
                        - **Data Explorer** — browse, search & filter every dataset, download results
                        - **Data Studio** — upload a CSV, clean missing values/duplicates, download the cleaned file
                        - **Reports** — download full Excel / PDF / CSV reports
                        """)

                with col_profile:
                    with st.popover(f"{initials}  {user['name'].split()[0]} ▾", width="stretch"):
                        st.markdown(f"""
                        <div style="text-align:center;margin-bottom:10px;">
                            <div class="fm-avatar" style="margin:0 auto 8px auto;">{initials}</div>
                            <div class="fm-profile-name">{user['name']}</div>
                            <div class="fm-profile-role">{user['role']} · {user['department']}</div>
                            <div class="fm-profile-role">{user['email']}</div>
                            <span style="display:inline-block; margin-top:8px; background:{role_color}; color:white;
                                         font-size:10.5px; font-weight:800; padding:3px 11px; border-radius:20px;
                                         letter-spacing:0.3px;">{role.upper() if role else ''}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown("**Update Profile**")
                        from utils.auth import update_user
                        new_name = st.text_input("Name", value=user["name"], key="profile_name")
                        new_dept = st.text_input("Department", value=user["department"], key="profile_dept")
                        if st.button("Save Changes", key="profile_save", width="stretch"):
                            update_user(user["id"], name=new_name, department=new_dept)
                            st.session_state.user["name"] = new_name
                            st.session_state.user["department"] = new_dept
                            st.success("Profile updated.")
                            st.rerun()
                        st.markdown("---")
                        if role in ("Vendor", "Analyst"):
                            if st.button("📤 Re-upload My Dataset", key="profile_reupload", width="stretch"):
                                result["reupload_own_data"] = True
                            st.markdown("---")
                        if st.button("🚪 Logout", key="profile_logout", width="stretch"):
                            result["logout"] = True

    return result
