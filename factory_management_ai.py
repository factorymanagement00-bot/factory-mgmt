import streamlit as st
from datetime import date

# -----------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------
st.set_page_config(
    page_title="Factory-Management.AI",
    page_icon="🏭",
    layout="wide",
)

# -----------------------------------------------------
# CUSTOM PREMIUM UI (GLASSMORPHISM)
# -----------------------------------------------------
st.markdown("""
<style>

body {
    background: linear-gradient(145deg, #0f0f0f, #1a1a1a);
    color: #e5e5e5;
}

.block-container {
    padding-top: 2rem;
}

/* Glass Card */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 18px;
    padding: 25px 30px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(14px);
    margin-bottom: 25px;
    transition: 0.25s ease;
}
.glass-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.55);
}

/* Header */
.header-title {
    font-size: 52px;
    font-weight: 700;
    text-align: center;
    background: linear-gradient(90deg, #ff7a7a, #e88cff, #6acbff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-sub {
    text-align: center;
    font-size: 18px;
    color: #b5b5b5;
    margin-top: -10px;
}

/* Buttons */
div.stButton > button {
    background: linear-gradient(90deg, #7b3eff, #4776e6);
    color: white;
    border-radius: 10px;
    height: 48px;
    border: none;
    font-size: 16px;
    transition: 0.2s ease;
}
div.stButton > button:hover {
    background: linear-gradient(90deg, #9a63ff, #5b8bff);
    transform: scale(1.02);
}

/* Tabs */
.stTabs [role="tablist"] button {
    background: rgba(255,255,255,0.08);
    border-radius: 12px;
    margin-right: 10px;
    padding: 12px 16px;
    font-size: 16px;
}
.stTabs [role="tablist"] button:hover {
    background: rgba(255,255,255,0.18);
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------
# INIT SESSION STATE
# -----------------------------------------------------
def init_state():
    if "staff" not in st.session_state:
        st.session_state.staff = {"count": 5, "hours": 8.0}

    if "inventory" not in st.session_state:
        st.session_state.inventory = []

    if "jobs" not in st.session_state:
        st.session_state.jobs = []


# -----------------------------------------------------
# AI WORKLOAD PLANNER
# -----------------------------------------------------
def plan_today(jobs, staff_count, hours_per_staff):
    total_capacity = staff_count * hours_per_staff
    used = 0.0
    tasks = []

    # Sort jobs by due date
    sorted_jobs = sorted(jobs, key=lambda j: j["due"])

    for job in sorted_jobs:
        for proc in job["processes"]:
            if used + proc["hours"] <= total_capacity:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Hours": proc["hours"]
                })
                used += proc["hours"]

    return tasks, used, total_capacity


# -----------------------------------------------------
# STAFF UI
# -----------------------------------------------------
def staff_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("👷 Staff & Workload")

    # Force correct types
    st.session_state.staff["count"] = int(st.session_state.staff.get("count", 5))
    st.session_state.staff["hours"] = float(st.session_state.staff.get("hours", 8.0))

    col1, col2 = st.columns(2)

    with col1:
        count = st.number_input(
            "Number of Staff",
            min_value=1,
            max_value=500,
            value=st.session_state.staff["count"],
            step=1
        )

    with col2:
        hours = st.number_input(
            "Hours per Staff per Day",
            min_value=1.0,
            max_value=24.0,
            value=st.session_state.staff["hours"],
            step=0.5
        )

    st.session_state.staff["count"] = int(count)
    st.session_state.staff["hours"] = float(hours)

    st.success(f"Daily Capacity: {count * hours} hours")
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# INVENTORY UI
# -----------------------------------------------------
def inventory_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📦 Inventory")

    st.markdown("### ➕ Add Inventory Item")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        name = st.text_input("Item Name")

    with col2:
        weight = st.number_input("Weight (kg)", min_value=0.0, max_value=100000.0, value=0.0, step=0.1)

    with col3:
        qty = st.number_input("Quantity", min_value=0, max_value=100000, value=0, step=1)

    with col4:
        size = st.text_input("Size (e.g. 10x20 cm)")

    if st.button("Add Inventory Item"):
        if name.strip():
            st.session_state.inventory.append({
                "Item": name,
                "Weight (kg)": weight,
                "Quantity": qty,
                "Size": size if size.strip() else "N/A"
            })
            st.success("Item added!")
        else:
            st.error("Item name cannot be blank.")

    st.markdown("---")
    st.markdown("### 📋 Current Inventory")

    if st.session_state.inventory:
        st.table(st.session_state.inventory)
    else:
        st.info("No inventory items added yet.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# JOBS UI
# -----------------------------------------------------
def jobs_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("🧾 Jobs & Processes")

    # ------------------------------
    # SHOW EXISTING JOBS (DETAILED)
    # ------------------------------
    if st.session_state.jobs:
        st.markdown("### 📋 Existing Jobs")

        # Loop through jobs with index
        for idx, job in enumerate(st.session_state.jobs):

            with st.expander(f"📦 {job['name']} — Due: {job['due'].isoformat()}"):

                st.write(f"**Quantity:** {job['qty']} units")
                st.write("### 🛠 Processes:")

                for p in job["processes"]:
                    st.write(f"- **{p['name']}** — {p['hours']} hrs")

                st.markdown("---")

                # DELETE BUTTON
                delete_button = st.button(
                    f"🗑 Delete Job '{job['name']}'",
                    key=f"delete_job_{idx}"
                )

                if delete_button:
                    st.session_state.jobs.pop(idx)
                    st.success(f"Deleted job: {job['name']}")
                    st.experimental_rerun()

    else:
        st.info("No jobs added yet.")

    st.markdown("---")
    st.markdown("### ➕ Add Job")

    col1, col2 = st.columns(2)

    with col1:
        job_name = st.text_input("Job Name")
        qty = st.number_input("Quantity", min_value=1, max_value=100000, value=100, step=1)

    with col2:
        due_date = st.date_input("Due Date", date.today())

    num_processes = st.slider("Number of Processes", min_value=1, max_value=20, value=5)

    st.markdown("### 📝 Process Details")
    process_list = []

    for i in range(num_processes):
        colA, colB = st.columns([3, 1.2])

        with colA:
            p_name = st.text_input(f"Process {i+1} Name", key=f"pname_{i}")

        with colB:
            p_hours = st.number_input(
                "Hours",
                min_value=0.5,
                max_value=24.0,
                value=3.0,
                step=0.5,
                key=f"phours_{i}"
            )

        process_list.append({"name": p_name, "hours": float(p_hours)})

    # Add job
    if st.button("Add Job"):
        if not job_name.strip():
            st.error("Job name is required.")
        elif any(p["name"].strip() == "" for p in process_list):
            st.error("Please fill all process names.")
        else:
            st.session_state.jobs.append({
                "name": job_name,
                "qty": int(qty),
                "due": due_date,
                "processes": process_list
            })
            st.success("Job added successfully!")

    st.markdown("</div>", unsafe_allow_html=True)



# -----------------------------------------------------
# PLANNER UI
# -----------------------------------------------------
def planner_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📅 AI Workload Planner")

    if st.button("Generate Today's Plan"):
        if not st.session_state.jobs:
            st.warning("No jobs available to plan.")
        else:
            tasks, used, total = plan_today(
                st.session_state.jobs,
                st.session_state.staff["count"],
                st.session_state.staff["hours"]
            )

            if not tasks:
                st.warning("No tasks scheduled today (maybe capacity too low).")
            else:
                st.success(f"Planned {len(tasks)} tasks • Used {used}/{total} hours")
                st.table(tasks)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------
def main():
    init_state()

    st.markdown("<h1 class='header-title'>🏭 Factory-Management.AI</h1>", unsafe_allow_html=True)
    st.markdown("<p class='header-sub'>A premium AI dashboard to manage workforce, inventory & factory workload.</p>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["👷 Staff", "📦 Inventory", "🧾 Jobs", "📅 Planner"])

    with tab1:
        staff_ui()

    with tab2:
        inventory_ui()

    with tab3:
        jobs_ui()

    with tab4:
        planner_ui()


if __name__ == "__main__":
    main()
