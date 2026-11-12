import altair as alt
import pandas as pd
import streamlit as st

from data import RISK_LEVELS
from sidebar import get_filtered_patients

GENDER_COLORS = {"Male": "#3b82f6", "Female": "#f472b6", "Other": "#a78bfa", "Unknown": "#9ca3af"}
RISK_COLORS = {"High Risk": "#ef4444", "Medium Risk": "#facc15", "Low Risk": "#22c55e"}


def donut(data: pd.DataFrame, field: str, colors: dict, title: str) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta("patients:Q"),
            color=alt.Color(
                f"{field}:N",
                scale=alt.Scale(domain=list(colors), range=list(colors.values())),
                legend=alt.Legend(title=None),
            ),
            tooltip=[field, "patients"],
        )
        .properties(title=title, height=260)
    )


st.title("Diabetes Patient Analytics and 30-Day Readmission Prediction")
st.caption("Explore patient data, analyze population trends, and predict readmission risk using FHIR data.")
st.info("Readmission risk predictions are currently randomly generated and will be replaced with machine learning model predictions in a future update.")

df = get_filtered_patients()
if df.empty:
    st.warning("No patients match the selected filters.")
    st.stop()

# Normalize display values without changing the cached database records.
df = df.copy()
df["age_group"] = df["age_group"].astype("string").str.strip().fillna("Unknown").replace("", "Unknown")
df["gender"] = (
    df["gender"].astype("string").str.strip().str.lower()
    .map({"male": "Male", "female": "Female", "other": "Other", "unknown": "Unknown"})
    .fillna("Unknown")
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Patients", len(df))
kpi2.metric("High-Risk Patients", int((df["risk_level"] == "High Risk").sum()))
kpi3.metric("HbA1c", "TBD")
kpi4.metric("Average Length of Stay", f"{df['length_of_stay'].mean():.1f} days")

st.subheader("Population Overview")
age_df = (
    df["age_group"].value_counts()
    .rename("patients").rename_axis("age_group").reset_index()
)
# Sort intervals by their lower bound, including ages 100 and above.
age_df["lower_bound"] = pd.to_numeric(
    age_df["age_group"].str.extract(r"(\d+)", expand=False), errors="coerce"
)
age_df = age_df.sort_values("lower_bound", na_position="last").drop(columns="lower_bound")
age_order = age_df["age_group"].tolist()
gender_df = df["gender"].value_counts().rename_axis("gender").reset_index(name="patients")
gender_colors = {label: color for label, color in GENDER_COLORS.items() if label in gender_df["gender"].values}
risk_df = (
    df["risk_level"].value_counts().reindex(RISK_LEVELS, fill_value=0)
    .rename("patients").rename_axis("risk_level").reset_index()
)

chart_cols = st.columns(3)
with chart_cols[0]:
    with st.container(border=True):
        age_chart = (
            alt.Chart(age_df)
            .mark_bar(color="#90caf9")
            .encode(
                x=alt.X("age_group:N", sort=age_order, title="Age Group (years)"),
                y=alt.Y("patients:Q", title="Number of Patients"),
                tooltip=["age_group", "patients"],
            )
            .properties(title="Age Distribution", height=260)
        )
        st.altair_chart(age_chart)
        st.caption("[50-60) means ages 50–59: the lower bound is included, the upper bound is excluded.")
with chart_cols[1]:
    with st.container(border=True):
        st.altair_chart(donut(gender_df, "gender", gender_colors, "Gender Distribution"))
with chart_cols[2]:
    with st.container(border=True):
        st.altair_chart(donut(risk_df, "risk_level", RISK_COLORS, "Risk Distribution"))

left, right = st.columns([2, 1])
with left:
    st.subheader("Patient Cohort Table")
    table = df[
        ["patient_id", "age", "gender", "primary_diagnosis", "hba1c", "readmission_risk", "risk_level"]
    ].rename(columns={
        "patient_id": "Patient ID",
        "age": "Age Group",
        "gender": "Gender",
        "primary_diagnosis": "Primary Diagnosis",
        "hba1c": "HbA1c (%)",
        "readmission_risk": "Readmission Risk",
        "risk_level": "Predicted Outcome",
    })
    st.dataframe(
        table,
        hide_index=True,
        height=420,
        column_config={
            "HbA1c": st.column_config.TextColumn(),
            "Readmission Risk": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=1
            ),
        },
    )
    st.caption(f"Showing {len(df)} patients")

with right:
    st.subheader("Selected Patient Details")
    patient_id = st.selectbox("Patient", list(df["patient_id"]), key="selected_patient")
    p = df.loc[df["patient_id"] == patient_id].iloc[0]
    with st.container(border=True):
        st.markdown(f"**Patient ID:** {p['patient_id']}")
        st.markdown(f"**Age Group:** {p['age_group']}")
        st.markdown(f"**Gender:** {p['gender']}")
        st.markdown(f"**Primary Diagnosis:** {p['primary_diagnosis']}")
        st.markdown(f"**Length of Stay:** {p['length_of_stay']} days")
        st.markdown(f"**HbA1c:** {p['hba1c']}")

    risk = float(p["readmission_risk"])
    gauge_df = pd.DataFrame({"part": ["Predicted risk", "Remaining"], "value": [risk, 1 - risk]})
    gauge = (
        alt.Chart(gauge_df)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta("value:Q"),
            color=alt.Color(
                "part:N",
                scale=alt.Scale(
                    domain=["Predicted risk", "Remaining"],
                    range=[RISK_COLORS[p["risk_level"]], "#e5e7eb"],
                ),
                legend=None,
            ),
        )
        .properties(title="Predicted Readmission Risk", height=220)
    )
    st.altair_chart(gauge)
    st.caption(f"{risk:.0%} predicted risk of readmission within 30 days ({p['risk_level']})")
