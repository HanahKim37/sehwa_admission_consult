from __future__ import annotations
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────

def _safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def _clean_id(v):
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _clean_str_col(series: pd.Series) -> pd.Series:
    """
    엑셀 셀 줄바꿈 잔재 제거:
    - openpyxl이 \\r (0x0D)을 그대로 반환하는 경우
    - 일부 버전에서 리터럴 '_x000D_' 문자열로 반환하는 경우
    둘 다 공백으로 치환 후 strip.
    """
    return (
        series.astype(str)
        .str.replace("_x000D_", " ", regex=False)
        .str.replace("\r", " ", regex=False)
        .str.strip()
    )


def _fill_multiindex_ffill(df: pd.DataFrame) -> pd.DataFrame:
    """
    다중 헤더 시트에서 병합 셀로 인해 NaN이 된 상위 레벨을 ffill 처리.
    예: ('1학년 1학기', NaN, '전교과') → ('1학년 1학기', '석차등급', '전교과')

    마지막 레벨(실제 항목명)은 ffill 하지 않음.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    levels = list(zip(*df.columns.tolist()))
    new_levels = []
    for i, level in enumerate(levels):
        if i == len(levels) - 1:
            # 마지막 레벨은 그대로 유지
            new_levels.append(list(level))
        else:
            filled = []
            last_val = None
            for v in level:
                sv = str(v).strip()
                if sv.startswith("Unnamed:") or sv == "" or sv == "nan":
                    filled.append(last_val if last_val is not None else v)
                else:
                    last_val = v
                    filled.append(v)
            new_levels.append(filled)

    df = df.copy()
    df.columns = pd.MultiIndex.from_arrays(new_levels)
    return df


def _flatten_columns(cols) -> list[str]:
    flat = []
    for col in cols:
        if isinstance(col, tuple):
            parts = []
            for x in col:
                sx = str(x).strip()
                if not sx or sx.startswith("Unnamed:") or sx == "nan":
                    continue
                parts.append(sx)
            flat.append(" | ".join(parts) if parts else "")
        else:
            flat.append(str(col).strip())
    return flat


def _find_col_exact(df: pd.DataFrame, candidates: list[str]):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _find_col_contains(df: pd.DataFrame, include_keywords: list[str], exclude_keywords: list[str] | None = None):
    """첫 번째 매칭 컬럼 반환."""
    exclude_keywords = exclude_keywords or []
    for col in df.columns:
        col_s = str(col)
        if all(k in col_s for k in include_keywords) and not any(x in col_s for x in exclude_keywords):
            return col
    return None


def _find_pct_adjacent_to_grade(df: pd.DataFrame, grade_col: str | None) -> str | None:
    """등급 컬럼 기준 역방향으로 '백분위' 포함 컬럼 반환 (최대 4칸 앞까지 탐색)."""
    if grade_col is None or grade_col not in df.columns:
        return None
    cols = df.columns.tolist()
    grade_idx = cols.index(grade_col)
    for offset in range(1, 5):
        if grade_idx - offset < 0:
            break
        cand = str(cols[grade_idx - offset])
        if "백분위" in cand:
            return cols[grade_idx - offset]
    return None


def _find_all_cols_contains(df: pd.DataFrame, include_keywords: list[str], exclude_keywords: list[str] | None = None) -> list[str]:
    """매칭되는 모든 컬럼 반환 (전 학기 집계에 사용)."""
    exclude_keywords = exclude_keywords or []
    result = []
    for col in df.columns:
        col_s = str(col)
        if all(k in col_s for k in include_keywords) and not any(x in col_s for x in exclude_keywords):
            result.append(col)
    return result


def _coalesce_last(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """
    각 행에서 cols 순서로 마지막 non-NaN 값을 반환.
    (즉, 가장 최신 학기의 유효값 선택)
    """
    if not cols:
        return pd.Series([np.nan] * len(df), index=df.index)
    numeric_df = df[cols].apply(pd.to_numeric, errors="coerce")

    def last_valid(row):
        vals = [v for v in row if pd.notna(v)]
        return vals[-1] if vals else np.nan

    return numeric_df.apply(last_valid, axis=1)


# ─────────────────────────────────────────────
# 시트별 정규화
# ─────────────────────────────────────────────

def normalize_grade_sheet(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    # ✅ 핵심: 병합 셀 ffill → 모든 레벨에 상위 헤더값 전파
    data = _fill_multiindex_ffill(data)
    data.columns = _flatten_columns(data.columns)
    data = data.dropna(how="all").copy()

    # 식별 컬럼
    student_id_col = _find_col_exact(data, ["학번"]) or _find_col_contains(data, ["학번"])
    classroom_col  = _find_col_exact(data, ["학급"]) or _find_col_contains(data, ["학급"])
    serial_col     = (_find_col_exact(data, ["일련번호"])
                      or _find_col_contains(data, ["일련번호"])
                      or _find_col_exact(data, ["번호"])
                      or _find_col_contains(data, ["번호"], ["학번", "석차", "등급"]))
    name_col       = _find_col_exact(data, ["이름"]) or _find_col_contains(data, ["이름"])

    out = pd.DataFrame()
    out["student_id"] = data[student_id_col].apply(_clean_id) if student_id_col else None
    if classroom_col:
        out["classroom"] = data[classroom_col]
    if serial_col:
        out["serial_no"] = data[serial_col]
    if name_col:
        out["name"] = data[name_col].astype(str).str.strip()

    # ────────────────────────────────────────
    # 석차등급 블록: 전 학기 컬럼을 찾고, 각 학생의 마지막 유효값 사용
    # ────────────────────────────────────────

    # 전교과 (기준교과(전교과) 우선, 없으면 전교과)
    all_cols = (
        _find_all_cols_contains(data, ["석차등급", "기준교과(전교과)"])
        or _find_all_cols_contains(data, ["석차등급", "전교과"])
    )
    out["all_grade"] = _coalesce_last(data, all_cols)

    # 국수영
    ksy_cols = _find_all_cols_contains(
        data, ["석차등급", "국수영"], ["국수영사", "국수영과", "국수영사과"]
    )
    out["ksy_grade"] = _coalesce_last(data, ksy_cols)

    # 국어 (국수영, 수과 제외)
    kor_cols = _find_all_cols_contains(
        data, ["석차등급", "국"], ["국수영", "수과"]
    )
    out["kor_grade"] = _coalesce_last(data, kor_cols)

    # 수학 (수과, 국수영 제외)
    math_cols = _find_all_cols_contains(
        data, ["석차등급", "수"], ["수과", "국수영"]
    )
    out["math_grade"] = _coalesce_last(data, math_cols)

    # 영어 (국수영 제외)
    eng_cols = _find_all_cols_contains(
        data, ["석차등급", "영"], ["국수영"]
    )
    out["eng_grade"] = _coalesce_last(data, eng_cols)

    # 사회 (국수영사 제외)
    soc_cols = _find_all_cols_contains(
        data, ["석차등급", "사"], ["국수영사"]
    )
    out["soc_grade"] = _coalesce_last(data, soc_cols)

    # 과학 (국수영과, 국수영사과, 수과 제외)
    sci_cols = _find_all_cols_contains(
        data, ["석차등급", "과"], ["국수영과", "국수영사과", "수과"]
    )
    out["sci_grade"] = _coalesce_last(data, sci_cols)

    # 후속 코드 호환용 alias
    out["overall_grade"] = out["all_grade"]

    out = out.dropna(subset=["student_id"])
    out["student_id"] = out["student_id"].astype(str).str.strip()

    # ─ 진단용: 어떤 컬럼들이 감지됐는지 메타 정보 저장 ─
    out.attrs["detected_grade_cols"] = {
        "all_grade": all_cols,
        "ksy_grade": ksy_cols,
        "kor_grade": kor_cols,
        "math_grade": math_cols,
        "eng_grade": eng_cols,
        "soc_grade": soc_cols,
        "sci_grade": sci_cols,
    }

    return out


def normalize_mock_sheet(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    # ✅ 핵심: 병합 셀 ffill → 국어/수학/영어 등 과목명이 모든 하위 컬럼에 전파
    data = _fill_multiindex_ffill(data)
    data.columns = _flatten_columns(data.columns)
    data = data.dropna(how="all").copy()

    exam_key_col = _find_col_exact(data, ["학년월학번"]) or _find_col_contains(data, ["학년월학번"])
    name_col = _find_col_exact(data, ["성명"]) or _find_col_contains(data, ["성명"])
    track_col = _find_col_exact(data, ["계열"]) or _find_col_contains(data, ["계열"])

    out = pd.DataFrame()

    if exam_key_col:
        out["exam_student_key"] = data[exam_key_col].apply(_clean_id)
        # 규칙: 첫 1자리=학년, 다음 2자리=월, 나머지=학번
        # 예: 21031205 → 학년=2, 월=10, 학번=31205
        out["grade_level"] = out["exam_student_key"].str[0]
        out["exam_month"] = out["exam_student_key"].str[1:3]
        out["student_id"] = out["exam_student_key"].str[3:]
    else:
        out["exam_student_key"] = None
        out["student_id"] = None

    if name_col:
        out["name"] = data[name_col].astype(str).str.strip()
    if track_col:
        out["track"] = data[track_col]

    # 각 과목별 핵심 컬럼 탐색 (ffill 후 "국어 | 백분위" 형태로 존재)
    kor_pct_col    = _find_col_contains(data, ["국어", "백분위"])
    math_pct_col   = _find_col_contains(data, ["수학", "백분위"])
    eng_grade_col  = _find_col_contains(data, ["영어", "등급"])
    # 한국사
    hanuksa_grade_col = (
        _find_col_contains(data, ["한국사", "등급"])
        or _find_col_contains(data, ["한국사"])
        or _find_col_contains(data, ["한사"])
    )
    # 탐구1/탐구2 등급 및 과목명 (다양한 표기 패턴 대응)
    tanku1_grade_col = (
        _find_col_contains(data, ["탐구1", "등급"])
        or _find_col_contains(data, ["탐1", "등급"])
    )
    tanku2_grade_col = (
        _find_col_contains(data, ["탐구2", "등급"])
        or _find_col_contains(data, ["탐2", "등급"])
    )
    tanku1_subject_col = (
        _find_col_contains(data, ["탐구1", "과목"])
        or _find_col_contains(data, ["탐구1", "과목명"])
        or _find_col_contains(data, ["탐1", "과목"])
        or _find_col_contains(data, ["선택1", "과목"])
        or _find_col_contains(data, ["사탐1", "과목"])
        or _find_col_contains(data, ["과탐1", "과목"])
    )
    tanku2_subject_col = (
        _find_col_contains(data, ["탐구2", "과목"])
        or _find_col_contains(data, ["탐구2", "과목명"])
        or _find_col_contains(data, ["탐2", "과목"])
        or _find_col_contains(data, ["선택2", "과목"])
        or _find_col_contains(data, ["사탐2", "과목"])
        or _find_col_contains(data, ["과탐2", "과목"])
    )
    # 탐구1/2 백분위
    tanku1_pct_col = (
        _find_col_contains(data, ["탐구1", "백분위"])
        or _find_col_contains(data, ["탐1", "백분위"])
        or _find_col_contains(data, ["사탐1", "백분위"])
        or _find_col_contains(data, ["과탐1", "백분위"])
        or _find_col_contains(data, ["선택1", "백분위"])
        or _find_col_contains(data, ["선택과목1", "백분위"])
        or _find_pct_adjacent_to_grade(data, tanku1_grade_col)
    )
    tanku2_pct_col = (
        _find_col_contains(data, ["탐구2", "백분위"])
        or _find_col_contains(data, ["탐2", "백분위"])
        or _find_col_contains(data, ["사탐2", "백분위"])
        or _find_col_contains(data, ["과탐2", "백분위"])
        or _find_col_contains(data, ["선택2", "백분위"])
        or _find_col_contains(data, ["선택과목2", "백분위"])
        or _find_pct_adjacent_to_grade(data, tanku2_grade_col)
    )
    # 국수탐2 종합지표
    combined_pct_col = (
        _find_col_contains(data, ["국수탐2", "백분위합"])
        or _find_col_contains(data, ["백분위합"])
    )
    # 국수탐2 백분석차 (헤더명으로 동적 탐색, 열 위치에 의존하지 않음)
    combined_rank_col = (
        _find_col_contains(data, ["국수탐2", "백분석차"])
        or _find_col_contains(data, ["백분석차"])
    )
    # 총원 (교내 석차 비율 계산용)
    total_students_col = (
        _find_col_contains(data, ["총원"])
        or _find_col_contains(data, ["전체인원"])
        or _find_col_contains(data, ["인원수"])
    )

    # 숫자형 컬럼
    numeric_mapping = {
        "mock_kor_percentile":  kor_pct_col,
        "mock_math_percentile": math_pct_col,
        "mock_eng_grade":       eng_grade_col,
        "mock_hanuksa_grade":   hanuksa_grade_col,
        "mock_soc_grade":       tanku1_grade_col,
        "mock_sci_grade":       tanku2_grade_col,
        "mock_soc_percentile":  tanku1_pct_col,
        "mock_sci_percentile":  tanku2_pct_col,
        "mock_ks_percentile":   combined_pct_col,
        "mock_ks_rank":         combined_rank_col,
        "mock_total_students":  total_students_col,
    }
    for out_col, src_col in numeric_mapping.items():
        out[out_col] = _safe_numeric(data[src_col]) if src_col else np.nan

    # 문자형 컬럼 (탐구 과목명)
    string_mapping = {
        "mock_tanku1_subject": tanku1_subject_col,
        "mock_tanku2_subject": tanku2_subject_col,
    }
    for out_col, src_col in string_mapping.items():
        out[out_col] = data[src_col].astype(str).str.strip() if src_col else ""

    # 기존 코드 호환용
    out["combined_percentile_sum"] = out["mock_ks_percentile"]

    out = out.dropna(subset=["student_id"])
    out["student_id"] = out["student_id"].astype(str).str.strip()

    # 진단용 메타
    out.attrs["detected_mock_cols"] = {**numeric_mapping, **string_mapping}

    return out


def normalize_susi_sheet(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data.columns = [str(c).strip() for c in data.columns]
    rename_map = {
        "학번": "student_id",
        "이름": "name",
        "대학": "college",
        "지원\n시기": "apply_type",
        "전형명": "admission_name",
        "계열": "track_text",
        "모집단위": "department",
        "1\n단계": "first_result",
        "최종": "final_result",
        "예비": "waiting",
        "등록": "registered",
        "전형\n종류": "interview_type",
        "최저학력기준": "minimum_requirement",
        "전형분류": "admission_group",
        "전형방법": "admission_method",
    }
    data = data.rename(columns=rename_map)
    if "student_id" in data.columns:
        data["student_id"] = data["student_id"].apply(_clean_id)
    # 엑셀 셀 내 줄바꿈(\r 및 _x000D_) 제거
    for col in ["admission_name", "admission_method", "minimum_requirement",
                "college", "department", "track_text", "first_result",
                "final_result", "registered", "admission_group"]:
        if col in data.columns:
            data[col] = _clean_str_col(data[col])
    return data


def normalize_jungsi_sheet(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data.columns = [str(c).strip() for c in data.columns]
    rename_map = {
        "학번": "student_id",
        "이름": "name",
        "대학": "college",
        "군": "gun",
        "전형명": "admission_name",
        "계열": "track_text",
        "모집단위": "department",
        "1\n단계": "first_result",
        "최종": "final_result",
        "예비": "waiting",
        "등록": "registered",
        "전형분류": "admission_group",
        "전형방법": "admission_method",
    }
    data = data.rename(columns=rename_map)
    if "student_id" in data.columns:
        data["student_id"] = data["student_id"].apply(_clean_id)
    # 엑셀 셀 내 줄바꿈(\r 및 _x000D_) 제거
    for col in ["admission_name", "admission_method", "minimum_requirement",
                "college", "department", "track_text", "first_result",
                "final_result", "registered", "admission_group", "gun"]:
        if col in data.columns:
            data[col] = _clean_str_col(data[col])
    return data


def build_graduate_database(workbook: dict[str, pd.DataFrame]) -> dict:
    db = {}
    db["grade"] = normalize_grade_sheet(workbook["내신성적"]) if "내신성적" in workbook else pd.DataFrame()

    if "모의고사" in workbook:
        mock_df = normalize_mock_sheet(workbook["모의고사"])
        # attrs는 session_state 저장 시 유실될 수 있으므로 별도 키에도 저장
        db["mock"] = mock_df
        db["mock_detected_cols"] = mock_df.attrs.get("detected_mock_cols", {})
    else:
        db["mock"] = pd.DataFrame()
        db["mock_detected_cols"] = {}

    db["susi"] = normalize_susi_sheet(workbook["수시상담용"]) if "수시상담용" in workbook else pd.DataFrame()
    db["jungsi"] = normalize_jungsi_sheet(workbook["정시상담용"]) if "정시상담용" in workbook else pd.DataFrame()
    return db
