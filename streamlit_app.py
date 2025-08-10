import streamlit as st
import pandas as pd
import json
import os
import pdfplumber
import re

# Branding
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬")

st.title("Welcome to TrialMatch AI!")
st.write("Your AI-powered clinical trial matching platform for NSCLC patients.")

@st.cache_data
def load_data():
    patients = pd.read_csv("sample_patients.csv")
    return patients

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

def extract_criteria_from_pdf(pdf_path):
    inclusion = []
    exclusion = []

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

    # Regex to find inclusion/exclusion sections (case-insensitive)
    inclusion_match = re.search(r'Inclusion Criteria(.*?)(Exclusion Criteria|$)', full_text, re.DOTALL | re.IGNORECASE)
    exclusion_match = re.search(r'Exclusion Criteria(.*?)(Inclusion Criteria|$)', full_text, re.DOTALL | re.IGNORECASE)

    if inclusion_match:
        inclusion_text = inclusion_match.group(1).strip()
        inclusion = [line.strip('-• \n') for line in inclusion_text.split('\n') if line.strip()]

    if exclusion_match:
        exclusion_text = exclusion_match.group(1).strip()
        exclusion = [line.strip('-• \n') for line in exclusion_text.split('\n') if line.strip()]

    return inclusion, exclusion

patients = load_data()
trials = load_trials()

# Show top stats
st.header("Top Stats")
st.markdown(f"- Total Patients: **{len(patients)}**")
mutation_counts = patients['mutation_status'].value_counts()
st.markdown("**Mutation Status Distribution:**")
st.bar_chart(mutation_counts)

# Simple matching logic with explanation
def match_patient_to_trial(patient, trial_criteria):
    reasons = []

    # Stage check
    if "stage" in trial_criteria and patient["stage"] not in trial_criteria["stage"]:
        reasons.append(f"Stage {patient['stage']} not in allowed stages {trial_criteria['stage']}")
    
    # Mutation check
    mutation_required = trial_criteria.get("mutation_required", None)
    if mutation_required:
        if isinstance(mutation_required, list):
            if patient["mutation_status"] not in mutation_required:
                reasons.append(f"Mutation {patient['mutation_status']} not in required {mutation_required}")
        else:
            if patient["mutation_status"] != mutation_required:
                reasons.append(f"Mutation {patient['mutation_status']} does not match required {mutation_required}")

    # Performance status check
    if patient["performance_status"] > trial_criteria.get("performance_status_max", 2):
        reasons.append(f"Performance status {patient['performance_status']} exceeds max allowed {trial_criteria.get('performance_status_max', 2)}")

    is_match = len(reasons) == 0
    return is_match, reasons

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
            st.success(f"Match found: {trial['title']}")
        else:
            st.info(f"Trial '{trial['title']}' - No match")
            st.write("Reasons:")
            for r in reasons:
                st.write(f"- {r}")

# Trial-centric view
st.header("Trial-Centric Patient Matches")

selected_trial_file = st.selectbox("Select a Trial JSON", list(trials.keys()))
if selected_trial_file:
    trial = trials[selected_trial_file]
    st.write(f"### Trial: {trial['title']}")
    st.write("#### Criteria:")
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
    else:
        st.warning("No matching patients found.")

# PDF uploader and parser
st.write("**PDF Uploader should appear below:**")
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

st.write("---")
st.caption("Powered by TrialMatch AI")

