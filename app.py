import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# =====================================================
#                FIREBASE CONFIG
# =====================================================
PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"   # <-- PUT YOUR FIREBASE WEB API KEY HERE

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

OPENROUTER_KEY = st.secrets["openrouter_key"]


# =====================================================
#                CSS STYLING
# =====================================================

modern_css = """
<style>

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ---- HIDE SIDEBAR ON LOGIN PAGE ---- */
.no-sidebar section[data-testid="stSidebar"] { display: none !important; }

/* CENTER LOGIN BOX */
.center-box {
    max-width: 430px;
    margin: 120px auto;
    padding: 40px;
    background: #111827;
    border-radius: 16px;
    box-shadow: 0 0 40px rgba(0,0,0,0.55);
}
.center-box h1 {
    color: white;
    text-align: center;
    font-size: 30px;
    font-weight: 700;
}

/* ---- MODERN SIDEBAR ---- */
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    padding: 25px 20px !important;
    border-right: 1px solid #1f2937;
}

/* Sidebar title */
.sidebar-title {
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Section label */
.sidebar-label {
    font-size: 15px;
    color: #9ca3af;
    margin-bottom: 10px;
}

/* Nav button */
.nav-btn {
    width: 100%;
    padding: 12px 16px;
    border-radius: 10px;
    background: transparent;
    color: #e5e7eb;
    font-size: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: 0.2s;
    border: none;
}

.nav-btn:hover {
    background: #1e293b;
}

.nav-selected {
    background: #334155 !important;
    border-left: 4px solid #4f8cff;
}

/* Logout button */
.logout-btn {
    margin-top: 25px;
    padding: 12px 16px;
    border-radius: 10px;
    background: #1e2635;
    color: #f87171 !important;
    font-size: 16px;
    border: 1px solid #334155;
}
.logout-btn:hover {
    background: #dc2626;
    color: white !important;
}

</style>
"""
st.markdown(modern_css, unsafe_allow_html=True)


# =====================================================
#                SESSION CONTROL
# =====================================================
def init_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None

init_session()


# =====================================================
#                AUTH FUNCTIONS
# =====================================================
def signup_user(email, password):
    return requests.post(SIGNUP_URL, json={"email": email, "password": password, "returnSecureToken": True}).json()


def login_user(email, password):
    return requests.post(SIGNIN_URL, json={"email": email, "password": password, "returnSecureToken": True}).json()


# =====================================================
#                FIRESTORE HELPERS
# =====================================================
def firestore_add(collection, data):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    document = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.post(url, json=document)


@st.cache_data(ttl=10)
def firestore_get_all(collection):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    res = requests.get(url).json()

    if "documents" not in res:
        return []

    out = []
    for d in res["documents"]:
        fields = {k: v.get("stringValue", "") for k, v in d["fields"].items()}
        fields["id"] = d["name"].split("/")[-1]
        out.append(fields)

    return out


def firestore_update(collection, doc_id, data):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    document = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.patch(url, json=document)
    st.cache_data.clear()


def firestore_delete(collection, doc_id):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    requests.delete(url)
    st.cache_data.clear()


# =====================================================
#                AI PLANNER
# =====================================================
def safe_int(x):
    try: return int(x)
    except: return 0


def build_job_summary(email):
    jobs = firestore_get_all("jobs")
    jobs = [j for j in jobs if j.get("user_email") == email]

    if not jobs:
        return "No jobs found."

    lines = []
    total = 0
    pending = 0
    progress = 0
    done = 0

    for j in jobs:
        amt = safe_int(j["amount"])
        total += amt

        if j["status"] == "Pending": pending += 1
        elif j["status"] == "In Progress": progress += 1
        else: done += 1

        lines.append(f"- {j['job_name']} | {j['client_name']} | ₹{amt} | {j['status']}")

    return (
        f"Total jobs: {len(jobs)}, Pending: {pending}, In Progress: {progress}, Completed: {done}. "
        f"Total Amount: ₹{total}\n\n" + "\n".join(lines)
    )


def ask_ai(email, query):
    summary = build_job_summary(email)

    prompt = f"""
Analyze this factory job data and give:
- Today's work plan
- Tomorrow's plan
- High risk delays
- Efficiency suggestions

JOB DATA:
{summary}

QUESTION:
{query}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a factory planning expert."},
            {"role": "user", "content": prompt},
        ],
    }

    r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()
    return r["choices"][0]["message"]["content"]


# =====================================================
#              LOGIN PAGE (CENTERED)
# =====================================================
if st.session_state["user"] is None:

    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)

    st.markdown('<div class="center-box">', unsafe_allow_html=True)
    st.markdown("<h1>🔐 Factory Manager Login</h1>", unsafe_allow_html=True)

    mode = st.selectbox("Choose Mode", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")

    if mode == "Sign Up":
        confirm = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            r = login_user(email, pw)
            if "error" in r:
                st.error(r["error"]["message"])
            else:
                st.session_state["user"] = {"email": email}
                st.rerun()

        else:
            if pw != confirm:
                st.error("Passwords do not match.")
            else:
                r = signup_user(email, pw)
                if "error" in r:
                    st.error(r["error"]["message"])
                else:
                    st.success("Account created! You can now login.")

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()


# =====================================================
#              MAIN APP (SIDEBAR ENABLED)
# =====================================================
email = st.session_state["user"]["email"]

with st.sidebar:
    st.markdown('<div class="sidebar-title">📦 Factory Manager</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-label">Navigation</div>', unsafe_allow_html=True)

    page = st.radio("", ["Dashboard", "Add Job", "View Jobs", "AI Planner"], label_visibility="collapsed")

    if st.button("Logout", key="logout", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()


# =====================================================
#                 DASHBOARD
# =====================================================
if page == "Dashboard":
    st.title("📊 Dashboard")

    jobs = firestore_get_all("jobs")
    jobs = [j for j in jobs if j["user_email"] == email]

    if not jobs:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)
        df["amt"] = df["amount"].apply(safe_int)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Jobs", len(df))
        c2.metric("Pending", sum(df["status"] == "Pending"))
        c3.metric("Total Amount (₹)", df["amt"].sum())

        st.dataframe(df.drop(columns=["amt"]), use_container_width=True)


# =====================================================
#               ADD JOB
# =====================================================
elif page == "Add Job":
    st.title("➕ Add Job")

    jname = st.text_input("Job Name")
    cname = st.text_input("Client Name")
    phone = st.text_input("Phone Number")
    amt = st.number_input("Amount", min_value=0)
    jtype = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    notes = st.text_area("Notes")

    if st.button("Save Job"):
        firestore_add("jobs", {
            "job_name": jname,
            "client_name": cname,
            "phone": phone,
            "amount": amt,
            "job_type": jtype,
            "status": status,
            "notes": notes,
            "user_email": email,
            "created_at": datetime.utcnow().isoformat()
        })
        st.cache_data.clear()
        st.success("Job added successfully!")


# =====================================================
#              VIEW JOBS
# =====================================================
elif page == "View Jobs":
    st.title("📋 Manage Jobs")

    jobs = firestore_get_all("jobs")
    jobs = [j for j in jobs if j["user_email"] == email]

    if not jobs:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        jid = st.selectbox("Select Job", df["id"])
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


# =====================================================
#              AI PLANNER
# =====================================================
elif page == "AI Planner":
    st.title("🤖 AI Production Planner")

    q = st.text_area("Ask AI", "Give me today's factory plan.")

    if st.button("Generate Plan"):
        with st.spinner("AI analyzing your jobs..."):
            out = ask_ai(email, q)
        st.write(out)
