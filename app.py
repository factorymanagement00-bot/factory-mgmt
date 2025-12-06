import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime, date, time, timedelta

# ============================================
# APP SETTINGS
# ============================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"                         # your Firebase project id
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"     # your Firebase Web API key

# ---- OPENROUTER KEY: VERCEL + STREAMLIT SAFE ----
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")  # For Vercel / any host env

if not OPENROUTER_KEY:
    # Fallback for Streamlit secrets (Streamlit Cloud etc.)
    try:
        OPENROUTER_KEY = st.secrets["openrouter_key"]
    except Exception:
        st.error("OPENROUTER_KEY not found. Set it as env var or in Streamlit secrets.")
        st.stop()

BASE_URL = (
    f"https://firestore.googleapis.com/v1/projects/"
    f"{PROJECT_ID}/databases/(default)/documents"
)
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

/* Hide sidebar when logged out */
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

/* SIDEBAR */
[data-testid="stSidebar"] {
    background: #020617 !important;
    padding: 20px 16px !important;
    border-right: 1px solid rgba(30,64,175,0.7);
}
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
/* Toggle */
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

/* Mobile tweaks */
@media (max-width: 768px) {
  .block-container {
      padding-left: 0.5rem !important;
      padding-right: 0.5rem !important;
  }
  .metric-card {
      padding: 12px;
  }
  .login-card {
      margin: 80px auto !important;
      padding: 24px;
  }
}
</style>
"""
st.markdown(base_css, unsafe_allow_html=True)

# Sidebar collapse CSS
if "sidebar_collapsed" not in st.session_state:
    st.session_state["sidebar_collapsed"] = False

if st.session_state["sidebar_collapsed"]:
    st.markdown(
        """
        <style>
        .sidebar-title-text { display: none !important; }
        .navbox button {
            text-align: center !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================
# SESSION INIT
# ============================================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"
if "job_processes" not in st.session_state:
    st.session_state["job_processes"] = []
if "last_ai_answer" not in st.session_state:
    st.session_state["last_ai_answer"] = ""
if "last_plan_df" not in st.session_state:
    st.session_state["last_plan_df"] = []
if "schedule_settings" not in st.session_state:
    st.session_state["schedule_settings"] = {
        "work_start": time(9, 0),
        "work_end": time(17, 0),
        "breaks": [],
    }
if "ai_history" not in st.session_state:
    # list of {"user": "...", "assistant": "..."}
    st.session_state["ai_history"] = []

# ============================================
# SMALL UTILS
# ============================================
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
# STOCK HELPERS
# ============================================
def get_user_stocks(email):
    stocks = [s for s in fs_get("stocks") if s.get("user_email") == email]
    for s in stocks:
        s["quantity_float"] = safe_float(s.get("quantity", 0))
    return stocks

def adjust_stock_after_job(stock_id, used_qty):
    if not stock_id or used_qty <= 0:
        return
    stocks = fs_get("stocks")
    for s in stocks:
        if s["id"] == stock_id:
            current = safe_float(s.get("quantity", 0))
            remaining = current - used_qty
            if remaining <= 0:
                fs_delete("stocks", stock_id)
            else:
                fs_update("stocks", stock_id, {"quantity": remaining})
            break

# ============================================
# AI — DATA SUMMARIES FOR CONTEXT
# ============================================
def job_summary(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        return "No jobs in the system yet."
    return "\n".join(
        f"- {j['job_name']} | {j['status']} | Qty {j.get('quantity','')} | Amount ₹{j['amount']} | Due {j.get('due_date','')}"
        for j in jobs
    )

def stock_summary(email):
    stocks = get_user_stocks(email)
    if not stocks:
        return "No stock items currently available."
    return "\n".join(
        f"- {s['name']} ({s.get('category','')}) : {s['quantity_float']}"
        for s in stocks
    )

# ============================================
# AI — GENERAL + FACTORY (CHAT AI WITH MEMORY)
# ============================================
def ask_ai(email, query):
    jobs_text = job_summary(email)
    stocks_text = stock_summary(email)

    system_prompt = """
You are FactoryGPT, an expert assistant that helps manage a small factory.

You can:
- Answer GENERAL questions (life, maths, etc).
- Help with FACTORY jobs, processes, schedules, and stock.
- When user asks for a PLAN or SCHEDULE, you will design a practical daily plan.
- Your tone is friendly but clear.
"""

    history = st.session_state.get("ai_history", [])

    messages = [{"role": "system", "content": system_prompt}]

    # add previous conversation
    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    # latest question with current data snapshot
    user_prompt = f"""
User question:
{query}

Current factory snapshot:

Jobs:
{jobs_text}

Stock:
{stocks_text}

Use factory data when relevant. Otherwise treat it as a normal chat.
"""
    messages.append({"role": "user", "content": user_prompt})

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": "deepseek/deepseek-chat", "messages": messages},
    ).json()

    try:
        answer = resp["choices"][0]["message"]["content"]
    except Exception:
        answer = "AI error: " + str(resp)

    # update memory
    history.append({"user": query, "assistant": answer})
    # keep last 10 turns
    st.session_state["ai_history"] = history[-10:]

    return answer

# ============================================
# PLANNING HELPERS
# ============================================
def parse_processes(processes_str):
    try:
        data = json.loads(processes_str)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def get_schedule_settings():
    return st.session_state["schedule_settings"]

def is_planning_query(text: str) -> bool:
    if not text:
        return False
    text = text.lower()
    keywords = [
        "plan",
        "planning",
        "schedule",
        "today work",
        "tomorrow work",
        "factory plan",
        "production plan",
        "due date",
        "priority",
        "what should i do first",
        "work plan",
        "job plan",
        "make a plan",
        "generate a plan",
        "generate schedule",
    ]
    return any(k in text for k in keywords)

def build_ai_plan(email, work_start, work_end, breaks):
    """
    Build a time-based plan using daily working hours + breaks.
    breaks: list of (time_start, time_end)
    """

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    tasks = []

    for j in jobs:
        job_name = j.get("job_name", "")
        due_str = j.get("due_date", "")
        try:
            due_dt = date.fromisoformat(due_str) if due_str else None
        except Exception:
            due_dt = None

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
                    "due_date": due_dt,
                }
            )

    if not tasks:
        return pd.DataFrame()

    # sort by due date then job
    tasks.sort(key=lambda x: (x["due_date"] or date(2100, 1, 1), x["job"]))

    def next_work_start(current_dt):
        """Move current_dt to next working moment (respecting breaks & hours)."""
        while True:
            day = current_dt.date()
            day_start = datetime.combine(day, work_start)
            day_end = datetime.combine(day, work_end)

            # before work -> jump to start
            if current_dt < day_start:
                current_dt = day_start

            # after work -> next day
            if current_dt >= day_end:
                current_dt = datetime.combine(day + timedelta(days=1), work_start)
                continue

            todays_breaks = [
                (datetime.combine(day, b_start), datetime.combine(day, b_end))
                for (b_start, b_end) in breaks
                if b_start and b_end and b_end > b_start
            ]

            moved = False
            for b_start_dt, b_end_dt in todays_breaks:
                if b_start_dt <= current_dt < b_end_dt:
                    current_dt = b_end_dt
                    moved = True
                    break

            if moved:
                continue

            return current_dt

    rows = []
    today = date.today()
    current_dt = datetime.combine(today, work_start)
    day_index_by_date = {}

    def day_label(d):
        if d not in day_index_by_date:
            day_index_by_date[d] = len(day_index_by_date) + 1
        return f"Day {day_index_by_date[d]}"

    for t in tasks:
        hours_remaining = float(t["hours"])
        while hours_remaining > 1e-9:
            current_dt = next_work_start(current_dt)
            d = current_dt.date()
            day_end = datetime.combine(d, work_end)

            todays_breaks = [
                (datetime.combine(d, b_start), datetime.combine(d, b_end))
                for (b_start, b_end) in breaks
                if b_start and b_end and b_end > b_start
            ]

            boundary = day_end
            for b_start_dt, b_end_dt in todays_breaks:
                if current_dt < b_start_dt < boundary:
                    boundary = b_start_dt

            max_avail_hours = (boundary - current_dt).total_seconds() / 3600.0
            if max_avail_hours <= 1e-9:
                current_dt = boundary
                continue

            slot_hours = min(hours_remaining, max_avail_hours)
            end_dt = current_dt + timedelta(hours=slot_hours)

            rows.append(
                {
                    "Day": day_label(d),
                    "Planned Start": current_dt.strftime("%Y-%m-%d %I:%M %p"),
                    "Planned End": end_dt.strftime("%Y-%m-%d %I:%M %p"),
                    "Job": t["job"],
                    "Process": t["process"],
                    "Hours": round(slot_hours, 2),
                    "Due Date": t["due_date"].isoformat() if t["due_date"] else "",
                }
            )

            hours_remaining -= slot_hours
            current_dt = end_dt

    df = pd.DataFrame(rows)
    st.session_state["last_plan_df"] = df.to_dict("records")
    return df

# ============================================
# LOGIN PAGE
# ============================================
if st.session_state["user"] is None:
    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-wrapper"><div class="login-card">', unsafe_allow_html=True
    )

    st.markdown(
        '<div class="login-title">🔐 Factory Manager Login</div>',
        unsafe_allow_html=True,
    )

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
# SIDEBAR
# ============================================
with st.sidebar:
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
    nav_btn("Add Stock", "📦", "AddStock")
    nav_btn("View Jobs", "📋", "ViewJobs")
    nav_btn("AI Chat", "🤖", "AI")
    nav_btn("AI Production Plan", "📅", "AIPlan")

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

# ---------- DASHBOARD ----------
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

# ---------- ADD JOB ----------
elif page == "AddJob":
    st.title("➕ Add New Job")

    job_name = st.text_input("Job Name")
    client_name = st.text_input("Client Name")
    phone = st.text_input("Phone")
    amount = st.number_input("Amount", min_value=0)
    quantity = st.number_input("Quantity (pieces / units)", min_value=1, step=1)
    job_type = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    due_date = st.date_input("Due Date", value=date.today())

    st.markdown("### 🧩 Job Processes")

    col_p1, col_p2, col_p3 = st.columns([3, 1, 1])
    with col_p1:
        proc_name = st.text_input("Process Name")

    with col_p2:
        proc_hours = st.number_input("Hours", min_value=0.0, step=0.25)

    # Add process button (no rerun, no weird session state)
    with col_p3:
        if st.button("Add Process"):
            if proc_name and proc_hours > 0:
                st.session_state["job_processes"].append(
                    {"name": proc_name, "hours": proc_hours}
                )
            else:
                st.warning("Give a process name and hours > 0.")

    if st.session_state["job_processes"]:
        st.table(pd.DataFrame(st.session_state["job_processes"]))
    else:
        st.caption("No processes added yet. Add steps above.")

    st.markdown("### 🧰 Stock Used (optional)")
    stocks = get_user_stocks(user_email)
    stock_options = ["None"] + [
        f"{s['name']} ({s.get('category','')}) — {s['quantity_float']}" for s in stocks
    ]
    selected_stock_label = st.selectbox("Select Stock", stock_options)

    stock_use_qty = 0.0
    selected_stock_id = ""
    if selected_stock_label != "None":
        idx = stock_options.index(selected_stock_label) - 1
        selected_stock = stocks[idx]
        selected_stock_id = selected_stock["id"]
        max_qty = selected_stock["quantity_float"]
        stock_use_qty = st.number_input(
            "Stock quantity to use", min_value=0.0, max_value=max_qty, step=0.5
        )

    if st.button("Save Job"):
        processes_json = json.dumps(st.session_state["job_processes"])
        fs_add(
            "jobs",
            {
                "job_name": job_name,
                "client_name": client_name,
                "phone": phone,
                "amount": amount,
                "quantity": quantity,
                "job_type": job_type,
                "status": status,
                "notes": "",
                "user_email": user_email,
                "created_at": datetime.utcnow().isoformat(),
                "due_date": due_date.isoformat(),
                "processes": processes_json,
                "stock_id": selected_stock_id,
                "stock_used": stock_use_qty,
            },
        )
        if selected_stock_id and stock_use_qty > 0:
            adjust_stock_after_job(selected_stock_id, stock_use_qty)

        st.session_state["job_processes"] = []
        st.cache_data.clear()
        st.success("Job with processes saved!")

# ---------- ADD STOCK ----------
elif page == "AddStock":
    st.title("📦 Add / Manage Stock")

    st.subheader("Add New Stock Item")
    s_name = st.text_input("Stock Name")
    s_category = st.text_input("Category")
    s_qty = st.number_input("Quantity / Weight", min_value=0.0, step=0.5)

    if st.button("Save Stock"):
        fs_add(
            "stocks",
            {
                "name": s_name,
                "category": s_category,
                "quantity": s_qty,
                "user_email": user_email,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        st.success("Stock saved!")
        st.cache_data.clear()

    st.subheader("Current Stock")
    stocks = get_user_stocks(user_email)
    if not stocks:
        st.info("No stock items yet.")
    else:
        df_s = pd.DataFrame(
            [
                {
                    "Name": s["name"],
                    "Category": s.get("category", ""),
                    "Quantity": s["quantity_float"],
                    "id": s["id"],
                }
                for s in stocks
            ]
        )
        st.dataframe(df_s.drop(columns=["id"]), use_container_width=True)

# ---------- VIEW JOBS ----------
elif page == "ViewJobs":
    st.title("📋 Manage Jobs")

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]
    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)

        # remove sensitive / noisy columns from table
        cols_to_remove = ["user_email", "processes", "created_at"]
        df_show = df.drop(columns=[c for c in cols_to_remove if c in df.columns])

        st.subheader("All Jobs")
        st.dataframe(df_show, use_container_width=True)

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

# ---------- AI CHAT (TEXT ONLY, SMART + MEMORY + AUTO PLAN) ----------
elif page == "AI":
    st.title("🤖 AI Chat (smart, with memory + auto plan)")

    st.subheader("💬 Type to AI")
    q = st.text_area(
        "Ask anything (general or factory related):",
        "Plan my work for today and also motivate me.",
        key="text_question",
    )

    if st.button("Ask AI"):
        user_text = q.strip()
        if user_text:
            with st.spinner("AI thinking..."):
                answer = ask_ai(user_email, user_text)
            st.session_state["last_ai_answer"] = answer
            st.write("### 🧠 AI Answer")
            st.write(answer)

            if is_planning_query(user_text):
                st.write("### 📅 AI Plan (auto generated from your data)")
                settings = get_schedule_settings()
                df_plan = build_ai_plan(
                    user_email,
                    settings["work_start"],
                    settings["work_end"],
                    settings["breaks"],
                )
                if df_plan.empty:
                    st.warning(
                        "No processes found. Add processes to jobs first in 'Add Job'."
                    )
                else:
                    st.dataframe(df_plan, use_container_width=True)

    if st.session_state["ai_history"]:
        st.markdown("---")
        st.subheader("🧾 Conversation Context (last turns)")
        for turn in st.session_state["ai_history"][-5:]:
            st.markdown(f"**You:** {turn['user']}")
            st.markdown(f"**AI:** {turn['assistant']}")

# ---------- AI PRODUCTION PLAN (UNLIMITED BREAKS + EDIT ORDER) ----------
elif page == "AIPlan":
    st.title("📅 AI Production Plan")

    st.write(
        "This uses all jobs, their processes, durations, and due dates to build a schedule "
        "based on your working hours and breaks."
    )

    settings = get_schedule_settings()

    # --- Working hours using simple time picker ---
    st.subheader("Working Hours")
    work_start = st.time_input(
        "Work Start Time", value=settings["work_start"], key="work_start_time"
    )
    work_end = st.time_input(
        "Work End Time", value=settings["work_end"], key="work_end_time"
    )

    # --- Unlimited breaks UI ---
    st.subheader("Breaks in the day (optional)")

    breaks_list = list(settings.get("breaks", []))
    updated_breaks = []
    delete_index = None

    if breaks_list:
        st.caption("Edit or remove existing breaks:")
        for i, (b_start, b_end) in enumerate(breaks_list):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                nb_start = st.time_input(
                    f"Break {i+1} Start", value=b_start, key=f"break_start_{i}"
                )
            with col2:
                nb_end = st.time_input(
                    f"Break {i+1} End", value=b_end, key=f"break_end_{i}"
                )
            with col3:
                if st.button("❌ Remove", key=f"remove_break_{i}"):
                    delete_index = i
            updated_breaks.append((nb_start, nb_end))

        if delete_index is not None:
            updated_breaks.pop(delete_index)

        updated_breaks = [b for b in updated_breaks if b[1] > b[0]]
    else:
        updated_breaks = []

    st.markdown("---")
    st.caption("Add a new break:")
    coln1, coln2, coln3 = st.columns([2, 2, 1])
    with coln1:
        new_b_start = st.time_input(
            "New Break Start", value=time(13, 0), key="new_break_start"
        )
    with coln2:
        new_b_end = st.time_input(
            "New Break End", value=time(14, 0), key="new_break_end"
        )
    with coln3:
        if st.button("➕ Add Break"):
            if new_b_end > new_b_start:
                updated_breaks.append((new_b_start, new_b_end))
            else:
                st.warning("Break end time must be after start time.")

    breaks = updated_breaks

    # save back so AI Chat also uses same settings
    st.session_state["schedule_settings"] = {
        "work_start": work_start,
        "work_end": work_end,
        "breaks": breaks,
    }

    # --- Generate plan + drag-like editing using Order column ---
    if st.button("Generate Plan"):
        df_plan = build_ai_plan(user_email, work_start, work_end, breaks)
        if df_plan.empty:
            st.warning("No processes found. Add processes to jobs first in 'Add Job'.")
        else:
            st.success("Plan generated! You can edit order below.")

            # Add an Order column if not there
            if "Order" not in df_plan.columns:
                df_plan.insert(0, "Order", list(range(1, len(df_plan) + 1)))

            edited_df = st.data_editor(
                df_plan,
                use_container_width=True,
                num_rows="fixed",
                key="plan_editor",
                column_config={
                    "Order": st.column_config.NumberColumn(
                        "Order", min_value=1, step=1, help="Change numbers to reorder tasks"
                    )
                },
            )

            # Sort by Order to simulate drag/drop ordering
            edited_df = edited_df.sort_values("Order").reset_index(drop=True)
            st.session_state["last_plan_df"] = edited_df.to_dict("records")

            st.markdown("### 📋 Final Ordered Plan")
            st.dataframe(edited_df, use_container_width=True)
    else:
        existing = st.session_state.get("last_plan_df", [])
        if existing:
            st.info("Showing last generated plan (you can still change the order).")
            df_existing = pd.DataFrame(existing)
            if "Order" not in df_existing.columns:
                df_existing.insert(0, "Order", list(range(1, len(df_existing) + 1)))

            edited_df = st.data_editor(
                df_existing,
                use_container_width=True,
                num_rows="fixed",
                key="plan_editor_existing",
                column_config={
                    "Order": st.column_config.NumberColumn(
                        "Order", min_value=1, step=1, help="Change numbers to reorder tasks"
                    )
                },
            )

            edited_df = edited_df.sort_values("Order").reset_index(drop=True)
            st.session_state["last_plan_df"] = edited_df.to_dict("records")

            st.markdown("### 📋 Final Ordered Plan")
            st.dataframe(edited_df, use_container_width=True)
        else:
            st.info("Set your working hours, add breaks and click 'Generate Plan'.")
