import streamlit as st

from sidebar import render_sidebar

st.set_page_config(page_title="Health Analytics", layout="wide")

pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("views/patient_analytics.py", title="Patient Analytics", icon=":material/group:"),
    st.Page("views/readmission_prediction.py", title="Readmission Prediction", icon=":material/assignment:"),
    st.Page("views/data_explorer.py", title="Data Explorer", icon=":material/table_chart:"),
    st.Page("views/about.py", title="About", icon=":material/info:"),
]

nav = st.navigation(pages)
render_sidebar()
nav.run()
