import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================================================
#                 APP CONFIG
# ==========================================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"            # 🔥 put Firebase Web API Key
OPENROUTER_KEY = st.secrets["openrouter_key"]     # 🔥 saved in streamlit secrets

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ==========================================================
#                 PREMIUM CSS STYLING
# ==========================================================
premium_css = """
<style>

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Remove sidebar on login */
.no-sidebar section[data-testid="stSidebar"] {
    display: none !important;
}

/* ----------- Login Page ----------- */
.login-card {
    max-width: 430px;
    margin: 140px auto;
    padding: 40px;
    background: rgba(17, 25, 40, 0.55);
    backdrop-filter: blur(18px);
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 8px 40px rgba(0,0,0,0.55);
}
.login-title {
    font-size: 28px;
    color: white;
    text-align: center;
    font-weight: 700;
    margin-bottom: 20px;
}

/* ----------- Sidebar ----------- */
[data-testid="stSidebar"] {
    background: rgba(15, 23, 42, 0.75) !important;
    backdrop-filter: blur(16px);
    padding: 25px 22px !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}

.sidebar-title {
    font-size: 28px;
    font-weight: 700;
    color: white;
    margin-bottom: 30px;
    line-height: 1.2;
}

/* Nav Buttons */
.navbox button {
    width: 100% !important;
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #e2e8f0 !important;
    padding: 14px 16px !important;
    border-radius: 12px !important;
    font-size: 17px !important;
    text-align: left !important;
    transition: all 0.25s ease !important;
}

.navbox button:hover {
    background: rgba(255,255,255,0.12) !important;
    transform: translateX(4px);
}

.nav-selected button {
    background: #3b82f6 !important;
    color: white !important;
    font-weight: 600 !important;
    border: 1px solid #60a5fa !important;
    transform: scale(1.02);
}

/* Logout */
.logout-btn button {
    background: #dc2626 !important;
    color: white !important;
    padding: 12px !important;
    border-radius: 12px !important;
    border: none !important;
    margin-top: 40px;
}
.logout-btn button:hover {
    background: #f87171 !important;
}

/* Dashboard cards */
.metric-card {
    background: rgba(255,255,255,0.04);
    padding: 22px;
    border-radius: 16px;
    text-align: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.metric-card h2 {
    color: white;
    font-size: 36px;
    margin: 0;
}
.metric-card p {
    color: #cbd5e1;
    font-size: 16px;
}
</style>
"""
st.markdown(premium_css, unsafe_allow_html=True)

# ==========================================================
#        SESSION INIT
# ==========================================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"

def safe_int(v):
    try: return int(v)
    except: return 0

# ==========================================================
#        AUTH FUNCTIONS
# ==========================================================
def signup(email, pw):
    return requests.post(SIGNUP_URL, json={"email": email, "password": pw, "returnSecureToken": True}).json()

def login(email, pw):
    return requests.post(SIGNIN_URL, json={"email": email, "password": pw, "returnSecureToken": True}).json()

# ==========================================================
#        FIRESTORE HELPERS
# ==========================================================
def fs_add(col, data):
    url = f"{BASE_URL}/{col}?key={API_KEY}"
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.post(url, json={"fields": fields})

@st.cache_data(ttl=5)
def fs_get(col):
    r = requests.get(f"{BASE_URL}/{col}?key={API_KEY}").json()
    if "documents" not in r:
        return []
    out=[]
    for d in r["documents"]:
        row={k:v["stringValue"] for k,v in d["fields"].items()}
        row["id"]=d["name"].split("/")[-1]
        out.append(row)
    return out

def fs_update(col,id,data):
    url=f"{BASE_URL}/{col}/{id}?key={API_KEY}"
    fields={k:{"stringValue":str(v)} for k,v in data.items()}
    requests.patch(url,json={"fields":fields})
    st.cache_data.clear()

def fs_delete(col,id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    st.cache_data.clear()

# ==========================================================
#        AI PLANNER
# ==========================================================
def job_summary(email):
    jobs=[j for j in fs_get("jobs") if j["user_email"]==email]
    if not jobs: return "No jobs."
    lines=[f"- {j['job_name']} ({j['status']}) | ₹{j['amount']} | {j['client_name']}" for j in jobs]
    return "\n".join(lines)

def ask_ai(email, query):
    prompt=f"Factory job data:\n{job_summary(email)}\n\nUser question:\n{query}"
    r=requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization":f"Bearer {OPENROUTER_KEY}"},
        json={
            "model":"deepseek/deepseek-chat",
            "messages":[
                {"role":"system","content":"You are a senior production planner."},
                {"role":"user","content":prompt},
            ]
        }
    ).json()
    return r["choices"][0]["message"]["content"]

# ==========================================================
#        LOGIN PAGE
# ==========================================================
if st.session_state["user"] is None:
    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)

    st.markdown('<div class="login-title">🔐 Factory Manager Login</div>', unsafe_allow_html=True)

    mode = st.selectbox("Choose", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")
    if mode=="Sign Up":
        cpw = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode=="Login":
            res=login(email,pw)
            if "error" in res: st.error(res["error"]["message"])
            else:
                st.session_state["user"]=email
                st.rerun()
        else:
            if pw!=cpw: st.error("Passwords don’t match")
            else:
                res=signup(email,pw)
                if "error" in res: st.error(res["error"]["message"])
                else: st.success("Account created!")

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

email = st.session_state["user"]

# ==========================================================
#        SIDEBAR (PREMIUM)
# ==========================================================
with st.sidebar:
    st.markdown('<div class="sidebar-title">📦 Factory Manager</div>', unsafe_allow_html=True)

    def nav(label, icon, page):
        box = "nav-selected" if st.session_state["page"]==page else "navbox"
        with st.container():
            st.markdown(f'<div class="{box}">', unsafe_allow_html=True)
            if st.button(f"{icon}  {label}", key=f"{page}_nav"):
                st.session_state["page"]=page
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    nav("Dashboard", "📊", "Dashboard")
    nav("Add Job", "➕", "AddJob")
    nav("View Jobs", "📋", "ViewJobs")
    nav("AI Planner", "🤖", "AI")

    with st.container():
        st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
        if st.button("Logout"):
            st.session_state["user"]=None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
#        PAGES
# ==========================================================

page = st.session_state["page"]

# ---------- Dashboard ----------
if page=="Dashboard":
    st.title("📊 Dashboard Overview")

    jobs=[j for j in fs_get("jobs") if j["user_email"]==email]
    df=pd.DataFrame(jobs) if jobs else pd.DataFrame()

    if len(df)==0:
        st.info("No jobs found yet.")
    else:
        total = len(df)
        pending = sum(df["status"]=="Pending")
        progress = sum(df["status"]=="In Progress")
        done = sum(df["status"]=="Completed")

        col1,col2,col3,col4 = st.columns(4)
        col1.markdown(f'<div class="metric-card"><h2>{total}</h2><p>Total Jobs</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="metric-card"><h2>{pending}</h2><p>Pending</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="metric-card"><h2>{progress}</h2><p>In Progress</p></div>', unsafe_allow_html=True)
        col4.markdown(f'<div class="metric-card"><h2>{done}</h2><p>Completed</p></div>', unsafe_allow_html=True)

        st.write("")
        st.subheader("All Jobs")
        st.dataframe(df, use_container_width=True)

# ---------- Add Job ----------
elif page=="AddJob":
    st.title("➕ Add Job")

    jn = st.text_input("Job Name")
    cn = st.text_input("Client Name")
    ph = st.text_input("Phone")
    amt = st.number_input("Amount", min_value=0)
    jt = st.text_input("Job Type")
    stt = st.selectbox("Status", ["Pending","In Progress","Completed"])
    notes = st.text_area("Notes")

    if st.button("Save Job"):
        fs_add("jobs", {
            "job_name": jn,
            "client_name": cn,
            "phone": ph,
            "amount": amt,
            "job_type": jt,
            "status": stt,
            "notes": notes,
            "user_email": email,
            "created_at": datetime.utcnow().isoformat()
        })
        st.cache_data.clear()
        st.success("Job Added!")

# ---------- View / Edit Jobs ----------
elif page=="ViewJobs":
    st.title("📋 Manage Jobs")

    jobs=[j for j in fs_get("jobs") if j["user_email"]==email]

    if not jobs:
        st.info("No jobs available.")
    else:
        df=pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        jid = st.selectbox("Select Job ID", df["id"])
        row = df[df["id"]==jid].iloc[0]

        new_amt = st.number_input("Amount", value=safe_int(row["amount"]))
        new_status = st.selectbox("Status", ["Pending","In Progress","Completed"],
                                  index=["Pending","In Progress","Completed"].index(row["status"]))
        new_notes = st.text_area("Notes", row["notes"])

        if st.button("Update Job"):
            fs_update("jobs", jid, {
                "amount": new_amt,
                "status": new_status,
                "notes": new_notes
            })
            st.success("Updated!")

        if st.button("Delete Job"):
            fs_delete("jobs", jid)
            st.warning("Deleted!")

# ---------- AI Planner ----------
elif page=="AI":
    st.title("🤖 AI Work Planner")

    q = st.text_area("Ask AI", "Give me today's factory work plan")
    if st.button("Generate"):
        with st.spinner("AI Working..."):
            out = ask_ai(email, q)
        st.write(out)
