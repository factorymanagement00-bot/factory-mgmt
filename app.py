import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# ==========================================================
#                       CONFIG
# ==========================================================
PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"     # <-- YOUR FIREBASE WEB API KEY
OPENROUTER_KEY = st.secrets["openrouter_key"]

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ==========================================================
#                       CSS (MODERN UI)
# ==========================================================
modern_css = """
<style>

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Hide sidebar on login */
.no-sidebar section[data-testid="stSidebar"] { display: none !important; }

.center-box {
    max-width: 420px;
    margin: 120px auto;
    padding: 40px;
    background: #111827;
    border-radius: 16px;
    box-shadow: 0 0 40px rgba(0,0,0,0.55);
}
.center-box h1 {
    text-align: center;
    color: white;
    font-weight: 700;
    margin-bottom: 15px;
    font-size: 30px;
}

/* Modern Sidebar */
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    padding: 30px 25px !important;
    border-right: 1px solid #1f2937;
}

/* Sidebar Title */
.sidebar-title {
    font-size: 26px;
    font-weight: 700;
    color: white;
    margin-bottom: 25px;
}

/* Nav Buttons */
.nav-btn {
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 17px;
    margin-bottom: 8px;
    color: #e5e7eb;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: 0.2s;
}
.nav-btn:hover {
    background: #1e293b;
}
.nav-selected {
    background: #334155;
    border-left: 4px solid #4f8cff;
}

/* Logout */
.logout-btn {
    margin-top: 30px;
    padding: 12px 16px;
    border-radius: 10px;
    background: #1e2635;
    color: #f87171 !important;
    font-size: 16px;
    border: 1px solid #334155;
    text-align: center;
    cursor: pointer;
}
.logout-btn:hover {
    background: #dc2626;
    color: white !important;
}
</style>
"""
st.markdown(modern_css, unsafe_allow_html=True)

# ==========================================================
#                    SESSION CONTROL
# ==========================================================
def init_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"

init_session()

# ==========================================================
#                AUTHENTICATION FUNCTIONS
# ==========================================================
def signup(email, pw):
    return requests.post(SIGNUP_URL, json={"email": email, "password": pw, "returnSecureToken": True}).json()

def login(email, pw):
    return requests.post(SIGNIN_URL, json={"email": email, "password": pw, "returnSecureToken": True}).json()

# ==========================================================
#                  FIRESTORE FUNCTIONS
# ==========================================================
def firestore_add(col, data):
    url = f"{BASE_URL}/{col}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k,v in data.items()}}
    requests.post(url, json=payload)

@st.cache_data(ttl=10)
def firestore_get(col):
    url = f"{BASE_URL}/{col}?key={API_KEY}"
    r = requests.get(url).json()
    if "documents" not in r:
        return []
    out = []
    for d in r["documents"]:
        row = {k: v["stringValue"] for k, v in d["fields"].items()}
        row["id"] = d["name"].split("/")[-1]
        out.append(row)
    return out

def firestore_update(col, id, data):
    url = f"{BASE_URL}/{col}/{id}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k,v in data.items()}}
    requests.patch(url, json=payload)
    st.cache_data.clear()

def firestore_delete(col, id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    st.cache_data.clear()

# ==========================================================
#                       AI PLANNER
# ==========================================================
def safe_int(v):
    try: return int(v)
    except: return 0

def job_summary(email):
    jobs = [j for j in firestore_get("jobs") if j["user_email"] == email]
    if not jobs:
        return "No jobs available."

    total = sum(safe_int(j["amount"]) for j in jobs)
    pending = sum(j["status"] == "Pending" for j in jobs)
    active = sum(j["status"] == "In Progress" for j in jobs)
    done   = sum(j["status"] == "Completed" for j in jobs)

    lines = [
        f"- {j['job_name']} | {j['client_name']} | ₹{j['amount']} | {j['status']}"
        for j in jobs
    ]
    return f"Total: {len(jobs)}, Pending: {pending}, Working: {active}, Done: {done}, Value ₹{total}\n\n" + "\n".join(lines)

def ask_ai(email, query):
    prompt = f"""
Analyze this factory data and generate:
- Today's plan
- Tomorrow's plan
- Urgent delayed jobs
- Efficiency suggestions

JOB DATA:
{job_summary(email)}

QUESTION:
{query}
"""
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a factory planning expert."},
            {"role": "user", "content": prompt}
        ]
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()
    return r["choices"][0]["message"]["content"]

# ==========================================================
#                       LOGIN PAGE
# ==========================================================
if st.session_state["user"] is None:
    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="center-box">', unsafe_allow_html=True)

    st.markdown("<h1>🔐 Login</h1>", unsafe_allow_html=True)

    mode = st.selectbox("Mode", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")

    if mode == "Sign Up":
        confirm = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            res = login(email, pw)
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                st.session_state["user"] = {"email": email}
                st.rerun()

        else:
            if pw != confirm:
                st.error("Passwords don't match")
            else:
                res = signup(email, pw)
                if "error" in res:
                    st.error(res["error"]["message"])
                else:
                    st.success("Account created! You can login now.")

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# ==========================================================
#                APP SIDEBAR (AFTER LOGIN)
# ==========================================================
st.markdown(modern_css, unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-title">📦 Factory Manager</div>', unsafe_allow_html=True)

    def nav(label, icon, page_name):
        selected = "nav-selected" if st.session_state["page"] == page_name else ""
        btn = st.markdown(
            f'<div class="nav-btn {selected}">{icon} {label}</div>',
            unsafe_allow_html=True
        )
        if btn: 
            st.session_state["page"] = page_name

    nav("Dashboard", "🏠", "Dashboard")
    nav("Add Job", "➕", "Add Job")
    nav("View Jobs", "📋", "View Jobs")
    nav("AI Planner", "🤖", "AI Planner")

    # Logout
    if st.button("Logout"):
        st.session_state["user"] = None
        st.session_state["page"] = "Dashboard"
        st.rerun()

# ==========================================================
#                      MAIN PAGES
# ==========================================================
page = st.session_state["page"]
email = st.session_state["user"]["email"]

# ---------------- Dashboard ----------------
if page == "Dashboard":
    st.title("📊 Dashboard")

    jobs = [j for j in firestore_get("jobs") if j["user_email"] == email]

    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        df["amount_int"] = df["amount"].apply(safe_int)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Jobs", len(df))
        c2.metric("Pending", sum(df["status"] == "Pending"))
        c3.metric("Total Value", f"₹{df['amount_int'].sum()}")

        st.dataframe(df.drop(columns=["amount_int"]), use_container_width=True)

# ---------------- Add Job ----------------
elif page == "Add Job":
    st.title("➕ Add Job")

    jn = st.text_input("Job Name")
    cn = st.text_input("Client Name")
    ph = st.text_input("Phone Number")
    amt = st.number_input("Amount", min_value=0)
    jt = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    notes = st.text_area("Notes")

    if st.button("Save"):
        firestore_add("jobs", {
            "job_name": jn,
            "client_name": cn,
            "phone": ph,
            "amount": amt,
            "job_type": jt,
            "status": status,
            "notes": notes,
            "user_email": email,
            "created_at": datetime.utcnow().isoformat()
        })
        st.cache_data.clear()
        st.success("Job saved!")

# ---------------- View Jobs ----------------
elif page == "View Jobs":
    st.title("📋 Manage Jobs")

    jobs = [j for j in firestore_get("jobs") if j["user_email"] == email]

    if not jobs:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        jid = st.selectbox("Select Job ID", df["id"])
        job = df[df["id"] == jid].iloc[0]

        new_amt = st.number_input("Amount", value=safe_int(job["amount"]))
        new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"],
            index=["Pending", "In Progress", "Completed"].index(job["status"]))
        new_notes = st.text_area("Notes", job["notes"])

        if st.button("Update Job"):
            firestore_update("jobs", jid, {
                "amount": new_amt,
                "status": new_status,
                "notes": new_notes
            })
            st.success("Updated!")

        if st.button("Delete Job"):
            firestore_delete("jobs", jid)
            st.warning("Deleted!")

# ---------------- AI Planner ----------------
elif page == "AI Planner":
    st.title("🤖 AI Production Planner")

    q = st.text_area("Ask AI", "Give me today's work plan")
    if st.button("Generate Plan"):
        with st.spinner("AI analyzing..."):
            out = ask_ai(email, q)
        st.write(out)
