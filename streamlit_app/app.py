import streamlit as st

home = st.Page("streamlit_app/pages/home.py", title="Home", icon="🏠")
maps = st.Page("streamlit_app/pages/map_viewer.py", title="Maps", icon="🗺️")
refresh = st.Page("streamlit_app/pages/refresh_data.py", title="Refresh Data", icon="🔄")
methodology = st.Page("streamlit_app/pages/methodology.py", title="Methodology", icon="📘")

st.set_page_config(
    page_title="Uncornered Community Safety Dashboard",
    page_icon="🗺️",
    layout="wide"
)

pg = st.navigation([home, maps, refresh, methodology])

st.title("Uncornered Community Safety Dashboard")
st.caption("Geospatial analysis to support community safety initiatives")

pg.run()