import os
import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

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
    db_url = os.environ.get("DB_URL")
    if not db_url:
        db_url = st.secrets["DB_URL"]
        
    engine = create_engine(db_url)

    df = pd.read_sql("SELECT * FROM diabetic_encounters;", engine)

    df = df.rename(columns={
        "time_in_hospital": "length_of_stay",
    })

    df["age_group"] = df["age"]

    rng = np.random.default_rng(42)
    n = len(df)

    df["primary_diagnosis"] = "Type 2 Diabetes"

    df["hba1c"] = df["A1Cresult"]

    df["readmission_risk"] = np.round(rng.uniform(0.05, 0.95, n), 2)
    df["risk_level"] = np.select(
        [df["readmission_risk"] >= 0.70, df["readmission_risk"] >= 0.40],
        ["High Risk", "Medium Risk"],
        default="Low Risk",
    )

    return df
