import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# =============================================================
# CONFIG: FIREBASE + OPENROUTER
# =============================================================

PROJECT_ID = "factory-ai-ab9fa"

# Replace with your REAL Firebase Web API key (starts with AIzaSy...)
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"

# Firestore REST URL
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# Firebase Auth API endpoints
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# OpenRouter API key (set in Streamlit Secrets)
OPENROUTER_API_KEY = st.secrets["openrouter_key"]


# =============================================================
# FIRESTORE FUNCTIONS
# =============================================================

def firestore_add(collection: str, data: dict):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.post(url, json=payload)


@st.cache_data(ttl=20)
def firestore_get_all(collection: str):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    res = requests.get(url).json()

    if "documents" not in res:
        return []

    items = []
    for doc in res["documents"]:
        row = {k: v.get("stringValue", "") for k, v in doc["fields"].items()}
        row["id"] = doc["name"].split("/")[-1]
        items.append(row)

    return items


def firestore_update(collection, doc_id, data):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.patch(url, json=payload)
    st.cache_data.clear()


def firestore_delete(collection, doc_id):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    requests.delete(url)
    st.cache_data.clear()


def get_jobs_for_user(user_email):
    all_jobs = firestore_get_all("jobs")
    return [j for j in all_jobs if j.get("user_email") == user_email]


# =============================================================
# AUTH FUNCTIONS (Firebase Auth REST)
# =============================================================

def signup_user(email, password):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(SIGNUP_URL, json=payload).json()


def login_user(email, password):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(SIGNIN_URL, json=payload).json()


def init_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None


def require_login():
    if st.session_state["user"] is None:
        st.warning("Please log in first.")
        st.stop()


# =============================================================
# AI PLANNER (DeepSeek via OpenRouter)
# =============================================================

def _safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


def build_jobs_summary(user_email):
    jobs = get_jobs_for_user(user_email)

    if not jobs:
        return "No jobs found."

    lines = []
    status_count = {"Pending": 0, "In Progress": 0, "Completed": 0}
    total_amount = 0

    for j in jobs:
        amt = _safe_int(j.get("amount", 0))
        total_amount += amt
        stt = j.get("status", "Unknown")

        if stt in status_count:
            status_count[stt] += 1

        lines.append(
            f"- Job: {j.get('job_name')} | Client: {j.get('client_name')} | Amount: {amt} | "
            f"Status: {stt} | Type: {j.get('job_type')} | Notes: {j.get('notes')}"
        )

    return (
        f"Total Jobs: {len(jobs)}, Pending: {status_count['Pending']}, "
        f"In Progress: {status_count['In Progress']}, Completed: {status_count['Completed']}. "
        f"Total Amount: {total_amount}.\n\n"
        "JOB DETAILS:\n" + "\n".join(lines)
    )


def ask_ai(user_email, question):
    job_summary = build_jobs_summary(user_email)

    prompt = (
        "You are a professional factory planning expert. Analyze the job data and create:\n"
        "- A prioritized job list\n"
        "- What should be completed today and tomorrow\n"
        "- Delayed / risky jobs\n"
        "- Efficiency improvement suggestions\n\n"
        f"FACTORY JOB DATA:\n{job_summary}\n\n"
        f"QUESTION: {question}"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a top-tier factory planning assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers).json()

    if "error" in res:
        return "❌ AI Error: " + res["error"]["message"]

    return res["choices"][0]["message"]["content"]


# =============================================================
# LOGIN / SIGN UP UI
# =============================================================

init_session()

auth_page = st.sidebar.selectbox("Auth", ["Login", "Sign Up"])

if st.session_state["user"] is None:
    st.title("🔐 Factory Manager Login")

    # LOGIN
    if auth_page == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            res = login_user(email, password)
            if "error" in res:
                st.error("Login failed: " + res["error"]["message"])
            else:
                st.success("Logged in successfully!")
                st.session_state["user"] = {
                    "email": res["email"],
                    "idToken": res["idToken"],
                    "localId": res["localId"],
                }
                st.rerun()   # FIXED ✔

    # SIGN UP
    else:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        if st.button("Sign Up"):
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                res = signup_user(email, password)
                if "error" in res:
                    st.error("Sign up failed: " + res["error"]["message"])
                else:
                    st.success("Account created! Please login.")

else:
    # =============================================================
    # MAIN APP (AFTER LOGIN)
    # =============================================================

    user_email = st.session_state["user"]["email"]

    with st.sidebar:
        st.markdown(f"**Logged in as:** {user_email}")
        if st.button("Logout"):
            st.session_state["user"] = None
            st.rerun()

        page = st.radio("Navigate", ["Dashboard", "Add Job", "View Jobs", "AI Planner"])

    # -------------------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------------------
    if page == "Dashboard":
        st.title("📊 Factory Dashboard")

        jobs = get_jobs_for_user(user_email)

        if not jobs:
            st.info("No jobs added yet.")
        else:
            df = pd.DataFrame(jobs)

            df["amount_int"] = df["amount"].apply(_safe_int)

            st.metric("Total Jobs", len(df))
            st.metric("Total Amount (₹)", df["amount_int"].sum())
            st.metric("Pending Jobs", sum(df["status"] == "Pending"))

            st.dataframe(df.drop(columns=["amount_int"]), use_container_width=True)

    # -------------------------------------------------------------
    # ADD JOB
    # -------------------------------------------------------------
    elif page == "Add Job":
        st.title("➕ Add Job")

        job_name = st.text_input("Job Name")
        client_name = st.text_input("Client Name")
        phone = st.text_input("Phone Number")
        amount = st.number_input("Amount (₹)", min_value=0)
        status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
        job_type = st.text_input("Job Type")
        notes = st.text_area("Notes")

        if st.button("Save Job"):
            firestore_add("jobs", {
                "job_name": job_name,
                "client_name": client_name,
                "phone": phone,
                "amount": amount,
                "status": status,
                "job_type": job_type,
                "notes": notes,
                "created_at": datetime.utcnow().isoformat(),
                "user_email": user_email,
            })
            st.cache_data.clear()
            st.success("Job added!")

    # -------------------------------------------------------------
    # VIEW JOBS
    # -------------------------------------------------------------
    elif page == "View Jobs":
        st.title("📋 View & Edit Jobs")

        jobs = get_jobs_for_user(user_email)

        if not jobs:
            st.info("No jobs found.")
        else:
            df = pd.DataFrame(jobs)
            st.dataframe(df, use_container_width=True)

            selected = st.selectbox("Select Job ID", df["id"])
            job = df[df["id"] == selected].iloc[0]

            new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"], 
                                      index=["Pending", "In Progress", "Completed"].index(job["status"]))
            new_amount = st.number_input("Amount (₹)", value=_safe_int(job["amount"]))
            new_notes = st.text_area("Notes", job["notes"])

            if st.button("Update"):
                firestore_update("jobs", selected, {
                    "status": new_status,
                    "amount": new_amount,
                    "notes": new_notes
                })
                st.success("Updated!")

            if st.button("Delete"):
                firestore_delete("jobs", selected)
                st.warning("Deleted!")

    # -------------------------------------------------------------
    # AI PLANNER
    # -------------------------------------------------------------
    elif page == "AI Planner":
        st.title("🤖 Smart AI Planner")

        question = st.text_area("Ask AI:", "Give me today's factory plan.")

        if st.button("Generate Plan"):
            with st.spinner("AI thinking..."):
                answer = ask_ai(user_email, question)
            st.markdown("### 📌 AI Plan:")
            st.write(answer)
