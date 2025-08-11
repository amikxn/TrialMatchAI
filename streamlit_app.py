import streamlit as st
import pandas as pd
import json
import os
import pdfplumber
import matplotlib.pyplot as plt
import openai

# -------------------------------
# Page Config & Branding
# -------------------------------
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬", layout="wide")
TAGLINE = "Where advanced AI meets precision oncology — matching every NSCLC patient to the right trial."

# -------------------------------
# Load Data
# -------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("sample_patients.csv")

@st.cache_data
def load_trials():
    trials = {}
    for trial_file in ["egfr.json", "pd-l1.json", "kras_g12c.json", "combo.json", "early_stage.json"]:
        if os.path.exists(trial_file):
            with open(trial_file) as f:
                trials[trial_file] = json.load(f)
    return trials

patients = load_data()
trials = load_trials()

# -------------------------------
# Matching Logic
# -------------------------------
def match_patient_to_trial(patient, trial_criteria):
    reasons = []
    is_match = True

    # Stage check
    if "stage" in trial_criteria and patient["stage"] not in trial_criteria["stage"]:
        is_match = False
        reasons.append(f"Stage mismatch: patient is {patient['stage']}")
    else:
        reasons.append(f"Stage match: {patient['stage']}")

    # Mutation check
    mutation_required = trial_criteria.get("mutation_required")
    if mutation_required:
        if isinstance(mutation_required, list):
            if patient["mutation_status"] not in mutation_required:
                is_match = False
                reasons.append(f"Mutation mismatch: patient has {patient['mutation_status']}")
            else:
                reasons.append(f"Mutation match: {patient['mutation_status']}")
        else:
            if patient["mutation_status"] != mutation_required:
                is_match = False
                reasons.append(f"Mutation mismatch: patient has {patient['mutation_status']}")
            else:
                reasons.append(f"Mutation match: {patient['mutation_status']}")

    # Performance status check
    if patient["performance_status"] > trial_criteria.get("performance_status_max", 2):
        is_match = False
        reasons.append(f"Performance status too high: {patient['performance_status']}")
    else:
        reasons.append(f"Performance status acceptable: {patient['performance_status']}")

    return is_match, reasons

# -------------------------------
# AI-Powered PDF Interpretation
# -------------------------------
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

# -------------------------------
# Stat Cards + Graph
# -------------------------------
col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

col1.metric("Total Patients", len(patients))
col2.metric("Total Trials", len(trials))
match_rate = 0
col3.metric("Match Rate", f"{match_rate}%")

# Dark mode–friendly compact graph
mutation_counts = patients['mutation_status'].value_counts()
fig, ax = plt.subplots(figsize=(4, 2))
mutation_counts.plot(kind='bar', color='lightgray', ax=ax)
ax.set_facecolor('none')
fig.patch.set_alpha(0)
ax.set_xlabel("Mutation Status", color='white')
ax.set_ylabel("Patients", color='white')
ax.set_title("Mutation Status", fontsize=10, color='white')
ax.tick_params(axis='x', labelrotation=45, labelsize=8, colors='white')
ax.tick_params(axis='y', labelsize=8, colors='white')
fig.tight_layout()
col4.pyplot(fig)

# -------------------------------
# Tabs
# -------------------------------
tab1, tab2, tab3 = st.tabs(["📋 Patient-Centric View", "🧪 Trial-Centric View", "📄 Upload Trial PDF"])

# Patient-Centric View
with tab1:
    selected_patient = st.selectbox("Select a Patient ID", patients["patient_id"])
    patient_row = patients[patients["patient_id"] == selected_patient].iloc[0]
    st.subheader("Patient Info")
    st.write(patient_row)

    st.subheader("Matching Trials")
    for trial_file, trial in trials.items():
        match, reasons = match_patient_to_trial(patient_row, trial["criteria"])
        with st.expander(f"{'✅' if match else '❌'} {trial['title']}"):
            for r in reasons:
                st.write("- " + r)

# Trial-Centric View
with tab2:
    selected_trial_file = st.selectbox("Select a Trial JSON", list(trials.keys()))
    trial = trials[selected_trial_file]
    st.subheader(f"Trial: {trial['title']}")
    st.json(trial["criteria"])

    st.subheader("Matching Patients")
    for _, patient in patients.iterrows():
        match, reasons = match_patient_to_trial(patient, trial["criteria"])
        if match:
            with st.expander(f"✅ Patient {patient['patient_id']}"):
                for r in reasons:
                    st.write("- " + r)

# PDF Upload View (AI-powered)
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

st.write("---")
st.caption("Powered by TrialMatch AI")
