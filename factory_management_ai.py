import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Factory Management AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------
# DARK NEON UI CSS
# ----------------------
st.markdown("""
<style>
body, .stApp {
    background-color: #0d0f16 !important;
    color: white !important;
}
h1, h2, h3, h4 { color: #b27cff !important; }
.stButton>button {
    background: linear-gradient(90deg,#7928ca,#ff0080);
    color: white; border: none; padding: 10px 20px;
    border-radius: 10px; font-size: 16px;
}
</style>
""", unsafe_allow_html=True)

# ----------------------
# SESSION STATE
# ----------------------
if "inventory" not in st.session_state: st.session_state.inventory = []
if "categories" not in st.session_state: st.session_state.categories = []
if "jobs" not in st.session_state: st.session_state.jobs = []
if "staff_count" not in st.session_state: st.session_state.staff_count = 5
if "work_hours" not in st.session_state: st.session_state.work_hours = 8

# ----------------------
# SIDEBAR
# ----------------------
st.sidebar.title("⚙️ Factory Management AI")
page = st.sidebar.radio("Navigate", ["Inventory", "Jobs", "Planner", "Staff Settings"])

# ============================================================
#                    INVENTORY PAGE
# ============================================================
if page == "Inventory":

    st.title("📦 Inventory Management")

    st.subheader("➕ Add Category")
    new_category = st.text_input("New Category Name")

    if st.button("Add Category"):
        if new_category.strip() != "" and new_category not in st.session_state.categories:
            st.session_state.categories.append(new_category)
            st.success("Category added!")
        else:
            st.warning("Invalid or duplicate category.")

    st.markdown("---")

    st.subheader("➕ Add Inventory Item")
    col1, col2 = st.columns(2)
    with col1: item_name = st.text_input("Item Name")
    with col2:
        category = st.selectbox("Category", ["None"] + st.session_state.categories)

    col3, col4 = st.columns(2)
    with col3: weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)
    with col4: qty = st.number_input("Quantity", min_value=0, value=1)

    size = st.text_input("Size (e.g. 32, 50x70 cm)")

    if st.button("Add Inventory"):
        if item_name.strip() == "":
            st.warning("Item name required!")
        else:
            st.session_state.inventory.append({
                "name": item_name,
                "category": category if category != "None" else "",
                "weight": weight,
                "quantity": qty,
                "size": size
            })
            st.success("Item added!")

    st.markdown("---")
    st.subheader("📋 Inventory List")

    for i, it in enumerate(st.session_state.inventory):
        colA, colB, colC, colD, colDel = st.columns([2,2,2,2,1])
        colA.write(f"**{it['name']}**")
        colB.write(it["category"] if it["category"] else "—")
        colC.write(f"{it['weight']} kg")
        colD.write(f"Qty: {it['quantity']} | Size: {it['size']}")

        if colDel.button("🗑️", key=f"inv_{i}"):
            st.session_state.inventory.pop(i)
            st.experimental_rerun()

# ============================================================
#                         JOBS PAGE
# ============================================================
elif page == "Jobs":

    st.title("📝 Add Job")

    job_name = st.text_input("Job Name")
    due_date = st.date_input("Due Date")

    num_process = st.slider("Number of Processes", 1, 10, 1)

    processes = []
    st.markdown("---")

    for p in range(num_process):

        st.subheader(f"Process {p+1}")

        pname = st.text_input(f"Process Name {p+1}", key=f"pn{p}")
        hours = st.number_input(f"Hours for Process {p+1}", min_value=0.0, value=1.0, key=f"ph{p}")

        col1, col2 = st.columns(2)
        with col1:
            p_cat = st.selectbox(
                f"Category (optional) {p+1}",
                ["None"] + st.session_state.categories,
                key=f"pcat{p}"
            )
        with col2:
            # Filter items by category
            items = ["None"]
            if p_cat != "None":
                items += [i["name"] for i in st.session_state.inventory if i["category"] == p_cat]
            p_item = st.selectbox(f"Inventory Item {p+1}", items, key=f"pit{p}")

        # Size auto loaded
        size_options = ["None"]
        if p_item != "None":
            for inv in st.session_state.inventory:
                if inv["name"] == p_item:
                    size_options.append(inv["size"])
                    break

        p_size = st.selectbox(f"Size (optional) {p+1}", size_options, key=f"psz{p}")

        machine = st.text_input(f"Machine (optional) {p+1}", key=f"pmac{p}")
        workers = st.number_input(f"Workers for this process {p+1}", min_value=1, value=1, key=f"pwor{p}")

        processes.append({
            "name": pname,
            "hours": hours,
            "category": p_cat,
            "item": p_item,
            "size": p_size,
            "machine": machine,
            "workers": workers
        })

        st.markdown("---")

    if st.button("Save Job"):
        st.session_state.jobs.append({
            "job": job_name,
            "due": str(due_date),
            "processes": processes
        })
        st.success("Job saved successfully!")
def build_smart_schedule(jobs, task_done_state):
    """
    Build a schedule that:
    - sorts jobs by due date
    - batches same process names for close-due jobs
    - skips processes marked as done in task_done_state
    """

    start_time = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    # Build flat list of all remaining processes
    all_tasks = []
    for j_idx, job in enumerate(jobs):
        for p_idx, p in enumerate(job["processes"]):
            task_id = f"{j_idx}_{p_idx}"
            # skip if already marked done
            if task_done_state.get(task_id, False):
                continue

            # parse due date (stored as string "YYYY-MM-DD")
            try:
                due_dt = datetime.strptime(job["due"], "%Y-%m-%d").date()
            except Exception:
                # if stored differently, just ignore parsing
                due_dt = datetime.today().date()

            all_tasks.append({
                "task_id": task_id,
                "job_name": job["job"],
                "due": due_dt,
                "due_str": job["due"],
                "process_name": p["name"],
                "hours": float(p["hours"]),
                "workers": p["workers"],
                "machine": p.get("machine", None),
            })

    # sort by due date first
    all_tasks.sort(key=lambda t: t["due"])

    schedule = []
    cur_time = start_time
    today = datetime.today().date()

    scheduled_ids = set()

    i = 0
    n = len(all_tasks)

    while i < n:
        if all_tasks[i]["task_id"] in scheduled_ids:
            i += 1
            continue

        base = all_tasks[i]
        base_id = base["task_id"]
        base_name = base["process_name"].strip().lower()
        base_due = base["due"]

        # schedule this base process
        hrs = base["hours"]
        start = cur_time

        # handle lunch break
        end = start + timedelta(hours=hrs)
        if start < lunch_start < end:
            end += (lunch_end - lunch_start)

        # due status: for visual info
        if base_due < today:
            due_status = "OVERDUE"
        elif base_due <= today + timedelta(days=1):
            due_status = "NEAR DUE"
        else:
            due_status = "OK"

        schedule.append({
            "task_id": base_id,
            "Job": base["job_name"],
            "Due Date": base["due_str"],
            "Due Status": due_status,
            "Process": base["process_name"],
            "Machine": base["machine"],
            "Workers": base["workers"],
            "Hours": base["hours"],
            "Start": start.strftime("%I:%M %p"),
            "End": end.strftime("%I:%M %p"),
            "Status": "SCHEDULED"
        })

        scheduled_ids.add(base_id)
        cur_time = end

        # now try to batch other tasks with same process name & close due date
        for j in range(i + 1, n):
            t = all_tasks[j]
            if t["task_id"] in scheduled_ids:
                continue

            # same process name?
            if t["process_name"].strip().lower() != base_name:
                continue

            # due date "close" (|Δdays| <= 2, you can tweak)
            if abs((t["due"] - base_due).days) > 2:
                continue

            hrs2 = t["hours"]
            start2 = cur_time
            end2 = start2 + timedelta(hours=hrs2)
            if start2 < lunch_start < end2:
                end2 += (lunch_end - lunch_start)

            if t["due"] < today:
                due_status2 = "OVERDUE"
            elif t["due"] <= today + timedelta(days=1):
                due_status2 = "NEAR DUE"
            else:
                due_status2 = "OK"

            schedule.append({
                "task_id": t["task_id"],
                "Job": t["job_name"],
                "Due Date": t["due_str"],
                "Due Status": due_status2,
                "Process": t["process_name"],
                "Machine": t["machine"],
                "Workers": t["workers"],
                "Hours": t["hours"],
                "Start": start2.strftime("%I:%M %p"),
                "End": end2.strftime("%I:%M %p"),
                "Status": "SCHEDULED"
            })

            scheduled_ids.add(t["task_id"])
            cur_time = end2

        i += 1

    return schedule

# ============================================================
#                        PLANNER PAGE
# ============================================================
elif page == "Planner":

    st.title("📅 AI Daily Planner")

    if len(st.session_state.jobs) == 0:
        st.info("No jobs added yet.")
        st.stop()

    # -----------------------------
    # SORT JOBS BY DUE DATE
    # -----------------------------
    jobs_sorted = sorted(
        st.session_state.jobs,
        key=lambda x: datetime.strptime(x["due"], "%Y-%m-%d")
    )

    start_time = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    schedule = []
    cur_time = start_time
    today = datetime.now().date()

    for job in jobs_sorted:

        job_due = datetime.strptime(job["due"], "%Y-%m-%d").date()

        for p in job["processes"]:

            hrs = p["hours"]
            end_time = cur_time + timedelta(hours=hrs)

            # apply lunch break
            if cur_time < lunch_start < end_time:
                end_time += (lunch_end - lunch_start)

            # -----------------------------
            # DUE DATE STATUS COLOR
            # -----------------------------
            if job_due < today:
                due_status = "OVERDUE"
            elif job_due == today or job_due == today + timedelta(days=1):
                due_status = "NEAR DUE"
            else:
                due_status = "OK"

            schedule.append({
                "Job": job["job"],
                "Due Date": job["due"],
                "Due Status": due_status,
                "Process": p["name"],
                "Machine": p["machine"],
                "Workers": p["workers"],
                "Hours": hrs,
                "Start": cur_time.strftime("%I:%M %p"),
                "End": end_time.strftime("%I:%M %p"),
                "Status": "SCHEDULED"
            })

            cur_time = end_time

    df = pd.DataFrame(schedule)

    # -----------------------------
    # ADD COLOR HIGHLIGHTING
    # -----------------------------
    def color_due(val):
        if val == "OVERDUE":
            return "background-color: #ff4d4d; color: white;"   # red
        elif val == "NEAR DUE":
            return "background-color: #ffcc00; color: black;"   # yellow
        return ""

    st.write("### 📊 Planned Schedule (with Due Date Alerts)")
    st.dataframe(
        df.style.applymap(color_due, subset=["Due Status"]),
        use_container_width=True
    )

# ============================================================
#                      STAFF SETTINGS
# ============================================================
elif page == "Staff Settings":
    st.title("👥 Staff Settings")

    st.session_state.staff_count = st.number_input("Total Staff", min_value=1, value=st.session_state.staff_count)
    st.session_state.work_hours = st.number_input("Work Hours per Day", min_value=1, value=st.session_state.work_hours)

    st.success("Settings updated!")
