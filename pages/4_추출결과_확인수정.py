# pages/4_추출결과_확인수정.py
import pandas as pd
import streamlit as st

from modules.validator import build_validation_report

st.set_page_config(page_title="추출결과 확인수정", page_icon="✏️", layout="wide")
st.markdown("""
<style>
/* 드롭다운 선택값 텍스트 선명하게 */
div[data-baseweb="select"] div[class*="singleValue"] {
    color: rgb(49, 51, 63) !important;
    opacity: 1 !important;
}
div[data-baseweb="select"] span[class*="placeholder"] {
    color: rgb(49, 51, 63) !important;
    opacity: 1 !important;
}
/* 다크 모드 대응 */
[data-theme="dark"] div[data-baseweb="select"] div[class*="singleValue"] {
    color: rgb(250, 250, 250) !important;
}
</style>
""", unsafe_allow_html=True)
st.title("✏️ 추출결과 확인수정")

students = st.session_state.get("extracted_students", [])

if not students:
    st.warning("먼저 상담자료 PDF를 업로드하고 자동 추출을 실행해 주세요.")
    st.stop()

options = [
    f"{s['student_index']}. {s['basic_info'].get('name','이름없음')} / {s['basic_info'].get('student_id','학번없음')} / {s['validation']['status']}"
    for s in students
]
_default_idx = st.session_state.get("confirmed_student_idx", 0)
_default_idx = min(_default_idx, len(options) - 1)
selected_idx = st.selectbox("학생 선택", range(len(options)), index=_default_idx, format_func=lambda i: options[i])

student = students[selected_idx]

st.subheader("기본 정보")
col1, col2, col3 = st.columns(3)
with col1:
    student["basic_info"]["student_id"] = st.text_input("학번", value=student["basic_info"].get("student_id", ""))
with col2:
    student["basic_info"]["name"] = st.text_input("이름", value=student["basic_info"].get("name", ""))
with col3:
    current_track = student["basic_info"].get("track", "미정")
    if current_track not in ["인문", "자연", "미정"]:
        current_track = "미정"
    student["basic_info"]["track"] = st.selectbox(
        "계열",
        ["인문", "자연", "미정"],
        index=["인문", "자연", "미정"].index(current_track),
    )

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
grade_df = pd.DataFrame(student.get("grade_records", []))
grade_df = st.data_editor(
    grade_df,
    use_container_width=True,
    num_rows="dynamic",
    key=f"grade_editor_{selected_idx}",
    column_config=grade_column_config,
)
student["grade_records"] = grade_df.to_dict(orient="records")

st.subheader("전국연합학력평가")
mock_df = pd.DataFrame(student.get("mock_records", []))
for _col in ["soc_percentile", "sci_percentile"]:
    if _col not in mock_df.columns:
        mock_df[_col] = None
_mock_cols = list(mock_column_config.keys())
_extra_cols = [c for c in mock_df.columns if c not in _mock_cols]
mock_df = mock_df.reindex(columns=_mock_cols + _extra_cols)
mock_df = st.data_editor(
    mock_df,
    use_container_width=True,
    num_rows="dynamic",
    key=f"mock_editor_{selected_idx}",
    column_config=mock_column_config,
)
student["mock_records"] = mock_df.to_dict(orient="records")

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("검증 다시 실행", type="primary"):
        student["validation"] = build_validation_report(student)
        students[selected_idx] = student
        st.session_state["extracted_students"] = students
        st.success("검증이 갱신되었습니다.")

with col_b:
    if st.button("이 학생 분석 대상으로 확정"):
        student["selected_for_analysis"] = True
        students[selected_idx] = student
        st.session_state["extracted_students"] = students
        st.session_state["confirmed_student_idx"] = selected_idx  # 다음에 이 페이지 올 때 같은 학생 유지

        # 실제 분석용 현재 학생 데이터 세션에 저장
        st.session_state["current_student_data"] = {
            "basic_info": student.get("basic_info", {}),
            "grade_records": student.get("grade_records", []),
            "mock_records": student.get("mock_records", []),
            "validation": student.get("validation", {}),
        }

        st.success("분석 대상으로 확정했습니다. 이제 분석 결과 페이지로 이동할 수 있습니다.")

st.subheader("검증 결과")
validation = student.get("validation", {"status": "확인 필요", "messages": []})

if validation["status"] == "정상":
    st.success("정상")
elif validation["status"] == "일부 누락":
    st.warning("일부 누락")
else:
    st.error("확인 필요")

if validation["messages"]:
    for msg in validation["messages"]:
        st.write(f"- {msg}")
else:
    st.write("- 검증 오류 없음")

st.page_link("pages/5_분석결과_보고서.py", label="분석 결과 / 보고서로 이동", icon="📊")