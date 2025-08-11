import streamlit as st
import pandas as pd
import json
import pdfplumber
import os
import openai
import matplotlib.pyplot as plt
from datetime import datetime
import io

# Branding
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬", layout="wide")
st.title("Welcome to TrialMatch AI")
st.write("Your AI-powered clinical trial matching platform for NSCLC patients.")

# -----------------------------
# Data Loading
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv("sample_patients.csv")

@st.cache_data
def load_trials():
    trials = {}
    for trial_file in ["egfr.json", "pd-l1.json", "kras_g12c.json", "combo.json", "early_stage.json"]:
        try:
            with open(trial_file) as f:
                trials[trial_file] = json.load(f)
        except FileNotFoundError:
            st.error(f"Trial file {trial_file} not found.")
    return trials

patients = load_data()
trials = load_trials()

# -----------------------------
# Matching Logic
# -----------------------------
def match_patient_to_trial(patient, trial_criteria):
    reasons = []
    if "stage" in trial_criteria and patient["stage"] not in trial_criteria["stage"]:
        reasons.append(f"Patient stage {patient['stage']} not in allowed stages {trial_criteria['stage']}")
        return False, reasons

    mutation_required = trial_criteria.get("mutation_required", None)
    if mutation_required:
        if isinstance(mutation_required, list):
            if patient["mutation_status"] not in mutation_required:
                reasons.append(f"Mutation {patient['mutation_status']} not in required list {mutation_required}")
                return False, reasons
        else:
            if patient["mutation_status"] != mutation_required:
                reasons.append(f"Mutation {patient['mutation_status']} does not match required {mutation_required}")
                return False, reasons

    if patient["performance_status"] > trial_criteria.get("performance_status_max", 2):
        reasons.append(f"Performance status {patient['performance_status']} exceeds max {trial_criteria.get('performance_status_max', 2)}")
        return False, reasons

    reasons.append("Meets all inclusion criteria")
    return True, reasons

# -----------------------------
# Initialize session state for comments/status, collaboration notes, audit logs
# -----------------------------
if "match_comments" not in st.session_state:
    # key = (trial_file, patient_id)
    st.session_state.match_comments = {}

if "collab_notes" not in st.session_state:
    # key = trial_file, value = notes string
    st.session_state.collab_notes = {}

if "audit_log" not in st.session_state:
    # list of dicts: {"timestamp": ..., "action": ...}
    st.session_state.audit_log = []

def log_action(action_desc):
    st.session_state.audit_log.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": action_desc})

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📋 Patient-Centric View", "🧪 Trial-Centric View", "📄 Upload Trial PDF", "🗂️ Collaboration & Logs"])

# Patient-Centric View
with tab1:
    selected_patient = st.selectbox("Select a Patient ID", patients["patient_id"])
    patient_row = patients[patients["patient_id"] == selected_patient].iloc[0]
    st.subheader("Patient Info")
    st.write(patient_row)

    st.subheader("Matching Trials")
    for trial_file, trial in trials.items():
        is_match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
        with st.expander(f"{'✅' if is_match else '❌'} {trial['title']}"):
            for r in reasons:
                st.write("- " + r)
            # Comment/status for this match
            key = (trial_file, selected_patient)
            prev_comment = st.session_state.match_comments.get(key, {}).get("comment", "")
            prev_status = st.session_state.match_comments.get(key, {}).get("status", "Not Reviewed")

            comment = st.text_area(f"Comment for {trial['title']} / Patient {selected_patient}", value=prev_comment, key=f"comment_{trial_file}_{selected_patient}")
            status = st.selectbox(f"Status for {trial['title']} / Patient {selected_patient}", options=["Not Reviewed", "Reviewed", "Eligible", "Not Eligible"], index=["Not Reviewed", "Reviewed", "Eligible", "Not Eligible"].index(prev_status), key=f"status_{trial_file}_{selected_patient}")

            if st.button(f"Save Comment & Status for {trial['title']} / Patient {selected_patient}", key=f"save_{trial_file}_{selected_patient}"):
                st.session_state.match_comments[key] = {"comment": comment, "status": status}
                st.success("Saved!")
                log_action(f"Saved comment/status for patient {selected_patient} and trial {trial['title']}")

# Trial-Centric View
with tab2:
    selected_trial_file = st.selectbox("Select a Trial JSON", list(trials.keys()))
    trial = trials[selected_trial_file]
    st.subheader(f"Trial: {trial['title']}")
    st.json(trial["criteria"])

    st.subheader("Matching Patients")
    matched_patients_list = []
    for _, patient in patients.iterrows():
        is_match, reasons = match_patient_to_trial(patient, trial["criteria"])
        if is_match:
            matched_patients_list.append(patient)

            with st.expander(f"✅ Patient {patient['patient_id']}"):
                for r in reasons:
                    st.write("- " + r)
                # Show comment/status for match
                key = (selected_trial_file, patient["patient_id"])
                prev_comment = st.session_state.match_comments.get(key, {}).get("comment", "")
                prev_status = st.session_state.match_comments.get(key, {}).get("status", "Not Reviewed")

                comment = st.text_area(f"Comment for Patient {patient['patient_id']}", value=prev_comment, key=f"trial_comment_{selected_trial_file}_{patient['patient_id']}")
                status = st.selectbox(f"Status for Patient {patient['patient_id']}", options=["Not Reviewed", "Reviewed", "Eligible", "Not Eligible"], index=["Not Reviewed", "Reviewed", "Eligible", "Not Eligible"].index(prev_status), key=f"trial_status_{selected_trial_file}_{patient['patient_id']}")

                if st.button(f"Save Comment & Status for Patient {patient['patient_id']}", key=f"trial_save_{selected_trial_file}_{patient['patient_id']}"):
                    st.session_state.match_comments[key] = {"comment": comment, "status": status}
                    st.success("Saved!")
                    log_action(f"Saved comment/status for patient {patient['patient_id']} and trial {trial['title']}")

    # Export matched patients button
    if matched_patients_list:
        df_matched = pd.DataFrame(matched_patients_list)
        csv = df_matched.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export Matched Patients as CSV",
            data=csv,
            file_name=f"matched_patients_{selected_trial_file.replace('.json','')}.csv",
            mime="text/csv",
        )
        log_action(f"Exported matched patients CSV for trial {trial['title']}")

# PDF Upload View (AI-powered)
openai.api_key = st.secrets["OPENAI_API_KEY"]
def interpret_trial_criteria_llm(text):
    prompt = f"""
    You are a clinical trial document parser. Extract the following from the trial text below:
    - Stage requirements (as list of strings, e.g. ["I", "IIIA"])
    - Required mutations (as list, e.g. ["EGFR", "PD-L1"])
    - Maximum allowed ECOG performance status (integer)
    - Raw inclusion criteria (list of strings)
    - Raw exclusion criteria (list of strings)

    Only return a valid JSON object with the following keys:
    stage, mutation_required, performance_status_max, raw_inclusion, raw_exclusion.

    Trial text:
    {text}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a helpful clinical trial parser."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )

    parsed = response["choices"][0]["message"]["content"]

    try:
        structured = json.loads(parsed)
    except json.JSONDecodeError:
        st.error("Failed to parse JSON from AI output.")
        structured = {}

    return structured

with tab3:
    st.subheader("Upload Trial PDF to Extract & Interpret Criteria (AI-powered)")
    uploaded_file = st.file_uploader("Upload a trial PDF", type=["pdf"])
    if uploaded_file:
        temp_path = "temp_trial.pdf"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with pdfplumber.open(temp_path) as pdf:
            all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        trial_criteria = interpret_trial_criteria_llm(all_text)

        st.markdown("### Structured Criteria Extracted (AI)")
        st.json(trial_criteria)

        st.markdown("### Raw Inclusion Criteria")
        st.write(trial_criteria.get("raw_inclusion", []))

        st.markdown("### Raw Exclusion Criteria")
        st.write(trial_criteria.get("raw_exclusion", []))

# Collaboration & Audit Logs Tab
with tab4:
    st.header("Collaboration & Audit Logs")

    st.subheader("Shared Notes per Trial")
    selected_trial_for_notes = st.selectbox("Select Trial to View/Edit Notes", list(trials.keys()))

    notes = st.session_state.collab_notes.get(selected_trial_for_notes, "")
    updated_notes = st.text_area(f"Notes for {selected_trial_for_notes}", value=notes, height=200)

    if st.button("Save Notes"):
        st.session_state.collab_notes[selected_trial_for_notes] = updated_notes
        st.success("Notes saved!")
        log_action(f"Saved collaboration notes for trial {selected_trial_for_notes}")

    st.subheader("Audit Log")
    if st.session_state.audit_log:
        df_logs = pd.DataFrame(st.session_state.audit_log)
        st.dataframe(df_logs)
    else:
        st.write("No audit log entries yet.")

# Footer
st.write("---")
st.caption("Powered by TrialMatch AI")
