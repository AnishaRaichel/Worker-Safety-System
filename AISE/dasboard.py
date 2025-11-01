# dashboard.py
import boto3
import streamlit as st
import pandas as pd
from datetime import datetime
import os
from decimal import Decimal
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh

# =====================
# AWS DynamoDB Connection
# =====================
dynamodb = boto3.resource(
    'dynamodb',
    region_name='ap-southeast-2',
    aws_access_key_id='XX',
    aws_secret_access_key='YY'
)

table = dynamodb.Table("SafetyAlerts")

# =====================
# Streamlit UI Config
# =====================
st.set_page_config(page_title="Worker Safety Dashboard", page_icon="🚧", layout="wide")

st.markdown("""
    <style>
        /* Override Streamlit's body background */
        html, body, [class*="stAppViewContainer"], [class*="stMainBlockContainer"] {
            background-color: #1a1a1a !important; /* Matte dark */
            color: #f2f2f2 !important;
        }

        /* Page titles */
        h1, h2, h3, h4, h5, h6 {
            color: #FFD700 !important; /* Bold yellow */
            font-weight: 700;
        }

        /* Paragraphs and text */
        p, div, span, label {
            color: #eaeaea !important;
        }

        /* Navbar container */
        .nav-container {
            background-color: #2E2E2E !important;
            border-radius: 10px;
        }

        /* Metric cards */
        .metric-container {
            background-color: rgba(255, 165, 0, 0.15);
            border: 1px solid #FFA500;
            border-radius: 12px;
            padding: 10px;
        }

        /* DataFrame table */
        [data-testid="stDataFrame"] {
            background-color: #262626;
            border-radius: 10px;
            color: white;
        }

        /* Title */
        .title {
            text-align: center;
            font-size: 30px;
            font-weight: 800;
            color: #FFD700;
            letter-spacing: 1px;
            padding-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# Auto refresh every 10s
st_autorefresh(interval=10 * 1000, key="datarefresh")

# =====================
# Header
# =====================
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("https://cdn-icons-png.flaticon.com/512/4255/4255689.png", width=80)
with col_title:
    st.markdown("<div class='title'>🚧 Industrial Worker Safety Dashboard</div>", unsafe_allow_html=True)

st.write("")

# =====================
# NAVBAR
# =====================
selected = option_menu(
    menu_title="Navigation",  
    options=["Overview", "Alerts Table", "Charts"],  
    icons=["speedometer2", "table", "bar-chart-line"],  
    menu_icon="cast",  
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#2E2E2E"},
        "icon": {"color": "#FFA500", "font-size": "20px"}, 
        "nav-link": {"color": "#f2f2f2", "font-size": "16px", "text-align": "center"},
        "nav-link-selected": {"background-color": "#FF4B4B"},
    }
)

# =====================
# Data Fetch & Cleanup
# =====================
def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    else:
        return obj

response = table.scan()
items = convert_decimals(response.get("Items", []))

cleaned_items = []
for item in items:
    if "payload" in item and isinstance(item["payload"], dict):
        flat = {**item, **item["payload"]}
        flat.pop("payload", None)
        cleaned_items.append(flat)
    else:
        cleaned_items.append(item)

df = pd.DataFrame(cleaned_items)

if not df.empty and "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp", ascending=False)

# =====================
# OVERVIEW PAGE
# =====================
if selected == "Overview":
    st.title("📊 System Overview")

    if df.empty:
        st.success("✅ No alerts yet. Everything is safe!")
    else:
        total_alerts = len(df)
        fatigue = df["status"].str.contains("Fatigue", case=False, na=False).sum()
        heat = df["status"].str.contains("Heat", case=False, na=False).sum()
        unauthorized = df["status"].str.contains("Unauthorized", case=False, na=False).sum()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🚨 Total Alerts", total_alerts)
        with col2:
            st.metric("😴 Fatigue", fatigue)
        with col3:
            st.metric("🌡️ Heat Hazards", heat)
        with col4:
            st.metric("🔑 Unauthorized", unauthorized)

        st.write("### ⚠️ Alert Breakdown")
        st.bar_chart(df["status"].value_counts())

# =====================
# ALERTS TABLE PAGE
# =====================
elif selected == "Alerts Table":
    st.title("📋 Recent Safety Alerts")
    if df.empty:
        st.info("No alerts recorded.")
    else:
        employees = ["All"] + sorted(df["employee_id"].unique().tolist())
        selected_emp = st.selectbox("Filter by Employee ID:", employees)
        if selected_emp != "All":
            df = df[df["employee_id"] == float(selected_emp)]

        def color_status(val):
            if isinstance(val, str):
                if "Critical" in val:
                    return "background-color: red; color: white;"
                elif "Danger" in val:
                    return "background-color: orange; color: white;"
                elif "Fatigue" in val or "Heat" in val:
                    return "background-color: yellow; color: black;"
                elif "Unauthorized" in val:
                    return "background-color: purple; color: white;"
            return ""

        styled_df = df[["employee_id", "status", "timestamp"]].style.map(color_status, subset=["status"])
        st.dataframe(styled_df, use_container_width=True)

# =====================
# CHARTS PAGE
# =====================
elif selected == "Charts":
    st.title("📈 Alerts Analysis")
    if df.empty:
        st.info("No data for charts.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("⚠️ Alerts by Type")
            st.bar_chart(df["status"].value_counts())

        with col2:
            st.subheader("🕒 Alerts Over Time")
            df["time"] = pd.to_datetime(df["timestamp"])
            df_time = df.groupby(df["time"].dt.strftime("%H:%M"))["status"].count()
            st.line_chart(df_time)
