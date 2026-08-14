"""
📱 CustomerLens — Smart Retail Customer Insights & Sales Intelligence Platform
Enhanced version with improved login, role-based dashboards, and advanced features
"""
import streamlit as st
import pandas as pd

from utils import ui
from utils.auth import authenticate_user, register_user, log_user_activity, MANDATORY_UPLOAD_ROLES
from utils.data_handler import (
    load_core_data, process_uploaded_files,
    save_platform_data, load_platform_data, clear_platform_data, get_platform_data_updated_at,
    scope_data_for_vendor, save_user_data, load_user_data, clear_user_data,
    auto_clean_datasets, get_data_quality_report,
)
from views import (
    dashboard, customers, sales, products, marketing, ai_predictions,
    reports, admin, data_explorer, business_insights, customer_360,
    vendor, inventory, forecast, product_comparison, product_tiers,
    vendor_360, product_360, warranty, platform_feedback, add_data,
)

# Import enhanced versions
from views import data_studio

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="CustomerLens Platform",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject_base_css()

# =====================================================================
# DATA LOADING (cached)
# =====================================================================
@st.cache_data(show_spinner="📊 Loading CustomerLens datasets...")
def get_data():
    return load_core_data()


# =====================================================================
# SESSION STATE
# =====================================================================
def init_session():
    defaults = {
        "authenticated": False,
        "user": None,
        "current_page": "dashboard",
        "auth_screen": "landing",  # "landing" | "login"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()


# =====================================================================
# PUBLIC LANDING PAGE — shown before any login/register form. Purely
# informational + marketing: hero, live-feeling stats, and testimonials
# pulled from platform_feedback (Viewers/Analysts/Vendors can leave one
# from inside the app; Admins can show/hide/delete from the Admin Panel).
# =====================================================================
def _stars_html(n, size="14px", muted="#e2defa"):
    n = int(n)
    return (f'<span style="color:#f5a623; font-size:{size}; letter-spacing:1px;">'
            + ("★" * n) + f'<span style="color:{muted};">{"★" * (5 - n)}</span></span>')


def show_landing():
    from utils import platform_feedback as pf
    pf.seed_sample_feedback()
    testimonials = pf.list_feedback(visible_only=True)[:6]

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ---- Top nav ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        with st.container(key="landing_nav"):
            nc1, nc2, nc3 = st.columns([2.2, 3.6, 2.2])
            with nc1:
                st.markdown("""
                <div style="display:flex; align-items:center; gap:9px; font-weight:800; font-size:16px; color:#161029; height:38px;">
                    <span style="background:linear-gradient(135deg,#6c5ce7,#00c2d1); width:28px; height:28px; border-radius:9px;
                                 display:flex; align-items:center; justify-content:center; font-size:14px;
                                 box-shadow:0 4px 10px rgba(108,92,231,0.3);">📱</span>
                    CustomerLens
                </div>
                """, unsafe_allow_html=True)
            with nc2:
                st.markdown("""
                <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:center; align-items:center; height:38px;">
                    <span class="fm-landing-pill">Platform</span>
                    <span class="fm-landing-pill">Brands</span>
                    <span class="fm-landing-pill">Insights</span>
                    <span class="fm-landing-pill">Reports</span>
                </div>
                """, unsafe_allow_html=True)
            with nc3:
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("Login", key="landing_login_btn", width="stretch"):
                        st.session_state.auth_screen = "login"
                        st.rerun()
                with bcol2:
                    if st.button("Create Account", key="landing_signup_btn", width="stretch"):
                        st.session_state.auth_screen = "login"
                        st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ---- Hero: dark violet/cyan gradient banner (matches the reference
    # look) — headline/CTA on the left, a stylized live "dashboard preview"
    # card mockup on the right (pure CSS, no image assets). ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        with st.container(key="landing_hero"):
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            hero_l, hero_r = st.columns([1.15, 1], gap="large")
            with hero_l:
                st.markdown("""
                <div style="display:inline-block; padding:6px 16px; border-radius:999px; background:rgba(255,255,255,0.12);
                            color:#8ff0ff; font-size:12px; font-weight:700; letter-spacing:0.4px; margin-bottom:20px;
                            border:1px solid rgba(255,255,255,0.18);">
                    📱 RETAIL INTELLIGENCE PLATFORM
                </div>
                <h1 style="font-size:44px; font-weight:900; color:white; line-height:1.16; margin:0 0 20px 0;">
                    Make smarter<br>
                    <span style="background:linear-gradient(135deg,#8ff0ff,#a29bfe); -webkit-background-clip:text;
                                 -webkit-text-fill-color:transparent; background-clip:text;">mobile retail</span>
                    decisions.
                </h1>
                <p style="font-size:14.5px; color:#c7c3e6; line-height:1.7; margin:0 0 30px 0; max-width:460px;">
                    CustomerLens turns raw store, brand, and warranty data into a single live dashboard —
                    sales trends, stock health, churn risk, and demand forecasts, powered by AI, across
                    every phone brand you sell.
                </p>
                """, unsafe_allow_html=True)

                with st.container(key="hero_cta_wrap"):
                    cta1, cta2, cta_sp = st.columns([1.1, 1.1, 1.6])
                    with cta1:
                        if st.button("🚀 Get Started", key="hero_get_started", width="stretch"):
                            st.session_state.auth_screen = "login"
                            st.rerun()
                    with cta2:
                        if st.button("▶️ See a Demo", key="hero_demo", width="stretch"):
                            st.session_state.auth_screen = "login"
                            st.rerun()

                st.markdown("""
                <div style="margin-top:34px;">
                    <div style="font-size:10.5px; color:#8f8ab8; font-weight:700; letter-spacing:1px; margin-bottom:10px;">
                        TRUSTED ACROSS BRANDS
                    </div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <span class="fm-brand-chip-dark">Samsung</span>
                        <span class="fm-brand-chip-dark">Apple</span>
                        <span class="fm-brand-chip-dark">Xiaomi</span>
                        <span class="fm-brand-chip-dark">OnePlus</span>
                        <span class="fm-brand-chip-dark">Vivo</span>
                        <span class="fm-brand-chip-dark">+5 more</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with hero_r:
                st.markdown("""
                <div class="fm-hero-mock">
                    <div class="fm-hero-mock-topbar">
                        <span style="background:#ff5f57;"></span><span style="background:#febc2e;"></span><span style="background:#28c840;"></span>
                        <span style="margin-left:10px; font-size:11px; color:#a8a4c8; font-weight:600;"></span>
                    </div>
                    <div class="fm-hero-mock-body">
                        <div class="fm-hero-kpi-row">
                            <div class="fm-hero-kpi"><div class="l">Total Sales</div><div class="v">₹185.4L</div><div class="d">▲ 8.4%</div></div>
                            <div class="fm-hero-kpi"><div class="l">Orders</div><div class="v">2,50,000</div><div class="d">▲ 3.9%</div></div>
                        </div>
                        <div class="fm-hero-chart">
                            <div class="bar" style="height:38%; background:#6c5ce7;"></div>
                            <div class="bar" style="height:62%; background:#00c2d1;"></div>
                            <div class="bar" style="height:48%; background:#a29bfe;"></div>
                            <div class="bar" style="height:80%; background:#6c5ce7;"></div>
                            <div class="bar" style="height:55%; background:#00c2d1;"></div>
                            <div class="bar" style="height:70%; background:#00d68f;"></div>
                            <div class="bar" style="height:44%; background:#a29bfe;"></div>
                        </div>
                        <div class="fm-hero-mock-row">
                            <span class="fm-hero-dot" style="background:#6c5ce7;"></span> Samsung
                            <span style="flex:1;"></span>
                            <span style="color:#00d68f; font-weight:700;">▲ 12%</span>
                        </div>
                        <div class="fm-hero-mock-row">
                            <span class="fm-hero-dot" style="background:#00c2d1;"></span> Apple
                            <span style="flex:1;"></span>
                            <span style="color:#00d68f; font-weight:700;">▲ 9%</span>
                        </div>
                        <div class="fm-hero-mock-row">
                            <span class="fm-hero-dot" style="background:#ff8fc7;"></span> Xiaomi
                            <span style="flex:1;"></span>
                            <span style="color:#ff5d73; font-weight:700;">▼ 2%</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)


    # ---- Stats strip ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        s1, s2, s3, s4 = st.columns(4)
        stats = [("🏬", "60", "Stores tracked live", "#6c5ce7"), ("📱", "10", "Mobile brands", "#00c2d1"),
                 ("🤖", "5+", "ML models built-in", "#00d68f"), ("🛡️", "24/7", "Warranty claim tracking", "#ff8fc7")]
        for col, (icon, big, small, color) in zip([s1, s2, s3, s4], stats):
            with col:
                st.markdown(f"""
                <div class="fm-stat-card">
                    <div class="fm-stat-icon" style="background:{color}18; color:{color};">{icon}</div>
                    <div class="fm-stat-value">{big}</div>
                    <div class="fm-stat-label">{small}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height:64px;'></div>", unsafe_allow_html=True)

    # ---- Features ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        st.markdown("""
        <div style="text-align:center; margin-bottom:34px;">
            <div style="display:inline-block; padding:5px 14px; border-radius:999px; background:#e7fbf5;
                        color:#00a877; font-size:11.5px; font-weight:700; letter-spacing:0.4px; margin-bottom:14px;">
                WHY CUSTOMERLENS
            </div>
            <h2 style="font-size:28px; font-weight:800; color:#161029; margin:0;">Everything a mobile retail team needs</h2>
        </div>
        """, unsafe_allow_html=True)

        f1, f2, f3, f4 = st.columns(4)
        features = [
            ("🏷️", "#6c5ce7", "Brand-wise Analytics", "Compare Samsung, Apple, Xiaomi and every brand you carry side by side, store by store."),
            ("📦", "#00c2d1", "Live Inventory", "Store × brand stock heatmaps and low-stock alerts before you run out."),
            ("🔮", "#00d68f", "AI Forecasting", "Demand forecasts, churn risk, and segment-level insights out of the box."),
            ("🛡️", "#ff8fc7", "Warranty Tracking", "Claim status, resolution rate, and issue trends per brand and model."),
        ]
        for col, (icon, color, title, desc) in zip([f1, f2, f3, f4], features):
            with col:
                st.markdown(f"""
                <div class="fm-feature-card">
                    <div class="fm-feature-icon" style="background:linear-gradient(135deg,{color},{color}99);">{icon}</div>
                    <div class="fm-feature-title">{title}</div>
                    <div class="fm-feature-desc">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height:64px;'></div>", unsafe_allow_html=True)

    # ---- Testimonials ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        st.markdown("""
        <div style="text-align:center; margin-bottom:30px;">
            <div style="display:inline-block; padding:5px 14px; border-radius:999px; background:#fff6e5;
                        color:#c98a00; font-size:11.5px; font-weight:700; letter-spacing:0.4px; margin-bottom:14px;">
                TESTIMONIALS
            </div>
            <h2 style="font-size:28px; font-weight:800; color:#161029; margin:0 0 8px 0;">Loved by the teams who use it</h2>
            <p style="font-size:13px; color:#8a86a8; margin:0;">Real feedback from Vendors, Analysts, and Viewers on the platform.</p>
        </div>
        """, unsafe_allow_html=True)

        if not testimonials:
            st.info("No public testimonials yet.")
        else:
            cols = st.columns(3)
            for i, row in enumerate(testimonials):
                initials = "".join([p[0] for p in row["name"].split()][:2]).upper()
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="fm-testimonial-card">
                        <div class="fm-testimonial-quote">"</div>
                        <div style="margin-bottom:10px;">{_stars_html(row['rating'], size='13px')}</div>
                        <div style="font-size:13px; color:#4b4768; line-height:1.6; margin-bottom:18px; min-height:78px;">
                            {row['text']}
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="fm-testimonial-avatar">{initials}</div>
                            <div>
                                <div style="font-size:12.5px; font-weight:700; color:#161029;">{row['name']}</div>
                                <div style="font-size:11px; color:#8a86a8;">{row['role']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)

    # ---- Final CTA banner ----
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        st.markdown("""
        <div class="fm-cta-banner">
            <div style="font-size:24px; font-weight:800; margin-bottom:8px;">Ready to see it in action?</div>
            <div style="font-size:13.5px; opacity:0.85; margin-bottom:22px;">
                Jump in with sample data in under a minute — no setup required.
            </div>
        </div>
        """, unsafe_allow_html=True)
        cta_sp1, cta_btn, cta_sp2 = st.columns([2.6, 1.2, 2.6])
        with cta_btn:
            with st.container(key="cta_button_wrap"):
                if st.button("🚀 Get Started Free", key="banner_cta", width="stretch"):
                    st.session_state.auth_screen = "login"
                    st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    col_l, col_mid, col_r = st.columns([1, 6, 1])
    with col_mid:
        st.markdown("""
        <div style="text-align:center; padding:26px 0 6px 0; border-top:1px solid #e9e9f3; margin-top:26px;">
            <p style='color:#b6b3d1; font-size:11.5px; margin:0;'>
                Developed by <strong>Mayank Aneja</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)




# =====================================================================
# ENHANCED LOGIN / REGISTER PAGE
# =====================================================================
def show_login():
    """Enhanced login & register page with role-based information"""
    
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    col_back_l, col_back_m, col_back_r = st.columns([1, 5, 1])
    with col_back_m:
        if st.button("← Back to home", key="back_to_landing"):
            st.session_state.auth_screen = "landing"
            st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 5, 1])
    with col_mid:
        col_brand, col_form = st.columns([1, 1.15], gap="medium")
        
        # ============= BRAND PANEL =============
        with col_brand:
            with st.container(key="login_brand"):
                st.markdown("""
                <div style="display:flex; flex-direction:column; justify-content:space-between; min-height:500px;">
                    <div>
                        <div style="font-size:12px; font-weight:700; letter-spacing:1.5px;
                                    color:#00c2d1; text-transform:uppercase;">
                            Retail Intelligence Platform
                        </div>
                        <h1 style="color:white; font-size:36px; font-weight:900;
                                   margin:14px 0 12px 0; line-height:1.2;">
                            Every brand,<br>every store,<br>one dashboard.
                        </h1>
                        <p style="color:#a7abd1; font-size:13.5px; line-height:1.65; max-width:320px;">
                            CustomerLens turns raw mobile store data into actionable decisions. 
                            Brand performance, stock health, warranty trends, and demand forecasts 
                            powered by AI — all in one platform.
                        </p>
                        <div class="fm-dot-network">
                            <span style="top:6px; left:10%; background:#00c2d1; color:#00c2d1;"></span>
                            <span style="top:28px; left:22%; background:#6c5ce7; color:#6c5ce7;"></span>
                            <span style="top:4px; left:38%; background:#00d68f; color:#00d68f;"></span>
                            <span style="top:40px; left:33%; background:#00c2d1; color:#00c2d1; width:5px; height:5px;"></span>
                            <span style="top:16px; left:52%; background:#6c5ce7; color:#6c5ce7;"></span>
                            <span style="top:52px; left:48%; background:#00c2d1; color:#00c2d1;"></span>
                            <span style="top:2px; left:66%; background:#00d68f; color:#00d68f; width:5px; height:5px;"></span>
                            <span style="top:34px; left:63%; background:#6c5ce7; color:#6c5ce7;"></span>
                            <span style="top:60px; left:72%; background:#00c2d1; color:#00c2d1;"></span>
                            <span style="top:12px; left:82%; background:#00d68f; color:#00d68f;"></span>
                            <span style="top:46px; left:88%; background:#6c5ce7; color:#6c5ce7; width:5px; height:5px;"></span>
                            <span style="top:66px; left:20%; background:#6c5ce7; color:#6c5ce7; width:5px; height:5px;"></span>
                            <span style="top:70px; left:57%; background:#00c2d1; color:#00c2d1; width:5px; height:5px;"></span>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex; align-items:center; gap:12px; margin-bottom:18px;">
                            <div style="background:rgba(46,196,182,0.2); width:42px; height:42px; border-radius:12px;
                                        display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0;">🏬</div>
                            <div>
                                <div style="color:white; font-size:12px; font-weight:700;">60 Stores</div>
                                <div style="color:#a7abd1; font-size:11px;">Tracked live in real-time</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:12px; margin-bottom:18px;">
                            <div style="background:rgba(255,127,102,0.2); width:42px; height:42px; border-radius:12px;
                                        display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0;">📱</div>
                            <div>
                                <div style="color:white; font-size:12px; font-weight:700;">10 Mobile Brands</div>
                                <div style="color:#a7abd1; font-size:11px;">Samsung, Apple, Xiaomi & more</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:12px;">
                            <div style="background:rgba(91,110,225,0.2); width:42px; height:42px; border-radius:12px;
                                        display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0;">🤖</div>
                            <div>
                                <div style="color:white; font-size:12px; font-weight:700;">5+ ML Models</div>
                                <div style="color:#a7abd1; font-size:11px;">Instant predictions & insights</div>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # ============= LOGIN/REGISTER FORM =============
        with col_form:
            with st.container(key="login_card"):
                # Header
                top_l, top_r = st.columns([5, 1])
                with top_l:
                    st.markdown("""
                    <div style='font-size:32px; margin-bottom:2px;'>📱</div>
                    <h1 style='color:#161029; font-size:27px; font-weight:900; margin:0;'>CustomerLens</h1>
                    <p style='color:#8b8fb3; font-size:13px; margin-top:4px; font-weight:500;'>
                        Sales &amp; Customer Intelligence
                    </p>
                    """, unsafe_allow_html=True)
                with top_r:
                    with st.container(key="login_info"):
                        with st.popover("ⓘ", width="content"):
                            st.markdown("""
                            **Quick Access - Use these credentials:**
                            
                            Password format: `{role}123`
                            
                            👑 **Admin**  
                            admin@customerlens.com
                            
                            🏬 **Vendor** *(pick a brand, upload own data)*  
                            vendor.samsung@customerlens.com — Samsung  
                            vendor.apple@customerlens.com — Apple  
                            vendor.xiaomi@customerlens.com — Xiaomi  
                            vendor.oneplus@customerlens.com — OnePlus  
                            vendor.vivo@customerlens.com — Vivo  
                            
                            📊 **Analyst** *(upload own data)*  
                            analyst@customerlens.com  
                            analyst.rina@customerlens.com  
                            
                            👁️ **Viewer**  
                            viewer@customerlens.com
                            """)
                
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                
                # Tabs
                tab1, tab2 = st.tabs(["🔓 Sign In", "📝 Create Account"])
                
                # ============= LOGIN TAB =============
                with tab1:
                    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                    
                    email = st.text_input(
                        "Email Address",
                        placeholder="name@customerlens.com",
                        key="login_email",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        key="login_pwd",
                    )
                    
                    remember_me = st.checkbox("Remember me for 30 days", key="remember_me")
                    
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    
                    if st.button("🔓 Sign In", key="login_btn", width="stretch"):
                        if email and password:
                            result = authenticate_user(email, password)
                            if result["authenticated"]:
                                st.session_state.authenticated = True
                                st.session_state.user = result
                                st.session_state.current_page = "vendor" if result["role"] == "Vendor" else "dashboard"
                                log_user_activity(email)

                                # Admin gets asked to confirm/upload the platform
                                # dataset on every fresh login too (not just the
                                # very first time platform_data/ is empty) —
                                # they can still choose "Cancel and keep current
                                # data" on that screen to skip straight through.
                                if result["role"] == "Admin":
                                    st.session_state["force_upload_screen"] = True
                                
                                # Role-based welcome
                                role_emojis = {"Admin": "👑", "Vendor": "🏬", "Analyst": "📊", "Viewer": "👁️"}
                                role_emoji = role_emojis.get(str(result["role"]), "👤")
                                
                                st.success(f"{role_emoji} Welcome back, {result['name']}!")
                                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                                st.info("🚀 Redirecting to dashboard...")
                                st.rerun()
                            elif result.get("reason") == "deactivated":
                                st.error("🚫 This account has been deactivated by an Admin. Contact your administrator.")
                            else:
                                st.error("❌ Invalid email or password. Please try again.")
                        else:
                            st.warning("⚠️ Please enter both email and password.")
                    
                    st.markdown("""
                    <p style='text-align:center; color:#8b8fb3; font-size:12px; margin-top:16px;'>
                        Don't have an account? <strong>Register below →</strong>
                    </p>
                    """, unsafe_allow_html=True)
                
                # ============= REGISTER TAB =============
                with tab2:
                    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                    
                    r_email = st.text_input(
                        "Email Address",
                        key="reg_email",
                        placeholder="name@customerlens.com",
                    )
                    r_name = st.text_input(
                        "Full Name",
                        key="reg_name",
                        placeholder="John Doe",
                    )
                    r_pwd = st.text_input(
                        "Password (min 6 chars)",
                        type="password",
                        key="reg_pwd",
                    )
                    r_role = st.selectbox(
                        "Your Role",
                        ["Viewer", "Vendor", "Analyst"],
                        key="reg_role",
                    )

                    r_vendor_brand = None
                    if r_role == "Vendor":
                        r_vendor_brand = st.text_input(
                            "Your Brand / Vendor Name *",
                            key="reg_vendor_brand",
                            placeholder="e.g. Samsung",
                            help="Just a label for your own account — you'll upload your own isolated "
                                 "dataset every login, so this doesn't need to match anything else.",
                        )
                    
                    # Role descriptions
                    role_descriptions = {
                        "Viewer": {
                            "icon": "👁️",
                            "title": "Read-Only Access",
                            "perms": [
                                "✓ View dashboards",
                                "✓ Access reports",
                                "✓ View analytics",
                                "✗ Cannot modify data"
                            ]
                        },
                        "Vendor": {
                            "icon": "🏬",
                            "title": "Vendor Partner Access",
                            "perms": [
                                "🔒 Must upload your own dataset every login (fully isolated)",
                                "✓ Manage own products & inventory",
                                "✓ View own sales, customers & recommendations",
                                "✗ Cannot see other vendors' data"
                            ]
                        },
                        "Analyst": {
                            "icon": "📊",
                            "title": "Analyst Access",
                            "perms": [
                                "🔒 Must upload your own dataset every login (fully isolated)",
                                "✓ Full analytics: segmentation, forecasting, AI insights, reports",
                                "✓ Product & company comparison",
                                "✗ Cannot manage vendors or users"
                            ]
                        },
                    }
                    
                    role_info = role_descriptions[r_role]
                    st.markdown(f"""
                    <div style='background:#f5f7fb; border-radius:12px; padding:14px; border-left:4px solid #2EC4B6; margin:12px 0;'>
                        <div style='display:flex; gap:12px;'>
                            <div style='font-size:24px;'>{role_info["icon"]}</div>
                            <div>
                                <div style='font-size:13px; font-weight:700; color:#161029; margin-bottom:6px;'>
                                    {role_info["title"]}
                                </div>
                                <div style='font-size:12px; color:#555;'>
                                    {" | ".join(role_info["perms"][:2])}<br>
                                    {" | ".join(role_info["perms"][2:])}
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    
                    if st.button("📝 Create Account", key="reg_btn", width="stretch"):
                        if r_email and r_name and r_pwd and (r_role != "Vendor" or (r_vendor_brand and r_vendor_brand.strip())):
                            if len(r_pwd) < 6:
                                st.error("❌ Password must be at least 6 characters.")
                            else:
                                brand = r_vendor_brand.strip() if r_role == "Vendor" and r_vendor_brand else None
                                success, msg = register_user(r_email, r_pwd, r_name, r_role, vendor_brand=brand)
                                if success:
                                    if r_role == "Vendor" and brand:
                                        from utils import vendor_store
                                        vendor_store.register_vendor(brand, business_name=r_name)
                                    st.success(f"✅ {msg}")
                                    st.info("👉 Now sign in with your credentials above")
                                else:
                                    st.error(f"❌ {msg}")
                        else:
                            st.warning("⚠️ Please fill all fields" + (" (Brand / Vendor Name is required for Vendor accounts)." if r_role == "Vendor" else "."))


# =====================================================================
# WELCOME / UPLOAD SCREEN — shown until data exists in this session.
# No hardcoded CSV path is auto-loaded; the platform starts empty and
# only shows charts/KPIs/reports once real data is present.
# =====================================================================
# =====================================================================
# MANDATORY PER-LOGIN UPLOAD (Vendor / Analyst) — full data isolation
# =====================================================================
def show_mandatory_user_upload(user):
    """
    Vendor and Analyst accounts must upload their own dataset every login.
    Nothing they upload here is ever visible to another Vendor/Analyst, and
    it's completely separate from the shared platform dataset Admin/Viewer
    use — this is what makes vendor isolation real instead of just a Brand
    filter on a shared table.
    """
    role_word = "Vendor" if user["role"] == "Vendor" else "Analyst"
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 3, 1])
    with col_m:
        st.markdown(f"""
        <div style='text-align:center; margin-bottom:20px;'>
            <div style='font-size:40px;'>🔒</div>
            <h2 style='color:#161029; font-weight:900; margin:6px 0 4px 0;'>
                Upload your dataset to continue, {user['name'].split()[0]}
            </h2>
            <p style='color:#8b8fb3; font-size:13.5px;'>
                As a {role_word}, your data is fully isolated — no other Vendor or Analyst can ever see it,
                and it's separate from the shared platform dataset. Upload fresh CSV/Excel files each login
                (Products, Orders, Customers, Inventory, Feedback, etc.) — we'll auto-detect each file's type,
                validate it, and let you clean it before it powers your dashboard.
            </p>
        </div>
        """, unsafe_allow_html=True)

        step = st.session_state.get("mandatory_upload_step", "upload")

        # ---- Step 1: upload ----
        if step == "upload":
            uploaded_files = st.file_uploader(
                "Upload one or more CSV or Excel files",
                type=["csv", "xlsx", "xls"],
                accept_multiple_files=True,
                key="mandatory_uploader",
            )
            colu1, colu2 = st.columns(2)
            with colu1:
                if uploaded_files and st.button("🔍 Validate & Preview", key="mandatory_validate_btn", width="stretch"):
                    with st.spinner("Detecting dataset types, validating, and merging..."):
                        data, reports, unknown = process_uploaded_files(uploaded_files)
                    st.session_state["mandatory_raw_data"] = data
                    st.session_state["mandatory_reports"] = reports
                    st.session_state["mandatory_unknown"] = unknown
                    st.session_state["mandatory_upload_step"] = "preview"
                    st.rerun()
            with colu2:
                if st.button("✨ Use Sample Demo Data Instead", key="mandatory_sample_btn", width="stretch"):
                    st.session_state["mandatory_raw_data"] = get_data()
                    st.session_state["mandatory_reports"] = {}
                    st.session_state["mandatory_unknown"] = []
                    st.session_state["mandatory_upload_step"] = "preview"
                    st.rerun()
            return

        data = st.session_state.get("mandatory_raw_data")
        if data is None:
            st.session_state["mandatory_upload_step"] = "upload"
            st.rerun()

        # ---- Step 2: preview + validation + data quality report ----
        if step == "preview":
            st.markdown("#### 🔍 Validation Results")
            reports = st.session_state.get("mandatory_reports") or {}
            if reports:
                for dtype, items in reports.items():
                    for item in items:
                        rep = item["report"]
                        status = "🟢" if not rep["errors"] and not rep["warnings"] else ("🔴" if rep["errors"] else "🟡")
                        with st.expander(f"{status} {item['filename']} → detected as **{dtype}** ({item['rows']:,} rows)"):
                            for e in rep["errors"]:
                                st.error(e)
                            for w in rep["warnings"]:
                                st.warning(w)
                            for i in rep["info"]:
                                st.success(i)
            unknown = st.session_state.get("mandatory_unknown") or []
            if unknown:
                st.info(f"Could not confidently classify: {', '.join(unknown)}. They were kept under their own name.")

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 📋 Data Preview & Quality Report")
            any_data = False
            for key, df in data.items():
                if df is None or df.empty:
                    continue
                any_data = True
                q = get_data_quality_report(df)
                with st.expander(f"📄 {key} — {q['total_rows']:,} rows × {q['total_columns']} columns "
                                  f"({q['duplicate_rows']} duplicate rows, {q['missing_cells']} missing cells)"):
                    st.dataframe(df.head(10), width="stretch", hide_index=True)

            if not any_data:
                st.warning("No recognizable data in that upload. Go back and try different files, or use sample data.")

            colp1, colp2, colp3 = st.columns(3)
            with colp1:
                if st.button("← Back", key="mandatory_back_btn", width="stretch"):
                    st.session_state["mandatory_upload_step"] = "upload"
                    st.rerun()
            with colp2:
                if st.button("🧹 Auto-Clean Dataset", key="mandatory_clean_btn", width="stretch"):
                    cleaned, clean_report = auto_clean_datasets(data)
                    st.session_state["mandatory_raw_data"] = cleaned
                    st.session_state["mandatory_clean_report"] = clean_report
                    st.rerun()
            with colp3:
                if any_data and st.button("✅ Confirm & Enter Dashboard", key="mandatory_confirm_btn",
                                            width="stretch", type="primary"):
                    save_data = dict(st.session_state["mandatory_raw_data"])
                    if user["role"] == "Vendor":
                        # Even on the "sample demo data" shortcut, a Vendor
                        # only ever gets their own brand's slice saved.
                        save_data = scope_data_for_vendor(save_data, user.get("vendor_brand"))
                    save_user_data(user, save_data, uploaded_by=user["name"])
                    st.session_state["custom_data"] = save_data
                    st.session_state["user_data_confirmed_this_login"] = True
                    for k in ["mandatory_raw_data", "mandatory_reports", "mandatory_unknown",
                              "mandatory_upload_step", "mandatory_clean_report"]:
                        st.session_state.pop(k, None)
                    st.success("✅ Your isolated dataset is ready.")
                    st.rerun()

            clean_report = st.session_state.get("mandatory_clean_report")
            if clean_report:
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                st.success("🧹 Cleaned: " + "; ".join(
                    f"{k} — {v['duplicate_rows_removed']} dup rows removed, "
                    f"{v['numeric_values_filled']} numeric + {v['text_values_filled']} text values filled"
                    for k, v in clean_report.items()
                ) if clean_report else "Nothing needed cleaning.")


# =====================================================================
# WELCOME / SHARED PLATFORM UPLOAD (Admin / Viewer)
# =====================================================================
def show_welcome_upload(user):
    is_viewer = user["role"] == "Viewer"

    st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 3, 1])
    with col_m:
        st.markdown("""
        <div style='text-align:center; margin-bottom:20px;'>
            <div style='font-size:40px;'>📊</div>
            <h2 style='color:#161029; font-weight:900; margin:6px 0 4px 0;'>
                Upload your datasets to begin customer analysis.
            </h2>
            <p style='color:#8b8fb3; font-size:13.5px;'>
                Drop in one or more CSV files — Customers, Orders, Products, Payments, Feedback,
                Returns, Loyalty, and more. CustomerLens automatically detects each dataset type,
                validates it, and merges everything into a single Customer Intelligence Platform.
            </p>
        </div>
        """, unsafe_allow_html=True)

        if is_viewer:
            st.info("🔒 Your account has read-only (Viewer) access. Ask an Admin to upload data — "
                     "once they do, you'll see it here automatically.")
            return

        if st.session_state.get("force_upload_screen"):
            st.warning("You're replacing the platform's shared dataset — this affects what every user sees.")
            if st.button("← Cancel and keep current data", key="cancel_reupload"):
                st.session_state.pop("force_upload_screen", None)
                st.rerun()

        with st.container(key="welcome_upload_card"):
            uploaded_files = st.file_uploader(
                "Upload one or more CSV files",
                type=["csv"],
                accept_multiple_files=True,
                key="welcome_uploader",
            )

            if uploaded_files:
                if st.button("🚀 Process & Analyze Data", key="welcome_process_btn", width="stretch"):
                    with st.spinner("Detecting datasets, validating, and merging..."):
                        data, reports, unknown = process_uploaded_files(uploaded_files)
                        save_platform_data(data, uploaded_by=user["name"])
                    st.session_state["custom_data"] = data
                    st.session_state["upload_reports"] = reports
                    st.session_state["unknown_files"] = unknown
                    st.session_state.pop("force_upload_screen", None)
                    st.success("✅ Saved — this data is now visible to every user of the platform, not just this session.")
                    st.rerun()

            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align:center; color:#8b8fb3; font-size:12px;'>— or —</p>",
                unsafe_allow_html=True,
            )
            if st.button("✨ Load Sample Demo Data", key="welcome_sample_btn", width="stretch"):
                sample_data = get_data()
                save_platform_data(sample_data, uploaded_by=f"{user['name']} (sample data)")
                st.session_state["custom_data"] = sample_data
                st.session_state["upload_reports"] = {}
                st.session_state["unknown_files"] = []
                st.session_state.pop("force_upload_screen", None)
                st.rerun()

        # Show validation results from the last processed upload, if any
        reports = st.session_state.get("upload_reports")
        if reports:
            st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 🔍 Validation Results")
            for dtype, items in reports.items():
                for item in items:
                    rep = item["report"]
                    status = "🟢" if not rep["errors"] and not rep["warnings"] else ("🔴" if rep["errors"] else "🟡")
                    with st.expander(f"{status} {item['filename']} → detected as **{dtype}** ({item['rows']:,} rows)"):
                        for e in rep["errors"]:
                            st.error(e)
                        for w in rep["warnings"]:
                            st.warning(w)
                        for i in rep["info"]:
                            st.success(i)
            unknown = st.session_state.get("unknown_files") or []
            if unknown:
                st.info(f"Could not confidently classify: {', '.join(unknown)}. They were skipped for analysis.")


# =====================================================================
# MAIN APP
# =====================================================================
def main():
    if not st.session_state.authenticated:
        if st.session_state.auth_screen == "landing":
            show_landing()
        else:
            show_login()
        return
    
    user = st.session_state.user
    is_admin = user["role"] == "Admin"
    needs_own_upload = user["role"] in MANDATORY_UPLOAD_ROLES

    # Vendor / Analyst: mandatory, fully isolated dataset — re-confirmed
    # every fresh login (this flag lives only in session state, so a new
    # login always starts back at the upload gate).
    if needs_own_upload and not st.session_state.get("user_data_confirmed_this_login"):
        show_mandatory_user_upload(user)
        return

    # No hardcoded auto-load: but if ANYONE (in any session) has already
    # uploaded data, it's persisted to disk and shared with every user —
    # including a fresh Viewer login — so it "just shows up" automatically.
    # (Vendor/Analyst never touch this path — their data came from the
    # mandatory upload gate above and is already in session state.)
    if not needs_own_upload:
        if not st.session_state.get("force_upload_screen") and st.session_state.get("custom_data") is None:
            persisted = load_platform_data()
            if persisted is not None:
                st.session_state["custom_data"] = persisted

        if st.session_state.get("force_upload_screen") or st.session_state.get("custom_data") is None:
            show_welcome_upload(user)
            return

    data = st.session_state["custom_data"]

    # SAFETY NET: no matter where a Vendor's data came from — their own
    # upload, the "sample demo data" shortcut, or an accidentally
    # multi-brand file — they must never see another vendor's rows. This
    # is a no-op if their data was already single-brand (the normal case
    # for a genuine own-upload); it's the fix for the case where it wasn't.
    if user["role"] == "Vendor":
        data = scope_data_for_vendor(data, user.get("vendor_brand"))

    # Navigation (left sidebar)
    clicked = ui.sidebar_nav(st.session_state.current_page, is_admin=is_admin, role=user["role"])
    if clicked != st.session_state.current_page:
        st.session_state.current_page = clicked
        st.rerun()

    # Slim top strip: search / notifications / help / profile
    topbar_action = ui.topbar(user, data)
    if topbar_action["logout"]:
        st.session_state.authenticated = False
        st.session_state.user = None
        for k in ["custom_data", "upload_reports", "unknown_files", "force_upload_screen",
                  "user_data_confirmed_this_login", "mandatory_raw_data", "mandatory_reports",
                  "mandatory_unknown", "mandatory_upload_step", "mandatory_clean_report"]:
            st.session_state.pop(k, None)
        st.rerun()
    if topbar_action["navigate_to"] and topbar_action["navigate_to"] != st.session_state.current_page:
        st.session_state.current_page = topbar_action["navigate_to"]
        st.rerun()
    if topbar_action.get("reupload_own_data") and needs_own_upload:
        st.session_state.pop("user_data_confirmed_this_login", None)
        st.session_state.pop("custom_data", None)
        st.rerun()
    
    # Route to pages
    page = st.session_state.current_page
    
    is_vendor = user["role"] == "Vendor"

    if page == "dashboard" and not is_vendor:
        dashboard.render(data, user)
    elif page == "customers" and not is_vendor:
        customers.render(data, user)
    elif page == "customer360" and not is_vendor:
        customer_360.render(data, user)
    elif page == "sales":
        sales.render(data, user)
    elif page == "products":
        products.render(data, user)
    elif page == "product_tiers":
        product_tiers.render(data, user)
    elif page == "product_comparison":
        product_comparison.render(data, user)
    elif page == "product360":
        product_360.render(data, user)
    elif page == "inventory":
        inventory.render(data, user)
    elif page == "warranty":
        warranty.render(data, user)
    elif page == "vendor" and (is_admin or is_vendor):
        vendor.render(data, user)
    elif page == "vendor360" and (is_admin or is_vendor or user["role"] == "Analyst"):
        vendor_360.render(data, user)
    elif page == "marketing" and not is_vendor:
        marketing.render(data, user)
    elif page == "insights" and not is_vendor:
        # Use enhanced version
        business_insights.render(data, user)
    elif page == "ai":
        ai_predictions.render(data, user)
    elif page == "forecast":
        forecast.render(data, user)
    elif page == "explorer" and not is_vendor:
        data_explorer.render(data, user)
    elif page == "studio" and is_admin:
        # Use enhanced version
        data_studio.render(data, user)
    elif page == "reports":
        reports.render(data, user)
    elif page == "feedback":
        platform_feedback.render(data, user)
    elif page == "admin" and is_admin:
        # Use enhanced version
        admin.render(data, user)
    elif page == "add_data" and is_admin:
        add_data.render(data, user)
    elif is_vendor:
        vendor.render(data, user)
    else:
        dashboard.render(data, user)


if __name__ == "__main__":
    main()