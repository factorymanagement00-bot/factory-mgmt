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

/* Glassmorphism Card */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 18px;
    padding: 25px 30px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    margin-bottom: 25px;
    transition: 0.25s ease;
}
.glass-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.55);
}

/* Header Glow */
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

/* Tabs Style */
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
# SESSION STATE INIT
# -----------------------------------------------------
def init_state():
    if "staff" not in st.session_state:
        st.session_state.staff = {"count": 5, "hours": 8.0}

    if "inventory" not in st.session_state:
        st.session_state.inventory = []

    if "jobs" not in st.session_state:
        st.session_state.jobs = []


# -----------------------------------------------------
# AI PLANNER (LOGIC)
# -----------------------------------------------------
def plan_today(jobs, staff_count, hours_per_staff):
    total_capacity = staff_count * hours_per_staff
    tasks = []
    used_hours = 0

    sorted_jobs = sorted(jobs, key=lambda x: (x["due"], x["name"]))

    for job in sorted_jobs:
        for p in job["processes"]:
            if used_hours + p["hours"] <= total_capacity:
                tasks.append({"Job": job["name"], "Process": p["name"], "Hours": p["hours"]})
                used_hours += p["hours"]

    return tasks, used_hours, total_capacity


# -----------------------------------------------------
# STAFF UI (FIXED)
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
            value=int(st.session_state.staff["count"]),
            step=1
        )

    with col2:
        hours = st.number_input(
            "Hours per Staff per Day",
            min_value=1.0,
            max_value=24.0,
            value=float(st.session_state.staff["hours"]),
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

    # FORM for adding inventory
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
            st.success("Inventory item added!")
        else:
            st.error("Item name cannot be empty.")

    st.markdown("---")
    st.markdown("### 📋 Current Inventory")

    # SHOW INVENTORY LIST AT BOTTOM
    if st.session_state.inventory:
        st.table(st.session_state.inventory)
    else:
        st.info("No inventory items added yet.")

    st.markdown("</div>", unsafe_allow_html=True)



# -----------------------------------------------------
# JOB UI
# -----------------------------------------------------
def jobs_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("🧾 Jobs & Processes")

    # Show existing jobs
    if st.session_state.jobs:
        st.table([
            {"Job": j["name"], "Due": j["due"].isoformat(), "Processes": len(j["processes"])}
            for j in st.session_state.jobs
        ])
    else:
        st.info("No jobs added yet.")

    st.markdown("### ➕ Add Job")

    col1, col2 = st.columns(2)

    with col1:
        job_name = st.text_input("Job Name")
        quantity = st.number_input("Quantity", min_value=1, max_value=100000, value=100)

    with col2:
        due_date = st.date_input("Due Date", date.today())

    # Select number of processes
    num_processes = st.slider("Number of Processes", 1, 20, 5)

    st.markdown("### 📝 Process Names & Hours")

    process_list = []

    # Create input boxes for each process
    for i in range(num_processes):
        colA, colB = st.columns([3, 1.2])

        with colA:
            p_name = st.text_input(f"Process {i+1} Name", key=f"pname_{i}")

        with colB:
            p_hours = st.number_input(
                f"Hours",
                min_value=0.5,
                max_value=24.0,
                value=3.0,
                step=0.5,
                key=f"phours_{i}"
            )

        process_list.append({"name": p_name, "hours": p_hours})

    if st.button("Add Job"):
        if not job_name.strip():
            st.error("Job name cannot be empty.")
        else:
            # Validate process names
            missing = [p for p in process_list if not p["name"].strip()]
            if missing:
                st.error("Please enter all process names.")
            else:
                st.session_state.jobs.append({
                    "name": job_name,
                    "qty": quantity,
                    "due": due_date,
                    "processes": process_list
                })
                st.success("Job added successfully!")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------
def main():
    init_state()

    st.markdown("<h1 class='header-title'>🏭 Factory-Management.AI</h1>", unsafe_allow_html=True)
    st.markdown("<p class='header-sub'>A premium AI dashboard to manage workforce, inventory & factory workload.</p>", unsafe_allow_html=True)

    tabs = st.tabs(["👷 Staff", "📦 Inventory", "🧾 Jobs", "📅 Planner"])

    with tabs[0]: staff_ui()
    with tabs[1]: inventory_ui()
    with tabs[2]: jobs_ui()
    with tabs[3]: planner_ui()


main()
