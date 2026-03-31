# pages/3_상담자료_업로드_및_추출.py
import streamlit as st

from modules.pdf_parser import parse_pdf_students
from modules.extracted_data_cleaner import normalize_extracted_student
from modules.validator import build_validation_report

st.set_page_config(page_title="상담자료 업로드 및 추출", page_icon="📄", layout="wide")

st.title("📄 상담자료 업로드 및 추출")

st.info("PDF는 여러 학생이 들어 있어도 업로드할 수 있습니다. 자동 추출 후 반드시 확인·수정 단계를 거칩니다.")

uploaded_pdf = st.file_uploader("상담자료 PDF 업로드", type=["pdf"], accept_multiple_files=False)

if "extracted_students" not in st.session_state:
    st.session_state["extracted_students"] = []

if uploaded_pdf is not None:
    if st.button("자동 추출 시작", type="primary"):
        with st.spinner("PDF에서 학생별 데이터를 추출하는 중입니다..."):
            parsed_students = parse_pdf_students(uploaded_pdf)

            processed = []
            for idx, student in enumerate(parsed_students, start=1):
                student = normalize_extracted_student(student)
                report = build_validation_report(student)
                student["validation"] = report
                student["display_name"] = f"{student['basic_info'].get('name','이름없음')} ({student['basic_info'].get('student_id','학번없음')})"
                student["student_index"] = idx
                processed.append(student)

            st.session_state["extracted_students"] = processed

        st.success(f"{len(processed)}명의 학생 데이터를 추출했습니다.")

if st.session_state.get("extracted_students"):
    st.subheader("추출 결과 요약")

    summary_rows = []
    for s in st.session_state["extracted_students"]:
        summary_rows.append({
            "번호": s["student_index"],
            "학번": s["basic_info"].get("student_id", ""),
            "이름": s["basic_info"].get("name", ""),
            "상태": s["validation"]["status"],
            "오류수": len(s["validation"]["messages"]),
        })

    st.dataframe(summary_rows, use_container_width=True)

    st.page_link("pages/4_추출결과_확인수정.py", label="추출결과 확인·수정으로 이동", icon="✏️")