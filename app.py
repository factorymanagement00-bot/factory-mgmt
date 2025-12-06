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

PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "AIzaSyBCO9BMXJ3zJ8Ae0to4VJPXAYgYn4CHl58"

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
if not OPENROUTER_KEY:
    try:
        OPENROUTER_KEY = st.secrets["openrouter_key"]
    except Exception:
        st.error("OPENROUTER_KEY missing. Add to env or Streamlit secrets.")
        st.stop()

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

# ============================================
# CSS
# ============================================
st.markdown("""
<style>
html,body,[class*="css"]{font-family:'Inter',sans-serif!important;}
.no-sidebar [data-testid="stSidebar"]{display:none!important;}
...
</style>
""", unsafe_allow_html=True)

# ============================================
# SESSION STATE
# ============================================
ss = st.session_state
if "user" not in ss: ss["user"] = None
if "page" not in ss: ss["page"] = "Dashboard"
if "job_processes" not in ss: ss["job_processes"] = []
if "job_stocks" not in ss: ss["job_stocks"] = []
if "new_stock_sizes" not in ss: ss["new_stock_sizes"] = []
if "schedule_settings" not in ss:
    ss["schedule_settings"] = {
        "work_start": time(9,0),
        "work_end": time(17,0),
        "breaks": []
    }

# ============================================
# UTILITIES
# ============================================
def safe_int(v):
    try: return int(v)
    except: return 0

def safe_float(v):
    try: return float(v)
    except: return 0.0

# ============================================
# AUTH
# ============================================
def signup(email, pw):
    return requests.post(SIGNUP_URL, json={
        "email": email,
        "password": pw,
        "returnSecureToken": True
    }).json()

def login(email, pw):
    return requests.post(SIGNIN_URL, json={
        "email": email,
        "password": pw,
        "returnSecureToken": True
    }).json()

# ============================================
# FIRESTORE HELPERS (FIXED)
# ============================================
def fs_add(col, data):
    fields = {k: {"stringValue": str(v)} for k,v in data.items()}
    requests.post(f"{BASE_URL}/{col}?key={API_KEY}", json={"fields": fields})

@st.cache_data(ttl=5)
def fs_get(col):
    """ FIXED — returns ALL documents correctly """
    url = f"{BASE_URL}/{col}?key={API_KEY}"
    r = requests.get(url).json()

    if "documents" not in r:
        return []

    out = []
    for d in r["documents"]:
        fields = d.get("fields", {})
        row = {}
        for k,v in fields.items():
            if "stringValue" in v:
                row[k] = v["stringValue"]
            else:
                row[k] = str(v)
        row["id"] = d["name"].split("/")[-1]
        out.append(row)

    return out

def fs_update(col, id, data):
    fields = {k: {"stringValue": str(v)} for k,v in data.items()}
    requests.patch(
        f"{BASE_URL}/{col}/{id}?key={API_KEY}",
        json={"fields": fields}
    )
    st.cache_data.clear()

def fs_delete(col, id):
    requests.delete(f"{BASE_URL}/{col}/{id}?key={API_KEY}")
    st.cache_data.clear()

# ============================================
# STOCK HELPERS (MULTI SIZE + AUTO DEDUCT)
# ============================================
def parse_sizes(s):
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except:
        pass
    return []

def get_user_stocks(email):
    rows = [r for r in fs_get("stocks") if r.get("user_email") == email]

    for r in rows:
        sizes = parse_sizes(r.get("sizes","[]"))
        # fallback for old format
        if not sizes:
            old_size = r.get("size")
            old_qty = r.get("quantity")
            if old_size or old_qty:
                sizes = [{"size": old_size, "qty": safe_float(old_qty)}]

        r["sizes_list"] = sizes
        r["quantity_total"] = sum(safe_float(z.get("qty",0)) for z in sizes)

    return rows

def deduct_stock(job_stocks):
    """Auto deduct stock per size."""
    if not job_stocks:
        return

    all_rows = fs_get("stocks")

    for used in job_stocks:
        sid = used["stock_id"]
        size_str = str(used["size"])
        used_qty = safe_float(used["use_qty"])

        for row in all_rows:
            if row["id"] != sid:
                continue

            sizes = parse_sizes(row.get("sizes","[]"))

            # build new sizes list
            new_sizes = []
            for z in sizes:
                if str(z["size"]) == size_str:
                    rem = safe_float(z["qty"]) - used_qty
                    if rem > 0:
                        new_sizes.append({"size": z["size"], "qty": rem})
                else:
                    new_sizes.append(z)

            if not new_sizes:
                fs_delete("stocks", sid)
            else:
                fs_update("stocks", sid, {"sizes": json.dumps(new_sizes)})

            break

# ============================================
# LOGIN
# ============================================
if ss["user"] is None:
    st.markdown('<div class="no-sidebar">', unsafe_allow_html=True)
    st.title("🔐 Login")

    mode = st.selectbox("Mode", ["Login", "Sign Up"])
    email = st.text_input("Email")
    pw = st.text_input("Password", type="password")

    if mode == "Sign Up":
        cpw = st.text_input("Confirm Password", type="password")

    if st.button(mode):
        if mode == "Login":
            res = login(email,pw)
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                ss["user"] = email
                st.rerun()
        else:
            if pw != cpw:
                st.error("Passwords don't match")
            else:
                res = signup(email,pw)
                if "error" in res:
                    st.error(res["error"]["message"])
                else:
                    st.success("Account created.")
    st.stop()

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    def nav(name, icon, page):
        cls = "selected" if ss["page"] == page else ""
        if st.button(f"{icon} {name}"):
            ss["page"] = page
            st.rerun()

    st.header("📦 Factory")
    nav("Dashboard","🏠","Dashboard")
    nav("Add Job","➕","AddJob")
    nav("Add Stock","📦","AddStock")
    nav("View Jobs","📋","ViewJobs")
    nav("AI Chat","🤖","AI")
    nav("AI Plan","📅","AIPlan")

    if st.button("Logout"):
        ss["user"] = None
        st.rerun()

# ============================================
# PAGE: DASHBOARD
# ============================================
page = ss["page"]
user_email = ss["user"]

if page == "Dashboard":
    st.title("📊 Dashboard")
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]

    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df.drop(columns=[
            "user_email","processes","stocks_used","notes"
        ], errors="ignore"))

# ============================================
# PAGE: ADD JOB
# ============================================
elif page == "AddJob":
    st.title("➕ Add Job")

    job_name = st.text_input("Job Name")
    client_name = st.text_input("Client Name")
    phone = st.text_input("Phone")
    amount = st.number_input("Amount", min_value=0.0)
    quantity = st.number_input("Quantity", min_value=1)
    job_type = st.text_input("Job Type")
    status = st.selectbox("Status", ["Pending","In Progress","Completed"])
    due_date = st.date_input("Due Date", date.today())

    st.subheader("Processes")
    p1,p2,p3 = st.columns([3,1,1])
    with p1: pname = st.text_input("Process Name")
    with p2: phours = st.number_input("Hours", min_value=0.0, step=0.25)
    with p3:
        if st.button("Add Process"):
            if pname and phours>0:
                ss["job_processes"].append({"name":pname,"hours":phours})
    if ss["job_processes"]:
        st.table(pd.DataFrame(ss["job_processes"]))
    else:
        st.caption("No processes added yet.")

    # ============================================
    # STOCKS (MULTI SIZE + AUTO DEDUCT)
    # ============================================
    st.subheader("🧰 Stock Used (Multi-size)")

    stocks = get_user_stocks(user_email)
    stock_labels = ["None"]
    stock_map = {}

    # show sizes in dropdown
    for i, s in enumerate(stocks):
        size_parts = [f"{z['size']} ({z['qty']})" for z in s["sizes_list"]]
        size_text = " | ".join(size_parts) if size_parts else "No sizes"
        label = f"{s['name']} ({s.get('category','')}) — {size_text}"
        stock_labels.append(label)
        stock_map[label] = i

    selected_stock_label = st.selectbox("Select Stock", stock_labels)

    if selected_stock_label != "None":
        s = stocks[stock_map[selected_stock_label]]
        sizes_list = s["sizes_list"]

        if sizes_list:
            size_opts = [str(z["size"]) for z in sizes_list]
            selected_size = st.selectbox("Select Size", size_opts)

            chosen = next((z for z in sizes_list if str(z["size"]) == selected_size), None)
            if chosen:
                available = safe_float(chosen["qty"])
                st.info(f"Available: {available}")

                use_qty = st.number_input("Quantity to use", min_value=0.0, max_value=available, step=0.5)

                if st.button("Add Stock to Job"):
                    if use_qty > 0:
                        ss["job_stocks"].append({
                            "stock_id": s["id"],
                            "name": s["name"],
                            "category": s.get("category",""),
                            "size": selected_size,
                            "available_qty": available,
                            "use_qty": use_qty,
                        })
                    else:
                        st.warning("Quantity must be > 0")
        else:
            st.warning("This stock has no sizes.")

    if ss["job_stocks"]:
        st.subheader("Stocks Added to Job")
        st.table(pd.DataFrame(ss["job_stocks"])[
            ["name","category","size","use_qty","available_qty"]
        ])
    else:
        st.caption("No stocks added yet.")

    # ============================================
    # SAVE JOB
    # ============================================
    if st.button("Save Job"):
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
                "processes": json.dumps(ss["job_processes"]),
                "stocks_used": json.dumps(ss["job_stocks"]),
            },
        )

        # auto deduct from stock
        deduct_stock(ss["job_stocks"])

        ss["job_processes"] = []
        ss["job_stocks"] = []
        st.cache_data.clear()
        st.success("Job saved and stock updated automatically!")
        st.rerun()

# ============================================
# PAGE: ADD STOCK
# ============================================
elif page == "AddStock":
    st.title("📦 Add / Manage Stock")

    s_name = st.text_input("Stock Name")
    s_category = st.text_input("Category")

    st.subheader("➕ Add New Size")

    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        new_size = st.text_input("Size")
    with c2:
        new_qty = st.number_input("Quantity", min_value=0.0, step=0.5)
    with c3:
        st.write("")
        if st.button("Add Size"):
            if new_size and new_qty > 0:
                ss["new_stock_sizes"].append({"size": new_size, "qty": new_qty})
            else:
                st.warning("Enter valid size and qty.")

    if ss["new_stock_sizes"]:
        st.subheader("Sizes Added")
        st.table(pd.DataFrame(ss["new_stock_sizes"]))

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
    st.subheader("Current Stock")

    rows = []
    stocks = get_user_stocks(user_email)
    for s in stocks:
        for z in s["sizes_list"]:
            rows.append({
                "Name": s["name"],
                "Category": s.get("category",""),
                "Size": z["size"],
                "Quantity": z["qty"],
                "StockID": s["id"]
            })

    if rows:
        st.dataframe(pd.DataFrame(rows)[["Name","Category","Size","Quantity"]], use_container_width=True)
    else:
        st.info("No stock added yet.")

    st.subheader("🗑️ Delete Entire Stock")
    delete_options = ["None"] + [f"{s['name']} ({s.get('category','')})" for s in stocks]

    del_choice = st.selectbox("Select stock to delete", delete_options)
    if del_choice != "None":
        idx = delete_options.index(del_choice) - 1
        if idx >= 0:
            delete_id = stocks[idx]["id"]
            if st.button("Delete Now"):
                fs_delete("stocks", delete_id)
                st.success("Stock deleted!")
                st.cache_data.clear()
                st.rerun()

# ============================================
# PAGE: VIEW JOBS
# ============================================
elif page == "ViewJobs":
    st.title("📋 Manage Jobs")
    jobs = [j for j in fs_get("jobs") if j.get("user_email") == user_email]

    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)
        show = df.drop(columns=[
            "user_email","processes","stocks_used","created_at"
        ], errors="ignore")

        st.dataframe(show, use_container_width=True)

        job_id = st.selectbox("Select Job", df["id"])
        job = df[df["id"] == job_id].iloc[0]

        new_amt = st.number_input("Amount", value=safe_int(job["amount"]))
        new_stat = st.selectbox(
            "Status",
            ["Pending","In Progress","Completed"],
            index=["Pending","In Progress","Completed"].index(job["status"])
        )
        new_notes = st.text_area("Notes", job.get("notes",""))

        if st.button("Update Job"):
            fs_update("jobs", job_id, {
                "amount": new_amt,
                "status": new_stat,
                "notes": new_notes
            })
            st.success("Updated!")

        if st.button("Delete Job"):
            fs_delete("jobs", job_id)
            st.warning("Job deleted!")

# ============================================
# PAGE: AI CHAT
# ============================================
elif page == "AI":
    st.title("🤖 AI Chat")

    q = st.text_area("Ask something:", "Plan my today's work.")
    if st.button("Ask"):
        ans = ask_ai(user_email, q)
        st.write("### AI Response:")
        st.write(ans)

        if is_planning_query(q):
            st.subheader("📅 Auto Plan")
            ws = ss["schedule_settings"]["work_start"]
            we = ss["schedule_settings"]["work_end"]
            br = ss["schedule_settings"]["breaks"]
            df = build_ai_plan(user_email, ws, we, br)
            st.dataframe(df, use_container_width=True)

# ============================================
# PAGE: AI PLAN
# ============================================
elif page == "AIPlan":
    st.title("📅 AI Production Plan")

    settings = ss["schedule_settings"]

    st.subheader("Working Hours")
    ws = ui_time_picker_12("Work Start", settings["work_start"], "ws")
    we = ui_time_picker_12("Work End", settings["work_end"], "we")

    st.subheader("Breaks")
    breaks = []

    # existing breaks
    for i,(b1,b2) in enumerate(settings["breaks"]):
        st.markdown(f"**Break {i+1}**")
        c1,c2,c3 = st.columns([2,2,1])
        with c1:
            nb1 = ui_time_picker_12("Start", b1, f"b{i}start")
        with c2:
            nb2 = ui_time_picker_12("End", b2, f"b{i}end")
        with c3:
            if st.button("❌ Remove", key=f"rm{i}"):
                continue
        if nb2 > nb1:
            breaks.append((nb1,nb2))

    st.markdown("### Add New Break")
    c1,c2,c3 = st.columns([2,2,1])
    with c1: nb1 = ui_time_picker_12("Start", time(13,0), "nb1")
    with c2: nb2 = ui_time_picker_12("End", time(14,0), "nb2")
    with c3:
        if st.button("Add Break"):
            if nb2 > nb1:
                breaks.append((nb1,nb2))

    ss["schedule_settings"] = {
        "work_start": ws,
        "work_end": we,
        "breaks": breaks
    }

    if st.button("Generate Plan"):
        df = build_ai_plan(user_email, ws, we, breaks)
        if df.empty:
            st.warning("No processes found.")
        else:
            st.success("Plan generated!")
            st.dataframe(df, use_container_width=True)
            ss["last_plan_df"] = df.to_dict("records")
    else:
        if ss["last_plan_df"]:
            st.info("Showing last plan:")
            st.dataframe(pd.DataFrame(ss["last_plan_df"]), use_container_width=True)
