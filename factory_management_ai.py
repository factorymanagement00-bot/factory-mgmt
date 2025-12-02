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
