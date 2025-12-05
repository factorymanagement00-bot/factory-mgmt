import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, date, time, timedelta
from io import BytesIO

from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
from openai import OpenAI

# ============================================
# APP SETTINGS
# ============================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"                # <--- your Firebase project id
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"             # <--- your Firebase Web API key

OPENROUTER_KEY = st.secrets["openrouter_key"]                 # set in Streamlit secrets
OPENAI_API_KEY = st.secrets.get("openai_api_key", None)       # for voice STT

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
# AI — GENERAL + FACTORY (CHAT AI)
# ============================================
def job_summary(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        return ""
    return "\n".join(
        f"- {j['job_name']} | {j['status']} | Qty {j.get('quantity','')} | ₹{j['amount']}"
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
# VOICE HELPERS (STT + TTS)
# ============================================
def speech_to_text(audio_bytes: bytes):
    if openai_client is None:
        return None, "No OPENAI_API_KEY set in secrets."

    try:
        with open("voice_input.wav", "wb") as f:
            f.write(audio_bytes)
        with open("voice_input.wav", "rb") as audio_file:
            result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return result.text, None
    except Exception as e:
        return None, str(e)

def text_to_speech_bytes(text: str):
    mp3 = BytesIO()
    tts = gTTS(text=text, lang="en")
    tts.write_to_fp(mp3)
    mp3.seek(0)
    return mp3

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
                    "Planned Start": current_dt.strftime("%Y-%m-%d %H:%M"),
                    "Planned End": end_dt.strftime("%Y-%m-%d %H:%M"),
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
    nav_btn("AI Chat + Voice", "🤖", "AI")
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
    proc_name = st.text_input("Process Name", key="proc_name_input")
    proc_hours = st.number_input("Hours", min_value=0.0, step=0.25, key="proc_hours_input")

    with col_p3:
        if st.button("Add Process"):
            if proc_name and proc_hours > 0:
                st.session_state["job_processes"].append(
                    {"name": proc_name, "hours": proc_hours}
                )
                st.session_state["proc_name_input"] = ""
                st.session_state["proc_hours_input"] = 0.0
                st.rerun()

    if st.session_state["job_processes"]:
        st.table(pd.DataFrame(st.session_state["job_processes"]))
    else:
        st.caption("No processes added yet. Add steps above.")

    st.markdown("### 🧰 Stock Used (optional)")
    stocks = get_user_stocks(user_email)
    stock_options = ["None"] + [f"{s['name']} ({s.get('category','')}) — {s['quantity_float']}" for s in stocks]
    selected_stock_label = st.selectbox("Select Stock", stock_options)

    stock_use_qty = 0.0
    selected_stock_id = ""
    if selected_stock_label != "None":
        idx = stock_options.index(selected_stock_label) - 1
        selected_stock = stocks[idx]
        selected_stock_id = selected_stock["id"]
        max_qty = selected_stock["quantity_float"]
        stock_use_qty = st.number_input("Stock quantity to use", min_value=0.0, max_value=max_qty, step=0.5)

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

# ---------- AI CHAT + VOICE ----------
elif page == "AI":
    st.title("🤖 AI Chat + Voice (with Auto Plan)")

    # TEXT CHAT
    st.subheader("💬 Type to AI")
    q = st.text_area(
        "Ask anything (general or factory related):",
        "Plan my work for today and also motivate me.",
        key="text_question",
    )

    if st.button("Ask with Text"):
        user_text = q.strip()
        if user_text:
            with st.spinner("AI thinking..."):
                answer = ask_ai(user_email, user_text)
            st.session_state["last_ai_answer"] = answer
            st.write("### 🧠 AI Answer")
            st.write(answer)

            if is_planning_query(user_text):
                st.write("### 📅 AI Plan (auto generated)")
                settings = get_schedule_settings()
                df_plan = build_ai_plan(
                    user_email,
                    settings["work_start"],
                    settings["work_end"],
                    settings["breaks"],
                )
                if df_plan.empty:
                    st.warning("No processes found. Add processes to jobs first in 'Add Job'.")
                else:
                    st.dataframe(df_plan, use_container_width=True)

    st.markdown("---")

    # VOICE CHAT
    st.subheader("🎤 Talk to AI (Voice)")
    st.caption("Click to record, speak, then click again to stop. Then press 'Send Voice to AI'.")
    audio_bytes = audio_recorder(
        text="Click to record / stop",
        pause_threshold=2.0,
        sample_rate=44100,
        key="voice_recorder",
    )

    if audio_bytes is not None:
        st.audio(audio_bytes, format="audio/wav")

    if st.button("Send Voice to AI"):
        if audio_bytes is None:
            st.warning("Record something first.")
        elif openai_client is None:
            st.error("Set OPENAI_API_KEY in secrets to enable voice input.")
        else:
            with st.spinner("Transcribing your voice..."):
                text, err = speech_to_text(audio_bytes)
            if err:
                st.error("Speech-to-text error: " + err)
            else:
                st.write("### 📝 You said:")
                st.write(text)

                with st.spinner("AI thinking..."):
                    answer = ask_ai(user_email, text)
                st.session_state["last_ai_answer"] = answer
                st.write("### 🧠 AI Answer")
                st.write(answer)

                if is_planning_query(text):
                    st.write("### 📅 AI Plan (auto generated)")
                    settings = get_schedule_settings()
                    df_plan = build_ai_plan(
                        user_email,
                        settings["work_start"],
                        settings["work_end"],
                        settings["breaks"],
                    )
                    if df_plan.empty:
                        st.warning("No processes found. Add processes to jobs first in 'Add Job'.")
                    else:
                        st.dataframe(df_plan, use_container_width=True)

    if st.session_state["last_ai_answer"]:
        st.markdown("---")
        st.subheader("🔊 Listen to AI Answer")
        if st.button("Play AI Answer"):
            with st.spinner("Generating voice..."):
                audio_file = text_to_speech_bytes(st.session_state["last_ai_answer"])
            st.audio(audio_file, format="audio/mp3")

# ---------- AI PRODUCTION PLAN ----------
elif page == "AIPlan":
    st.title("📅 AI Production Plan")

    st.write(
        "This uses all jobs, their processes, durations, and due dates to build a schedule "
        "based on your working hours and breaks."
    )

    settings = get_schedule_settings()

    work_start = st.time_input("Work start time", value=settings["work_start"])
    work_end = st.time_input("Work end time", value=settings["work_end"])

    st.markdown("#### Breaks in the day (optional)")
    col_b1s, col_b1e = st.columns(2)
    with col_b1s:
        b1_start = st.time_input("Break 1 start", value=time(13, 0))
    with col_b1e:
        b1_end = st.time_input("Break 1 end", value=time(14, 0))

    col_b2s, col_b2e = st.columns(2)
    with col_b2s:
        b2_start = st.time_input("Break 2 start", value=time(17, 0))
    with col_b2e:
        b2_end = st.time_input("Break 2 end", value=time(17, 30))

    breaks = []
    if b1_end > b1_start:
        breaks.append((b1_start, b1_end))
    if b2_end > b2_start:
        breaks.append((b2_start, b2_end))

    # save so AI Chat uses same settings
    st.session_state["schedule_settings"] = {
        "work_start": work_start,
        "work_end": work_end,
        "breaks": breaks,
    }

    if st.button("Generate Plan"):
        df_plan = build_ai_plan(user_email, work_start, work_end, breaks)
        if df_plan.empty:
            st.warning("No processes found. Add processes to jobs first in 'Add Job'.")
        else:
            st.success("Plan generated!")
            st.dataframe(df_plan, use_container_width=True)
    else:
        records = st.session_state.get("last_plan_df", [])
        if records:
            st.dataframe(pd.DataFrame(records), use_container_width=True)
        else:
            st.info("Set your working hours and click 'Generate Plan'.")
