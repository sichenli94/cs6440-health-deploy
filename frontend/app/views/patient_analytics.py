import re

import altair as alt
import pandas as pd
import streamlit as st

from sidebar import get_filtered_patients


def age_order(label: str) -> tuple:
    match = re.search(r"\d+", str(label))
    return (int(match.group()) if match else float("inf"), str(label))


def numeric_values(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values.ge(0) & values.lt(float("inf")))


st.title("Patient Analytics")
st.caption("Explore clinical data coverage, hospital stays, and prior visits.")

df = get_filtered_patients().copy()
if df.empty:
    st.warning("No patients match the selected filters. Clear the sidebar filters to explore the cohort.")
    st.stop()

st.caption(f"{len(df):,} patients in the current selection • Charts follow sidebar filters")
st.info("Synthetic FHIR cohort. Readmission risk scores used by the risk filter are randomly generated.")

left, right = st.columns([1, 1.2])
with left:
    with st.container(border=True):
        st.subheader("HbA1c availability and categories")
        labels = ["No extracted result", "Below 7%", "7–8% inclusive", "Above 8%", "Unrecognized category"]
        raw = df["hba1c"].astype("string").str.strip().str.lower()
        categories = raw.map({"norm": labels[1], "7": labels[2], ">8": labels[3]})
        missing = raw.isna() | raw.isin(["", "none", "nan", "null"])
        categories = categories.fillna(labels[4]).mask(missing, labels[0])
        recognized = int(categories.isin(labels[1:4]).sum())
        st.caption(f"{recognized:,} of {len(df):,} patients have a recognized extracted result")
        counts = categories.value_counts().reindex(labels, fill_value=0)
        if counts[labels[4]] == 0:
            counts = counts.drop(labels[4])
        hba1c = counts.rename_axis("category").reset_index(name="patients")
        base = alt.Chart(hba1c).encode(
            y=alt.Y("category:N", sort=labels, title=None),
            x=alt.X("patients:Q", title="Patients", scale=alt.Scale(domain=[0, max(1, int(counts.max()) * 1.2)])),
            tooltip=[alt.Tooltip("category:N", title="HbA1c category"), alt.Tooltip("patients:Q", title="Patients")],
        )
        bars = base.mark_bar().encode(color=alt.Color(
            "category:N", legend=None,
            scale=alt.Scale(domain=labels, range=["#9ca3af", "#1677ff", "#14b8a6", "#8b5cf6", "#f59e0b"]),
        ))
        text = base.mark_text(align="left", dx=5).encode(text="patients:Q")
        st.altair_chart((bars + text).properties(height=280), use_container_width=True)
        st.caption("Categories reflect the current extraction rules. Missing results are not normal results.")

with right:
    with st.container(border=True):
        st.subheader("Hospital stay by patient group")
        controls = st.columns(2)
        measures = {
            "Length of stay": ("length_of_stay", "Median stay (days)"),
            "Medication count": ("num_medications", "Median medication count"),
            "Diagnosis count": ("number_diagnoses", "Median diagnosis count"),
            "Procedure count": ("num_procedures", "Median procedure count"),
        }
        groups = {"Age group": "age_group", "Gender": "gender", "Race": "race"}
        measure = controls[0].selectbox("Measure", list(measures), key="analytics_measure")
        group = controls[1].selectbox("Group by", list(groups), key="analytics_group")
        field, axis_title = measures[measure]
        values = numeric_values(df[field])
        grouped = pd.DataFrame({
            "group": df[groups[group]].astype("string").str.strip().fillna("Unknown").replace("", "Unknown"),
            "value": values,
        }).groupby("group", sort=False)["value"].agg(median="median", n="count").reset_index()
        grouped = grouped[grouped["n"] > 0].copy()
        if grouped.empty:
            st.info("No valid measurements are available for this selection.")
        else:
            order = sorted(grouped["group"], key=age_order if group == "Age group" else str)
            grouped["label"] = grouped["group"] + " (n=" + grouped["n"].astype(str) + ")"
            label_lookup = grouped.set_index("group")["label"].to_dict()
            base = alt.Chart(grouped).encode(
                x=alt.X("label:N", sort=[label_lookup[item] for item in order], title=group, axis=alt.Axis(labelAngle=-40)),
                y=alt.Y("median:Q", title=axis_title, scale=alt.Scale(zero=True)),
                tooltip=[alt.Tooltip("group:N", title=group), alt.Tooltip("median:Q", title=axis_title, format=".1f"), alt.Tooltip("n:Q", title="Patients with values")],
            )
            st.altair_chart(
                (base.mark_bar(color="#1677ff") + base.mark_text(dy=-8).encode(text=alt.Text("median:Q", format=".1f"))).properties(height=260),
                use_container_width=True,
            )
        if values.isna().any():
            st.caption(f"{int(values.isna().sum())} missing or invalid measurements excluded.")
        st.caption("n is the number of patients with a valid measurement. Small groups can produce unstable summaries.")

with st.container(border=True):
    st.subheader("Prior healthcare utilization")
    st.caption("Extracted encounters in the 365 days before each patient's selected index admission")
    records = []
    for label, field in [("Outpatient", "number_outpatient"), ("Emergency", "number_emergency"), ("Inpatient", "number_inpatient")]:
        values = numeric_values(df[field])
        valid = int(values.notna().sum())
        patients = int(values.gt(0).sum())
        records.append({"visit_type": label, "patients": patients, "encounters": values.sum() if valid else None,
                        "valid": valid, "total": len(df),
                        "label": f"{patients} / {len(df)}" if valid else f"No data / {len(df)}"})
    visits = pd.DataFrame(records)
    chart_col, table_col = st.columns([1.6, 1])
    with chart_col:
        st.markdown("**Patients with at least one visit**")
        base = alt.Chart(visits).encode(
            y=alt.Y("visit_type:N", sort=["Outpatient", "Emergency", "Inpatient"], title=None),
            x=alt.X("patients:Q", title="Patients", scale=alt.Scale(domain=[0, max(1, len(df) * 1.15)])),
            tooltip=[alt.Tooltip("visit_type:N", title="Visit type"), alt.Tooltip("patients:Q", title="Patients with visits"), alt.Tooltip("total:Q", title="Total selected patients"), alt.Tooltip("valid:Q", title="Patients with available data")],
        )
        st.altair_chart(
            (base.mark_bar(color="#1677ff") + base.mark_text(align="left", dx=5).encode(text="label:N")).properties(height=190),
            use_container_width=True,
        )
    with table_col:
        st.markdown("**Visit totals**")
        totals = visits[["visit_type", "encounters"]].rename(columns={"visit_type": "Visit type", "encounters": "Encounters"})
        st.dataframe(totals, hide_index=True, use_container_width=True,
                     column_config={"Encounters": st.column_config.NumberColumn(format="%d")})
    st.caption("A patient can appear in more than one visit category. Each denominator is the total number of patients in the current selection; patients with missing visit counts are not counted in the numerator.")
    inpatient = visits.loc[visits["visit_type"] == "Inpatient"].iloc[0]
