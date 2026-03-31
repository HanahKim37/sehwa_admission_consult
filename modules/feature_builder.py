from typing import Dict, Any, List, Optional
import pandas as pd


GRADE_SCORE_COLS = [
    "all_grade", "ksy_grade", "kor_grade", "math_grade", "eng_grade", "soc_grade", "sci_grade"
]

MOCK_SCORE_COLS = [
    "kor_percentile", "math_percentile", "eng_grade", "soc_grade", "sci_grade", "ks_percentile"
]


def calc_relative_position(rank, total):
    if rank in (None, 0) or total in (None, 0):
        return None
    try:
        rank = float(rank)
        total = float(total)
        return round(1 - ((rank - 1) / total), 6)
    except Exception:
        return None


def calc_trend(values: List[float]) -> str:
    vals = [v for v in values if v is not None and pd.notna(v)]
    if len(vals) < 2:
        return "판단불가"
    if vals[-1] < vals[0]:
        return "상승"
    if vals[-1] > vals[0]:
        return "하락"
    return "유지"


def _safe_mean(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return round(float(s.mean()), 3)


def _row_has_any_value(row: pd.Series, cols: List[str]) -> bool:
    for col in cols:
        if col in row.index and pd.notna(row.get(col)):
            return True
    return False


def _clean_id(v):
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _format_year_label(v):
    if v is None or pd.isna(v):
        return ""
    try:
        return f"{int(float(v))}학년"
    except Exception:
        s = str(v).strip()
        return s if "학년" in s else f"{s}학년"


def _normalize_grade_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).copy()
    if df.empty:
        return df

    df["school_year_num"] = pd.to_numeric(df.get("school_year"), errors="coerce")
    sem_map = {"1학기": 1, "2학기": 2}
    exam_map = {"중간": 1, "기말": 2, "종합": 3}

    df["semester_order"] = df.get("semester").map(sem_map) if "semester" in df.columns else None
    df["exam_order"] = df.get("exam_type").map(exam_map) if "exam_type" in df.columns else None

    sort_cols = [c for c in ["school_year_num", "semester_order", "exam_order"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    labels = []
    for _, row in df.iterrows():
        y = _format_year_label(row.get("school_year"))
        s = str(row.get("semester", "")).strip()
        e = str(row.get("exam_type", "")).strip()
        label = " ".join([x for x in [y, s, e] if x])
        labels.append(label if label else "내신 기록")

    df["record_label"] = labels
    df["has_score"] = df.apply(lambda r: _row_has_any_value(r, GRADE_SCORE_COLS), axis=1)
    return df


def _normalize_mock_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).copy()
    if df.empty:
        return df

    df["school_year_num"] = pd.to_numeric(df.get("school_year"), errors="coerce")
    month_map = {"3월": 3, "6월": 6, "9월": 9, "10월": 10}
    df["month_num"] = df.get("month").map(month_map) if "month" in df.columns else None

    sort_cols = [c for c in ["school_year_num", "month_num"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    labels = []
    for _, row in df.iterrows():
        y = _format_year_label(row.get("school_year"))
        m = str(row.get("month", "")).strip()
        label = " ".join([x for x in [y, m] if x])
        labels.append(label if label else "모의 기록")

    df["record_label"] = labels
    df["has_score"] = df.apply(lambda r: _row_has_any_value(r, MOCK_SCORE_COLS), axis=1)
    return df


def get_grade_basis_options(data: Dict[str, Any]) -> List[str]:
    df = _normalize_grade_df(data.get("grade_records", []))
    options = ["최신 입력값", "전체 평균"]

    if df.empty:
        return options

    valid = df[df["has_score"]].copy()
    if valid.empty:
        return options

    for label in valid["record_label"].tolist():
        if label and label not in options:
            options.append(label)

    if {"school_year", "semester"}.issubset(valid.columns):
        for (y, s), _ in valid.groupby(["school_year", "semester"], dropna=False):
            if pd.notna(y) and pd.notna(s):
                opt = f"{_format_year_label(y)} {s} 평균"
                if opt not in options:
                    options.append(opt)

    return options


def get_mock_basis_options(data: Dict[str, Any]) -> List[str]:
    df = _normalize_mock_df(data.get("mock_records", []))
    options = ["최신 입력값", "전체 평균"]

    if df.empty:
        return options

    valid = df[df["has_score"]].copy()
    if valid.empty:
        return options

    for label in valid["record_label"].tolist():
        if label and label not in options:
            options.append(label)

    return options


def _pick_grade_rows_by_basis(df: pd.DataFrame, basis: str) -> pd.DataFrame:
    if df.empty:
        return df

    valid = df[df["has_score"]].copy()
    if valid.empty:
        return pd.DataFrame()

    if basis == "최신 입력값":
        return pd.DataFrame([valid.iloc[-1]])

    if basis == "전체 평균":
        return valid.copy()

    if basis.endswith("평균"):
        parts = basis.split()
        if len(parts) >= 3:
            y = pd.to_numeric(parts[0].replace("학년", ""), errors="coerce")
            s = parts[1]
            sub = valid.copy()
            if "school_year" in sub.columns:
                sub = sub[pd.to_numeric(sub["school_year"], errors="coerce") == y]
            if "semester" in sub.columns:
                sub = sub[sub["semester"] == s]
            return sub.copy()

    if "record_label" in valid.columns:
        sub = valid[valid["record_label"] == basis]
        if not sub.empty:
            return sub.copy()

    return pd.DataFrame()


def _pick_mock_rows_by_basis(df: pd.DataFrame, basis: str) -> pd.DataFrame:
    if df.empty:
        return df

    valid = df[df["has_score"]].copy()
    if valid.empty:
        return pd.DataFrame()

    if basis == "최신 입력값":
        return pd.DataFrame([valid.iloc[-1]])

    if basis == "전체 평균":
        return valid.copy()

    if "record_label" in valid.columns:
        sub = valid[valid["record_label"] == basis]
        if not sub.empty:
            return sub.copy()

    return pd.DataFrame()


def _build_grade_basis_detail(basis: str, sub: pd.DataFrame) -> str:
    if sub.empty:
        return "선택 기준에 해당하는 내신 데이터가 없습니다."

    labels = sub["record_label"].dropna().astype(str).tolist() if "record_label" in sub.columns else []

    if basis == "최신 입력값":
        return f"최신 입력값 기준으로 실제 사용한 내신 데이터: {labels[-1]}"
    if basis == "전체 평균":
        return f"전체 평균 기준으로 사용한 내신 데이터: {', '.join(labels)}"
    if basis.endswith("평균"):
        return f"{basis} 기준으로 평균에 사용한 내신 데이터: {', '.join(labels)}"
    return f"{basis} 기준으로 사용한 내신 데이터: {', '.join(labels)}"


def _build_mock_basis_detail(basis: str, sub: pd.DataFrame) -> str:
    if sub.empty:
        return "선택 기준에 해당하는 모의 데이터가 없습니다."

    labels = sub["record_label"].dropna().astype(str).tolist() if "record_label" in sub.columns else []

    if basis == "최신 입력값":
        return f"최신 입력값 기준으로 실제 사용한 모의 데이터: {labels[-1]}"
    if basis == "전체 평균":
        return f"전체 평균 기준으로 사용한 모의 데이터: {', '.join(labels)}"
    return f"{basis} 기준으로 사용한 모의 데이터: {', '.join(labels)}"


def _avg_relative_position(df: pd.DataFrame, rank_col: str) -> Optional[float]:
    vals = []
    for _, row in df.iterrows():
        v = calc_relative_position(row.get(rank_col), row.get("total_students"))
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)


def build_current_student_features(
    data: Dict[str, Any],
    grade_basis: str = "최신 입력값",
    mock_basis: str = "최신 입력값",
) -> Dict[str, Any]:
    grade_df_all = _normalize_grade_df(data.get("grade_records", []))
    mock_df_all = _normalize_mock_df(data.get("mock_records", []))

    grade_df = _pick_grade_rows_by_basis(grade_df_all, grade_basis)
    mock_df = _pick_mock_rows_by_basis(mock_df_all, mock_basis)

    feature = {
        "student_id": _clean_id(data.get("basic_info", {}).get("student_id", "")),
        "name": data.get("basic_info", {}).get("name", ""),
        "track": data.get("basic_info", {}).get("track", "미정"),
        "grade_basis": grade_basis,
        "mock_basis": mock_basis,
        "grade_record_count_used": len(grade_df),
        "mock_record_count_used": len(mock_df),
        "grade_basis_detail": _build_grade_basis_detail(grade_basis, grade_df),
        "mock_basis_detail": _build_mock_basis_detail(mock_basis, mock_df),
    }

    if not grade_df.empty:
        latest_grade = grade_df.iloc[-1]

        feature["latest_school_year"] = latest_grade.get("school_year")
        feature["latest_semester"] = latest_grade.get("semester")
        feature["latest_exam_type"] = latest_grade.get("exam_type")

        for key in GRADE_SCORE_COLS:
            if key in grade_df.columns:
                feature[key] = _safe_mean(grade_df[key]) if len(grade_df) > 1 else latest_grade.get(key)
            else:
                feature[key] = None

        feature["all_pos"]  = _avg_relative_position(grade_df, "all_rank")  if "all_rank"  in grade_df.columns else None
        feature["ksy_pos"]  = _avg_relative_position(grade_df, "ksy_rank")  if "ksy_rank"  in grade_df.columns else None
        feature["kor_pos"]  = _avg_relative_position(grade_df, "kor_rank")  if "kor_rank"  in grade_df.columns else None
        feature["math_pos"] = _avg_relative_position(grade_df, "math_rank") if "math_rank" in grade_df.columns else None
        feature["eng_pos"]  = _avg_relative_position(grade_df, "eng_rank")  if "eng_rank"  in grade_df.columns else None
        feature["soc_pos"]  = _avg_relative_position(grade_df, "soc_rank")  if "soc_rank"  in grade_df.columns else None
        feature["sci_pos"]  = _avg_relative_position(grade_df, "sci_rank")  if "sci_rank"  in grade_df.columns else None

        valid_grade_all = grade_df_all[grade_df_all["has_score"]].copy()
        feature["grade_trend"] = calc_trend(valid_grade_all["all_grade"].tolist()) if "all_grade" in valid_grade_all.columns else "판단불가"
    else:
        for key in GRADE_SCORE_COLS:
            feature[key] = None
        feature["all_pos"]  = None
        feature["ksy_pos"]  = None
        feature["kor_pos"]  = None
        feature["math_pos"] = None
        feature["eng_pos"]  = None
        feature["soc_pos"]  = None
        feature["sci_pos"]  = None
        feature["grade_trend"] = "판단불가"
        feature["latest_school_year"] = None
        feature["latest_semester"] = None
        feature["latest_exam_type"] = None

    if not mock_df.empty:
        latest_mock = mock_df.iloc[-1]

        feature["latest_mock_year"] = latest_mock.get("school_year")
        feature["latest_mock_month"] = latest_mock.get("month")

        mapping = {
            "kor_percentile":  "mock_kor_percentile",
            "math_percentile": "mock_math_percentile",
            "eng_grade":       "mock_eng_grade",
            "soc_grade":       "mock_soc_grade",
            "sci_grade":       "mock_sci_grade",
            "ks_percentile":   "mock_ks_percentile",
            "ks_score":        "mock_ks_score",
            "ks_rank":         "mock_ks_rank",
            "total_rank":      "mock_total_rank",
            "total_students":  "mock_total_students",
        }

        for src_key, out_key in mapping.items():
            if src_key in mock_df.columns:
                feature[out_key] = _safe_mean(mock_df[src_key]) if len(mock_df) > 1 else latest_mock.get(src_key)
            else:
                feature[out_key] = None

        valid_mock_all = mock_df_all[mock_df_all["has_score"]].copy()
        feature["mock_trend"] = calc_trend(valid_mock_all["ks_percentile"].tolist()) if "ks_percentile" in valid_mock_all.columns else "판단불가"
    else:
        feature["latest_mock_year"] = None
        feature["latest_mock_month"] = None
        feature["mock_kor_percentile"]  = None
        feature["mock_math_percentile"] = None
        feature["mock_eng_grade"]        = None
        feature["mock_soc_grade"]        = None
        feature["mock_sci_grade"]        = None
        feature["mock_ks_percentile"]   = None
        feature["mock_ks_score"]        = None
        feature["mock_ks_rank"]         = None
        feature["mock_total_rank"]      = None
        feature["mock_total_students"]  = None
        feature["mock_trend"] = "판단불가"

    return feature


def build_graduate_features(db):
    grade_df = db.get("grade", pd.DataFrame()).copy()
    mock_df = db.get("mock", pd.DataFrame()).copy()

    if grade_df.empty:
        return pd.DataFrame()

    # 학생 목록 (학번 기준 중복 제거)
    out = grade_df[["student_id"]].copy().drop_duplicates("student_id").reset_index(drop=True)

    if "name" in grade_df.columns:
        out = out.merge(
            grade_df[["student_id", "name"]].drop_duplicates("student_id"),
            on="student_id",
            how="left",
        )

    # serial_no (일련번호): 교사용 화면에서 학번 옆에 표시
    if "serial_no" in grade_df.columns:
        out = out.merge(
            grade_df[["student_id", "serial_no"]].drop_duplicates("student_id"),
            on="student_id",
            how="left",
        )

    # track: grade_df에 없으면 mock_df에서 가져옴 (계열값 1=인문, 2=자연)
    if "track" in grade_df.columns:
        out = out.merge(
            grade_df[["student_id", "track"]].drop_duplicates("student_id"),
            on="student_id",
            how="left",
        )
    elif not mock_df.empty and "track" in mock_df.columns:
        track_mock = mock_df[["student_id", "track"]].drop_duplicates("student_id")
        out = out.merge(track_mock, on="student_id", how="left")

    # 내신 등급 컬럼 (normalize_grade_sheet 결과 컬럼명 직접 사용)
    # overall_grade는 all_grade의 alias이므로 overall_grade → all_grade 로 추가
    grade_col_map = {
        "overall_grade": "all_grade",
        "ksy_grade": "ksy_grade",
        "kor_grade": "kor_grade",
        "math_grade": "math_grade",
        "eng_grade": "eng_grade",
        "soc_grade": "soc_grade",
        "sci_grade": "sci_grade",
    }

    for src, dst in grade_col_map.items():
        if dst in out.columns:
            continue  # 이미 추가된 경우 스킵
        if src in grade_df.columns:
            temp = grade_df[["student_id", src]].drop_duplicates("student_id")
            temp = temp.rename(columns={src: dst})
            out = out.merge(temp, on="student_id", how="left")
        elif dst in grade_df.columns:
            # overall_grade 없이 all_grade만 있는 경우 대비
            temp = grade_df[["student_id", dst]].drop_duplicates("student_id")
            out = out.merge(temp, on="student_id", how="left")

    # 상대위치 proxy: 9등급 기준 → 0(최하)~1(최상) 연속값
    # 1등급=1.0, 5등급=0.5, 9등급≈0.0
    def pos_from_grade(v):
        try:
            f = float(v)
            if pd.isna(f):
                return None
            return round(max(0.0, 1.0 - (f - 1.0) / 8.0), 6)
        except Exception:
            return None

    for g_col, p_col in [
        ("all_grade",  "all_pos"),
        ("ksy_grade",  "ksy_pos"),
        ("kor_grade",  "kor_pos"),
        ("math_grade", "math_pos"),
        ("eng_grade",  "eng_pos"),
        ("soc_grade",  "soc_pos"),
        ("sci_grade",  "sci_pos"),
    ]:
        if g_col in out.columns:
            out[p_col] = out[g_col].apply(pos_from_grade)

    # ────────────────────────────────────────────────────────
    # 모의고사: 학생당 여러 행(시험 회차별) → student_id 기준 평균 집계
    # normalize_mock_sheet가 이미 영문 컬럼명으로 정규화했으므로 직접 사용
    # ────────────────────────────────────────────────────────
    if not mock_df.empty and "student_id" in mock_df.columns:
        mock_target_cols = [
            c for c in [
                "mock_kor_percentile",
                "mock_math_percentile",
                "mock_eng_grade",
                "mock_soc_grade",
                "mock_sci_grade",
                "mock_ks_percentile",
            ]
            if c in mock_df.columns
        ]

        if mock_target_cols:
            numeric_mock = mock_df[["student_id"] + mock_target_cols].copy()
            for col in mock_target_cols:
                numeric_mock[col] = pd.to_numeric(numeric_mock[col], errors="coerce")
            # 학생별 평균 (시험 회차 전체)
            mock_agg = (
                numeric_mock.groupby("student_id")[mock_target_cols]
                .mean()
                .reset_index()
            )
            out = out.merge(mock_agg, on="student_id", how="left")

    return out