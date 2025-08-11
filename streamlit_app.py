import streamlit as st
import pandas as pd
import json
import pdfplumber
import os
import openai
import matplotlib.pyplot as plt

# Branding
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬", layout="wide")

st.title("Welcome to TrialMatch AI")
st.write("Your AI-powered clinical trial matching platform for NSCLC patients.")

# -----------------------------
# Data Loading Functions
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

# -----------------------------
# Matching Logic with Explanation
# -----------------------------
def match_patient_to_trial(patient, trial_criteria):
    reasons = []

    # Stage check
    if "stage" in trial_criteria and patient["stage"] not in trial_criteria["stage"]:
        reasons.append(f"Patient stage {patient['stage']} not in allowed stages {trial_criteria['stage']}")
        return False, reasons

    # Mutation check
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

    # Performance status check
    if patient["performance_status"] > trial_criteria.get("performance_status_max", 2):
        reasons.append(f"Performance status {patient['performance_status']} exceeds max {trial_criteria.get('performance_status_max', 2)}")
        return False, reasons

    reasons.append("Meets all inclusion criteria")
    return True, reasons

# -----------------------------
# PDF Parsing Function
# -----------------------------
def extract_criteria_from_pdf(pdf_path):
    inclusion = []
    exclusion = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
            for line in lines:
                low = line.lower()
                if "inclusion" in low:
                    inclusion.append(line.strip())
                elif "exclusion" in low:
                    exclusion.append(line.strip())
    return inclusion, exclusion

# -----------------------------
# AI-Powered PDF Interpretation
# -----------------------------
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

# -----------------------------
# Load Data
# -----------------------------
patients = load_data()
trials = load_trials()

# -----------------------------
# Top Stats (Make sure this stays above the tabs)
# -----------------------------
st.header("Top Stats")
st.markdown(f"- Total Patients: **{len(patients)}**")
st.markdown(f"- Total Trials: **{len(trials)}**")

mutation_counts = patients['mutation_status'].value_counts()
st.bar_chart(mutation_counts)

# -----------------------------
# Local Storage for Comments/Status/Notes
# -----------------------------
if 'comments' not in st.session_state:
    st.session_state['comments'] = {}  # key: (patient_id, trial_title), value: dict with comment & status

if 'compliance_log' not in st.session_state:
    st.session_state['compliance_log'] = []

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Patient-Centric View", 
    "🧪 Trial-Centric View", 
    "📄 Upload Trial PDF", 
    "🗂️ Collaboration & Logs"
])

# --- Patient-Centric View ---
with tab1:
    selected_patient = st.selectbox("Select a Patient ID", patients["patient_id"])
    patient_row = patients[patients["patient_id"] == selected_patient].iloc[0]
    st.subheader("Patient Info")
    st.write(patient_row)

    st.subheader("Matching Trials")

    matched_trials = []
    for trial_file, trial in trials.items():
        is_match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
        matched_trials.append({
            "trial_title": trial["title"],
            "is_match": is_match,
            "reasons": reasons
        })
        with st.expander(f"{'✅' if is_match else '❌'} {trial['title']}"):
            for r in reasons:
                st.write("- " + r)

            # Comments and status input
            key = (selected_patient, trial["title"])
            comment_key = f"comment_{selected_patient}_{trial['title']}"
            status_key = f"status_{selected_patient}_{trial['title']}"

            comment = st.text_area("Add comment or notes:", key=comment_key, value=st.session_state['comments'].get(key, {}).get("comment", ""))
            status = st.selectbox("Set status:", ["Not Reviewed", "Reviewed", "Rejected", "Accepted"], key=status_key, index=["Not Reviewed", "Reviewed", "Rejected", "Accepted"].index(st.session_state['comments'].get(key, {}).get("status", "Not Reviewed")))

            # Save to session_state on change
            st.session_state['comments'][key] = {"comment": comment, "status": status}

    # Export matched patients for the selected patient (just one row)
    export_df = pd.DataFrame([{
        "patient_id": selected_patient,
        "trial_title": m["trial_title"],
        "match": m["is_match"],
        "reasons": "; ".join(m["reasons"]),
        "comment": st.session_state['comments'].get((selected_patient, m["trial_title"]), {}).get("comment", ""),
        "status": st.session_state['comments'].get((selected_patient, m["trial_title"]), {}).get("status", "")
    } for m in matched_trials])

    st.download_button(
        label="Export Patient Matches (CSV)",
        data=export_df.to_csv(index=False),
        file_name=f"patient_{selected_patient}_matches.csv",
        mime="text/csv"
    )

# --- Trial-Centric View ---
with tab2:
    selected_trial_file = st.selectbox("Select a Trial JSON", list(trials.keys()))
    trial = trials[selected_trial_file]
    st.subheader(f"Trial: {trial['title']}")
    st.json(trial["criteria"])

    st.subheader("Matching Patients")

    matched_patients = []
    for _, patient in patients.iterrows():
        is_match, reasons = match_patient_to_trial(patient, trial["criteria"])
        if is_match:
            matched_patients.append(patient["patient_id"])
            with st.expander(f"✅ Patient {patient['patient_id']}"):
                for r in reasons:
                    st.write("- " + r)

    # Export matched patients for selected trial
    export_trial_df = patients[patients["patient_id"].isin(matched_patients)]
    st.download_button(
        label="Export Matched Patients for Trial (CSV)",
        data=export_trial_df.to_csv(index=False),
        file_name=f"trial_{trial['title'].replace(' ', '_')}_matched_patients.csv",
        mime="text/csv"
    )

# --- PDF Upload View (AI-powered) ---
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

# --- Collaboration & Logs Tab ---
with tab4:
    st.subheader("Collaboration & Notes")

    # Display existing comments and statuses
    if st.session_state['comments']:
        st.write("### Comments & Status per Patient-Trial Match")
        for (patient_id, trial_title), data in st.session_state['comments'].items():
            st.markdown(f"**Patient {patient_id} — Trial: {trial_title}**")
            st.write(f"- Status: {data.get('status', '')}")
            st.write(f"- Comment: {data.get('comment', '')}")
            st.write("---")
    else:
        st.write("No comments or statuses added yet.")

    st.subheader("Compliance & Audit Logs")
    st.write("This section will track actions for compliance and audit purposes.")
    if st.button("Add sample compliance log entry"):
        st.session_state['compliance_log'].append({
            "action": "Sample log entry",
            "timestamp": pd.Timestamp.now().isoformat()
        })

    if st.session_state['compliance_log']:
        for entry in st.session_state['compliance_log']:
            st.write(f"{entry['timestamp']}: {entry['action']}")
    else:
        st.write("No compliance logs recorded yet.")

st.write("---")
st.caption("Powered by TrialMatch AI")
