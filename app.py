# ==========================================
# AI FINANCE TRACKER - FRONTEND (CLIENT)
# ==========================================
import streamlit as st
import requests
import pandas as pd
import json

# --- CONFIGURATION ---
BASE_URL = "http://localhost:8000"
API_Recent = f"{BASE_URL}/recent"
API_Analytics = f"{BASE_URL}/analytics"
API_Query = f"{BASE_URL}/query"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="💰 AI Finance Tracker",
    page_icon="💸",
    layout="wide"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #1f1c2c, #928dab);
        color: white;
        font-family: 'Trebuchet MS', sans-serif;
    }
    
    /* Hero Header */
    .hero-title {
        font-size: 3.5rem;
        font-weight: bold;
        color: #fff;
        text-align: center;
        text-shadow: 0 0 10px #00ffe7, 0 0 20px #00ffe7;
        margin-bottom: 0px;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: #FFD700;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 30px;
        font-style: italic;
    }

    /* Cards & Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
        color: #00ffe7;
    }
    
    /* Input Field */
    .stTextInput > div > div > input {
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid #00ffe7;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def fetch_recent():
    try:
        res = requests.get(API_Recent)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        st.error(f"Error fetching recent activity: {e}")
    return []

def fetch_analytics():
    try:
        res = requests.get(API_Analytics)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        st.error(f"Error fetching analytics: {e}")
    return []

def handle_query():
    query_text = st.session_state.user_query
    if query_text:
        try:
            with st.spinner("Processing with Groq LPU™..."):
                res = requests.post(API_Query, json={"question": query_text})
                if res.status_code == 200:
                    response_data = res.json()
                    st.session_state.last_response = response_data
                    st.success("Processed Successfully!")
                else:
                     st.error(f"Error: {res.status_code}")
        except Exception as e:
            st.error(f"Connection Error: {e}")

# --- INITIALIZATION ---
if 'last_response' not in st.session_state:
    st.session_state.last_response = None

# Load data on startup logic - (Streamlit re-runs script on interaction, so we fetch fresh data to keep dashboard updated)
recent_data = fetch_recent()
analytics_data = fetch_analytics()

# --- SECTION A: HERO HEADER ---
st.markdown("<div class='hero-title'>💰 AI Finance Tracker</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-subtitle'>Powered by Groq LPU™</div>", unsafe_allow_html=True)

# --- SECTION B: THE DASHBOARD (Top Row) ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 📊 Metrics")
    total_spend = 0.0
    if analytics_data:
        total_spend = sum(item['total'] for item in analytics_data)
    st.metric(label="Total Expenses (All Time)", value=f"${total_spend:,.2f}")

with col2:
    st.markdown("### 🍩 Spending Breakdown")
    if analytics_data:
        df_analytics = pd.DataFrame(analytics_data)
        st.bar_chart(df_analytics, x="category", y="total", color="#00ffe7")
    else:
        st.info("No analytics data available yet.")

st.markdown("---")

# --- SECTION C: RECENT ACTIVITY (Middle Row) ---
st.markdown("### 🕒 Recent Activity")
if recent_data:
    df_recent = pd.DataFrame(recent_data)
    # Reorder/Rename columns for display if needed
    st.dataframe(df_recent, use_container_width=True, hide_index=True)
else:
    st.info("No recent transactions found.")

st.markdown("---")

# --- SECTION D: ACTION CENTER (Bottom Row) ---
st.markdown("### 💬 Action Center")

col_input, col_history = st.columns([2, 1])

with col_input:
    st.text_input(
        "Talk to your finance tracker...", 
        placeholder="e.g. 'I spent $20 on Coffee' or 'Show all food expenses'", 
        key="user_query", 
        on_change=handle_query
    )
    st.caption("Press Enter to send.")

with col_history:
    st.markdown("**Last AI Response:**")
    if st.session_state.last_response:
        msg = st.session_state.last_response.get("message", "")
        row_count = st.session_state.last_response.get("row_count", 0)
        
        if "success" in msg.lower() or "added" in msg.lower():
             st.success(f"{msg}")
        elif row_count > 0:
             st.info(f"{msg}")
        else:
             st.warning(f"{msg}")
        
        # If it was a SELECT query, we might want to show that separate data too? 
        # The requirements said "History: Show the last AI response (Success/Fail messages)." 
        # so keeping it simple.
    else:
        st.write("waiting for input...")
