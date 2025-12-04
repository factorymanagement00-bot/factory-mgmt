import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# =============================================================
# CONFIG: FIREBASE + OPENROUTER
# =============================================================
PROJECT_ID = "factory-ai-ab9fa"

# Your Firebase Web API key (from Firebase console -> Project settings -> Web app)
API_KEY = "YOUR_FIREBASE_API_KEY_HERE"  # starts with AIza...

# Firestore base REST URL
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# Firebase Auth REST endpoints
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# OpenRouter key from Streamlit secrets (you added this in Secrets)
OPENROUTER_API_KEY = st.secrets["openrouter_key"]


# =============================================================
# FIRESTORE HELPERS (REST API)
# =============================================================
def firestore_add(collection: str, data: dict):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.post(url, json=payload)


@st.cache_data(ttl=30)
def firestore_get_all(collection: str):
    """
    Cached fetch of ALL documents in a collection.
    ttl=30 => refreshes every 30 seconds -> faster app.
    """
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


def firestore_update(collection: str, doc_id: str, data: dict):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.patch(url, json=payload)
    st.cache_data.clear()  # clear cache after write


def firestore_delete(collection: str, doc_id: str):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    requests.delete(url)
    st.cache_data.clear()  # clear cache after delete


def get_jobs_for_user(user_email: str):
    """Return only jobs created by this user (client-side filter)."""
    all_jobs = firestore_get_all("jobs")
    return [j for j in all_jobs if j.get("user_email") == user_email]


# =============================================================
# AUTH: SIGNUP + LOGIN USING FIREBASE AUTH REST
# =============================================================
def signup_user(email: str, password: str):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(SIGNUP_URL, json=payload)
    return resp.json()


def login_user(email: str, password: str):
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resp = requests.post(SIGNIN_URL, json=payload)
    return resp.json()


def init_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None


def require_login():
    if st.session_state["user"] is None:
        st.warning("Please login first to access the app.")
        st.stop()


# =============================================================
# AI: SMART FACTORY ASSISTANT USING OPENROUTER (DEEPSEEK)
# =============================================================
def build_jobs_summary_for_ai(user_email: str) -> str:
    jobs = get_jobs_for_user(user_email)

    if not jobs:
        return "There are currently no jobs in the factory."

    # try to convert amount to int safely
    def to_int(val, default=0):
        try:
            return int(val)
        except:
            return default

    summary_lines = []
    total_amount = 0
    status_counts = {"Pending": 0, "In Progress": 0, "Completed": 0}

    for j in jobs:
        amt = to_int(j.get("amount", 0))
        total_amount += amt
        status = j.get("status", "Unknown")
        if status in status_counts:
            status_counts[status] += 1

        summary_lines.append(
            f"- Job: {j.get('job_name','')} | Client: {j.get('client_name','')} | "
            f"Amount: {amt} | Status: {status} | Type: {j.get('job_type','')} | "
            f"Notes: {j.get('notes','')}"
        )

    summary_text = "\n".join(summary_lines)

    overview = (
        f"Total jobs: {len(jobs)}. "
        f"Pending: {status_counts['Pending']}, In Progress: {status_counts['In Progress']}, "
        f"Completed: {status_counts['Completed']}. "
        f"Total amount across all jobs: {total_amount}."
    )

    return f"{overview}\n\nJob details:\n{summary_text}"


def ask_ai(user_email: str, user_question: str) -> str:
    job_summary = build_jobs_summary_for_ai(user_email)

    final_prompt = (
        "You are an expert factory planner and production manager. "
        "You will be given the current job list of a cardboard/box factory, "
        "with status, amount, type and notes. "
        "Based on this, give a detailed, practical plan for what to do next, "
        "which jobs to prioritize, and how to schedule today's and tomorrow's work.\n\n"
        f"FACTORY JOB DATA:\n{job_summary}\n\n"
        f"USER QUESTION: {user_question}\n\n"
        "Provide:\n"
        "1) A priority-ordered job list\n"
        "2) What should be completed today vs tomorrow\n"
        "3) Any jobs at risk or delayed\n"
        "4) Suggestions to improve efficiency.\n"
    )

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a smart factory planning assistant."},
            {"role": "user", "content": final_prompt},
        ]
    }

    resp = requests.post(url, json=payload, headers=headers).json()

    if "error" in resp:
        return "❌ AI API Error: " + resp["error"].get("message", str(resp["error"]))

    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return "❌ Unexpected AI response: " + str(resp)


# =============================================================
# UI: LOGIN / SIGNUP SCREENS
# =============================================================
init_session()

auth_page = st.sidebar.selectbox("Auth", ["Login", "Sign Up"])

if st.session_state["user"] is None:
    st.title("🔐 Factory Manager Login")

    if auth_page == "Login":
        st.subheader("Login to your account")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            data = login_user(email, password)
            if "error" in data:
                st.error("Login failed: " + data["error"]["message"])
            else:
                st.success("Logged in successfully!")
                st.session_state["user"] = {
                    "email": data["email"],
                    "idToken": data["idToken"],
                    "localId": data["localId"],
                }
                st.experimental_rerun()

    else:  # Sign Up
        st.subheader("Create a new account")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        if st.button("Sign Up"):
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                data = signup_user(email, password)
                if "error" in data:
                    st.error("Sign up failed: " + data["error"]["message"])
                else:
                    st.success("Account created! You can now log in.")
else:
    # =========================================================
    # MAIN APP (ONLY AFTER LOGIN)
    # =========================================================
    user_email = st.session_state["user"]["email"]

    with st.sidebar:
        st.markdown(f"**Logged in as:** {user_email}")
        if st.button("Logout"):
            st.session_state["user"] = None
            st.experimental_rerun()

        page = st.radio("Navigation", ["Dashboard", "Add Job", "View Jobs", "AI Planner"])

    # -------------------- DASHBOARD -------------------------
    if page == "Dashboard":
        require_login()
        st.title("📊 Factory Dashboard")

        jobs = get_jobs_for_user(user_email)

        if not jobs:
            st.info("No jobs yet. Add some jobs first.")
        else:
            df = pd.DataFrame(jobs)

            # safely convert amount to int
            def to_int(x):
                try:
                    return int(x)
                except:
                    return 0

            df["amount_int"] = df["amount"].apply(to_int)

            total_jobs = len(df)
            total_amount = int(df["amount_int"].sum())
            pending = (df["status"] == "Pending").sum()
            progress = (df["status"] == "In Progress").sum()
            completed = (df["status"] == "Completed").sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Jobs", total_jobs)
            c2.metric("Pending", pending)
            c3.metric("In Progress", progress)
            c4.metric("Completed", completed)
            st.metric("Total Amount (₹)", total_amount)

            st.markdown("### Jobs Table")
            st.dataframe(df.drop(columns=["amount_int"]), use_container_width=True)

    # -------------------- ADD JOB -------------------------
    elif page == "Add Job":
        require_login()
        st.title("➕ Add New Job")

        col1, col2 = st.columns(2)

        with col1:
            job_name = st.text_input("Job Name")
            client_name = st.text_input("Client Name")
            phone = st.text_input("Phone Number")
        with col2:
            amount = st.number_input("Amount (₹)", min_value=0)
            status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
            job_type = st.text_input("Job Type (e.g., Box, Printing, Die Cutting)")

        notes = st.text_area("Notes")

        if st.button("Save Job"):
            data = {
                "job_name": job_name,
                "client_name": client_name,
                "phone": phone,
                "amount": amount,
                "status": status,
                "job_type": job_type,
                "notes": notes,
                "created_at": datetime.utcnow().isoformat(),
                "user_email": user_email,
            }
            firestore_add("jobs", data)
            st.cache_data.clear()
            st.success("Job saved!")

    # -------------------- VIEW / EDIT JOBS ----------------
    elif page == "View Jobs":
        require_login()
        st.title("📋 View / Edit Jobs")

        jobs = get_jobs_for_user(user_email)

        if not jobs:
            st.info("No jobs found.")
        else:
            df = pd.DataFrame(jobs)
            st.dataframe(df, use_container_width=True)

            st.subheader("Edit or Delete Job")
            selected_id = st.selectbox("Select Job ID", df["id"])
            job = df[df["id"] == selected_id].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                new_status = st.selectbox(
                    "Status",
                    ["Pending", "In Progress", "Completed"],
                    index=["Pending", "In Progress", "Completed"].index(job["status"])
                )
                new_amount = st.number_input("Amount (₹)", min_value=0, value=int(job["amount"]))
            with col2:
                new_notes = st.text_area("Notes", job["notes"])

            if st.button("Update Job"):
                firestore_update("jobs", selected_id, {
                    "status": new_status,
                    "amount": new_amount,
                    "notes": new_notes
                })
                st.success("Job updated! Refresh page to see latest data.")

            if st.button("Delete Job"):
                firestore_delete("jobs", selected_id)
                st.warning("Job deleted!")

    # -------------------- AI PLANNER ----------------------
    elif page == "AI Planner":
        require_login()
        st.title("🤖 Smart Factory Planner (AI)")
        st.write("AI reads your jobs and gives you a work plan.")

        q_default = "Give me a plan for what I should complete today and tomorrow."
        user_q = st.text_area("Ask the AI planner:", q_default, height=80)

        if st.button("Generate Plan"):
            with st.spinner("Asking AI..."):
                reply = ask_ai(user_email, user_q)
            st.markdown("### 📌 AI Plan:")
            st.write(reply)
