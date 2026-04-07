# pages/3_상담자료_업로드_및_추출.py
import pandas as pd
import streamlit as st

from modules.pdf_parser import parse_pdf_students
from modules.extracted_data_cleaner import normalize_extracted_student
from modules.validator import build_validation_report

st.set_page_config(page_title="상담자료 업로드 및 추출", page_icon="📄", layout="wide")

st.title("📄 상담자료 업로드 및 추출")

if "extracted_students" not in st.session_state:
    st.session_state["extracted_students"] = []

tab_pdf, tab_manual = st.tabs(["PDF 업로드", "직접 입력"])

# ── PDF 업로드 탭 (기존 기능 그대로) ─────────────────────────────────────────
with tab_pdf:
    st.info("PDF는 여러 학생이 들어 있어도 업로드할 수 있습니다. 자동 추출 후 반드시 확인·수정 단계를 거칩니다.")

    uploaded_pdf = st.file_uploader("상담자료 PDF 업로드", type=["pdf"], accept_multiple_files=False)

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

# ── 직접 입력 탭 ──────────────────────────────────────────────────────────────
with tab_manual:
    st.info("학번·이름·성적을 직접 입력해 한 명의 학생 데이터를 추가합니다. 입력 후 '추가' 버튼을 누르면 확인·수정 단계로 이동할 수 있습니다.")

    col1, col2, col3 = st.columns(3)
    with col1:
        manual_id = st.text_input("학번", key="manual_student_id")
    with col2:
        manual_name = st.text_input("이름", key="manual_student_name")
    with col3:
        manual_track = st.selectbox("계열", ["인문", "자연", "미정"], key="manual_track")

    grade_column_config = {
        "school_year": st.column_config.NumberColumn("학년", step=1),
        "semester": st.column_config.TextColumn("학기"),
        "exam_type": st.column_config.TextColumn("구분"),
        "label": st.column_config.TextColumn("표시명"),
        "kor_score": st.column_config.NumberColumn("국어 점수"),
        "kor_rank": st.column_config.NumberColumn("국어 석차", step=1),
        "kor_grade": st.column_config.NumberColumn("국어 등급"),
        "math_score": st.column_config.NumberColumn("수학 점수"),
        "math_rank": st.column_config.NumberColumn("수학 석차", step=1),
        "math_grade": st.column_config.NumberColumn("수학 등급"),
        "eng_score": st.column_config.NumberColumn("영어 점수"),
        "eng_grade": st.column_config.NumberColumn("영어 등급"),
        "soc_score": st.column_config.NumberColumn("통합사회 점수"),
        "soc_grade": st.column_config.NumberColumn("통합사회 등급"),
        "sci_score": st.column_config.NumberColumn("통합과학 점수"),
        "sci_grade": st.column_config.NumberColumn("통합과학 등급"),
        "ksy_grade": st.column_config.NumberColumn("국수영 등급"),
        "ksy_rank": st.column_config.NumberColumn("국수영 석차", step=1),
        "all_grade": st.column_config.NumberColumn("전교과 등급"),
        "all_rank": st.column_config.NumberColumn("전교과 석차", step=1),
        "total_students": st.column_config.NumberColumn("총원", step=1),
    }

    mock_column_config = {
        "school_year": st.column_config.NumberColumn("학년", step=1),
        "month": st.column_config.TextColumn("월"),
        "label": st.column_config.TextColumn("표시명"),
        "kor_score": st.column_config.NumberColumn("국어 원점수"),
        "kor_percentile": st.column_config.NumberColumn("국어 백분위"),
        "kor_rank": st.column_config.NumberColumn("국어 석차", step=1),
        "kor_grade": st.column_config.NumberColumn("국어 등급"),
        "math_score": st.column_config.NumberColumn("수학 원점수"),
        "math_percentile": st.column_config.NumberColumn("수학 백분위"),
        "math_rank": st.column_config.NumberColumn("수학 석차", step=1),
        "math_grade": st.column_config.NumberColumn("수학 등급"),
        "eng_score": st.column_config.NumberColumn("영어 원점수"),
        "eng_rank": st.column_config.NumberColumn("영어 석차", step=1),
        "eng_grade": st.column_config.NumberColumn("영어 등급"),
        "soc_score": st.column_config.NumberColumn("통합사회 원점수"),
        "soc_percentile": st.column_config.NumberColumn("통합사회 백분위"),
        "soc_grade": st.column_config.NumberColumn("통합사회 등급"),
        "sci_score": st.column_config.NumberColumn("통합과학 원점수"),
        "sci_percentile": st.column_config.NumberColumn("통합과학 백분위"),
        "sci_grade": st.column_config.NumberColumn("통합과학 등급"),
        "history_score": st.column_config.NumberColumn("한국사 원점수"),
        "history_grade": st.column_config.NumberColumn("한국사 등급"),
        "ks_type": st.column_config.TextColumn("국수영/탐 구분"),
        "ks_score": st.column_config.NumberColumn("국수영/탐 원점수"),
        "ks_rank": st.column_config.NumberColumn("국수영/탐 석차", step=1),
        "ks_percentile": st.column_config.NumberColumn("국수 백분위"),
        "total_rank": st.column_config.NumberColumn("국수 석차", step=1),
        "total_students": st.column_config.NumberColumn("총원", step=1),
    }

    st.subheader("내신고사")
    manual_grade_df = st.data_editor(
        pd.DataFrame(columns=list(grade_column_config.keys())),
        use_container_width=True,
        num_rows="dynamic",
        key="manual_grade_editor",
        column_config=grade_column_config,
    )

    st.subheader("전국연합학력평가")
    manual_mock_df = st.data_editor(
        pd.DataFrame(columns=list(mock_column_config.keys())),
        use_container_width=True,
        num_rows="dynamic",
        key="manual_mock_editor",
        column_config=mock_column_config,
    )

    if st.button("학생 추가", type="primary", key="manual_add_btn"):
        if not manual_id.strip() and not manual_name.strip():
            st.error("학번 또는 이름을 입력해 주세요.")
        else:
            new_student = {
                "basic_info": {
                    "student_id": manual_id.strip(),
                    "name": manual_name.strip(),
                    "track": manual_track,
                },
                "grade_records": manual_grade_df.to_dict(orient="records"),
                "mock_records": manual_mock_df.to_dict(orient="records"),
            }
            new_student["validation"] = build_validation_report(new_student)
            new_idx = len(st.session_state["extracted_students"]) + 1
            new_student["display_name"] = f"{manual_name.strip() or '이름없음'} ({manual_id.strip() or '학번없음'})"
            new_student["student_index"] = new_idx
            st.session_state["extracted_students"].append(new_student)
            st.success(f"{new_student['display_name']} 학생이 추가되었습니다. (번호: {new_idx})")
            st.page_link("pages/4_추출결과_확인수정.py", label="추출결과 확인·수정으로 이동", icon="✏️")