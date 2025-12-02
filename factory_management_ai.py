import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

# Load API Key
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OPENAI_KEY:
    client = OpenAI(api_key=OPENAI_KEY)

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Factory AI", layout="wide")

# ============================================================
# SESSION STATE
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
# AI PLANNER FUNCTION (ChatGPT)
# ============================================================
def call_ai_planner(jobs, inventory, staff_count, work_hours):
    if client is None:
        return None, "❌ No API key found! Add it in .env as OPENAI_API_KEY=..."

    payload = {
        "jobs": jobs,
        "inventory": inventory,
        "staff_count": staff_count,
        "work_hours": work_hours,
    }

    SYSTEM_PROMPT = """
    You are an AI factory production planner.

    RULES YOU MUST FOLLOW:
    - Prioritize closest due dates.
    - Prefer batching same processes to save electricity.
    - Respect working hours 09:00–17:00 (13:00–14:00 lunch break).
    - Do NOT invent any jobs or processes.
    - Do NOT exceed 17:00 end time.
    - Always output STRICT JSON in this format:
      {
        "tasks": [
          {
            "job": "...",
            "process": "...",
            "machine": "...",
            "workers": 3,
            "start": "HH:MM",
            "end": "HH:MM"
          }
        ]
      }
    """

    USER_PROMPT = f"""
    Use this data to generate today's optimized plan. Return ONLY JSON.
    {json.dumps(payload)}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)
        return data.get("tasks", []), None

    except Exception as e:
        return None, str(e)


# ============================================================
# SMART MANUAL SCHEDULER (Your Old Logic)
# ============================================================
def smart_batch_schedule(jobs, done_map):
    start_dt = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    today = date.today()
    tasks = []

    for j_idx, job in enumerate(jobs):
        due = datetime.strptime(job["due"], "%Y-%m-%d").date()

        for p_idx, p in enumerate(job["processes"]):
            tid = f"{j_idx}_{p_idx}"
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
                "machine": p["machine"],
            })

    if not tasks:
        return []

    tasks.sort(key=lambda x: x["due"])
    timeline = []
    cur_time = start_dt
    used = set()

    for i, base in enumerate(tasks):

        if base["task_id"] in used:
            continue

        # Base scheduling
        start = cur_time
        end = start + timedelta(hours=base["hours"])
        if start < lunch_start < end:
            end += (lunch_end - lunch_start)

        # Due Status
        if base["due"] < today:
            due_status = "OVERDUE"
        elif base["due"] <= today + timedelta(days=1):
            due_status = "NEAR DUE"
        else:
            due_status = "OK"

        timeline.append({
            "task_id": base["task_id"],
            "Job": base["job"],
            "Due Date": base["due_str"],
            "Due Status": due_status,
            "Process": base["process"],
            "Machine": base["machine"],
            "Workers": base["workers"],
            "Hours": base["hours"],
            "Start": start.strftime("%H:%M"),
            "End": end.strftime("%H:%M"),
        })

        used.add(base["task_id"])
        cur_time = end

        # Batch Same Process
        for j in range(i + 1, len(tasks)):
            t = tasks[j]
            if t["task_id"] in used:
                continue
            if t["process"].lower() != base["process"].lower():
                continue
            if abs((t["due"] - base["due"]).days) > 2:
                continue

            start2 = cur_time
            end2 = start2 + timedelta(hours=t["hours"])
            if start2 < lunch_start < end2:
                end2 += (lunch_end - lunch_start)

            if t["due"] < today:
                due_status2 = "OVERDUE"
            elif t["due"] <= today + timedelta(days=1):
                due_status2 = "NEAR DUE"
            else:
                due_status2 = "OK"

            timeline.append({
                "task_id": t["task_id"],
                "Job": t["job"],
                "Due Date": t["due_str"],
                "Due Status": due_status2,
                "Process": t["process"],
                "Machine": t["machine"],
                "Workers": t["workers"],
                "Hours": t["hours"],
                "Start": start2.strftime("%H:%M"),
                "End": end2.strftime("%H:%M"),
            })

            used.add(t["task_id"])
            cur_time = end2

    return timeline


# ============================================================
# INVENTORY PAGE
# ============================================================
def inventory_page():
    st.title("📦 Inventory")

    with st.expander("Add Category"):
        cat = st.text_input("Category Name")
        if st.button("Add Category"):
            if cat.strip() and cat not in st.session_state.categories:
                st.session_state.categories.append(cat)

    st.subheader("Add Item")
    name = st.text_input("Item Name")
    cat = st.selectbox("Category", ["None"] + st.session_state.categories)
    qty = st.number_input("Quantity", min_value=0, value=1)
    size = st.text_input("Size")
    weight = st.number_input("Weight (kg)", min_value=0.0)

    if st.button("Add Item"):
        st.session_state.inventory.append({
            "name": name,
            "category": cat if cat != "None" else "",
            "quantity": qty,
            "size": size,
            "weight": weight,
        })

    st.subheader("Inventory List")
    for idx, item in enumerate(st.session_state.inventory):
        col1, col2, col3, col4, col5 = st.columns([2,2,2,2,1])
        col1.write(item["name"])
        col2.write(item["category"])
        col3.write(f"Qty: {item['quantity']}")
        col4.write(f"Size: {item['size']}")
        if col5.button("❌", key=f"del{idx}"):
            st.session_state.inventory.pop(idx)
            st.experimental_rerun()


# ============================================================
# JOBS PAGE
# ============================================================
def jobs_page():
    st.title("📝 Jobs")

    name = st.text_input("Job Name")
    due = st.date_input("Due Date")
    n = st.slider("Number of Processes", 1, 20, 1)

    processes = []

    for i in range(n):
        st.markdown(f"### Process {i+1}")

        pname = st.text_input(f"Process name {i+1}", key=f"pn{i}")
        hrs = st.number_input(f"Hours", min_value=0.5, value=1.0, key=f"ph{i}")
        workers = st.number_input(f"Workers", min_value=1, value=1, key=f"pw{i}")
        machine = st.text_input(f"Machine", key=f"pm{i}")

        cat = st.selectbox(f"Category", ["None"] + st.session_state.categories, key=f"pc{i}")

        inv_item = None
        size = None

        if cat != "None":
            items = ["None"] + [inv["name"] for inv in st.session_state.inventory if inv["category"] == cat]
            inv_sel = st.selectbox("Inventory Item", items, key=f"pit{i}")
            if inv_sel != "None": inv_item = inv_sel

            sizes = ["None"] + [inv["size"] for inv in st.session_state.inventory if inv["category"] == cat]
            size_sel = st.selectbox("Size", sizes, key=f"psz{i}")
            if size_sel != "None": size = size_sel

        processes.append({
            "name": pname,
            "hours": float(hrs),
            "workers": int(workers),
            "machine": machine,
            "category": cat if cat != "None" else None,
            "item": inv_item,
            "size": size,
        })

        st.write("---")

    if st.button("Save Job"):
        st.session_state.jobs.append({
            "job": name,
            "due": due.isoformat(),
            "processes": processes
        })
        st.success("Job Saved")
        st.session_state.task_done = {}  # Reset


# ============================================================
# PLANNER PAGE
# ============================================================
def planner_page():
    st.title("🧠 AI Planner")

    if not st.session_state.jobs:
        st.info("No jobs yet.")
        return

    st.subheader("🔮 Generate AI Plan (ChatGPT)")

    if st.button("Ask AI to Plan My Day"):
        tasks, error = call_ai_planner(
            st.session_state.jobs,
            st.session_state.inventory,
            st.session_state.staff_count,
            st.session_state.work_hours,
        )

        if error:
            st.error(error)
        else:
            st.success("AI Plan Generated!")
            df = pd.DataFrame(tasks)
            st.dataframe(df, use_container_width=True)

    st.markdown("---")

    st.subheader("⚙ Manual Smart Planner (No AI, your old logic)")

    sched = smart_batch_schedule(st.session_state.jobs, st.session_state.task_done)

    if not sched:
        st.success("All processes done.")
        return

    df = pd.DataFrame(sched)
    st.dataframe(df, use_container_width=True)

    st.subheader("Mark Done:")

    for row in sched:
        tid = row["task_id"]
        col1, col2 = st.columns([3,1])
        col1.write(f"{row['Job']} | {row['Process']} | {row['Start']}-{row['End']}")
        done = st.checkbox("Done", value=st.session_state.task_done.get(tid, False), key=f"done{tid}")
        st.session_state.task_done[tid] = done


# ============================================================
# STAFF SETTINGS
# ============================================================
def staff_page():
    st.title("👷 Staff Settings")

    st.session_state.staff_count = st.number_input("Total Staff", min_value=1, value=st.session_state.staff_count)
    st.session_state.work_hours = st.number_input("Work Hours", min_value=1, value=st.session_state.work_hours)

    st.success("Saved!")


# ============================================================
# ROUTER
# ============================================================
page = st.sidebar.radio("Pages", ["Inventory", "Jobs", "Planner", "Staff"])

if page == "Inventory":
    inventory_page()
elif page == "Jobs":
    jobs_page()
elif page == "Planner":
    planner_page()
elif page == "Staff":
    staff_page()
