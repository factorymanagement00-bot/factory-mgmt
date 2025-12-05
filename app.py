import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# ===================== FIREBASE CONFIG =====================
PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"   # <-- YOUR FIREBASE WEB API KEY

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

OPENROUTER_KEY = st.secrets["openrouter_key"]  # OpenRouter Chat Key


# ======================= MODERN LOGIN PAGE CSS =======================
login_css = """
<style>
section[data-testid="stSidebar"] { display: none !important; }

.center-box {
    max-width: 420px;
    margin: 120px auto;
    padding: 40px;
    background: #111827;
    border-radius: 14px;
    box-shadow: 0 0 30px rgba(0,0,0,0.5);
}
.center-box h1 {
    text-align: center;
    font-size: 30px;
    color: white;
    margin-bottom: 20px;
}
</style>
"""


# ============================ SESSION ============================
def init_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None


init_session()


# ======================= FIREBASE AUTH ============================
def signup_user(email, password):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(SIGNUP_URL, json=payload).json()


def login_user(email, password):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(SIGNIN_URL, json=payload).json()


# ========================= FIRESTORE HELPERS =========================
def firestore_add(collection, data):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.post(url, json=payload)


@st.cache_data(ttl=15)
def firestore_get_all(collection):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    res = requests.get(url).json()

    if "documents" not in res:
        return []

    out = []
    for doc in res["documents"]:
        row = {k: v.get("stringValue", "") for k, v in doc["fields"].items()}
        row["id"] = doc["name"].split("/")[-1]
        out.append(row)

    return out


def firestore_update(collection, doc_id, data):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.patch(url, json=payload)
    st.cache_data.clear()


def firestore_delete(collection, doc_id):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    requests.delete(url)
    st.cache_data.clear()


def get_user_jobs(email):
    jobs = firestore_get_all("jobs")
    return [j for j in jobs if j.get("user_email") == email]


# ============================ AI PLANNER ============================
def safe_int(x):
    try:
        return int(x)
    except:
        return 0


def build_job_summary(email):
    jobs = get_user_jobs(email)
    if not jobs:
        return "No jobs found."

    total_amt = 0
    pending = 0
    working = 0
    done = 0

    lines = []

    for j in jobs:
        amt = safe_int(j.get("amount"))
        total_amt += amt

        status = j.get("status")
        if status == "Pending":
            pending += 1
        elif status == "In Progress":
            working += 1
        elif status == "Completed":
            done += 1

        lines.append(
            f"- {j.get('job_name')} ({j.get('job_type')}) | Client: {j.get('client_name')} | ₹{amt} | {status}"
        )

    return (
        f"Total: {len(jobs)}, Pending: {pending}, Working: {working}, Done: {done}. "
        f"Total Value: ₹{total_amt}\n\nJobs:\n" + "\n".join(lines)
    )


def ask_ai(email, question):
    job_summary = build_job_summary(email)

    prompt = f"""
You are a factory planning expert. Analyze the following jobs and give:
- Today's plan
- Tomorrow's plan
- Risky jobs
- Efficiency suggestions

JOB DATA:
{job_summary}

QUESTION:
{question}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are an expert production planner."},
            {"role": "user", "content": prompt},
        ],
    }

    res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()

    return res["choices"][0]["message"]["content"]


# ============================== LOGIN SCREEN ==============================
if st.session_state["user"] is None:

    st.markdown(login_css, unsafe_allow_html=True)
    st.markdown('<div class="center-box">', unsafe_allow_html=True)

    st.markdown("### 🔐 Factory Manager Login")

    mode = st.selectbox("Choose Mode:", ["Login", "Sign Up"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if mode == "Sign Up":
        confirm = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            res = login_user(email, password)
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                st.session_state["user"] = {"email": email, "idToken": res["idToken"]}
                st.rerun()

        else:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                res = signup_user(email, password)
                if "error" in res:
                    st.error(res["error"]["message"])
                else:
                    st.success("Account created! Please login.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ============================== MAIN APP ==============================
# Sidebar becomes visible ONLY AFTER LOGIN
with st.sidebar:
    st.title("📦 Factory Manager")

    page = st.radio("Navigate", ["Dashboard", "Add Job", "View Jobs", "AI Planner"])

    if st.button("Logout"):
        st.session_state["user"] = None
        st.rerun()


email = st.session_state["user"]["email"]


# ============================== PAGES ==============================

# ---- DASHBOARD ----
if page == "Dashboard":
    st.title("📊 Dashboard")

    jobs = get_user_jobs(email)

    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        df["amount_int"] = df["amount"].apply(safe_int)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Jobs", len(df))
        col2.metric("Pending", sum(df["status"] == "Pending"))
        col3.metric("Total Value (₹)", df["amount_int"].sum())

        st.dataframe(df.drop(columns=["amount_int"]), use_container_width=True)


# ---- ADD JOB ----
elif page == "Add Job":
    st.title("➕ Add Job")

    job_name = st.text_input("Job Name")
    client_name = st.text_input("Client Name")
    phone = st.text_input("Phone")
    amount = st.number_input("Amount", min_value=0)
    job_type = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    notes = st.text_area("Notes")

    if st.button("Save"):
        firestore_add("jobs", {
            "job_name": job_name,
            "client_name": client_name,
            "phone": phone,
            "amount": amount,
            "job_type": job_type,
            "status": status,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
            "user_email": email,
        })
        st.cache_data.clear()
        st.success("Saved!")


# ---- VIEW JOBS ----
elif page == "View Jobs":
    st.title("📋 Manage Jobs")

    jobs = get_user_jobs(email)
    if not jobs:
        st.info("No jobs added.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        job_id = st.selectbox("Select Job ID", df["id"])
        job = df[df["id"] == job_id].iloc[0]

        new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"],
                                  index=["Pending", "In Progress", "Completed"].index(job["status"]))
        new_amount = st.number_input("Amount", value=safe_int(job["amount"]))
        new_notes = st.text_area("Notes", job["notes"])

        if st.button("Update Job"):
            firestore_update("jobs", job_id, {
                "status": new_status,
                "amount": new_amount,
                "notes": new_notes,
            })
            st.success("Updated!")

        if st.button("Delete Job"):
            firestore_delete("jobs", job_id)
            st.warning("Deleted!")


# ---- AI PLANNER ----
elif page == "AI Planner":
    st.title("🤖 Smart AI Planner")

    question = st.text_area("Ask AI", "Give me today's production plan.")

    if st.button("Generate Plan"):
        with st.spinner("AI Thinking..."):
            ans = ask_ai(email, question)
        st.write(ans)
