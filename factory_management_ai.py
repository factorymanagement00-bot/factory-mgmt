import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd

# -----------------------------------------------------
# PAGE CONFIG & THEME
# -----------------------------------------------------
st.set_page_config(
    page_title="Factory-Management.AI",
    page_icon="🏭",
    layout="wide",
)

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
# SESSION STATE INIT
# -----------------------------------------------------
def init_state():
    if "staff" not in st.session_state:
        st.session_state.staff = {"count": 5, "hours": 8.0}
    if "inventory" not in st.session_state:
        st.session_state.inventory = []
    if "jobs" not in st.session_state:
        st.session_state.jobs = []
    if "categories" not in st.session_state:
        st.session_state.categories = []


# -----------------------------------------------------
# STAFF UI
# -----------------------------------------------------
def staff_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("👷 Staff & Workload")

    col1, col2 = st.columns(2)
    with col1:
        count = st.number_input(
            "Number of Staff",
            min_value=1, max_value=500,
            value=st.session_state.staff["count"]
        )
    with col2:
        hours = st.number_input(
            "Hours per Staff per Day",
            min_value=1.0, max_value=24.0,
            value=float(st.session_state.staff["hours"]),
            step=0.5
        )

    st.session_state.staff["count"] = int(count)
    st.session_state.staff["hours"] = float(hours)

    st.success(f"Daily capacity: {count * hours} hours")
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# INVENTORY UI (CATEGORY + FILTER + DELETE)
# -----------------------------------------------------
def inventory_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📦 Inventory")

    # --- Category management ---
    st.markdown("### ➕ Manage Categories")
    colA, colB = st.columns(2)

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

    with colB:
        if st.session_state.categories:
            selected_category = st.selectbox(
                "Select Category for New Item",
                st.session_state.categories
            )
        else:
            selected_category = None
            st.info("No categories yet. Add one on the left.")

    st.markdown("---")

    # --- Add inventory item ---
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
        size = st.text_input("Size (e.g. 32, 20x30 cm, etc.)")

    if st.button("Add Inventory Item"):
        if name.strip():
            st.session_state.inventory.append({
                "Item": name,
                "Category": category,
                "Weight (kg)": weight,
                "Quantity": qty,
                "Size": size if size.strip() else "N/A",
            })
            st.success("Item added.")
            st.rerun()
        else:
            st.error("Item name cannot be empty.")

    st.markdown("---")
    st.subheader("📋 Inventory List")

    if not st.session_state.inventory:
        st.info("No inventory items yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    filter_opts = ["All"] + st.session_state.categories
    filter_choice = st.selectbox("Filter by Category", filter_opts)

    if filter_choice == "All":
        filtered = st.session_state.inventory
    else:
        filtered = [
            item for item in st.session_state.inventory
            if item["Category"] == filter_choice
        ]

    st.table(filtered)

    st.markdown("### 🗑 Delete Inventory Items")
    for i, item in enumerate(filtered):
        with st.expander(f"{item['Item']} — {item['Category']}"):
            st.write(f"Weight: {item['Weight (kg)']} kg")
            st.write(f"Quantity: {item['Quantity']}")
            st.write(f"Size: {item['Size']}")

            if st.button(f"Delete '{item['Item']}'", key=f"inv_del_{i}"):
                real_index = st.session_state.inventory.index(item)
                st.session_state.inventory.pop(real_index)
                st.success("Item deleted.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# JOBS UI (OPTIONAL MATERIAL + MACHINE + WORKERS)
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
    inventory = st.session_state.inventory
    categories = st.session_state.categories

    for i in range(num_proc):
        st.markdown(f"### Process {i+1}")
        colA, colB = st.columns([3, 1.2])

        with colA:
            pname = st.text_input(f"Process {i+1} Name", key=f"pname_{i}")
        with colB:
            phours = st.number_input(
                "Hours",
                min_value=0.5, max_value=24.0,
                value=3.0, step=0.5,
                key=f"phours_{i}"
            )

        # Material section
        colC, colD, colE = st.columns([2, 2, 1.5])

        with colC:
            p_cat = st.selectbox(
                "Category (optional)",
                options=["None"] + categories,
                key=f"pcat_{i}"
            )
            if p_cat == "None":
                p_cat = ""

        with colD:
            if p_cat:
                items_for_cat = sorted({item["Item"] for item in inventory if item["Category"] == p_cat})
                items_for_cat = ["None"] + items_for_cat
            else:
                items_for_cat = ["None"]

            p_item = st.selectbox(
                "Inventory Item (optional)",
                options=items_for_cat,
                key=f"pitem_{i}"
            )
            if p_item == "None":
                p_item = ""

        with colE:
            if p_cat and p_item:
                sizes_for_item = sorted({
                    str(item["Size"])
                    for item in inventory
                    if item["Category"] == p_cat and item["Item"] == p_item
                })
                sizes_for_item = ["None"] + sizes_for_item
            else:
                sizes_for_item = ["None"]

            p_size = st.selectbox(
                "Size (optional)",
                options=sizes_for_item,
                key=f"psize_{i}"
            )
            if p_size == "None":
                p_size = ""

        # Machine + workers
        colF, colG = st.columns([2, 1])
        with colF:
            machine = st.text_input("Machine (optional)", key=f"pmachine_{i}")
        with colG:
            workers = st.number_input(
                "Workers for this process",
                min_value=1, max_value=50, value=1,
                key=f"pworkers_{i}"
            )

        processes.append({
            "name": pname,
            "hours": float(phours),
            "material_category": p_cat,
            "material_item": p_item,
            "material_size": p_size,
            "machine": machine,
            "workers": int(workers),
        })

        st.markdown("---")

    if st.button("Add Job"):
        if not job_name.strip():
            st.error("Job name is required.")
        elif any(p["name"].strip() == "" for p in processes):
            st.error("All process names are required.")
        else:
            st.session_state.jobs.append({
                "name": job_name,
                "qty": int(qty),
                "due": due_date,
                "processes": processes
            })
            st.success("Job added.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Existing jobs ----
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📋 Existing Jobs")

    if not st.session_state.jobs:
        st.info("No jobs added yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for idx, job in enumerate(st.session_state.jobs):
        with st.expander(f"📦 {job['name']} — Due {job['due']}"):
            st.write(f"**Quantity:** {job['qty']}")
            st.write("### Processes:")

            for p in job["processes"]:
                if p["material_category"]:
                    mat = f"{p['material_category']} → {p['material_item']} → {p['material_size']}"
                else:
                    mat = "No material selected"

                machine = p.get("machine", "") or "N/A"
                workers = p.get("workers", 1)

                st.write(
                    f"- **{p['name']}** — {p['hours']} hrs | "
                    f"Machine: {machine} | Workers: {workers} | Material: {mat}"
                )

            if st.button(f"🗑 Delete Job '{job['name']}'", key=f"job_del_{idx}"):
                st.session_state.jobs.pop(idx)
                st.success("Job deleted.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# ADVANCED PLANNING ENGINE (break, material, staff lanes)
# -----------------------------------------------------
def plan_today_advanced(jobs, inventory, staff_count, hours_per_staff):
    # Workday + break time settings
    work_start_str = "09:00"
    break_start_str = "13:00"
    break_end_str = "14:00"

    work_start = datetime.combine(date.today(), datetime.strptime(work_start_str, "%H:%M").time())
    break_start = datetime.combine(date.today(), datetime.strptime(break_start_str, "%H:%M").time())
    break_end = datetime.combine(date.today(), datetime.strptime(break_end_str, "%H:%M").time())

    # Each staff has its own timeline
    staff_free = [work_start for _ in range(staff_count)]
    staff_end = [work_start + timedelta(hours=hours_per_staff) for _ in range(staff_count)]
    staff_used = [0.0 for _ in range(staff_count)]

    # Snapshot of inventory for simulation (no real subtraction in DB)
    inv_snapshot = []
    for item in inventory:
        inv_snapshot.append({
            "Item": item["Item"],
            "Category": item["Category"],
            "Size": str(item["Size"]),
            "Quantity": item["Quantity"],
        })

    def find_inventory(cat, name, size):
        for inv in inv_snapshot:
            if (
                inv["Category"] == cat and
                inv["Item"] == name and
                inv["Size"] == str(size) and
                inv["Quantity"] > 0
            ):
                return inv
        return None

    tasks = []

    # Sort jobs by due date
    sorted_jobs = sorted(jobs, key=lambda j: j["due"])

    for job in sorted_jobs:
        for proc in job["processes"]:
            hours = float(proc["hours"])
            if hours <= 0:
                continue

            # --- Material check ---
            mat_status = "OK"
            inv_match = None
            if proc.get("material_category") and proc.get("material_item") and proc.get("material_size"):
                inv_match = find_inventory(
                    proc["material_category"],
                    proc["material_item"],
                    proc["material_size"]
                )
                if inv_match is None:
                    mat_status = "NO MATERIAL"

            if mat_status == "NO MATERIAL":
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": proc.get("workers", 1),
                    "Hours": hours,
                    "Staff": None,
                    "Start": "",
                    "End": "",
                    "Status": "BLOCKED: No material",
                })
                continue

            # --- Assign to staff lane with earliest free time ---
            staff_idx = min(range(staff_count), key=lambda i: staff_free[i])
            start_time = staff_free[staff_idx]

            # Ensure not before work start
            if start_time < work_start:
                start_time = work_start

            # Handle lunch break (no splitting; push whole task after break)
            if start_time < break_start and start_time + timedelta(hours=hours) > break_start:
                start_time = break_end

            # Check capacity in this staff's day
            if start_time >= staff_end[staff_idx]:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": proc.get("workers", 1),
                    "Hours": hours,
                    "Staff": None,
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: No capacity",
                })
                continue

            end_time = start_time + timedelta(hours=hours)
            if end_time > staff_end[staff_idx]:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": proc.get("workers", 1),
                    "Hours": hours,
                    "Staff": None,
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: No capacity",
                })
                continue

            # Simulated material consumption (1 unit per process)
            if inv_match is not None:
                inv_match["Quantity"] -= 1

            staff_free[staff_idx] = end_time
            staff_used[staff_idx] += hours

            tasks.append({
                "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": proc.get("workers", 1),
                    "Hours": hours,
                    "Staff": staff_idx + 1,
                    "Start": start_time.strftime("%I:%M %p"),
                    "End": end_time.strftime("%I:%M %p"),
                    "Status": "SCHEDULED",
            })

    total_used = sum(staff_used)
    total_capacity = staff_count * hours_per_staff
    return tasks, total_used, total_capacity


# -----------------------------------------------------
# PLANNER UI (USES ADVANCED ENGINE)
# -----------------------------------------------------
def planner_ui():
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📅 AI Daily Planner")

    staff_count = st.session_state.staff["count"]
    hours_per_staff = st.session_state.staff["hours"]

    st.info(
        f"Using **{staff_count} staff × {hours_per_staff} hours** "
        f"per day (set in the Staff tab). Workday: 9:00–{9 + int(hours_per_staff)}:00 with 1–2 PM lunch break."
    )

    if st.button("Generate Today's Plan"):
        if not st.session_state.jobs:
            st.error("No jobs available to plan.")
        else:
            tasks, used, capacity = plan_today_advanced(
                st.session_state.jobs,
                st.session_state.inventory,
                staff_count,
                hours_per_staff,
            )

            st.success(f"Planned {len(tasks)} processes — Used {used:.1f}/{capacity:.1f} hours")

            if tasks:
                df = pd.DataFrame(tasks)
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("Nothing could be scheduled for today.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------
def main():
    init_state()

    st.markdown("<h1 class='header-title'>🏭 Factory-Management.AI</h1>", unsafe_allow_html=True)

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
