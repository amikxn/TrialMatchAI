import streamlit as st
import pandas as pd
import json

# Branding
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬")

st.title("Welcome to TrialMatch AI")
st.write("Your AI-powered clinical trial matching platform for NSCLC patients.")

# About / Explanation expandable section
with st.expander("About TrialMatch AI - What is this demo?"):
    st.markdown("""
    This app demonstrates **TrialMatch AI**, a clinical trial matching platform designed for Non-Small Cell Lung Cancer (NSCLC) patients.
    
    **Data:**  
    - 200 synthetic NSCLC patients with realistic attributes like age, stage, mutation status, and performance status.  
    - 5 clinical trial criteria JSONs covering different mutation types and stages.
    
    **How matching works:**  
    Patients are matched against trial criteria based on stage, mutation status, and performance status.  
    This demo shows which trials a selected patient qualifies for and explains why,  
    and also which patients qualify for a selected trial.
    
    **How to use:**  
    Use the tabs to switch between:  
    - Patient-centric matching: pick a patient, see matches  
    - Trial-centric matching: pick a trial, see matched patients  
    """)

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

patients = load_data()
trials = load_trials()

# Show top stats
st.header("Top Stats")
st.markdown(f"- Total Patients: **{len(patients)}**")
mutation_counts = patients['mutation_status'].value_counts()
st.markdown("**Mutation Status Distribution:**")
st.bar_chart(mutation_counts)

def match_patient_to_trial(patient, trial_criteria):
    reasons = []
    match = True
    
    # Stage check
    if "stage" in trial_criteria:
        if patient["stage"] not in trial_criteria["stage"]:
            match = False
            reasons.append(f"Stage '{patient['stage']}' not in trial eligible stages {trial_criteria['stage']}.")
        else:
            reasons.append(f"Stage '{patient['stage']}' matches trial eligible stages.")
    
    # Mutation check
    mutation_required = trial_criteria.get("mutation_required", None)
    if mutation_required:
        if isinstance(mutation_required, list):
            if patient["mutation_status"] not in mutation_required:
                match = False
                reasons.append(f"Mutation status '{patient['mutation_status']}' not in required {mutation_required}.")
            else:
                reasons.append(f"Mutation status '{patient['mutation_status']}' matches required mutations.")
        else:
            if patient["mutation_status"] != mutation_required:
                match = False
                reasons.append(f"Mutation status '{patient['mutation_status']}' does not match required '{mutation_required}'.")
            else:
                reasons.append(f"Mutation status '{patient['mutation_status']}' matches required '{mutation_required}'.")
    
    # Performance status check
    max_perf = trial_criteria.get("performance_status_max", 2)
    if patient["performance_status"] > max_perf:
        match = False
        reasons.append(f"Performance status {patient['performance_status']} exceeds max allowed {max_perf}.")
    else:
        reasons.append(f"Performance status {patient['performance_status']} is within allowed max {max_perf}.")
    
    return match, reasons

# Tabs for hybrid view
tab1, tab2 = st.tabs(["Patient View", "Trial View"])

with tab1:
    st.header("Patient-Centric Matching")
    selected_patient = st.selectbox("Select a Patient ID", patients["patient_id"])
    if selected_patient:
        patient_row = patients[patients["patient_id"] == selected_patient].iloc[0]
        st.write("### Patient Info")
        st.write(patient_row)
        
        st.write("### Matching Trials and Explanation")
        found_any = False
        for trial_file, trial in trials.items():
            match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
            if match:
                found_any = True
                st.success(f"Match found: **{trial['title']}**")
            else:
                st.warning(f"No match: **{trial['title']}**")
            
            with st.expander(f"Why {'match' if match else 'no match'}?"):
                for r in reasons:
                    st.write(f"- {r}")
        
        if not found_any:
            st.info("No matching trials found for this patient.")

with tab2:
    st.header("Trial-Centric Matching")
    trial_titles = {trial_file: trial["title"] for trial_file, trial in trials.items()}
    selected_trial_file = st.selectbox("Select a Trial", list(trial_titles.keys()), format_func=lambda x: trial_titles[x])
    if selected_trial_file:
        trial = trials[selected_trial_file]
        st.write("### Trial Criteria (JSON)")
        st.json(trial["criteria"])
        
        st.write("### Matched Patients")
        matched_patients = []
        for _, patient_row in patients.iterrows():
            match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
            if match:
                matched_patients.append((patient_row["patient_id"], patient_row, reasons))
        
        if matched_patients:
            for pid, patient_row, reasons in matched_patients:
                st.success(f"Patient ID: {pid}")
                st.write(patient_row)
                with st.expander("Why match?"):
                    for r in reasons:
                        st.write(f"- {r}")
        else:
            st.warning("No patients matched this trial.")

st.write("---")
st.caption("Powered by TrialMatch AI")


