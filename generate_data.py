"""
generate_data.py
Generates realistic synthetic CSV datasets for CustomerLens — a mobile phone
retail chain platform selling multiple brands (Samsung, Apple, Xiaomi,
OnePlus, Vivo, Oppo, Realme, Google, Motorola, Nothing) through a network of
retail outlets. Enterprise scale — 50,000 customers and ~250,000 orders
spanning 3 years. Fully vectorized (no per-row Python loops) so it runs in
seconds even at this size. Run once: python generate_data.py
"""
import numpy as np
import pandas as pd
from datetime import datetime
import os
import time

rng = np.random.default_rng(42)
OUT = "data"
os.makedirs(OUT, exist_ok=True)

CITIES_STATES = [
    ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("Delhi", "Delhi"),
    ("Bengaluru", "Karnataka"), ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"),
    ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"), ("Chandigarh", "Punjab"), ("Bhopal", "Madhya Pradesh"),
    ("Patna", "Bihar"), ("Surat", "Gujarat"), ("Nagpur", "Maharashtra"), ("Indore", "Madhya Pradesh"),
    ("Panipat", "Haryana"), ("Rohtak", "Haryana"),
]
CITY_ARR = np.array([c for c, s in CITIES_STATES])
STATE_ARR = np.array([s for c, s in CITIES_STATES])

FIRST_NAMES = ["Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Krishna","Ishaan",
               "Ananya","Diya","Aadhya","Saanvi","Myra","Aarohi","Anika","Riya","Kiara","Navya",
               "Rohan","Karan","Manish","Suresh","Priya","Neha","Pooja","Kavya","Sneha","Meera",
               "Aryan","Kabir","Advik","Dhruv","Yash","Zara","Ira","Anaya","Tara","Amara"]
LAST_NAMES = ["Sharma","Verma","Gupta","Singh","Kumar","Patel","Nair","Iyer","Reddy","Rao",
              "Mehta","Joshi","Chopra","Malhotra","Das","Bose","Pillai","Menon","Kapoor","Agarwal",
              "Bhatt","Trivedi","Saxena","Kulkarni","Desai","Shetty","Bhat","Rana","Chauhan","Mishra"]

# ---------------------------------------------------------------------------
# Mobile phone catalog: real-market-accurate model lines per brand, tagged
# with a price/positioning Category. No random brand x category crossing —
# every model is a real line from that brand.
# ---------------------------------------------------------------------------
CATEGORIES = ["Flagship", "Premium", "Mid-Range", "Budget", "Gaming"]

BRAND_CATALOG = {
    # Every generation from the iPhone X era through today is kept side by
    # side — older stock still sells (and still needs to show up in
    # analytics/inventory), it's just priced and categorized lower than
    # the current flagships.
    "Samsung": [("Galaxy S8", "Mid-Range"), ("Galaxy S9+", "Mid-Range"),
                ("Galaxy Note 9", "Premium"), ("Galaxy S10+", "Premium"),
                ("Galaxy Note 10+", "Flagship"), ("Galaxy A50", "Budget"),
                ("Galaxy S20 Ultra", "Flagship"), ("Galaxy Note 20 Ultra", "Flagship"),
                ("Galaxy A51", "Budget"), ("Galaxy S21 Ultra", "Flagship"),
                ("Galaxy A32", "Budget"), ("Galaxy S22 Ultra", "Flagship"),
                ("Galaxy A53 5G", "Mid-Range"), ("Galaxy S23 Ultra", "Flagship"),
                ("Galaxy Z Fold5", "Flagship"), ("Galaxy A54 5G", "Mid-Range"),
                ("Galaxy S24 Ultra", "Flagship"), ("Galaxy S24+", "Flagship"),
                ("Galaxy A55 5G", "Mid-Range"), ("Galaxy S25 Ultra", "Flagship"),
                ("Galaxy S25+", "Flagship"), ("Galaxy S25", "Premium"),
                ("Galaxy Z Fold7", "Flagship"), ("Galaxy Z Flip7", "Premium"),
                ("Galaxy A56 5G", "Mid-Range"), ("Galaxy A36 5G", "Mid-Range"),
                ("Galaxy M56 5G", "Budget"), ("Galaxy F56 5G", "Budget")],
    "Apple": [("iPhone X", "Premium"), ("iPhone XR", "Mid-Range"), ("iPhone XS", "Premium"),
              ("iPhone 11", "Mid-Range"), ("iPhone 11 Pro Max", "Premium"),
              ("iPhone SE (2nd Gen)", "Budget"), ("iPhone 12 Mini", "Mid-Range"),
              ("iPhone 12", "Premium"), ("iPhone 12 Pro Max", "Flagship"),
              ("iPhone 13", "Premium"), ("iPhone 13 Pro Max", "Flagship"),
              ("iPhone SE (3rd Gen)", "Budget"), ("iPhone 14", "Premium"),
              ("iPhone 14 Pro Max", "Flagship"), ("iPhone 15", "Premium"),
              ("iPhone 15 Pro Max", "Flagship"), ("iPhone 16", "Premium"),
              ("iPhone 16 Pro Max", "Flagship"), ("iPhone 16e", "Mid-Range"),
              ("iPhone 17", "Premium"), ("iPhone 17 Pro Max", "Flagship"),
              ("iPhone 17 Pro", "Flagship"), ("iPhone 17 Air", "Premium"),
              ("iPhone SE (4th Gen)", "Budget")],
    "Xiaomi": [("Mi 8", "Mid-Range"), ("Redmi Note 7 Pro", "Budget"), ("Mi 9", "Premium"),
               ("Redmi Note 8 Pro", "Budget"), ("Mi 10", "Premium"), ("Redmi Note 9 Pro", "Budget"),
               ("Mi 11", "Flagship"), ("Redmi Note 10 Pro", "Mid-Range"),
               ("Xiaomi 12", "Flagship"), ("Redmi Note 11 Pro+", "Mid-Range"),
               ("POCO F4", "Gaming"), ("Xiaomi 13", "Flagship"),
               ("Redmi Note 12 Pro+", "Mid-Range"), ("POCO X5 Pro", "Gaming"),
               ("Xiaomi 14", "Flagship"), ("Redmi Note 13 Pro+", "Mid-Range"),
               ("POCO X6 Pro", "Gaming"), ("Xiaomi 15 Ultra", "Flagship"),
               ("Xiaomi 15", "Premium"), ("Redmi Note 14 Pro+", "Mid-Range"),
               ("Redmi 14C", "Budget"), ("POCO X7 Pro", "Gaming"), ("POCO F7", "Gaming")],
    "OnePlus": [("OnePlus 5T", "Mid-Range"), ("OnePlus 6T", "Premium"),
                ("OnePlus 7 Pro", "Flagship"), ("OnePlus 7T", "Premium"),
                ("OnePlus 8", "Premium"), ("OnePlus 8T", "Premium"),
                ("OnePlus 9", "Premium"), ("OnePlus 9 Pro", "Flagship"),
                ("OnePlus Nord 2", "Mid-Range"), ("OnePlus 10 Pro", "Flagship"),
                ("OnePlus 10R", "Gaming"), ("OnePlus 11", "Flagship"),
                ("OnePlus Nord 3", "Mid-Range"), ("OnePlus 12", "Flagship"),
                ("OnePlus 12R", "Gaming"), ("OnePlus Nord 4", "Mid-Range"),
                ("OnePlus 13", "Flagship"), ("OnePlus 13R", "Premium"),
                ("OnePlus Nord CE5", "Mid-Range")],
    "Vivo": [("Vivo V9", "Mid-Range"), ("Vivo V15 Pro", "Mid-Range"), ("Vivo V17", "Mid-Range"),
             ("Vivo X50", "Premium"), ("Vivo V20", "Mid-Range"), ("Vivo X60 Pro", "Flagship"),
             ("Vivo V21", "Mid-Range"), ("Vivo X70 Pro", "Flagship"), ("Vivo V23", "Mid-Range"),
             ("Vivo X80 Pro", "Flagship"), ("Vivo V25", "Mid-Range"), ("Vivo X90 Pro", "Flagship"),
             ("Vivo V29", "Premium"), ("Vivo X100 Pro", "Flagship"), ("Vivo V40", "Premium"),
             ("Vivo X200 Pro", "Flagship"), ("Vivo T4", "Budget"), ("Vivo Y300", "Mid-Range"),
             ("Vivo Y29", "Budget")],
    "Oppo": [("Oppo F9", "Mid-Range"), ("Oppo Reno 2", "Mid-Range"), ("Oppo Find X2", "Flagship"),
             ("Oppo Reno 4", "Mid-Range"), ("Oppo Find X3 Pro", "Flagship"),
             ("Oppo Reno 6", "Mid-Range"), ("Oppo Find X5 Pro", "Flagship"),
             ("Oppo Reno 8", "Mid-Range"), ("Oppo Find X6 Pro", "Flagship"),
             ("Oppo Reno10 Pro", "Premium"), ("Oppo Find X7", "Flagship"),
             ("Oppo Reno13 Pro", "Premium"), ("Oppo Find X8", "Flagship"),
             ("Oppo A5 Pro", "Mid-Range"), ("Oppo A5", "Budget")],
    "Realme": [("Realme 1", "Budget"), ("Realme 2 Pro", "Budget"), ("Realme X", "Mid-Range"),
               ("Realme 5 Pro", "Budget"), ("Realme X2 Pro", "Premium"),
               ("Realme 6 Pro", "Mid-Range"), ("Realme X7 Pro", "Premium"),
               ("Realme 8 Pro", "Mid-Range"), ("Realme GT", "Flagship"),
               ("Realme 9 Pro+", "Mid-Range"), ("Realme GT Neo 3", "Gaming"),
               ("Realme 10 Pro+", "Mid-Range"), ("Realme GT Neo 5", "Gaming"),
               ("Realme 12 Pro+", "Mid-Range"), ("Realme GT 6", "Flagship"),
               ("Realme 14 Pro+", "Mid-Range"), ("Realme GT 7", "Flagship"),
               ("Realme GT Neo 7", "Gaming"), ("Realme Narzo 80", "Budget"),
               ("Realme C75", "Budget")],
    "Google": [("Pixel 3", "Premium"), ("Pixel 3a", "Budget"), ("Pixel 4", "Premium"),
               ("Pixel 4a", "Budget"), ("Pixel 5", "Premium"), ("Pixel 6", "Premium"),
               ("Pixel 6 Pro", "Flagship"), ("Pixel 7", "Premium"), ("Pixel 7 Pro", "Flagship"),
               ("Pixel 8", "Premium"), ("Pixel 8 Pro", "Flagship"), ("Pixel 9", "Mid-Range"),
               ("Pixel 9a", "Mid-Range"), ("Pixel 10", "Premium"), ("Pixel 10 Pro", "Flagship")],
    "Nothing": [("Nothing Phone (1)", "Premium"), ("Nothing Phone (2)", "Premium"),
                ("Nothing Phone (2a)", "Mid-Range"), ("Nothing Phone (3)", "Premium"),
                ("Nothing Phone (3a)", "Mid-Range")],
    "Motorola": [("Moto G6", "Budget"), ("Moto G7 Power", "Budget"), ("Moto One Vision", "Mid-Range"),
                 ("Moto G8 Power", "Budget"), ("Moto Edge", "Premium"), ("Moto G9 Power", "Budget"),
                 ("Moto Edge 20", "Premium"), ("Moto G60", "Mid-Range"),
                 ("Moto Edge 30 Pro", "Premium"), ("Moto G82", "Mid-Range"),
                 ("Moto Edge 40 Pro", "Premium"), ("Moto G84 5G", "Mid-Range"),
                 ("Moto Edge 50 Pro", "Premium"), ("Moto Razr 40", "Premium"),
                 ("Moto G95 5G", "Mid-Range"), ("Moto Edge 60 Pro", "Premium"),
                 ("Moto Razr 60", "Premium"), ("Moto G45 5G", "Budget")],
}
BRANDS = list(BRAND_CATALOG.keys())

# Rough per-brand chipset flavor, used to make the Processor column feel real.
BRAND_PROCESSORS = {
    "Samsung": ["Snapdragon 8 Elite", "Exynos 2500", "Snapdragon 7 Gen 4",
                "Snapdragon 8 Gen 2", "Exynos 2200", "Exynos 9810", "Snapdragon 845", "Snapdragon 730"],
    "Apple": ["Apple A19 Pro", "Apple A19", "Apple A18", "Apple A17 Pro", "Apple A16 Bionic",
              "Apple A15 Bionic", "Apple A14 Bionic", "Apple A13 Bionic", "Apple A12 Bionic", "Apple A11 Bionic"],
    "Xiaomi": ["Snapdragon 8 Elite", "Dimensity 9400", "Snapdragon 7s Gen 3",
               "Snapdragon 8 Gen 1", "Snapdragon 855", "Snapdragon 660"],
    "OnePlus": ["Snapdragon 8 Elite", "Snapdragon 8s Gen 4", "Dimensity 8350",
                "Snapdragon 888", "Snapdragon 855", "Snapdragon 835"],
    "Vivo": ["Dimensity 9400", "Snapdragon 7 Gen 4", "Dimensity 8350",
             "Snapdragon 865", "Snapdragon 720G", "Snapdragon 675"],
    "Oppo": ["Dimensity 9400", "Dimensity 8350", "Snapdragon 6 Gen 4",
             "Snapdragon 865", "Snapdragon 660", "MediaTek Helio P70"],
    "Realme": ["Snapdragon 8s Elite", "Dimensity 8350", "Snapdragon 5 Gen 1",
               "Snapdragon 778G", "MediaTek Helio P70", "Snapdragon 665"],
    "Google": ["Google Tensor G5", "Google Tensor G4", "Google Tensor G3", "Google Tensor G2",
               "Google Tensor", "Snapdragon 765G"],
    "Nothing": ["Snapdragon 8s Gen 4", "Dimensity 7300 Pro", "Snapdragon 8+ Gen 1"],
    "Motorola": ["Snapdragon 7 Gen 4", "Dimensity 7300", "Snapdragon 6s Gen 4",
                 "Snapdragon 8 Gen 1", "Snapdragon 665", "Snapdragon 632", "MediaTek Helio P35"],
}
COLORS = ["Midnight Black", "Titanium Gray", "Ocean Blue", "Rose Gold", "Silver",
          "Forest Green", "Lavender", "Sunrise Orange", "Graphite", "Cream White"]

PRICE_RANGES = {
    "Flagship": (69999, 159999),
    "Premium": (39999, 69999),
    "Mid-Range": (18999, 39999),
    "Budget": (7999, 18999),
    "Gaming": (24999, 44999),
}
RAM_BY_CAT = {"Flagship": [12, 16], "Premium": [8, 12], "Mid-Range": [6, 8],
              "Budget": [4, 6], "Gaming": [8, 12, 16]}
STORAGE_BY_CAT = {"Flagship": [256, 512, 1024], "Premium": [128, 256],
                   "Mid-Range": [128, 256], "Budget": [64, 128], "Gaming": [128, 256, 512]}
BATTERY_BY_CAT = {"Flagship": (4500, 5500), "Premium": (4200, 5000),
                  "Mid-Range": (4500, 5200), "Budget": (4000, 5000), "Gaming": (5000, 6000)}
CAMERA_BY_CAT = {"Flagship": [50, 108, 200], "Premium": [48, 50, 64],
                 "Mid-Range": [48, 50, 64], "Budget": [13, 48, 50], "Gaming": [50, 64, 108]}
SCREEN_BY_CAT = {"Flagship": (6.5, 6.9), "Premium": (6.4, 6.8), "Mid-Range": (6.5, 6.7),
                  "Budget": (6.4, 6.6), "Gaming": (6.6, 6.9)}

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Cash", "Net Banking", "EMI", "Wallet"]
ROLES = ["Store Manager", "Sales Executive", "Inventory Staff", "Technician / Repair", "Delivery Staff", "Security"]

# ---- Scale: enterprise-size dataset, ~3 years of history ----
N_CUSTOMERS = 50_000
N_STORES = 60
N_PRODUCTS = 600
N_ORDERS = 250_000
N_EMPLOYEES = 500
N_FEEDBACK = 40_000
N_WARRANTY_CLAIMS = 6_000

START = datetime(2023, 7, 1)
END = datetime(2026, 7, 7)  # ~3 years
START_NS, END_NS = np.datetime64(START), np.datetime64(END)


def random_dates(n):
    span_days = (END - START).days
    offsets = rng.integers(0, span_days, size=n)
    return (START_NS + offsets.astype("timedelta64[D]"))


t0 = time.time()

# ---------------- stores.csv ----------------
store_city_idx = rng.integers(0, len(CITIES_STATES), size=N_STORES)
stores_df = pd.DataFrame({
    "StoreID": [f"ST{i:04d}" for i in range(1, N_STORES + 1)],
    "StoreName": [f"CustomerLens Mobile Store, {CITY_ARR[idx]} #{i}" for i, idx in enumerate(store_city_idx, start=1)],
    "City": CITY_ARR[store_city_idx],
    "State": STATE_ARR[store_city_idx],
    "Manager": [f"{FIRST_NAMES[a]} {LAST_NAMES[b]}" for a, b in
                zip(rng.integers(0, len(FIRST_NAMES), N_STORES), rng.integers(0, len(LAST_NAMES), N_STORES))],
    "OpeningDate": pd.to_datetime(random_dates(N_STORES)).strftime("%Y-%m-%d"),
})
stores_df.to_csv(f"{OUT}/stores.csv", index=False)

# ---------------- customers.csv ----------------
cust_city_idx = rng.integers(0, len(CITIES_STATES), size=N_CUSTOMERS)
customers_df = pd.DataFrame({
    "CustomerID": [f"CUST{i:06d}" for i in range(1, N_CUSTOMERS + 1)],
    "Name": [f"{FIRST_NAMES[a]} {LAST_NAMES[b]}" for a, b in
             zip(rng.integers(0, len(FIRST_NAMES), N_CUSTOMERS), rng.integers(0, len(LAST_NAMES), N_CUSTOMERS))],
    "Age": rng.integers(18, 70, size=N_CUSTOMERS),
    "Gender": rng.choice(["M", "F", "O"], size=N_CUSTOMERS, p=[0.48, 0.48, 0.04]),
    "City": CITY_ARR[cust_city_idx],
    "State": STATE_ARR[cust_city_idx],
    "Income": rng.integers(15000, 200000, size=N_CUSTOMERS),
    "SignupDate": pd.to_datetime(random_dates(N_CUSTOMERS)).strftime("%Y-%m-%d"),
})
customers_df.to_csv(f"{OUT}/customers.csv", index=False)

# ---------------- products.csv (phone models) ----------------
brand_idx = rng.integers(0, len(BRANDS), size=N_PRODUCTS)

brand_occurrence = {}
names, cats, brands_list = [], [], []
for b in brand_idx:
    brand = BRANDS[b]
    occ = brand_occurrence.get(brand, 0)
    brand_occurrence[brand] = occ + 1
    line = BRAND_CATALOG[brand]
    model_name, cat = line[occ % len(line)]
    names.append(model_name)
    cats.append(cat)
    brands_list.append(brand)

# Cost/Price driven by category price tier, brand as a mild premium/discount
cost_arr = np.zeros(N_PRODUCTS)
price_arr = np.zeros(N_PRODUCTS)
ram_arr = np.zeros(N_PRODUCTS, dtype=int)
storage_arr = np.zeros(N_PRODUCTS, dtype=int)
battery_arr = np.zeros(N_PRODUCTS, dtype=int)
camera_arr = np.zeros(N_PRODUCTS, dtype=int)
screen_arr = np.zeros(N_PRODUCTS)
processor_arr = []
color_arr = []
warranty_arr = np.zeros(N_PRODUCTS, dtype=int)
network_arr = []

for i, cat in enumerate(cats):
    lo, hi = PRICE_RANGES[cat]
    price_arr[i] = round(rng.uniform(lo, hi), 2)
    cost_arr[i] = round(price_arr[i] / rng.uniform(1.10, 1.28), 2)
    ram_arr[i] = rng.choice(RAM_BY_CAT[cat])
    storage_arr[i] = rng.choice(STORAGE_BY_CAT[cat])
    b_lo, b_hi = BATTERY_BY_CAT[cat]
    battery_arr[i] = rng.integers(b_lo, b_hi)
    camera_arr[i] = rng.choice(CAMERA_BY_CAT[cat])
    s_lo, s_hi = SCREEN_BY_CAT[cat]
    screen_arr[i] = round(rng.uniform(s_lo, s_hi), 1)
    processor_arr.append(rng.choice(BRAND_PROCESSORS[brands_list[i]]))
    color_arr.append(rng.choice(COLORS))
    warranty_arr[i] = int(rng.choice([12, 12, 12, 24], p=[0.55, 0.2, 0.15, 0.10]))
    network_arr.append("4G" if cat == "Budget" and rng.random() < 0.25 else "5G")

products_df = pd.DataFrame({
    "ProductID": [f"P{i:04d}" for i in range(1, N_PRODUCTS + 1)],
    "ProductName": names,
    "Category": cats,
    "Brand": brands_list,
    "Cost": np.round(cost_arr, 2),
    "Price": np.round(price_arr, 2),
    "Stock": rng.integers(0, 400, size=N_PRODUCTS),
    "Rating": np.round(rng.uniform(3.0, 5.0, size=N_PRODUCTS), 1),
    "RAM_GB": ram_arr,
    "Storage_GB": storage_arr,
    "Battery_mAh": battery_arr,
    "CameraMP": camera_arr,
    "ScreenSize_in": screen_arr,
    "Processor": processor_arr,
    "Color": color_arr,
    "Network": network_arr,
    "WarrantyMonths": warranty_arr,
})
# Force a realistic slice of the catalog to be genuinely out of stock (not
# just "got lucky with a low random draw") so Inventory/Alerts pages always
# have real out-of-stock items to show, same as any real retail catalog.
oos_idx = rng.choice(N_PRODUCTS, size=max(1, int(N_PRODUCTS * 0.06)), replace=False)
products_df.loc[oos_idx, "Stock"] = 0
# Disambiguate any (Brand, ProductName) collisions from repeated cycling
dup_mask = products_df.duplicated(subset=["Brand", "ProductName"], keep=False)
if dup_mask.any():
    products_df.loc[dup_mask, "ProductName"] = (
        products_df.loc[dup_mask, "ProductName"] + " (" + products_df.loc[dup_mask, "Color"].str.split().str[0] + ")"
    )
products_df.to_csv(f"{OUT}/products.csv", index=False)

# ---------------- employees.csv ----------------
emp_store_idx = rng.integers(0, N_STORES, size=N_EMPLOYEES)
employees_df = pd.DataFrame({
    "EmployeeID": [f"EMP{i:05d}" for i in range(1, N_EMPLOYEES + 1)],
    "Name": [f"{FIRST_NAMES[a]} {LAST_NAMES[b]}" for a, b in
             zip(rng.integers(0, len(FIRST_NAMES), N_EMPLOYEES), rng.integers(0, len(LAST_NAMES), N_EMPLOYEES))],
    "Role": rng.choice(ROLES, size=N_EMPLOYEES),
    "StoreID": stores_df["StoreID"].values[emp_store_idx],
    "Salary": rng.integers(15000, 80000, size=N_EMPLOYEES),
    "JoinDate": pd.to_datetime(random_dates(N_EMPLOYEES)).strftime("%Y-%m-%d"),
})
employees_df.to_csv(f"{OUT}/employees.csv", index=False)

# ---------------- orders.csv ----------------
cust_weights = rng.gamma(shape=2.0, scale=1.0, size=N_CUSTOMERS)
cust_weights = cust_weights / cust_weights.sum()
order_cust_idx = rng.choice(N_CUSTOMERS, size=N_ORDERS, p=cust_weights)
order_store_idx = rng.integers(0, N_STORES, size=N_ORDERS)

# Correlate what a customer buys with what they can actually afford. Before,
# order_prod_idx was picked fully at random from all 600 phones regardless
# of the customer's Income, so a customer earning ~15k/month could easily
# rack up several ~1.5L phones and end up spending way more than their
# income could plausibly support. Now customers and products are each split
# into 5 tiers (by Income / Price), and each order draws mostly from the
# buying customer's own tier — with some spillover into a neighbouring tier
# (saving up for an upgrade, buying a budget phone as a gift, etc.) and a
# small "wildcard" chance capped at 2 tiers away (occasional splurge/bargain,
# but a bottom-tier earner still can't land on the flagship tier) — so
# spending stays broadly realistic relative to income while still having
# natural variety.
N_TIERS = 5

# Convert qcut results explicitly to NumPy integer arrays.
# This avoids Pandas ExtensionArray/Categorical typing issues in Pylance.
cust_income_tier = np.asarray(
    pd.qcut(customers_df["Income"], N_TIERS, labels=False),
    dtype=np.int64,
)

prod_price_tier = np.asarray(
    pd.qcut(products_df["Price"], N_TIERS, labels=False),
    dtype=np.int64,
)

tier_to_products = [
    np.flatnonzero(prod_price_tier == t)
    for t in range(N_TIERS)
]

order_cust_tier = cust_income_tier[order_cust_idx].astype(np.int64)

roll = rng.random(N_ORDERS)

same_tier = order_cust_tier.copy()

adjacent_offset = rng.choice(
    np.array([-1, 1], dtype=np.int64),
    size=N_ORDERS,
)

adjacent_tier = np.clip(
    order_cust_tier + adjacent_offset,
    0,
    N_TIERS - 1,
).astype(np.int64)

wildcard_offset = rng.integers(
    -2,
    3,
    size=N_ORDERS,
    dtype=np.int64,
)

wildcard_tier = np.clip(
    order_cust_tier + wildcard_offset,
    0,
    N_TIERS - 1,
).astype(np.int64)

# 65% same tier, 25% adjacent tier, 10% wildcard tier.
order_prod_tier = np.where(
    roll < 0.65,
    same_tier,
    np.where(
        roll < 0.90,
        adjacent_tier,
        wildcard_tier,
    ),
).astype(np.int64)

order_prod_idx = np.empty(N_ORDERS, dtype=int)
for t in range(N_TIERS):
    mask = order_prod_tier == t
    n = int(mask.sum())
    if n:
        order_prod_idx[mask] = rng.choice(tier_to_products[t], size=n)

# Quantity: phones are rarely bought in bulk, and buying 2+ units gets rarer
# the pricier the phone is (nobody casually buys two flagships in one order).
qty_arr = np.where(
    order_prod_tier >= 3,
    1,
    rng.choice([1, 2], size=N_ORDERS, p=[0.75, 0.25]),
)

price_arr_full = products_df["Price"].values[order_prod_idx]
total_arr = np.round(qty_arr * price_arr_full, 2)

orders_df = pd.DataFrame({
    "OrderID": [f"ORD{i:07d}" for i in range(1, N_ORDERS + 1)],
    "CustomerID": customers_df["CustomerID"].values[order_cust_idx],
    "Date": pd.to_datetime(random_dates(N_ORDERS)),
    "ProductID": products_df["ProductID"].values[order_prod_idx],
    "Quantity": qty_arr,
    "Price": price_arr_full,
    "TotalAmount": total_arr,
    "StoreID": stores_df["StoreID"].values[order_store_idx],
    # Historical orders are, well, history — all treated as completed sales.
    # New orders added via the Admin "Add New Data" wizard can pick a real
    # status (Processing/Cancelled/Returned/Completed).
    "OrderStatus": "Completed",
})
orders_df = orders_df.sort_values("Date").reset_index(drop=True)
orders_df["Date"] = orders_df["Date"].dt.strftime("%Y-%m-%d")
orders_df.to_csv(f"{OUT}/orders.csv", index=False)

# ---------------- payments.csv ----------------
payments_df = pd.DataFrame({
    "PaymentID": [f"PAY{i:07d}" for i in range(1, N_ORDERS + 1)],
    "OrderID": orders_df["OrderID"].values,
    "CustomerID": orders_df["CustomerID"].values,
    "Amount": orders_df["TotalAmount"].values,
    "Method": rng.choice(PAYMENT_METHODS, size=N_ORDERS),
    "Date": orders_df["Date"].values,
})
payments_df.to_csv(f"{OUT}/payments.csv", index=False)

# ---------------- feedback.csv ----------------
POSITIVE = ["Excellent phone, camera quality is amazing", "Super fast delivery and genuine product",
            "Great value for money, battery life is superb", "Loved the display and performance",
            "Very happy with the purchase, smooth experience", "Build quality and after-sales support are great"]
NEUTRAL = ["Phone is okay, expected slightly better battery", "Average performance, heats up a bit while gaming",
           "It's fine, delivery took a couple of extra days"]
NEGATIVE = ["Received a scratched unit, very disappointed", "Battery drains too fast, not worth the price",
            "Phone hung frequently, had to get it exchanged", "Poor packaging, box was damaged on arrival",
            "Warranty claim process was very slow"]

fb_cust_idx = rng.integers(0, N_CUSTOMERS, size=N_FEEDBACK)
fb_prod_idx = rng.integers(0, N_PRODUCTS, size=N_FEEDBACK)
fb_bucket = rng.choice(["pos", "neu", "neg"], size=N_FEEDBACK, p=[0.6, 0.18, 0.22])

fb_review = np.empty(N_FEEDBACK, dtype=object)
fb_rating = np.empty(N_FEEDBACK, dtype=int)

pos_mask, neu_mask, neg_mask = fb_bucket == "pos", fb_bucket == "neu", fb_bucket == "neg"
fb_review[pos_mask] = rng.choice(POSITIVE, size=pos_mask.sum())
fb_rating[pos_mask] = rng.integers(4, 6, size=pos_mask.sum())
fb_review[neu_mask] = rng.choice(NEUTRAL, size=neu_mask.sum())
fb_rating[neu_mask] = 3
fb_review[neg_mask] = rng.choice(NEGATIVE, size=neg_mask.sum())
fb_rating[neg_mask] = rng.integers(1, 3, size=neg_mask.sum())

feedback_df = pd.DataFrame({
    "FeedbackID": [f"FB{i:06d}" for i in range(1, N_FEEDBACK + 1)],
    "CustomerID": customers_df["CustomerID"].values[fb_cust_idx],
    "ProductID": products_df["ProductID"].values[fb_prod_idx],
    "Review": fb_review,
    "Rating": fb_rating,
    "Date": pd.to_datetime(random_dates(N_FEEDBACK)).strftime("%Y-%m-%d"),
})
feedback_df.to_csv(f"{OUT}/feedback.csv", index=False)

# ---------------- inventory.csv (store-wise stock) ----------------
inv_rows = []
for store_id in stores_df["StoreID"]:
    n_sample = min(80, N_PRODUCTS)
    sample_idx = rng.choice(N_PRODUCTS, size=n_sample, replace=False)
    inv_rows.append(pd.DataFrame({
        "StoreID": store_id,
        "ProductID": products_df["ProductID"].values[sample_idx],
        "StockLevel": rng.integers(0, 250, size=n_sample),
        "ReorderLevel": rng.integers(10, 40, size=n_sample),
    }))
inventory_df = pd.concat(inv_rows, ignore_index=True)
# Products already flagged globally out-of-stock (see oos_idx above) should
# read as out-of-stock at store level too, not just in the master catalog.
oos_product_ids = set(products_df.loc[oos_idx, "ProductID"])
inventory_df.loc[inventory_df["ProductID"].isin(oos_product_ids), "StockLevel"] = 0
inventory_df.to_csv(f"{OUT}/inventory.csv", index=False)

# ---------------- warranty_claims.csv ----------------
ISSUES = ["Battery draining fast", "Screen flickering", "Charging port not working",
          "Camera not focusing", "Software update issue", "Speaker/mic not working",
          "Overheating during use", "Physical damage - screen crack", "Network/SIM issue",
          "Water damage"]
STATUSES = ["Resolved", "In Progress", "Pending Pickup", "Rejected - Out of Warranty", "Replaced"]

wc_cust_idx = rng.integers(0, N_CUSTOMERS, size=N_WARRANTY_CLAIMS)
wc_prod_idx = rng.integers(0, N_PRODUCTS, size=N_WARRANTY_CLAIMS)
wc_store_idx = rng.integers(0, N_STORES, size=N_WARRANTY_CLAIMS)
claim_dates = pd.to_datetime(random_dates(N_WARRANTY_CLAIMS))
warranty_months = products_df["WarrantyMonths"].values[wc_prod_idx]
# purchase date is somewhere before the claim date, within the warranty window
days_before = rng.integers(1, np.maximum(warranty_months * 30, 30))
purchase_dates = claim_dates - pd.to_timedelta(days_before, unit="D")

warranty_df = pd.DataFrame({
    "ClaimID": [f"WC{i:06d}" for i in range(1, N_WARRANTY_CLAIMS + 1)],
    "CustomerID": customers_df["CustomerID"].values[wc_cust_idx],
    "ProductID": products_df["ProductID"].values[wc_prod_idx],
    "StoreID": stores_df["StoreID"].values[wc_store_idx],
    "PurchaseDate": purchase_dates.strftime("%Y-%m-%d"),
    "ClaimDate": claim_dates.strftime("%Y-%m-%d"),
    "Issue": rng.choice(ISSUES, size=N_WARRANTY_CLAIMS),
    "Status": rng.choice(STATUSES, size=N_WARRANTY_CLAIMS, p=[0.45, 0.15, 0.15, 0.1, 0.15]),
    "WarrantyMonths": warranty_months,
})
warranty_df = warranty_df.sort_values("ClaimDate").reset_index(drop=True)
warranty_df.to_csv(f"{OUT}/warranty_claims.csv", index=False)

elapsed = time.time() - t0
print(f"All datasets generated in ./data/ in {elapsed:.1f}s")
for f in os.listdir(OUT):
    path = os.path.join(OUT, f)
    print(f" - {f}: {sum(1 for _ in open(path)) - 1:,} rows")
