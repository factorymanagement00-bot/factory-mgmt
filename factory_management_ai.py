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

    if st.session_state.inventory:
        st.table(st.session_state.inventory)
    else:
        st.info("No inventory added yet.")

    st.markdown("### ➕ Add Inventory Item")

    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Item Name")
    with col2:
        stock = st.number_input("Stock", 0, 100000, 0)
    with col3:
        reorder = st.number_input("Reorder Level", 0, 100000, 10)

    if st.button("Add Inventory Item"):
        if name:
            st.session_state.inventory.append({"Item": name, "Stock": stock, "Reorder Level": reorder})
            st.success("Item added!")
        else:
            st.error("Item name is required.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# JOB UI
# -----------------------------------------------------
def jobs_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("🧾 Jobs & Processes")

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
        name = st.text_input("Job Name")
        qty = st.number_input("Quantity", 1, 100000, 100)

    with col2:
        due = st.date_input("Due Date", date.today())

    process_count = st.slider("Number of Processes", 1, 10, 5)
    hrs = st.slider("Hours per Process", 1.0, 6.0, 3.0)

    if st.button("Add Job"):
        if name:
            st.session_state.jobs.append({
                "name": name,
                "qty": qty,
                "due": due,
                "processes": [{"name": f"Process {i+1}", "hours": hrs} for i in range(process_count)]
            })
            st.success("Job added!")
        else:
            st.error("Job name required.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# PLANNER UI
# -----------------------------------------------------
def planner_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📅 AI Workload Planner")

    if st.button("Generate Today's Plan"):
        tasks, used, total = plan_today(
            st.session_state.jobs,
            st.session_state.staff["count"],
            st.session_state.staff["hours"]
        )

        if not tasks:
            st.warning("No tasks scheduled for today.")
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

    tabs = st.tabs(["👷 Staff", "📦 Inventory", "🧾 Jobs", "📅 Planner"])

    with tabs[0]: staff_ui()
    with tabs[1]: inventory_ui()
    with tabs[2]: jobs_ui()
    with tabs[3]: planner_ui()


main()
