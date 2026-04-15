from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

def render_html_map(html_path: str, height: int = 780):
    path = Path(html_path)

    if not path.exists():
        st.error(f"Map file not found: {html_path}")
        st.write("Current working directory:", Path.cwd())
        return

    html_content = path.read_text(encoding="utf-8")
    components.html(html_content, height=height, scrolling=True)