import csv
import io
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.theme import apply_theme

st.header("Players")
apply_theme()

with st.form("player_filters"):
    position = st.selectbox("Position", ["", "QB", "RB", "WR", "TE", "K", "DST"])
    school = st.text_input("School")
    search = st.text_input("Search name")
    submitted = st.form_submit_button("Apply filters")

filters = {"position": position, "school": school.strip(), "search": search.strip()}

try:
    data = api_client.get_players(filters)
    st.dataframe(data["data"], use_container_width=True)
except Exception as exc:
    st.error(f"Failed to load players: {exc}")

st.subheader("Add player")
with st.form("add_player"):
    name = st.text_input("Player name")
    external_id = st.text_input("External id (optional)")
    position = st.selectbox("Position", ["QB", "RB", "WR", "TE", "K", "DST"])
    school = st.text_input("School", value="")
    submitted = st.form_submit_button("Add player")

if submitted:
    if not name.strip() or not school.strip():
        st.error("Name and school are required.")
    else:
        try:
            api_client.create_players(
                [
                    {
                        "name": name.strip(),
                        "external_id": external_id.strip() or None,
                        "position": position,
                        "school": school.strip(),
                    }
                ]
            )
            st.success("Player added.")
        except Exception as exc:
            st.error(f"Failed to add player: {exc}")

st.subheader("Bulk upload (CSV)")
file = st.file_uploader("Upload CSV with columns: name, position, school, external_id", type=["csv"])
if file is not None:
    try:
        content = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        payload = []
        for row in reader:
            payload.append(
                {
                    "name": row.get("name", "").strip(),
                    "position": row.get("position", "").strip(),
                    "school": row.get("school", "").strip(),
                    "external_id": row.get("external_id", "").strip() or None,
                }
            )
        payload = [entry for entry in payload if entry["name"] and entry["position"] and entry["school"]]
        if not payload:
            st.error("No valid rows found.")
        else:
            api_client.create_players(payload)
            st.success(f"Uploaded {len(payload)} players.")
    except Exception as exc:
        st.error(f"Failed to upload players: {exc}")
