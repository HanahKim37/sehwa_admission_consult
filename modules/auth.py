from pathlib import Path
import pandas as pd
import streamlit as st

AUTH_FILE = Path("sample_data/login_users.xlsx")

def _normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()

def load_auth_users() -> pd.DataFrame:
    if not AUTH_FILE.exists():
        return pd.DataFrame(columns=["아이디", "비밀번호"])
    try:
        df = pd.read_excel(AUTH_FILE)
    except Exception:
        return pd.DataFrame(columns=["아이디", "비밀번호"])
    rename_map = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if c in ["아이디", "id", "user", "username", "로그인아이디"]:
            rename_map[col] = "아이디"
        elif c in ["비밀번호", "pw", "password", "passwd"]:
            rename_map[col] = "비밀번호"
    if rename_map:
        df = df.rename(columns=rename_map)
    for required in ["아이디", "비밀번호"]:
        if required not in df.columns:
            df[required] = ""
    df["아이디"] = df["아이디"].map(_normalize)
    df["비밀번호"] = df["비밀번호"].map(_normalize)
    df = df[(df["아이디"] != "") & (df["비밀번호"] != "")]
    return df[["아이디", "비밀번호"]].drop_duplicates()

def authenticate(username: str, password: str) -> bool:
    df = load_auth_users()
    if df.empty:
        return False
    username = _normalize(username)
    password = _normalize(password)
    matched = df[(df["아이디"] == username) & (df["비밀번호"] == password)]
    return not matched.empty

def render_login_form() -> None:
    st.title("🔐 로그인")
    st.caption("계정 정보를 입력한 뒤 프로그램을 사용할 수 있습니다.")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", use_container_width=True)
    if submitted:
        if authenticate(username, password):
            st.session_state["logged_in"] = True
            st.session_state["current_user"] = username.strip()
            st.success("로그인되었습니다.")
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

def require_login() -> None:
    if not st.session_state.get("logged_in", False):
        render_login_form()
        st.stop()

def render_logout_button() -> None:
    user = st.session_state.get("current_user")
    cols = st.columns([1,1,6])
    with cols[0]:
        if st.button("로그아웃", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["current_user"] = None
            st.rerun()
    with cols[1]:
        if user:
            st.write("")
    if user:
        cols[2].markdown(f"**사용자:** {user}")
