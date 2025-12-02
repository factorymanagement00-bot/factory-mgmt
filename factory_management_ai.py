import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Factory Management AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------
# Dark Neon UI CSS
# ----------------------
st.markdown("""
<style>

body, .stApp {
    background-color: #0d0f16 !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3, h4, h5 {
    color: #b27cff !important;
    font-weight: 600;
}

.stButton>button {
    background: linear-gradient(90deg, #7928ca, #ff0080);
    border: none;
    color: white;
    padding: 10px 22px;
    border-radius: 10px;
    font-size: 17px;
}

.stButton>button:hover {
    opacity: 0.85;
}

.stSelectbox, .stTextInput, .stNumberInput {
    background: #1a1d29;
    color: #ffffff !important;
}

</style>
""", unsafe_allow_html=True)

# ----------------------
# INIT SESSION STATE
# ----------------------
if "inventory" not in st.session_state:
    st.session_state.inventory = []

if "categories" not in st.session_state:
    st.session_state.categories = []

if "jobs" not in st.session_state:
    st.session_state.jobs = []

if "staff_count" not in st.session_state:
    st.session_state.staff_count = 5

if "work_hours" not in st.session_state:
    st.session_state.work_hours = 8

# ----------------------
# NAVIGATION
# ----------------------
st.sidebar.title("⚙️ Factory Management AI")

page = st.sidebar.radio(
    "Navigate",
    ["Inventory", "Jobs", "Planner", "Staff Settings"],
)

# ============================================================
#              INVENTORY MANAGEMENT UI — PART 2
# ============================================================

if page == "Inventory":

    st.title("📦 Inventory Management")

    st.subheader("➕ Add Category")
    new_cat = st.text_input("Enter new category name")

    if st.button("Add Category"):
        if new_cat.strip() == "":
            st.warning("Category cannot be empty.")
        elif new_cat in st.session_state.categories:
            st.warning("Category already exists!")
        else:
            st.session_state.categories.append(new_cat)
            st.success(f"Category '{new_cat}' added!")

    st.markdown("---")

    st.subheader("➕ Add Inventory Item")

    col1, col2 = st.columns(2)
    with col1:
        item_name = st.text_input("Item Name")

    with col2:
        category = st.selectbox(
            "Select Category",
            ["None"] + st.session_state.categories
        )

    col3, col4 = st.columns(2)
    with col3:
        weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)

    with col4:
        quantity = st.number_input("Quantity", min_value=0, value=1)

    size = st.text_input("Size (e.g. 32 or 50x70 cm)")

    if st.button("Add Inventory"):
        if item_name.strip() == "":
            st.warning("Item name cannot be empty.")
        else:
            st.session_state.inventory.append({
                "name": item_name,
                "category": category if category != "None" else "",
                "weight": weight,
                "quantity": quantity,
                "size": size,
            })
            st.success("Item added successfully!")

    st.markdown("---")
    st.subheader("📋 Inventory List")

    if len(st.session_state.inventory) == 0:
        st.info("No inventory added yet.")
    else:
        for i, item in enumerate(st.session_state.inventory):
            with st.container():
                colA, colB, colC, colD, colDel = st.columns([2, 2, 2, 2, 1])

                colA.write(f"**{item['name']}**")
                colB.write(item["category"] if item["category"] else "—")
                colC.write(f"{item['weight']} kg")
                colD.write(f"Qty: {item['quantity']}  |  Size: {item['size']}")

                # Delete Button
                if colDel.button("🗑️", key=f"del_{i}"):
                    st.session_state.inventory.pop(i)
                    st.experimental_rerun()
# ============================================================
#                    JOBS PAGE — PART 3
# ============================================================

elif page == "Jobs":

    st.title("🧾 Jobs & Processes")

    st.subheader("➕ Add Job")

    job_name = st.text_input("Job Name")
    due_date = st.date_input("Due Date")

    num_proc = st.slider("Number of Processes", 1, 20, 1)

    processes = []

    for i in range(num_proc):
        st.markdown(f"### Process {i+1}")

        col1, col2 = st.columns(2)
        with col1:
            pname = st.text_input(f"Process {i+1} Name", key=f"pname_{i}")
        with col2:
            hours = st.number_input(
                f"Hours for Process {i+1}",
                min_value=0.5, step=0.5, value=1.0,
                key=f"phours_{i}"
            )

        workers = st.number_input(
            f"Workers needed (Process {i+1})",
            min_value=1, value=1,
            key=f"pworkers_{i}"
        )

        # Material linking (optional)
        category = st.selectbox(
            f"Category (optional) for Process {i+1}",
            ["None"] + st.session_state.categories,
            key=f"pcat_{i}"
        )

        inventory_item = None
        size = None

        if category != "None":
            # Filter inventory for this category
            items = [
                inv["name"] for inv in st.session_state.inventory
                if inv["category"] == category
            ]
            sizes = [
                inv["size"] for inv in st.session_state.inventory
                if inv["category"] == category
            ]

            inventory_item = st.selectbox(
                f"Inventory Item (optional) for Process {i+1}",
                ["None"] + items,
                key=f"pitem_{i}"
            )
            if inventory_item == "None":
                inventory_item = None

            size = st.selectbox(
                f"Size (optional) for Process {i+1}",
                ["None"] + sizes,
                key=f"psize_{i}"
            )
            if size == "None":
                size = None

        machine = st.text_input(
            f"Machine (optional) for Process {i+1}",
            key=f"pmachine_{i}"
        )

        processes.append({
            "name": pname,
            "hours": float(hours),
            "workers": int(workers),
            "category": category if category != "None" else None,
            "inventory_item": inventory_item,
            "size": size,
            "machine": machine
        })

        st.markdown("---")

    if st.button("Save Job"):
        if not job_name.strip():
            st.warning("Job name is required.")
        elif any(p["name"].strip() == "" for p in processes):
            st.warning("All process names are required.")
        else:
            st.session_state.jobs.append({
                "name": job_name,
                "due": due_date,
                "processes": processes
            })
            st.success("Job saved!")
            st.experimental_rerun()

    st.markdown("### Existing Jobs")
    if len(st.session_state.jobs) == 0:
        st.info("No jobs added yet.")
    else:
        for j_idx, job in enumerate(st.session_state.jobs):
            with st.expander(f"📦 {job['name']} — Due {job['due']}"):
                st.write(f"**Total Processes:** {len(job['processes'])}")
                for p in job["processes"]:
                    mat = "No material linked"
                    if p["category"] and p["inventory_item"]:
                        mat = f"{p['category']} → {p['inventory_item']} ({p['size']})"
                    st.write(
                        f"- **{p['name']}** — {p['hours']} hrs, "
                        f"Workers: {p['workers']}, Machine: {p['machine'] or '—'}, "
                        f"Material: {mat}"
                    )

                if st.button("Delete Job", key=f"del_job_{j_idx}"):
                    st.session_state.jobs.pop(j_idx)
                    st.experimental_rerun()


# ============================================================
#              PLANNER ENGINE (FUNCTION)
# ============================================================

def plan_schedule(jobs, inventory, staff_count, work_hours):
    # Workday setup
    work_start = datetime.combine(datetime.today().date(), datetime.strptime("09:00", "%H:%M").time())
    break_start = datetime.combine(datetime.today().date(), datetime.strptime("13:00", "%H:%M").time())
    break_end = datetime.combine(datetime.today().date(), datetime.strptime("14:00", "%H:%M").time())

    # Staff timelines
    staff_free = [work_start for _ in range(staff_count)]
    staff_end = [work_start + timedelta(hours=work_hours) for _ in range(staff_count)]
    staff_used = [0.0 for _ in range(staff_count)]

    # Inventory snapshot (so we don't mutate original)
    inv_snapshot = [
        {
            "name": inv["name"],
            "category": inv["category"],
            "size": str(inv["size"]),
            "quantity": inv["quantity"],
        }
        for inv in inventory
    ]

    def find_material(cat, item, size):
        for inv in inv_snapshot:
            if (
                inv["category"] == cat and
                inv["name"] == item and
                inv["size"] == str(size) and
                inv["quantity"] > 0
            ):
                return inv
        return None

    tasks = []

    # Sort jobs by due date
    sorted_jobs = sorted(jobs, key=lambda j: j["due"])

    for job in sorted_jobs:
        for p in job["processes"]:
            hours = p["hours"]
            workers_req = p["workers"]

            # 1) MATERIAL CHECK (if linked)
            inv_match = None
            if p["category"] and p["inventory_item"] and p["size"]:
                inv_match = find_material(p["category"], p["inventory_item"], p["size"])
                if inv_match is None:
                    tasks.append({
                        "Job": job["name"],
                        "Process": p["name"],
                        "Hours": hours,
                        "Workers": workers_req,
                        "Start": "",
                        "End": "",
                        "Machine": p["machine"],
                        "Status": "BLOCKED: NO MATERIAL"
                    })
                    continue

            # 2) STAFF CAPACITY CHECK
            if workers_req > staff_count:
                tasks.append({
                    "Job": job["name"],
                    "Process": p["name"],
                    "Hours": hours,
                    "Workers": workers_req,
                    "Start": "",
                    "End": "",
                    "Machine": p["machine"],
                    "Status": "NOT SCHEDULED: NEED MORE STAFF"
                })
                continue

            # 3) FIND EARLIEST GROUP OF STAFF
            staff_indices = list(range(staff_count))
            staff_indices.sort(key=lambda i: staff_free[i])
            group = staff_indices[:workers_req]

            start_time = max(staff_free[i] for i in group)

            # handle lunch break
            if start_time < break_start and start_time + timedelta(hours=hours) > break_start:
                start_time = break_end

            end_time = start_time + timedelta(hours=hours)

            # capacity per staff
            if any(end_time > staff_end[i] for i in group):
                tasks.append({
                    "Job": job["name"],
                    "Process": p["name"],
                    "Hours": hours,
                    "Workers": workers_req,
                    "Start": "",
                    "End": "",
                    "Machine": p["machine"],
                    "Status": "NO CAPACITY"
                })
                continue

            # 4) CONSUME MATERIAL (1 unit per process)
            if inv_match is not None:
                inv_match["quantity"] -= 1

            # 5) ASSIGN TO STAFF GROUP
            for i in group:
                staff_free[i] = end_time
                staff_used[i] += hours

            staff_str = ", ".join(str(i + 1) for i in group)

            tasks.append({
                "Job": job["name"],
                "Process": p["name"],
                "Hours": hours,
                "Workers": workers_req,
                "Start": start_time.strftime("%I:%M %p"),
                "End": end_time.strftime("%I:%M %p"),
                "Machine": p["machine"],
                "Status": f"SCHEDULED (Staff {staff_str})"
            })

    total_used = sum(staff_used)
    total_capacity = staff_count * work_hours
    return tasks, total_used, total_capacity


# ============================================================
#              PLANNER PAGE — PART 3
# ============================================================

elif page == "Planner":

    st.title("🧠 AI Daily Planner")

    st.write(f"👷 Staff available: **{st.session_state.staff_count}**")
    st.write(f"⏱ Hours per staff: **{st.session_state.work_hours}**")

    if st.button("Generate Today's Plan"):
        tasks, used, cap = plan_schedule(
            st.session_state.jobs,
            st.session_state.inventory,
            st.session_state.staff_count,
            st.session_state.work_hours
        )

        st.success(f"Planned {len(tasks)} tasks — Used {used:.1f}/{cap:.1f} hours")

        if tasks:
            df = pd.DataFrame(tasks)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No tasks could be scheduled.")
    else:
        st.info("Click the button to generate today's plan.")


# ============================================================
#              STAFF SETTINGS PAGE — PART 3
# ============================================================

elif page == "Staff Settings":

    st.title("👷 Staff Settings")

    st.session_state.staff_count = st.number_input(
        "Total Staff",
        min_value=1,
        value=st.session_state.staff_count
    )

    st.session_state.work_hours = st.number_input(
        "Working Hours per Staff",
        min_value=1,
        value=st.session_state.work_hours
    )

    st.success("Staff settings updated. Go to the Planner page to use them.")
