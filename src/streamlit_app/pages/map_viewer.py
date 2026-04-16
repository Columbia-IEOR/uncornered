import streamlit as st
from streamlit_app.components.map_embed import render_html_map
from streamlit_app.components.sidebar_controls import get_sidebar_controls

st.header("Map Viewer")

controls = get_sidebar_controls()

city = controls["city"]
view_mode = controls["view_mode"]

if city == "Boston":
    if view_mode == "Dashboard Map":
        html_path = "outputs/maps/boston_crew_network_dashboard.html"
    else:
        html_path = "outputs/maps/boston_crew_network_map.html"
else:
    html_path = "outputs/maps/kc_crew_network_map.html"

st.write("Selected controls")
st.json(controls)

st.write("Looking for file:", html_path)

render_html_map(html_path, height=780)