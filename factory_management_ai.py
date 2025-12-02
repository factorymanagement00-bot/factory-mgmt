import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Factory Management AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# SESSION STATE
# ============================================================
if "inventory" not in st.session_state:
    st.session_state.inventory = []  # list of dicts

if "categories" not in st.session_state:
    st.session_state.categories = []  # list of strings

if "jobs" not in st.session_state:
    st.session_state.jobs = []  # list of jobs

if "task_done" not in st.session_state:
    # key: "jobIndex_processIndex" -> bool
    st.session_state.task_done = {}

if "staff_count" not in st.session_state:
    st.session_state.staff_count = 5

if "work_hours" not in st.session_state:
    st.session_state.work_hours = 8


# ============================================================
# SMART BATCH SCHEDULER
# ============================================================
def smart_batch_schedule(jobs, done_map):
    """
    Build a schedule that:
    - sorts jobs by due date
    - batches same process names for close-due jobs (within 2 days)
    - skips processes marked as done in done_map
    """

    # base time settings (no strict end limit)
    start_dt = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    today = date.today()

    # Step 1: flatten all remaining tasks
    tasks = []
    for j_idx, job in enumerate(jobs):
        # due stored as ISO string: "YYYY-MM-DD"
        try:
            due_date = datetime.strptime(job["due"], "%Y-%m-%d").date()
        except Exception:
            # if somehow stored as date already
            if isinstance(job["due"], date):
                due_date = job["due"]
            else:
                due_date = today

        for p_idx, p in enumerate(job["processes"]):
            task_id = f"{j_idx}_{p_idx}"
            if done_map.get(task_id, False):
                continue  # skip done processes

            tasks.append({
                "task_id": task_id,
                "job": job["job"],
                "due": due_date,
                "due_str": job["due"],
                "process": p["name"],
                "hours": float(p["hours"]),
                "workers": int(p["workers"]),
                "machine": p.get("machine", ""),
            })

    # If no remaining tasks, return empty schedule
    if not tasks:
        return []

    # Step 2: sort by due date first
    tasks.sort(key=lambda t: t["due"])

    timeline = []
    current_time = start_dt
    used_ids = set()

    for i, base in enumerate(tasks):
        if base["task_id"] in used_ids:
            continue

        # 2a. schedule the base task
        start = current_time
        end = start + timedelta(hours=base["hours"])

        # handle lunch break
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
            "Start": start.strftime("%I:%M %p"),
            "End": end.strftime("%I:%M %p"),
            "Status": "SCHEDULED",
        })

        used_ids.add(base["task_id"])
        current_time = end

        # 2b. batch other tasks with same process name & close due date
        base_name = base["process"].strip().lower()
        base_due = base["due"]

        for j in range(i + 1, len(tasks)):
            t = tasks[j]
            if t["task_id"] in used_ids:
                continue

            # same process name?
            if t["process"].strip().lower() != base_name:
                continue

            # due date close enough? (<= 2 days difference)
            if abs((t["due"] - base_due).days) > 2:
                continue

            start2 = current_time
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
                "Start": start2.strftime("%I:%M %p"),
                "End": end2.strftime("%I:%M %p"),
                "Status": "SCHEDULED",
            })

            used_ids.add(t["task_id"])
            current_time = end2

    return timeline


# ============================================================
# INVENTORY PAGE
# ============================================================
def page_inventory():
    st.header("📦 Inventory")

    # --- Add Category ---
    with st.expander("➕ Add Category"):
        new_cat = st.text_input("New category name")
        if st.button("Add Category"):
            if new_cat.strip() and new_cat not in st.session_state.categories:
                st.session_state.categories.append(new_cat.strip())
                st.success("Category added.")
            else:
                st.warning("Category is empty or already exists.")

    st.markdown("---")

    # --- Add Inventory Item ---
    st.subheader("Add Inventory Item")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Item name")
        category = st.selectbox("Category", ["None"] + st.session_state.categories)
    with col2:
        quantity = st.number_input("Quantity", min_value=0, value=1)
        weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)

    size = st.text_input("Size (e.g. 32 or 50x70cm)")

    if st.button("Add Item"):
        if not name.strip():
            st.warning("Item name is required.")
        else:
            st.session_state.inventory.append({
                "name": name.strip(),
                "category": category if category != "None" else "",
                "quantity": quantity,
                "weight": weight,
                "size": size,
            })
            st.success("Item added.")

    st.markdown("---")
    st.subheader("Current Inventory")

    if not st.session_state.inventory:
        st.info("No inventory items yet.")
    else:
        for idx, item in enumerate(st.session_state.inventory):
            colA, colB, colC, colD, colDel = st.columns([2, 2, 2, 2, 1])
            colA.write(f"**{item['name']}**")
            colB.write(item["category"] or "—")
            colC.write(f"Qty: {item['quantity']}")
            colD.write(f"Size: {item['size']}")
            if colDel.button("Delete", key=f"del_inv_{idx}"):
                st.session_state.inventory.pop(idx)
                st.experimental_rerun()


# ============================================================
# JOBS PAGE
# ============================================================
def page_jobs():
    st.header("🧾 Jobs & Processes")

    job_name = st.text_input("Job Name")
    due_date = st.date_input("Due Date")

    num_proc = st.slider("Number of processes", 1, 20, 1)

    processes = []

    for i in range(num_proc):
        st.markdown(f"### Process {i + 1}")

        pname = st.text_input(f"Process name {i+1}", key=f"pname_{i}")
        hours = st.number_input(f"Hours for process {i+1}", min_value=0.5, step=0.5, value=1.0, key=f"phours_{i}")
        workers = st.number_input(f"Workers for process {i+1}", min_value=1, value=1, key=f"pworkers_{i}")
        machine = st.text_input(f"Machine (optional) {i+1}", key=f"pmachine_{i}")

        category = st.selectbox(f"Category (optional) {i+1}", ["None"] + st.session_state.categories, key=f"pcat_{i}")

        item = None
        size = None

        if category != "None":
            # filter inventory items for category
            items = ["None"] + [inv["name"] for inv in st.session_state.inventory if inv["category"] == category]
            item_sel = st.selectbox(f"Inventory item (optional) {i+1}", items, key=f"pitem_{i}")
            if item_sel != "None":
                item = item_sel

            sizes = ["None"] + [inv["size"] for inv in st.session_state.inventory if inv["category"] == category]
            size_sel = st.selectbox(f"Size (optional) {i+1}", sizes, key=f"psize_{i}")
            if size_sel != "None":
                size = size_sel

        processes.append({
            "name": pname,
            "hours": hours,
            "workers": workers,
            "machine": machine,
            "category": category if category != "None" else None,
            "item": item,
            "size": size,
        })

        st.markdown("---")

    if st.button("Save Job"):
        if not job_name.strip():
            st.warning("Job name is required.")
        else:
            st.session_state.jobs.append({
                "job": job_name.strip(),
                "due": due_date.isoformat(),
                "processes": processes,
            })
            st.success("Job saved.")
            # reset done state because job list changed
            st.session_state.task_done = {}

    st.markdown("## Existing Jobs")
    if not st.session_state.jobs:
        st.info("No jobs yet.")
    else:
        for j_idx, job in enumerate(st.session_state.jobs):
            with st.expander(f"{job['job']} (Due {job['due']})"):
                for p in job["processes"]:
                    st.write(f"- {p['name']} — {p['hours']} hrs, workers: {p['workers']}, machine: {p['machine'] or '—'}")


# ============================================================
# PLANNER PAGE
# ============================================================
def page_planner():
    st.header("🧠 AI Smart Planner")

    if not st.session_state.jobs:
        st.info("No jobs to plan yet.")
        return

    # build schedule from remaining (not done) processes
    schedule = smart_batch_schedule(st.session_state.jobs, st.session_state.task_done)

    if not schedule:
        st.success("✅ All processes are marked as done. Nothing left to schedule.")
        return

    df = pd.DataFrame(schedule)

    st.subheader("📅 Planned Schedule (batched by process & due date)")
    st.dataframe(df.drop(columns=["task_id"]), use_container_width=True)

    st.markdown("---")
    st.subheader("✅ Mark processes as Done / Remaining")

    for row in schedule:
        tid = row["task_id"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(
                f"**{row['Job']}** | {row['Process']} | "
                f"{row['Start']}–{row['End']} | Due: {row['Due Date']} ({row['Due Status']})"
            )
        with col2:
            checked = st.checkbox(
                "Done",
                value=st.session_state.task_done.get(tid, False),
                key=f"done_{tid}",
            )
            st.session_state.task_done[tid] = checked

    st.info("When you refresh or reopen this page, processes marked as Done will be skipped and only remaining ones will be scheduled.")


# ============================================================
# STAFF SETTINGS PAGE
# ============================================================
def page_staff():
    st.header("👷 Staff Settings")

    st.session_state.staff_count = st.number_input(
        "Total staff (not yet used in scheduling logic, but stored)",
        min_value=1,
        value=st.session_state.staff_count,
    )
    st.session_state.work_hours = st.number_input(
        "Work hours per day (not yet used in scheduling logic, but stored)",
        min_value=1,
        value=st.session_state.work_hours,
    )

    st.success("Staff settings saved.")


# ============================================================
# MAIN ROUTER
# ============================================================
def main():
    page_choice = st.sidebar.radio(
        "Pages",
        ["Inventory", "Jobs", "Planner", "Staff"],
        index=0
    )

    if page_choice == "Inventory":
        page_inventory()
    elif page_choice == "Jobs":
        page_jobs()
    elif page_choice == "Planner":
        page_planner()
    elif page_choice == "Staff":
        page_staff()


if __name__ == "__main__":
    main()
