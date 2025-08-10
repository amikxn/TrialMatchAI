import streamlit as st
import pandas as pd
import json
import os
import pdfplumber

# -------------------------------
# Branding & Page Config
# -------------------------------
st.set_page_config(page_title="TrialMatch AI", page_icon="🧬", layout="wide")

PRIMARY_COLOR = "#006e96"
TAGLINE = "Where advanced AI meets precision oncology — matching every NSCLC patient to the right trial."

# Custom CSS for branding
st.markdown(f"""
    <style>
        .main {{ background-color: #f8f9fa; }}
        .hero {{
            background-color: {PRIMARY_COLOR};
            padding: 2rem;
            border-radius: 0.5rem;
            text-align: center;
        }}
        .hero h1 {{
            color: white;
            margin-bottom: 0.5rem;
        }}
        .hero p {{
            color: white;
            font-size: 1.2rem;
            margin: 0;
        }}
        .stat-card {{
            background-color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 1.5rem;
            font-weight: bold;
            color: {PRIMARY_COLOR};
        }}
    </style>
""", unsafe_allow_html=True)

# Hero Banner
st.markdown(f"""
<div class="hero">
    <h1>TrialMatch AI</h1>
    <p>{TAGLINE}</p>
</div>
""", unsafe_allow_html=True)

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
# Stat Cards
# -------------------------------
col1, col2, col3 = st.columns(3)
col1.markdown(f'<div class="stat-card"><div>Total Patients</div><div class="stat-number">{len(patients)}</div></div>', unsafe_allow_html=True)
col2.markdown(f'<div class="stat-card"><div>Total Trials</div><div class="stat-number">{len(trials)}</div></div>', unsafe_allow_html=True)
match_rate = 0  # can be calculated dynamically if desired
col3.markdown(f'<div class="stat-card"><div>Match Rate</div><div class="stat-number">{match_rate}%</div></div>', unsafe_allow_html=True)

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
# PDF Extraction
# -------------------------------
def extract_criteria_from_pdf(pdf_path):
    inclusion, exclusion = [], []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split("\n"):
                    lower_line = line.lower()
                    if "inclusion" in lower_line:
                        inclusion.append(line.strip())
                    elif "exclusion" in lower_line:
                        exclusion.append(line.strip())
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
    return inclusion, exclusion

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

# PDF Upload View
with tab3:
    st.subheader("Upload Trial PDF to Extract Criteria")
    uploaded_file = st.file_uploader("Upload a trial PDF", type=["pdf"])
    if uploaded_file:
        temp_path = "temp_trial.pdf"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        inclusion, exclusion = extract_criteria_from_pdf(temp_path)

        st.markdown("### Inclusion Criteria")
        if inclusion:
            for i, crit in enumerate(inclusion, 1):
                st.write(f"{i}. {crit}")
        else:
            st.write("No inclusion criteria found.")

        st.markdown("### Exclusion Criteria")
        if exclusion:
            for i, crit in enumerate(exclusion, 1):
                st.write(f"{i}. {crit}")
        else:
            st.write("No exclusion criteria found.")

st.write("---")
st.caption("Powered by TrialMatch AI")

