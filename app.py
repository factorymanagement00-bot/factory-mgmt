import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ============================================
# APP SETTINGS
# ============================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"          # <-- put your Firebase Web API key here
OPENROUTER_KEY = st.secrets["openrouter_key"]

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ============================================
# GLOBAL CSS (base styles)
# ============================================
base_css = """
<style>

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Hide sidebar when user is logged out */
.no-sidebar [data-testid="stSidebar"] {
    display: none !important;
}

/* LOGIN LAYOUT */
.login-wrapper {
    max-width: 430px;
    margin: 160px auto !important;
}
.login-card {
    padding: 40px;
    background: rgba(17, 25, 40, 0.55);
    backdrop-filter: blur(18px);
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 8px 40px rgba(0,0,0,0.55);
}
.login-title {
    text-align: center;
    font-size: 28px;
    color: white;
    font-weight: 700;
    margin-bottom: 20px;
}

/* SIDEBAR BASE */
[data-testid="stSidebar"] {
    background: rgba(15, 23, 42, 0.9) !important;
    backdrop-filter: blur(16px);
    padding: 20px 16px !important;
    border-right: 1px solid rgba(148,163,184,0.35);
    transition: width 0.25s ease-in-out, min-width 0.25s ease-in-out;
}

/* header */
.sidebar-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 24px;
}

.sidebar-title-text {
    font-size: 22px;
    font-weight: 700;
    color: #e5e7eb;
    line-height: 1.1;
}

/* collapse toggle button */
.collapse-btn button {
    background: rgba(15,23,42,1) !important;
    border-radius: 999px !important;
    border: 1px solid rgba(148,163,184,0.6) !important;
    color: #e5e7eb !important;
    padding: 6px 9px !important;
    font-size: 16px !important;
}

/* nav buttons */
.navbox button {
    width: 100% !important;
    background: rgba(255,255,255,0.04) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(148,163,184,0.4) !important;
    color: #e5e7eb !important;
    padding: 10px 14px !important;
    text-align: left !important;
    font-size: 15px !important;
    margin-bottom: 8px;
    transition: all 0.2s ease-in-out;
}
.navbox button:hover {
    background: rgba(148,163,184,0.3) !important;
    transform: translateX(3px);
}
.nav-selected button {
    background: #3b82f6 !important;
    border-color: #60a5fa !important;
    color: white !important;
    font-weight: 600 !important;
    transform: translateX(2px) scale(1.01);
}

/* logout button */
.logout-btn button {
    width: 100% !important;
    margin-top: 28px;
    background: #dc2626 !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    padding: 10px 14px !important;
}
.logout-btn button:hover {
    background: #f97373 !important;
}

/* DASHBOARD CARDS */
.metric-card {
    background: rgba(15,23,42,0.9);
    padding: 20px;
    border-radius: 16px;
    border: 1px solid rgba(148,163,184,0.4);
    box-shadow: 0 4px 20px rgba(0,0,0,0.35);
    text-align: center;
}
.metric-card h2 {
    color: white;
    font-size: 32px;
    margin: 0;
}
.metric-card p {
    color: #cbd5e1;
    margin: 4px 0 0 0;
}

/* main content spacing */
.block-container {
    padding-top: 24px !important;
}

</style>
"""
st.markdown(base_css, unsafe_allow_html=True)

# ============================================
# DYNAMIC SIDEBAR WIDTH CSS (collapsed / expanded)
# ============================================
if "sidebar_collapsed" not in st.session_state:
    st.session_state["sidebar_collapsed"] = False

if st.session_state["sidebar_collapsed"]:
    sidebar_mode_css = """
    <style>
    [data-testid="stSidebar"] {
        width: 80px !important;
        min-width: 80px !important;
    }
    .sidebar-title-text {
        display: none !important;
    }
    </style>
    """
else:
    sidebar_mode_css = """
    <style>
    [data-testid="stSidebar"] {
        width: 260px !important;
        min-width: 260px !important;
    }
    </style>
    """

st.markdown(sidebar_mode_css, unsafe_allow_html=True)

# ============================================
# SESSION INIT
# ============================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

def safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0

# ============================================
# AUTH FUNCTIONS
# ============================================
def signup(email, pw):
    payload = {"email": email, "password": pw, "returnSecureToken": True}
    return requests.post(SIGNUP_URL, json=payload).json()

def login(email, pw):
    payload = {"email": email, "password": pw, "returnSecureToken": True}
    return requests.post(SIGNIN_URL, json=payload).json()

# ============================================
# FIRESTORE HELPERS
# ============================================
def fs_add(col, data):
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.post(f"{BASE_URL}/{col}?key={API_KEY}", json={"fields": fields})

@st.cache_data(ttl=5)
def fs_get(col):
    r = requests.get(f"{BASE_URL}/{col}?key={API_KEY}").json()
    if "documents" not in r:
        return []
    out = []
    for d in r["documents"]:
        row = {k: v["stringValue"] for k, v in d["fields"].items()}
        row["id"] = d["name"].split("/")[-1]
        out.append(row)
    return out

def fs_update(col, id, data):
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.patch(f"{BASE_URL}/{col}/{id}?key={API_KEY}", json={"fields": fields})
    st.cache_data.clear()

def fs_delete(col, id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    st.cache_data.clear()

# ============================================
# AI — GENERAL + FACTORY
# ============================================
def job_summary(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        return ""
    return "\n".join(
        f"- {j['job_name']} | {j['status']} | ₹{j['amount']}"
        for j in jobs
    )

def ask_ai(email, query):
    summary = job_summary(email)
    user_prompt = f"""
User question:
{query}

Factory job data (only use this if the question is about the factory, jobs, production, planning, money etc):
{summary}
"""

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek/deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. "
                        "You can answer both general questions AND factory/production questions. "
                        "Only use the factory data when the user asks about work, jobs, production, or planning."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        },
    ).json()

    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return "AI error: " + str(resp)

# ============================================
# LOGIN PAGE (CENTERED, NO STRANGE BOX)
# ============================================
if st.session_state["user"] is None:
    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="login-wrapper"><div class="login-card">', unsafe_allow_html=True)

    st.markdown('<div class="login-title">🔐 Factory Manager Login</div>', unsafe_allow_html=True)

    mode = st.selectbox("Mode", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")
    if mode == "Sign Up":
        cpw = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            res = login(email, pw)
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                st.session_state["user"] = email
                st.rerun()
        else:
            if pw != cpw:
                st.error("Passwords don't match")
            else:
                res = signup(email, pw)
                if "error" in res:
                    st.error(res["error"]["message"])
                else:
                    st.success("Account created! You can log in now.")

    st.markdown("</div></div></div>", unsafe_allow_html=True)
    st.stop()

# ============================================
# SIDEBAR (ANIMATED COLLAPSING)
# ============================================
with st.sidebar:
    # Header with collapse toggle
    col_toggle, col_title = st.columns([1, 4])

    with col_toggle:
        with st.container():
            st.markdown('<div class="collapse-btn">', unsafe_allow_html=True)
            if st.button("☰" if st.session_state["sidebar_collapsed"] else "⮜", key="toggle_sidebar"):
                st.session_state["sidebar_collapsed"] = not st.session_state["sidebar_collapsed"]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with col_title:
        st.markdown(
            '<div class="sidebar-title-text">📦<br/>Factory</div>',
            unsafe_allow_html=True,
        )

    st.write("")  # small spacing

    # Navigation buttons
    def nav_btn(label, icon, page_name):
        box_class = "nav-selected" if st.session_state["page"] == page_name else "navbox"
        display_text = icon if st.session_state["sidebar_collapsed"] else f"{icon}  {label}"

        with st.container():
            st.markdown(f'<div class="{box_class}">', unsafe_allow_html=True)
            if st.button(display_text, key=f"nav_{page_name}"):
                st.session_state["page"] = page_name
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    nav_btn("Dashboard", "📊", "Dashboard")
    nav_btn("Add Job", "➕", "AddJob")
    nav_btn("View Jobs", "📋", "ViewJobs")
    nav_btn("AI Chat", "🤖", "AI")

    # Logout
    st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
    if st.button("Logout"):
        st.session_state["user"] = None
        st.session_state["page"] = "Dashboard"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ============================================
# MAIN PAGES
# ============================================
page = st.session_state["page"]
user_email = st.session_state["user"]

# ---------- Dashboard ----------
if page == "Dashboard":
    st.title("📊 Dashboard")

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]
    if not jobs:
        st.info("No jobs yet. Add one from 'Add Job'.")
    else:
        df = pd.DataFrame(jobs)
        col1, col2, col3 = st.columns(3)

        col1.markdown(
            f'<div class="metric-card"><h2>{len(df)}</h2><p>Total Jobs</p></div>',
            unsafe_allow_html=True,
        )
        col2.markdown(
            f'<div class="metric-card"><h2>{(df["status"]=="Pending").sum()}</h2><p>Pending</p></div>',
            unsafe_allow_html=True,
        )
        col3.markdown(
            f'<div class="metric-card"><h2>{(df["status"]=="Completed").sum()}</h2><p>Completed</p></div>',
            unsafe_allow_html=True,
        )

        st.subheader("All Jobs")
        st.dataframe(df, use_container_width=True)

# ---------- Add Job ----------
elif page == "AddJob":
    st.title("➕ Add New Job")

    job_name = st.text_input("Job Name")
    client_name = st.text_input("Client Name")
    phone = st.text_input("Phone")
    amount = st.number_input("Amount", min_value=0)
    job_type = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    notes = st.text_area("Notes")

    if st.button("Save Job"):
        fs_add(
            "jobs",
            {
                "job_name": job_name,
                "client_name": client_name,
                "phone": phone,
                "amount": amount,
                "job_type": job_type,
                "status": status,
                "notes": notes,
                "user_email": user_email,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        st.cache_data.clear()
        st.success("Job saved!")

# ---------- View & Edit Jobs ----------
elif page == "ViewJobs":
    st.title("📋 Manage Jobs")

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]
    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        job_id = st.selectbox("Select Job", df["id"])
        job = df[df["id"] == job_id].iloc[0]

        new_amount = st.number_input("Amount", value=safe_int(job["amount"]))
        new_status = st.selectbox(
            "Status",
            ["Pending", "In Progress", "Completed"],
            index=["Pending", "In Progress", "Completed"].index(job["status"]),
        )
        new_notes = st.text_area("Notes", job["notes"])

        if st.button("Update Job"):
            fs_update(
                "jobs",
                job_id,
                {"amount": new_amount, "status": new_status, "notes": new_notes},
            )
            st.success("Job updated!")

        if st.button("Delete Job"):
            fs_delete("jobs", job_id)
            st.warning("Job deleted!")

# ---------- AI Chat ----------
elif page == "AI":
    st.title("🤖 AI Chat Assistant")

    q = st.text_area("Ask anything:", "Give me a plan for tomorrow's work, and also tell me a random fun fact.")
    if st.button("Ask AI"):
        with st.spinner("AI thinking..."):
            answer = ask_ai(user_email, q)
        st.write(answer)
