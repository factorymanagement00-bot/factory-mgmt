import streamlit as st
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Factory Management AI", layout="wide")


# -------------------------------------------------
# Initialize Session State Variables
# -------------------------------------------------
if "inventory" not in st.session_state:
    st.session_state.inventory = []

if "categories" not in st.session_state:
    st.session_state.categories = []

if "jobs" not in st.session_state:
    st.session_state.jobs = []

if "staff_count" not in st.session_state:
    st.session_state.staff_count = 5

if "hours_per_staff" not in st.session_state:
    st.session_state.hours_per_staff = 8


# -------------------------------------------------
# ADVANCED DAILY PLANNER (FINAL FIXED VERSION)
# -------------------------------------------------
def plan_today_advanced(jobs, inventory, staff_count, hours_per_staff):
    work_start = datetime.combine(date.today(), datetime.strptime("09:00", "%H:%M").time())
    break_start = datetime.combine(date.today(), datetime.strptime("13:00", "%H:%M").time())
    break_end = datetime.combine(date.today(), datetime.strptime("14:00", "%H:%M").time())

    staff_free = [work_start for _ in range(staff_count)]
    staff_end = [work_start + timedelta(hours=hours_per_staff) for _ in range(staff_count)]
    staff_used = [0.0 for _ in range(staff_count)]

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
                inv["Category"] == cat
                and inv["Item"] == name
                and inv["Size"] == str(size)
                and inv["Quantity"] > 0
            ):
                return inv
        return None

    tasks = []
    sorted_jobs = sorted(jobs, key=lambda j: j["due"])

    for job in sorted_jobs:
        for proc in job["processes"]:
            hours = float(proc["hours"])
            required_workers = max(1, int(proc.get("workers", 1)))

            # MATERIAL CHECK
            inv_match = None
            if proc.get("category") and proc.get("inventory_item") and proc.get("size"):
                inv_match = find_inventory(proc["category"], proc["inventory_item"], proc["size"])
                if inv_match is None:
                    tasks.append({
                        "Job": job["name"],
                        "Process": proc["name"],
                        "Machine": proc.get("machine", ""),
                        "Workers": required_workers,
                        "Hours": hours,
                        "Staff": "",
                        "Start": "",
                        "End": "",
                        "Status": "BLOCKED: No Material",
                    })
                    continue

            if required_workers > staff_count:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": required_workers,
                    "Hours": hours,
                    "Staff": "",
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: Not Enough Staff",
                })
                continue

            staff_indices = list(range(staff_count))
            staff_indices.sort(key=lambda i: staff_free[i])
            group = staff_indices[:required_workers]

            start_time = max(staff_free[i] for i in group)

            if start_time < break_start and start_time + timedelta(hours=hours) > break_start:
                start_time = break_end

            if start_time < work_start:
                start_time = work_start

            end_time = start_time + timedelta(hours=hours)

            can_schedule = True
            for i in group:
                if end_time > staff_end[i]:
                    can_schedule = False

            if not can_schedule:
                tasks.append({
                    "Job": job["name"],
                    "Process": proc["name"],
                    "Machine": proc.get("machine", ""),
                    "Workers": required_workers,
                    "Hours": hours,
                    "Staff": "",
                    "Start": "",
                    "End": "",
                    "Status": "NOT SCHEDULED: No Capacity",
                })
                continue

            if inv_match is not None:
                inv_match["Quantity"] -= 1

            for i in group:
                staff_free[i] = end_time
                staff_used[i] += hours

            staff_str = ", ".join(str(i + 1) for i in group)

            tasks.append({
                "Job": job["name"],
                "Process": proc["name"],
                "Machine": proc.get("machine", ""),
                "Workers": required_workers,
                "Hours": hours,
                "Staff": staff_str,
                "Start": start_time.strftime("%I:%M %p"),
                "End": end_time.strftime("%I:%M %p"),
                "Status": "SCHEDULED",
            })

    return tasks, sum(staff_used), staff_count * hours_per_staff


# -------------------------------------------------
# INVENTORY UI
# -------------------------------------------------
def inventory_ui():
    st.header("Add Inventory Item")
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Item Name")
        category = st.selectbox("Category", ["None"] + st.session_state.categories)
        add_new_cat = st.text_input("Add New Category")

    if add_new_cat:
        if add_new_cat not in st.session_state.categories:
            st.session_state.categories.append(add_new_cat)
        category = add_new_cat

    col3, col4, col5 = st.columns(3)
    with col3:
        weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0)
    with col4:
        qty = st.number_input("Quantity", min_value=0, value=1)
    with col5:
        size = st.text_input("Size")

    if st.button("Add Inventory Item"):
        st.session_state.inventory.append({
            "Item": name,
            "Category": category,
            "Weight": weight,
            "Quantity": qty,
            "Size": size,
        })
        st.success("Item added!")

    st.subheader("Inventory List (with delete)")
    for i, inv in enumerate(st.session_state.inventory):
        colA, colB = st.columns([4, 1])
        with colA:
            st.write(inv)
        with colB:
            if st.button(f"Delete {i}"):
                st.session_state.inventory.pop(i)
                st.experimental_rerun()


# -------------------------------------------------
# JOB UI
# -------------------------------------------------
def jobs_ui():
    st.header("Add Job")

    job_name = st.text_input("Job Name")
    due_date = st.date_input("Due Date")

    num_proc = st.slider("Number of Processes", 1, 10, 1)

    processes = []

    for i in range(num_proc):
        st.subheader(f"Process {i+1}")

        name = st.text_input(f"Process {i+1} Name")
        hours = st.number_input(f"Hours for Process {i+1}", value=1.0)
        workers = st.number_input(f"Workers Needed for Process {i+1}", value=1)

        category = st.selectbox(
            f"Category (optional) {i+1}",["None"] + st.session_state.categories,key=f"cat_{i}"
        )

        inventory_item = "None"
        size = "None"

        if category != "None":
            items = [inv["Item"] for inv in st.session_state.inventory if inv["Category"] == category]
            sizes = [inv["Size"] for inv in st.session_state.inventory if inv["Category"] == category]

            inventory_item = st.selectbox(f"Inventory Item {i+1}", ["None"] + items)
            size = st.selectbox(f"Size {i+1}", ["None"] + sizes)

        machine = st.text_input(f"Machine (optional) {i+1}")

        processes.append({
            "name": name,
            "hours": hours,
            "workers": workers,
            "category": category if category != "None" else None,
            "inventory_item": inventory_item if inventory_item != "None" else None,
            "size": size if size != "None" else None,
            "machine": machine,
        })

    if st.button("Add Job"):
        st.session_state.jobs.append({
            "name": job_name,
            "due": due_date,
            "processes": processes,
        })
        st.success("Job Added!")


# -------------------------------------------------
# PLANNER UI
# -------------------------------------------------
def planner_ui():
    st.header("AI Daily Planner")

    tasks, used, capacity = plan_today_advanced(
        st.session_state.jobs,
        st.session_state.inventory,
        st.session_state.staff_count,
        st.session_state.hours_per_staff
    )

    if st.button("Generate Today's Plan"):
        st.experimental_rerun()

    st.write(f"Using {st.session_state.staff_count} staff × {st.session_state.hours_per_staff} hrs")
    st.write(f"Planned {len(tasks)} processes — Used {used}/{capacity} hours")

    st.table(tasks)


# -------------------------------------------------
# MAIN MENU
# -------------------------------------------------
def main():
    tab1, tab2, tab3 = st.tabs(["Inventory", "Jobs", "Planner"])

    with tab1:
        inventory_ui()

    with tab2:
        jobs_ui()

    with tab3:
        planner_ui()


main()
