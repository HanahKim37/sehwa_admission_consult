import streamlit as st
from modules.session_state import init_session_state
from modules.ui_helpers import render_header_box
from modules.auth import require_login, render_logout_button

st.set_page_config(
    page_title="고2 진학 상담 분석",
    page_icon="📘",
    layout="wide",
)

init_session_state()
require_login()

def 홈():
    st.title("🏠 홈")
    render_logout_button()
    render_header_box(
        "프로그램 개요",
        "졸업생 엑셀을 기준 데이터로 사용하고, 현재 고2 상담자료를 반자동으로 읽어 유사 사례와 전형 적합도를 분석합니다."
    )
    st.markdown(
        """
### 사용 순서
1. **졸업생 데이터 불러오기**
2. **상담자료 업로드 및 추출**
3. **추출결과 확인수정**
4. **분석결과 보고서 확인 및 PDF 저장**

### 개인정보 및 보고서 원칙
- 현재 학생 원데이터는 세션 종료 후 유지하지 않습니다.
- 학생용 보고서에는 졸업생 개인정보를 표시하지 않습니다.
- 결과는 참고용 예측 자료이며 상담 자료로만 활용합니다.
"""
    )

pg = st.navigation([
    st.Page(홈, title="홈", icon="🏠"),
    st.Page("pages/2_졸업생_데이터_불러오기.py", title="졸업생 데이터 불러오기"),
    st.Page("pages/3_상담자료_업로드_및_추출.py", title="상담자료 업로드 및 추출"),
    st.Page("pages/4_추출결과_확인수정.py", title="추출결과 확인수정"),
    st.Page("pages/5_분석결과_보고서.py", title="분석결과 보고서"),
    st.Page("pages/6_[참고]_분석기준.py", title="[참고] 분석기준"),
])
pg.run()
