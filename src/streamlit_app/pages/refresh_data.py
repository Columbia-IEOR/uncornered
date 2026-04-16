import streamlit as st
from src.refresh_pipeline import refresh_public_data_pipeline

st.header("Refresh Data")

city = st.selectbox("City to refresh", ["Boston", "Kansas City", "Both"])
dry_run = st.checkbox("Dry run only", value=True)

if st.button("Run refresh"):
    result = refresh_public_data_pipeline(city=city, dry_run=dry_run)
    st.success("Refresh complete")
    st.json(result)