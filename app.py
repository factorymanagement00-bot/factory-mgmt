import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Factory Manager", layout="wide")

# -------------------------------------------------------------
# FIRESTORE CONFIG  (NO PRIVATE KEY NEEDED)
# -------------------------------------------------------------
PROJECT_ID = "factory-ai-ab9fa"
API_KEY = "YOUR_API_KEY"   # Replace with your Firebase Web API key

BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


# -------------------------------------------------------------
# FIRESTORE FUNCTIONS (REST API)
# -------------------------------------------------------------
def firestore_add(collection, data):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.post(url, json=payload)


def firestore_get(collection):
    url = f"{BASE_URL}/{collection}?key={API_KEY}"
    res = requests.get(url).json()

    if "documents" not in res:
        return []

    documents = []
    for doc in res["documents"]:
        entry = {k: v["stringValue"] for k, v in doc["fields"].items()}
        entry["id"] = doc["name"].split("/")[-1]
        documents.append(entry)

    return documents


def firestore_update(collection, doc_id, data):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    payload = {"fields": {k: {"stringValue": str(v)} for k, v in data.items()}}
    requests.patch(url, json=payload)


def firestore_delete(collection, doc_id):
    url = f"{BASE_URL}/{collection}/{doc_id}?key={API_KEY}"
    requests.delete(url)


# -------------------------------------------------------------
# DEEPSEEK CHATBOT (LIVE — NO STORAGE)
# -------------------------------------------------------------
DEEPSEEK_KEY = "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"   # Replace with your DeepSeek key

def ask_deepseek(prompt):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a factory assistant. Do not store any data."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(url, headers=headers, json=data).json()
    return response["choices"][0]["message"]["content"]


# -------------------------------------------------------------
# UI NAVIGATION
# -------------------------------------------------------------
page = st.sidebar.radio("Navigation", ["Add Job", "View Jobs", "Dashboard", "AI Chatbot"])


# -------------------------------------------------------------
# ADD JOB PAGE
# -------------------------------------------------------------
if page == "Add Job":
    st.title("➕ Add New Factory Job")

    col1, col2 = st.columns(2)

    with col1:
        job_name = st.text_input("Job Name")
        client = st.text_input("Client Name")
        phone = st.text_input("Phone Number")

    with col2:
        amount = st.number_input("Amount ₹", min_value=0)
        status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
        job_type = st.text_input("Job Type (Box / Printing / Other)")

    notes = st.text_area("Notes")

    if st.button("Save Job"):
        data = {
            "job_name": job_name,
            "client_name": client,
            "phone": phone,
            "amount": amount,
            "status": status,
            "job_type": job_type,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat()
        }

        firestore_add("jobs", data)
        st.success("Job saved successfully!")


# -------------------------------------------------------------
# VIEW JOBS PAGE
# -------------------------------------------------------------
elif page == "View Jobs":
    st.title("📋 View & Manage Jobs")

    jobs = firestore_get("jobs")

    if not jobs:
        st.info("No jobs found.")
    else:
        df = pd.DataFrame(jobs)
        st.dataframe(df, use_container_width=True)

        st.subheader("Edit or Delete Job")

        selected_id = st.selectbox("Select Job ID", df["id"])
        job = df[df["id"] == selected_id].iloc[0]

        new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"],
                                  index=["Pending", "In Progress", "Completed"].index(job["status"]))
        new_amount = st.number_input("Amount ₹", min_value=0, value=int(job["amount"]))
        new_notes = st.text_area("Notes", job["notes"])

        if st.button("Update Job"):
            firestore_update("jobs", selected_id, {
                "status": new_status,
                "amount": new_amount,
                "notes": new_notes
            })
            st.success("Job updated!")

        if st.button("Delete Job"):
            firestore_delete("jobs", selected_id)
            st.warning("Job deleted!")


# -------------------------------------------------------------
# DASHBOARD PAGE
# -------------------------------------------------------------
elif page == "Dashboard":
    st.title("📊 Factory Dashboard Summary")

    jobs = firestore_get("jobs")

    if not jobs:
        st.info("No data available.")
    else:
        df = pd.DataFrame(jobs)

        total_jobs = len(df)
        total_amount = sum(int(x) for x in df["amount"])
        pending = (df["status"] == "Pending").sum()
        progress = (df["status"] == "In Progress").sum()
        completed = (df["status"] == "Completed").sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jobs", total_jobs)
        col2.metric("Pending", pending)
        col3.metric("In Progress", progress)
        col4.metric("Completed", completed)

        st.metric("Total Amount ₹", total_amount)


# -------------------------------------------------------------
# AI CHATBOT PAGE
# -------------------------------------------------------------
elif page == "AI Chatbot":
    st.title("🤖 DeepSeek Factory Assistant")
    st.write("Ask anything about factory work. (Does NOT store chats.)")

    user_msg = st.text_input("Your Question:")

    if st.button("Ask AI"):
        answer = ask_deepseek(user_msg)
        st.write("### AI Response:")
        st.write(answer)
