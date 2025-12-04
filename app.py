import streamlit as st
import pyrebase
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Factory Management Dashboard", layout="wide")

# -----------------------------------------------------
# FIREBASE CONFIG (NO PRIVATE KEY NEEDED)
# -----------------------------------------------------
firebaseConfig = {
    "apiKey": "YOUR_API_KEY",
    "authDomain": "factory-ai-ab9fa.firebaseapp.com",
    "projectId": "factory-ai-ab9fa",
    "storageBucket": "factory-ai-ab9fa.appspot.com",
    "messagingSenderId": "117527347099932396116",
    "appId": "YOUR_APP_ID",
    "databaseURL": ""
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.firestore()

st.title("🏭 Factory Management Dashboard (No Private Key Needed)")


# -----------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------
def add_job(job):
    db.collection("jobs").add(job)

def get_jobs():
    jobs = db.collection("jobs").get()
    return [ {"id": j.id, **j.to_dict()} for j in jobs ]

def update_job(job_id, new_data):
    db.collection("jobs").document(job_id).update(new_data)

def delete_job(job_id):
    db.collection("jobs").document(job_id).delete()


# -----------------------------------------------------
# SIDEBAR MENU
# -----------------------------------------------------
menu = st.sidebar.radio(
    "Menu",
    ["Add Job", "View Jobs", "Dashboard"]
)


# -----------------------------------------------------
# ADD JOB PAGE
# -----------------------------------------------------
if menu == "Add Job":
    st.header("➕ Add a New Job")

    col1, col2 = st.columns(2)

    with col1:
        job_name = st.text_input("Job Name")
        client_name = st.text_input("Client Name")
        phone = st.text_input("Phone Number")

    with col2:
        amount = st.number_input("Amount (₹)", min_value=0)
        status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
        job_type = st.selectbox("Job Type", ["Box", "Printing", "Die Cutting", "Pasting", "Other"])

    notes = st.text_area("Notes")

    if st.button("Save Job"):
        job_data = {
            "job_name": job_name,
            "client_name": client_name,
            "phone": phone,
            "amount": amount,
            "status": status,
            "job_type": job_type,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat()
        }
        add_job(job_data)
        st.success("✅ Job saved successfully!")


# -----------------------------------------------------
# VIEW JOBS PAGE
# -----------------------------------------------------
elif menu == "View Jobs":
    st.header("📋 All Jobs")

    jobs = get_jobs()

    if len(jobs) == 0:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)

        st.dataframe(df)

        st.subheader("✏️ Edit or Delete Job")

        # Select job
        job_ids = df["id"].tolist()
        selected_job = st.selectbox("Select a job to modify", job_ids)

        job_row = df[df["id"] == selected_job].iloc[0]

        col1, col2 = st.columns(2)

        with col1:
            new_status = st.selectbox(
                "Update Status",
                ["Pending", "In Progress", "Completed"],
                index=["Pending", "In Progress", "Completed"].index(job_row["status"])
            )

            new_amount = st.number_input("Update Amount", min_value=0, value=int(job_row["amount"]))

        with col2:
            new_notes = st.text_area("Update Notes", value=job_row["notes"])

        if st.button("Save Changes"):
            update_job(selected_job, {
                "status": new_status,
                "amount": new_amount,
                "notes": new_notes
            })
            st.success("Updated successfully! Refresh to see changes.")

        if st.button("🗑️ Delete Job"):
            delete_job(selected_job)
            st.warning("Job deleted. Refresh to update list.")


# -----------------------------------------------------
# DASHBOARD PAGE
# -----------------------------------------------------
elif menu == "Dashboard":
    st.header("📊 Summary Dashboard")

    jobs = get_jobs()

    if len(jobs) == 0:
        st.info("No data available.")
    else:
        df = pd.DataFrame(jobs)

        total_jobs = len(df)
        pending = (df["status"] == "Pending").sum()
        progress = (df["status"] == "In Progress").sum()
        completed = (df["status"] == "Completed").sum()
        total_amount = df["amount"].sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jobs", total_jobs)
        col2.metric("Pending", pending)
        col3.metric("In Progress", progress)
        col4.metric("Completed", completed)

        st.metric("💰 Total Amount", f"₹{total_amount}")
