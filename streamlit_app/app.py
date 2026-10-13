import streamlit as st

home = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
maps = st.Page("pages/map_viewer.py", title="Legacy Maps", icon="🧭")
refresh = st.Page("pages/refresh_data.py", title="Refresh Data", icon="🔄")
methodology = st.Page("pages/methodology.py", title="Methodology", icon="📘")

st.set_page_config(
    page_title="Uncornered Community Safety Dashboard",
    page_icon="🗺️",
    layout="wide"
)

pg = st.navigation([home, maps, refresh, methodology])

st.title("Uncornered Community Safety Dashboard")
st.caption("Geospatial analysis to support community safety initiatives")
st.info(
    "Phase 2 Boston Atlas demo lives in `phase2_pipeline/`. "
    "Run: `python3 -m streamlit run phase2_pipeline/app/boston_atlas.py`"
)

pg.run()
