import streamlit as st

home = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
maps = st.Page("pages/map_viewer.py", title="Maps", icon="🗺️")
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

pg.run()