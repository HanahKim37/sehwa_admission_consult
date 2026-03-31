import streamlit as st

DEFAULTS = {
    "logged_in": False,
    "current_user": None,
    "graduates_loaded": False,
    "graduate_raw_sheets": {},
    "graduate_db": {},
    "graduate_summary": {},
    "current_upload_name": None,
    "current_extracted": None,
    "current_validation": None,
    "current_features": None,
    "analysis_result": None,
    "report_html": None,
    "report_pdf_path": None,
    "teacher_review": None,
}

def init_session_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_current_student() -> None:
    for key in [
        "current_upload_name",
        "current_extracted",
        "current_validation",
        "current_features",
        "analysis_result",
        "report_html",
        "report_pdf_path",
        "teacher_review",
    ]:
        st.session_state[key] = DEFAULTS[key]

def reset_all() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
