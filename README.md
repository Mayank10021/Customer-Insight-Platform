# 📱 CustomerLens — Mobile Store Customer Insights & Sales Intelligence Platform

An enterprise-style Python analytics platform built for **CustomerLens**, a simulated
60-store Indian mobile phone retail chain selling multiple brands (Samsung, Apple,
Xiaomi, OnePlus, Vivo, Oppo, Realme, Google, Motorola, Nothing). It centralizes
customer, sales, product (phone model/specs), inventory, and warranty claim data
into one dashboard, and layers five machine learning models on top to answer real
retail business questions: who buys the most, which models sell best, who might
churn, what to recommend next, and what next month's sales will look like.

---

## ✅ Verified Working

Every page and every ML feature in this build was **programmatically tested**
using Streamlit's official `AppTest` framework before delivery — logins for all
4 roles, every navigation page, every AI Predictions tab (segmentation, churn,
recommendations, forecasting, sentiment), Admin user creation, and Excel/PDF/CSV
report generation all ran with **zero exceptions**. See `test_app.py` if you'd
like to re-run these checks yourself.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (custom-themed, dark sidebar / light dashboard UI) |
| Backend | Python 3.14+ |
| Database | SQLite (users, login history, custom uploads) |
| Data | Pandas, NumPy |
| Charts | Plotly |
| ML | Scikit-learn (KMeans, RandomForest, LinearRegression, NearestNeighbors) |
| Sentiment | TextBlob |
| Reports | OpenPyXL / XlsxWriter (Excel), fpdf2 (PDF) |

---

## 📁 Project Structure

```
CustomerLens/
├── app.py                     # Entry point — auth, routing, layout
├── generate_data.py            # Generates the 8 synthetic datasets (already run)
├── requirements.txt
├── README.md
├── .streamlit/config.toml      # Theme config
│
├── data/                       # 9 core CSV datasets (~50,000 customers, 250,000 orders, 3 years)
│   ├── customers.csv
│   ├── orders.csv
│   ├── products.csv            # phone models: Brand, Category, RAM, Storage, Battery, Camera, Warranty...
│   ├── payments.csv
│   ├── feedback.csv
│   ├── employees.csv
│   ├── stores.csv
│   ├── inventory.csv           # store-wise stock levels, joined with Brand for breakdowns
│   └── warranty_claims.csv     # per-device warranty claim history
│
├── utils/
│   ├── auth.py                 # Login / register / roles / login history
│   ├── data_handler.py         # Loads core CSVs, custom uploads, admin CRUD
│   ├── ml_engine.py             # Segmentation, churn, recommendation, forecast, sentiment
│   ├── report_generator.py     # Excel + PDF report builders
│   └── ui.py                    # Theme CSS, sidebar, topbar, KPI cards
│
├── views/
│   ├── dashboard.py             # Home — KPIs, trends
│   ├── customers.py             # Customer Analytics
│   ├── sales.py                  # Sales Dashboard
│   ├── products.py               # Product Analytics
│   ├── marketing.py              # Marketing Dashboard
│   ├── business_insights.py     # Business Insights — AI recommendations
│   ├── ai_predictions.py         # AI Prediction Page (5 tabs)
│   ├── data_explorer.py          # Full data sheet browser: search + filters + download
│   ├── data_studio.py            # Upload → Clean → Analyze → Download tab
│   ├── reports.py                # Excel / PDF / CSV export incl. "Download Everything"
│   └── admin.py                  # User mgmt, upload, record deletion (Admin only)
│
├── database/                    # users.db, data.db — created automatically
├── uploads/                     # Custom admin CSV uploads land here
└── exports/                     # Reserved for saved report copies
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies (Python 3.14+)
pip install -r requirements.txt

# 2. (Optional) Regenerate the datasets — already included, so this is optional
python generate_data.py

# 3. Run the app
python -m streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@customerlens.com | admin123 |
| Analyst | analyst@customerlens.com | analyst123 |
| Manager | manager@customerlens.com | manager123 |
| Viewer | viewer@customerlens.com | viewer123 |

---

## 🎨 Major UI/UX Updates (v3)

✅ **Login Page — Professional, Role-Aware, No White Box**
- Removed the white box container artifact — clean, centered design
- Demo credentials displayed as an info box (not a "Show Demo" button) to look professional
- Role-based signup: users see what each role unlocks when they select it
- Role-specific welcome messages (👑 Admin, 📊 Analyst, 💼 Manager, 👁️ Viewer)
- Improved validation: 6-character password minimum, better form styling

✅ **Sidebar Navigation — 11 Pages, Icon + Label**
- Every nav item shows icon AND descriptive label ("🏠 Home", "🎯 Insights", "🧹 Data Studio")
- **New: 🎯 Business Insights page** — AI-generated smart recommendations
- Active page highlighted in coral

✅ **Topbar — Fully Functional**
- 🔍 **Search** → jumps to Data Explorer with query pre-filled
- 🔔 **Notifications** → live alerts (out-of-stock, low-stock, negative reviews)
- ❓ **Help** → quick reference guide
- 👤 **Profile** → edit name/department or log out


## 📊 Pages

- **Home** — company-wide KPIs (sales, customers, orders, profit), monthly trend, category order volume
- **Customer Analytics** — age/gender/state breakdown, K-Means segments (Gold/Silver/Bronze), top 10 customers
- **Sales Dashboard** — daily/monthly/yearly trend toggle, category sales, profit vs cost, sales by city
- **Product Analytics** — best/worst sellers, stock alerts, rating distribution, category mix
- **Marketing Dashboard** — payment method mix, acquisition trend, simulated campaign ROI (clearly labeled as illustrative, since no campaign dataset exists in the source data)
- **Business Insights** *(new)* — AI-generated smart recommendations: top revenue drivers, churn risks, inventory alerts, VIP retention, quality concerns, cross-sell opportunities, growth momentum
- **AI Predictions** — 5 tabs:
  1. Customer Segmentation (K-Means on RFM) — now with a **segment pie chart + Frequency-vs-Monetary scatter plot**, plus estimated Customer Lifetime Value lookup
  2. Churn Prediction (Random Forest) with risk % — automatically drops duplicate/incomplete rows before training
  3. Product Recommendations (Nearest Neighbors, co-purchase based)
  4. Sales Forecast (Linear Regression, 1–6 months ahead)
  5. Review Sentiment Analysis (TextBlob) + a live text box to try your own review
- **Data Explorer** *(new)* — pick any of the 8 core datasets, full-table search across all columns, per-column filters (numeric range / date range / category multiselect), and a download button for whatever you're currently viewing. The topbar's global search box jumps straight here with your query pre-filled.
- **Data Studio** *(new)* — the one tab that combines **Upload → Clean → Analyze → Download**: upload any CSV, see a missing-value/duplicate-row profile, choose a cleaning strategy (drop missing / fill mean-mode, remove duplicates), preview the cleaned result, then download the cleaned CSV or a full analysis Excel workbook.
- **Reports** — a prominent **"Download Everything"** button that bundles all 8 datasets + customer segments + sentiment-scored feedback + KPI summary into one Excel workbook, plus the original focused Excel/PDF/CSV exports
- **Admin Panel** (Admin role only) — user management, custom CSV upload, core-dataset record deletion, login history

## 🧭 Navigation & Topbar

- The **sidebar** now shows an icon **and label** for every page (not icon-only), and highlights the active page in coral.
- The **topbar** is fully functional, not decorative:
  - 🔍 **Search** — type anything and it jumps to Data Explorer with your query already applied.
  - 🔔 **Notifications** — a live popover listing real alerts (out-of-stock products, low-stock warnings, negative reviews needing attention).
  - ❓ **Help** — a quick-reference popover explaining what each page does.
  - 👤 **Profile** (replaces the old sidebar logout icon) — click your name to view your role/department/email, update your name or department, or log out.

---

## 🎨 Major UI/UX Updates (v3)

✅ **Login Page — Professional, Role-Aware, No White Box**
- Removed the white box container artifact — clean, centered design
- Demo credentials displayed as an info box (not a "Show Demo" button) to look professional
- Role-based signup: users see what each role unlocks when they select it
- Role-specific welcome messages (👑 Admin, 📊 Analyst, 💼 Manager, 👁️ Viewer)
- Improved validation: 6-character password minimum, better form styling

✅ **Sidebar Navigation — 11 Pages, Icon + Label**
- Every nav item shows icon AND descriptive label ("🏠 Home", "🎯 Insights", "🧹 Data Studio")
- **New: 🎯 Business Insights page** — AI-generated smart recommendations
- Active page highlighted in coral

✅ **Topbar — Fully Functional**
- 🔍 **Search** → jumps to Data Explorer with query pre-filled
- 🔔 **Notifications** → live alerts (out-of-stock, low-stock, negative reviews)
- ❓ **Help** → quick reference guide
- 👤 **Profile** → edit name/department or log out


## 📊 Pages (details)


---

## 🧠 Machine Learning Notes

- **Segmentation** and **Churn** are both trained live, in-app, from the current
  order history (RFM: Recency, Frequency, Monetary) — there's no pre-baked model
  file, so results update automatically as data changes.
- **Churn labels** are generated with a documented heuristic (customers far more
  inactive than average are treated as "churned" for training purposes) since no
  manually-labelled churn ground truth exists in retail CSV exports. This is
  explained in the code comments in `ml_engine.py` — worth mentioning if your
  mentor asks how ground truth was obtained.
- **Recommendations** use item-item cosine similarity over a customer × product
  purchase matrix (classic collaborative filtering), not just "same category."
- **Forecasting** is intentionally simple (Linear Regression on monthly totals)
  as the brief specified — a good discussion point for "how would you improve
  this?" during your presentation (e.g., swap in Prophet or ARIMA for seasonality).

---

## 🎓 Suggested Presentation Line

> "We built a Mobile Store Customer Insights & Sales Intelligence Platform for
> a simulated 60-store mobile phone retail chain, CustomerLens, selling ten
> phone brands. It centralizes customer, order, product (specs/warranty),
> inventory, and feedback data, and layers five machine learning models —
> K-Means segmentation, Random Forest churn prediction, Nearest-Neighbors product
> recommendations, Linear Regression sales forecasting, and TextBlob sentiment
> analysis — on top of an interactive Streamlit dashboard with role-based access
> control and Excel/PDF reporting."
