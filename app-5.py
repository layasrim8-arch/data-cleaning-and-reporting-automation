# ============================================================
# Data Cleaning & Reporting Automation  (Thiranex Task 4)
# Everything lives in this one file: sample data, cleaning,
# analysis, dashboard, charts, filters, insights, downloads.
# ============================================================
import io
import re
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Data Cleaning & Reporting Automation", page_icon="🧹", layout="wide")

# ---------- Page styling (CSS inside Python, no extra files) ----------
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
.main-title {font-size: 2.3rem; font-weight: 800; color: #1f3a93; margin-bottom: 0;}
.sub-title {font-size: 1.1rem; color: #6b7280; margin-bottom: 1.2rem;}
.kpi {background: linear-gradient(135deg,#eef2ff,#ffffff); border-left: 5px solid #4f46e5;
      border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.12);}
.kpi .label {font-size: .8rem; color: #6b7280; text-transform: uppercase; letter-spacing: .04em;}
.kpi .value {font-size: 1.5rem; font-weight: 700; color: #111827; word-wrap: break-word;}
.insight {background:#f0fdf4; border-left:5px solid #16a34a; color:#14532d;
          padding:10px 14px; border-radius:8px; margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

REQUIRED_COLS = ["Customer ID", "Customer Name", "Age", "Gender", "City", "Product",
                 "Quantity", "Price", "Order Date", "Payment Method", "Sales", "Email"]


def kpi_cards(items, per_row=4):
    """Show a list of (label, value) pairs as KPI cards."""
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, (label, value) in zip(cols, items[i:i + per_row]):
            col.markdown(f'<div class="kpi"><div class="label">{label}</div>'
                         f'<div class="value">{value}</div></div>', unsafe_allow_html=True)


# ---------- 1. Built-in messy sample dataset ----------
def generate_sample_data(n=300, seed=42):
    rng = np.random.default_rng(seed)
    first = ["John", "Mary", "Ali", "Sara", "David", "Priya", "Chen", "Emma", "Omar", "Lucy", "Raj", "Anna"]
    last = ["Smith", "Khan", "Patel", "Brown", "Lee", "Garcia", "Wilson", "Taylor", "Singh", "Davis"]
    products = {"Laptop": 900, "Phone": 600, "Tablet": 350, "Headphones": 80, "Monitor": 220, "Keyboard": 45}
    cities = ["New York", "NYC", "new york ", "Los Angeles", "LA", "los angeles", "Chicago", "chicago", "Houston", "HOUSTON", "Miami"]
    genders = ["Male", "male", "M", "m", "Female", "female", "F", "f", " MALE ", "Female "]
    pays = ["Credit Card", "credit card", "Debit Card", "PayPal", "paypal", "Cash", "CASH", "UPI"]
    dates = pd.date_range("2024-01-01", "2024-12-31", periods=n)
    rows = []
    for i in range(n):
        prod = rng.choice(list(products))
        qty = int(rng.integers(1, 6))
        price = round(products[prod] * rng.uniform(0.9, 1.1), 2)
        d = dates[i]
        fmt = rng.choice(["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%b %d, %Y"])
        name = f"{rng.choice(first)} {rng.choice(last)}"
        email = f"{name.lower().replace(' ', '.')}@example.com"
        if rng.random() < 0.08:
            email = rng.choice(["not-an-email", "john@@mail", "user.example.com", "abc@", "@nouser.com"])
        rows.append({
            "Customer ID": f"C{1000 + i}", "Customer Name": rng.choice(["  ", ""]) + name if rng.random() < 0.1 else name,
            "Age": int(rng.integers(18, 70)), "Gender": rng.choice(genders), "City": rng.choice(cities),
            "Product": rng.choice([prod, prod.lower(), prod.upper(), " " + prod]), "Quantity": qty, "Price": price,
            "Order Date": d.strftime(fmt), "Payment Method": rng.choice(pays), "Sales": round(qty * price, 2), "Email": email})
    df = pd.DataFrame(rows)
    # Inject missing values (including numeric ones)
    for col, frac in [("Age", .05), ("Gender", .04), ("City", .04), ("Quantity", .04), ("Price", .04),
                      ("Sales", .05), ("Payment Method", .03), ("Email", .03), ("Order Date", .02)]:
        df.loc[rng.choice(n, int(n * frac), replace=False), col] = np.nan
    df.loc[rng.choice(n, 3, replace=False), "Age"] = [-5, 250, 0]  # invalid ages
    # Inject duplicate rows
    df = pd.concat([df, df.sample(15, random_state=1)], ignore_index=True)
    return df.sample(frac=1, random_state=3).reset_index(drop=True)


# ---------- 2. Data cleaning ----------
CITY_MAP = {"nyc": "New York", "ny": "New York", "new york city": "New York", "la": "Los Angeles",
            "l.a.": "Los Angeles", "chi": "Chicago", "hou": "Houston"}
GENDER_MAP = {"m": "Male", "male": "Male", "man": "Male", "f": "Female", "female": "Female", "woman": "Female"}
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def clean_data(raw):
    """Returns (cleaned_df, summary_dict). Works on a copy; never modifies the original."""
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    text_cols = ["Customer ID", "Customer Name", "Gender", "City", "Product", "Payment Method", "Email"]
    num_cols = ["Age", "Quantity", "Price", "Sales"]
    summary = {"Rows Before Cleaning": len(raw)}

    # Trim spaces, collapse repeated spaces, turn blanks into NaN
    for c in text_cols:
        s = df[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        df[c] = s.replace({"": pd.NA, "nan": pd.NA, "none": pd.NA, "None": pd.NA, "NaN": pd.NA}).astype(object)
        df[c] = df[c].where(df[c].notna(), np.nan)

    # Standardize text: Title Case, gender and city mapping
    for c in ["Customer Name", "City", "Product", "Payment Method"]:
        df[c] = df[c].map(lambda x: x.title() if isinstance(x, str) else x)
    df["Gender"] = df["Gender"].map(lambda x: GENDER_MAP.get(x.lower(), np.nan) if isinstance(x, str) else x)
    df["City"] = df["City"].map(lambda x: CITY_MAP.get(x.lower(), x) if isinstance(x, str) else x)
    df["Email"] = df["Email"].map(lambda x: x.lower() if isinstance(x, str) else x)

    # Convert numeric columns (bad text becomes NaN) and flag impossible values as invalid
    invalid = 0
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    bad = {"Age": (df["Age"] <= 0) | (df["Age"] > 100), "Quantity": df["Quantity"] <= 0,
           "Price": df["Price"] <= 0, "Sales": df["Sales"] < 0}
    for c, mask in bad.items():
        invalid += int(mask.sum())
        df.loc[mask, c] = np.nan

    # Standardize dates (mixed formats supported)
    try:
        df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce", format="mixed")
    except (TypeError, ValueError):
        df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    invalid += int((df["Order Date"].isna() & raw["Order Date"].notna()).sum())

    # Email validation: invalid ones are flagged, not deleted
    df["Email Status"] = df["Email"].map(lambda x: "Valid" if isinstance(x, str) and EMAIL_RE.match(x) else "Invalid")
    invalid_emails = int(((df["Email Status"] == "Invalid") & df["Email"].notna()).sum())
    invalid += invalid_emails

    # Remove duplicates AFTER standardizing (so "john" and "John " match)
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    summary["Duplicates Removed"] = before - len(df)

    # Fill missing values: median for numbers, mode for categories
    missing_total = int(df.drop(columns=["Email Status"]).isna().sum().sum())
    for c in num_cols:
        df[c] = df[c].fillna(df[c].median())
    # Sales can be rebuilt from Quantity x Price where the original was missing/invalid
    for c in ["Age", "Quantity"]:
        df[c] = df[c].round().astype(int)
    for c in ["Customer ID", "Customer Name", "Gender", "City", "Product", "Payment Method"]:
        mode = df[c].mode()
        df[c] = df[c].fillna(mode.iloc[0] if len(mode) else "Unknown")
    df["Email"] = df["Email"].fillna("Not Provided")
    if df["Order Date"].notna().any():
        df["Order Date"] = df["Order Date"].fillna(df["Order Date"].dropna().median())
    df["Order Date"] = pd.to_datetime(df["Order Date"]).dt.normalize()
    df["Price"] = df["Price"].round(2)
    df["Sales"] = df["Sales"].round(2)

    summary["Rows After Cleaning"] = len(df)
    summary["Missing Values Handled"] = missing_total
    summary["Invalid Values Detected"] = invalid
    summary["Invalid Emails"] = invalid_emails
    return df, summary


# ---------- 3. Analysis helpers ----------
def compute_kpis(df):
    top = lambda col: df.groupby(col)["Sales"].sum().idxmax()
    return {
        "Total Sales": f"${df['Sales'].sum():,.2f}",
        "Total Orders": f"{len(df):,}",
        "Average Order Value": f"${df['Sales'].mean():,.2f}",
        "Total Quantity Sold": f"{int(df['Quantity'].sum()):,}",
        "Number of Customers": f"{df['Customer ID'].nunique():,}",
        "Number of Products": f"{df['Product'].nunique():,}",
        "Top Product": top("Product"),
        "Top City": top("City"),
        "Most Used Payment Method": df["Payment Method"].mode().iloc[0],
    }


def make_insights(df):
    """Insights are built from the (filtered) data, nothing is hardcoded."""
    ps = df.groupby("Product")["Sales"].sum()
    cs = df.groupby("City")["Sales"].sum()
    monthly = df.groupby(df["Order Date"].dt.to_period("M"))["Sales"].sum()
    pay = df["Payment Method"].value_counts()
    gen = df["Gender"].value_counts()
    qty = df.groupby("Product")["Quantity"].sum()
    out = [
        f"{ps.idxmax()} generated the highest sales (${ps.max():,.2f}, {ps.max() / ps.sum():.1%} of total).",
        f"{ps.idxmin()} generated the lowest sales (${ps.min():,.2f}).",
        f"{cs.idxmax()} had the highest sales among cities (${cs.max():,.2f}).",
        f"Payment method '{pay.idxmax()}' was used most frequently ({pay.max()} orders).",
        f"{qty.idxmax()} sold the most units ({int(qty.max()):,}).",
        f"{gen.idxmax()} customers placed the most orders ({gen.max() / gen.sum():.1%} of orders).",
        f"The best sales month was {monthly.idxmax()} (${monthly.max():,.2f}); the weakest was {monthly.idxmin()} (${monthly.min():,.2f}).",
        f"The average order value is ${df['Sales'].mean():,.2f}.",
    ]
    return out


def build_excel(clean_df, summary, df, kpis, insights):
    """Creates the 4-sheet Excel report in memory and returns bytes."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        x = clean_df.copy()
        x["Order Date"] = x["Order Date"].dt.strftime("%Y-%m-%d")
        x.to_excel(writer, sheet_name="Cleaned Data", index=False)
        pd.DataFrame(list(summary.items()), columns=["Metric", "Value"]).to_excel(writer, sheet_name="Cleaning Summary", index=False)
        pd.DataFrame(list(kpis.items()), columns=["Metric", "Value"]).to_excel(writer, sheet_name="Sales Summary", index=False)
        row = len(kpis) + 3
        df.groupby("Product")["Sales"].sum().sort_values(ascending=False).reset_index().to_excel(
            writer, sheet_name="Sales Summary", index=False, startrow=row)
        df.groupby("City")["Sales"].sum().sort_values(ascending=False).reset_index().to_excel(
            writer, sheet_name="Sales Summary", index=False, startrow=row, startcol=3)
        pd.DataFrame({"Insight": insights}).to_excel(writer, sheet_name="Insights", index=False)
        for ws in writer.book.worksheets:  # widen columns
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(len(str(c.value or "")) for c in col) + 3)
    return buf.getvalue()


def load_uploaded(file):
    """Reads CSV/Excel safely. Returns (df, error_message)."""
    try:
        name = file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(file)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file)
        else:
            return None, "Unsupported file type. Please upload a .csv or .xlsx file."
    except pd.errors.EmptyDataError:
        return None, "The uploaded file is empty."
    except Exception as e:
        return None, f"Could not read the file (invalid or corrupted): {e}"
    if df.empty:
        return None, "The uploaded file has no data rows."
    return df, None


# ============================================================
# APP LAYOUT
# ============================================================
st.markdown('<div class="main-title">Data Cleaning & Reporting Automation</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Automated Data Preprocessing, Analysis & Reporting</div>', unsafe_allow_html=True)

# ---------- Data Input ----------
st.header("📂 Data Input")
source = st.radio("Choose data source", ["Use Built-in Sample Dataset", "Upload CSV or Excel file"], horizontal=True)
raw = None
if source.startswith("Use"):
    raw = generate_sample_data()
    st.info("Using the automatically generated messy sample dataset.")
else:
    up = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx", "xls"])
    if up is None:
        st.warning("Please upload a file, or switch to the built-in sample dataset.")
    else:
        raw, err = load_uploaded(up)
        if err:
            st.error(err)
            raw = None
        else:
            raw.columns = [str(c).strip() for c in raw.columns]
            missing_cols = [c for c in REQUIRED_COLS if c not in raw.columns]
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                raw = None
if raw is None:
    st.stop()

# ---------- Data Preview (before cleaning) ----------
st.header("🔍 Data Preview")
blank_as_nan = raw.replace(r"^\s*$", np.nan, regex=True)
kpi_cards([("Total Rows", f"{len(raw):,}"), ("Total Columns", len(raw.columns)),
           ("Missing Values", f"{int(blank_as_nan.isna().sum().sum()):,}"),
           ("Duplicate Rows", f"{int(raw.duplicated().sum()):,}")])
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader("Original Dataset")
    st.dataframe(raw, use_container_width=True, height=300)
with c2:
    st.subheader("Data Types & Missing")
    st.dataframe(pd.DataFrame({"Type": raw.dtypes.astype(str), "Missing": blank_as_nan.isna().sum()}),
                 use_container_width=True, height=300)

# ---------- Data Cleaning ----------
st.header("🧹 Data Cleaning")
try:
    clean, summary = clean_data(raw[REQUIRED_COLS])
except Exception as e:
    st.error(f"Cleaning failed because of invalid data: {e}")
    st.stop()
if clean.empty:
    st.error("The dataset is empty after cleaning.")
    st.stop()
st.success("Cleaning steps applied: duplicates removed, spaces trimmed, text/gender/city standardized, "
           "missing values filled (median/mode), emails validated, dates standardized, numbers converted.")

# ---------- Cleaning Summary ----------
st.header("📊 Cleaning Summary")
kpi_cards([(k, f"{v:,}") for k, v in summary.items()], per_row=5)
st.dataframe(pd.DataFrame(list(summary.items()), columns=["Metric", "Value"]), use_container_width=True, hide_index=True)
st.subheader("Cleaned Dataset")
st.dataframe(clean, use_container_width=True, height=300)
st.download_button("⬇️ Download Cleaned Data", clean.to_csv(index=False).encode("utf-8"),
                   "cleaned_data.csv", "text/csv")

# ---------- Sidebar filters ----------
st.sidebar.header("🎛️ Filters")
f_city = st.sidebar.multiselect("City", sorted(clean["City"].unique()), default=sorted(clean["City"].unique()))
f_prod = st.sidebar.multiselect("Product", sorted(clean["Product"].unique()), default=sorted(clean["Product"].unique()))
f_gen = st.sidebar.multiselect("Gender", sorted(clean["Gender"].unique()), default=sorted(clean["Gender"].unique()))
f_pay = st.sidebar.multiselect("Payment Method", sorted(clean["Payment Method"].unique()),
                               default=sorted(clean["Payment Method"].unique()))
dmin, dmax = clean["Order Date"].min().date(), clean["Order Date"].max().date()
f_date = st.sidebar.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(f_date, (tuple, list)) and len(f_date) == 2:
    d_start, d_end = f_date
else:
    d_start = d_end = f_date[0] if isinstance(f_date, (tuple, list)) else f_date

view = clean[clean["City"].isin(f_city) & clean["Product"].isin(f_prod) & clean["Gender"].isin(f_gen)
             & clean["Payment Method"].isin(f_pay)
             & (clean["Order Date"].dt.date >= d_start) & (clean["Order Date"].dt.date <= d_end)]

# ---------- Automated Report ----------
st.header("📈 Automated Report")
if view.empty:
    st.warning("No data matches the selected filters. Please adjust the filters in the sidebar.")
    st.stop()
kpis = compute_kpis(view)
kpi_cards(list(kpis.items()), per_row=3)

def chart(fig):
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)

by_prod = view.groupby("Product", as_index=False)["Sales"].sum().sort_values("Sales", ascending=False)
by_city = view.groupby("City", as_index=False)["Sales"].sum().sort_values("Sales", ascending=False)
monthly = view.groupby(view["Order Date"].dt.to_period("M").astype(str), as_index=False)["Sales"].sum()
qty_prod = view.groupby("Product", as_index=False)["Quantity"].sum().sort_values("Quantity", ascending=False)

a, b = st.columns(2)
with a:
    chart(px.bar(by_prod, x="Product", y="Sales", color="Product", title="Sales by Product"))
with b:
    chart(px.bar(by_city, x="City", y="Sales", color="City", title="Sales by City"))
a, b = st.columns(2)
with a:
    chart(px.line(monthly, x="Order Date", y="Sales", markers=True, title="Monthly Sales Trend"))
with b:
    chart(px.pie(view, names="Gender", title="Gender Distribution", hole=0.4))
a, b = st.columns(2)
with a:
    chart(px.pie(view, names="Payment Method", title="Payment Method Distribution", hole=0.4))
with b:
    chart(px.bar(by_prod.head(5), x="Sales", y="Product", orientation="h", color="Product", title="Top 5 Products"))
chart(px.bar(qty_prod, x="Product", y="Quantity", color="Product", title="Quantity Sold by Product"))

# ---------- Key Insights ----------
st.header("💡 Key Insights")
insights = make_insights(view)
for text in insights:
    st.markdown(f'<div class="insight">✅ {text}</div>', unsafe_allow_html=True)

# ---------- Download Reports ----------
st.header("⬇️ Download Reports")
try:
    excel_bytes = build_excel(clean, summary, view, kpis, insights)
    st.download_button("⬇️ Download Report (Excel)", excel_bytes, "data_cleaning_report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Excel sheets: Cleaned Data, Cleaning Summary, Sales Summary (uses current filters), Insights.")
except Exception as e:
    st.error(f"Could not generate the Excel report: {e}")
st.download_button("⬇️ Download Cleaned Data (CSV)", clean.to_csv(index=False).encode("utf-8"),
                   "cleaned_data.csv", "text/csv", key="csv2")
