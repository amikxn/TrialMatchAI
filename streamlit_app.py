import streamlit as st
import pandas as pd
import json
import pdfplumber
import os

# Branding
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬")

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
# Load Data
# -----------------------------
patients = load_data()
trials = load_trials()

# -----------------------------
# Top Stats
# -----------------------------
st.header("Top Stats")
st.markdown(f"- Total Patients: **{len(patients)}**")
mutation_counts = patients['mutation_status'].value_counts()
st.bar_chart(mutation_counts)

# -----------------------------
# TABS UI
# -----------------------------
tab1, tab2, tab3 = st.tabs(["Patient-Trial Matches", "Trial-Centric Matches", "Upload Trial PDF"])

with tab1:
    st.header("Patient-Trial Matches")
    selected_patient = st.selectbox("Select a Patient ID", patients["patient_id"])
    if selected_patient:
        patient_row = patients[patients["patient_id"] == selected_patient].iloc[0]
        st.write("### Patient Info")
        st.write(patient_row)

        st.write("### Matching Trials")
        matched_trials = []
        for trial_file, trial in trials.items():
            is_match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
            if is_match:
                matched_trials.append((trial["title"], reasons))
            else:
                matched_trials.append((trial["title"], reasons))

        for title, reasons in matched_trials:
            if "Meets all inclusion criteria" in reasons:
                st.success(f"Trial '{title}' - Match")
            else:
                st.error(f"Trial '{title}' - No match")
            st.write("Reasons:")
            for r in reasons:
                st.write(f"- {r}")

with tab2:
    st.header("Trial-Centric Patient Matches")
    selected_trial_file = st.selectbox("Select a Trial JSON", list(trials.keys()))
    trial = trials[selected_trial_file]

    st.write(f"Trial: {trial['title']}")
    st.json(trial["criteria"])

    st.write("#### Matching Patients:")
    matched = []
    for _, patient in patients.iterrows():
        is_match, reasons = match_patient_to_trial(patient, trial["criteria"])
        if is_match:
            matched.append((patient["patient_id"], reasons))

    if matched:
        for pid, reasons in matched:
            st.success(f"Patient {pid} matches")
            st.write("Reasons:")
            for r in reasons:
                st.write(f"- {r}")
    else:
        st.warning("No matching patients found.")

with tab3:
    st.header("Upload Trial PDF to Extract Criteria")
    uploaded_file = st.file_uploader("Upload a trial PDF", type=["pdf"])
    if uploaded_file:
        with open("temp_trial.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        inclusion, exclusion = extract_criteria_from_pdf("temp_trial.pdf")

        st.subheader("Inclusion Criteria")
        if inclusion:
            for i, crit in enumerate(inclusion, 1):
                st.write(f"{i}. {crit}")
        else:
            st.write("No inclusion criteria found.")

        st.subheader("Exclusion Criteria")
        if exclusion:
            for i, crit in enumerate(exclusion, 1):
                st.write(f"{i}. {crit}")
        else:
            st.write("No exclusion criteria found.")

# Footer
st.write("---")
st.caption("Powered by TrialMatch AI")
