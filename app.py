import streamlit as st
import pandas as pd
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Factory Management App",
    layout="wide",
)

st.title("🏭 Factory Management Dashboard")


# ============================================================
# FIREBASE INITIALIZATION (USING st.secrets)
# ============================================================
@st.cache_resource
def init_firestore():
    """
    Initialize Firebase Admin SDK & return Firestore client.
    Expects firebase service account JSON in st.secrets["firebase"].
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


db = init_firestore()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def add_job(job_data: dict):
    """Add a new job document to Firestore."""
    db.collection("jobs").add(job_data)


def get_jobs():
    """Fetch all jobs from Firestore as list of dicts."""
    docs = db.collection("jobs").order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        rows.append(data)
    return rows


def update_job(doc_id: str, updated_data: dict):
    db.collection("jobs").document(doc_id).update(updated_data)


def delete_job(doc_id: str):
    db.collection("jobs").document(doc_id).delete()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Add New Job", "View / Manage Jobs", "Summary"],
)


# ============================================================
# PAGE: ADD NEW JOB
# ============================================================
if page == "Add New Job":
    st.subheader("➕ Add New Job")

    with st.form("add_job_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            job_name = st.text_input("Job Name *")
            client_name = st.text_input("Client Name")
            quantity = st.number_input("Quantity", min_value=0, step=1, value=0)
            amount = st.number_input("Amount (₹)", min_value=0.0, step=100.0, value=0.0)

        with col2:
            job_type = st.selectbox(
                "Job Type",
                ["Box Making", "Printing", "Die Cutting", "Pasting", "Other"],
            )
            status = st.selectbox(
                "Status",
                ["Pending", "In Progress", "Completed", "On Hold"],
            )
            due_date = st.date_input("Due Date (optional)", value=None)
            phone = st.text_input("Client Phone")

        notes = st.text_area("Notes / Details")

        submitted = st.form_submit_button("Save Job")

        if submitted:
            if not job_name:
                st.error("Job Name is required.")
            else:
                job_data = {
                    "job_name": job_name,
                    "client_name": client_name,
                    "job_type": job_type,
                    "quantity": int(quantity),
                    "amount": float(amount),
                    "status": status,
                    "phone": phone,
                    "due_date": due_date.isoformat() if due_date else None,
                    "notes": notes,
                    "created_at": datetime.utcnow(),
                }
                add_job(job_data)
                st.success("✅ Job saved to Firebase!")


# ============================================================
# PAGE: VIEW / MANAGE JOBS
# ============================================================
elif page == "View / Manage Jobs":
    st.subheader("📋 Jobs List")

    jobs = get_jobs()
    if not jobs:
        st.info("No jobs found. Add a job from the ‘Add New Job’ page.")
    else:
        df = pd.DataFrame(jobs)

        # Format for display
        display_df = df.copy()
        if "created_at" in display_df.columns:
            display_df["created_at"] = display_df["created_at"].astype(str)

        st.dataframe(
            display_df[
                [
                    "job_name",
                    "client_name",
                    "job_type",
                    "quantity",
                    "amount",
                    "status",
                    "phone",
                    "due_date",
                    "notes",
                    "created_at",
                    "id",
                ]
            ],
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("✏️ Edit or 🗑️ Delete Job")

        job_ids = df["id"].tolist()
        job_labels = [
            f"{row.job_name} ({row.status}) - {row.id[:6]}"
            for _, row in df.iterrows()
        ]

        selected_index = st.selectbox(
            "Select a job",
            options=list(range(len(job_ids))),
            format_func=lambda i: job_labels[i],
        )

        selected_row = df.iloc[selected_index]
        doc_id = selected_row["id"]

        tab1, tab2 = st.tabs(["Edit", "Delete"])

        with tab1:
            st.write("Update details and click **Save Changes**.")
            with st.form("edit_job_form"):
                col1, col2 = st.columns(2)

                with col1:
                    edit_job_name = st.text_input("Job Name *", value=selected_row.get("job_name", ""))
                    edit_client_name = st.text_input("Client Name", value=selected_row.get("client_name", ""))
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=0,
                        step=1,
                        value=int(selected_row.get("quantity", 0)),
                    )
                    edit_amount = st.number_input(
                        "Amount (₹)",
                        min_value=0.0,
                        step=100.0,
                        value=float(selected_row.get("amount", 0.0)),
                    )

                with col2:
                    edit_job_type = st.selectbox(
                        "Job Type",
                        ["Box Making", "Printing", "Die Cutting", "Pasting", "Other"],
                        index=max(
                            0,
                            ["Box Making", "Printing", "Die Cutting", "Pasting", "Other"].index(
                                selected_row.get("job_type", "Box Making")
                            )
                            if selected_row.get("job_type") in
                               ["Box Making", "Printing", "Die Cutting", "Pasting", "Other"]
                            else 0,
                        ),
                    )
                    edit_status = st.selectbox(
                        "Status",
                        ["Pending", "In Progress", "Completed", "On Hold"],
                        index=max(
                            0,
                            ["Pending", "In Progress", "Completed", "On Hold"].index(
                                selected_row.get("status", "Pending")
                            )
                            if selected_row.get("status") in
                               ["Pending", "In Progress", "Completed", "On Hold"]
                            else 0,
                        ),
                    )
                    edit_phone = st.text_input("Client Phone", value=selected_row.get("phone", ""))
                    # Due date stored as string; leave as text for simplicity
                    edit_due_date = st.text_input(
                        "Due Date (YYYY-MM-DD or blank)",
                        value=selected_row.get("due_date", "") or "",
                    )

                edit_notes = st.text_area("Notes / Details", value=selected_row.get("notes", ""))

                save_btn = st.form_submit_button("Save Changes")

                if save_btn:
                    updated = {
                        "job_name": edit_job_name,
                        "client_name": edit_client_name,
                        "job_type": edit_job_type,
                        "quantity": int(edit_quantity),
                        "amount": float(edit_amount),
                        "status": edit_status,
                        "phone": edit_phone,
                        "notes": edit_notes,
                    }
                    if edit_due_date.strip():
                        updated["due_date"] = edit_due_date.strip()
                    else:
                        updated["due_date"] = None

                    update_job(doc_id, updated)
                    st.success("✅ Job updated successfully! Please refresh the page to see changes.")

        with tab2:
            st.error("This will permanently delete the job.")
            if st.button("🗑️ Delete this job"):
                delete_job(doc_id)
                st.success("🗑️ Job deleted. Please refresh the page to update the list.")


# ============================================================
# PAGE: SUMMARY / DASHBOARD
# ============================================================
elif page == "Summary":
    st.subheader("📊 Summary")

    jobs = get_jobs()
    if not jobs:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(jobs)

        total_jobs = len(df)
        total_pending = (df["status"] == "Pending").sum()
        total_in_progress = (df["status"] == "In Progress").sum()
        total_completed = (df["status"] == "Completed").sum()
        total_amount = df["amount"].sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Jobs", total_jobs)
        c2.metric("Pending", int(total_pending))
        c3.metric("In Progress", int(total_in_progress))
        c4.metric("Completed", int(total_completed))
        c5.metric("Total Amount (₹)", f"{total_amount:,.2f}")

        st.markdown("### Jobs by Status")
        status_counts = df["status"].value_counts()
        st.bar_chart(status_counts)
