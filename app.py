import streamlit as st
import requests
import pandas as pd
import json
import os
import io
from datetime import datetime, date, time, timedelta

# =========================================
# APP SETTINGS
# =========================================
st.set_page_config(page_title="Factory Manager Pro", layout="wide")

# Load secrets safely
PROJECT_ID = st.secrets["project_id"]
API_KEY = st.secrets["firebase_api_key"]

# OpenRouter API KEY (for AI chat / review / schedule)
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
    "last_plan_df": None,      # DataFrame with plan (visible)
    "last_plan_review": "",    # AI review text
    "plan_row_meta": [],       # [{job_id, proc_index} or None for breaks]
    "schedule_settings": {
        "work_start": time(9, 0),
        "work_end": time(17, 0),
        "breaks": [],          # list[(time,time)]
    },
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


def time_picker(label, default, key):
    """12-hour time picker (HH, MM, AM/PM)."""
    h24 = default.hour
    h12 = h24 % 12 or 12
    ap = "AM" if h24 < 12 else "PM"

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        h = st.selectbox(
            f"{label} Hour", list(range(1, 13)), index=h12 - 1, key=f"{key}_h"
        )
    with c2:
        m = st.selectbox(
            f"{label} Min", [0, 15, 30, 45], index=0, key=f"{key}_m"
        )
    with c3:
        ap_sel = st.selectbox(
            f"{label} AM/PM",
            ["AM", "PM"],
            index=0 if ap == "AM" else 1,
            key=f"{key}_ap",
        )

    h24_new = h % 12 + (12 if ap_sel == "PM" else 0)
    return time(h24_new, m)


# =========================================
# FIRESTORE HELPERS
# =========================================
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


def fs_add(col, data):
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.post(f"{BASE_URL}/{col}?key={API_KEY}", json={"fields": fields})
    fs_get.clear()


def fs_update(col, id, data):
    fields = {k: {"stringValue": str(v)} for k, v in data.items()}
    requests.patch(f"{BASE_URL}/{col}/{id}?key={API_KEY}", json={"fields": fields})
    fs_get.clear()


def fs_delete(col, id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    fs_get.clear()


# =========================================
# DOMAIN HELPERS (STOCK, STAFF, AI, SCHEDULER)
# =========================================
def parse_sizes(s):
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return []


def get_user_staff(email):
    return [r for r in fs_get("staff") if r.get("user_email") == email]


def get_user_stocks(email):
    rows = [r for r in fs_get("stocks") if r.get("user_email") == email]
    for r in rows:
        sizes = parse_sizes(r.get("sizes", "[]"))
        if not sizes:
            sizes = [{
                "size": r.get("size", ""),
                "qty": safe_float(r.get("quantity", 0)),
            }]
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
        for z in s["sizes_list"] in s["sizes_list"]:
            out.append(f"- {s['name']} size {z['size']} qty {z['qty']}")
    return "\n".join(out)


def ask_ai(email, query):
    if not OPENROUTER_KEY:
        return "OPENROUTER_KEY not set. Add it to env or Streamlit secrets."

    system_prompt = "You are FactoryGPT — expert in factory workflows, stock, jobs, and planning."
    messages = [{"role": "system", "content": system_prompt}]

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
    return ans


# =========================================
# AI-POWERED SCHEDULER (2-DAY PLAN, WITH PASTING RULE)
# =========================================
def generate_schedule(email, settings):
    """
    AI-powered schedule generator (today + tomorrow).

    - Sends all jobs + processes + settings to OpenRouter.
    - AI creates a CSV schedule using your rules:
        1) Always prioritize urgent jobs (earlier due_date first).
        2) PASTING RULE:
           For any job, once a process named "pasting" is scheduled on a date,
           all later processes for that job must be scheduled on the NEXT day
           or later (never same date).
        3) Respect work_start, work_end, and breaks.
        4) Skip completed=True processes.
        5) Respect defer_until (don't schedule before that date).
        6) Only use TODAY or TOMORROW as dates (no further days).

    - Returns:
        df: DataFrame with columns:
            Date, Job, Process, Staff, Outsiders, Start, End, Due Date, Done, CantDoToday
        row_meta: list with either None (for breaks) or {job_id, proc_index}
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    jobs_all = [j for j in fs_get("jobs") if j.get("user_email") == email]
    if not jobs_all:
        return pd.DataFrame(), []

    # Build jobs payload for the AI
    jobs_payload = []
    for j in jobs_all:
        try:
            procs = json.loads(j.get("processes", "[]"))
        except Exception:
            procs = []

        jobs_payload.append(
            {
                "id": j["id"],
                "job_name": j.get("job_name", ""),
                "due_date": j.get("due_date", ""),
                "quantity": j.get("quantity", ""),
                "status": j.get("status", ""),
                "processes": procs,
            }
        )

    # Breaks into a simple structure
    breaks_simple = []
    for (b1, b2) in settings["breaks"]:
        breaks_simple.append(
            {
                "start": b1.strftime("%H:%M"),
                "end": b2.strftime("%H:%M"),
            }
        )

    # Data that AI will receive
    ai_input = {
        "today": today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "work_start": settings["work_start"].strftime("%H:%M"),
        "work_end": settings["work_end"].strftime("%H:%M"),
        "breaks": breaks_simple,
        "jobs": jobs_payload,
    }

    if not OPENROUTER_KEY:
        # If key is missing, return empty and let UI show error
        return pd.DataFrame(), []

    system_prompt = """
You are FactoryScheduleGPT — an expert factory planner.

You must create a realistic, efficient 2-DAY production schedule that follows these RULES:

1) PRIORITIZE URGENT JOBS:
   - Jobs with the earliest 'due_date' must be scheduled first.
   - Do not leave a near-due job idle while a far-away job is scheduled.

2) PASTING RULE (VERY IMPORTANT):
   - In any single job, there may be multiple processes in sequence.
   - If a process has name 'pasting' (case-insensitive),
     then ALL processes that come AFTER 'pasting' for that same job
     MUST be scheduled on the NEXT calendar day or later,
     never on the same date as 'pasting'.
   - Example:
       Processes: Conversion -> Pasting -> Slotting -> Packing
       If Pasting is scheduled on 2025-12-09,
       then Slotting and Packing must be scheduled on 2025-12-10 or later.

3) DATE LIMIT (ONLY TODAY + TOMORROW):
   - You are only allowed to use TWO dates in the schedule:
       - 'today'
       - 'tomorrow'
   - If there is not enough time in these 2 days to schedule all processes,
     you may leave some processes unscheduled (they simply won't appear in the CSV).

4) RESPECT WORKING HOURS AND BREAKS:
   - Only schedule between 'work_start' and 'work_end' for each day.
   - Do NOT schedule any process during any break interval.
   - Breaks apply to both today and tomorrow for the same hours.

5) COMPLETED AND DEFERRED PROCESSES:
   - Each process may have fields like 'completed' (bool-ish) and 'defer_until' (date string).
   - SKIP any process where 'completed' is true (e.g. 'True', 'true', '1').
   - If 'defer_until' is set, do NOT schedule the process before that date.

6) STAFF AND OUTSIDERS:
   - Each process has 'staff' (list of names) and 'outsiders' (integer).
   - Put the staff names into a single string in the CSV, separated by commas.
   - Outsiders should be an integer in the CSV (0 if none).

OUTPUT FORMAT (VERY STRICT):
- You MUST reply ONLY with a CSV table. No commentary, no markdown, no explanation.
- The header row must be exactly:

Date,Job,Process,Staff,Outsiders,Start,End,Due Date,JobID,ProcessIndex

Where:
- Date: the calendar date for that row, in YYYY-MM-DD format.
        It must be either 'today' or 'tomorrow' from the provided data.
- Job: the job_name from the data.
- Process: the process name (or 'Break' for a break row, if you include breaks as rows).
- Staff: comma-separated staff names for that process.
- Outsiders: integer number of outsiders working on that process.
- Start: human-readable time, e.g. '09:00 AM'.
- End: human-readable time, e.g. '10:30 AM'.
- Due Date: the job's due_date.
- JobID: the job's 'id' field from input (blank for breaks).
- ProcessIndex: the index of the process within that job's processes array (0-based).
  For break rows, leave JobID and ProcessIndex empty.

Additional notes:
- Fill time chronologically without overlapping processes for the same job.
- You may insert rows for breaks (Process='Break'), with empty JobID and ProcessIndex.
- Ensure you strictly follow the PASTING RULE and DATE LIMIT.
"""

    user_prompt = f"""
Here is the factory data in JSON:

{json.dumps(ai_input, ensure_ascii=False, indent=2)}

Remember:
- Today's date is {today.isoformat()}.
- Tomorrow's date is {tomorrow.isoformat()}.
- Respect work_start, work_end, and breaks.
- Apply the PASTING RULE strictly.
- Only use these dates in the 'Date' column: {today.isoformat()} or {tomorrow.isoformat()}.
- Return ONLY CSV with the exact header:
Date,Job,Process,Staff,Outsiders,Start,End, Due Date,JobID,ProcessIndex
"""

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek/deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=90,
        ).json()
    except Exception as e:
        st.error(f"AI scheduling error: {e}")
        return pd.DataFrame(), []

    try:
        content = r["choices"][0]["message"]["content"]
    except Exception:
        st.error(f"AI returned unexpected response: {r}")
        return pd.DataFrame(), []

    # Extract CSV from response (strip markdown fences if present)
    text = content.strip()
    if "```" in text:
        parts = text.split("```")
        csv_candidate = ""
        for p in parts:
            if "Date,Job,Process,Staff,Outsiders" in p:
                csv_candidate = p.strip()
                break
        if csv_candidate.lower().startswith("csv"):
            csv_candidate = "\n".join(csv_candidate.splitlines()[1:])
        csv_text = csv_candidate
    else:
        csv_text = text

    if not csv_text:
        st.error("AI did not return any CSV schedule.")
        return pd.DataFrame(), []

    try:
        df = pd.read_csv(io.StringIO(csv_text))
    except Exception as e:
        st.error(f"Failed to parse AI CSV: {e}\nRaw text:\n{csv_text}")
        return pd.DataFrame(), []

    # Build row_meta from JobID + ProcessIndex
    row_meta = []
    for _, row in df.iterrows():
        job_id = str(row.get("JobID", "")).strip()
        if not job_id or job_id.lower() == "nan":
            row_meta.append(None)
        else:
            try:
                pidx = int(row.get("ProcessIndex", 0))
            except Exception:
                pidx = 0
            row_meta.append({"job_id": job_id, "proc_index": pidx})

    # Drop helper columns from visible table
    for col in ["JobID", "ProcessIndex"]:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    # Add status columns for UI
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
            r = requests.post(
                SIGNIN_URL,
                json={"email": email, "password": pw, "returnSecureToken": True},
            ).json()
            if "error" in r:
                st.error("Invalid login")
            else:
                ss["user"] = email
                st.rerun()
        else:
            if pw != cpw:
                st.error("Passwords mismatch")
            else:
                r = requests.post(
                    SIGNUP_URL,
                    json={"email": email, "password": pw, "returnSecureToken": True},
                ).json()
                if "error" in r:
                    st.error("Error creating account")
                else:
                    st.success("Account created. Login now.")

    st.stop()

email = ss["user"]

# =========================================
# SIDEBAR NAVIGATION
# =========================================
with st.sidebar:
    def nav(label, icon, page_name):
        cls = "nav-selected" if ss["page"] == page_name else "navbox"
        st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
        if st.button(f"{icon} {label}", key=f"nav_{page_name}"):
            ss["page"] = page_name
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

page = ss["page"]

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

        hide_cols = ["user_email", "processes", "stocks_used", "notes"]
        df_show = df.drop(columns=[c for c in hide_cols if c in df.columns])
        st.subheader("All Jobs")
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
        st.dataframe(df[["name", "role", "status", "id"]], use_container_width=True)

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
# ADD JOB
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

    c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 2, 1])
    with c1:
        pname = st.text_input("Process Name")
    with c2:
        phours = st.number_input("Hours", min_value=0.0, step=0.25)
    with c3:
        selected_staff = st.multiselect("Staff", staff_names, key="proc_staff")
    with c4:
        outsider_count = st.number_input("Outsiders", min_value=0, max_value=50, step=1)
    with c5:
        if st.button("Add Process"):
            if pname and phours > 0:
                ss["job_processes"].append(
                    {
                        "name": pname,
                        "hours": phours,
                        "staff": selected_staff,
                        "outsiders": outsider_count,
                        "completed": False,
                        "defer_until": "",
                    }
                )
            else:
                st.warning("Enter valid process name & hours.")

    if ss["job_processes"]:
        st.table(pd.DataFrame(ss["job_processes"]))

    # STOCKS
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
        chosen = next(z for z in s["sizes_list"] if str(z["size"]) == str(sel_size))
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
# ADD STOCK
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
        st.dataframe(df[["Name", "Category", "Size", "Quantity"]], use_container_width=True)

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

        new_amount = st.number_input("Amount", value=safe_int(job["amount"]))
        new_status = st.selectbox(
            "Status",
            ["Pending", "In Progress", "Completed"],
            index=["Pending", "In Progress", "Completed"].index(job["status"]),
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
            st.table(pd.DataFrame(process_list))
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
# AI PRODUCTION PLAN (AI-POWERED, TODAY + TOMORROW)
# =========================================
elif page == "AIPlan":
    st.title("📅 AI Production Plan (Today + Tomorrow)")

    settings = ss["schedule_settings"]

    # Working hours
    st.subheader("Working Hours")
    ws = time_picker("Start", settings["work_start"], "ws")
    we = time_picker("End", settings["work_end"], "we")

    # Breaks
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
            ss["schedule_settings"]["breaks"] = breaks
            st.rerun()
        else:
            st.warning("Invalid break")

    # Save settings
    ss["schedule_settings"] = {
        "work_start": ws,
        "work_end": we,
        "breaks": breaks,
    }

    st.markdown("---")
    st.subheader("Generate Plan with AI (Today + Tomorrow)")

    if st.button("Generate AI Production Plan"):
        if not OPENROUTER_KEY:
            st.error("OPENROUTER_KEY is missing. Add it to Streamlit secrets as 'openrouter_key'.")
        else:
            df_plan, meta = generate_schedule(email, ss["schedule_settings"])
            if df_plan.empty:
                st.info("No jobs / processes to schedule (or AI failed).")
            else:
                ss["last_plan_df"] = df_plan
                ss["plan_row_meta"] = meta
                ss["last_plan_review"] = (
                    "This schedule was generated directly by AI using your custom rules "
                    "(urgent jobs first, and all processes after 'pasting' moved to the next day)."
                )
                st.success("AI-generated production plan created!")

    st.markdown("---")
    st.subheader("Current Plan")

    if isinstance(ss.get("last_plan_df"), pd.DataFrame) and not ss["last_plan_df"].empty:
        base_df = ss["last_plan_df"].copy()

        # Toggle: merge staff & outsiders into process label or not
        merge_toggle = st.checkbox(
            "Merge Staff & Outsiders into Process label", value=False
        )

        if merge_toggle:
            def build_label(row):
                label = row.get("Process", "")
                parts = []
                staff = row.get("Staff", "")
                outs = row.get("Outsiders", 0)
                try:
                    outs_int = int(outs)
                except Exception:
                    outs_int = 0
                if staff:
                    parts.append(f"Staff: {staff}")
                if outs_int > 0:
                    parts.append(f"Outsiders: {outs_int}")
                if parts:
                    return f"{label} ({', '.join(parts)})"
                return label

            base_df["Process"] = base_df.apply(build_label, axis=1)

        edited_df = st.data_editor(
            base_df,
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

            jobs_all = [j for j in fs_get("jobs") if j.get("user_email") == email]
            job_map = {j["id"]: j for j in jobs_all}
            updated_jobs = {}

            for i, row in edited_df.iterrows():
                if i >= len(meta):
                    continue
                m = meta[i]
                if not m:
                    continue  # break row or non-process row

                job_id = m["job_id"]
                proc_index = m["proc_index"]

                done = bool(row.get("Done", False))
                cant = bool(row.get("CantDoToday", False))
                if not (done or cant):
                    continue

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
                    procs[proc_index]["defer_until"] = (
                        date.today() + timedelta(days=1)
                    ).isoformat()

                updated_jobs[job_id] = procs

            for jid, procs in updated_jobs.items():
                fs_update("jobs", jid, {"processes": json.dumps(procs)})

            st.success("Process statuses updated. Regenerate plan to see changes.")

        if ss.get("last_plan_review"):
            st.markdown("### AI Note")
            st.write(ss["last_plan_review"])
    else:
        st.info("No plan yet. Click 'Generate AI Production Plan'.")
