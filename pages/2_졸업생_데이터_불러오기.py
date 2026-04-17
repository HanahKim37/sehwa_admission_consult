from modules.auth import require_login, render_logout_button
import streamlit as st
import pandas as pd
from modules.graduate_loader import load_excel_file, load_from_google_drive, detect_required_sheets, summarize_workbook
from modules.graduate_normalizer import build_graduate_database, _fill_multiindex_ffill, _flatten_columns
from modules.ui_helpers import render_status_badge, render_summary_card

require_login()
render_logout_button()

st.title("📂 졸업생 데이터 불러오기")

tab_default, tab_upload = st.tabs(["기본 데이터 사용", "파일 직접 업로드"])

# ── 기본 데이터 탭 (Google Drive) ──────────────────────────────────────────────
with tab_default:
    st.info("사전에 등록된 졸업생 데이터를 불러옵니다. 별도 파일 업로드 없이 바로 사용할 수 있습니다.")

    if st.button("기본 데이터 불러오기", type="primary", key="btn_default"):
        with st.spinner("졸업생 데이터를 불러오는 중입니다..."):
            try:
                workbook = load_from_google_drive()
                detected = detect_required_sheets(workbook)
                summary = summarize_workbook(workbook)
                db = build_graduate_database(workbook)

                st.session_state["graduate_raw_sheets"] = workbook
                st.session_state["graduate_db"] = db
                st.session_state["graduate_summary"] = {"detected": detected, "summary": summary}
                st.session_state["graduates_loaded"] = True

                st.success("기본 졸업생 데이터 로딩이 완료되었습니다.")
            except Exception as e:
                st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")

# ── 파일 직접 업로드 탭 ────────────────────────────────────────────────────────
with tab_upload:
    st.info("직접 준비한 졸업생 엑셀 파일을 업로드합니다.")

    uploaded = st.file_uploader("졸업생 엑셀 파일 업로드", type=["xlsx", "xlsm", "xls"], key="uploader_grad")
    if uploaded is not None:
        if st.button("데이터 불러오기", type="primary", key="btn_upload"):
            with st.spinner("엑셀 파일을 분석하는 중입니다..."):
                workbook = load_excel_file(uploaded)
                detected = detect_required_sheets(workbook)
                summary = summarize_workbook(workbook)
                db = build_graduate_database(workbook)

                st.session_state["graduate_raw_sheets"] = workbook
                st.session_state["graduate_db"] = db
                st.session_state["graduate_summary"] = {"detected": detected, "summary": summary}
                st.session_state["graduates_loaded"] = True

            st.success("졸업생 데이터 로딩이 완료되었습니다.")

# ── 로딩 결과 표시 (공통) ──────────────────────────────────────────────────────
if st.session_state.get("graduates_loaded"):
    info = st.session_state["graduate_summary"]
    st.subheader("시트 인식 결과")
    cols = st.columns(3)
    items = list(info["detected"].items())
    for idx, (k, v) in enumerate(items):
        with cols[idx % 3]:
            st.markdown(f"**{k}**")
            render_status_badge(v if v in ["정상", "누락"] else "정상" if "인식" in v else "확인 필요")

    st.subheader("데이터 개수 요약")
    summary = info["summary"]
    cols = st.columns(4)
    for idx, (k, v) in enumerate(summary.items()):
        with cols[idx % 4]:
            render_summary_card(k, str(v), "행 수 기준")

    st.subheader("내부 DB 요약")
    db = st.session_state["graduate_db"]
    st.write({k: len(v) for k, v in db.items()})

    with st.expander("🔍 진단 정보 (컬럼 감지 결과 확인용)"):
        grade_df = db.get("grade", pd.DataFrame())
        mock_df = db.get("mock", pd.DataFrame())

        st.markdown("**내신 DB 컬럼:**")
        st.write(grade_df.columns.tolist() if not grade_df.empty else "없음")
        if not grade_df.empty:
            has_serial = "serial_no" in grade_df.columns
            st.markdown(f"**일련번호 감지:** {'✅ serial_no 컬럼 있음' if has_serial else '❌ serial_no 없음 — 졸업생 엑셀의 내신성적 시트에 일련번호 열이 있는지 확인'}")

        st.markdown("**내신 샘플 (처음 3행):**")
        if not grade_df.empty:
            st.dataframe(grade_df.head(3))
        else:
            st.write("없음")

        st.markdown("**내신 등급 컬럼 NaN 비율:**")
        if not grade_df.empty:
            grade_check_cols = [c for c in ["all_grade", "ksy_grade", "kor_grade", "math_grade", "eng_grade"] if c in grade_df.columns]
            if grade_check_cols:
                nan_rate = grade_df[grade_check_cols].isna().mean().round(3)
                st.write(nan_rate.to_dict())
            else:
                st.warning("내신 등급 컬럼(all_grade 등)이 없습니다. 엑셀 구조를 확인하세요.")

        st.markdown("**모의 DB 컬럼:**")
        st.write(mock_df.columns.tolist() if not mock_df.empty else "없음")

        st.markdown("**모의 샘플 (처음 3행):**")
        if not mock_df.empty:
            st.dataframe(mock_df.head(3))
        else:
            st.write("없음")

        st.markdown("**모의 핵심 컬럼 NaN 비율:**")
        if not mock_df.empty:
            mock_check_cols = [c for c in ["mock_kor_percentile", "mock_math_percentile", "mock_eng_grade", "mock_ks_percentile"] if c in mock_df.columns]
            if mock_check_cols:
                nan_rate = mock_df[mock_check_cols].isna().mean().round(3)
                st.write(nan_rate.to_dict())
            else:
                st.warning("모의 핵심 컬럼(mock_kor_percentile 등)이 없습니다. 엑셀 구조를 확인하세요.")

        st.markdown("---")
        st.markdown("### 🔬 모의고사 감지 컬럼 (한국사·탐구 디버깅용)")

        detected_cols = (
            mock_df.attrs.get("detected_mock_cols")
            or db.get("mock_detected_cols")
            or {}
        )
        if detected_cols:
            st.markdown("**감지된 컬럼 매핑 (출력컬럼 → 원본 Excel 컬럼명):**")
            rows = []
            for out_col, src_col in detected_cols.items():
                rows.append({"출력 컬럼": out_col, "원본 Excel 컬럼": src_col if src_col else "❌ 미감지"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.warning("detected_mock_cols 정보 없음 (attrs 미보존). 아래 원본 컬럼 목록 참고.")

        workbook = st.session_state.get("graduate_raw_sheets", {})
        raw_mock = workbook.get("모의고사")
        if raw_mock is not None:
            flat_mock = _fill_multiindex_ffill(raw_mock.copy())
            flat_cols = _flatten_columns(flat_mock.columns)
            st.markdown("**모의고사 시트 원본 컬럼명 전체 (flatten 후):**")
            st.code("\n".join(f"{i}: {c}" for i, c in enumerate(flat_cols)))
        else:
            st.warning("모의고사 시트 없음")
