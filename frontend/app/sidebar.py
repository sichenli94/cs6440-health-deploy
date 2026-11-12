import os
import re
import pandas as pd
import streamlit as st

from data import load_patients
from fhir_json_convertor import parse_fhir_bundle_to_df

import json
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import insert


ALL_AGES = "All Ages"
ALL_GENDERS = "All Genders"
ALL_RISKS = "All Risk Levels"


def _patients_for_filters() -> pd.DataFrame:
    """Use the same display categories for filter options and comparisons."""
    df = load_patients().copy()
    df["age_group"] = (
        df["age_group"].astype("string").str.strip()
        .fillna("Unknown").replace("", "Unknown")
    )
    df["gender"] = (
        df["gender"].astype("string").str.strip().str.lower()
        .map({"male": "Male", "female": "Female", "other": "Other", "unknown": "Unknown"})
        .fillna("Unknown")
    )
    return df


def _age_sort_key(label: str) -> tuple:
    match = re.search(r"\d+", label)
    return (int(match.group()) if match else float("inf"), label)


def _clear_filters() -> None:
    st.session_state["age_group"] = ALL_AGES
    st.session_state["gender"] = ALL_GENDERS
    st.session_state["risk_level"] = ALL_RISKS


def upload_bundle_to_database(uploaded_file) -> tuple[list[str], list[str]]:
    """Insert new patients; return inserted and already-existing patient IDs."""
    # The same file can be submitted again without resetting the uploader.
    uploaded_file.seek(0)
    bundle_data = json.load(uploaded_file)

    df = parse_fhir_bundle_to_df(bundle_data)

    if df is None or df.empty:
        raise ValueError("No eligible patient records were found in this file.")

    if "patient_id" not in df or df["patient_id"].isna().any():
        raise ValueError("Every patient must have a patient ID.")
    if not df["patient_id"].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
        raise ValueError("Every patient must have a nonempty patient ID.")
    df = df.drop_duplicates(subset="patient_id")
    patient_ids = df["patient_id"].tolist()

    db_url = os.environ.get("DB_URL")
    if not db_url:
        db_url = st.secrets["DB_URL"]

    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            table = Table("diabetic_encounters", MetaData(), autoload_with=conn)
            # Let PostgreSQL handle conflicts atomically, including simultaneous uploads.
            statement = (
                insert(table).values(df.to_dict(orient="records"))
                .on_conflict_do_nothing(index_elements=[table.c.patient_id])
                .returning(table.c.patient_id)
            )
            inserted_ids = list(conn.execute(statement).scalars())
        inserted_set = set(inserted_ids)
        existing_ids = [patient_id for patient_id in patient_ids if patient_id not in inserted_set]
        return inserted_ids, existing_ids
    finally:
        engine.dispose()

def render_sidebar() -> None:
    st.sidebar.subheader("Upload FHIR JSON Bundle")
    uploaded_file = st.sidebar.file_uploader(
        "Drag and drop your FHIR JSON bundle here",
        type=["json"],
        key="fhir_bundle",
    )
    st.sidebar.caption("Supported format: .json (FHIR Bundle).")
    upload_clicked = st.sidebar.button("Upload to Database", disabled=uploaded_file is None)
    if upload_clicked:
        try:
            with st.sidebar:
                with st.spinner("Processing file and adding new patients to the database…"):
                    inserted_ids, existing_ids = upload_bundle_to_database(uploaded_file)
            if existing_ids:
                if len(existing_ids) == 1:
                    st.sidebar.info(f"Patient {existing_ids[0]} is already in the database.")
                else:
                    st.sidebar.info(f"{len(existing_ids)} patients are already in the database and were skipped.")
            if inserted_ids:
                load_patients.clear()
                # Filters are rendered below, so resetting them here shows the new cohort.
                _clear_filters()
                if len(inserted_ids) == 1:
                    st.sidebar.success(f"Patient {inserted_ids[0]} was successfully added.")
                else:
                    st.sidebar.success(f"{len(inserted_ids)} patients were successfully added.")
            # Continue this run: the dashboard reads fresh data and messages stay visible.
        except Exception as e:
            st.sidebar.error(f"Upload failed: {e}")

    st.sidebar.subheader("Filters")
    patients = _patients_for_filters()
    age_options = [ALL_AGES, *sorted(patients["age_group"].unique(), key=_age_sort_key)]
    gender_options = [
        ALL_GENDERS,
        *[label for label in ("Male", "Female", "Other", "Unknown")
          if label in patients["gender"].values],
    ]
    # Reset obsolete selections after a database refresh or category change.
    for key, options in (("age_group", age_options), ("gender", gender_options)):
        if st.session_state.get(key) not in options:
            st.session_state[key] = options[0]
    st.sidebar.selectbox("Age Group", age_options, key="age_group")
    st.sidebar.selectbox("Gender", gender_options, key="gender")
    st.sidebar.selectbox(
        "Risk Level", [ALL_RISKS, "High Risk", "Medium Risk", "Low Risk"], key="risk_level"
    )
    st.sidebar.button("Clear Filters", on_click=_clear_filters)


def get_filtered_patients() -> pd.DataFrame:
    df = _patients_for_filters()
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
