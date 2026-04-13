import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Report Viewer", layout="wide")

# ── Demo mode ──────────────────────────────────────────────────────────────────
DEMO_MODE = not all([
    os.getenv("DB2_DSN"),
    os.getenv("DB2_USERNAME"),
    os.getenv("DB2_PASSWORD"),
])

DEMO_DATA = {
    "Healthcare Provider Report": pd.DataFrame({
        "Provider ID":   ["HP001", "HP002", "HP003", "HP004", "HP005"],
        "Provider Name": ["Sydney Medical", "North Shore Clinic", "Westmead Health", "Bondi GP", "Parramatta Care"],
        "Specialty":     ["Cardiology", "General Practice", "Oncology", "General Practice", "Radiology"],
        "State":         ["NSW", "NSW", "NSW", "NSW", "NSW"],
        "Loan Amount":   [450000, 125000, 780000, 95000, 340000],
        "Status":        ["Active", "Active", "Settled", "Active", "Active"],
        "Approval Date": ["2024-03-01", "2024-01-15", "2023-11-20", "2024-02-28", "2024-04-05"],
    }),
    "Loan Arrears Summary": pd.DataFrame({
        "Account ID":    ["LA1001", "LA1002", "LA1003", "LA1004"],
        "Client Name":   ["Dr. James Wu", "Dr. Sarah Chen", "Dr. Mark Patel", "Dr. Amy Torres"],
        "Days Overdue":  [15, 32, 7, 61],
        "Amount Owing":  [2400.00, 8750.50, 1100.00, 15600.75],
        "Product":       ["Equipment Finance", "Practice Loan", "Equipment Finance", "Practice Loan"],
        "Risk Band":     ["Low", "Medium", "Low", "High"],
    }),
    "Monthly Settlements": pd.DataFrame({
        "Month":         ["Jan 2024", "Feb 2024", "Mar 2024", "Apr 2024", "May 2024"],
        "Settlements":   [42, 38, 55, 61, 49],
        "Total Value":   [8_200_000, 7_450_000, 10_900_000, 12_300_000, 9_800_000],
        "Avg Loan Size": [195238, 196053, 198182, 201639, 200000],
        "YoY Change":    ["12%", "8%", "21%", "18%", "14%"],
    }),
}

# Column format hints: currency, percent, integer
DEMO_FORMATS = {
    "Healthcare Provider Report": {
        "Loan Amount": "currency",
    },
    "Loan Arrears Summary": {
        "Amount Owing": "currency",
        "Days Overdue": "integer",
    },
    "Monthly Settlements": {
        "Total Value":   "currency",
        "Avg Loan Size": "currency",
        "Settlements":   "integer",
    },
}

DEMO_FILTERS = {
    "Healthcare Provider Report": [
        {"name": "Specialty", "type": "multiselect", "options": ["Cardiology", "General Practice", "Oncology", "Radiology"]},
        {"name": "Status",    "type": "multiselect", "options": ["Active", "Settled", "Pending"]},
    ],
    "Loan Arrears Summary": [
        {"name": "Risk Band",    "type": "multiselect", "options": ["Low", "Medium", "High"]},
        {"name": "Days Overdue", "type": "numeric"},
    ],
    "Monthly Settlements": [],
}

ROW_LIMIT_WARNING = 5000

# ── Column formatter ───────────────────────────────────────────────────────────
def apply_formats(df, formats):
    df = df.copy()
    for col, fmt in (formats or {}).items():
        if col not in df.columns:
            continue
        if fmt == "currency":
            df[col] = pd.to_numeric(df[col], errors="coerce").apply(
                lambda v: f"${v:,.0f}" if pd.notna(v) else ""
            )
        elif fmt == "percent":
            df[col] = pd.to_numeric(df[col], errors="coerce").apply(
                lambda v: f"{v:.1f}%" if pd.notna(v) else ""
            )
        elif fmt == "integer":
            df[col] = pd.to_numeric(df[col], errors="coerce").apply(
                lambda v: f"{int(v):,}" if pd.notna(v) else ""
            )
    return df

# ── DB2 connection ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    import pyodbc
    return pyodbc.connect(
        f"DSN={os.getenv('DB2_DSN')};"
        f"UID={os.getenv('DB2_USERNAME')};"
        f"PWD={os.getenv('DB2_PASSWORD')};"
    )

def run_query(sql):
    conn = get_connection()
    return pd.read_sql(sql, conn)

# ── Load reports config ────────────────────────────────────────────────────────
def load_reports():
    path = os.path.join(os.path.dirname(__file__), "reports.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("reports", [])

# ── SQL builder ────────────────────────────────────────────────────────────────
def build_sql(base_sql, filters, filter_values):
    sql = base_sql
    for f in filters:
        token = f.get("token", f":{f['name'].lower().replace(' ', '_')}")
        val = filter_values.get(f["name"])
        if val is None or val == [] or val == "":
            sql = sql.replace(token, "NULL")
            continue
        if f["type"] == "multiselect" and val:
            quoted = ", ".join(f"'{v}'" for v in val)
            sql = sql.replace(token, f"({quoted})")
        elif f["type"] == "date":
            sql = sql.replace(token, f"'{val}'")
        elif f["type"] == "numeric":
            sql = sql.replace(token, str(val))
    return sql

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Report Viewer")

    if DEMO_MODE:
        st.info("**Demo mode** — sample data only.\nAdd DB2 credentials to `.env` to connect live.", icon="🔌")

    if DEMO_MODE:
        all_report_names = list(DEMO_DATA.keys())
    else:
        reports = load_reports()
        all_report_names = [r["name"] for r in reports] if reports else []

    if not all_report_names:
        st.warning("No reports configured. Add entries to reports.json.")
        st.stop()

    # ── Report search ──────────────────────────────────────────────────────────
    search = st.text_input("🔍 Search reports", placeholder="Type to filter...")
    filtered_names = (
        [n for n in all_report_names if search.lower() in n.lower()]
        if search else all_report_names
    )

    if not filtered_names:
        st.warning("No reports match that search.")
        st.stop()

    selected_name = st.selectbox("Select Report", filtered_names)

    # ── Filters ───────────────────────────────────────────────────────────────
    filter_values = {}
    st.markdown("---")
    st.subheader("Filters")

    if DEMO_MODE:
        demo_filters = DEMO_FILTERS.get(selected_name, [])
        for f in demo_filters:
            if f["type"] == "multiselect":
                opts = f["options"]
                all_selected = st.checkbox(f"All {f['name']}", value=True, key=f"all_{f['name']}")
                filter_values[f["name"]] = opts if all_selected else st.multiselect(f["name"], opts, key=f"ms_{f['name']}")
            elif f["type"] == "numeric":
                filter_values[f["name"]] = st.number_input(f["name"], min_value=0, value=0, key=f"n_{f['name']}")
        if not demo_filters:
            st.caption("No filters for this report.")
    else:
        report = next(r for r in reports if r["name"] == selected_name)
        for f in report.get("filters", []):
            if f["type"] == "multiselect":
                try:
                    opts_df = run_query(f"SELECT DISTINCT {f['column']} FROM {f['table']} ORDER BY {f['column']}")
                    opts = opts_df.iloc[:, 0].astype(str).tolist()
                except Exception as e:
                    st.error(f"Could not load {f['name']} options: {e}")
                    opts = []
                all_sel = st.checkbox(f"All {f['name']}", value=True, key=f"all_{f['name']}")
                filter_values[f["name"]] = opts if all_sel else st.multiselect(f["name"], opts, key=f"ms_{f['name']}")
            elif f["type"] == "date":
                default = date.fromisoformat(f.get("default") or str(date.today()))
                filter_values[f["name"]] = st.date_input(f["name"], value=default, key=f"d_{f['name']}")
            elif f["type"] == "numeric":
                filter_values[f["name"]] = st.number_input(f["name"], value=f.get("default", 0), key=f"n_{f['name']}")

    st.markdown("---")
    run_clicked = st.button("▶ Run Report", use_container_width=True, type="primary")

# ── Main area ──────────────────────────────────────────────────────────────────
st.header(selected_name)

if DEMO_MODE:
    report_desc = {
        "Healthcare Provider Report": "Active and settled provider loans by specialty and state.",
        "Loan Arrears Summary": "Accounts with outstanding overdue amounts by risk band.",
        "Monthly Settlements": "Settlement volume and value trends by month.",
    }
    if d := report_desc.get(selected_name):
        st.caption(d)
else:
    report = next(r for r in reports if r["name"] == selected_name)
    if desc := report.get("description"):
        st.caption(desc)

if run_clicked or DEMO_MODE:
    last_run = datetime.now().strftime("%-I:%M %p")

    if DEMO_MODE:
        df = DEMO_DATA[selected_name].copy()
        demo_filters = DEMO_FILTERS.get(selected_name, [])
        for f in demo_filters:
            val = filter_values.get(f["name"])
            if f["type"] == "multiselect" and val and f["name"] in df.columns:
                df = df[df[f["name"]].isin(val)]
            elif f["type"] == "numeric" and val and val > 0 and f["name"] in df.columns:
                df = df[df[f["name"]] >= val]

        display_df = apply_formats(df, DEMO_FORMATS.get(selected_name, {}))

        col_a, col_b = st.columns([3, 1])
        with col_a:
            if run_clicked:
                st.success(f"{len(df):,} rows returned (demo data)")
            else:
                st.caption(f"{len(df):,} rows — click **Run Report** to apply filters")
        with col_b:
            st.caption(f"Last run: {last_run}")

    else:
        if run_clicked:
            try:
                t0 = datetime.now()
                final_sql = build_sql(report["sql"], report.get("filters", []), filter_values)
                df = run_query(final_sql)
                elapsed = (datetime.now() - t0).total_seconds()
                if report.get("columns"):
                    df.columns = report["columns"][:len(df.columns)]

                formats = {
                    c.get("name"): c.get("format")
                    for c in report.get("column_formats", [])
                    if c.get("format")
                } if report.get("column_formats") else {}
                display_df = apply_formats(df, formats)

                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.success(f"{len(df):,} rows — {elapsed:.2f}s")
                with col_b:
                    st.caption(f"Last run: {last_run}")

            except Exception as e:
                st.error(f"Query failed: {e}")
                st.code(final_sql, language="sql")
                st.stop()

    # ── Row limit warning ──────────────────────────────────────────────────────
    if len(df) >= ROW_LIMIT_WARNING and len(df) % 1000 == 0:
        st.warning(
            f"⚠ Results show exactly {len(df):,} rows — data may be truncated. "
            "Apply filters to narrow the result set."
        )

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Downloads — raw df so exports are clean numbers not formatted strings
    col1, col2 = st.columns([1, 1])
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download CSV", csv, f"{selected_name}.csv", "text/csv", use_container_width=True)
    with col2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="Report")
        st.download_button("⬇ Download Excel", buf.getvalue(), f"{selected_name}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
else:
    st.info("Set your filters and click **Run Report**.")
