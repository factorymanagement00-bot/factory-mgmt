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
# CUSTOM PREMIUM UI (GLASS EFFECT)
# -----------------------------------------------------
st.markdown("""
<style>
body {
    background: linear-gradient(145deg, #0f0f0f, #1a1a1a);
    color: #e5e5e5;
}
.block-container { padding-top: 2rem; }

.glass-card {
    background: rgba(255,255,255,0.05);
    border-radius: 18px;
    padding: 25px 30px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 8px 25px rgba(0,0,0,0.35);
    backdrop-filter: blur(14px);
    margin-bottom: 25px;
    transition: 0.25s;
}
.glass-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 35px rgba(0,0,0,0.55);
}

.header-title {
    font-size: 52px;
    font-weight: 700;
    text-align: center;
    background: linear-gradient(90deg,#ff7a7a,#e88cff,#6acbff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-sub {
    text-align: center;
    font-size: 18px;
    color: #b5b5b5;
    margin-top: -10px;
}

div.stButton > button {
    background: linear-gradient(90deg,#7b3eff,#4776e6);
    color:white;
    border-radius:10px;
    height:48px;
    border:none;
    font-size:16px;
    transition:0.2s ease;
}
div.stButton > button:hover {
    background: linear-gradient(90deg,#9a63ff,#5b8bff);
    transform:scale(1.02);
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

    # CATEGORY SYSTEM FIX
    if "categories" not in st.session_state:
        st.session_state.categories = []


# -----------------------------------------------------
# AI WORKLOAD PLANNER
# -----------------------------------------------------
def plan_today(jobs, staff_count, hours_per_staff):
    total_capacity = staff_count * hours_per_staff
    used = 0.0
    tasks = []

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

    col1, col2 = st.columns(2)

    with col1:
        count = st.number_input("Number of Staff", 1, 500, st.session_state.staff["count"])

    with col2:
        hours = st.number_input("Hours per Staff per Day", 1.0, 24.0, st.session_state.staff["hours"], step=0.5)

    st.session_state.staff["count"] = int(count)
    st.session_state.staff["hours"] = float(hours)

    st.success(f"Daily Capacity: {count * hours} hours")
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# INVENTORY UI (WITH CATEGORY ADD + SELECT + FILTER)
# -----------------------------------------------------
def inventory_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📦 Inventory")

    st.markdown("### ➕ Manage Categories")

    colA, colB = st.columns(2)

    # 1️⃣ ADD NEW CATEGORY
    with colA:
        new_cat = st.text_input("Add New Category")
        if st.button("Add Category"):
            if new_cat.strip():
                if new_cat not in st.session_state.categories:
                    st.session_state.categories.append(new_cat)
                    st.success(f"Category '{new_cat}' added!")
                    st.rerun()
                else:
                    st.warning("Category already exists.")
            else:
                st.error("Category cannot be empty.")

    # 2️⃣ SELECT CATEGORY FOR NEW ITEMS
    with colB:
        if st.session_state.categories:
            selected_category = st.selectbox("Select Category for Inventory Item", st.session_state.categories)
        else:
            selected_category = None
            st.info("No categories added yet.")

    st.markdown("---")
    st.subheader("➕ Add Inventory Item")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        name = st.text_input("Item Name")

    with col2:
        category = selected_category if selected_category else "Uncategorized"

    with col3:
        weight = st.number_input("Weight (kg)", 0.0, 100000.0, 0.0, step=0.1)

    with col4:
        qty = st.number_input("Quantity", 0, 100000, 0)

    with col5:
        size = st.text_input("Size (e.g. 10x20 cm)")

    if st.button("Add Inventory Item"):
        if name.strip():
            st.session_state.inventory.append({
                "Item": name,
                "Category": category,
                "Weight (kg)": weight,
                "Quantity": qty,
                "Size": size if size.strip() else "N/A"
            })
            st.success("Item added successfully!")
            st.rerun()
        else:
            st.error("Item name cannot be empty.")

    st.markdown("---")
    st.subheader("📋 Inventory List (Filterable)")

    if len(st.session_state.inventory) == 0:
        st.info("No inventory items added yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    filter_opts = ["All"] + st.session_state.categories
    filter_choice = st.selectbox("Filter by Category", filter_opts)

    if filter_choice == "All":
        filtered = st.session_state.inventory
    else:
        filtered = [item for item in st.session_state.inventory if item["Category"] == filter_choice]

    st.table(filtered)
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# JOBS UI (WITH DELETE + JOBS AT BOTTOM)
# -----------------------------------------------------
def jobs_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("🧾 Add Job")

    col1, col2 = st.columns(2)

    with col1:
        job_name = st.text_input("Job Name")
        qty = st.number_input("Quantity", 1, 100000, 100)

    with col2:
        due_date = st.date_input("Due Date", date.today())

    num_proc = st.slider("Number of Processes", 1, 20, 5)

    st.markdown("### 📝 Process Details")
    processes = []

    for i in range(num_proc):
        colA, colB = st.columns([3, 1.2])
        with colA:
            pname = st.text_input(f"Process {i+1} Name", key=f"pname_{i}")
        with colB:
            phours = st.number_input("Hours", 0.5, 24.0, 3.0, step=0.5, key=f"phours_{i}")
        processes.append({"name": pname, "hours": float(phours)})

    if st.button("Add Job"):
        if not job_name.strip():
            st.error("Job name required.")
        elif any(p["name"].strip() == "" for p in processes):
            st.error("All process names required.")
        else:
            st.session_state.jobs.append({
                "name": job_name,
                "qty": qty,
                "due": due_date,
                "processes": processes
            })
            st.success("Job added!")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- JOBS LIST AT BOTTOM ----------------
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📋 Existing Jobs")

    if len(st.session_state.jobs) == 0:
        st.info("No jobs added yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for idx, job in enumerate(st.session_state.jobs):
        with st.expander(f"📦 {job['name']} — Due {job['due']}"):
            st.write(f"**Quantity:** {job['qty']}")
            st.write("### Processes:")
            for p in job["processes"]:
                st.write(f"- {p['name']} — {p['hours']} hrs")

            if st.button(f"🗑 Delete Job '{job['name']}'", key=f"del{idx}"):
                st.session_state.jobs.pop(idx)
                st.success("Job deleted.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# PLANNER UI
# -----------------------------------------------------
def planner_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📅 AI Daily Planner")

    if st.button("Generate Today's Plan"):
        if len(st.session_state.jobs) == 0:
            st.warning("No jobs added.")
        else:
            tasks, used, total = plan_today(
                st.session_state.jobs,
                st.session_state.staff["count"],
                st.session_state.staff["hours"]
            )

            st.success(f"Planned {len(tasks)} tasks — Used {used}/{total} hrs")
            st.table(tasks)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# MAIN APP
# -----------------------------------------------------
def main():
    init_state()

    st.markdown("<h1 class='header-title'>🏭 Factory-Management.AI</h1>", unsafe_allow_html=True)
    st.markdown("<p class='header-sub'>A premium AI dashboard to manage workforce, inventory & factory workload.</p>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["👷 Staff", "📦 Inventory", "🧾 Jobs", "📅 Planner"])

    with tab1: staff_ui()
    with tab2: inventory_ui()
    with tab3: jobs_ui()
    with tab4: planner_ui()


if __name__ == "__main__":
    main()
