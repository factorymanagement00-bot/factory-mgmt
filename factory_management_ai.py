import firebase_admin
from firebase_admin import credentials, firestore

import os
import json
from datetime import datetime, timedelta, date

import streamlit as st
import pandas as pd

# GEMINI AI
import google.generativeai as genai

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="Factory Management AI", layout="wide")

# ============================================================
# READ GEMINI API KEY FROM SECRETS
# ============================================================
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", None)

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None
    st.error("❌ No GEMINI_API_KEY found in secrets.toml!")

# ============================================================
# FIREBASE INIT
# ============================================================
db = None
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    st.error(f"Firebase initialization failed: {e}")

# ============================================================
# SESSION STATE INIT
# ============================================================
if "inventory" not in st.session_state:
    st.session_state.inventory = []

if "categories" not in st.session_state:
    st.session_state.categories = []

if "jobs" not in st.session_state:
    st.session_state.jobs = []

if "task_done" not in st.session_state:
    st.session_state.task_done = {}

if "staff_count" not in st.session_state:
    st.session_state.staff_count = 5

if "work_hours" not in st.session_state:
    st.session_state.work_hours = 8


# ============================================================
# FIREBASE HELPERS
# ============================================================

def get_categories_from_db():
    if db is None:
        return st.session_state.get("categories", [])
    names = set()
    for d in db.collection("categories").stream():
        x = d.to_dict().get("name")
        if x:
            names.add(x)
    return sorted(list(names))


def add_category_to_db(name: str):
    if db:
        db.collection("categories").add({"name": name})


def get_inventory_from_db():
    if db is None:
        return st.session_state.get("inventory", [])

    items = []
    for doc in db.collection("inventory").stream():
        data = doc.to_dict()
        data["id"] = doc.id
        items.append(data)
    return items


def add_inventory_item_to_db(item: dict):
    if db:
        db.collection("inventory").add(item)


def delete_inventory_item_from_db(doc_id: str):
    if db:
        db.collection("inventory").document(doc_id).delete()


def get_jobs_from_db():
    if db is None:
        return st.session_state.get("jobs", [])

    jobs = []
    for doc in db.collection("jobs").stream():
        d = doc.to_dict()
        d["id"] = doc.id
        jobs.append(d)
    return jobs


def add_job_to_db(job_doc: dict):
    if db:
        db.collection("jobs").add(job_doc)


def get_task_done_map_from_db():
    if db is None:
        return st.session_state.get("task_done", {})
    out = {}
    for doc in db.collection("task_done").stream():
        out[doc.id] = bool(doc.to_dict().get("done", False))
    return out


def set_task_done_in_db(task_id: str, done: bool):
    if db:
        db.collection("task_done").document(task_id).set({"done": done})


def load_settings_from_db():
    staff = st.session_state.staff_count
    hours = st.session_state.work_hours

    if db is None:
        return staff, hours

    doc = db.collection("settings").document("factory").get()
    if doc.exists:
        d = doc.to_dict()
        staff = int(d.get("staff_count", staff))
        hours = int(d.get("work_hours", hours))

    return staff, hours


def save_settings_to_db(staff: int, hours: int):
    if db:
        db.collection("settings").document("factory").set(
            {"staff_count": staff, "work_hours": hours},
            merge=True
        )


# ============================================================
# AI PLANNER (GEMINI)
# ============================================================

def call_ai_planner(jobs, inventory, staff_count, work_hours):
    if gemini_model is None:
        return None, "Gemini API not configured!"

    payload = {
        "jobs": jobs,
        "inventory": inventory,
        "staff_count": staff_count,
        "work_hours": work_hours,
    }

    prompt = f"""
You are an AI factory scheduler.

Rules:
- Prioritize jobs with earlier due dates.
- Batch similar processes together.
- Workday 09:00–17:00 with lunch 13:00–14:00.
- Do not create fake jobs.
- Return ONLY valid JSON with this structure:

{{ "tasks": [
   {{"job":"Tiger", "process":"cutting", "machine":"M1",
     "workers":2, "start":"09:00", "end":"10:30"}}
] }}

Here is the data:
{json.dumps(payload)}
"""

    try:
        res = gemini_model.generate_content(prompt)
        text = res.text.strip()

        data = json.loads(text)
        return data.get("tasks", []), None

    except Exception as e:
        return None, f"Gemini Planner Error: {e}"


# ============================================================
# SIMPLE LOCAL PLANNER
# ============================================================

def smart_batch_schedule(jobs, done_map):
    start_dt = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    today = date.today()
    tasks = []

    # flatten jobs
    for idx, job in enumerate(jobs):
        job_id = job.get("id", str(idx))

        try:
            due = datetime.strptime(job["due"], "%Y-%m-%d").date()
        except:
            due = today

        for pi, p in enumerate(job["processes"]):
            tid = f"{job_id}_{pi}"
            if done_map.get(tid, False):
                continue

            tasks.append({
                "task_id": tid,
                "job": job["job"],
                "due": due,
                "due_str": job["due"],
                "process": p["name"],
                "hours": float(p["hours"]),
                "workers": int(p["workers"]),
                "machine": p.get("machine", "")
            })

    if not tasks:
        return []

    tasks.sort(key=lambda x: x["due"])

    timeline = []
    current = start_dt
    used = set()

    for i, base in enumerate(tasks):
        if base["task_id"] in used:
            continue

        start = current
        end = start + timedelta(hours=base["hours"])

        if start < lunch_start < end:
            end += (lunch_end - lunch_start)

        # due status
        if base["due"] < today:
            due_status = "OVERDUE"
        elif base["due"] <= today + timedelta(days=1):
            due_status = "NEAR DUE"
        else:
            due_status = "OK"

        timeline.append({
            "task_id": base["task_id"],
            "Job": base["job"],
            "Process": base["process"],
            "Machine": base["machine"],
            "Workers": base["workers"],
            "Hours": base["hours"],
            "Due Date": base["due_str"],
            "Due Status": due_status,
            "Start": start.strftime("%H:%M"),
            "End": end.strftime("%H:%M")
        })

        used.add(base["task_id"])
        current = end

    return timeline


# ============================================================
# INVENTORY PAGE
# ============================================================

def inventory_page():
    st.title("📦 Inventory")

    st.session_state.categories = get_categories_from_db()
    st.session_state.inventory = get_inventory_from_db()

    with st.expander("Add Category"):
        c = st.text_input("Category name")
        if st.button("Save Category"):
            if c.strip() and c not in st.session_state.categories:
                add_category_to_db(c.strip())
                st.experimental_rerun()

    st.subheader("Add Inventory Item")
    name = st.text_input("Item name")
    cat = st.selectbox("Category", ["None"] + st.session_state.categories)
    qty = st.number_input("Quantity", min_value=0, value=1)
    size = st.text_input("Size")
    weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)

    if st.button("Add Item"):
        if name.strip():
            add_inventory_item_to_db({
                "name": name.strip(),
                "category": cat if cat != "None" else "",
                "quantity": qty,
                "size": size,
                "weight": weight
            })
            st.success("Item added!")
            st.experimental_rerun()

    st.markdown("---")
    st.subheader("Inventory List")

    if not st.session_state.inventory:
        st.info("No items added yet.")
    else:
        for it in st.session_state.inventory:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            col1.write(f"**{it.get('name')}**")
            col2.write(it.get("category") or "—")
            col3.write(f"Qty: {it.get('quantity')}")
            col4.write(f"Size: {it.get('size')}")
            if col5.button("🗑️", key=f"del_{it['id']}"):
                delete_inventory_item_from_db(it["id"])
                st.experimental_rerun()


# ============================================================
# JOBS PAGE
# ============================================================

def jobs_page():
    st.title("🧾 Jobs")

    st.session_state.categories = get_categories_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.jobs = get_jobs_from_db()

    job_name = st.text_input("Job name")
    due_date = st.date_input("Due date")

    num_proc = st.slider("Number of processes", 1, 20, 1)
    processes = []

    for i in range(num_proc):
        st.markdown(f"### Process {i+1}")
        pname = st.text_input(f"Process name {i+1}", key=f"pn_{i}")
        hours = st.number_input(f"Hours {i+1}", min_value=0.5, value=1.0, key=f"h_{i}")
        workers = st.number_input(f"Workers {i+1}", min_value=1, value=1, key=f"w_{i}")
        machine = st.text_input(f"Machine {i+1}", key=f"m_{i}")

        processes.append({
            "name": pname,
            "hours": hours,
            "workers": workers,
            "machine": machine,
        })
        st.markdown("---")

    if st.button("Save Job"):
        if job_name.strip():
            add_job_to_db({
                "job": job_name.strip(),
                "due": due_date.isoformat(),
                "processes": processes
            })
            st.success("Job saved!")
            st.experimental_rerun()

    st.subheader("Existing Jobs")
    for j in st.session_state.jobs:
        with st.expander(f"{j['job']} (Due {j['due']})"):
            for p in j["processes"]:
                st.write(f"- {p['name']} | {p['hours']} hrs | {p['workers']} workers")


# ============================================================
# PLANNER PAGE
# ============================================================

def planner_page():
    st.title("🧠 Planner")

    st.session_state.jobs = get_jobs_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.task_done = get_task_done_map_from_db()
    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    if not st.session_state.jobs:
        st.info("No jobs created yet.")
        return

    st.subheader("🤖 AI Planner (Gemini)")

    if st.button("Generate Today's Plan with AI"):
        tasks, err = call_ai_planner(
            st.session_state.jobs,
            st.session_state.inventory,
            st.session_state.staff_count,
            st.session_state.work_hours,
        )
        if err:
            st.error(err)
        else:
            st.dataframe(pd.DataFrame(tasks), use_container_width=True)

    st.markdown("---")

    st.subheader("⚙ Local Smart Planner")

    schedule = smart_batch_schedule(st.session_state.jobs, st.session_state.task_done)

    if not schedule:
        st.success("All tasks are done!")
        return

    df = pd.DataFrame(schedule)
    st.dataframe(df.drop(columns=["task_id"]), use_container_width=True)

    st.markdown("### Mark tasks as Done")

    for row in schedule:
        tid = row["task_id"]

        col1, col2 = st.columns([4, 1])
        col1.write(f"**{row['Job']}** | {row['Process']} | {row['Start']}–{row['End']} | Due {row['Due Date']} ({row['Due Status']})")

        done_state = st.checkbox("Done", value=st.session_state.task_done.get(tid, False), key=f"done_{tid}")
        st.session_state.task_done[tid] = done_state
        set_task_done_in_db(tid, done_state)


# ============================================================
# AI CHAT PAGE
# ============================================================

def ai_chat_page():
    st.title("💬 Factory AI Chat")

    if gemini_model is None:
        st.error("Gemini API Key missing!")
        return

    st.session_state.jobs = get_jobs_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    msg = st.text_area("Ask something", height=120)

    if st.button("Ask AI"):
        context = {
            "jobs": st.session_state.jobs,
            "inventory": st.session_state.inventory,
            "staff_count": st.session_state.staff_count,
            "work_hours": st.session_state.work_hours,
        }

        prompt = f"""You are a smart factory assistant.

DATA:
{json.dumps(context)}

USER QUESTION:
{msg}
"""

        try:
            res = gemini_model.generate_content(prompt)
            st.write(res.text)
        except Exception as e:
            st.error(f"AI Error: {e}")


# ============================================================
# STAFF PAGE
# ============================================================

def staff_page():
    st.title("👷 Staff Settings")

    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    staff = st.number_input("Total Staff", min_value=1, value=st.session_state.staff_count)
    hours = st.number_input("Daily Work Hours", min_value=1, value=st.session_state.work_hours)

    if st.button("Save"):
        save_settings_to_db(staff, hours)
        st.success("Saved!")


# ============================================================
# MAIN ROUTER
# ============================================================

def main():
    page = st.sidebar.radio(
        "Navigate",
        ["Inventory", "Jobs", "Planner", "AI Chat", "Staff"],
        index=0
    )

    if page == "Inventory":
        inventory_page()
    elif page == "Jobs":
        jobs_page()
    elif page == "Planner":
        planner_page()
    elif page == "AI Chat":
        ai_chat_page()
    elif page == "Staff":
        staff_page()


if __name__ == "__main__":
    main()
