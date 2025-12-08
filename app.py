import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime, date, time, timedelta

# =========================================
# APP SETTINGS
# =========================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"

# OpenRouter API KEY (for AI chat / review)
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
if not OPENROUTER_KEY:
    try:
        OPENROUTER_KEY = st.secrets["openrouter_key"]
    except Exception:
        OPENROUTER_KEY = None

# Firebase
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# =========================================
# CSS
# =========================================
st.markdown(
    """
<style>
html,body,[class*="css"]{font-family:'Inter',sans-serif!important;}
[data-testid="stSidebar"]{background:#020617!important;border-right:1px solid #1e3a8a;}
.navbox button{width:100%!important;background:#111827!important;border-radius:14px;
border:1px solid #475569!important;color:#e5e7eb!important;padding:10px 16px!important;}
.nav-selected button{background:#3b82f6!important;color:white!important;}
.metric-card{background:#020617;border-radius:16px;padding:20px;border:1px solid #1e293b;}
.metric-card h2{color:white;}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================
# SESSION STATE
# =========================================
ss = st.session_state

defaults = {
    "user": None,
    "page": "Dashboard",
    "job_processes": [],
    "job_stocks": [],
    "new_stock_sizes": [],
    "last_ai_answer": "",
    "last_plan_df": None,      # DataFrame with plan (visible columns)
    "last_plan_review": "",    # AI's review text
    "plan_row_meta": [],       # mapping for each row to (job_id, proc_index) or None
    "schedule_settings": {
        "work_start": time(9, 0),
        "work_end": time(17, 0),
        "breaks": [],          # list of (time, time)
    },
    "ai_history": [],
}
for k, v in defaults.items():
    if k not in ss:
        ss[k] = v

# =========================================
# HELPERS
# =========================================
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


# =========================================
# AUTH
# =========================================
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


# =========================================
# FIRESTORE
# =========================================
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


# =========================================
# STOCK + STAFF HELPERS
# =========================================
def parse_sizes(s):
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return []


def get_user_stocks(email):
    """Return all stocks with multi-size support."""
    rows = [r for r in fs_get("stocks") if r.get("user_email") == email]
    for r in rows:
        sizes = parse_sizes(r.get("sizes", "[]"))
        if not sizes:
            sizes = [
                {
                    "size": r.get("size", ""),
                    "qty": safe_float(r.get("quantity", 0)),
                }
            ]
        r["sizes_list"] = sizes
        r["total_qty"] = sum(safe_float(z["qty"]) for z in sizes)
    return rows


def adjust_stock_after_job_multi(stocks_used):
    """Deduct selected stock quantities automatically."""
    all_items = fs_get("stocks")
    for used in stocks_used:
        sid = used["stock_id"]
        size = used["size"]
        qty = safe_float(used["use_qty"])
        if qty <= 0:
            continue

        for s in all_items:
            if s["id"] != sid:
                continue
            sizes = parse_sizes(s.get("sizes", "[]"))
            new_sizes = []
            for z in sizes:
                if str(z["size"]) == str(size):
                    newq = safe_float(z["qty"]) - qty
                    if newq > 0:
                        new_sizes.append({"size": size, "qty": newq})
                else:
                    new_sizes.append(z)
            if not new_sizes:
                fs_delete("stocks", sid)
            else:
                fs_update("stocks", sid, {"sizes": json.dumps(new_sizes)})
            break


def get_user_staff(email):
    """All staff for this user."""
    return [r for r in fs_get("staff") if r.get("user_email") == email]


# =========================================
# AI SECTION (chat / review)
# =========================================
def job_summary(email):
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        return "No jobs yet."
    return "\n".join(
        f"- {j['job_name']} | {j['status']} | Qty {j['quantity']} | ₹{j['amount']} | Due {j['due_date']}"
        for j in jobs
    )


def stock_summary(email):
    stocks = get_user_stocks(email)
    if not stocks:
        return "No stock available."
    out = []
    for s in stocks:
        for z in s["sizes_list"]:
            out.append(f"- {s['name']} size {z['size']} qty {z['qty']}")
    return "\n".join(out)


def ask_ai(email, query):
    if not OPENROUTER_KEY:
        return "OPENROUTER_KEY not set. Configure it in your environment or Streamlit secrets."

    system_prompt = "You are FactoryGPT — expert in factory workflows, stock, jobs, and planning."
    messages = [{"role": "system", "content": system_prompt}]
    for t in ss["ai_history"]:
        messages.append({"role": "user", "content": t["user"]})
        messages.append({"role": "assistant", "content": t["assistant"]})

    user_prompt = f"""
User Query:
{query}

Jobs:
{job_summary(email)}

Stock:
{stock_summary(email)}
"""
    messages.append({"role": "user", "content": user_prompt})

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "deepseek/deepseek-chat", "messages": messages},
            timeout=60,
        ).json()
    except Exception as e:
        return f"AI request error: {e}"

    try:
        ans = r["choices"][0]["message"]["content"]
    except Exception:
        ans = f"AI error. Raw response: {r}"
    ss["ai_history"].append({"user": query, "assistant": ans})
    ss["ai_history"] = ss["ai_history"][-10:]
    return ans


# =========================================
# SCHEDULER (TODAY ONLY, breaks, defer_until, per-process completion)
# =========================================
def generate_schedule(email, settings):
    """
    - Only generates schedule for TODAY.
    - Uses process order from first job.
    - Skips processes with completed=True.
    - Skips processes with defer_until > today.
    - Tasks that don't fit in today's working window are left for tomorrow.
    - Returns (df_display, row_meta) where row_meta[i] = {job_id, proc_index} or None (for breaks).
    """
    today = date.today()
    today_str = today.isoformat()

    jobs_all = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs_all:
        return pd.DataFrame(), []

    # sort jobs by due date so earlier jobs get earlier slots
    def parse_due(j):
        try:
            return datetime.fromisoformat(j.get("due_date"))
        except Exception:
            return datetime.max

    jobs_sorted = sorted(jobs_all, key=parse_due)
    job_due_map = {j["id"]: j.get("due_date", "") for j in jobs_sorted}

    # collect tasks: only incomplete + not deferred beyond today
    tasks = []
    for j in jobs_sorted:
        try:
            procs = json.loads(j.get("processes", "[]"))
        except Exception:
            procs = []
        for idx, p in enumerate(procs):
            hours = safe_float(p.get("hours", 0))
            if hours <= 0:
                continue

            completed = bool(p.get("completed", False))
            if completed:
                continue

            defer_until = p.get("defer_until", "")
            if defer_until:
                try:
                    ddt = datetime.fromisoformat(defer_until).date()
                    if ddt > today:
                        # scheduled for future, skip today
                        continue
                except Exception:
                    pass

            raw_staff = p.get("staff", [])
            if isinstance(raw_staff, str):
                staff_list = [raw_staff] if raw_staff.strip() else []
            elif isinstance(raw_staff, list):
                staff_list = [str(x).strip() for x in raw_staff if str(x).strip()]
            else:
                staff_list = []

            tasks.append(
                {
                    "job_id": j["id"],
                    "job_name": j["job_name"],
                    "process": p.get("name", "").strip(),
                    "hours": hours,
                    "staff": staff_list,
                    "proc_index": idx,
                }
            )

    if not tasks:
        return pd.DataFrame(), []

    # global process order from first job, then others
    process_order = []
    for j in jobs_sorted:
        try:
            procs = json.loads(j.get("processes", "[]"))
        except Exception:
            procs = []
        for p in procs:
            name = p.get("name", "").strip()
            if name and name not in process_order:
                process_order.append(name)

    for t in tasks:
        if t["process"] and t["process"] not in process_order:
            process_order.append(t["process"])

    # sort tasks by job order inside each process
    job_order_index = {j["id"]: idx for idx, j in enumerate(jobs_sorted)}
    tasks_sorted = sorted(
        tasks, key=lambda t: job_order_index.get(t["job_id"], 9999)
    )

    # group tasks by process
    process_to_tasks = {p: [] for p in process_order}
    for t in tasks_sorted:
        process_to_tasks.setdefault(t["process"], []).append(t)

    # Build working segments for today (excluding breaks)
    work_start_t = settings["work_start"]
    work_end_t = settings["work_end"]
    ws = datetime.combine(today, work_start_t)
    we = datetime.combine(today, work_end_t)

    # Breaks as datetime intervals today
    breaks = settings["breaks"]
    break_intervals = []
    for (b1, b2) in breaks:
        bs = datetime.combine(today, b1)
        be = datetime.combine(today, b2)
        if be > bs:
            break_intervals.append((bs, be))
    break_intervals.sort(key=lambda x: x[0])

    # Build available segments (no breaks)
    segments = []
    prev = ws
    for bs, be in break_intervals:
        if bs > prev:
            segments.append((prev, bs))
        prev = max(prev, be)
    if prev < we:
        segments.append((prev, we))

    # schedule tasks into today's segments only
    schedule_rows = []
    row_meta = []

    seg_idx = 0
    current_time = segments[0][0] if segments else ws

    def hours_between(a, b):
        return (b - a).total_seconds() / 3600.0

    outer_break = False
    for proc in process_order:
        for t in process_to_tasks.get(proc, []):
            if outer_break or not segments:
                break

            needed = t["hours"]
            placed = False

            while seg_idx < len(segments):
                seg_start, seg_end = segments[seg_idx]
                if current_time < seg_start:
                    current_time = seg_start

                available = hours_between(current_time, seg_end)
                if available >= needed:
                    # fits in this segment
                    start_dt = current_time
                    end_dt = start_dt + timedelta(hours=needed)

                    label = t["process"]
                    if t["staff"]:
                        label = f"{label} (Staff: {', '.join(t['staff'])})"

                    schedule_rows.append(
                        {
                            "Date": today_str,
                            "Job": t["job_name"],
                            "Process": label,
                            "Start": start_dt.strftime("%I:%M %p"),
                            "End": end_dt.strftime("%I:%M %p"),
                            "Due Date": job_due_map.get(t["job_id"], ""),
                        }
                    )
                    row_meta.append(
                        {"job_id": t["job_id"], "proc_index": t["proc_index"]}
                    )

                    current_time = end_dt
                    placed = True
                    break
                else:
                    # move to next segment
                    seg_idx += 1
                    if seg_idx < len(segments):
                        current_time = segments[seg_idx][0]

            if not placed:
                # no more space today
                outer_break = True
                break
        if outer_break:
            break

    # Add break rows into schedule (for display)
    for bs, be in break_intervals:
        schedule_rows.append(
            {
                "Date": today_str,
                "Job": "",
                "Process": "Break",
                "Start": bs.strftime("%I:%M %p"),
                "End": be.strftime("%I:%M %p"),
                "Due Date": "",
            }
        )
        row_meta.append(None)

    if not schedule_rows:
        return pd.DataFrame(), []

    # Sort schedule rows by time
    def parse_time_str(t):
        return datetime.strptime(t, "%I:%M %p")

    sorted_pairs = sorted(
        zip(schedule_rows, row_meta),
        key=lambda x: parse_time_str(x[0]["Start"]),
    )
    schedule_rows, row_meta = zip(*sorted_pairs)
    schedule_rows = list(schedule_rows)
    row_meta = list(row_meta)

    # Build DataFrame for display with Done / CantDoToday columns
    df = pd.DataFrame(schedule_rows)
    df["Done"] = False
    df["CantDoToday"] = False

    return df, row_meta


# =========================================
# LOGIN PAGE
# =========================================
if ss["user"] is None:
    st.title("🔐 Login")
    mode = st.radio("Mode", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")

    if mode == "Sign Up":
        cpw = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            r = login(email, pw)
            if "error" in r:
                st.error("Invalid login")
            else:
                ss["user"] = email
                st.rerun()
        else:
            if pw != cpw:
                st.error("Passwords mismatch")
            else:
                r = signup(email, pw)
                if "error" in r:
                    st.error("Error creating account")
                else:
                    st.success("Account created. Login now.")

    st.stop()

# =========================================
# SIDEBAR NAVIGATION
# =========================================
with st.sidebar:

    def nav(label, icon, page):
        cls = "nav-selected" if ss["page"] == page else "navbox"
        st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
        if st.button(f"{icon} {label}", key=f"nav_{page}"):
            ss["page"] = page
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### 📦 Factory Menu")
    nav("Dashboard", "🏠", "Dashboard")
    nav("Staff", "👷", "Staff")
    nav("Add Job", "➕", "AddJob")
    nav("Add Stock", "📦", "AddStock")
    nav("View Jobs", "📋", "ViewJobs")
    nav("AI Chat", "🤖", "AI")
    nav("AI Production Plan", "📅", "AIPlan")

    if st.button("🚪 Logout"):
        ss["user"] = None
        ss["page"] = "Dashboard"
        st.rerun()

# =========================================
# MAIN PAGES
# =========================================
page = ss["page"]
email = ss["user"]

# =========================================
# DASHBOARD
# =========================================
if page == "Dashboard":
    st.title("📊 Dashboard")

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]

    if not jobs:
        st.info("No jobs yet.")
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
        hide_cols = ["user_email", "processes", "stocks_used", "notes"]
        df_show = df.drop(columns=[c for c in hide_cols if c in df.columns])
        st.dataframe(df_show, use_container_width=True)

# =========================================
# STAFF PAGE
# =========================================
elif page == "Staff":
    st.title("👷 Staff")

    st.subheader("Add Staff Member")
    s_name = st.text_input("Staff Name")
    s_role = st.text_input("Role / Skill")
    s_status = st.selectbox("Status", ["Active", "Inactive"])

    if st.button("Save Staff"):
        if not s_name:
            st.error("Enter staff name")
        else:
            fs_add(
                "staff",
                {
                    "name": s_name,
                    "role": s_role,
                    "status": s_status,
                    "user_email": email,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            st.success("Staff saved")
            st.rerun()

    st.subheader("Current Staff")
    staff = get_user_staff(email)
    if staff:
        df = pd.DataFrame(staff)
        show_cols = ["name", "role", "status", "id"]
        st.dataframe(df[show_cols], use_container_width=True)

        del_map = {"None": None}
        for s in staff:
            label = f"{s['name']} ({s.get('role','')})"
            del_map[label] = s["id"]

        sel_del = st.selectbox("Delete Staff", list(del_map.keys()))
        if sel_del != "None" and st.button("Delete Selected Staff"):
            fs_delete("staff", del_map[sel_del])
            st.success("Staff deleted")
            st.rerun()
    else:
        st.info("No staff added yet.")

# =========================================
# ADD JOB PAGE
# =========================================
elif page == "AddJob":
    st.title("➕ Add Job")

    job_name = st.text_input("Job Name")
    client = st.text_input("Client Name")
    phone = st.text_input("Phone")
    amount = st.number_input("Amount", min_value=0)
    qty = st.number_input("Quantity", min_value=1)
    job_type = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
    due = st.date_input("Due Date", date.today())

    # PROCESSES
    st.subheader("🧩 Job Processes")

    staff_members = get_user_staff(email)
    staff_names = [s["name"] for s in staff_members]

    c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
    with c1:
        pname = st.text_input("Process Name")
    with c2:
        phours = st.number_input("Hours", min_value=0.0, step=0.25)
    with c3:
        selected_staff = st.multiselect("Staff", staff_names, key="proc_staff")
    with c4:
        if st.button("Add Process"):
            if pname and phours > 0:
                ss["job_processes"].append(
                    {
                        "name": pname,
                        "hours": phours,
                        "staff": selected_staff,   # list of names
                        "completed": False,
                        "defer_until": "",
                    }
                )
            else:
                st.warning("Enter valid process name & hours.")

    if ss["job_processes"]:
        st.table(pd.DataFrame(ss["job_processes"]))

    # STOCK SELECTION (MULTI + SIZE)
    st.subheader("🧰 Stock Used (multi-stock)")

    stocks = get_user_stocks(email)

    stock_labels = ["None"]
    stock_map = {}
    for i, s in enumerate(stocks):
        sdesc = " | ".join([f"{z['size']} ({z['qty']})" for z in s["sizes_list"]])
        label = f"{s['name']} — {sdesc}"
        stock_labels.append(label)
        stock_map[label] = i

    sel = st.selectbox("Select Stock", stock_labels)

    if sel != "None":
        s = stocks[stock_map[sel]]
        sizes = [z["size"] for z in s["sizes_list"]]
        sel_size = st.selectbox("Select Size", sizes)
        chosen = next(
            z for z in s["sizes_list"] if str(z["size"]) == str(sel_size)
        )
        max_qty = safe_float(chosen["qty"])
        use_qty = st.number_input(
            "Use Quantity", min_value=0.0, max_value=max_qty, step=0.5
        )

        if st.button("Add Stock to Job"):
            if use_qty > 0:
                ss["job_stocks"].append(
                    {
                        "stock_id": s["id"],
                        "name": s["name"],
                        "size": sel_size,
                        "use_qty": use_qty,
                        "available": max_qty,
                    }
                )
            else:
                st.warning("Quantity must be > 0.")

    if ss["job_stocks"]:
        st.subheader("Selected Stock")
        st.table(pd.DataFrame(ss["job_stocks"]))

    # SAVE JOB
    if st.button("Save Job"):
        fs_add(
            "jobs",
            {
                "job_name": job_name,
                "client_name": client,
                "phone": phone,
                "amount": amount,
                "quantity": qty,
                "job_type": job_type,
                "status": status,
                "notes": "",
                "user_email": email,
                "created_at": datetime.utcnow().isoformat(),
                "due_date": due.isoformat(),
                "processes": json.dumps(ss["job_processes"]),
                "stocks_used": json.dumps(ss["job_stocks"]),
            },
        )

        adjust_stock_after_job_multi(ss["job_stocks"])

        ss["job_processes"] = []
        ss["job_stocks"] = []

        st.success("Job Saved & Stock Updated!")
        st.rerun()

# =========================================
# ADD STOCK PAGE
# =========================================
elif page == "AddStock":
    st.title("📦 Add Stock")

    name = st.text_input("Stock Name")
    category = st.text_input("Category")

    st.subheader("Add Sizes to Stock")
    size = st.text_input("Size")
    qty = st.number_input("Quantity", min_value=0.0, step=0.5)

    if st.button("Add Size"):
        if size and qty > 0:
            ss["new_stock_sizes"].append({"size": size, "qty": qty})
        else:
            st.warning("Invalid size or qty")

    if ss["new_stock_sizes"]:
        st.table(pd.DataFrame(ss["new_stock_sizes"]))

    if st.button("Save Stock"):
        if not name:
            st.error("Enter stock name")
        elif not ss["new_stock_sizes"]:
            st.error("Add at least one size")
        else:
            fs_add(
                "stocks",
                {
                    "name": name,
                    "category": category,
                    "sizes": json.dumps(ss["new_stock_sizes"]),
                    "user_email": email,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            ss["new_stock_sizes"] = []
            st.success("Stock Saved!")
            st.rerun()

    st.subheader("Current Stock")
    items = get_user_stocks(email)
    rows = []

    for s in items:
        for z in s["sizes_list"]:
            rows.append(
                {
                    "Name": s["name"],
                    "Category": s["category"],
                    "Size": z["size"],
                    "Quantity": z["qty"],
                    "StockID": s["id"],
                }
            )

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(
            df[["Name", "Category", "Size", "Quantity"]],
            use_container_width=True,
        )

        label_to_id = {"None": None}
        for s in items:
            size_desc = " | ".join(
                [f"{z['size']} ({z['qty']})" for z in s["sizes_list"]]
            )
            label = f"{s['name']} — {size_desc}"
            label_to_id[label] = s["id"]

        selected_label = st.selectbox("Delete Stock", list(label_to_id.keys()))
        if selected_label != "None" and st.button("Delete"):
            fs_delete("stocks", label_to_id[selected_label])
            st.success("Deleted")
            st.rerun()
    else:
        st.info("No stock yet")

# =========================================
# VIEW JOBS (no completion here)
# =========================================
elif page == "ViewJobs":
    st.title("📋 Jobs")

    jobs = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs:
        st.info("No jobs yet")
    else:
        df = pd.DataFrame(jobs)

        hide = ["user_email", "stocks_used", "created_at"]
        df_show = df.drop(columns=[c for c in hide if c in df.columns])
        st.dataframe(df_show, use_container_width=True)

        sel = st.selectbox("Select Job", df["id"])
        job = df[df["id"] == sel].iloc[0]

        new_amount = st.number_input(
            "Amount", value=safe_int(job["amount"])
        )
        new_status = st.selectbox(
            "Status",
            ["Pending", "In Progress", "Completed"],
            index=["Pending", "In Progress", "Completed"].index(
                job["status"]
            ),
        )
        new_notes = st.text_area("Notes", job.get("notes", ""))

        if st.button("Update"):
            fs_update(
                "jobs",
                sel,
                {"amount": new_amount, "status": new_status, "notes": new_notes},
            )
            st.success("Updated")

        if st.button("Delete Job"):
            fs_delete("jobs", sel)
            st.success("Job removed")
            st.rerun()

        st.subheader("Processes for this Job")

        try:
            process_list = json.loads(job.get("processes", "[]"))
        except Exception:
            process_list = []

        if process_list:
            df_proc = pd.DataFrame(process_list)
            st.table(df_proc)
        else:
            st.info("No processes added for this job.")

# =========================================
# AI CHAT (Q&A only)
# =========================================
elif page == "AI":
    st.title("🤖 AI Chat")

    question = st.text_area("Ask AI")

    if st.button("Send"):
        ans = ask_ai(email, question)
        ss["last_ai_answer"] = ans
        st.write("### Reply:")
        st.write(ans)

# =========================================
# AI PRODUCTION PLAN (today only, with Done / Can't Do Today)
# =========================================
elif page == "AIPlan":
    st.title("📅 AI Production Plan")

    settings = ss["schedule_settings"]

    # --------------------------
    # Working hours
    # --------------------------
    st.subheader("Working Hours")
    ws = time_picker("Start", settings["work_start"], "ws")
    we = time_picker("End", settings["work_end"], "we")

    # --------------------------
    # Break management
    # --------------------------
    st.subheader("Breaks")
    breaks = settings["breaks"].copy()

    for i, (b1, b2) in enumerate(breaks):
        st.markdown(f"**Break {i+1}**")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            nb1 = time_picker("Start", b1, f"b1_{i}")
        with c2:
            nb2 = time_picker("End", b2, f"b2_{i}")
        with c3:
            if st.button("❌ Remove", key=f"remove_break_{i}"):
                breaks.pop(i)
                st.rerun()
        breaks[i] = (nb1, nb2)

    st.markdown("---")
    st.caption("Add new break")
    nb1 = time_picker("New Break Start", time(13, 0), "addb1")
    nb2 = time_picker("New Break End", time(14, 0), "addb2")

    if st.button("Add Break"):
        if nb2 > nb1:
            breaks.append((nb1, nb2))
            # update settings and rerun
            ss["schedule_settings"]["breaks"] = breaks
            st.rerun()
        else:
            st.warning("Invalid break")

    # Save setting updates (hours + breaks)
    ss["schedule_settings"] = {
        "work_start": ws,
        "work_end": we,
        "breaks": breaks,
    }

    st.markdown("---")
    st.subheader("Generate Today's Plan")

    if st.button("Generate Today's Production Plan"):
        df_plan, meta = generate_schedule(email, ss["schedule_settings"])
        if df_plan.empty:
            st.info("No jobs or processes to schedule today.")
        else:
            ss["last_plan_df"] = df_plan
            ss["plan_row_meta"] = meta

            # AI review of plan
            csv_plan = df_plan.to_csv(index=False)
            review_prompt = f"""
I have generated this factory production schedule (CSV) for TODAY:

{csv_plan}

Instructions:
- Do NOT change the schedule.
- Only review it.
- Tell me if process grouping looks efficient.
- Point out if any job with an earlier due date seems too close to the deadline.
- Suggest improvements in simple bullet points.
"""
            ss["last_plan_review"] = ask_ai(email, review_prompt)
            st.success("Today's plan generated and reviewed by AI!")

    st.markdown("---")
    st.subheader("Today's Plan")

    if isinstance(ss.get("last_plan_df"), pd.DataFrame) and not ss["last_plan_df"].empty:
        # Editable table with Done / CantDoToday in columns
        edited_df = st.data_editor(
            ss["last_plan_df"],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Done": st.column_config.CheckboxColumn("Done"),
                "CantDoToday": st.column_config.CheckboxColumn("Can't Do Today"),
            },
        )

        if st.button("Save Status Updates"):
            ss["last_plan_df"] = edited_df
            meta = ss.get("plan_row_meta", [])

            # Load jobs for this user into a map
            jobs_all = [j for j in fs_get("jobs") if j.get("user_email") == email]
            job_map = {j["id"]: j for j in jobs_all}
            updated_jobs = {}

            for i, row in edited_df.iterrows():
                if i >= len(meta):
                    continue
                m = meta[i]
                if not m:
                    # break rows (no job/process to update)
                    continue

                job_id = m["job_id"]
                proc_index = m["proc_index"]

                done = bool(row.get("Done", False))
                cant = bool(row.get("CantDoToday", False))

                if not (done or cant):
                    continue  # nothing to change

                job = job_map.get(job_id)
                if not job:
                    continue

                try:
                    procs = json.loads(job.get("processes", "[]"))
                except Exception:
                    procs = []

                if proc_index < 0 or proc_index >= len(procs):
                    continue

                if done:
                    procs[proc_index]["completed"] = True
                    procs[proc_index]["defer_until"] = ""
                elif cant:
                    procs[proc_index]["completed"] = False
                    procs[proc_index]["defer_until"] = (date.today() + timedelta(days=1)).isoformat()

                updated_jobs[job_id] = procs

            for jid, procs in updated_jobs.items():
                fs_update("jobs", jid, {"processes": json.dumps(procs)})

            st.success("Process statuses updated. Regenerate plan tomorrow to see rescheduled tasks.")

        # Show AI review if available
        if ss.get("last_plan_review"):
            st.markdown("### AI Review")
            st.write(ss["last_plan_review"])
    else:
        st.info("No plan yet. Click 'Generate Today's Production Plan'.")
