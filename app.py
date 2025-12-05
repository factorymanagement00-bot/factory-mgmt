import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, date, timedelta

# ============================================
# APP SETTINGS
# ============================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"          # <-- put your Firebase Web API key here
OPENROUTER_KEY = st.secrets["openrouter_key"]  # <-- set in Streamlit secrets

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ============================================
# BASE CSS
# ============================================
base_css = """
<style>
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Hide sidebar container when logged out */
.no-sidebar [data-testid="stSidebar"] {
    display: none !important;
}

/* LOGIN STYLES */
.login-wrapper {
    max-width: 430px;
    margin: 160px auto !important;
}
.login-card {
    padding: 40px;
    background: rgba(17, 25, 40, 0.65);
    backdrop-filter: blur(18px);
    border-radius: 18px;
    border: 1px solid rgba(148,163,184,0.4);
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
    background: #020617 !important;
    padding: 20px 16px !important;
    border-right: 1px solid rgba(30,64,175,0.7);
}

/* Sidebar header */
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

/* Toggle button */
.collapse-btn button {
    background: #020617 !important;
    border-radius: 999px !important;
    border: 1px solid #4b5563 !important;
    color: #e5e7eb !important;
    padding: 6px 9px !important;
    font-size: 16px !important;
}

/* Nav buttons */
.navbox button {
    width: 100% !important;
    background: #111827 !important;
    border-radius: 999px !important;
    border: 1px solid #4b5563 !important;
    color: #e5e7eb !important;
    padding: 10px 16px !important;
    text-align: left !important;
    font-size: 15px !important;
    margin-bottom: 10px;
    transition: all 0.18s ease-in-out;
}
.navbox button:hover {
    background: #1e293b !important;
    transform: translateX(2px);
}
.nav-selected button {
    background: #3b82f6 !important;
    border-color: #60a5fa !important;
    color: white !important;
    font-weight: 600 !important;
}

/* Logout */
.logout-btn button {
    width: 100% !important;
    margin-top: 30px;
    background: #dc2626 !important;
    color: white !important;
    border-radius: 999px !important;
    padding: 10px 16px !important;
    border: none !important;
}
.logout-btn button:hover {
    background: #f97373 !important;
}

/* Dashboard cards */
.metric-card {
    background: #020617;
    padding: 20px;
    border-radius: 16px;
    border: 1px solid #1f2937;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
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

.block-container {
    padding-top: 24px !important;
}
</style>
"""
st.markdown(base_css, unsafe_allow_html=True)

# ============================================
# COLLAPSE STATE & EXTRA CSS
# ============================================
if "sidebar_collapsed" not in st.session_state:
    st.session_state["sidebar_collapsed"] = False

# When collapsed: hide title text and center icons
if st.session_state["sidebar_collapsed"]:
    collapsed_css = """
    <style>
    .sidebar-title-text { display: none !important; }
    .navbox button {
        text-align: center !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    </style>
    """
    st.markdown(collapsed_css, unsafe_allow_html=True)

# ============================================
# SESSION INIT
# ============================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"
if "job_processes" not in st.session_state:
    st.session_state["job_processes"] = []  # used in Add Job process builder

def safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

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

Factory jobs for reference (only use if the question is about work, production, jobs, or money):
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
                        "You can answer ANY general question AND also give smart factory planning advice. "
                        "Only use the job data when it's relevant."
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
# AI PLAN GENERATION (NO LLM, SMART SCHEDULER)
# ============================================
DAILY_HOURS = 8  # number of working hours per day

def parse_processes(processes_str):
    try:
        data = json.loads(processes_str)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def build_ai_plan(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    tasks = []

    for j in jobs:
        job_name = j.get("job_name", "")
        due_str = j.get("due_date", "")
        try:
            due = date.fromisoformat(due_str) if due_str else None
        except Exception:
            due = None

        processes = parse_processes(j.get("processes", "[]"))
        for p in processes:
            pname = p.get("name", "")
            hrs = safe_float(p.get("hours", 0))
            if hrs <= 0:
                continue
            tasks.append(
                {
                    "job": job_name,
                    "process": pname,
                    "hours": hrs,
                    "due_date": due,
                }
            )

    if not tasks:
        return pd.DataFrame()

    # sort by due date (None last), then by job
    tasks.sort(key=lambda x: (x["due_date"] or date(2100, 1, 1), x["job"]))

    rows = []
    current_day = 1
    remaining_hours = DAILY_HOURS
    today = date.today()

    for t in tasks:
        hrs = t["hours"]
        if hrs > remaining_hours:  # move to next day
            current_day += 1
            remaining_hours = DAILY_HOURS

        plan_date = today + timedelta(days=current_day - 1)
        remaining_hours -= hrs

        rows.append(
            {
                "Day": f"Day {current_day}",
                "Planned Date": plan_date.isoformat(),
                "Job": t["job"],
                "Process": t["process"],
                "Hours": hrs,
                "Due Date": t["due_date"].isoformat() if t["due_date"] else "",
            }
        )

    df = pd.DataFrame(rows)
    st.session_state["last_plan_df"] = df.to_dict("records")
    return df

# ============================================
# LOGIN PAGE (CENTERED)
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
# SIDEBAR (CLEAN COLLAPSE: ICONS ONLY)
# ============================================
with st.sidebar:
    # header: toggle + title
    col_toggle, col_title = st.columns([1, 4])
    with col_toggle:
        st.markdown('<div class="collapse-btn">', unsafe_allow_html=True)
        toggle_label = "☰" if st.session_state["sidebar_collapsed"] else "⮜"
        if st.button(toggle_label, key="toggle_sidebar"):
            st.session_state["sidebar_collapsed"] = not st.session_state["sidebar_collapsed"]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col_title:
        st.markdown(
            '<div class="sidebar-header"><div class="sidebar-title-text">📦 Factory</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    def nav_btn(label, icon, page_name):
        box_class = "nav-selected" if st.session_state["page"] == page_name else "navbox"
        text = icon if st.session_state["sidebar_collapsed"] else f"{icon}  {label}"
        with st.container():
            st.markdown(f'<div class="{box_class}">', unsafe_allow_html=True)
            if st.button(text, key=f"nav_{page_name}"):
                st.session_state["page"] = page_name
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    nav_btn("Dashboard", "🏠", "Dashboard")
    nav_btn("Add Job", "➕", "AddJob")
    nav_btn("View Jobs", "📋", "ViewJobs")
    nav_btn("AI Chat", "🤖", "AI")
    nav_btn("AI Plan", "📅", "AIPlan")

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
    due_date = st.date_input("Due Date", value=date.today())

    st.markdown("### 🧩 Job Processes")

    # Process builder
    col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
    with col_p1:
        proc_name = st.text_input("Process Name", key="proc_name")
    with col_p2:
        proc_hours = st.number_input("Hours", min_value=0.0, step=0.25, key="proc_hours")
    with col_p3:
        if st.button("Add Process"):
            if proc_name and proc_hours > 0:
                st.session_state["job_processes"].append(
                    {"name": proc_name, "hours": proc_hours}
                )
                st.session_state["proc_name"] = ""
                st.session_state["proc_hours"] = 0.0

    # Show current processes
    if st.session_state["job_processes"]:
        st.table(pd.DataFrame(st.session_state["job_processes"]))
    else:
        st.caption("No processes added yet. Add steps above.")

    if st.button("Save Job"):
        processes_json = json.dumps(st.session_state["job_processes"])
        fs_add(
            "jobs",
            {
                "job_name": job_name,
                "client_name": client_name,
                "phone": phone,
                "amount": amount,
                "job_type": job_type,
                "status": status,
                "notes": "",
                "user_email": user_email,
                "created_at": datetime.utcnow().isoformat(),
                "due_date": due_date.isoformat(),
                "processes": processes_json,
            },
        )
        st.session_state["job_processes"] = []
        st.cache_data.clear()
        st.success("Job with processes saved!")

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
        new_notes = st.text_area("Notes", job.get("notes", ""))

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

    q = st.text_area(
        "Ask anything:",
        "Give me today's factory plan and also tell me a random tech fact.",
    )
    if st.button("Ask AI"):
        with st.spinner("AI thinking..."):
            answer = ask_ai(user_email, q)
        st.write(answer)

# ---------- AI Plan ----------
elif page == "AIPlan":
    st.title("📅 AI Production Plan")

    st.write("This will use all jobs, their processes, durations, and due dates to build a simple schedule.")
    if st.button("Generate Plan"):
        df_plan = build_ai_plan(user_email)
        if df_plan.empty:
            st.warning("No processes found. Add processes to jobs first in 'Add Job'.")
        else:
            st.success("Plan generated!")
            st.dataframe(df_plan, use_container_width=True)
    else:
        # If we already generated a plan in this session, show it
        records = st.session_state.get("last_plan_df", [])
        if records:
            st.dataframe(pd.DataFrame(records), use_container_width=True)
        else:
            st.info("Click 'Generate Plan' to create a schedule.")
