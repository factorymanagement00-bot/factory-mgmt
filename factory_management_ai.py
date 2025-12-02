import os
import json
from datetime import datetime, timedelta, date

import streamlit as st
import pandas as pd
from openai import OpenAI

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="Factory Management AI", layout="wide")

# ============================================================
# OPENAI CLIENT (USING st.secrets)
# ============================================================
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", None)
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# ============================================================
# FIREBASE INIT (USING st.secrets["firebase"])
# ============================================================
db = None
firebase_config = st.secrets.get("firebase", None)

if firebase_config:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        st.error(f"Firebase init error: {e}")
        db = None
else:
    st.warning("⚠ No Firebase config found in st.secrets['firebase']. Data will not be saved permanently.")

# ============================================================
# SESSION STATE INIT (USED AS CACHE ONLY)
# ============================================================
if "inventory" not in st.session_state:
    st.session_state.inventory = []  # list[dict]

if "categories" not in st.session_state:
    st.session_state.categories = []  # list[str]

if "jobs" not in st.session_state:
    st.session_state.jobs = []  # list[dict]

if "task_done" not in st.session_state:
    # key: "jobId_processIndex" -> bool
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
    for doc in db.collection("categories").stream():
        data = doc.to_dict()
        name = data.get("name")
        if name:
            names.add(name)
    return sorted(list(names))


def add_category_to_db(name: str):
    if db is None:
        return
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
    if db is None:
        return
    db.collection("inventory").add(item)


def delete_inventory_item_from_db(doc_id: str):
    if db is None:
        return
    db.collection("inventory").document(doc_id).delete()


def get_jobs_from_db():
    if db is None:
        return st.session_state.get("jobs", [])
    jobs = []
    for doc in db.collection("jobs").stream():
        data = doc.to_dict()
        data["id"] = doc.id
        jobs.append(data)
    return jobs


def add_job_to_db(job_doc: dict):
    if db is None:
        return
    db.collection("jobs").add(job_doc)


def get_task_done_map_from_db():
    if db is None:
        return st.session_state.get("task_done", {})
    done_map = {}
    for doc in db.collection("task_done").stream():
        data = doc.to_dict()
        done_map[doc.id] = bool(data.get("done", False))
    return done_map


def set_task_done_in_db(task_id: str, done: bool):
    if db is None:
        return
    db.collection("task_done").document(task_id).set({"done": done})


def load_settings_from_db():
    staff = st.session_state.staff_count
    hours = st.session_state.work_hours
    if db is None:
        return staff, hours

    doc = db.collection("settings").document("factory").get()
    if doc.exists:
        data = doc.to_dict()
        staff = int(data.get("staff_count", staff))
        hours = int(data.get("work_hours", hours))
    return staff, hours


def save_settings_to_db(staff_count: int, work_hours: int):
    if db is None:
        return
    db.collection("settings").document("factory").set(
        {
            "staff_count": staff_count,
            "work_hours": work_hours,
        },
        merge=True,
    )


# ============================================================
# AI PLANNER (GPT)
# ============================================================
def call_ai_planner(jobs, inventory, staff_count, work_hours):
    """
    Sends jobs + inventory to GPT and asks it to return a JSON schedule.
    Returns (tasks, error_message)
    """
    if client is None:
        return None, "No OPENAI_API_KEY configured in Streamlit secrets."

    payload = {
        "jobs": jobs,
        "inventory": inventory,
        "staff_count": staff_count,
        "work_hours": work_hours,
    }

    system_msg = """
You are an AI factory scheduler for a cardboard box manufacturing plant.

Rules:
- Prioritize jobs with earlier due dates.
- Try to batch the same processes or same machine operations together
  (e.g. conversion, lamination) to save machine setup time & electricity.
- Workday: 09:00–17:00 with lunch break 13:00–14:00.
- Do not invent new jobs or processes; only use given data.
- Respect total work hours; do not schedule beyond 17:00.
- If material seems clearly impossible (e.g. no inventory), you can skip that job.

Output:
Return ONLY valid JSON, with this structure:
{
  "tasks": [
    {
      "job": "Tiger",
      "process": "conversion",
      "machine": "lamination line 1",
      "workers": 3,
      "start": "09:00",
      "end": "10:30",
      "note": "optional explanation"
    }
  ]
}
    """

    user_msg = (
        "Here is the factory data for today as JSON. "
        "Generate a schedule for TODAY only. "
        "Return ONLY JSON in the format described.\n\n"
        + json.dumps(payload)
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        return data.get("tasks", []), None
    except Exception as e:
        return None, f"AI Planner error: {e}"


# ============================================================
# SIMPLE RULE-BASED SMART PLANNER (NO AI)
# ============================================================
def smart_batch_schedule(jobs, done_map):
    """
    Local smart planner:
    - Sorts jobs by due date
    - Batches same process names for close-due jobs
    - Handles lunch break
    - Skips processes marked done
    Uses stable task_id: "<job_id>_<process_index>"
    """
    start_dt = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    today = date.today()
    tasks = []

    # Flatten job processes
    for idx, job in enumerate(jobs):
        job_id = job.get("id", str(idx))
        try:
            due = datetime.strptime(job["due"], "%Y-%m-%d").date()
        except Exception:
            if isinstance(job["due"], date):
                due = job["due"]
            else:
                due = today

        for p_idx, p in enumerate(job["processes"]):
            tid = f"{job_id}_{p_idx}"
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
                "machine": p.get("machine", ""),
            })

    if not tasks:
        return []

    # Sort by due date
    tasks.sort(key=lambda t: t["due"])

    timeline = []
    current = start_dt
    used = set()

    for i, base in enumerate(tasks):
        if base["task_id"] in used:
            continue

        # schedule base
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
        current = end

        # batch same process w/ close due date
        for j in range(i + 1, len(tasks)):
            t = tasks[j]
            if t["task_id"] in used:
                continue
            if t["process"].strip().lower() != base["process"].strip().lower():
                continue
            if abs((t["due"] - base["due"]).days) > 2:
                continue

            start2 = current
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
            current = end2

    return timeline


# ============================================================
# INVENTORY PAGE
# ============================================================
def inventory_page():
    st.title("📦 Inventory")

    # sync with Firestore
    st.session_state.categories = get_categories_from_db()
    st.session_state.inventory = get_inventory_from_db()

    with st.expander("Add Category"):
        new_cat = st.text_input("Category name")
        if st.button("Save Category"):
            if new_cat.strip() and new_cat.strip() not in st.session_state.categories:
                add_category_to_db(new_cat.strip())
                st.session_state.categories.append(new_cat.strip())
                st.success("Category added.")
                st.experimental_rerun()
            else:
                st.warning("Invalid or duplicate category.")

    st.subheader("Add Inventory Item")
    name = st.text_input("Item name")
    cat = st.selectbox("Category", ["None"] + st.session_state.categories)
    qty = st.number_input("Quantity", min_value=0, value=1)
    size = st.text_input("Size (e.g. 32 or 50x70)")
    weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)

    if st.button("Add Item"):
        if not name.strip():
            st.warning("Item name required.")
        else:
            item = {
                "name": name.strip(),
                "category": cat if cat != "None" else "",
                "quantity": qty,
                "size": size,
                "weight": weight,
            }
            add_inventory_item_to_db(item)
            st.success("Item added.")
            st.experimental_rerun()

    st.markdown("---")
    st.subheader("Inventory List")

    if not st.session_state.inventory:
        st.info("No items yet.")
    else:
        for i, item in enumerate(st.session_state.inventory):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            col1.write(f"**{item.get('name', '')}**")
            col2.write(item.get("category") or "—")
            col3.write(f"Qty: {item.get('quantity', 0)}")
            col4.write(f"Size: {item.get('size', '')}")
            if col5.button("🗑️", key=f"inv_del_{item.get('id', i)}"):
                if "id" in item:
                    delete_inventory_item_from_db(item["id"])
                st.experimental_rerun()


# ============================================================
# JOBS PAGE
# ============================================================
def jobs_page():
    st.title("🧾 Jobs")

    # sync from Firestore
    st.session_state.categories = get_categories_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.jobs = get_jobs_from_db()

    job_name = st.text_input("Job name")
    due_date = st.date_input("Due date")

    num_proc = st.slider("Number of processes", 1, 20, 1)
    processes = []

    for i in range(num_proc):
        st.markdown(f"### Process {i+1}")

        pname = st.text_input(f"Process name {i+1}", key=f"pname_{i}")
        hours = st.number_input(
            f"Hours for process {i+1}",
            min_value=0.5,
            step=0.5,
            value=1.0,
            key=f"phours_{i}",
        )
        workers = st.number_input(
            f"Workers for process {i+1}",
            min_value=1,
            value=1,
            key=f"pworkers_{i}",
        )
        machine = st.text_input(f"Machine (optional) {i+1}", key=f"pmachine_{i}")

        cat = st.selectbox(
            f"Category (optional) {i+1}",
            ["None"] + st.session_state.categories,
            key=f"pcat_{i}",
        )

        item = None
        size = None
        if cat != "None":
            inv_for_cat = [
                inv for inv in st.session_state.inventory
                if inv.get("category") == cat
            ]
            items = ["None"] + [inv["name"] for inv in inv_for_cat]
            item_sel = st.selectbox(
                f"Inventory item {i+1}",
                items,
                key=f"pitem_{i}",
            )
            if item_sel != "None":
                item = item_sel

            sizes = ["None"] + [str(inv.get("size", "")) for inv in inv_for_cat]
            size_sel = st.selectbox(
                f"Size {i+1}",
                sizes,
                key=f"psize_{i}",
            )
            if size_sel != "None":
                size = size_sel

        processes.append({
            "name": pname,
            "hours": hours,
            "workers": workers,
            "machine": machine,
            "category": cat if cat != "None" else None,
            "item": item,
            "size": size,
        })

        st.markdown("---")

    if st.button("Save Job"):
        if not job_name.strip():
            st.warning("Job name required.")
        else:
            job_doc = {
                "job": job_name.strip(),
                "due": due_date.isoformat(),
                "processes": processes,
            }
            add_job_to_db(job_doc)
            st.session_state.task_done = {}  # reset cache
            st.success("Job saved.")
            st.experimental_rerun()

    st.markdown("## Existing Jobs")
    if not st.session_state.jobs:
        st.info("No jobs saved yet.")
    else:
        for job in st.session_state.jobs:
            with st.expander(f"{job['job']} (Due {job['due']})"):
                for p in job["processes"]:
                    st.write(
                        f"- {p['name']} — {p['hours']} hrs, "
                        f"workers: {p['workers']}, machine: {p.get('machine') or '—'}"
                    )


# ============================================================
# PLANNER PAGE
# ============================================================
def planner_page():
    st.title("🧠 Planner")

    # sync latest data from Firestore
    st.session_state.jobs = get_jobs_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.task_done = get_task_done_map_from_db()
    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    if not st.session_state.jobs:
        st.info("No jobs to plan yet.")
        return

    # ---------- AI Planner Section ----------
    st.subheader("🤖 AI Planner (ChatGPT)")

    if st.button("Ask AI to create today's plan"):
        tasks, err = call_ai_planner(
            st.session_state.jobs,
            st.session_state.inventory,
            st.session_state.staff_count,
            st.session_state.work_hours,
        )
        if err:
            st.error(err)
        else:
            if not tasks:
                st.warning("AI returned an empty plan.")
            else:
                df_ai = pd.DataFrame(tasks)
                st.success("AI plan generated.")
                st.dataframe(df_ai, use_container_width=True)

    st.markdown("---")

    # ---------- Local Smart Planner ----------
    st.subheader("⚙ Local Smart Planner (batching)")

    schedule = smart_batch_schedule(st.session_state.jobs, st.session_state.task_done)

    if not schedule:
        st.success("All processes are marked as done.")
        return

    df = pd.DataFrame(schedule)
    st.dataframe(df.drop(columns=["task_id"]), use_container_width=True)

    st.markdown("### ✅ Mark processes as Done / Remaining")

    for row in schedule:
        tid = row["task_id"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(
                f"**{row['Job']}** | {row['Process']} | "
                f"{row['Start']}-{row['End']} | Due: {row['Due Date']} ({row['Due Status']})"
            )
        with col2:
            done_flag = st.checkbox(
                "Done",
                value=st.session_state.task_done.get(tid, False),
                key=f"done_{tid}",
            )
            st.session_state.task_done[tid] = done_flag
            set_task_done_in_db(tid, done_flag)

    st.info("Refresh / rerun to rebuild schedule using remaining (not done) processes.")


# ============================================================
# AI CHAT PAGE
# ============================================================
def ai_chat_page():
    st.title("💬 Factory AI Chat")

    if client is None:
        st.error("No OPENAI_API_KEY set in Streamlit secrets. Chat is disabled.")
        return

    # make sure context is fresh
    st.session_state.jobs = get_jobs_from_db()
    st.session_state.inventory = get_inventory_from_db()
    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    st.write("Ask anything about your jobs, inventory, planning, etc.")

    user_msg = st.text_area("Your message to the AI", height=120)

    if st.button("Ask AI"):
        if not user_msg.strip():
            st.warning("Type a question first.")
            return

        context = {
            "jobs": st.session_state.jobs,
            "inventory": st.session_state.inventory,
            "staff_count": st.session_state.staff_count,
            "work_hours": st.session_state.work_hours,
        }

        system_msg = """
You are a helpful assistant for a factory management system.
You see the current jobs, inventory and staff info and answer questions clearly.
If user asks for suggestions, give practical planning advice.
Do not invent fake jobs; talk only about the provided data.
"""

        user_full = (
            "FACTORY DATA (JSON):\n"
            + json.dumps(context)
            + "\n\nUSER QUESTION:\n"
            + user_msg
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_full},
                ],
            )
            answer = resp.choices[0].message.content
            st.markdown("### 🤖 AI Answer")
            st.write(answer)
        except Exception as e:
            st.error(f"AI error: {e}")


# ============================================================
# STAFF PAGE
# ============================================================
def staff_page():
    st.title("👷 Staff & Workday Settings")

    st.session_state.staff_count, st.session_state.work_hours = load_settings_from_db()

    staff_count = st.number_input(
        "Total staff (info used by AI planner)",
        min_value=1,
        value=st.session_state.staff_count,
    )
    work_hours = st.number_input(
        "Work hours per staff per day",
        min_value=1,
        value=st.session_state.work_hours,
    )

    if st.button("Save Settings"):
        st.session_state.staff_count = staff_count
        st.session_state.work_hours = work_hours
        save_settings_to_db(staff_count, work_hours)
        st.success("Settings saved.")


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
