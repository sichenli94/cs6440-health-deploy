import numpy as np
import pandas as pd
import streamlit as st

AGE_BINS = [0, 30, 40, 50, 60, 70, 200]
AGE_LABELS = ["< 30", "30–39", "40–49", "50–59", "60–69", "≥ 70"]
RISK_LEVELS = ["High Risk", "Medium Risk", "Low Risk"]
DIAGNOSES = [
    "Type 2 Diabetes",
    "Type 1 Diabetes",
    "Diabetes with CKD",
    "Diabetes with CHF",
    "Diabetes with HTN",
    "Gestational Diabetes",
]


@st.cache_data
def load_patients() -> pd.DataFrame:
    # Placeholder data; replaced by FHIR parsing and PostgreSQL in Weeks 2-3.
    rng = np.random.default_rng(42)
    n = 125
    df = pd.DataFrame({
        "patient_id": [f"PT-{i:03d}" for i in range(1, n + 1)],
        "age": rng.integers(18, 90, n),
        "gender": rng.choice(["Male", "Female"], n, p=[0.56, 0.44]),
        "primary_diagnosis": rng.choice(DIAGNOSES, n),
        "hba1c": np.round(rng.normal(8.1, 1.3, n).clip(5.5, 14.0), 1),
        "length_of_stay": np.round(rng.gamma(4.0, 1.4, n), 1),
        "readmission_risk": np.round(rng.uniform(0.05, 0.95, n), 2),
    })
    df["age_group"] = pd.cut(df["age"], AGE_BINS, labels=AGE_LABELS, right=False).astype(str)
    df["risk_level"] = np.select(
        [df["readmission_risk"] >= 0.70, df["readmission_risk"] >= 0.40],
        ["High Risk", "Medium Risk"],
        default="Low Risk",
    )
    return df
