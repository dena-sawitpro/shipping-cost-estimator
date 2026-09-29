"""Local visual check with a pre-filled scenario: streamlit run preview.py --server.port 8502"""
from pathlib import Path

import streamlit as st

if "preview" not in st.session_state:
    st.session_state.update(preview=True, qty={"10101600": 2, "10300100": 12},
                            origin="Kota Dumai", dest="Kab. Kampar", district="Bangkinang")
exec(Path(__file__).with_name("app.py").read_text(encoding="utf-8"))
