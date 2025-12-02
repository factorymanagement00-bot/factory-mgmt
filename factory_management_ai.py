import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Factory Management AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------
# Dark Neon UI CSS
# ----------------------
st.markdown("""
<style>

body, .stApp {
    background-color: #0d0f16 !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3, h4, h5 {
    color: #b27cff !important;
    font-weight: 600;
}

.stButton>button {
    background: linear-gradient(90deg, #7928ca, #ff0080);
    border: none;
    color: white;
    padding: 10px 22px;
    border-radius: 10px;
    font-size: 17px;
}

.stButton>button:hover {
    opacity: 0.85;
}

.stSelectbox, .stTextInput, .stNumberInput {
    background: #1a1d29;
    color: #ffffff !important;
}

</style>
""", unsafe_allow_html=True)

# ----------------------
# INIT SESSION STATE
# ----------------------
if "inventory" not in st.session_state:
    st.session_state.inventory = []

if "categories" not in st.session_state:
    st.session_state.categories = []

if "jobs" not in st.session_state:
    st.session_state.jobs = []

if "staff_count" not in st.session_state:
    st.session_state.staff_count = 5

if "work_hours" not in st.session_state:
    st.session_state.work_hours = 8

# ----------------------
# NAVIGATION
# ----------------------
st.sidebar.title("⚙️ Factory Management AI")

page = st.sidebar.radio(
    "Navigate",
    ["Inventory", "Jobs", "Planner", "Staff Settings"],
)

