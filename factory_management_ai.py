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

# ============================================================
#                        PLANNER PAGE
# ============================================================
elif page == "Planner":

    st.title("📅 AI Daily Planner")

    if len(st.session_state.jobs) == 0:
        st.info("No jobs added yet.")
        st.stop()

    start_time = datetime.strptime("09:00", "%H:%M")
    lunch_start = datetime.strptime("13:00", "%H:%M")
    lunch_end = datetime.strptime("14:00", "%H:%M")

    schedule = []
    cur_time = start_time

    for job in st.session_state.jobs:
        for p in job["processes"]:
            hrs = p["hours"]
            end_time = cur_time + timedelta(hours=hrs)

            # apply lunch break
            if cur_time < lunch_start < end_time:
                end_time += (lunch_end - lunch_start)

            schedule.append({
                "Job": job["job"],
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
    st.dataframe(df, use_container_width=True)

# ============================================================
#                      STAFF SETTINGS
# ============================================================
elif page == "Staff Settings":
    st.title("👥 Staff Settings")

    st.session_state.staff_count = st.number_input("Total Staff", min_value=1, value=st.session_state.staff_count)
    st.session_state.work_hours = st.number_input("Work Hours per Day", min_value=1, value=st.session_state.work_hours)

    st.success("Settings updated!")
