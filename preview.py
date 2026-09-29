"""Local visual check with a pre-filled scenario: streamlit run preview.py --server.port 8502"""
from pathlib import Path

import streamlit as st

if "preview" not in st.session_state:
    st.session_state.update(preview=True, chosen=["10101600", "10300100"], qty={"10101600": 2, "10300100": 12},
                            origin="Kota Dumai", dest_pick="Kab. Kampar · Bangkinang")
exec(Path(__file__).with_name("app.py").read_text(encoding="utf-8"))
