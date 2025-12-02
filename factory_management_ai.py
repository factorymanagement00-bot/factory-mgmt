import streamlit as st
from datetime import datetime, date, timedelta

# -----------------------------
# CONFIG – SUBSCRIPTION SYSTEM
# -----------------------------
PREMIUM_TOKENS = ["FACTORYPRO123", "PREMIUM999", "FM2025"]  # change/add your own tokens

MAX_JOBS_FREE = 5        # Free users can add up to 5 jobs
MAX_INVENTORY_FREE = 10  # Free users can add up to 10 inventory items


def check_subscription(token: str) -> str:
    """
    Check if the token is premium or not.
    Empty token = free plan.
    Invalid token = free plan (with warning).
    """
    if not token.strip():
        return "free"
    if token.strip() in PREMIUM_TOKENS:
        return "premium"
    return "invalid"


# -----------------------------
# INITIALIZE SESSION STATE
# -----------------------------
def init_state():
    if "staff" not in st.session_state:
        st.session_state.staff = {
            "staff_count": 5,
            "hours_per_staff": 8
        }
    if "inventory" not in st.session_state:
        st.session_state.inventory = []  # list of dicts
    if "jobs" not in st.session_state:
        st.session_state.jobs = []  # list of jobs


# -----------------------------
# SCHEDULER / "AI" PLANNER
# -----------------------------
def plan_today(jobs, staff_count: int, hours_per_staff: float):
    """
    Very simple planning logic:
    - Total capacity = staff_count * hours_per_staff
    - Sort jobs by due_date, then by name
    - Go through each job and its processes in order
    - Fill up today's capacity
    """
    if staff_count <= 0 or hours_per_staff <= 0:
        return [], 0, 0

    total_capacity = staff_count * hours_per_staff

    # Flatten processes with reference to job
    # Each job: {id, name, due_date, quantity, processes:[{name, hours}]}
    sorted_jobs = sorted(
        jobs,
        key=lambda j: (j["due_date"], j["name"])
    )

    today_tasks = []
    used_hours = 0.0

    for job in sorted_jobs:
        for idx, process in enumerate(job["processes"], start=1):
            duration = process["hours"]
            if used_hours + duration <= total_capacity:
                today_tasks.append({
                    "job_name": job["name"],
                    "job_id": job["id"],
                    "due_date": job["due_date"],
                    "process_name": process["name"],
                    "process_index": idx,
                    "duration_hours": duration
                })
                used_hours += duration
            else:
                # No more capacity
                break

        if used_hours >= total_capacity:
            break

    return today_tasks, used_hours, total_capacity


def add_time_slots_to_tasks(tasks, workday_start_hour=9):
    """
    Add start/end time slots to the tasks based on duration.
    Workday starts at workday_start_hour.
    """
    if not tasks:
        return tasks

    today = date.today()
    current_time = datetime(
        year=today.year,
        month=today.month,
        day=today.day,
        hour=workday_start_hour,
        minute=0
    )

    for t in tasks:
        start_time = current_time
        end_time = start_time + timedelta(hours=t["duration_hours"])
        t["start_time"] = start_time.strftime("%H:%M")
        t["end_time"] = end_time.strftime("%H:%M")
        current_time = end_time

    return tasks


# -----------------------------
# UI SECTIONS
# -----------------------------
def staff_section(subscription_type: str):
    st.subheader("👷 Staff & Workload Settings")
    st.write("Set how many people are working and their daily working hours.")

    col1, col2 = st.columns(2)

    with col1:
        staff_count = st.number_input(
            "Number of Staff",
            min_value=1,
            max_value=500 if subscription_type == "premium" else 50,
            value=st.session_state.staff["staff_count"],
            step=1
        )
    with col2:
        hours_per_staff = st.number_input(
            "Working Hours per Staff (per day)",
            min_value=1.0,
            max_value=24.0,
            value=float(st.session_state.staff["hours_per_staff"]),
            step=0.5
        )

    st.session_state.staff["staff_count"] = int(staff_count)
    st.session_state.staff["hours_per_staff"] = float(hours_per_staff)

    st.info(
        f"Total daily capacity: **{staff_count * hours_per_staff:.1f} hours** "
        f"({staff_count} staff × {hours_per_staff} hours)"
    )


def inventory_section(subscription_type: str):
    st.subheader("📦 Inventory Management")

    inventory = st.session_state.inventory

    if inventory:
        st.table(inventory)
    else:
        st.write("No inventory items yet.")

    st.markdown("---")
    st.markdown("### ➕ Add Inventory Item")

    col1, col2, col3 = st.columns(3)
    with col1:
        item_name = st.text_input("Item Name", key="inv_name")
    with col2:
        stock = st.number_input("Current Stock", min_value=0, value=0, key="inv_stock")
    with col3:
        reorder_level = st.number_input("Reorder Level", min_value=0, value=10, key="inv_reorder")

    if st.button("Add Item"):
        if subscription_type == "free" and len(inventory) >= MAX_INVENTORY_FREE:
            st.error(f"Free plan limit reached: You can only add {MAX_INVENTORY_FREE} inventory items.")
        elif not item_name.strip():
            st.error("Please enter an item name.")
        else:
            inventory.append({
                "item_name": item_name.strip(),
                "stock": stock,
                "reorder_level": reorder_level
            })
            st.session_state.inventory = inventory
            st.success("Inventory item added.")


def jobs_section(subscription_type: str):
    st.subheader("🧾 Jobs & Processes")

    jobs = st.session_state.jobs

    if jobs:
        # Show a simple overview
        st.write("**Current Jobs:**")
        display_jobs = []
        for j in jobs:
            display_jobs.append({
                "ID": j["id"],
                "Name": j["name"],
                "Due Date": j["due_date"].isoformat(),
                "Quantity": j["quantity"],
                "Processes": len(j["processes"]),
                "Hours Total": sum(p["hours"] for p in j["processes"])
            })
        st.table(display_jobs)
    else:
        st.write("No jobs added yet.")

    st.markdown("---")
    st.markdown("### ➕ Add New Job")

    col1, col2 = st.columns(2)
    with col1:
        job_name = st.text_input("Job Name", key="job_name")
        quantity = st.number_input("Quantity", min_value=1, value=100, step=1, key="job_qty")
    with col2:
        due_date = st.date_input("Due Date", value=date.today(), key="job_due")

    col3, col4 = st.columns(2)
    with col3:
        num_processes = st.number_input(
            "Number of Processes",
            min_value=1,
            max_value=20 if subscription_type == "premium" else 5,
            value=5,
            step=1,
            key="job_proc"
        )
    with col4:
        base_hours = st.slider(
            "Estimated Hours per Process (2–5 hours typical)",
            min_value=1.0,
            max_value=8.0,
            value=3.0,
            step=0.5,
            key="job_base_hours"
        )

    st.caption("You can think of base hours as average time per process (you said usually 2–5 hours).")

    if st.button("Add Job"):
        if subscription_type == "free" and len(jobs) >= MAX_JOBS_FREE:
            st.error(f"Free plan limit reached: You can only add {MAX_JOBS_FREE} jobs.")
        elif not job_name.strip():
            st.error("Please enter a job name.")
        else:
            # Simple logic: total hours per process = base_hours
            processes = []
            for i in range(int(num_processes)):
                processes.append({
                    "name": f"Process {i+1}",
                    "hours": float(base_hours)
                })

            new_job = {
                "id": f"JOB-{len(jobs)+1}",
                "name": job_name.strip(),
                "due_date": due_date,
                "quantity": int(quantity),
                "processes": processes
            }
            jobs.append(new_job)
            st.session_state.jobs = jobs
            st.success(f"Job '{job_name}' added with {num_processes} processes.")


def planning_section(subscription_type: str):
    st.subheader("📅 AI Planning: What Should Be Done Today?")

    jobs = st.session_state.jobs
    staff_count = st.session_state.staff["staff_count"]
    hours_per_staff = st.session_state.staff["hours_per_staff"]

    if not jobs:
        st.warning("No jobs available. Add some jobs in the 'Jobs & Processes' section.")
        return

    if st.button("Generate Today's Plan"):
        tasks, used_hours, total_capacity = plan_today(jobs, staff_count, hours_per_staff)
        tasks = add_time_slots_to_tasks(tasks)

        if not tasks:
            st.info("No tasks scheduled for today (maybe capacity is zero or jobs are empty).")
            return

        st.success(
            f"Planned **{len(tasks)} processes** for today using **{used_hours:.1f}/{total_capacity:.1f} hours** "
            f"of capacity."
        )

        # Show tasks in a table
        display_tasks = []
        for t in tasks:
            display_tasks.append({
                "Job": t["job_name"],
                "Process": t["process_name"],
                "Duration (hrs)": t["duration_hours"],
                "Start": t["start_time"],
                "End": t["end_time"],
                "Due Date": t["due_date"].isoformat()
            })

        st.table(display_tasks)

        # Simple natural language summary
        st.markdown("### 🧠 AI Summary (Simple Logic)")
        top_jobs = sorted(
            {t["Job"] for t in display_tasks},
            key=lambda name: name
        )
        st.write(
            f"Today, the system prioritized jobs with the earliest due dates and filled up your available "
            f"capacity of **{total_capacity:.1f} hours**. It scheduled processes from these jobs: "
            f"**{', '.join(top_jobs)}**."
        )


# -----------------------------
# MAIN APP
# -----------------------------
def main():
    st.set_page_config(page_title="Factory-Management.AI", layout="wide")
    init_state()

    st.title("🏭 Factory-Management.AI")
    st.write("Smart helper to manage your **inventory, staff, and daily workload**.")

    # Subscription bar
    st.markdown("### 💳 Subscription")
    token = st.text_input("Enter Subscription Token (leave empty for FREE plan):", type="password")
    sub_status = check_subscription(token)

    if sub_status == "invalid":
        subscription_type = "free"
        st.error("Invalid token. You are on the FREE plan with limited features.")
    elif sub_status == "premium":
        subscription_type = "premium"
        st.success("✅ Premium plan active! All features unlocked.")
    else:
        subscription_type = "free"
        st.warning("You are on the FREE plan. Some limits apply.")

    st.markdown("---")

    # Tabs for sections
    tab1, tab2, tab3, tab4 = st.tabs(["👷 Staff", "📦 Inventory", "🧾 Jobs", "📅 Today's Plan"])

    with tab1:
        staff_section(subscription_type)

    with tab2:
        inventory_section(subscription_type)

    with tab3:
        jobs_section(subscription_type)

    with tab4:
        planning_section(subscription_type)


if __name__ == "__main__":
    main()
