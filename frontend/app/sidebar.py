import os
import pandas as pd
import streamlit as st

from data import AGE_LABELS, load_patients
from fhir_json_convertor import parse_fhir_bundle_to_df

import json
from sqlalchemy import create_engine


ALL_AGES = "All Ages"
ALL_GENDERS = "All Genders"
ALL_RISKS = "All Risk Levels"


def _clear_filters() -> None:
    st.session_state["age_group"] = ALL_AGES
    st.session_state["gender"] = ALL_GENDERS
    st.session_state["risk_level"] = ALL_RISKS


def upload_bundle_to_database(uploaded_file) -> int:
    """Parse the FHIR bundle and store its patients in PostgreSQL; return the number stored."""
    bundle_data = json.load(uploaded_file)

    df = parse_fhir_bundle_to_df(bundle_data)

    if df is None or df.empty:
        return 0

    db_url = os.environ.get("DB_URL")
    if not db_url:
        db_url = st.secrets["DB_URL"]
        
    engine = create_engine(db_url)

    with engine.begin() as conn:
        df.to_sql("diabetic_encounters", con=conn, if_exists="append", index=False)

    return len(df)

def render_sidebar() -> None:
    st.sidebar.subheader("Upload FHIR JSON Bundle")
    uploaded_file = st.sidebar.file_uploader(
        "Drag and drop your FHIR JSON bundle here",
        type=["json"],
        key="fhir_bundle",
    )
    st.sidebar.caption("Supported format: .json (FHIR Bundle). Parsing is added in Week 2.")
    upload_clicked = st.sidebar.button("Upload to Database", disabled=uploaded_file is None)
    if upload_clicked:
        try:
            count = upload_bundle_to_database(uploaded_file)
            st.sidebar.success(f"Stored {count} patients.")

            load_patients.clear()
            st.rerun()
        except NotImplementedError as e:
            st.sidebar.info(str(e))
        except Exception as e:
            st.sidebar.error(f"Upload failed: {e}")

    st.sidebar.subheader("Filters")
    st.sidebar.selectbox("Age Group", [ALL_AGES, *AGE_LABELS], key="age_group")
    st.sidebar.selectbox("Gender", [ALL_GENDERS, "Male", "Female"], key="gender")
    st.sidebar.selectbox(
        "Risk Level", [ALL_RISKS, "High Risk", "Medium Risk", "Low Risk"], key="risk_level"
    )
    st.sidebar.button("Clear Filters", on_click=_clear_filters)


def get_filtered_patients() -> pd.DataFrame:
    df = load_patients()
    age = st.session_state.get("age_group", ALL_AGES)
    gender = st.session_state.get("gender", ALL_GENDERS)
    risk = st.session_state.get("risk_level", ALL_RISKS)

    if age != ALL_AGES:
        df = df[df["age_group"] == age]
    if gender != ALL_GENDERS:
        df = df[df["gender"] == gender]
    if risk != ALL_RISKS:
        df = df[df["risk_level"] == risk]
    return df
