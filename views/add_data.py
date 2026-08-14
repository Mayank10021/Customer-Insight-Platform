"""
Add New Data — a guided, step-by-step data-entry workflow (Admin-only).

Replaces the old single "Add Customer" form, which wrote to a disconnected
static folder (so the dashboard never reflected it) and only ever created a
bare customer row with no order/product/feedback links.

Flow: Create Customer -> Add Order (select or create Product) -> Add
Feedback (optional) -> Review. Every record created here is linked by
CustomerID / OrderID / ProductID, is written straight into the live shared
dataset (st.session_state["custom_data"] + save_platform_data), and is
visible immediately — no re-login or re-upload needed.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from utils import ui
from utils.data_handler import (
    save_platform_data, search_customers,
    append_customer_record, append_order_record, append_product_record,
    append_feedback_record,
)

STEP_LABELS = {1: "Create Customer", 2: "Add Order", 3: "Add Feedback (optional)", 4: "Review"}


def _reset_wizard():
    for k in list(st.session_state.keys()):
        if k.startswith("adw_"):
            del st.session_state[k]
    st.session_state["adw_step"] = 1


def _persist(data, keys, uploaded_by):
    """Writes only the given dataset keys to the shared platform dataset and
    refreshes the in-session copy, so every page (dashboard, Customer 360,
    tables) sees the change on its very next render — no reload needed."""
    save_platform_data(data, dataset_meta={k: {"uploaded_by": uploaded_by} for k in keys})
    st.session_state["custom_data"] = data


def _progress_bar(current_step):
    cols = st.columns(4)
    for i, col in enumerate(cols, start=1):
        with col:
            if i < current_step:
                st.markdown(f"<div style='text-align:center; color:#00c2d1; font-weight:700;'>"
                            f"✅ {i}. {STEP_LABELS[i]}</div>", unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f"<div style='text-align:center; color:#ff7f66; font-weight:800;'>"
                            f"🔵 {i}. {STEP_LABELS[i]}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center; color:#8b8fb3;'>"
                            f"{i}. {STEP_LABELS[i]}</div>", unsafe_allow_html=True)
    st.progress((current_step - 1) / 3)


def _pick_or_other(label, options, key):
    """A selectbox of existing values plus an 'Other (type new)' escape
    hatch — used for City/State/Category/Brand so data stays consistent
    with what's already in the dataset by default, without locking the
    admin out of adding something genuinely new."""
    options = sorted(set(str(o) for o in options if str(o).strip()))
    choice = st.selectbox(label, options + ["➕ Other (type new)"], key=f"{key}_sel")
    if choice == "➕ Other (type new)":
        return st.text_input(f"New {label}", key=f"{key}_txt")
    return choice


def render(data, user):
    ui.page_header("➕ Add New Data", "HOME &nbsp;›&nbsp; ADMIN &nbsp;›&nbsp; ADD NEW DATA")

    if "adw_step" not in st.session_state:
        _reset_wizard()
    step = st.session_state["adw_step"]

    st.markdown("""
    <div style='background:linear-gradient(135deg, #5b6ee1 0%, #7d87f5 100%);
                padding:14px 16px; border-radius:12px; color:white; margin-bottom:16px;'>
        <div style='font-size:13px; font-weight:600;'>Guided data entry</div>
        <div style='font-size:12px; color:rgba(255,255,255,0.85); margin-top:4px;'>
            Build a complete customer record step by step — everything you add here
            is linked by ID and shows up across the app immediately.
        </div>
    </div>
    """, unsafe_allow_html=True)

    _progress_bar(step)
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    if st.session_state.get("adw_customer_id"):
        st.info(f"👤 Working on: **{st.session_state.get('adw_customer_label', st.session_state['adw_customer_id'])}**")

    # ================= STEP 1: CREATE CUSTOMER =================
    if step == 1:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown("### Step 1 — Create Customer")
        with col_b:
            if st.button("Have an existing customer? Skip to Add Order →", key="adw_skip_to_order"):
                st.session_state["adw_step"] = 2
                st.session_state["adw_customer_id"] = None
                st.rerun()

        ui.card_open("Customer Details")
        customers_df = data.get("customers", pd.DataFrame())
        existing_cities = customers_df["City"].dropna().unique().tolist() if "City" in customers_df.columns else []
        existing_states = customers_df["State"].dropna().unique().tolist() if "State" in customers_df.columns else []

        # City/State live outside the form: the "Other (type new)" option
        # needs an immediate rerun to reveal its text box, and widgets
        # inside st.form() only commit on submit, not on every interaction.
        st.markdown("**Location**")
        l1, l2 = st.columns(2)
        with l1:
            city = _pick_or_other("City", existing_cities, "adw_city")
        with l2:
            state = _pick_or_other("State", existing_states, "adw_state")

        with st.form("adw_customer_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Customer Name *", placeholder="Priya Sharma")
                email = st.text_input("Email *", placeholder="priya.sharma@example.com")
                phone = st.text_input("Phone Number *", placeholder="+91 9876543210")
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            with c2:
                age = st.number_input("Age", min_value=10, max_value=100, value=30)
                income = st.number_input("Monthly Income (₹)", min_value=0, value=40000, step=1000,
                                          help="Used to keep purchase amounts realistic relative to this customer.")
                signup_date = st.date_input("Registration / Join Date", value=datetime.now())

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("✅ Create Customer & Continue", type="primary", width="stretch")

            if submitted:
                if not (name.strip() and email.strip() and phone.strip() and city.strip() and state.strip()):
                    st.error("❌ Please fill in Name, Email, Phone, City, and State.")
                else:
                    customer_data = {
                        "Name": name.strip(),
                        "Email": email.strip(),
                        "Phone": phone.strip(),
                        "Gender": {"Male": "M", "Female": "F", "Other": "O"}.get(gender, gender),
                        "Age": int(age),
                        "Income": int(income),
                        "City": city.strip(),
                        "State": state.strip(),
                        "SignupDate": pd.Timestamp(signup_date),
                    }
                    updated_customers, new_id = append_customer_record(customers_df, customer_data)
                    data["customers"] = updated_customers
                    _persist(data, ["customers"], user.get("name"))

                    st.session_state["adw_customer_id"] = new_id
                    st.session_state["adw_customer_label"] = f"{name.strip()} ({new_id})"
                    st.session_state["adw_summary_customer"] = {**customer_data, "CustomerID": new_id}
                    st.session_state["adw_step"] = 2
                    st.success(f"✅ Customer created — ID **{new_id}**. Total customers: {len(updated_customers):,}")
                    st.rerun()
        ui.card_close()

    # ================= STEP 2: ADD ORDER =================
    elif step == 2:
        st.markdown("### Step 2 — Add Order")

        # Pick a customer if we arrived here without one from Step 1
        if not st.session_state.get("adw_customer_id"):
            ui.card_open("Select Customer")
            query = st.text_input("Search by CustomerID, Name, Email, or Phone", key="adw_cust_search")
            matches = search_customers(data, query) if query else pd.DataFrame()
            if not matches.empty:
                options = {f"{r['Name']} — {r['CustomerID']} — {r.get('City','')}": r["CustomerID"]
                           for _, r in matches.iterrows()}
                pick = st.selectbox("Matching customers", list(options.keys()), key="adw_cust_pick")
                if st.button("Use this customer", key="adw_use_cust"):
                    st.session_state["adw_customer_id"] = options[pick]
                    st.session_state["adw_customer_label"] = pick.split(" — ")[0] + f" ({options[pick]})"
                    st.rerun()
            elif query:
                st.warning("No matching customer found.")
            st.caption("Or go back and create a brand-new customer instead.")
            if st.button("← Back to Create Customer", key="adw_back_to_step1"):
                st.session_state["adw_step"] = 1
                st.rerun()
            ui.card_close()
            return

        products_df = data.get("products", pd.DataFrame())
        stores_df = data.get("stores", pd.DataFrame())

        ui.card_open("Order Details")
        use_new_product = st.toggle("This product doesn't exist yet — add it now", key="adw_new_product_toggle")

        new_product_data = None
        if use_new_product:
            st.markdown("**New Product**")
            existing_cats = products_df["Category"].dropna().unique().tolist() if "Category" in products_df.columns else []
            existing_brands = products_df["Brand"].dropna().unique().tolist() if "Brand" in products_df.columns else []
            p1, p2 = st.columns(2)
            with p1:
                p_name = st.text_input("Product Name *", placeholder="Galaxy S25 (Black)", key="adw_p_name")
                p_brand = _pick_or_other("Brand", existing_brands, "adw_p_brand")
                p_price = st.number_input("Price (₹) *", min_value=0, value=20000, step=500, key="adw_p_price")
            with p2:
                p_category = _pick_or_other("Category", existing_cats, "adw_p_category")
                p_stock = st.number_input("Stock / Quantity Available", min_value=0, value=50, key="adw_p_stock")
            unit_price = float(p_price)
        else:
            if products_df.empty:
                st.warning("No products exist yet — toggle 'add it now' above.")
                unit_price = 0.0
                selected_product_id = None
            else:
                prod_query = st.text_input("Search product (name or brand)", key="adw_prod_search")
                pdf = products_df
                if prod_query:
                    q = prod_query.strip().lower()
                    pdf = products_df[
                        products_df["ProductName"].astype(str).str.lower().str.contains(q, na=False)
                        | products_df["Brand"].astype(str).str.lower().str.contains(q, na=False)
                    ]
                pdf = pdf.head(300)
                prod_options = {f"{r['ProductName']} — {r['Brand']} — ₹{r['Price']:,.0f} ({r['ProductID']})": r
                                 for _, r in pdf.iterrows()}
                if prod_options:
                    prod_pick = st.selectbox("Product *", list(prod_options.keys()), key="adw_prod_pick")
                    selected_row = prod_options[prod_pick]
                    selected_product_id = selected_row["ProductID"]
                    unit_price = float(selected_row["Price"])
                    st.caption(f"Category: {selected_row.get('Category', '—')}")
                else:
                    st.warning("No products match that search.")
                    selected_product_id = None
                    unit_price = 0.0

        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        with st.form("adw_order_form"):
            o1, o2, o3 = st.columns(3)
            with o1:
                order_date = st.date_input("Order Date", value=datetime.now())
                quantity = st.number_input("Quantity", min_value=1, value=1)
            with o2:
                unit_price_input = st.number_input("Unit Price (₹)", min_value=0.0, value=float(unit_price), step=100.0)
                total_amount = round(quantity * unit_price_input, 2)
                st.metric("Total Amount", f"₹{total_amount:,.2f}")
            with o3:
                if not stores_df.empty:
                    store_options = {f"{r['StoreName']} ({r['StoreID']})": r["StoreID"] for _, r in stores_df.iterrows()}
                    store_pick = st.selectbox("Store", list(store_options.keys()))
                    store_id = store_options[store_pick]
                else:
                    store_id = st.text_input("Store ID", value="ST0001")
                order_status = st.selectbox("Order Status", ["Completed", "Processing", "Cancelled", "Returned"])

            payment_method = st.selectbox("Payment Method",
                                           ["UPI", "Credit Card", "Debit Card", "Cash", "EMI", "Net Banking", "Wallet"])

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            c_submit, c_skip = st.columns([3, 1])
            with c_submit:
                order_submitted = st.form_submit_button("✅ Add Order & Continue", type="primary", width="stretch")
            with c_skip:
                skip_order = st.form_submit_button("Skip →", width="stretch")

            if order_submitted:
                if use_new_product and not p_name.strip():
                    st.error("❌ Please enter a Product Name for the new product.")
                elif not use_new_product and selected_product_id is None:
                    st.error("❌ Please select a product, or toggle 'add it now'.")
                else:
                    persist_keys = []
                    if use_new_product:
                        new_product_data = {
                            "ProductName": p_name.strip(),
                            "Category": p_category,
                            "Brand": p_brand,
                            "Price": float(p_price),
                            "Stock": int(p_stock),
                        }
                        updated_products, product_id = append_product_record(products_df, new_product_data)
                        data["products"] = updated_products
                        persist_keys.append("products")
                    else:
                        product_id = selected_product_id

                    order_data = {
                        "CustomerID": st.session_state["adw_customer_id"],
                        "ProductID": product_id,
                        "Date": pd.Timestamp(order_date),
                        "Quantity": int(quantity),
                        "Price": float(unit_price_input),
                        "TotalAmount": total_amount,
                        "StoreID": store_id,
                        "OrderStatus": order_status,
                        "PaymentMethod": payment_method,
                    }
                    updated_orders, updated_payments, order_id = append_order_record(
                        data.get("orders", pd.DataFrame()), data.get("payments", pd.DataFrame()), order_data
                    )
                    data["orders"] = updated_orders
                    data["payments"] = updated_payments
                    persist_keys += ["orders", "payments"]

                    _persist(data, persist_keys, user.get("name"))

                    st.session_state["adw_order_id"] = order_id
                    st.session_state["adw_product_id"] = product_id
                    st.session_state["adw_summary_order"] = {**order_data, "OrderID": order_id}
                    st.session_state["adw_step"] = 3
                    st.success(f"✅ Order **{order_id}** added for {st.session_state['adw_customer_label']}.")
                    st.rerun()

            if skip_order:
                st.session_state["adw_step"] = 4
                st.rerun()
        ui.card_close()

    # ================= STEP 3: ADD FEEDBACK (optional) =================
    elif step == 3:
        st.markdown("### Step 3 — Add Feedback (optional)")
        ui.card_open("Customer Feedback / Review")

        products_df = data.get("products", pd.DataFrame())
        default_product = st.session_state.get("adw_product_id")

        with st.form("adw_feedback_form"):
            f1, f2 = st.columns(2)
            with f1:
                if not products_df.empty:
                    prod_ids = products_df["ProductID"].astype(str).tolist()
                    idx = prod_ids.index(default_product) if default_product in prod_ids else 0
                    fb_product = st.selectbox("Product", prod_ids, index=idx)
                else:
                    fb_product = st.text_input("Product ID")
                rating = st.select_slider("Rating", options=[1, 2, 3, 4, 5], value=5)
            with f2:
                fb_date = st.date_input("Feedback Date", value=datetime.now())
                review = st.text_area("Review", placeholder="Great phone, battery life is excellent...")

            c_submit, c_skip = st.columns([3, 1])
            with c_submit:
                fb_submitted = st.form_submit_button("✅ Add Feedback & Continue", type="primary", width="stretch")
            with c_skip:
                fb_skip = st.form_submit_button("Skip →", width="stretch")

            if fb_submitted:
                feedback_data = {
                    "CustomerID": st.session_state["adw_customer_id"],
                    "ProductID": fb_product,
                    "Review": review.strip(),
                    "Rating": int(rating),
                    "Date": pd.Timestamp(fb_date),
                }
                updated_feedback, feedback_id = append_feedback_record(data.get("feedback", pd.DataFrame()), feedback_data)
                data["feedback"] = updated_feedback
                _persist(data, ["feedback"], user.get("name"))
                st.session_state["adw_summary_feedback"] = {**feedback_data, "FeedbackID": feedback_id}
                st.session_state["adw_step"] = 4
                st.success(f"✅ Feedback **{feedback_id}** recorded.")
                st.rerun()
            if fb_skip:
                st.session_state["adw_step"] = 4
                st.rerun()
        ui.card_close()

    # ================= STEP 4: REVIEW =================
    elif step == 4:
        st.markdown("### Step 4 — Review & Done")
        ui.card_open("Summary")

        cust = st.session_state.get("adw_summary_customer")
        order = st.session_state.get("adw_summary_order")
        fb = st.session_state.get("adw_summary_feedback")

        if cust:
            st.markdown(f"**👤 Customer:** {cust['Name']} — `{cust['CustomerID']}` — {cust['City']}, {cust['State']}")
        elif st.session_state.get("adw_customer_id"):
            st.markdown(f"**👤 Customer:** {st.session_state.get('adw_customer_label')}")
        if order:
            st.markdown(f"**🛒 Order:** `{order['OrderID']}` — {order['Quantity']} × Product `{order['ProductID']}` "
                        f"— Total ₹{order['TotalAmount']:,.2f} — {order.get('OrderStatus','')} — {order.get('PaymentMethod','')}")
        if fb:
            st.markdown(f"**💬 Feedback:** `{fb['FeedbackID']}` — {fb['Rating']}★ on `{fb['ProductID']}`")

        if not order:
            st.info("No order was added for this customer yet — they'll show up in the customer list and count, "
                     "but won't appear in Customer 360 (which only lists customers with order activity) until an order exists.")

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button("➕ Add Another Order\nfor this Customer", key="adw_another_order", width="stretch"):
                for k in ["adw_order_id", "adw_product_id", "adw_summary_order", "adw_summary_feedback"]:
                    st.session_state.pop(k, None)
                st.session_state["adw_step"] = 2
                st.rerun()
        with b2:
            if st.session_state.get("adw_customer_id") and st.button("👤 View Customer 360", key="adw_view_360", width="stretch"):
                st.session_state["c360_direct_customer_id"] = st.session_state["adw_customer_id"]
                st.session_state["current_page"] = "customer360"
                st.rerun()
        with b3:
            if st.button("🆕 Add Another\nNew Customer", key="adw_new_cust", width="stretch"):
                _reset_wizard()
                st.rerun()
        with b4:
            if st.button("🏠 Go to Dashboard", key="adw_go_dash", width="stretch"):
                _reset_wizard()
                st.session_state["current_page"] = "dashboard"
                st.rerun()
        ui.card_close()
