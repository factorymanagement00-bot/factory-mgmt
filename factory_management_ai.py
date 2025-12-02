import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Factory Management AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# DARK PREMIUM UI
# ============================================================
st.markdown("""
<style>
body, .stApp { background-color: #0d0f16 !important; color: white !important; }

h1, h2, h3, h4 {
    color: #b27cff !important;
    font-weight: 600;
}

.stButton>button {
    background: linear-gradient(90deg,#7928ca,#ff0080);
    color: white; border: none;
    padding: 10px 22px; border-radius: 8px;
}

.dataframe td, .dataframe th {
    color: white !important;
    background-color: #1a1d29 !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE SETUP
# ============================================================
if "inventory" not in st.session_state: st.session_state.inventory = []
if "categories" not in st.session_state: st.session_state.categories = []
if "jobs" not in st.session_state: st.session_state.jobs = []
if "task_done" not in st.session_state: st.session_state.task_done = {}
if "staff_count" not in st.session_state: st.session_state.staff_count = 5
if "work_hours" not in st.session_state: st.session_state.work_hours = 8


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
st.sidebar.title("⚙️ Factory Management AI")
page = st.sidebar.radio("Navigate", ["Inventory", "Jobs", "Planner", "Staff Settings"])


# ============================================================
# INVENTORY PAGE
# ============================================================
if page == "Inventory":

    st.title("📦 Inventory Management")

    # Add Category
    st.subheader("➕ Add Category")
    new_cat = st.text_input("New Category Name")

    if st.button("Add Category"):
        if new_cat.strip() and new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.success("Category added!")
        else:
            st.warning("Invalid or duplicate category")

    st.markdown("---")

    # Add Inventory Item
    st.subheader("➕ Add Inventory Item")
    name = st.text_input("Item Name")
    cat = st.selectbox("Category", ["None"] + st.session_state.categories)
    col1, col2 = st.columns(2)
    with col1:
        qty = st.number_input("Quantity", min_value=0, value=1)
    with col2:
        weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)

    size = st.text_input("Size")

    if st.button("Add Item"):
        st.session_state.inventory.append({
            "name": name,
            "category": cat if cat != "None" else "",
            "quantity": qty,
            "weight": weight,
            "size": size
        })
        st.success("Item Added!")

    st.markdown("---")
    st.subheader("📋 Inventory List")

    for i, item in enumerate(st.session_state.inventory):
        colA, colB, colC, colD, colDel = st.columns([2,2,2,2,1])
        colA.write(f"**{item['name']}**")
        colB.write(item["category"] or "—")
        colC.write(f"Qty: {item['quantity']}")
        colD.write(f"Size: {item['size']}")
        if colDel.button("🗑️", key=f"del_{i}"):
            st.session_state.inventory.pop(i)
            st.experimental_rerun()


# ============================================================
# JOBS PAGE
# ============================================================
elif page == "Jobs":

    st.title("📝 Jobs")

    job_name = st.text_input("Job Name")
    due_date = st.date_input("Due Date")

    num_proc = st.slider("Number of Processes", 1, 20, 1)

    processes = []
    st.markdown("---")

    for i in range(num_proc):
        st.subheader(f"Process {i+1}")

        pname = st.text_input(f"Process Name {i+1}", key=f"pname{i}")
        hours = st.number_input(f"Hours", min_value=0.5, value=1.0, step=0.5, key=f"phours{i}")
        workers = st.number_input(f"Workers", min_value=1, value=1, key=f"pworkers{i}")
        machine = st.text_input(f"Machine (optional)", key=f"pmachine{i}")

        cat = st.selectbox(f"Category (optional)", ["None"] + st.session_state.categories, key=f"pcat{i}")

        item = None
        size = None

        if cat != "None":
            items = ["None"] + [inv["name"] for inv in st.session_state.inventory if inv["category"] == cat]
            item = st.selectbox(f"Inventory Item", items, key=f"pitem{i}")
            if item == "None": item = None

            sizes = ["None"] + [inv["size"] for inv in st.session_state.inventory if inv["category"] == cat]
            size = st.selectbox(f"Size", sizes, key=f"psize{i}")
            if size == "None": size = None

        processes.append({
            "name": pname,
            "hours": float(hours),
            "workers": int(workers),
            "machine": machine,
            "category": cat if cat != "None" else None,
            "item": item,
            "size": size
        })

        st.markdown("---")

    if st.button("Save Job"):
        st.session_state.jobs.append({
            "job": job_name,
            "due": str(due_date),
            "processes": processes
        })
        st.success("Job Saved!")


# ============================================================
# SMART BATCHING PLANNER ENGINE
# ============================================================
def smart_batch_schedule(jobs, done_map):

    start = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    today = date.today()

    # flatten tasks
    tasks = []
    for j_idx, job in enumerate(jobs):
        due = datetime.strptime(job["due"], "%Y-%m-%d").date()

        for p_idx, p in enumerate(job["processes"]):
            t_id = f"{j_idx}_{p_idx}"
            if done_map.get(t_id, False):
                continue  # skip done tasks

            tasks.append({
                "task_id": t_id,
                "job": job["job"],
                "due": due,
                "due_str": job["due"],
                "name": p["name"],
                "hours": p["hours"],
                "workers": p["workers"],
                "machine": p["machine"]
            })

    # sort by due date first
    tasks.sort(key=lambda x: x["due"])

    timeline = []
    cur = start

    used = set()

    for i, t in enumerate(tasks):
        if t["task_id"] in used:
            continue

        # schedule this task
        hrs = t["hours"]
        start_t = cur
        end_t = cur + timedelta(hours=hrs)

        if start_t < lunch_start < end_t:
            end_t += (lunch_end - lunch_start)

        # due status
        if t["due"] < today:
            due_status = "OVERDUE"
        elif t["due"] <= today + timedelta(days=1):
            due_status = "NEAR DUE"
        else:
            due_status = "OK"

        timeline.append({
            "task_id": t["task_id"],
            "Job": t["job"],
            "Due Date": t["due_str"],
            "Due Status": due_status,
            "Process": t["name"],
            "Machine": t["machine"],
            "Workers": t["workers"],
            "Hours": t["hours"],
            "Start": start_t.strftime("%I:%M %p"),
            "End": end_t.strftime("%I:%M %p"),
            "Status": "SCHEDULED"
        })

        used.add(t["task_id"])
        cur = end_t

        # BATCH SAME PROCESS NAME FOR NEAR-DUE JOBS
        for j in range(i+1, len(tasks)):
            x = tasks[j]

            if x["task_id"] in used:
                continue

            # same process name?
            if x["name"].strip().lower() != t["name"].strip().lower():
                continue

            # due dates close?
            if abs((x["due"] - t["due"]).days) > 2:
                continue

            hrs2 = x["hours"]
            start2 = cur
            end2 = start2 + timedelta(hours=hrs2)

            if start2 < lunch_start < end2:
                end2 += (lunch_end - lunch_start)

            if x["due"] < today:
                due_status2 = "OVERDUE"
            elif x["due"] <= today + timedelta(days=1):
                due_status2 = "NEAR DUE"
            else:
                due_status2 = "OK"

            timeline.append({
                "task_id": x["task_id"],
                "Job": x["job"],
                "Due Date": x["due_str"],
                "Due Status": due_status2,
                "Process": x["name"],
                "Machine": x["machine"],
                "Workers": x["workers"],
                "Hours": x["hours"],
                "Start": start2.strftime("%I:%M %p"),
                "End": end2.strftime("%I:%M %p"),
                "Status": "SCHEDULED"
            })

            used.add(x["task_id"])
            cur = end2

    return timeline


# ============================================================
# PLANNER PAGE
# ============================================================
elif page == "Planner":

    st.title("🧠 AI Smart Planner (Batching + Done/Remaining)")

    if len(st.session_state.jobs) == 0:
        st.info("No jobs yet.")
        st.stop()

    # Build schedule
    schedule = smart_batch_schedule(st.session_state.jobs, st.session_state.task_done)

    if not schedule:
        st.success("🎉 All processes completed!")
        st.stop()

    df = pd.DataFrame(schedule)

    st.subheader("📅 Today's Schedule")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("✔ Mark Processes as Done")

    for row in schedule:
        tid = row["task_id"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(
                f"**{row['Job']}** | {row['Process']} | "
                f"{row['Start']} - {row['End']} | Due: {row['Due Date']} ({row['Due Status']})"
            )
        with col2:
            done_now = st.checkbox("Done", value=st.session_state.task_done.get(tid, False), key=f"chk{tid}")
            st.session_state.task_done[tid] = done_now

    st.info("Refresh the page after marking Done to rebuild the plan.")


# ============================================================
# STAFF SETTINGS PAGE
# ============================================================
elif page == "Staff Settings":

    st.title("👷 Staff Settings")

    st.session_state.staff_count = st.number_input("Total Staff", min_value=1, value=st.session_state.staff_count)
    st.session_state.work_hours = st.number_input("Work Hours per Day", min_value=1, value=st.session_state.work_hours)

    st.success("Settings updated!")
