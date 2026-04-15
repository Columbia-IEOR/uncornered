import streamlit as st

def get_sidebar_controls():
    st.sidebar.header("Controls")

    city = st.sidebar.selectbox("City", ["Boston", "Kansas City"])
    view_mode = st.sidebar.selectbox("Map mode", ["Standard Map", "Dashboard Map"])
    show_crews = st.sidebar.toggle("Show crews", value=True)
    show_conflicts = st.sidebar.toggle("Show conflicts", value=True)
    show_catalyst_links = st.sidebar.toggle("Show catalyst links", value=True)
    refresh_window = st.sidebar.selectbox(
        "Time window",
        ["Past week", "Past month", "Full available history"]
    )

    return {
        "city": city,
        "view_mode": view_mode,
        "show_crews": show_crews,
        "show_conflicts": show_conflicts,
        "show_catalyst_links": show_catalyst_links,
        "refresh_window": refresh_window
    }