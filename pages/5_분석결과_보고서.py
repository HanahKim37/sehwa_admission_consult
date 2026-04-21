from modules.auth import require_login, render_logout_button
from pathlib import Path
import streamlit as st
import pandas as pd

from modules.feature_builder import (
    build_current_student_features,
    build_graduate_features,
    get_grade_basis_options,
    get_mock_basis_options,
)
from modules.similarity_engine import (
    calculate_grade_similarity,
    calculate_mock_similarity,
    calculate_total_similarity,
    get_top_similar_cases,
)
from modules.admission_fit import build_fit_summary
from modules.report_text import (
    build_strength_summary,
    build_weakness_summary,
    build_strategy_summary,
    get_report_disclaimer_lines,
)
from modules.report_pdf import build_report_context, render_report_html, export_pdf, get_conv_table_data
from modules.ui_helpers import styled_dataframe
from modules.college_tracker import search_college_cases

st.set_page_config(page_title="분석결과 보고서", page_icon="📊", layout="wide")

require_login()
render_logout_button()

graduate_db = st.session_state.get("graduate_db")
current_student_data = st.session_state.get("current_student_data")

if graduate_db is None:
    st.warning("졸업생 데이터가 없습니다. 먼저 졸업생 엑셀 파일을 업로드해 주세요.")
    st.stop()

if current_student_data is None:
    st.warning("현재 학생 데이터가 없습니다. '추출결과 확인수정' 페이지에서 학생을 분석 대상으로 확정해 주세요.")
    st.stop()


def safe_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)


def format_value(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def _fmt_grade_with_pos(grade_val, pos_val=None):
    """내신 등급 + 교내 상대위치로 '상위 약 X%' 병기."""
    if grade_val is None or (isinstance(grade_val, float) and pd.isna(grade_val)):
        return "-"
    g_str = f"{float(grade_val):.2f}".rstrip("0").rstrip(".")
    if pos_val is not None and not (isinstance(pos_val, float) and pd.isna(pos_val)):
        top_pct = round((1 - float(pos_val)) * 100)
        return f"{g_str}등급 (상위 약 {top_pct}%)"
    return f"{g_str}등급"


def _fmt_percentile(pct_val):
    """백분위(0-100, 높을수록 좋음) → 'X (상위 약 Y%)'."""
    if pct_val is None or (isinstance(pct_val, float) and pd.isna(pct_val)):
        return "-"
    p = int(round(float(pct_val)))
    top = 100 - p
    return f"{p} (상위 약 {top}%)"


def _fmt_mock_grade(grade_val):
    """9등급 모의 등급(낮을수록 좋음) → 'X등급 (상위 약 Y%)'."""
    if grade_val is None or (isinstance(grade_val, float) and pd.isna(grade_val)):
        return "-"
    g = float(grade_val)
    top_pct = round((g - 1) / 8 * 100)
    return f"{int(round(g))}등급 (상위 약 {top_pct}%)"


def _fmt_percentile_rank(pct_val, rank=None, total=None):
    """백분위 + 석차 → 'X (Y등/Z명)'."""
    if pct_val is None or (isinstance(pct_val, float) and pd.isna(pct_val)):
        return "-"
    p = int(round(float(pct_val)))
    if rank is not None and not (isinstance(rank, float) and pd.isna(rank)):
        r = f"{int(round(float(rank)))}등"
        if total is not None and not (isinstance(total, float) and pd.isna(total)):
            r += f"/{int(round(float(total)))}명"
        return f"{p} ({r})"
    return str(p)


def _fmt_score_rank(score, rank, total=None):
    """원점수(석차) 형태 → 'X점 (Y등/Z명)' 또는 'X점 (Y등)'."""
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return "-"
    s = f"{int(round(float(score)))}점"
    if rank is not None and not (isinstance(rank, float) and pd.isna(rank)):
        r = f"{int(round(float(rank)))}등"
        if total is not None and not (isinstance(total, float) and pd.isna(total)):
            r += f"/{int(round(float(total)))}명"
        s += f" ({r})"
    return s


def _fmt_pos(pos_val):
    """교내 상대위치(0-1, 높을수록 좋음) → '0.85 (상위 약 15%)'."""
    if pos_val is None or (isinstance(pos_val, float) and pd.isna(pos_val)):
        return "-"
    p = float(pos_val)
    top_pct = round((1 - p) * 100)
    raw = f"{p:.3f}".rstrip("0").rstrip(".")
    return f"{raw} (상위 약 {top_pct}%)"


def _small_rank(text: str) -> str:
    """카드 표시용: (상위 약 X%) 부분만 폰트를 줄여서 반환."""
    import re
    return re.sub(
        r"(\(상위 약 \d+%\))",
        r"<span style='font-size:17px;font-weight:500;color:#94a3b8;'>\1</span>",
        text,
    )


def _pct_to_grade9(pct: float) -> int:
    """모의고사 백분위 → 9등급 근사값 (수능 기준)."""
    if pct >= 96: return 1
    if pct >= 89: return 2
    if pct >= 77: return 3
    if pct >= 60: return 4
    if pct >= 40: return 5
    if pct >= 23: return 6
    if pct >= 11: return 7
    if pct >= 4:  return 8
    return 9


def _eng_grade_to_raw_range(grade: float) -> str:
    """수능 영어 절대평가 등급 → 원점수 범위 문자열."""
    g = int(round(float(grade)))
    ranges = {1: "90점↑", 2: "80~89점", 3: "70~79점", 4: "60~69점",
              5: "50~59점", 6: "40~49점", 7: "30~39점", 8: "20~29점", 9: "0~19점"}
    return ranges.get(g, "")


def clean_display_id(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _mask_id(s: str) -> str:
    s = str(s).strip()
    if len(s) <= 2:
        return s
    return s[:-2] + "**"


def _mask_name(s: str) -> str:
    s = str(s).strip()
    if len(s) <= 1:
        return s
    if len(s) == 2:
        return s[0] + "*"
    return s[0] + "*" + s[2:]


def section_header(title: str):
    st.markdown(f"## {title}")


def info_card(title: str, value: str, note: str = ""):
    st.markdown(
        f"""
        <div style="
            border:1px solid #d0d5dd;
            border-radius:18px;
            padding:18px 20px;
            background:#ffffff;
            box-shadow:0 1px 2px rgba(16,24,40,0.04);
            min-height:120px;
        ">
            <div style="font-size:14px;color:#475467;font-weight:700;">{title}</div>
            <div style="font-size:34px;color:#101828;font-weight:800;margin-top:10px;">{value}</div>
            <div style="font-size:13px;color:#667085;margin-top:10px;line-height:1.6;">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def colored_reason_box(title: str, lines: list[str], bg="#eef4ff", border="#b2ccff"):
    inner = "".join([f"<li style='margin-bottom:8px;'>{line}</li>" for line in lines])
    st.markdown(
        f"""
        <div style="
            border:1px solid {border};
            border-radius:18px;
            padding:18px 20px;
            background:{bg};
            margin-top:6px;
            margin-bottom:12px;
        ">
            <div style="font-size:16px;font-weight:800;color:#1d2939;margin-bottom:10px;">{title}</div>
            <ul style="margin:0 0 0 18px;padding:0;color:#344054;line-height:1.7;">
                {inner}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rename_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    rename_map = {
        "case_code": "사례 코드",
        "student_id": "학번",
        "name": "이름",
        "track": "계열",
        "grade_similarity": "내신 유사도",
        "mock_similarity": "모의 유사도",
        "total_similarity": "통합 유사도",
        "grade_confidence": "내신 근거 비중",
        "mock_confidence": "모의 근거 비중",
        "total_confidence": "통합 근거 비중",
        "susi_summary": "수시 결과 요약",
        "jungsi_summary": "정시 결과 요약",
        "source": "구분",
        "college": "대학",
        "department": "모집단위",
        "admission_name": "전형명",
        "first_result": "1차 결과",
        "final_result": "최종 결과",
        "registered": "등록 여부",
    }
    return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})


def find_id_col(df: pd.DataFrame):
    for c in ["student_id", "학번"]:
        if c in df.columns:
            return c
    return None


def find_name_col(df: pd.DataFrame):
    for c in ["name", "이름", "성명"]:
        if c in df.columns:
            return c
    return None


def find_track_col(df: pd.DataFrame):
    for c in ["track", "계열", "계열값"]:
        if c in df.columns:
            return c
    return None


def get_student_title(data: dict) -> str:
    info = data.get("basic_info", {})
    sid = safe_str(info.get("student_id", ""))
    name = safe_str(info.get("name", ""))
    if sid and name:
        return f"세화고 {sid} {name} 성적 분석 결과"
    if name:
        return f"세화고 {name} 성적 분석 결과"
    return "세화고 성적 분석 결과"


def get_case_identity_map(top_cases: pd.DataFrame, graduate_db: dict) -> pd.DataFrame:
    if not isinstance(top_cases, pd.DataFrame) or top_cases.empty or "student_id" not in top_cases.columns:
        return pd.DataFrame()

    source_df = None
    for key in ["grade", "susi", "jungsi"]:
        df = graduate_db.get(key, pd.DataFrame())
        if isinstance(df, pd.DataFrame) and not df.empty and find_id_col(df):
            source_df = df.copy()
            break

    if source_df is None:
        return pd.DataFrame()

    id_col = find_id_col(source_df)
    name_col = find_name_col(source_df)
    track_col = find_track_col(source_df)

    keep = [c for c in [id_col, name_col, track_col] if c]
    base = source_df[keep].copy().drop_duplicates()
    base = base.rename(columns={id_col: "student_id"})
    if name_col:
        base = base.rename(columns={name_col: "name"})
    if track_col:
        base = base.rename(columns={track_col: "track"})

    merged = top_cases.merge(base, on="student_id", how="left")
    cols = [c for c in ["case_code", "student_id", "name", "track", "grade_similarity", "mock_similarity", "total_similarity"] if c in merged.columns]
    return merged[cols].copy()


def prettify_summary_text(text: str) -> str:
    if not text or (isinstance(text, float) and pd.isna(text)):
        return "기록 없음"
    text = str(text)
    text = text.replace("(합)", "🟢 합격")
    text = text.replace("(불)", "🔴 불합격")
    text = text.replace("(등록)", "🔵 등록")
    return text


def susi_summary(student_id, susi_df):
    if susi_df.empty:
        return ""

    id_col = find_id_col(susi_df)
    if not id_col:
        return ""

    sid = clean_display_id(student_id)
    rows = susi_df[susi_df[id_col].astype(str).str.replace(".0", "", regex=False) == sid]
    if rows.empty:
        return ""

    parts = []
    for _, r in rows.head(3).iterrows():
        college = r.get("college", r.get("대학", ""))
        dept = r.get("department", r.get("학과", r.get("모집단위", "")))
        final_result = r.get("final_result", r.get("최종결과", ""))
        parts.append(f"{college}-{dept}({final_result})")
    return " / ".join(parts)


def jungsi_summary(student_id, jungsi_df):
    if jungsi_df.empty:
        return ""

    id_col = find_id_col(jungsi_df)
    if not id_col:
        return ""

    sid = clean_display_id(student_id)
    rows = jungsi_df[jungsi_df[id_col].astype(str).str.replace(".0", "", regex=False) == sid]
    if rows.empty:
        return ""

    parts = []
    for _, r in rows.head(3).iterrows():
        college = r.get("college", r.get("대학", ""))
        dept = r.get("department", r.get("학과", r.get("모집단위", "")))
        final_result = r.get("final_result", r.get("최종결과", ""))
        parts.append(f"{college}-{dept}({final_result})")
    return " / ".join(parts)


SUBJECT_LABEL_MAP = {
    # 내신 등급
    "all_grade": "전교과 등급",
    "ksy_grade": "국수영 등급",
    "kor_grade": "국어 등급",
    "math_grade": "수학 등급",
    "eng_grade": "영어 등급",
    "soc_grade": "사회 등급",
    "sci_grade": "과학 등급",
    # 교내 상대위치 (0~1, 높을수록 상위)
    "all_pos": "전교과 교내위치",
    "ksy_pos": "국수영 교내위치",
    "kor_pos": "국어 교내위치",
    "math_pos": "수학 교내위치",
    # 모의고사
    "mock_kor_percentile": "모의 국어 백분위",
    "mock_math_percentile": "모의 수학 백분위",
    "mock_eng_grade": "모의 영어 등급",
    "mock_soc_grade": "모의 사회/탐구 등급",
    "mock_sci_grade": "모의 과학/탐구 등급",
    "mock_ks_percentile": "모의 국수탐 백분위합",
    "mock_ks_pct_sum":    "모의 국수탐 백분위합",   # 현재 학생 4과목 합산 (졸업생 mock_ks_percentile과 비교)
    "mock_ks_pos (교내위치)": "모의 교내 상대위치",
}


def to_display_label(key: str) -> str:
    return SUBJECT_LABEL_MAP.get(key, key)


def safe_list(v):
    return v if isinstance(v, list) else []


def build_similarity_reason_lines(row: pd.Series, max_lines: int = 4) -> list[str]:
    reasons = []
    grade_detail = safe_list(row.get("grade_detail"))
    mock_detail = safe_list(row.get("mock_detail"))

    merged = []
    for item in grade_detail + mock_detail:
        if isinstance(item, dict):
            score = pd.to_numeric(item.get("부분점수"), errors="coerce")
            weight = pd.to_numeric(item.get("가중치"), errors="coerce")
            merged.append(
                {
                    "항목": item.get("항목"),
                    "현재값": item.get("현재값"),
                    "졸업생값": item.get("졸업생값"),
                    "기여도": (0 if pd.isna(score) else score) * (0 if pd.isna(weight) else weight),
                }
            )

    # 고정 우선순위: 전교과 교내위치 → 국수영 교내위치 → 국수탐 백분위합 → 수학 백분위 → 국어 백분위 → 교내위치
    _REASON_ORDER = {
        "all_pos": 0,
        "ksy_pos": 1,
        "mock_ks_percentile": 2,
        "mock_math_percentile": 3,
        "mock_kor_percentile": 4,
        "mock_ks_pos (교내위치)": 5,
    }
    merged = sorted(merged,
                    key=lambda x: (_REASON_ORDER.get(x["항목"] or "", 99), -x["기여도"]))

    def _fmt_reason_val(key: str, v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        # 국수탐 백분위합은 0~400 스케일 — _fmt_percentile(100 - v) 쓰면 음수 발생
        if key in ("mock_ks_percentile", "mock_ks_pct_sum"):
            v_num = float(v)
            if v_num > 100:
                return f"백분위합 {int(round(v_num))}"
            return _fmt_percentile(v)
        if "percentile" in key:
            return _fmt_percentile(v)
        if "_pos" in key or key == "mock_ks_pos (교내위치)":
            # grade_detail의 값은 _pop_normalize로 0~100 정규화된 값 (raw 0-1 아님)
            # _fmt_pos는 0-1 범위를 가정하므로 여기서 사용하면 음수 % 발생
            fv = float(v)
            top_pct = max(0, round(100 - fv))
            return f"{fv:.1f} (상위 약 {top_pct}%)"
        if "mock_eng" in key or "mock_soc" in key or "mock_sci" in key:
            return _fmt_mock_grade(v)
        return format_value(v)

    for item in merged[:max_lines]:
        key = item['항목'] or ""
        reasons.append(
            f"{to_display_label(key)}: 현재 {_fmt_reason_val(key, item['현재값'])} / 사례 {_fmt_reason_val(key, item['졸업생값'])}"
        )

    if not reasons:
        grade_conf = pd.to_numeric(row.get("grade_confidence"), errors="coerce")
        mock_conf = pd.to_numeric(row.get("mock_confidence"), errors="coerce")

        if pd.notna(grade_conf) and grade_conf > 0 and (pd.isna(mock_conf) or mock_conf == 0):
            reasons.append("내신 기준 비교는 가능했으나, 모의고사 비교 축이 부족했습니다.")
        elif pd.notna(mock_conf) and mock_conf > 0 and (pd.isna(grade_conf) or grade_conf == 0):
            reasons.append("모의고사 기준 비교는 가능했으나, 내신 비교 축이 부족했습니다.")
        else:
            reasons.append("비교 가능한 세부 성적 항목 정보가 부족합니다.")

    return reasons

def count_result_tokens(top_cases: pd.DataFrame) -> dict:
    joined = ""
    if isinstance(top_cases, pd.DataFrame) and not top_cases.empty:
        for col in ["susi_summary", "jungsi_summary"]:
            if col in top_cases.columns:
                joined += " " + " ".join(top_cases[col].fillna("").astype(str).tolist())

    return {
        "합": joined.count("(합)"),
        "불": joined.count("(불)"),
        "등록": joined.count("(등록)"),
    }


def build_fit_evidence_lines(current: dict, fit_scores: list[dict], top_cases: pd.DataFrame) -> list[str]:
    lines = []

    if safe_str(current.get("grade_basis_detail")):
        lines.append(current.get("grade_basis_detail"))
    if safe_str(current.get("mock_basis_detail")):
        lines.append(current.get("mock_basis_detail"))

    if current.get("all_pos") is not None and not pd.isna(current.get("all_pos")):
        lines.append(f"전교과 교내 상대 위치는 {_fmt_pos(current.get('all_pos'))}입니다.")
    if current.get("ksy_pos") is not None and not pd.isna(current.get("ksy_pos")):
        lines.append(f"국수영 교내 상대 위치는 {_fmt_pos(current.get('ksy_pos'))}입니다.")
    if current.get("mock_ks_percentile") is not None and not pd.isna(current.get("mock_ks_percentile")):
        _ks_v = float(current.get("mock_ks_percentile"))
        _ks_str = f"백분위합 {int(round(_ks_v))}" if _ks_v > 100 else _fmt_percentile(_ks_v)
        lines.append(f"모의 국수탐 백분위는 {_ks_str}입니다.")
    if current.get("mock_eng_grade") is not None and not pd.isna(current.get("mock_eng_grade")):
        lines.append(f"모의 영어 등급은 {_fmt_mock_grade(current.get('mock_eng_grade'))}입니다.")

    counts = count_result_tokens(top_cases)
    lines.append(
        f"상위 유사 사례 기준으로 확인된 결과는 합격 {counts['합']}건, 불합격 {counts['불']}건, 등록 {counts['등록']}건입니다."
    )

    if fit_scores:
        sorted_scores = sorted(
            fit_scores,
            key=lambda x: pd.to_numeric(x.get("score", x.get("적합도 점수")), errors="coerce"),
            reverse=True,
        )
        best = sorted_scores[0]
        best_name = best.get("name", best.get("전형 유형", "전형"))
        best_score = best.get("score", best.get("적합도 점수", "-"))
        lines.append(f"현재 계산상 가장 높은 전형은 '{best_name}'이며 적합도 점수는 {format_value(best_score)}입니다.")

    return lines


def _admission_cards_html(rows_list: list, show_adm_detail: bool = False) -> str:
    """수시 또는 정시 결과 행들을 결과 유형별로 묶어 박스 하나에 표시."""
    if not rows_list:
        return "<span style='font-size:12px;color:#94a3b8;'>기록 없음</span>"

    def _classify(result: str):
        if "등록" in result:
            return "등록"
        if "합" in result and "불합" not in result:
            return "합격"
        if "불합" in result or result == "불":
            return "불합격"
        if "예비" in result:
            return "예비"
        return "기타"

    styles = {
        "등록":  ("#eff6ff", "#3b82f6", "🔵 등록"),
        "합격":  ("#f0fdf4", "#22c55e", "✅ 합격"),
        "예비":  ("#fffbeb", "#f59e0b", "🟡 예비"),
        "불합격": ("#fef2f2", "#ef4444", "❌ 불합격"),
        "기타":  ("#f8fafc", "#94a3b8", "📋 기타"),
    }
    order = ["등록", "합격", "예비", "불합격", "기타"]

    groups: dict = {k: [] for k in order}
    for r in rows_list:
        result = str(r.get("final_result", "")).strip()
        key = _classify(result)
        college = safe_str(r.get("college", ""))
        dept = safe_str(r.get("department", ""))
        adm = safe_str(r.get("admission_name", ""))
        method = safe_str(r.get("admission_method", ""))
        minimum = safe_str(r.get("minimum_requirement", ""))
        label = (
            f"<span style='color:#1e293b;font-weight:600;'>{college}</span>"
            f"<span style='color:#64748b;'> / {dept}</span>"
        )
        if adm and adm not in ["-", "nan"]:
            label += f"<br><span style='color:#64748b;font-size:10px;'>📋 {adm}</span>"
        if show_adm_detail:
            if method and method not in ["-", "nan"]:
                label += f"<br><span style='color:#7c3aed;font-size:10px;'>🔹 {method}</span>"
            if minimum and minimum not in ["-", "nan"]:
                label += f"<br><span style='color:#b45309;font-size:10px;'>⚠️ 최저: {minimum}</span>"
        groups[key].append(label)

    parts = []
    for key in order:
        items = groups[key]
        if not items:
            continue
        bg, border, header = styles[key]
        rows_html = "".join(
            f"<div style='padding:3px 0;border-bottom:1px solid {border}22;'>{item}</div>"
            for item in items
        )
        parts.append(
            f"<div style='border:1.5px solid {border};border-radius:8px;"
            f"padding:6px 10px;background:{bg};margin-bottom:5px;font-size:11px;line-height:1.7;'>"
            f"<div style='font-weight:700;color:{border};margin-bottom:4px;'>{header}</div>"
            f"{rows_html}</div>"
        )
    return "".join(parts)


def render_case_cards(
    top_cases: pd.DataFrame,
    susi_df: pd.DataFrame = None,
    jungsi_df: pd.DataFrame = None,
    sim_col: str = "total_similarity",
    show_adm_detail: bool = False,
):
    if not isinstance(top_cases, pd.DataFrame) or top_cases.empty:
        st.info("표시할 유사 사례가 없습니다.")
        return

    sim_display_label = {
        "total_similarity": "통합 유사도",
        "grade_similarity": "내신 유사도",
        "mock_similarity": "모의 유사도",
    }.get(sim_col, "유사도")

    for _, row in top_cases.head(8).iterrows():
        case_code = safe_str(row.get("case_code", "-"))
        sim_score = format_value(row.get(sim_col))
        grade_similarity = format_value(row.get("grade_similarity"))
        mock_similarity = format_value(row.get("mock_similarity"))
        reason_lines = build_similarity_reason_lines(row, max_lines=4)

        # 학생별 실제 지원 결과 조회
        student_id = str(row.get("student_id", "")).replace(".0", "").strip()
        susi_rows, jungsi_rows = [], []

        if susi_df is not None and not susi_df.empty:
            id_col = find_id_col(susi_df)
            if id_col:
                matching = susi_df[
                    susi_df[id_col].astype(str).str.replace(".0", "", regex=False).str.strip() == student_id
                ]
                susi_rows = [r for _, r in matching.iterrows()]

        if jungsi_df is not None and not jungsi_df.empty:
            id_col = find_id_col(jungsi_df)
            if id_col:
                matching = jungsi_df[
                    jungsi_df[id_col].astype(str).str.replace(".0", "", regex=False).str.strip() == student_id
                ]
                jungsi_rows = [r for _, r in matching.iterrows()]

        with st.container(border=True):
            left, right = st.columns([1.1, 2.9])

            with left:
                st.markdown(f"### {case_code}")
                st.caption(f"{sim_display_label} {sim_score}")
                if sim_col == "total_similarity":
                    st.caption(f"내신 {grade_similarity} / 모의 {mock_similarity}")

            with right:
                st.markdown(
                    "<div style='font-size:13px;font-weight:700;color:#344054;margin-bottom:6px;'>"
                    "왜 이 사례를 유사 사례로 보았는가</div>",
                    unsafe_allow_html=True,
                )
                items = reason_lines[:4] if reason_lines else ["비교 가능한 세부 성적 항목 정보가 부족합니다."]
                # 2행 × 2열 컴팩트 그리드
                for i in range(0, len(items), 2):
                    pair = items[i:i+2]
                    rcols = st.columns(len(pair))
                    for j, line in enumerate(pair):
                        with rcols[j]:
                            st.markdown(
                                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;"
                                f"border-radius:7px;padding:6px 10px;font-size:12px;"
                                f"line-height:1.6;color:#334155;'>{line}</div>",
                                unsafe_allow_html=True,
                            )

                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                res_c1, res_c2 = st.columns(2)
                with res_c1:
                    st.markdown(
                        "<div style='font-size:12px;font-weight:700;color:#344054;margin-bottom:4px;'>📋 수시 결과</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(_admission_cards_html(susi_rows, show_adm_detail=show_adm_detail), unsafe_allow_html=True)
                with res_c2:
                    st.markdown(
                        "<div style='font-size:12px;font-weight:700;color:#344054;margin-bottom:4px;'>📋 정시 결과</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(_admission_cards_html(jungsi_rows, show_adm_detail=show_adm_detail), unsafe_allow_html=True)


def build_passing_analysis(
    top_cases: pd.DataFrame,
    susi_df: pd.DataFrame,
    jungsi_df: pd.DataFrame,
    current_features=None,
    graduates_df=None,
    all_sim_df=None,
) -> dict:
    """
    상위 유사 사례들의 실제 합격/등록 결과를 분석.
    - 유사 학생(적정권): 현재 학생과 유사도가 높은 졸업생 합격 사례
    - 인접 구간(안정권): 현재 학생보다 성적이 살짝 낮은 졸업생 합격 사례
    """
    empty = {"susi": pd.DataFrame(), "jungsi": pd.DataFrame(),
             "susi_below": pd.DataFrame(), "jungsi_below": pd.DataFrame()}

    if top_cases.empty or "student_id" not in top_cases.columns:
        return empty

    # 유사도 매핑 (학번·이름 포함)
    sim_map = {}
    for _, row in top_cases.iterrows():
        sid = str(row.get("student_id", "")).replace(".0", "").strip()
        sim_map[sid] = {
            "case_code": safe_str(row.get("case_code", "")),
            "total_similarity": float(row.get("total_similarity", 0) or 0),
            "student_id": sid,
            "name": safe_str(row.get("name", "")),
        }
    case_ids = set(sim_map.keys())

    def _is_pass(row_r, result_col="final_result", reg_col="registered"):
        fr = str(row_r.get(result_col, "")).strip()
        rg = str(row_r.get(reg_col, "")).strip()
        if "합" in fr and "불합" not in fr:
            return True
        if rg and rg not in ["-", "nan", "", "X", "x", "불"]:
            return True
        return False

    def _process_df(df, id_set, code_map, extra_cols):
        if df.empty or "student_id" not in df.columns:
            return pd.DataFrame()
        d = df.copy()
        d["_sid"] = d["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
        d = d[d["_sid"].isin(id_set)].copy()
        if d.empty:
            return pd.DataFrame()
        passed = d[d.apply(_is_pass, axis=1)].copy()
        if passed.empty:
            return pd.DataFrame()
        passed["사례코드"] = passed["_sid"].map(lambda x: code_map.get(x, {}).get("case_code", x))
        passed["학번"]   = passed["_sid"].map(lambda x: code_map.get(x, {}).get("student_id", x))
        passed["이름"]   = passed["_sid"].map(lambda x: code_map.get(x, {}).get("name", ""))
        keep = [c for c in ["사례코드", "학번", "이름"] + extra_cols if c in passed.columns]
        return passed[keep].copy()

    # ── 적정권 (유사 학생) ────────────────────────────────────────────────────
    susi_out = _process_df(
        susi_df, case_ids, sim_map,
        ["college", "department", "admission_name", "admission_method", "minimum_requirement",
         "admission_group", "final_result", "registered"],
    )
    jungsi_out = _process_df(
        jungsi_df, case_ids, sim_map,
        ["college", "department", "admission_name", "admission_method", "minimum_requirement",
         "gun", "final_result", "registered"],
    )
    if not susi_out.empty:
        susi_out["구분"] = "적정권"
        susi_out["유사도"] = susi_out["학번"].map(
            lambda x: round(sim_map.get(x, {}).get("total_similarity", 0), 1))
    if not jungsi_out.empty:
        jungsi_out["구분"] = "적정권"
        jungsi_out["유사도"] = jungsi_out["학번"].map(
            lambda x: round(sim_map.get(x, {}).get("total_similarity", 0), 1))

    # ── 안정권 (성적 하위 학생) ───────────────────────────────────────────────
    susi_below = pd.DataFrame()
    jungsi_below = pd.DataFrame()

    if (current_features is not None
            and graduates_df is not None
            and not graduates_df.empty
            and "student_id" in graduates_df.columns):

        gf = graduates_df.copy()
        gf["_sid"] = gf["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()

        below_mask = pd.Series([False] * len(gf), index=gf.index)

        try:
            cur_grade = float(current_features.get("all_grade") or 0)
            if cur_grade > 0 and "all_grade" in gf.columns:
                gm = gf["all_grade"].apply(
                    lambda x: (cur_grade + 0.3) <= float(x) <= (cur_grade + 0.8)
                    if pd.notna(x) and x not in ("", "-") else False
                )
                below_mask = below_mask | gm
        except Exception:
            pass

        try:
            cur_pct = float(current_features.get("mock_ks_percentile") or 0)
            if cur_pct > 0 and "mock_ks_percentile" in gf.columns:
                mm = gf["mock_ks_percentile"].apply(
                    lambda x: (cur_pct - 15) <= float(x) <= (cur_pct - 5)
                    if pd.notna(x) and x not in ("", "-") else False
                )
                below_mask = below_mask | mm
        except Exception:
            pass

        below_rows = gf[below_mask & ~gf["_sid"].isin(case_ids)]
        below_ids = set(below_rows["_sid"].tolist())

        if below_ids:
            # 전체 유사도 조회용 맵 (all_sim_df 활용)
            full_sim_lookup: dict = {}
            if all_sim_df is not None and not all_sim_df.empty and "student_id" in all_sim_df.columns:
                for _, _sr in all_sim_df.iterrows():
                    _fsid = str(_sr.get("student_id", "")).replace(".0", "").strip()
                    full_sim_lookup[_fsid] = float(_sr.get("total_similarity", 0) or 0)

            _ALPHA26 = 'abcdefghijklmnopqrstuvwxyz'
            name_map = {}
            for _bidx, (_, r) in enumerate(below_rows.drop_duplicates("_sid").iterrows()):
                sid = r["_sid"]
                _label = (_ALPHA26[_bidx] if _bidx < 26
                          else _ALPHA26[_bidx // 26 - 1] + _ALPHA26[_bidx % 26])
                name_map[sid] = {
                    "case_code": f"사례{_label}",
                    "student_id": sid,
                    "name": safe_str(r.get("name", "")),
                }

            susi_below = _process_df(
                susi_df, below_ids, name_map,
                ["college", "department", "admission_name", "admission_method", "minimum_requirement",
                 "admission_group", "final_result", "registered"],
            )
            jungsi_below = _process_df(
                jungsi_df, below_ids, name_map,
                ["college", "department", "admission_name", "admission_method", "minimum_requirement",
                 "gun", "final_result", "registered"],
            )
            if not susi_below.empty:
                susi_below["구분"] = "안정권"
                susi_below["유사도"] = susi_below["학번"].map(
                    lambda x: round(full_sim_lookup.get(str(x).replace(".0", "").strip(), 0), 1))
            if not jungsi_below.empty:
                jungsi_below["구분"] = "안정권"
                jungsi_below["유사도"] = jungsi_below["학번"].map(
                    lambda x: round(full_sim_lookup.get(str(x).replace(".0", "").strip(), 0), 1))

    return {
        "susi": susi_out,
        "jungsi": jungsi_out,
        "susi_below": susi_below,
        "jungsi_below": jungsi_below,
    }


def _passing_card_html(records: list, show_adm_name: bool = True, show_gun: bool = False,
                       show_adm_detail: bool = False) -> str:
    """합격/등록 레코드를 카드 HTML로 변환 (전형명·군·전형방법·최저 표시 옵션)."""
    if not records:
        return "<span style='font-size:12px;color:#94a3b8;'>없음</span>"
    parts = []
    for r in records:
        college = safe_str(r.get("college", ""))
        dept = safe_str(r.get("department", ""))
        result = str(r.get("final_result", "")).strip()
        reg = str(r.get("registered", "")).strip()
        adm = safe_str(r.get("admission_name", ""))
        gun = safe_str(r.get("gun", ""))
        method = safe_str(r.get("admission_method", ""))
        minimum = safe_str(r.get("minimum_requirement", ""))
        if reg and reg not in ["-", "nan", "", "X", "x", "불", "None"]:
            emoji, bg, border = "🔵", "#eff6ff", "#3b82f6"
        else:
            emoji, bg, border = "✅", "#f0fdf4", "#22c55e"
        sub_parts = []
        if show_adm_name and adm:
            sub_parts.append(f"<span style='color:#64748b;font-size:10px;'>📋 {adm}</span>")
        if show_gun and gun:
            sub_parts.append(f"<span style='color:#94a3b8;font-size:10px;'>({gun}군)</span>")
        if show_adm_detail:
            if method and method not in ["-", "nan"]:
                sub_parts.append(f"<span style='color:#7c3aed;font-size:10px;'>🔹 {method}</span>")
            if minimum and minimum not in ["-", "nan"]:
                sub_parts.append(f"<span style='color:#b45309;font-size:10px;'>⚠️ 최저: {minimum}</span>")
        sub = "<br>".join(sub_parts)
        parts.append(
            f"<div style='border:1.5px solid {border};border-radius:8px;"
            f"padding:5px 10px;background:{bg};margin-bottom:4px;font-size:11px;line-height:1.6;'>"
            f"<span style='font-weight:700;color:{border};'>{emoji} {result}</span><br>"
            f"<span style='color:#1e293b;font-weight:600;'>{college}</span>"
            f"<span style='color:#64748b;'> / {dept}</span>"
            + (f"<br>{sub}" if sub else "")
            + "</div>"
        )
    return "".join(parts)


def render_passing_tab(
    top_cases: pd.DataFrame,
    susi_df: pd.DataFrame,
    jungsi_df: pd.DataFrame,
    current_features=None,
    graduates_df=None,
    all_sim_df=None,
):
    passing = build_passing_analysis(
        top_cases, susi_df, jungsi_df,
        current_features=current_features,
        graduates_df=graduates_df,
        all_sim_df=all_sim_df,
    )
    susi_p       = passing["susi"]
    jungsi_p     = passing["jungsi"]
    susi_below   = passing["susi_below"]
    jungsi_below = passing["jungsi_below"]

    has_similar = not susi_p.empty or not jungsi_p.empty
    has_below   = not susi_below.empty or not jungsi_below.empty

    if not has_similar and not has_below:
        st.info("합격/등록 결과가 확인되지 않습니다.")
        return

    st.markdown(
        """
        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:14px 18px;margin-bottom:14px;font-size:13px;">
        <b>읽는 방법</b><br>
        🟢 <b>유사 학생</b>: 현재 학생과 성적이 유사한 졸업생들이 합격한 사례입니다.<br>
        🔵 <b>인접 구간</b>: 현재 학생보다 성적이 살짝 낮은 졸업생들도 합격한 사례입니다 — 현재 학생에게 더 유리한 참고 정보입니다.<br>
        본 결과는 상담 참고용이며 실제 합격을 보장하지 않습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    BADGE = {
        "적정권": ("#dcfce7", "#166534"),   # 초록
        "안정권": ("#dbeafe", "#1e40af"),   # 파랑
    }
    DISPLAY_LABEL = {
        "적정권": "유사 학생",
        "안정권": "인접 구간",
    }

    def _collect_codes(s_df, j_df):
        seen, codes = set(), []
        for df in [s_df, j_df]:
            if not df.empty and "사례코드" in df.columns:
                for c in df["사례코드"].tolist():
                    if c and c not in seen:
                        seen.add(c); codes.append(c)
        return codes

    def _info_map(s_df, j_df, sim_key="유사도"):
        m = {}
        for df in [s_df, j_df]:
            if not df.empty and "사례코드" in df.columns:
                for _, row in df.iterrows():
                    code = safe_str(row.get("사례코드", ""))
                    if code and code not in m:
                        m[code] = {
                            "유사도": float(row.get(sim_key, 0) or 0),
                            "구분": safe_str(row.get("구분", "")),
                        }
        return m

    # ── 전형방법·최저학력기준 표시 토글 ──────────────────────────────────────
    _show_adm_detail = st.toggle("📋 전형방법·최저학력기준 보기", value=False, key="passing_adm_detail")

    def _render_cards(s_df, j_df, show_sim=True):
        codes    = _collect_codes(s_df, j_df)
        info_map = _info_map(s_df, j_df)
        for code in codes:
            info     = info_map.get(code, {})
            sim      = info.get("유사도", 0)
            category = info.get("구분", "")
            badge_bg, badge_color = BADGE.get(category, ("#f1f5f9", "#475569"))

            case_susi = (
                s_df[s_df["사례코드"] == code].to_dict("records")
                if not s_df.empty and "사례코드" in s_df.columns else []
            )
            case_jungsi = (
                j_df[j_df["사례코드"] == code].to_dict("records")
                if not j_df.empty and "사례코드" in j_df.columns else []
            )

            with st.container(border=True):
                left, right = st.columns([1.1, 2.9])
                with left:
                    st.markdown(f"### {code}")
                    if show_sim and sim:
                        st.caption(f"유사도 {sim:.1f}%")
                    st.markdown(
                        f"<span style='background:{badge_bg};color:{badge_color};border-radius:5px;"
                        f"padding:2px 10px;font-size:12px;font-weight:700;'>{DISPLAY_LABEL.get(category, category)}</span>",
                        unsafe_allow_html=True,
                    )
                with right:
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown(
                            "<div style='font-size:12px;font-weight:700;color:#344054;margin-bottom:4px;'>📋 수시 합격</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(_passing_card_html(case_susi, show_adm_name=True,
                                                       show_adm_detail=_show_adm_detail), unsafe_allow_html=True)
                    with rc2:
                        st.markdown(
                            "<div style='font-size:12px;font-weight:700;color:#344054;margin-bottom:4px;'>📋 정시 합격</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(_passing_card_html(case_jungsi, show_gun=True,
                                                       show_adm_detail=_show_adm_detail), unsafe_allow_html=True)

    # ── 유사 학생 섹션 ────────────────────────────────────────────────────────
    if has_similar:
        st.markdown(
            "<div style='background:#f0fdf4;border-left:4px solid #22c55e;"
            "border-radius:6px;padding:8px 14px;margin:12px 0 10px 0;"
            "font-weight:700;color:#166534;font-size:14px;'>🟢 유사 학생 합격 사례</div>",
            unsafe_allow_html=True,
        )
        _render_cards(susi_p, jungsi_p, show_sim=True)

    # ── 인접 구간 섹션 ────────────────────────────────────────────────────────
    if has_below:
        st.markdown(
            "<div style='background:#eff6ff;border-left:4px solid #3b82f6;"
            "border-radius:6px;padding:8px 14px;margin:20px 0 10px 0;"
            "font-weight:700;color:#1e40af;font-size:14px;'>🔵 인접 구간 합격 사례</div>",
            unsafe_allow_html=True,
        )
        _render_cards(susi_below, jungsi_below, show_sim=True)

    # ── 교사용 상세 보기 ──────────────────────────────────────────────────────
    _serial_pass = {}
    _gdb = st.session_state.get("graduate_db") or {}
    _raw_grade_pass = _gdb.get("grade", pd.DataFrame()) if isinstance(_gdb, dict) else pd.DataFrame()
    if isinstance(_raw_grade_pass, pd.DataFrame) and not _raw_grade_pass.empty \
            and "serial_no" in _raw_grade_pass.columns and "student_id" in _raw_grade_pass.columns:
        for _, _r in _raw_grade_pass.drop_duplicates("student_id").iterrows():
            _sid = str(_r.get("student_id", "")).replace(".0", "").strip()
            _serial_pass[_sid] = _r.get("serial_no", "")

    def _apply_passing_mask(df):
        if st.session_state.get("_passing_show_full", False):
            return df
        d = df.copy()
        if "학번" in d.columns:
            d["학번"] = d["학번"].astype(str).apply(_mask_id)
        if "이름" in d.columns:
            d["이름"] = d["이름"].astype(str).apply(_mask_name)
        return d

    def _build_passing_teacher_df(parts_raw, col_rename):
        """적정권+안정권 합쳐서 교사용 테이블 구성."""
        if not parts_raw:
            return pd.DataFrame()
        combined = pd.concat(parts_raw, ignore_index=True)

        # 구분 뱃지 이모지
        def _fmt_cat(v):
            s = str(v)
            if s == "적정권": return "🟢 유사 학생"
            if s == "안정권": return "🔵 인접 구간"
            return s
        if "구분" in combined.columns:
            combined["구분"] = combined["구분"].apply(_fmt_cat)

        # 성적 데이터 병합 (학번 = student_id 기준)
        _gf = st.session_state.get("graduate_features", pd.DataFrame())
        if isinstance(_gf, pd.DataFrame) and not _gf.empty and "student_id" in _gf.columns:
            gf = _gf.copy()
            gf["student_id"] = gf["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
            score_cols = [c for c in [
                "all_grade", "ksy_grade", "kor_grade", "math_grade", "eng_grade",
                "mock_kor_percentile", "mock_math_percentile", "mock_eng_grade", "mock_ks_percentile",
            ] if c in gf.columns]
            if score_cols:
                combined = combined.merge(
                    gf[["student_id"] + score_cols].rename(columns={"student_id": "학번"}),
                    on="학번", how="left",
                )

        # 일련번호 삽입 (마스킹 전에 raw 학번으로 조회)
        if _serial_pass and "학번" in combined.columns:
            serial_vals = combined["학번"].astype(str).str.strip().map(lambda x: _serial_pass.get(x, ""))
            combined.insert(0, "일련번호", serial_vals)

        # 마스킹
        combined = _apply_passing_mask(combined)

        # 열 이름 변환 (등록·유사도 제외)
        grade_rename = {
            "all_grade": "전교과 등급", "ksy_grade": "국수영 등급",
            "kor_grade": "국어 등급", "math_grade": "수학 등급", "eng_grade": "영어 등급",
            "mock_kor_percentile": "모의 국어 백분위", "mock_math_percentile": "모의 수학 백분위",
            "mock_eng_grade": "모의 영어 등급", "mock_ks_percentile": "모의 국수탐 백분위합",
        }
        all_rename = {**col_rename, **grade_rename}
        combined = combined.rename(columns={k: v for k, v in all_rename.items() if k in combined.columns})

        # 불필요 열 제거
        combined = combined.drop(columns=[c for c in ["등록", "유사도", "유사도(%)", "registered"] if c in combined.columns], errors="ignore")

        # 열 순서: 구분 → 일련번호 → 사례코드 → 학번 → 이름 → 성적 → 입시결과
        priority = [
            "구분", "일련번호", "사례코드", "학번", "이름",
            "전교과 등급", "국수영 등급", "국어 등급", "수학 등급", "영어 등급",
            "모의 국어 백분위", "모의 수학 백분위", "모의 영어 등급", "모의 국수탐 백분위합",
        ]
        rest = [c for c in combined.columns if c not in priority]
        combined = combined[[c for c in priority if c in combined.columns] + rest]
        return combined

    susi_col_rename = {
        "college": "대학", "department": "모집단위",
        "admission_name": "전형명", "admission_method": "전형방법",
        "minimum_requirement": "최저학력기준", "admission_group": "전형분류",
        "final_result": "최종결과",
    }
    jungsi_col_rename = {
        "college": "대학", "department": "모집단위",
        "admission_name": "전형명", "admission_method": "전형방법",
        "minimum_requirement": "최저학력기준", "gun": "군",
        "final_result": "최종결과",
    }

    _passing_show_full = st.toggle("🔓 학번·이름 보기", value=False, key="passing_show_full")
    st.session_state["_passing_show_full"] = _passing_show_full
    with st.expander("교사용 상세 보기"):
        ptab1, ptab2 = st.tabs(["수시 합격", "정시 합격"])
        with ptab1:
            df_t = _build_passing_teacher_df(
                [d for d in [susi_p, susi_below] if not d.empty],
                susi_col_rename,
            )
            if df_t.empty:
                st.info("수시 합격 사례가 없습니다.")
            else:
                st.dataframe(df_t, use_container_width=True, hide_index=True)
        with ptab2:
            df_t = _build_passing_teacher_df(
                [d for d in [jungsi_p, jungsi_below] if not d.empty],
                jungsi_col_rename,
            )
            if df_t.empty:
                st.info("정시 합격 사례가 없습니다.")
            else:
                st.dataframe(df_t, use_container_width=True, hide_index=True)


def _result_badge(v: str) -> str:
    """최종결과 값을 시각적 이모지+텍스트로 변환."""
    s = str(v).strip()
    if not s or s in ["-", "nan"]:
        return "-"
    if "합" in s and "불합" not in s:
        return "✅ " + s
    if "불합" in s or (s == "불"):
        return "❌ " + s
    if "등록" in s:
        return "🔵 " + s
    if "예비" in s:
        return "🟡 " + s
    return s


def render_fit_case_details(top_cases: pd.DataFrame, susi_df: pd.DataFrame, jungsi_df: pd.DataFrame):
    """전형 적합도 판단에 사용된 실제 사례를 전형 유형별로 보여줌."""
    if top_cases.empty or "student_id" not in top_cases.columns:
        st.info("사례 데이터가 없습니다.")
        return

    # 사례코드 + 학번 + 이름 + 일련번호 매핑
    _gf_fit = st.session_state.get("graduate_features", pd.DataFrame())
    _serial_fit = {}
    if isinstance(_gf_fit, pd.DataFrame) and not _gf_fit.empty and "serial_no" in _gf_fit.columns:
        for _, r in _gf_fit.iterrows():
            sid = str(r.get("student_id", "")).replace(".0", "").strip()
            _serial_fit[sid] = r.get("serial_no", "")

    sim_map = {}
    for _, row in top_cases.iterrows():
        sid = str(row.get("student_id", "")).replace(".0", "").strip()
        sim_map[sid] = {
            "일련번호": _serial_fit.get(sid, ""),
            "사례코드": safe_str(row.get("case_code", "")),
            "학번": sid,
            "이름": safe_str(row.get("name", "")),
        }

    def _add_id_cols(d):
        d["일련번호"] = d["_sid"].map(lambda x: sim_map.get(x, {}).get("일련번호", ""))
        d["사례코드"] = d["_sid"].map(lambda x: sim_map.get(x, {}).get("사례코드", ""))
        d["학번"]    = d["_sid"].map(lambda x: sim_map.get(x, {}).get("학번", ""))
        d["이름"]    = d["_sid"].map(lambda x: sim_map.get(x, {}).get("이름", ""))
        return d

    def get_susi_for_cases(keyword_include, keyword_exclude=None):
        if susi_df.empty or "student_id" not in susi_df.columns:
            return pd.DataFrame()
        d = susi_df.copy()
        d["_sid"] = d["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
        ids = set(sim_map.keys())
        d = d[d["_sid"].isin(ids)].copy()
        if d.empty:
            return pd.DataFrame()
        if "admission_name" in d.columns:
            if keyword_include:
                mask = d["admission_name"].astype(str).str.contains("|".join(keyword_include), na=False)
                d = d[mask]
            if keyword_exclude:
                mask = ~d["admission_name"].astype(str).str.contains("|".join(keyword_exclude), na=False)
                d = d[mask]
        d = _add_id_cols(d)
        keep = [c for c in ["일련번호", "사례코드", "학번", "이름", "college", "department", "admission_name", "final_result", "registered"] if c in d.columns]
        return d[keep].copy()

    def get_jungsi_for_cases():
        if jungsi_df.empty or "student_id" not in jungsi_df.columns:
            return pd.DataFrame()
        d = jungsi_df.copy()
        d["_sid"] = d["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
        ids = set(sim_map.keys())
        d = d[d["_sid"].isin(ids)].copy()
        if d.empty:
            return pd.DataFrame()
        d = _add_id_cols(d)
        keep = [c for c in ["일련번호", "사례코드", "학번", "이름", "college", "department", "admission_name", "gun", "final_result", "registered"] if c in d.columns]
        return d[keep].copy()

    def _display_fit_df(df):
        if df.empty:
            return df
        d = df.copy()
        # 합격 먼저 정렬: 합=0, 등록=1, 예비=2, 기타=3, 불합=4
        if "final_result" in d.columns:
            def _sort_key(v):
                s = str(v).strip()
                if "합" in s and "불합" not in s:
                    return 0
                if "등록" in s:
                    return 1
                if "예비" in s:
                    return 2
                if "불합" in s or s == "불":
                    return 4
                return 3
            d["_sort"] = d["final_result"].apply(_sort_key)
            d = d.sort_values("_sort").drop(columns=["_sort"])
            d["final_result"] = d["final_result"].astype(str).apply(_result_badge)
        d = d.rename(columns={
            "college": "대학", "department": "모집단위",
            "admission_name": "전형명", "gun": "군",
            "final_result": "최종결과", "registered": "등록",
        })
        if not st.session_state.get("_fit_show_full", False):
            if "학번" in d.columns:
                d["학번"] = d["학번"].astype(str).apply(_mask_id)
            if "이름" in d.columns:
                d["이름"] = d["이름"].astype(str).apply(_mask_name)
        return d

    ft1, ft2, ft3, ft4 = st.tabs(["교과/종합형 수시 사례", "논술형 수시 사례", "실기형 수시 사례", "정시 사례"])
    with ft1:
        df = get_susi_for_cases(keyword_include=None, keyword_exclude=["논술", "면접", "실기", "체육", "예체"])
        if df.empty:
            st.info("교과/종합형 수시 사례가 없습니다.")
        else:
            st.dataframe(_display_fit_df(df), use_container_width=True, hide_index=True)
    with ft2:
        df = get_susi_for_cases(keyword_include=["논술"])
        if df.empty:
            st.info("논술형 수시 사례가 없습니다.")
        else:
            st.dataframe(_display_fit_df(df), use_container_width=True, hide_index=True)
    with ft3:
        df = get_susi_for_cases(keyword_include=["실기", "체육", "예체"])
        if df.empty:
            st.info("실기형 수시 사례가 없습니다.")
        else:
            st.dataframe(_display_fit_df(df), use_container_width=True, hide_index=True)
    with ft4:
        df = get_jungsi_for_cases()
        if df.empty:
            st.info("정시 사례가 없습니다.")
        else:
            st.dataframe(_display_fit_df(df), use_container_width=True, hide_index=True)



def build_counseling_data(current: dict, top_cases, susi_df, jungsi_df) -> dict:
    """상담 포인트 4가지 데이터를 dict로 반환 (PDF/화면 공용)."""
    def _sf(v):
        try:
            if v is None or pd.isna(v): return None
            return float(v)
        except Exception: return None

    # ── 성적 구조 ──────────────────────────────────────────────────────
    all_pos = _sf(current.get('all_pos'))
    mock_ks = _sf(current.get('mock_ks_percentile'))
    if all_pos is not None and mock_ks is not None:
        grade_score = round(all_pos * 100, 1)
        diff = grade_score - mock_ks
        if diff > 15:
            bal_type = '내신강세'
            bal_msg  = f'내신 위치 상위 약 {100 - grade_score:.0f}% / 모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%) → 수시 중심 전략이 유리할 수 있습니다.'
        elif diff < -15:
            bal_type = '모의강세'
            bal_msg  = f'모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%) / 내신 위치 상위 약 {100 - grade_score:.0f}% → 정시 가능성도 함께 검토할 만합니다.'
        else:
            bal_type = '균형'
            bal_msg  = f'내신 위치 상위 약 {100 - grade_score:.0f}% / 모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%) → 수시·정시 병행 전략 검토 가능합니다.'
    else:
        bal_type = '데이터부족'
        bal_msg  = '성적 구조 비교를 위한 데이터가 부족합니다.'

    # ── 과목 강약 ──────────────────────────────────────────────────────
    _grade_key_map = {'kor_pos': 'kor_grade', 'math_pos': 'math_grade', 'eng_pos': 'eng_grade',
                      'soc_pos': 'soc_grade',  'sci_pos': 'sci_grade'}
    grade_subj = {}
    for pos_key, label in [('kor_pos','국어'),('math_pos','수학'),('eng_pos','영어'),
                           ('soc_pos','사회'),('sci_pos','과학')]:
        v = _sf(current.get(pos_key))
        if v is not None:
            top_pct = round((1 - v) * 100)
            g_val = _sf(current.get(_grade_key_map.get(pos_key, '')))
            disp = (f'{g_val:.1f}'.rstrip('0').rstrip('.') + f'등급 (상위 약 {top_pct}%)') if g_val is not None else f'(상위 약 {top_pct}%)'
            grade_subj[label] = (top_pct, disp)
    if len(grade_subj) >= 2:
        g_ranked = sorted(grade_subj.items(), key=lambda x: x[1][0])
        g_str = f'{g_ranked[0][0]} {g_ranked[0][1][1]}'
        g_wk  = f'{g_ranked[-1][0]} {g_ranked[-1][1][1]}'
    elif len(grade_subj) == 1:
        nm, (_, disp) = next(iter(grade_subj.items()))
        g_str, g_wk = f'{nm} {disp}', '비교 데이터 부족'
    else:
        g_str = g_wk = '데이터 부족'

    mock_subj = {}
    mk = _sf(current.get('mock_kor_percentile'))
    mm = _sf(current.get('mock_math_percentile'))
    me = _sf(current.get('mock_eng_grade'))
    if mk is not None:
        g = _pct_to_grade9(mk)
        mock_subj['국어'] = (mk, f'{g}등급 (상위 약 {100 - int(mk)}%)')
    if mm is not None:
        g = _pct_to_grade9(mm)
        mock_subj['수학'] = (mm, f'{g}등급 (상위 약 {100 - int(mm)}%)')
    if me is not None:
        mock_subj['영어'] = ((10 - me) / 9 * 100, f'{int(me)}등급 (상위 약 {round((me - 1) / 8 * 100)}%)')
    if len(mock_subj) >= 2:
        m_ranked = sorted(mock_subj.items(), key=lambda x: x[1][0], reverse=True)
        m_str = f'{m_ranked[0][0]} {m_ranked[0][1][1]}'
        m_wk  = f'{m_ranked[-1][0]} {m_ranked[-1][1][1]}'
    elif len(mock_subj) == 1:
        nm, (_, disp) = next(iter(mock_subj.items()))
        m_str, m_wk = f'{nm} {disp}', '비교 데이터 부족'
    else:
        m_str = m_wk = '데이터 부족'

    # ── 유사 졸업생 등록 패턴 ──────────────────────────────────────────
    pass_types: dict = {}
    total_pass = 0
    if not top_cases.empty and 'student_id' in top_cases.columns:
        ids = {str(s).replace('.0','').strip() for s in top_cases['student_id']}
        for df, is_jungsi in [(susi_df, False), (jungsi_df, True)]:
            if df is None or df.empty: continue
            id_col = find_id_col(df)
            if not id_col: continue
            matched = df[df[id_col].astype(str).str.replace('.0','',regex=False).str.strip().isin(ids)]
            for _, r in matched.iterrows():
                res = str(r.get('final_result','')).strip()
                if '합' not in res or '불합' in res: continue
                total_pass += 1
                if is_jungsi:
                    t = '정시'
                else:
                    adm = str(r.get('admission_name',''))
                    t = ('교과형' if '교과' in adm else '종합형' if '종합' in adm else '논술형' if '논술' in adm else '수시 기타')
                pass_types[t] = pass_types.get(t, 0) + 1

    # ── 추세 해석 ──────────────────────────────────────────────────────
    grade_trend = current.get('grade_trend', '판단불가')
    mock_trend  = current.get('mock_trend',  '판단불가')
    trend_map = {'상승': '상승 추세', '하락': '하락 추세', '유지': '안정 유지'}
    grade_label = trend_map.get(grade_trend, '판단불가')
    mock_label  = trend_map.get(mock_trend,  '판단불가')
    grade_comment = {'상승': '3학년 성적이 쌓일수록 교과/종합형 경쟁력 향상 기대',
                     '하락': '현재 성적 기준 보수적 접근 필요, 인접 구간 우선 검토',
                     '유지': '현재 수준 기준 그대로 전략 수립 가능'}.get(grade_trend, '데이터 부족으로 판단 어려움')
    mock_comment  = {'상승': '정시 가능성이 시간이 갈수록 높아질 수 있음',
                     '하락': '정시 전략 수립 시 최근 점수 기준으로 보수적 판단 필요',
                     '유지': '현재 모의 수준 기준으로 정시 가능성 판단 가능'}.get(mock_trend, '데이터 부족으로 판단 어려움')

    return {
        'grade_structure': {'type': bal_type, 'message': bal_msg},
        'subject_strength': {'grade_strong': g_str, 'grade_weak': g_wk,
                             'mock_strong': m_str, 'mock_weak': m_wk},
        'pass_pattern': {'total': total_pass, 'by_type': pass_types},
        'trend': {'grade_trend': grade_trend, 'grade_label': grade_label, 'grade_comment': grade_comment,
                  'mock_trend': mock_trend,  'mock_label': mock_label,  'mock_comment': mock_comment},
    }


def render_counseling_summary(
    current: dict,
    top_cases: pd.DataFrame,
    susi_df: pd.DataFrame,
    jungsi_df: pd.DataFrame,
):
    """상담 포인트 4가지: 성적 구조 / 과목 강약 / 졸업생 등록 패턴 / 추세 해석"""

    def _sf(v):
        try:
            if v is None or pd.isna(v):
                return None
            return float(v)
        except Exception:
            return None

    # ── 카드 1: 성적 구조 (내신 vs 모의) ─────────────────────
    all_pos  = _sf(current.get("all_pos"))   # 0-1
    mock_ks  = _sf(current.get("mock_ks_percentile"))   # 0-100

    if all_pos is not None and mock_ks is not None:
        grade_score = round(all_pos * 100, 1)
        diff = grade_score - mock_ks
        if diff > 15:
            bal_msg  = f"내신 강세 — 내신 위치 상위 약 {100 - grade_score:.0f}% / 모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%)<br>→ 수시 중심 전략이 유리할 수 있습니다."
            bal_color, bal_bg = "#1D4ED8", "#EFF6FF"
        elif diff < -15:
            bal_msg  = f"모의 강세 — 모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%) / 내신 위치 상위 약 {100 - grade_score:.0f}%<br>→ 정시 가능성도 함께 검토할 만합니다."
            bal_color, bal_bg = "#7C3AED", "#F5F3FF"
        else:
            bal_msg  = f"내신·모의 균형 — 내신 위치 상위 약 {100 - grade_score:.0f}% / 모의 국수 백분위 {mock_ks:.0f} (상위 약 {100 - mock_ks:.0f}%)<br>→ 수시·정시 병행 전략 검토 가능합니다."
            bal_color, bal_bg = "#059669", "#F0FDF4"
    else:
        bal_msg  = "성적 구조 비교를 위한 데이터가 부족합니다."
        bal_color, bal_bg = "#6B7280", "#F9FAFB"

    # ── 카드 2: 과목 강약 ──────────────────────────────────────
    # 내신 기준: 제일 좋은 과목 1개, 제일 낮은 과목 1개 (겹침 없음)
    _grade_key_map = {
        "kor_pos": "kor_grade", "math_pos": "math_grade", "eng_pos": "eng_grade",
        "soc_pos": "soc_grade", "sci_pos": "sci_grade",
    }
    grade_subj = {}  # label → (sort_key=top_pct, display_text)
    for pos_key, label in [("kor_pos","국어"),("math_pos","수학"),("eng_pos","영어"),
                           ("soc_pos","사회"),("sci_pos","과학")]:
        v = _sf(current.get(pos_key))
        if v is not None:
            top_pct = round((1 - v) * 100)
            g_val = _sf(current.get(_grade_key_map.get(pos_key, "")))
            if g_val is not None:
                g_str = f"{g_val:.1f}".rstrip("0").rstrip(".")
                disp = f"{g_str}등급 (상위 약 {top_pct}%)"
            else:
                disp = f"(상위 약 {top_pct}%)"
            grade_subj[label] = (top_pct, disp)

    if len(grade_subj) >= 2:
        g_ranked = sorted(grade_subj.items(), key=lambda x: x[1][0])
        g_str_txt = f"<b>{g_ranked[0][0]}</b> {g_ranked[0][1][1]}"
        g_wk_txt  = f"<b>{g_ranked[-1][0]}</b> {g_ranked[-1][1][1]}"
    elif len(grade_subj) == 1:
        nm, (_, disp) = next(iter(grade_subj.items()))
        g_str_txt = f"<b>{nm}</b> {disp}"
        g_wk_txt  = "비교 데이터 부족"
    else:
        g_str_txt = g_wk_txt = "데이터 부족"

    # 모의 기준: 제일 좋은 과목 1개, 제일 낮은 과목 1개 (겹침 없음)
    # 국어/수학 백분위 → 9등급 근사값으로 통일 표시
    mock_subj = {}  # label → (sort_key=높을수록좋음, display_text)
    mk = _sf(current.get("mock_kor_percentile"))
    mm = _sf(current.get("mock_math_percentile"))
    me = _sf(current.get("mock_eng_grade"))
    if mk is not None:
        g = _pct_to_grade9(mk)
        mock_subj["국어"] = (mk, f"{g}등급 (상위 약 {100 - int(mk)}%)")
    if mm is not None:
        g = _pct_to_grade9(mm)
        mock_subj["수학"] = (mm, f"{g}등급 (상위 약 {100 - int(mm)}%)")
    if me is not None:
        mock_subj["영어"] = ((10 - me) / 9 * 100, f"{int(me)}등급 (상위 약 {round((me - 1) / 8 * 100)}%)")

    if len(mock_subj) >= 2:
        m_ranked = sorted(mock_subj.items(), key=lambda x: x[1][0], reverse=True)
        m_str_txt = f"<b>{m_ranked[0][0]}</b> {m_ranked[0][1][1]}"
        m_wk_txt  = f"<b>{m_ranked[-1][0]}</b> {m_ranked[-1][1][1]}"
    elif len(mock_subj) == 1:
        nm, (_, disp) = next(iter(mock_subj.items()))
        m_str_txt = f"<b>{nm}</b> {disp}"
        m_wk_txt  = "비교 데이터 부족"
    else:
        m_str_txt = m_wk_txt = "데이터 부족"

    # ── 카드 3: 유사 졸업생 합격 패턴 ────────────────────────
    pass_types: dict = {}
    total_pass = 0

    if not top_cases.empty and "student_id" in top_cases.columns:
        ids = {str(s).replace(".0","").strip() for s in top_cases["student_id"]}

        for df, is_jungsi in [(susi_df, False), (jungsi_df, True)]:
            if df is None or df.empty:
                continue
            id_col = find_id_col(df)
            if not id_col:
                continue
            matched = df[df[id_col].astype(str).str.replace(".0","",regex=False).str.strip().isin(ids)]
            for _, r in matched.iterrows():
                result = str(r.get("final_result","")).strip()
                if "합" not in result or "불합" in result:
                    continue
                total_pass += 1
                if is_jungsi:
                    t = "정시"
                else:
                    adm = str(r.get("admission_name",""))
                    t = ("교과형" if "교과" in adm else
                         "종합형" if "종합" in adm else
                         "논술형" if "논술" in adm else "수시 기타")
                pass_types[t] = pass_types.get(t, 0) + 1

    if pass_types:
        sorted_pass = sorted(pass_types.items(), key=lambda x: x[1], reverse=True)
        pass_detail = " / ".join([f"<b>{t}</b> {n}건" for t, n in sorted_pass])
        reg_msg = f"유사 졸업생 합격 {total_pass}건 확인<br>{pass_detail}"
    else:
        reg_msg = "유사 졸업생 합격 결과 데이터가 없습니다."

    # ── 카드 4: 추세 해석 ──────────────────────────────────────
    grade_trend = current.get("grade_trend", "판단불가")
    mock_trend  = current.get("mock_trend",  "판단불가")

    trend_lines = []
    trend_map = {
        "상승": ("📈", "상승 추세"),
        "하락": ("📉", "하락 추세"),
        "유지": ("➡️", "안정 유지"),
    }
    grade_icon, grade_label = trend_map.get(grade_trend, ("❓", "판단불가"))
    mock_icon,  mock_label  = trend_map.get(mock_trend,  ("❓", "판단불가"))

    grade_comment = {
        "상승": "3학년 성적이 쌓일수록 교과/종합형 경쟁력 향상 기대",
        "하락": "현재 성적 기준 보수적 접근 필요, 인접 구간 우선 검토",
        "유지": "현재 수준 기준 그대로 전략 수립 가능",
    }.get(grade_trend, "데이터 부족으로 판단 어려움")

    mock_comment = {
        "상승": "정시 가능성이 시간이 갈수록 높아질 수 있음",
        "하락": "정시 전략 수립 시 최근 점수 기준으로 보수적 판단 필요",
        "유지": "현재 모의 수준 기준으로 정시 가능성 판단 가능",
    }.get(mock_trend, "데이터 부족으로 판단 어려움")

    has_up   = "상승" in (grade_trend, mock_trend)
    has_down = "하락" in (grade_trend, mock_trend)
    tr_border = "#22c55e" if has_up and not has_down else ("#ef4444" if has_down else "#94a3b8")
    tr_bg     = "#f0fdf4" if has_up and not has_down else ("#fef2f2" if has_down else "#f8fafc")
    tr_color  = "#16a34a" if has_up and not has_down else ("#dc2626" if has_down else "#64748b")

    # ── 렌더링 ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
<div style='border:1.5px solid {bal_color}55;border-radius:12px;padding:14px 16px;
            background:{bal_bg};margin-bottom:12px;height:130px;box-sizing:border-box;overflow:hidden;'>
  <div style='font-weight:700;color:{bal_color};margin-bottom:7px;font-size:0.93rem;'>📊 성적 구조</div>
  <div style='font-size:0.87rem;color:#1e293b;line-height:1.8;'>{bal_msg}</div>
</div>""", unsafe_allow_html=True)

        st.markdown(f"""
<div style='border:1.5px solid #d9770688;border-radius:12px;padding:14px 16px;
            background:#fffbeb;margin-bottom:12px;min-height:110px;'>
  <div style='font-weight:700;color:#b45309;margin-bottom:7px;font-size:0.93rem;'>👥 유사 졸업생 등록 패턴</div>
  <div style='font-size:0.87rem;color:#1e293b;line-height:1.8;'>{reg_msg}</div>
</div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
<div style='border:1.5px solid #8b5cf688;border-radius:12px;padding:14px 16px;
            background:#f5f3ff;margin-bottom:12px;height:130px;box-sizing:border-box;'>
  <div style='font-weight:700;color:#7c3aed;margin-bottom:8px;font-size:0.93rem;'>📚 과목 강약</div>
  <div style='display:flex;gap:12px;'>
    <div style='flex:1;border-right:1px solid #e9d5ff;padding-right:12px;'>
      <div style='font-size:0.78rem;color:#7c3aed;font-weight:600;margin-bottom:4px;'>내신 위치</div>
      <div style='font-size:0.84rem;color:#1e293b;line-height:1.8;'>
        <span style='color:#059669;font-weight:600;'>강점</span> {g_str_txt}<br>
        <span style='color:#dc2626;font-weight:600;'>주의</span> {g_wk_txt}
      </div>
    </div>
    <div style='flex:1;'>
      <div style='font-size:0.78rem;color:#7c3aed;font-weight:600;margin-bottom:4px;'>모의 성적</div>
      <div style='font-size:0.84rem;color:#1e293b;line-height:1.8;'>
        <span style='color:#059669;font-weight:600;'>강점</span> {m_str_txt}<br>
        <span style='color:#dc2626;font-weight:600;'>주의</span> {m_wk_txt}
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown(f"""
<div style='border:1.5px solid {tr_border}88;border-radius:12px;padding:14px 16px;
            background:{tr_bg};margin-bottom:12px;min-height:110px;'>
  <div style='font-weight:700;color:{tr_color};margin-bottom:7px;font-size:0.93rem;'>📈 추세 해석</div>
  <div style='font-size:0.87rem;color:#1e293b;line-height:1.8;'>
    {grade_icon} 내신 {grade_label} — {grade_comment}<br>
    {mock_icon} 모의 {mock_label} — {mock_comment}
  </div>
</div>""", unsafe_allow_html=True)


def prepare_sim_tab_cases(sim_df: pd.DataFrame, susi_df: pd.DataFrame, jungsi_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """내신/모의 유사도 DataFrame에서 탭용 top-N 사례를 준비 (susi/jungsi 요약 포함)."""
    if not isinstance(sim_df, pd.DataFrame) or sim_df.empty:
        return pd.DataFrame()
    top = get_top_similar_cases(sim_df, n=n)
    if top.empty:
        return top
    if "student_id" in top.columns:
        top = top.copy()
        top["student_id"] = top["student_id"].apply(clean_display_id)
        top["susi_summary"] = top["student_id"].apply(lambda x: susi_summary(x, susi_df))
        top["jungsi_summary"] = top["student_id"].apply(lambda x: jungsi_summary(x, jungsi_df))
    return top


grade_options = get_grade_basis_options(current_student_data)
mock_options = get_mock_basis_options(current_student_data)

student_title = get_student_title(current_student_data)
st.title(student_title)

basic_info = current_student_data.get("basic_info", {})
st.caption(
    f"학번: {safe_str(basic_info.get('student_id', '-'))} | "
    f"이름: {safe_str(basic_info.get('name', '-'))} | "
    f"계열: {safe_str(basic_info.get('track', '-'))}"
)

section_header("🧭 분석 기준 선택")
basis_col1, basis_col2 = st.columns(2)
with basis_col1:
    selected_grade_basis = st.selectbox("내신 분석 기준", grade_options, key="selected_grade_basis")
with basis_col2:
    selected_mock_basis = st.selectbox("모의고사 분석 기준", mock_options, key="selected_mock_basis")

if st.button("분석 실행", type="primary"):
    current = build_current_student_features(
        current_student_data,
        grade_basis=selected_grade_basis,
        mock_basis=selected_mock_basis,
    )

    graduates = build_graduate_features(graduate_db)

    grade_sim = calculate_grade_similarity(current, graduates)
    mock_sim = calculate_mock_similarity(current, graduates)
    total_sim = calculate_total_similarity(grade_sim, mock_sim)
    top_cases = get_top_similar_cases(total_sim, n=10)

    susi_df = graduate_db.get("susi", pd.DataFrame())
    jungsi_df = graduate_db.get("jungsi", pd.DataFrame())

    if not top_cases.empty and "student_id" in top_cases.columns:
        top_cases["student_id"] = top_cases["student_id"].apply(clean_display_id)
        top_cases["susi_summary"] = top_cases["student_id"].apply(lambda x: susi_summary(x, susi_df))
        top_cases["jungsi_summary"] = top_cases["student_id"].apply(lambda x: jungsi_summary(x, jungsi_df))

    fit_result = build_fit_summary(current, top_cases, susi_df, jungsi_df)

    strength = build_strength_summary(current, fit_result)
    weakness = build_weakness_summary(current, fit_result)
    strategy = build_strategy_summary(
        top_cases.to_dict(orient="records") if not top_cases.empty else [],
        fit_result
    )
    disclaimer_lines = get_report_disclaimer_lines()

    # 유사 사례: 성적 컬럼 + 유사 이유 병합 (내신/모의 분리)
    # PDF 유사 이유 항목 제한: 내신순=교내위치 2개, 모의순=국수 백분위 2개
    _GRADE_PDF_KEYS = {"all_pos", "ksy_pos"}
    _MOCK_PDF_KEYS  = {"mock_math_percentile", "mock_kor_percentile"}

    def _build_report_cases(sim_df: pd.DataFrame, sim_col: str) -> list:
        """sim_df(grade_sim 또는 mock_sim)에서 PDF용 사례 리스트 생성."""
        if sim_df.empty:
            return []
        from modules.similarity_engine import get_top_similar_cases as _gtsc
        rc = _gtsc(sim_df, n=8).copy()
        if "student_id" not in rc.columns:
            return []
        rc["student_id"] = rc["student_id"].astype(str).str.replace(".0","",regex=False).str.strip()
        rc["susi_summary"]   = rc["student_id"].apply(lambda x: susi_summary(x, susi_df))
        rc["jungsi_summary"] = rc["student_id"].apply(lambda x: jungsi_summary(x, jungsi_df))
        rc["case_code"] = [f"사례 {chr(65+i)}" for i in range(len(rc))]
        if not graduates.empty and "student_id" in graduates.columns:
            gf = graduates.copy()
            gf["student_id"] = gf["student_id"].astype(str).str.replace(".0","",regex=False).str.strip()
            score_cols = [c for c in ["all_grade", "ksy_grade", "mock_ks_percentile"] if c in gf.columns]
            if score_cols:
                rc = rc.merge(gf[["student_id"] + score_cols], on="student_id", how="left")
        keep = [c for c in ["case_code", "all_grade", "ksy_grade", "mock_ks_percentile",
                             "susi_summary", "jungsi_summary",
                             "grade_detail", "mock_detail"] if c in rc.columns]
        cases = rc[keep].to_dict(orient="records")
        # PDF 이유 키 필터: 내신순=교내위치, 모의순=국수 백분위만
        _allowed = _GRADE_PDF_KEYS if sim_col == "grade_similarity" else _MOCK_PDF_KEYS
        for idx, (_, row) in enumerate(rc.iterrows()):
            if idx < len(cases):
                all_reasons = build_similarity_reason_lines(row, max_lines=10)
                # 키 필터: "라벨: 현재 X / 사례 Y" 에서 원본 키 매칭
                filtered = []
                for item in _get_detail_items(row):
                    if item.get("항목") in _allowed:
                        key  = item["항목"]
                        cur  = item.get("현재값")
                        grad = item.get("졸업생값")
                        filtered.append(
                            f"{to_display_label(key)}: 현재 {_fmt_reason_val_safe(key, cur)} / 사례 {_fmt_reason_val_safe(key, grad)}"
                        )
                cases[idx]["similarity_reason"] = "  /  ".join(filtered) if filtered else (
                    "  /  ".join(all_reasons[:2])
                )
        return cases

    def _get_detail_items(row) -> list:
        """row에서 grade_detail + mock_detail 병합."""
        def _safe_list(v):
            return v if isinstance(v, list) else []
        return _safe_list(row.get("grade_detail")) + _safe_list(row.get("mock_detail"))

    def _fmt_reason_val_safe(key: str, v) -> str:
        """PDF 이유 값 포맷 (간략)."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        try:
            v_f = float(v)
            if key in ("all_pos", "ksy_pos", "kor_pos", "math_pos", "eng_pos",
                       "soc_pos", "sci_pos", "mock_ks_pos (교내위치)"):
                # pos는 정규화된 0~100 값 → "상위 약 X%" 로 표시
                top = round(100 - v_f)
                return f"상위 약 {top}%"
            if key in ("mock_kor_percentile", "mock_math_percentile",
                       "mock_soc_percentile", "mock_sci_percentile"):
                top = round(100 - v_f)
                return f"{int(round(v_f))} (상위 약 {top}%)"
        except Exception:
            pass
        return str(v)

    report_cases       = _build_report_cases(total_sim,  "total_similarity")
    grade_report_cases = _build_report_cases(grade_sim,  "grade_similarity")
    mock_report_cases  = _build_report_cases(mock_sim,   "mock_similarity")

    # 합격 사례: 유사 사례에 표시된 학생 합집합 기준 (내신 상위 8 + 모의 상위 8)
    _grade_top_ids = (
        set(grade_sim.head(8)["student_id"].astype(str)
            .str.replace(".0", "", regex=False).str.strip().tolist())
        if not grade_sim.empty and "student_id" in grade_sim.columns else set()
    )
    _mock_top_ids = (
        set(mock_sim.head(8)["student_id"].astype(str)
            .str.replace(".0", "", regex=False).str.strip().tolist())
        if not mock_sim.empty and "student_id" in mock_sim.columns else set()
    )
    _sim_union_ids = _grade_top_ids | _mock_top_ids
    if not total_sim.empty and "student_id" in total_sim.columns and _sim_union_ids:
        _ts_copy = total_sim.copy()
        _ts_copy["_sid_tmp"] = _ts_copy["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
        _union_sim_df = _ts_copy[_ts_copy["_sid_tmp"].isin(_sim_union_ids)].drop(columns=["_sid_tmp"])
        top_cases_for_passing = get_top_similar_cases(_union_sim_df, n=len(_sim_union_ids))
    else:
        top_cases_for_passing = top_cases

    # 합격 사례에도 성적 컬럼 병합
    passing_data   = build_passing_analysis(top_cases_for_passing, susi_df, jungsi_df, current_features=current, graduates_df=graduates)
    passing_susi   = passing_data["susi"].to_dict("records")   if not passing_data["susi"].empty   else []
    passing_jungsi = passing_data["jungsi"].to_dict("records") if not passing_data["jungsi"].empty else []
    if (passing_susi or passing_jungsi) and not graduates.empty and "student_id" in graduates.columns:
        gf2 = graduates.copy()
        gf2["학번"] = gf2["student_id"].astype(str).str.replace(".0","",regex=False).str.strip()
        grade_cols = [c for c in ["all_grade", "ksy_grade", "mock_ks_percentile"] if c in gf2.columns]
        if grade_cols:
            gf2_slim = gf2[["학번"] + grade_cols].drop_duplicates("학번")
            if passing_susi:
                ps_df = pd.DataFrame(passing_susi)
                if "학번" in ps_df.columns:
                    ps_df["학번"] = ps_df["학번"].astype(str).str.replace(".0","",regex=False).str.strip()
                    ps_df = ps_df.merge(gf2_slim, on="학번", how="left")
                    passing_susi = ps_df.to_dict("records")
            if passing_jungsi:
                pj_df = pd.DataFrame(passing_jungsi)
                if "학번" in pj_df.columns:
                    pj_df["학번"] = pj_df["학번"].astype(str).str.replace(".0","",regex=False).str.strip()
                    pj_df = pj_df.merge(gf2_slim, on="학번", how="left")
                    passing_jungsi = pj_df.to_dict("records")

    counseling_data = build_counseling_data(current, top_cases, susi_df, jungsi_df)

    # pinned_entries 없는 기본 컨텍스트를 저장 → 다운로드 시 최신값으로 재생성
    _ctx_base = dict(
        student=current,
        similar_cases=report_cases,
        grade_similar_cases=grade_report_cases,
        mock_similar_cases=mock_report_cases,
        fit_result=fit_result,
        strength=strength,
        weakness=weakness,
        strategy=strategy,
        disclaimer_lines=disclaimer_lines,
        passing_susi=passing_susi,
        passing_jungsi=passing_jungsi,
        counseling_data=counseling_data,
    )
    st.session_state["report_context_base"] = _ctx_base
    st.session_state["_last_pdf_pinned_count"] = -1  # 새 학생 분석 시 PDF 강제 재생성

    context = build_report_context(
        **_ctx_base,
        pinned_entries=st.session_state.get("report_pinned_entries", []),
    )

    html = render_report_html(context)
    pdf_path = export_pdf(context)

    st.session_state["current_features"] = current
    st.session_state["graduate_features"] = graduates  # 유사 사례 표에서 실제 성적 표시용
    st.session_state["analysis_result"] = {
        "grade_sim": grade_sim,
        "mock_sim": mock_sim,
        "total_sim": total_sim,
        "top_cases": top_cases,
        "fit_result": fit_result,
        "strength": strength,
        "weakness": weakness,
        "strategy": strategy,
    }
    st.session_state["report_html"] = html
    st.session_state["report_pdf_path"] = pdf_path
    st.session_state["teacher_review"] = {
        "current": current,
        "graduates": graduates.head(20) if isinstance(graduates, pd.DataFrame) else pd.DataFrame(),
        "grade_sim": grade_sim.head(20) if isinstance(grade_sim, pd.DataFrame) else pd.DataFrame(),
        "mock_sim": mock_sim.head(20) if isinstance(mock_sim, pd.DataFrame) else pd.DataFrame(),
        "total_sim": total_sim.head(20) if isinstance(total_sim, pd.DataFrame) else pd.DataFrame(),
        "case_identity": get_case_identity_map(top_cases, graduate_db),
    }

    st.success("분석이 완료되었습니다.")

result = st.session_state.get("analysis_result")

if result:
    current = st.session_state.get("current_features", {})

    section_header("📌 현재 학생 요약")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        info_card("전교과 (등급)", _small_rank(_fmt_grade_with_pos(current.get("all_grade"), current.get("all_pos"))), safe_str(current.get("grade_basis_detail")))
    with c2:
        info_card("국수영 (등급)", _small_rank(_fmt_grade_with_pos(current.get("ksy_grade"), current.get("ksy_pos"))), f"사용된 내신 기록 수: {safe_str(current.get('grade_record_count_used'))}건")
    with c3:
        # 값: 원점수 (등수/총원) 형식
        _c3_s = current.get("mock_ks_score")
        _c3_r = current.get("mock_ks_rank")
        _c3_t = current.get("mock_total_students")
        if _c3_s is not None and not (isinstance(_c3_s, float) and pd.isna(_c3_s)):
            _c3_v = f"{int(round(float(_c3_s)))}점"
            if _c3_r is not None and not (isinstance(_c3_r, float) and pd.isna(_c3_r)):
                _rr = str(int(round(float(_c3_r))))
                if _c3_t is not None and not (isinstance(_c3_t, float) and pd.isna(_c3_t)):
                    _rr += f"/{int(round(float(_c3_t)))}"
                _c3_v += f" ({_rr})"
        else:
            _c3_v = "-"
        info_card(
            "모의 국수영 원점수(등수)",
            _c3_v,
            safe_str(current.get("mock_basis_detail")),
        )
    with c4:
        # 값: 백분위 (상위 X%) 형식 — (상위 X%) 부분 작은 회색 HTML
        _c4_p = current.get("mock_ks_percentile")
        if _c4_p is not None and not (isinstance(_c4_p, float) and pd.isna(_c4_p)):
            _pct4 = int(round(float(_c4_p)))
            _top4 = 100 - _pct4
            _c4_v = (f"<span style='font-size:34px;font-weight:800;color:#101828;'>{_pct4}</span>"
                     f" <span style='font-size:16px;font-weight:500;color:#94a3b8;'>(상위 약 {_top4}%)</span>")
        else:
            _c4_v = "-"
        info_card(
            "국수 백분위",
            _c4_v,
            f"사용된 모의 기록 수: {safe_str(current.get('mock_record_count_used'))}건",
        )

    section_header("🧾 분석 근거")
    reason_lines = [
        current.get("grade_basis_detail", "내신 기준 설명이 없습니다."),
        current.get("mock_basis_detail", "모의 기준 설명이 없습니다."),
        f"내신 추세는 '{safe_str(current.get('grade_trend'))}', 모의 추세는 '{safe_str(current.get('mock_trend'))}'로 반영했습니다.",
        f"선택된 내신 기록 수는 {safe_str(current.get('grade_record_count_used'))}건, 모의 기록 수는 {safe_str(current.get('mock_record_count_used'))}건입니다.",
    ]
    colored_reason_box("현재 분석에 사용된 기준", reason_lines)

    debug_lines = [
        f"현재 학생 내신 상대위치: 전교과 {_fmt_pos(current.get('all_pos'))}, 국수영 {_fmt_pos(current.get('ksy_pos'))}, 국어 {_fmt_pos(current.get('kor_pos'))}, 수학 {_fmt_pos(current.get('math_pos'))}",
        f"현재 학생 내신 등급: 전교과 {_fmt_grade_with_pos(current.get('all_grade'), current.get('all_pos'))}, 국수영 {_fmt_grade_with_pos(current.get('ksy_grade'), current.get('ksy_pos'))}, 국어 {_fmt_grade_with_pos(current.get('kor_grade'), current.get('kor_pos'))}, 수학 {_fmt_grade_with_pos(current.get('math_grade'), current.get('math_pos'))}, 영어 {_fmt_grade_with_pos(current.get('eng_grade'), current.get('eng_pos'))}",
        f"현재 학생 모의값: 국어 {_fmt_percentile(current.get('mock_kor_percentile'))}, 수학 {_fmt_percentile(current.get('mock_math_percentile'))}, 영어 {_fmt_mock_grade(current.get('mock_eng_grade'))}, 사회/탐구 {_fmt_mock_grade(current.get('mock_soc_grade'))}, 과학/탐구 {_fmt_mock_grade(current.get('mock_sci_grade'))}, 국수탐 {'백분위합 ' + str(int(round(float(current.get('mock_ks_percentile'))))) if current.get('mock_ks_percentile') is not None and not pd.isna(current.get('mock_ks_percentile')) and float(current.get('mock_ks_percentile')) > 100 else _fmt_percentile(current.get('mock_ks_percentile'))}",
    ]
    colored_reason_box(
        "유사도 계산에 실제 사용된 현재 학생 핵심값",
        debug_lines,
        bg="#fff7ed",
        border="#fdba74",
    )

    section_header("👥 유사 사례 / 합격 사례 분석")
    top_cases_result = result.get("top_cases", pd.DataFrame())
    susi_df_cur = graduate_db.get("susi", pd.DataFrame())
    jungsi_df_cur = graduate_db.get("jungsi", pd.DataFrame())

    main_tab1, main_tab2 = st.tabs(["유사 사례", "합격 사례 분석"])

    with main_tab1:
        _case_adm_detail = st.toggle("📋 전형방법·최저학력기준 보기", value=False, key="case_adm_detail")
        sim_sub1, sim_sub2 = st.tabs(["내신 유사도 순", "모의 유사도 순"])

        # 내신/모의 탭용 top cases 준비
        grade_sim_top = prepare_sim_tab_cases(
            result.get("grade_sim", pd.DataFrame()), susi_df_cur, jungsi_df_cur
        )
        mock_sim_top = prepare_sim_tab_cases(
            result.get("mock_sim", pd.DataFrame()), susi_df_cur, jungsi_df_cur
        )

        def _render_teacher_table(cases_df, sim_col_key):
            if not isinstance(cases_df, pd.DataFrame) or cases_df.empty:
                st.info("표시할 유사 사례가 없습니다.")
                return
            base_cols = [c for c in ["case_code", "student_id", "name", "track",
                                     sim_col_key, "susi_summary", "jungsi_summary"]
                         if c in cases_df.columns]
            display_df = cases_df[base_cols].copy()
            display_df["student_id"] = display_df["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()

            grad_features = st.session_state.get("graduate_features", pd.DataFrame())
            if not grad_features.empty and "student_id" in grad_features.columns:
                gf = grad_features.copy()
                gf["student_id"] = gf["student_id"].astype(str).str.strip()
                score_cols = [c for c in ["all_grade", "ksy_grade", "kor_grade", "math_grade",
                                          "eng_grade", "mock_kor_percentile", "mock_math_percentile",
                                          "mock_eng_grade", "mock_ks_percentile"]
                              if c in gf.columns]
                if score_cols:
                    display_df = display_df.merge(gf[["student_id"] + score_cols], on="student_id", how="left")

            _raw_g = graduate_db.get("grade", pd.DataFrame()) if isinstance(graduate_db, dict) else pd.DataFrame()
            if isinstance(_raw_g, pd.DataFrame) and not _raw_g.empty \
                    and "serial_no" in _raw_g.columns and "student_id" in _raw_g.columns:
                _sdf = _raw_g[["student_id", "serial_no"]].drop_duplicates("student_id").copy()
                _sdf["student_id"] = _sdf["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
                display_df = display_df.merge(_sdf, on="student_id", how="left")

            if "serial_no" in display_df.columns:
                cols = display_df.columns.tolist()
                cols.remove("serial_no")
                sid_idx = cols.index("student_id") if "student_id" in cols else 0
                cols.insert(sid_idx, "serial_no")
                display_df = display_df[cols]

            col_rename = {
                "serial_no": "일련번호", "case_code": "사례코드", "student_id": "학번",
                "name": "이름", "track": "계열",
                "grade_similarity": "내신 유사도", "mock_similarity": "모의 유사도",
                "all_grade": "전교과 등급", "ksy_grade": "국수영 등급",
                "kor_grade": "국어 등급", "math_grade": "수학 등급", "eng_grade": "영어 등급",
                "mock_kor_percentile": "모의 국어 백분위", "mock_math_percentile": "모의 수학 백분위",
                "mock_eng_grade": "모의 영어 등급", "mock_ks_percentile": "모의 국수 종합지표",
                "susi_summary": "수시 결과 요약", "jungsi_summary": "정시 결과 요약",
            }
            display_df = display_df.rename(columns={k: v for k, v in col_rename.items() if k in display_df.columns})
            if "학번" in display_df.columns:
                display_df["학번"] = display_df["학번"].apply(clean_display_id)
            if not st.session_state.get("_analysis_show_full", False):
                if "학번" in display_df.columns:
                    display_df["학번"] = display_df["학번"].apply(_mask_id)
                if "이름" in display_df.columns:
                    display_df["이름"] = display_df["이름"].apply(_mask_name)
            styled_dataframe(display_df)

        with sim_sub1:
            render_case_cards(grade_sim_top, susi_df_cur, jungsi_df_cur,
                              sim_col="grade_similarity", show_adm_detail=_case_adm_detail)
            _grade_show_full = st.toggle("🔓 학번·이름 보기", value=False, key="analysis_show_full_grade")
            st.session_state["_analysis_show_full"] = _grade_show_full
            with st.expander("교사용 상세 보기"):
                _render_teacher_table(grade_sim_top, "grade_similarity")

        with sim_sub2:
            render_case_cards(mock_sim_top, susi_df_cur, jungsi_df_cur,
                              sim_col="mock_similarity", show_adm_detail=_case_adm_detail)
            _mock_show_full = st.toggle("🔓 학번·이름 보기", value=False, key="analysis_show_full_mock")
            st.session_state["_analysis_show_full"] = _mock_show_full
            with st.expander("교사용 상세 보기"):
                _render_teacher_table(mock_sim_top, "mock_similarity")

    with main_tab2:
        render_passing_tab(
            top_cases_result, susi_df_cur, jungsi_df_cur,
            current_features=current,
            graduates_df=st.session_state.get("graduate_features", pd.DataFrame()),
            all_sim_df=result.get("total_sim", pd.DataFrame()),
        )

    section_header("🎯 전형 적합도")
    fit_scores = result["fit_result"].get("scores", [])
    fit_df = pd.DataFrame(fit_scores)

    if not fit_df.empty:
        # 점수 내림차순 정렬
        fit_scores_sorted = sorted(fit_scores, key=lambda x: float(x.get("score", 0) or 0), reverse=True)
        top3 = fit_scores_sorted[:3]

        view = pd.DataFrame(fit_scores_sorted).rename(columns={
            "name": "전형 유형", "score": "적합도 점수",
            "reason": "계산 근거", "comment": "설명",
        })

        RANK_STYLES = [
            ("1위", "#f59e0b", "#fffbeb"),   # 금
            ("2위", "#94a3b8", "#f8fafc"),   # 은
            ("3위", "#cd7c4a", "#fdf6ee"),   # 동
        ]
        fc1, fc2, fc3 = st.columns(3)

        for idx, (item, col) in enumerate(zip(top3, [fc1, fc2, fc3])):
            rank_label, badge_color, card_bg = RANK_STYLES[idx]
            with col:
                st.markdown(
                    f"<div style='margin-bottom:4px;'>"
                    f"<span style='background:{badge_color};color:white;border-radius:5px;"
                    f"padding:2px 9px;font-size:12px;font-weight:800;'>{rank_label}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                note = safe_str(item.get("comment", item.get("reason", "")))
                info_card(
                    safe_str(item.get("name", "-")),
                    format_value(item.get("score", "-")),
                    note,
                )

        fit_evidence = build_fit_evidence_lines(
            current,
            fit_scores,
            result.get("top_cases", pd.DataFrame())
        )
        colored_reason_box(
            "전형 적합도 판단 근거",
            fit_evidence,
            bg="#ecfdf3",
            border="#abefc6",
        )

        with st.expander("전형 적합도 표 보기"):
            styled_dataframe(view)

        _fit_show_full = st.toggle("🔓 학번·이름 보기", value=False, key="fit_show_full")
        st.session_state["_fit_show_full"] = _fit_show_full
        with st.expander("전형 유형별 실제 사례 보기"):
            render_fit_case_details(top_cases_result, susi_df_cur, jungsi_df_cur)
    else:
        st.info("전형 적합도 결과가 없습니다.")

    section_header("💬 상담 포인트")
    render_counseling_summary(current, top_cases_result, susi_df_cur, jungsi_df_cur)

    with st.expander("교사용 내부 검토 화면"):
        tr = st.session_state.get("teacher_review", {})

        _col_kr = {
            "serial_no": "일련번호", "student_id": "학번", "name": "이름", "track": "계열",
            "grade_similarity": "내신 유사도", "grade_confidence": "내신 근거 비중",
            "mock_similarity": "모의 유사도",  "mock_confidence": "모의 근거 비중",
            "total_similarity": "통합 유사도", "total_confidence": "통합 근거 비중",
        }

        # 일련번호 조회용: graduate_db["grade"]에서 직접 매핑 (Excel 업로드만 되면 항상 사용 가능)
        _serial_map = {}
        _raw_grade = graduate_db.get("grade", pd.DataFrame()) if isinstance(graduate_db, dict) else pd.DataFrame()
        if isinstance(_raw_grade, pd.DataFrame) and not _raw_grade.empty \
                and "serial_no" in _raw_grade.columns and "student_id" in _raw_grade.columns:
            for _, r in _raw_grade.drop_duplicates("student_id").iterrows():
                sid = str(r.get("student_id", "")).replace(".0", "").strip()
                _serial_map[sid] = r.get("serial_no", "")

        def _sim_table(df):
            if not isinstance(df, pd.DataFrame) or df.empty:
                return
            drop_cols = [c for c in ["grade_detail", "mock_detail"] if c in df.columns]
            tmp = df.drop(columns=drop_cols).copy()
            if "student_id" in tmp.columns:
                tmp["student_id"] = tmp["student_id"].apply(clean_display_id)
                if _serial_map:
                    tmp.insert(0, "serial_no",
                               tmp["student_id"].map(lambda x: _serial_map.get(str(x).strip(), "")))
            tmp = tmp.rename(columns={k: v for k, v in _col_kr.items() if k in tmp.columns})
            styled_dataframe(tmp)

        st.markdown("**내신 유사도 상위**")
        if isinstance(tr.get("grade_sim"), pd.DataFrame) and not tr["grade_sim"].empty:
            _sim_table(tr["grade_sim"])
        else:
            st.info("내신 유사도 데이터가 없습니다.")

        st.markdown("**모의 유사도 상위**")
        if isinstance(tr.get("mock_sim"), pd.DataFrame) and not tr["mock_sim"].empty:
            _sim_table(tr["mock_sim"])
        else:
            st.info("모의 유사도 데이터가 없습니다.")

        st.markdown("**통합 유사도 상위**")
        if isinstance(tr.get("total_sim"), pd.DataFrame) and not tr["total_sim"].empty:
            _sim_table(tr["total_sim"])
        else:
            st.info("통합 유사도 데이터가 없습니다.")

    # ── 대학/학과 역추적 헤더 + 마스킹 토글 ─────────────────────
    _hdr_col, _toggle_col = st.columns([5, 1])
    _hdr_col.markdown(
        "<h3 style='margin-bottom:0'>🏫 대학/학과 역추적</h3>",
        unsafe_allow_html=True,
    )
    with _toggle_col:
        _show_full = st.toggle("🔓 학번·이름 보기", value=False, key="tracker_show_full")

    def _mask_id(s: str) -> str:
        s = str(s).strip()
        if len(s) <= 2:
            return s
        return s[:-2] + "**"

    def _mask_name(s: str) -> str:
        s = str(s).strip()
        if len(s) <= 1:
            return s
        if len(s) == 2:
            return s[0] + "*"
        return s[0] + "*" + s[2:]

    def _classify_adm_type(name, group=""):
        """전형명/분류로 전형 유형 분류."""
        # admission_group(전형분류)이 명확한 유형값이면 직접 매핑
        g = str(group).strip()
        _g_map = {
            "교과": "교과형", "학생부교과": "교과형", "교과위주": "교과형",
            "종합": "종합형", "학생부종합": "종합형", "종합위주": "종합형",
            "논술": "논술형", "논술위주": "논술형",
            "실기": "실기형", "실기위주": "실기형", "예체능": "실기형",
        }
        if g in _g_map:
            return _g_map[g]
        # 전형명 + 전형분류 통합 키워드 매칭
        text = str(name) + " " + g
        if "논술" in text:
            return "논술형"
        if any(k in text for k in ["실기", "체육", "예체", "예능", "미술", "음악", "디자인"]):
            return "실기형"
        if any(k in text for k in ["종합", "서류", "활동우수", "인재전형", "학생부종합",
                                    "자기추천", "잠재력", "역량", "창의인재", "글로벌인재",
                                    "학업역량", "성장잠재력", "네오르네상스", "KU자기추천",
                                    "DKU자기추천", "SW특기자"]):
            return "종합형"
        if any(k in text for k in ["교과", "지역균형", "추천", "학업우수", "학교장",
                                    "지역인재", "고교추천", "일반고교과", "기회균등"]):
            return "교과형"
        return "기타"

    # 전체 DB(수시+정시) 합친 데이터에서 대학 목록 구축
    _all_records = pd.concat(
        [df for df in [graduate_db.get("susi", pd.DataFrame()), graduate_db.get("jungsi", pd.DataFrame())]
         if isinstance(df, pd.DataFrame) and not df.empty and "college" in df.columns],
        ignore_index=True,
    )

    college_query = st.text_input("대학명 검색 (일부만 입력해도 됩니다)", key="tracker_college_input")

    college_list = []
    department = ""
    admission_name = ""

    if college_query.strip() and not _all_records.empty:
        _col_matches = _all_records[
            _all_records["college"].astype(str).str.contains(college_query.strip(), na=False, regex=False)
        ]
        matching_colleges = sorted(_col_matches["college"].dropna().astype(str).unique().tolist())

        if not matching_colleges:
            st.warning("일치하는 대학이 없습니다.")
        elif len(matching_colleges) == 1:
            college_list = matching_colleges
            st.success(f"✅ {matching_colleges[0]}")
        else:
            college_list = st.multiselect(
                f"'{college_query}' 검색 결과 {len(matching_colleges)}개 — 선택하세요 (복수 선택 가능)",
                matching_colleges, default=[], key="tracker_college_sel",
            )

        if college_list:
            _filtered = _all_records[_all_records["college"].astype(str).isin(college_list)]
            dept_options = ["(전체)"] + sorted(_filtered["department"].dropna().astype(str).unique().tolist()) if "department" in _filtered.columns else ["(전체)"]
            adm_options  = ["(전체)"] + sorted(_filtered["admission_name"].dropna().astype(str).unique().tolist()) if "admission_name" in _filtered.columns else ["(전체)"]
            dd1, dd2 = st.columns(2)
            dept_opts_clean = [o for o in dept_options if o != "(전체)"]
            adm_opts_clean  = [o for o in adm_options  if o != "(전체)"]
            dept_sel = dd1.multiselect("모집단위 선택 (복수 가능)", dept_opts_clean, key="tracker_dept_sel")
            adm_sel  = dd2.multiselect("전형명 선택 (복수 가능)",   adm_opts_clean,  key="tracker_adm_sel")
            department     = dept_sel   # list; 비어있으면 전체
            admission_name = adm_sel    # list; 비어있으면 전체

    _btn_disabled = not bool(college_list)
    if st.button("역추적 검색", disabled=_btn_disabled):
        tracker = search_college_cases(
            graduate_db,
            college_list=college_list,
            department=department,
            admission_name=admission_name,
        )
        st.session_state["tracker_result"] = tracker

    tracker_result = st.session_state.get("tracker_result")
    if tracker_result:
        summary = tracker_result.get("summary", {})
        if isinstance(summary, dict) and summary:
            sm1, sm2, sm3 = st.columns(3)
            sm1.metric("지원자 수", summary.get("지원자 수", 0))
            sm2.metric("최종 합격자 수", summary.get("최종 합격자 수", 0))
            sm3.metric("등록자 수", summary.get("등록자 수", 0))

        cases_df = tracker_result.get("cases", pd.DataFrame())
        if isinstance(cases_df, pd.DataFrame) and not cases_df.empty:
            grad_features = st.session_state.get("graduate_features", pd.DataFrame())

            # ── 수능 성적: 모의고사 시트에서 grade_level=3, exam_month=11 (3학년 11월 = 수능) ──
            _mock_raw = graduate_db.get("mock", pd.DataFrame())
            _suneung_feat = pd.DataFrame()
            _suneung_avail: list[str] = []
            if (not _mock_raw.empty
                    and "grade_level" in _mock_raw.columns
                    and "exam_month" in _mock_raw.columns
                    and "student_id" in _mock_raw.columns):
                _su_rows = _mock_raw[
                    (_mock_raw["grade_level"] == "3") & (_mock_raw["exam_month"] == "11")
                ].copy()
                _su_num_src = [c for c in ["mock_kor_percentile", "mock_math_percentile",
                                           "mock_eng_grade", "mock_hanuksa_grade",
                                           "mock_soc_grade", "mock_sci_grade",
                                           "mock_soc_percentile", "mock_sci_percentile",
                                           "mock_ks_percentile"]
                               if c in _su_rows.columns]
                _su_str_src = [c for c in ["mock_tanku1_subject", "mock_tanku2_subject"]
                               if c in _su_rows.columns]
                if not _su_rows.empty and (_su_num_src or _su_str_src):
                    # 수치형: 평균 (수능은 1회이므로 사실상 그대로)
                    _parts = []
                    if _su_num_src:
                        _num_df = _su_rows[["student_id"] + _su_num_src].copy()
                        for _c in _su_num_src:
                            _num_df[_c] = pd.to_numeric(_num_df[_c], errors="coerce")
                        _parts.append(_num_df.groupby("student_id")[_su_num_src].mean())
                    # 문자형: 첫 번째 값 사용
                    if _su_str_src:
                        _str_df = _su_rows[["student_id"] + _su_str_src].copy()
                        _parts.append(_str_df.groupby("student_id")[_su_str_src].first())
                    _suneung_agg = pd.concat(_parts, axis=1).reset_index()
                    _all_su_src = _su_num_src + _su_str_src
                    _suneung_feat = _suneung_agg.rename(
                        columns={c: c.replace("mock_", "suneung_") for c in _all_su_src})
                    _suneung_avail = [c for c in _suneung_feat.columns if c != "student_id"]

            # 내신 등급 컬럼 — 표에는 전교과·국수영만 표시
            _grade_score_cols = [c for c in ["all_grade", "ksy_grade"]
                                  if not grad_features.empty and c in grad_features.columns]
            # 수능 있으면 해당 mock_ 제외, 없으면 mock_ 포함
            _mock_score_cols = [c for c in ["mock_kor_percentile", "mock_math_percentile",
                                            "mock_eng_grade", "mock_ks_percentile"]
                                if not grad_features.empty and c in grad_features.columns
                                and c.replace("mock_", "suneung_") not in _suneung_avail]
            score_cols_tr = _grade_score_cols + _mock_score_cols

            def _merge_scores(d, badge=True):
                """내신·수능(모의) 성적 병합."""
                d = d.copy()
                if score_cols_tr and not grad_features.empty and "student_id" in grad_features.columns and "student_id" in d.columns:
                    sc = grad_features[["student_id"] + score_cols_tr].copy()
                    sc["student_id"] = sc["student_id"].astype(str).str.strip()
                    d["student_id"] = d["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
                    d = d.merge(sc, on="student_id", how="left")
                elif "student_id" in d.columns:
                    d["student_id"] = d["student_id"].astype(str).str.replace(".0", "", regex=False).str.strip()
                if not _suneung_feat.empty and "student_id" in d.columns:
                    _su_m = _suneung_feat.copy()
                    _su_m["student_id"] = _su_m["student_id"].astype(str).str.strip()
                    d = d.merge(_su_m, on="student_id", how="left")
                if badge and "final_result" in d.columns:
                    d["final_result"] = d["final_result"].astype(str).apply(_result_badge)
                return d

            base_cols = [c for c in ["source", "student_id", "name", "college", "department",
                                      "admission_name", "admission_method", "minimum_requirement",
                                      "first_result", "final_result", "registered"]
                         if c in cases_df.columns]

            col_rename_tr = {
                "source": "구분", "student_id": "학번", "name": "이름",
                "college": "대학", "department": "모집단위", "admission_name": "전형명",
                "admission_method": "전형방법", "minimum_requirement": "최저학력기준",
                "first_result": "1차결과", "final_result": "최종결과", "registered": "등록",
                "all_grade": "전교과 등급", "ksy_grade": "국수영 등급",
                "kor_grade": "국어 등급", "math_grade": "수학 등급", "eng_grade": "영어 등급",
                "mock_kor_percentile": "모의 국어 백분위", "mock_math_percentile": "모의 수학 백분위",
                "mock_eng_grade": "모의 영어 등급", "mock_ks_percentile": "모의 국수 종합",
                "suneung_kor_percentile": "수능 국어 백분위",
                "suneung_math_percentile": "수능 수학 백분위",
                "suneung_eng_grade": "수능 영어 등급",
                "suneung_ks_percentile": "국수탐2 백분위 종합",
            }

            def _apply_mask(d: pd.DataFrame) -> pd.DataFrame:
                if _show_full:
                    return d
                d = d.copy()
                if "학번" in d.columns:
                    d["학번"] = d["학번"].astype(str).apply(
                        lambda x: _mask_id(x) if x not in ("", "nan") else x)
                if "이름" in d.columns:
                    d["이름"] = d["이름"].astype(str).apply(
                        lambda x: _mask_name(x) if x not in ("", "nan") else x)
                return d

            def _fmt_suneung_cell(row) -> str:
                """수능 데이터를 '국어 3등급(87) / 수학 1등급(95) / 영어 2등급 / 한국사 1등급 / 생명과학II 2등급' 형태로 합치기."""
                def _get(col):
                    return row.get(col) if col in row.index else float("nan")

                parts = []
                kor = pd.to_numeric(_get("suneung_kor_percentile"), errors="coerce")
                if pd.notna(kor):
                    parts.append(f"국어 {_pct_to_grade9(kor)}등급({int(round(kor))})")

                math_ = pd.to_numeric(_get("suneung_math_percentile"), errors="coerce")
                if pd.notna(math_):
                    parts.append(f"수학 {_pct_to_grade9(math_)}등급({int(round(math_))})")

                eng = pd.to_numeric(_get("suneung_eng_grade"), errors="coerce")
                if pd.notna(eng):
                    parts.append(f"영어 {int(round(eng))}등급")

                han = pd.to_numeric(_get("suneung_hanuksa_grade"), errors="coerce")
                if pd.notna(han):
                    parts.append(f"한국사 {int(round(han))}등급")

                soc_g = pd.to_numeric(_get("suneung_soc_grade"), errors="coerce")
                if pd.notna(soc_g):
                    soc_subj = str(_get("suneung_tanku1_subject") or "").strip()
                    name1 = soc_subj if soc_subj and soc_subj not in ("nan", "") else "탐구1"
                    soc_p = pd.to_numeric(_get("suneung_soc_percentile"), errors="coerce")
                    pct1 = f"({int(round(soc_p))})" if pd.notna(soc_p) else ""
                    parts.append(f"{name1} {int(round(soc_g))}등급{pct1}")

                sci_g = pd.to_numeric(_get("suneung_sci_grade"), errors="coerce")
                if pd.notna(sci_g):
                    sci_subj = str(_get("suneung_tanku2_subject") or "").strip()
                    name2 = sci_subj if sci_subj and sci_subj not in ("nan", "") else "탐구2"
                    sci_p = pd.to_numeric(_get("suneung_sci_percentile"), errors="coerce")
                    pct2 = f"({int(round(sci_p))})" if pd.notna(sci_p) else ""
                    parts.append(f"{name2} {int(round(sci_g))}등급{pct2}")

                return " / ".join(parts) if parts else "-"

            def _make_display(df_sub):
                d = _merge_scores(df_sub[base_cols + [c for c in score_cols_tr if c in df_sub.columns]])
                if "student_id" in d.columns:
                    d["student_id"] = d["student_id"].apply(clean_display_id)
                # 수능 성적을 단일 열로 합치기
                if _suneung_avail and any(c in d.columns for c in _suneung_avail):
                    d["수능 성적 등급(백분위)"] = d.apply(_fmt_suneung_cell, axis=1)
                    # suneung_ks_percentile은 별도 열로 표시 → drop 제외
                    _su_drop = [c for c in _suneung_avail
                                if c != "suneung_ks_percentile" and c in d.columns]
                    d = d.drop(columns=_su_drop)
                d = d.rename(columns={k: v for k, v in col_rename_tr.items() if k in d.columns})
                return _apply_mask(d)

            def _stat_card_group(label: str, color: str, items: list):
                """그룹 제목 + 3칸 metric 카드 렌더링."""
                st.markdown(
                    f"<div style='background:{color};border-left:4px solid #4a86e8;"
                    f"padding:6px 14px 2px;border-radius:6px;margin:10px 0 4px'>"
                    f"<b style='font-size:14px'>{label}</b></div>",
                    unsafe_allow_html=True,
                )
                cols_ = st.columns(len(items))
                for i, (title, val, help_txt) in enumerate(items):
                    cols_[i].metric(title, val, help=help_txt)

            def _show_stat_cards(df_group, is_pass_group: bool):
                """합격/불합격 그룹의 성적 통계 — 그룹 카드 형태."""
                enriched = _merge_scores(df_group, badge=False)
                any_card = False

                # ── 내신 그룹 (전교과 / 국수영) ─────────────────
                st.caption("※ 내신 등급은 낮을수록 우수")
                for col, gname in [("all_grade", "📚 전교과 내신"), ("ksy_grade", "📐 국수영 내신")]:
                    if col not in enriched.columns:
                        continue
                    s = pd.to_numeric(enriched[col], errors="coerce").dropna()
                    if len(s) == 0:
                        continue
                    any_card = True
                    if is_pass_group:
                        items = [
                            ("커트라인", f"{s.max():.2f}등급", "합격자 중 가장 낮은 성적 (최저 합격선)"),
                            ("70%선",   f"{s.quantile(0.7):.2f}등급", "합격자 70%가 이 등급 이내"),
                            ("평균",    f"{s.mean():.2f}등급", "합격자 평균 내신"),
                        ]
                    else:
                        items = [
                            ("최고 불합격", f"{s.min():.2f}등급", "불합격자 중 가장 좋은 성적"),
                            ("70%선",      f"{s.quantile(0.3):.2f}등급", "불합격자 70%가 이 등급 이상"),
                            ("평균",       f"{s.mean():.2f}등급", "불합격자 평균 내신"),
                        ]
                    _stat_card_group(gname, "#f0f4ff", items)

                # ── 수능 그룹: 국어/수학/영어 개별 카드 ─────────
                _has_suneung = any(
                    col in enriched.columns and pd.to_numeric(enriched[col], errors="coerce").notna().any()
                    for col in ["suneung_kor_percentile", "suneung_math_percentile", "suneung_eng_grade"]
                )

                if _has_suneung:
                    st.caption("※ 수능 백분위는 높을수록, 영어 등급은 낮을수록 우수")
                    # 국어 백분위
                    if "suneung_kor_percentile" in enriched.columns:
                        s = pd.to_numeric(enriched["suneung_kor_percentile"], errors="coerce").dropna()
                        if len(s) > 0:
                            any_card = True
                            if is_pass_group:
                                items = [
                                    ("하한",  f"{s.min():.1f} ({_pct_to_grade9(s.min())}등급)", "합격자 수능 국어 최저 백분위"),
                                    ("70%선", f"{s.quantile(0.3):.1f} ({_pct_to_grade9(s.quantile(0.3))}등급)", "합격자 70%가 이 백분위 이상"),
                                    ("평균",  f"{s.mean():.1f} ({_pct_to_grade9(s.mean())}등급)", "합격자 수능 국어 평균 백분위"),
                                ]
                            else:
                                items = [
                                    ("최고",  f"{s.max():.1f} ({_pct_to_grade9(s.max())}등급)", "불합격자 수능 국어 최고 백분위"),
                                    ("70%선", f"{s.quantile(0.7):.1f} ({_pct_to_grade9(s.quantile(0.7))}등급)", "불합격자 70%가 이 백분위 이하"),
                                    ("평균",  f"{s.mean():.1f} ({_pct_to_grade9(s.mean())}등급)", "불합격자 수능 국어 평균 백분위"),
                                ]
                            _stat_card_group("📘 수능 국어 백분위", "#f0fff4", items)

                    # 수학 백분위
                    if "suneung_math_percentile" in enriched.columns:
                        s = pd.to_numeric(enriched["suneung_math_percentile"], errors="coerce").dropna()
                        if len(s) > 0:
                            any_card = True
                            if is_pass_group:
                                items = [
                                    ("하한",  f"{s.min():.1f} ({_pct_to_grade9(s.min())}등급)", "합격자 수능 수학 최저 백분위"),
                                    ("70%선", f"{s.quantile(0.3):.1f} ({_pct_to_grade9(s.quantile(0.3))}등급)", "합격자 70%가 이 백분위 이상"),
                                    ("평균",  f"{s.mean():.1f} ({_pct_to_grade9(s.mean())}등급)", "합격자 수능 수학 평균 백분위"),
                                ]
                            else:
                                items = [
                                    ("최고",  f"{s.max():.1f} ({_pct_to_grade9(s.max())}등급)", "불합격자 수능 수학 최고 백분위"),
                                    ("70%선", f"{s.quantile(0.7):.1f} ({_pct_to_grade9(s.quantile(0.7))}등급)", "불합격자 70%가 이 백분위 이하"),
                                    ("평균",  f"{s.mean():.1f} ({_pct_to_grade9(s.mean())}등급)", "불합격자 수능 수학 평균 백분위"),
                                ]
                            _stat_card_group("📗 수능 수학 백분위", "#f0fff4", items)

                    # 영어 등급 (낮을수록 좋음)
                    if "suneung_eng_grade" in enriched.columns:
                        s = pd.to_numeric(enriched["suneung_eng_grade"], errors="coerce").dropna()
                        if len(s) > 0:
                            any_card = True
                            rate_1 = f"{(s <= 1).mean() * 100:.0f}%"
                            if is_pass_group:
                                items = [
                                    ("커트라인",   f"{int(round(s.max()))}등급", "합격자 수능 영어 최저 등급"),
                                    ("70%선",      f"{int(round(s.quantile(0.7)))}등급", "합격자 70%가 이 등급 이내"),
                                    ("1등급 비율", rate_1, "합격자 중 영어 1등급 비율"),
                                ]
                            else:
                                items = [
                                    ("최고 불합격", f"{int(round(s.min()))}등급", "불합격자 수능 영어 최고 등급"),
                                    ("70%선",       f"{int(round(s.quantile(0.3)))}등급", "불합격자 70%가 이 등급 이상"),
                                    ("1등급 비율",  rate_1, "불합격자 중 영어 1등급 비율"),
                                ]
                            _stat_card_group("📙 수능 영어 등급", "#f0fff4", items)

                else:
                    # 수능 데이터 없을 때 모의고사 fallback
                    st.caption("※ 수능(311월) 데이터 없음 — 최근 모의고사 기준")
                    for col, gname in [
                        ("mock_kor_percentile",  "📘 모의 국어 백분위"),
                        ("mock_math_percentile", "📗 모의 수학 백분위"),
                    ]:
                        if col not in enriched.columns:
                            continue
                        s = pd.to_numeric(enriched[col], errors="coerce").dropna()
                        if len(s) == 0:
                            continue
                        any_card = True
                        if is_pass_group:
                            items = [
                                ("하한",  f"{s.min():.1f}", "합격자 최저 백분위"),
                                ("70%선", f"{s.quantile(0.3):.1f}", "합격자 70%가 이 백분위 이상"),
                                ("평균",  f"{s.mean():.1f}", "합격자 평균 백분위"),
                            ]
                        else:
                            items = [
                                ("최고",  f"{s.max():.1f}", "불합격자 최고 백분위"),
                                ("70%선", f"{s.quantile(0.7):.1f}", "불합격자 70%가 이 백분위 이하"),
                                ("평균",  f"{s.mean():.1f}", "불합격자 평균 백분위"),
                            ]
                        _stat_card_group(gname, "#fff8f0", items)

                    if "mock_eng_grade" in enriched.columns:
                        s = pd.to_numeric(enriched["mock_eng_grade"], errors="coerce").dropna()
                        if len(s) > 0:
                            any_card = True
                            rate_1 = f"{(s <= 1).mean() * 100:.0f}%"
                            if is_pass_group:
                                items = [
                                    ("커트라인",  f"{s.max():.0f}등급", "합격자 최저 모의 영어 등급"),
                                    ("70%선",     f"{s.quantile(0.7):.0f}등급", "합격자 70%가 이 등급 이내"),
                                    ("1등급 비율", rate_1, "합격자 중 영어 1등급 비율"),
                                ]
                            else:
                                items = [
                                    ("최고 불합격", f"{s.min():.0f}등급", "불합격자 최고 모의 영어 등급"),
                                    ("70%선",       f"{s.quantile(0.3):.0f}등급", "불합격자 70%가 이 등급 이상"),
                                    ("1등급 비율",  rate_1, "불합격자 중 영어 1등급 비율"),
                                ]
                            _stat_card_group("📙 모의 영어 등급", "#fff8f0", items)

                if not any_card:
                    st.caption("성적 데이터가 없습니다. 분석 실행 후 다시 확인해주세요.")
                    return
                st.divider()

            # 합격/불합격 판별
            def is_pass(v):
                s = str(v).strip()
                return "합" in s and "불합" not in s

            def is_fail(v):
                s = str(v).strip()
                return "불" in s or "불합" in s

            # 수시/정시 분리
            if "source" in cases_df.columns:
                susi_mask_tr   = cases_df["source"].astype(str).str.contains("수시", na=False)
                jungsi_mask_tr = cases_df["source"].astype(str).str.contains("정시", na=False)
            else:
                susi_mask_tr   = pd.Series([True] * len(cases_df), index=cases_df.index)
                jungsi_mask_tr = pd.Series([False] * len(cases_df), index=cases_df.index)

            def _render_group_tabs(df_group, key_pfx=""):
                """전체/합격자/불합격자 서브탭 렌더링."""
                if df_group.empty:
                    st.info("데이터가 없습니다.")
                    return
                pm = df_group["final_result"].astype(str).apply(is_pass) if "final_result" in df_group.columns else pd.Series([False] * len(df_group), index=df_group.index)
                fm = df_group["final_result"].astype(str).apply(is_fail) if "final_result" in df_group.columns else pd.Series([False] * len(df_group), index=df_group.index)
                sub1, sub2, sub3 = st.tabs([
                    f"전체 ({len(df_group)}건)",
                    f"합격자 ({int(pm.sum())}건)",
                    f"불합격자 ({int(fm.sum())}건)",
                ])
                with sub1:
                    st.dataframe(_make_display(df_group), use_container_width=True, hide_index=True)
                with sub2:
                    passed = df_group[pm].copy()
                    if passed.empty:
                        st.info("합격자 데이터가 없습니다.")
                    else:
                        if "admission_name" in passed.columns:
                            passed["_adm_type"] = passed.apply(
                                lambda r: _classify_adm_type(
                                    r.get("admission_name", ""),
                                    r.get("admission_group", ""),
                                ), axis=1,
                            )
                            _type_opts = ["전체"] + sorted(passed["_adm_type"].unique().tolist())
                            if len(_type_opts) > 2:
                                _sel = st.selectbox("전형 유형 필터", _type_opts,
                                                    key=f"adm_pass_{key_pfx}")
                                if _sel != "전체":
                                    passed = passed[passed["_adm_type"] == _sel]
                        _show_stat_cards(passed, is_pass_group=True)
                        st.dataframe(_make_display(passed), use_container_width=True, hide_index=True)
                with sub3:
                    failed = df_group[fm].copy()
                    if failed.empty:
                        st.info("불합격자 데이터가 없습니다.")
                    else:
                        if "admission_name" in failed.columns:
                            failed["_adm_type"] = failed.apply(
                                lambda r: _classify_adm_type(
                                    r.get("admission_name", ""),
                                    r.get("admission_group", ""),
                                ), axis=1,
                            )
                            _type_opts_f = ["전체"] + sorted(failed["_adm_type"].unique().tolist())
                            if len(_type_opts_f) > 2:
                                _sel_f = st.selectbox("전형 유형 필터", _type_opts_f,
                                                      key=f"adm_fail_{key_pfx}")
                                if _sel_f != "전체":
                                    failed = failed[failed["_adm_type"] == _sel_f]
                        _show_stat_cards(failed, is_pass_group=False)
                        st.dataframe(_make_display(failed), use_container_width=True, hide_index=True)

            # ── 메인 탭: 전체 / 수시 / 정시
            susi_df_tr   = cases_df[susi_mask_tr]
            jungsi_df_tr = cases_df[jungsi_mask_tr]
            mt1, mt2, mt3 = st.tabs([
                f"전체 ({len(cases_df)}건)",
                f"수시 ({int(susi_mask_tr.sum())}건)",
                f"정시 ({int(jungsi_mask_tr.sum())}건)",
            ])
            with mt1:
                _render_group_tabs(cases_df, "all")
            with mt2:
                _render_group_tabs(susi_df_tr, "susi")
            with mt3:
                _render_group_tabs(jungsi_df_tr, "jungsi")

            # ── 보고서에 추가 버튼 ────────────────────────────────────────────
            st.divider()

            def _safe_stat(s: pd.Series):
                """통계 dict 반환 (데이터 없으면 None)."""
                s2 = pd.to_numeric(s, errors="coerce").dropna()
                if len(s2) == 0:
                    return None
                return {
                    "min":  float(s2.min()),
                    "max":  float(s2.max()),
                    "p70":  float(s2.quantile(0.7)),
                    "p30":  float(s2.quantile(0.3)),
                    "mean": float(s2.mean()),
                    "n":    int(len(s2)),
                }

            def _compute_pinned_stats():
                """현재 검색 결과의 합격/불합격 통계를 dict로 반환."""
                pm_ = cases_df["final_result"].astype(str).apply(is_pass) if "final_result" in cases_df.columns else pd.Series([False] * len(cases_df), index=cases_df.index)
                fm_ = cases_df["final_result"].astype(str).apply(is_fail) if "final_result" in cases_df.columns else pd.Series([False] * len(cases_df), index=cases_df.index)
                pass_e = _merge_scores(cases_df[pm_].copy(), badge=False)
                fail_e = _merge_scores(cases_df[fm_].copy(), badge=False) if fm_.sum() > 0 else pd.DataFrame()
                # department/admission_name은 list일 수 있음 (multiselect)
                _dept_str = " · ".join(department) if isinstance(department, list) else (department or "")
                _adm_str  = " · ".join(admission_name) if isinstance(admission_name, list) else (admission_name or "")
                entry = {
                    "title":          " · ".join(college_list) + (f" / {_dept_str}" if _dept_str else "") + (f" [{_adm_str}]" if _adm_str else ""),
                    "colleges":       list(college_list),
                    "department":     _dept_str,
                    "admission_name": _adm_str,
                    "pass_count":     int(pm_.sum()),
                    "fail_count":     int(fm_.sum()),
                }
                for col, key in [("all_grade", "all_grade"), ("ksy_grade", "ksy_grade")]:
                    entry[f"pass_{key}"] = _safe_stat(pass_e[col]) if col in pass_e.columns else None
                    entry[f"fail_{key}"] = _safe_stat(fail_e[col]) if not fail_e.empty and col in fail_e.columns else None
                for su_col in ["suneung_kor_percentile", "suneung_math_percentile", "suneung_eng_grade"]:
                    entry[f"pass_{su_col}"] = _safe_stat(pass_e[su_col]) if su_col in pass_e.columns else None
                    entry[f"fail_{su_col}"] = _safe_stat(fail_e[su_col]) if not fail_e.empty and su_col in fail_e.columns else None
                return entry

            _pinned        = st.session_state.setdefault("report_pinned_entries", [])
            _pin_key       = f"{'|'.join(sorted(college_list))}||{department}||{admission_name}"
            _already_added = any(e.get("_key") == _pin_key for e in _pinned)

            _pcol1, _pcol2 = st.columns([2, 5])
            with _pcol1:
                if _already_added:
                    if st.button("❌ 보고서에서 제거", key="tracker_unpin"):
                        st.session_state["report_pinned_entries"] = [e for e in _pinned if e.get("_key") != _pin_key]
                        st.rerun()
                elif len(_pinned) >= 3:
                    st.button("📌 보고서에 추가", disabled=True, key="tracker_pin",
                              help="최대 3개까지 추가 가능합니다. 먼저 기존 항목을 제거해주세요.")
                else:
                    if st.button("📌 보고서에 추가", key="tracker_pin", type="primary"):
                        try:
                            _new_entry = _compute_pinned_stats()
                            _new_entry["_key"] = _pin_key
                            st.session_state["report_pinned_entries"].append(_new_entry)
                            st.rerun()
                        except Exception as _pin_err:
                            st.error(f"보고서 추가 중 오류: {_pin_err}")
            with _pcol2:
                if _pinned:
                    _plist = " / ".join(f"[{i+1}] {e['title'][:18]}{'…' if len(e['title']) > 18 else ''}" for i, e in enumerate(_pinned))
                    st.caption(f"📌 추가됨 ({len(_pinned)}/3): {_plist}")
                else:
                    st.caption("검색 결과를 보고서에 추가할 수 있습니다. (최대 3개)")

        else:
            st.info("검색 결과가 없습니다.")

    # ── 관심 대학/학과 요약 ──────────────────────────────────────────
    section_header("📌 관심 대학/학과 요약")
    _pinned_entries = st.session_state.get("report_pinned_entries", [])
    if not _pinned_entries:
        st.info("역추적 섹션에서 '📌 보고서에 추가'를 눌러 대학/학과 통계를 추가하세요. (최대 3개)")
    else:
        for _pi, _pe in enumerate(_pinned_entries):
            _ph, _pdel = st.columns([8, 1])
            _ph.markdown(f"#### [{_pi + 1}] {_pe['title']}")
            if _pdel.button("🗑", key=f"del_pin_{_pi}", help="이 항목 삭제"):
                st.session_state["report_pinned_entries"].pop(_pi)
                st.rerun()

            _pc, _fc = _pe.get("pass_count", 0), _pe.get("fail_count", 0)
            st.caption(f"합격 {_pc}명 / 불합격 {_fc}명 / 총 {_pc + _fc}명")

            _pp_col, _pf_col = st.columns(2)

            with _pp_col:
                st.markdown("**✅ 합격자 통계**")
                for _gk, _glabel in [("pass_all_grade", "전교과 내신"), ("pass_ksy_grade", "국수영 내신")]:
                    _gs = _pe.get(_gk)
                    if _gs:
                        st.markdown(
                            f"**{_glabel}:** 커트라인 {_gs['max']:.2f}등급 / "
                            f"70%선 {_gs['p70']:.2f}등급 / 평균 {_gs['mean']:.2f}등급"
                        )
                _pk = _pe.get("pass_suneung_kor_percentile")
                if _pk:
                    st.markdown(
                        f"**수능 국어:** 하한 {_pk['min']:.1f} ({_pct_to_grade9(_pk['min'])}등급) / "
                        f"70%선 {_pk['p30']:.1f} ({_pct_to_grade9(_pk['p30'])}등급) / "
                        f"평균 {_pk['mean']:.1f} ({_pct_to_grade9(_pk['mean'])}등급)"
                    )
                _pm = _pe.get("pass_suneung_math_percentile")
                if _pm:
                    st.markdown(
                        f"**수능 수학:** 하한 {_pm['min']:.1f} ({_pct_to_grade9(_pm['min'])}등급) / "
                        f"70%선 {_pm['p30']:.1f} ({_pct_to_grade9(_pm['p30'])}등급) / "
                        f"평균 {_pm['mean']:.1f} ({_pct_to_grade9(_pm['mean'])}등급)"
                    )
                _pe_eng = _pe.get("pass_suneung_eng_grade")
                if _pe_eng:
                    st.markdown(
                        f"**수능 영어:** 커트라인 {int(round(_pe_eng['max']))}등급 / "
                        f"70%선 {int(round(_pe_eng['p70']))}등급 / "
                        f"평균 {_pe_eng['mean']:.1f}등급"
                    )

            with _pf_col:
                if _fc > 0:
                    st.markdown("**❌ 불합격자 통계**")
                    for _gk, _glabel in [("fail_all_grade", "전교과 내신"), ("fail_ksy_grade", "국수영 내신")]:
                        _gs = _pe.get(_gk)
                        if _gs:
                            st.markdown(
                                f"**{_glabel}:** 커트라인 {_gs['min']:.2f}등급 / "
                                f"70%선 {_gs['p30']:.2f}등급 / 평균 {_gs['mean']:.2f}등급"
                            )
                    _fk = _pe.get("fail_suneung_kor_percentile")
                    if _fk:
                        st.markdown(
                            f"**수능 국어:** 최고 {_fk['max']:.1f} ({_pct_to_grade9(_fk['max'])}등급) / "
                            f"평균 {_fk['mean']:.1f} ({_pct_to_grade9(_fk['mean'])}등급)"
                        )
                    _fm = _pe.get("fail_suneung_math_percentile")
                    if _fm:
                        st.markdown(
                            f"**수능 수학:** 최고 {_fm['max']:.1f} ({_pct_to_grade9(_fm['max'])}등급) / "
                            f"평균 {_fm['mean']:.1f} ({_pct_to_grade9(_fm['mean'])}등급)"
                        )
                    _fe_eng = _pe.get("fail_suneung_eng_grade")
                    if _fe_eng:
                        st.markdown(
                            f"**수능 영어:** 최고 {int(round(_fe_eng['min']))}등급 / "
                            f"평균 {_fe_eng['mean']:.1f}등급"
                        )

            st.divider()

    # ── 내신 9→5 변환 참고표 (화면 전체, PDF 범위 하이라이트) ──────────────
    section_header("📊 내신 9등급 / 5등급 변환 참고표 (2028~)")
    _conv_all = get_conv_table_data()   # 49개

    # 학생 전교과 등급 기준 중심 행
    _cv_stu_raw = current.get("all_grade") or current.get("overall_grade")
    _cv_center  = None
    if _cv_stu_raw is not None:
        try:
            _cv_sg = float(_cv_stu_raw)
            if 1.0 <= _cv_sg <= 5.5:
                _cv_center = min(range(len(_conv_all)), key=lambda i: abs(_conv_all[i][1] - _cv_sg))
        except Exception:
            pass

    # PDF 범위: 위 14행 + 학생 행 + 아래 1행 = 최대 16행
    _cv_pdf_start = max(0, _cv_center - 14) if _cv_center is not None else None
    _cv_pdf_end   = min(len(_conv_all), _cv_center + 2) if _cv_center is not None else None

    # HTML 테이블 생성 (2단)
    _cv_half = (len(_conv_all) + 1) // 2
    _cv_left  = _conv_all[:_cv_half]
    _cv_right = _conv_all[_cv_half:]

    def _cv_row_style(abs_idx: int) -> str:
        if _cv_center is not None and abs_idx == _cv_center:
            return "background:#fef9c3;font-weight:700;"
        if (_cv_pdf_start is not None
                and _cv_pdf_start <= abs_idx < _cv_pdf_end
                and abs_idx != _cv_center):
            return "background:#dbeafe;"
        return "background:#f8fafc;" if abs_idx % 2 == 0 else "background:#ffffff;"

    _cell = "padding:4px 10px;text-align:center;font-size:13px;border:1px solid #e2e8f0;"
    _hdr  = "padding:5px 10px;text-align:center;font-size:12px;font-weight:700;background:#dbeafe;border:1px solid #cbd5e1;"
    _sep  = "width:14px;border:none;background:white;"

    _cv_rows_html = ""
    for _ri in range(_cv_half):
        _g9l, _g5l, _pl = _cv_left[_ri]
        _ls = _cv_row_style(_ri)
        if _ri < len(_cv_right):
            _g9r, _g5r, _pr = _cv_right[_ri]
            _rs  = _cv_row_style(_cv_half + _ri)
            _r_cells = (
                f"<td style='{_cell}{_rs}'>{_g9r:.2f}</td>"
                f"<td style='{_cell}{_rs}'>{_g5r:.2f}</td>"
                f"<td style='{_cell}{_rs}'>상위 {_pr:.1f}%</td>"
            )
        else:
            _r_cells = "<td colspan='3' style='border:none;'></td>"
        _cv_rows_html += (
            "<tr>"
            f"<td style='{_cell}{_ls}'>{_g9l:.2f}</td>"
            f"<td style='{_cell}{_ls}'>{_g5l:.2f}</td>"
            f"<td style='{_cell}{_ls}'>상위 {_pl:.1f}%</td>"
            f"<td style='{_sep}'></td>"
            + _r_cells +
            "</tr>"
        )

    _cv_html = (
        "<div style='overflow-x:auto;'>"
        "<table style='border-collapse:collapse;width:100%;font-family:sans-serif;'>"
        "<thead><tr>"
        f"<th style='{_hdr}'>9등급</th><th style='{_hdr}'>5등급</th><th style='{_hdr}'>누적 백분위</th>"
        f"<th style='{_sep}'></th>"
        f"<th style='{_hdr}'>9등급</th><th style='{_hdr}'>5등급</th><th style='{_hdr}'>누적 백분위</th>"
        "</tr></thead><tbody>"
        + _cv_rows_html +
        "</tbody></table></div>"
    )

    _cv_legend = ""
    if _cv_center is not None:
        _cg9 = _conv_all[_cv_center][0]
        _cg5 = _conv_all[_cv_center][1]
        _cv_legend = (
            "<span style='display:inline-block;width:14px;height:14px;"
            "background:#fef9c3;border:1px solid #ccc;vertical-align:middle;margin-right:4px;'></span>"
            f"현재 학생 전교과 등급 ({_cg9:.2f} → 5등급제 {_cg5:.2f})&nbsp;&nbsp;&nbsp;"
            "<span style='display:inline-block;width:14px;height:14px;"
            "background:#dbeafe;border:1px solid #ccc;vertical-align:middle;margin-right:4px;'></span>"
            "PDF 출력 범위"
        )
    st.markdown(
        f"<div style='font-size:12px;margin-bottom:6px;'>{_cv_legend}</div>" + _cv_html,
        unsafe_allow_html=True,
    )
    st.caption("* 5등급제 경계 (2028~): 1등급 상위 10% / 2등급 ~34% / 3등급 ~66% / 4등급 ~90% | 9등급제 비율: 4-7-12-17-20-17-12-7-4%")
    st.markdown("")

    section_header("📄 보고서 저장")
    _ctx_base = st.session_state.get("report_context_base")
    if _ctx_base:
        _pinned_count = len(st.session_state.get("report_pinned_entries", []))
        _last_pinned_count = st.session_state.get("_last_pdf_pinned_count", -1)
        # pinned 개수 변화 또는 최초 생성 시에만 PDF 재생성
        if _last_pinned_count != _pinned_count:
            _pinned_now = st.session_state.get("report_pinned_entries", [])
            _ctx_fresh = build_report_context(
                **_ctx_base,
                pinned_entries=_pinned_now,
            )
            try:
                _pdf_path_fresh = export_pdf(_ctx_fresh)
                _pdf_deploy_fresh = export_pdf(_ctx_fresh, deploy=True)
                st.session_state["report_pdf_path"]        = _pdf_path_fresh
                st.session_state["report_pdf_deploy_path"] = _pdf_deploy_fresh
                st.session_state["_last_pdf_pinned_count"] = _pinned_count
            except Exception as _e:
                st.error(f"PDF 생성 오류: {_e}")

        _pdf_path        = st.session_state.get("report_pdf_path")
        _pdf_deploy_path = st.session_state.get("report_pdf_deploy_path")
        _btn_col1, _btn_col2 = st.columns(2)
        with _btn_col1:
            if _pdf_path:
                try:
                    with open(_pdf_path, "rb") as _f:
                        _pdf_bytes = _f.read()
                    st.download_button(
                        "학생용 PDF 저장",
                        data=_pdf_bytes,
                        file_name=Path(_pdf_path).name,
                        mime="application/pdf",
                    )
                except Exception:
                    st.warning("PDF 파일을 찾을 수 없습니다. 분석을 다시 실행해주세요.")
        with _btn_col2:
            if _pdf_deploy_path:
                try:
                    with open(_pdf_deploy_path, "rb") as _f:
                        _pdf_deploy_bytes = _f.read()
                    st.download_button(
                        "학생 PDF 보고서 생성(배포용)",
                        data=_pdf_deploy_bytes,
                        file_name=Path(_pdf_deploy_path).name,
                        mime="application/pdf",
                    )
                except Exception:
                    st.warning("배포용 PDF 파일을 찾을 수 없습니다. 분석을 다시 실행해주세요.")

    st.caption("본 보고서는 9등급제와 5등급제의 차이를 단순 환산하지 않고, 본교 학생들의 학교 내부 상대 위치와 실제 졸업생 입시 결과를 바탕으로 비교·분석한 참고용 자료입니다.")
    st.caption("본 결과는 진학 상담 지원을 위한 예측 자료로서 실제 전형 결과와 차이가 있을 수 있으며, 상담 자료로만 활용합니다.")
else:
    st.info("아직 분석이 실행되지 않았습니다. 상단의 '분석 실행' 버튼을 눌러 주세요.")