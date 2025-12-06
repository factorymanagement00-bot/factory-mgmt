import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime, date, time, timedelta

# ============ APP SETTINGS ============
st.set_page_config(page_title="Factory Manager Pro", layout="wide")
PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
if not OPENROUTER_KEY:
    try:
        OPENROUTER_KEY = st.secrets["openrouter_key"]
    except Exception:
        st.error("OPENROUTER_KEY not found. Set it as env var or in Streamlit secrets.")
        st.stop()

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ============ CSS ============
st.markdown(
    """
<style>
html,body,[class*="css"]{font-family:'Inter',sans-serif!important;}
.no-sidebar [data-testid="stSidebar"]{display:none!important;}
.login-wrapper{max-width:430px;margin:160px auto!important;}
.login-card{padding:40px;background:rgba(17,25,40,0.65);backdrop-filter:blur(18px);
border-radius:18px;border:1px solid rgba(148,163,184,0.4);box-shadow:0 8px 40px rgba(0,0,0,0.55);}
.login-title{text-align:center;font-size:28px;color:white;font-weight:700;margin-bottom:20px;}
[data-testid="stSidebar"]{background:#020617!important;padding:20px 16px!important;
border-right:1px solid rgba(30,64,175,0.7);}
.sidebar-header{display:flex;align-items:center;gap:10px;margin-bottom:24px;}
.sidebar-title-text{font-size:22px;font-weight:700;color:#e5e7eb;line-height:1.1;}
.collapse-btn button{background:#020617!important;border-radius:999px!important;
border:1px solid #4b5563!important;color:#e5e7eb!important;padding:6px 9px!important;font-size:16px!important;}
.navbox button{width:100%!important;background:#111827!important;border-radius:999px!important;
border:1px solid #4b5563!important;color:#e5e7eb!important;padding:10px 16px!important;
text-align:left!important;font-size:15px!important;margin-bottom:10px;transition:all .18s;}
.navbox button:hover{background:#1e293b!important;transform:translateX(2px);}
.nav-selected button{background:#3b82f6!important;border-color:#60a5fa!important;
color:white!important;font-weight:600!important;}
.logout-btn button{width:100%!important;margin-top:30px;background:#dc2626!important;
color:white!important;border-radius:999px!important;padding:10px 16px!important;border:none!important;}
.logout-btn button:hover{background:#f97373!important;}
.metric-card{background:#020617;padding:20px;border-radius:16px;border:1px solid #1f2937;
box-shadow:0 4px 20px rgba(0,0,0,0.4);text-align:center;}
.metric-card h2{color:white;font-size:32px;margin:0;}
.metric-card p{color:#cbd5e1;margin:4px 0 0 0;}
.block-container{padding-top:24px!important;}
@media (max-width:768px){
 .block-container{padding-left:.5rem!important;padding-right:.5rem!important;}
 .metric-card{padding:12px;}
 .login-card{margin:80px auto!important;padding:24px;}
}
</style>
""",
    unsafe_allow_html=True,
)

if "sidebar_collapsed" not in st.session_state:
    st.session_state["sidebar_collapsed"] = False
if st.session_state["sidebar_collapsed"]:
    st.markdown(
        """
    <style>
    .sidebar-title-text{display:none!important;}
    .navbox button{text-align:center!important;padding-left:0!important;padding-right:0!important;}
    </style>
    """,
        unsafe_allow_html=True,
    )

# ============ SESSION INIT ============
ss = st.session_state
if "user" not in ss:
    ss["user"] = None
if "page" not in ss:
    ss["page"] = "Dashboard"
if "job_processes" not in ss:
    ss["job_processes"] = []
if "job_stocks" not in ss:
    ss["job_stocks"] = []
if "new_stock_sizes" not in ss:
    ss["new_stock_sizes"] = []
if "last_ai_answer" not in ss:
    ss["last_ai_answer"] = ""
if "last_plan_df" not in ss:
    ss["last_plan_df"] = []
if "schedule_settings" not in ss:
    ss["schedule_settings"] = {
        "work_start": time(9, 0),
        "work_end": time(17, 0),
        "breaks": [],
    }
if "ai_history" not in ss:
    ss["ai_history"] = []

# ============ UTILS ============
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


# ============ AUTH ============
def signup(email, pw):
    return requests.post(
        SIGNUP_URL,
        json={"email": email, "password": pw, "returnSecureToken": True},
    ).json()


def login(email, pw):
    return requests.post(
        SIGNIN_URL,
        json={"email": email, "password": pw, "returnSecureToken": True},
    ).json()


# ============ FIRESTORE ============
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
        return out
    return out


def fs_update(col, id, data):
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.patch(
        f"{BASE_URL}/{col}/{id}?key={API_KEY}",
        json={"fields": fields},
    )
    st.cache_data.clear()


def fs_delete(col, id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    st.cache_data.clear()


# ============ STOCK HELPERS (MULTI SIZE) ============
def parse_sizes_field(s):
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return []


def get_user_stocks(email):
    """Return stocks for user, each with sizes_list + quantity_total.
    Supports both new 'sizes' JSON and old 'size' + 'quantity' format."""
    rows = [r for r in fs_get("stocks") if r.get("user_email") == email]
    for r in rows:
        sizes = parse_sizes_field(r.get("sizes", "[]"))

        # fallback for old single-size records
        if not sizes:
            old_size = r.get("size")
            old_qty = r.get("quantity")
            if old_size is not None or old_qty is not None:
                sizes = [{"size": old_size or "", "qty": safe_float(old_qty or 0)}]

        r["sizes_list"] = sizes
        r["quantity_total"] = sum(safe_float(z.get("qty", 0)) for z in sizes)
    return rows


def adjust_stock_after_job_multi(stocks_used):
    """Auto deduct stock per size when a job is saved."""
    if not stocks_used:
        return
    all_stocks = fs_get("stocks")
    for item in stocks_used:
        sid = item.get("stock_id")
        size_str = str(item.get("size", ""))
        used = safe_float(item.get("use_qty", 0))
        if not sid or used <= 0:
            continue
        for row in all_stocks:
            if row["id"] != sid:
                continue
            sizes = parse_sizes_field(row.get("sizes", "[]"))
            # fallback for old format
            if not sizes:
                old_size = row.get("size")
                old_qty = row.get("quantity")
                if old_size is not None or old_qty is not None:
                    sizes = [{"size": old_size or "", "qty": safe_float(old_qty or 0)}]
            new_sizes = []
            for z in sizes:
                if str(z.get("size", "")) == size_str:
                    new_qty = safe_float(z.get("qty", 0)) - used
                    if new_qty > 0:
                        new_sizes.append({"size": z.get("size", ""), "qty": new_qty})
                else:
                    new_sizes.append(z)
            if not new_sizes:
                fs_delete("stocks", sid)
            else:
                fs_update("stocks", sid, {"sizes": json.dumps(new_sizes)})
            break


# ============ AI CONTEXT ============
def job_summary(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        return "No jobs in the system yet."
    return "\n".join(
        f"- {j.get('job_name','')} | {j.get('status','')} | Qty {j.get('quantity','')} | Amount ₹{j.get('amount','')} | Due {j.get('due_date','')}"
        for j in jobs
    )


def stock_summary(email):
    stocks = get_user_stocks(email)
    if not stocks:
        return "No stock items currently available."
    lines = []
    for s in stocks:
        for z in s["sizes_list"]:
            lines.append(
                f"- {s.get('name','')} ({s.get('category','')}) size {z.get('size','')} qty {z.get('qty',0)}"
            )
    return "\n".join(lines)


# ============ AI CHAT ============
def ask_ai(email, query):
    jobs_text = job_summary(email)
    stocks_text = stock_summary(email)
    system_prompt = """
You are FactoryGPT, an expert assistant that helps manage a small factory.
You can answer general questions, and also help with jobs, processes, schedules, and stock.
When user asks for a PLAN or SCHEDULE, you design a practical daily plan.
Tone: friendly but clear.
"""
    history = ss.get("ai_history", [])
    msgs = [{"role": "system", "content": system_prompt}]
    for t in history:
        msgs.append({"role": "user", "content": t["user"]})
        msgs.append({"role": "assistant", "content": t["assistant"]})
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
    msgs.append({"role": "user", "content": user_prompt})
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": "deepseek/deepseek-chat", "messages": msgs},
    ).json()
    try:
        ans = resp["choices"][0]["message"]["content"]
    except Exception:
        ans = "AI error: " + str(resp)
    history.append({"user": query, "assistant": ans})
    ss["ai_history"] = history[-10:]
    return ans


# ============ PLANNING ============
def parse_processes(s):
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return []


def get_schedule_settings():
    return ss["schedule_settings"]


def is_planning_query(text: str) -> bool:
    if not text:
        return False
    text = text.lower()
    kws = [
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
    return any(k in text for k in kws)


def build_ai_plan(email, work_start, work_end, breaks):
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
                {"job": job_name, "process": pname, "hours": hrs, "due_date": due_dt}
            )
    if not tasks:
        return pd.DataFrame()
    tasks.sort(key=lambda x: (x["due_date"] or date(2100, 1, 1), x["job"]))

    def next_work_start(cur):
        while True:
            day = cur.date()
            day_start = datetime.combine(day, work_start)
            day_end = datetime.combine(day, work_end)
            if cur < day_start:
                cur = day_start
            if cur >= day_end:
                cur = datetime.combine(day + timedelta(days=1), work_start)
                continue
            todays_breaks = [
                (datetime.combine(day, b1), datetime.combine(day, b2))
                for (b1, b2) in breaks
                if b1 and b2 and b2 > b1
            ]
            moved = False
            for b1, b2 in todays_breaks:
                if b1 <= cur < b2:
                    cur = b2
                    moved = True
                    break
            if moved:
                continue
            return cur

    rows = []
    today = date.today()
    cur = datetime.combine(today, work_start)
    idx_by_date = {}

    def day_label(d):
        if d not in idx_by_date:
            idx_by_date[d] = len(idx_by_date) + 1
        return f"Day {idx_by_date[d]}"

    for t in tasks:
        hrs_rem = float(t["hours"])
        while hrs_rem > 1e-9:
            cur = next_work_start(cur)
            d = cur.date()
            day_end = datetime.combine(d, work_end)
            todays_breaks = [
                (datetime.combine(d, b1), datetime.combine(d, b2))
                for (b1, b2) in breaks
                if b1 and b2 and b2 > b1
            ]
            boundary = day_end
            for b1, b2 in todays_breaks:
                if cur < b1 < boundary:
                    boundary = b1
            max_hours = (boundary - cur).total_seconds() / 3600.0
            if max_hours <= 1e-9:
                cur = boundary
                continue
            slot = min(hrs_rem, max_hours)
            end_dt = cur + timedelta(hours=slot)
            rows.append(
                {
                    "Day": day_label(d),
                    "Planned Start": cur.strftime("%Y-%m-%d %I:%M %p"),
                    "Planned End": end_dt.strftime("%Y-%m-%d %I:%M %p"),
                    "Job": t["job"],
                    "Process": t["process"],
                    "Hours": round(slot, 2),
                    "Due Date": t["due_date"].isoformat() if t["due_date"] else "",
                }
            )
            hrs_rem -= slot
            cur = end_dt
    df = pd.DataFrame(rows)
    ss["last_plan_df"] = df.to_dict("records")
    return df


def ui_time_picker_12(label: str, default: time, key_prefix: str) -> time:
    c1, c2, c3 = st.columns([2, 2, 1])
    h24 = default.hour
    h12 = h24 % 12 or 12
    minute = default.minute
    ampm = "AM" if h24 < 12 else "PM"
    minute_opts = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    try:
        m_idx = minute_opts.index(minute)
    except ValueError:
        m_idx = 0
    with c1:
        h = st.selectbox(
            f"{label} (Hour)",
            list(range(1, 13)),
            index=h12 - 1,
            key=f"{key_prefix}_h",
        )
    with c2:
        m = st.selectbox(
            f"{label} (Minute)",
            minute_opts,
            index=m_idx,
            key=f"{key_prefix}_m",
        )
    with c3:
        ap = st.selectbox(
            f"{label} (AM/PM)",
            ["AM", "PM"],
            index=0 if ampm == "AM" else 1,
            key=f"{key_prefix}_ap",
        )
    h24 = h % 12 + (12 if ap == "PM" else 0)
    return time(h24, m)


# ============ LOGIN ============
if ss["user"] is None:
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
                ss["user"] = email
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

# ============ SIDEBAR ============
with st.sidebar:
    c_tog, c_title = st.columns([1, 4])
    with c_tog:
        st.markdown('<div class="collapse-btn">', unsafe_allow_html=True)
        lab = "☰" if ss["sidebar_collapsed"] else "⮜"
        if st.button(lab, key="toggle_sidebar"):
            ss["sidebar_collapsed"] = not ss["sidebar_collapsed"]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c_title:
        st.markdown(
            '<div class="sidebar-header"><div class="sidebar-title-text">📦 Factory</div></div>',
            unsafe_allow_html=True,
        )
    st.write("")

    def nav_btn(label, icon, page_name):
        cls = "nav-selected" if ss["page"] == page_name else "navbox"
        text = icon if ss["sidebar_collapsed"] else f"{icon}  {label}"
        with st.container():
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(text, key=f"nav_{page_name}"):
                ss["page"] = page_name
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
        ss["user"] = None
        ss["page"] = "Dashboard"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ============ MAIN PAGES ============
page = ss["page"]
user_email = ss["user"]

# ----- DASHBOARD -----
if page == "Dashboard":
    st.title("📊 Dashboard")
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]
    if not jobs:
        st.info("No jobs yet. Add one from 'Add Job'.")
    else:
        df = pd.DataFrame(jobs)
        c1, c2, c3 = st.columns(3)
        c1.markdown(
            f'<div class="metric-card"><h2>{len(df)}</h2><p>Total Jobs</p></div>',
            unsafe_allow_html=True,
        )
        c2.markdown(
            f'<div class="metric-card"><h2>{(df["status"]=="Pending").sum()}</h2><p>Pending</p></div>',
            unsafe_allow_html=True,
        )
        c3.markdown(
            f'<div class="metric-card"><h2>{(df["status"]=="Completed").sum()}</h2><p>Completed</p></div>',
            unsafe_allow_html=True,
        )
        st.subheader("All Jobs")
        cols_rm = ["user_email", "notes", "processes", "stocks_used"]
        df_show = df.drop(columns=[c for c in cols_rm if c in df.columns])
        st.dataframe(df_show, use_container_width=True)

# ----- ADD JOB -----
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

    # ---------- PROCESSES ----------
    st.markdown("### 🧩 Job Processes")
    cp1, cp2, cp3 = st.columns([3, 1, 1])
    with cp1:
        proc_name = st.text_input("Process Name")
    with cp2:
        proc_hours = st.number_input("Hours", min_value=0.0, step=0.25)
    with cp3:
        if st.button("Add Process"):
            if proc_name and proc_hours > 0:
                ss["job_processes"].append(
                    {"name": proc_name, "hours": proc_hours}
                )
            else:
                st.warning("Give a process name and hours > 0.")
    if ss["job_processes"]:
        st.table(pd.DataFrame(ss["job_processes"]))
    else:
        st.caption("No processes added yet. Add steps above.")

    # ---------- STOCKS (MULTI + SIZE) ----------
    st.markdown("### 🧰 Stock Used (optional, multi-stock)")
    stocks = get_user_stocks(user_email)

    # build labels with sizes
    stock_labels = ["None"]
    stock_map = {}
    for i, s in enumerate(stocks):
        sizes = s.get("sizes_list", [])
        size_parts = [f"{z.get('size','')} ({z.get('qty',0)})" for z in sizes]
        size_text = " | ".join(size_parts) if size_parts else "No size"
        label = f"{s['name']} ({s.get('category','')}) — {size_text}"
        stock_labels.append(label)
        stock_map[label] = i

    sel_label = st.selectbox("Select Stock", stock_labels)

    if "job_stocks" not in ss:
        ss["job_stocks"] = []

    if sel_label != "None" and stock_map:
        s = stocks[stock_map[sel_label]]
        sizes_list = s.get("sizes_list", [])
        if not sizes_list:
            st.warning("This stock has no sizes configured. Add them in Add Stock page.")
        else:
            size_opts = [str(z.get("size", "")) for z in sizes_list]
            sel_size = st.selectbox("Select Size", size_opts)
            chosen = next(
                (z for z in sizes_list if str(z.get("size", "")) == sel_size),
                None,
            )
            if chosen is not None:
                max_qty = safe_float(chosen.get("qty", 0))
                st.info(f"Available: {max_qty}")
                use_qty = st.number_input(
                    "Quantity to use from this size",
                    min_value=0.0,
                    max_value=max_qty,
                    step=0.5,
                )
                if st.button("Add Stock to Job"):
                    if use_qty > 0:
                        ss["job_stocks"].append(
                            {
                                "stock_id": s["id"],
                                "name": s["name"],
                                "category": s.get("category", ""),
                                "size": sel_size,
                                "available_qty": max_qty,
                                "use_qty": use_qty,
                            }
                        )
                    else:
                        st.warning("Use quantity must be > 0.")

    if ss["job_stocks"]:
        st.subheader("Stocks added to this job")
        st.table(
            pd.DataFrame(ss["job_stocks"])[
                ["name", "category", "size", "use_qty", "available_qty"]
            ]
        )
    else:
        st.caption(
            "No stocks attached yet. Select stock & size, enter quantity, then click 'Add Stock to Job'."
        )

    # ---------- SAVE JOB ----------
    if st.button("Save Job"):
        processes_json = json.dumps(ss["job_processes"])
        stocks_json = json.dumps(ss["job_stocks"])
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
                "stocks_used": stocks_json,
            },
        )
        # auto stock deduction
        adjust_stock_after_job_multi(ss["job_stocks"])
        ss["job_processes"] = []
        ss["job_stocks"] = []
        st.cache_data.clear()
        st.success("Job with processes and stocks saved, stock updated!")

# ----- ADD STOCK -----
elif page == "AddStock":
    st.title("📦 Add / Manage Stock")
    st.subheader("Add New Stock Item")

    s_name = st.text_input("Stock Name")
    s_category = st.text_input("Category")

    st.markdown("### ➕ Add Size to Stock")
    colz1, colz2, colz3 = st.columns([2, 2, 1])
    with colz1:
        new_size = st.text_input("Size", key="size_input")
    with colz2:
        new_qty = st.number_input(
            "Qty", key="qty_input", min_value=0.0, step=0.5
        )
    with colz3:
        st.write("")
        if st.button("Add Size"):
            if new_size and new_qty > 0:
                ss["new_stock_sizes"].append(
                    {"size": new_size, "qty": new_qty}
                )
            else:
                st.warning("Enter valid size and quantity.")

    if ss["new_stock_sizes"]:
        st.markdown("### 📄 Sizes Added")
        st.table(pd.DataFrame(ss["new_stock_sizes"]))
    else:
        st.caption("No sizes added yet. Add at least one size before saving.")

    if st.button("Save Stock"):
        if not s_name:
            st.error("Stock name required.")
        elif not ss["new_stock_sizes"]:
            st.error("Add at least one size.")
        else:
            fs_add(
                "stocks",
                {
                    "name": s_name,
                    "category": s_category,
                    "sizes": json.dumps(ss["new_stock_sizes"]),
                    "user_email": user_email,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            ss["new_stock_sizes"] = []
            st.success("Stock saved!")
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")
    st.subheader("Current Stock (per size)")

    stocks = get_user_stocks(user_email)
    if not stocks:
        st.info("No stock items yet.")
    else:
        rows = []
        for s in stocks:
            for z in s["sizes_list"]:
                rows.append(
                    {
                        "Name": s["name"],
                        "Category": s.get("category", ""),
                        "Size": z.get("size", ""),
                        "Quantity": z.get("qty", 0),
                        "StockID": s["id"],
                    }
                )
        if rows:
            df_stock = pd.DataFrame(rows)
            st.dataframe(
                df_stock[["Name", "Category", "Size", "Quantity"]],
                use_container_width=True,
            )
        else:
            st.info("Stocks exist but no sizes found yet.")

        st.markdown("### 🗑️ Delete Entire Stock")
        delete_options = [
            f"{s['name']} ({s.get('category','')})" for s in stocks
        ]
        selected_delete = st.selectbox(
            "Select stock to delete", ["None"] + delete_options
        )
        if selected_delete != "None":
            idx = delete_options.index(selected_delete)
            delete_id = stocks[idx]["id"]
            if st.button("Delete Selected Stock"):
                fs_delete("stocks", delete_id)
                st.success("Stock deleted successfully!")
                st.cache_data.clear()
                st.rerun()

# ----- VIEW JOBS -----
elif page == "ViewJobs":
    st.title("📋 Manage Jobs")
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]
    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        cols_rm = ["user_email", "processes", "created_at", "stocks_used"]
        df_show = df.drop(columns=[c for c in cols_rm if c in df.columns])
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

# ----- AI CHAT -----
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
                ans = ask_ai(user_email, user_text)
            ss["last_ai_answer"] = ans
            st.write("### 🧠 AI Answer")
            st.write(ans)
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
    if ss["ai_history"]:
        st.markdown("---")
        st.subheader("🧾 Conversation Context (last turns)")
        for t in ss["ai_history"][-5:]:
            st.markdown(f"**You:** {t['user']}")
            st.markdown(f"**AI:** {t['assistant']}")

# ----- AI PLAN -----
elif page == "AIPlan":
    st.title("📅 AI Production Plan")
    st.write(
        "This uses all jobs, their processes, durations, and due dates to build a schedule based on your working hours and breaks."
    )
    settings = get_schedule_settings()
    st.subheader("Working Hours (12-hour format)")
    work_start = ui_time_picker_12(
        "Work Start Time", settings["work_start"], "work_start"
    )
    work_end = ui_time_picker_12(
        "Work End Time", settings["work_end"], "work_end"
    )

    st.subheader("Breaks in the day (optional) — 12-hour format")
    breaks_list = list(settings.get("breaks", []))
    updated_breaks = []
    delete_idx = None
    if breaks_list:
        st.caption("Edit or remove existing breaks:")
        for i, (b1, b2) in enumerate(breaks_list):
            st.markdown(f"**Break {i+1}**")
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                nb1 = ui_time_picker_12("Start", b1, f"break_{i}_start")
            with c2:
                nb2 = ui_time_picker_12("End", b2, f"break_{i}_end")
            with c3:
                st.write("")
                if st.button("❌ Remove", key=f"rm_break_{i}"):
                    delete_idx = i
            updated_breaks.append((nb1, nb2))
        if delete_idx is not None:
            updated_breaks.pop(delete_idx)
        updated_breaks = [b for b in updated_breaks if b[1] > b[0]]
    else:
        updated_breaks = []

    st.markdown("---")
    st.caption("Add a new break:")
    cnb1, cnb2, cnb3 = st.columns([2, 2, 1])
    with cnb1:
        new_b1 = ui_time_picker_12("New Break Start", time(13, 0), "new_break_start")
    with cnb2:
        new_b2 = ui_time_picker_12("New Break End", time(14, 0), "new_break_end")
    with cnb3:
        st.write("")
        if st.button("➕ Add Break"):
            if new_b2 > new_b1:
                updated_breaks.append((new_b1, new_b2))
            else:
                st.warning("Break end time must be after start time.")

    breaks = updated_breaks
    ss["schedule_settings"] = {
        "work_start": work_start,
        "work_end": work_end,
        "breaks": breaks,
    }

    if st.button("Generate Plan"):
        df_plan = build_ai_plan(user_email, work_start, work_end, breaks)
        if df_plan.empty:
            st.warning(
                "No processes found. Add processes to jobs first in 'Add Job'."
            )
        else:
            st.success("Plan generated! You can edit order below.")
            if "Order" not in df_plan.columns:
                df_plan.insert(0, "Order", list(range(1, len(df_plan) + 1)))
            edited = st.data_editor(
                df_plan,
                use_container_width=True,
                num_rows="fixed",
                key="plan_editor",
                column_config={
                    "Order": st.column_config.NumberColumn(
                        "Order",
                        min_value=1,
                        step=1,
                        help="Change numbers to reorder tasks",
                    )
                },
            )
            edited = edited.sort_values("Order").reset_index(drop=True)
            ss["last_plan_df"] = edited.to_dict("records")
            st.markdown("### 📋 Final Ordered Plan")
            st.dataframe(edited, use_container_width=True)
    else:
        existing = ss.get("last_plan_df", [])
        if existing:
            st.info("Showing last generated plan (you can still change the order).")
            df_exist = pd.DataFrame(existing)
            if "Order" not in df_exist.columns:
                df_exist.insert(0, "Order", list(range(1, len(df_exist) + 1)))
            edited = st.data_editor(
                df_exist,
                use_container_width=True,
                num_rows="fixed",
                key="plan_editor_existing",
                column_config={
                    "Order": st.column_config.NumberColumn(
                        "Order",
                        min_value=1,
                        step=1,
                        help="Change numbers to reorder tasks",
                    )
                },
            )
            edited = edited.sort_values("Order").reset_index(drop=True)
            ss["last_plan_df"] = edited.to_dict("records")
            st.markdown("### 📋 Final Ordered Plan")
            st.dataframe(edited, use_container_width=True)
        else:
            st.info("Set your working hours, add breaks and click 'Generate Plan'.")
