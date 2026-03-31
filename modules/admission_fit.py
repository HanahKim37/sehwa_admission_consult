from __future__ import annotations
import pandas as pd


def _safe_float(v, default=None):
    try:
        if v is None or pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def _ratio_to_score(v):
    if v is None or pd.isna(v):
        return None
    v = max(0.0, min(1.0, float(v)))
    return round(v * 100, 1)


def _grade_trend_bonus(trend: str) -> float:
    """종합형 전용: 내신 흐름이 실제 평가 요소"""
    if trend == "상승":
        return 4.0
    if trend == "유지":
        return 2.0
    return 0.0  # 하락, 판단불가 모두 0


def _get_student_ids(top_cases: pd.DataFrame | None) -> set:
    if not isinstance(top_cases, pd.DataFrame) or top_cases.empty or "student_id" not in top_cases.columns:
        return set()
    return {str(sid).replace(".0", "").strip() for sid in top_cases["student_id"].tolist()}


def _count_outcomes_by_type(
    top_cases: pd.DataFrame | None,
    susi_df: pd.DataFrame | None,
    jungsi_df: pd.DataFrame | None,
    use_susi: bool = True,
    use_jungsi: bool = False,
    include_kw: list | None = None,
    exclude_kw: list | None = None,
) -> dict:
    """전형 유형별로 실제 DB 레코드를 필터링해서 합/불/등록 건수를 집계."""
    counts = {"합": 0, "불": 0, "등록": 0}
    student_ids = _get_student_ids(top_cases)
    if not student_ids:
        return counts

    def _process(df: pd.DataFrame | None):
        if df is None or df.empty:
            return
        id_col = next((c for c in ["student_id", "학번"] if c in df.columns), None)
        if not id_col:
            return

        d = df.copy()
        d["_sid"] = d[id_col].astype(str).str.replace(".0", "", regex=False).str.strip()
        d = d[d["_sid"].isin(student_ids)]
        if d.empty:
            return

        # 전형명 또는 전형분류로 필터링
        if include_kw:
            mask = pd.Series(False, index=d.index)
            for col in ["admission_name", "admission_group"]:
                if col in d.columns:
                    mask |= d[col].astype(str).str.contains("|".join(include_kw), na=False)
            if exclude_kw:
                for col in ["admission_name", "admission_group"]:
                    if col in d.columns:
                        mask &= ~d[col].astype(str).str.contains("|".join(exclude_kw), na=False)
            d = d[mask]

        if d.empty:
            return

        for _, row in d.iterrows():
            result = str(row.get("final_result", "")).strip()
            reg = str(row.get("registered", "")).strip()
            if "합" in result and "불합" not in result:
                counts["합"] += 1
            elif "불합" in result or result == "불":
                counts["불"] += 1
            if reg and reg not in ["-", "nan", "", "X", "x", "불", "None"]:
                counts["등록"] += 1

    if use_susi:
        _process(susi_df)
    if use_jungsi:
        _process(jungsi_df)

    return counts


def _evidence_bonus(counts: dict) -> tuple[float, str]:
    total = counts["합"] + counts["불"] + counts["등록"]

    if total < 3:
        return 0.0, f"유사 사례 표본({total}건)이 부족하여 실적 반영을 제외했습니다."

    positive = counts["합"] + counts["등록"]
    ratio = positive / total
    bonus = round(ratio * 15, 1)
    comment = f"합격 {counts['합']}건, 등록 {counts['등록']}건, 불합격 {counts['불']}건 (총 {total}건)"
    return bonus, comment


def score_school_record_fit(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    all_pos = _ratio_to_score(current.get("all_pos"))
    ksy_pos = _ratio_to_score(current.get("ksy_pos"))
    grade_trend = current.get("grade_trend", "판단불가")

    counts = _count_outcomes_by_type(
        top_cases, susi_df, jungsi_df,
        use_susi=True, use_jungsi=False,
        include_kw=["교과"],
        exclude_kw=["논술"],
    )
    bonus, evidence = _evidence_bonus(counts)

    base_items = [v for v in [all_pos, ksy_pos] if v is not None]
    base = sum(base_items) / len(base_items) if base_items else 0.0

    # 교과형: 누적 내신 성적 기준 → 추세 보너스 없음
    score = round(base * 0.7 + bonus, 1)
    score = min(score, 100.0)

    reason = f"교과형은 전교과·국수영의 교내 상대 위치를 중심으로 계산했습니다. (내신 추세는 교과형 합격과 직접 연관이 낮아 반영하지 않았습니다)"
    comment = f"[교과형 수시 사례] {evidence}"
    return {"name": "교과형", "score": score, "reason": reason, "comment": comment}


def score_comprehensive_fit(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    kor = _ratio_to_score(current.get("kor_pos"))
    math_ = _ratio_to_score(current.get("math_pos"))
    all_pos = _ratio_to_score(current.get("all_pos"))
    grade_trend = current.get("grade_trend", "판단불가")

    counts = _count_outcomes_by_type(
        top_cases, susi_df, jungsi_df,
        use_susi=True, use_jungsi=False,
        include_kw=["종합"],
        exclude_kw=["논술"],
    )
    bonus, evidence = _evidence_bonus(counts)

    subject_scores = [v for v in [kor, math_, all_pos] if v is not None]
    balance = sum(subject_scores) / len(subject_scores) if subject_scores else 0.0

    # 종합형: 성장 흐름이 실제 평가 요소 → 소폭 반영 (상승 +4, 유지 +2)
    score = round(balance * 0.65 + _grade_trend_bonus(grade_trend) + bonus, 1)
    score = min(score, 100.0)

    reason = f"종합형은 전교과 위치와 국어·수학의 과목 구조, 내신 흐름('{grade_trend}')을 함께 반영했습니다."
    comment = f"[종합형 수시 사례] {evidence}"
    return {"name": "종합형", "score": score, "reason": reason, "comment": comment}


def score_essay_fit(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    kp = _safe_float(current.get("mock_kor_percentile"), 0.0)
    mp = _safe_float(current.get("mock_math_percentile"), 0.0)
    eng = _safe_float(current.get("mock_eng_grade"), 9.0)

    counts = _count_outcomes_by_type(
        top_cases, susi_df, jungsi_df,
        use_susi=True, use_jungsi=False,
        include_kw=["논술"],
    )
    bonus, evidence = _evidence_bonus(counts)

    english_adj = max(0.0, 100 - (eng - 1) * 12)
    score = round(kp * 0.35 + mp * 0.45 + english_adj * 0.10 + bonus, 1)
    score = min(score, 100.0)

    reason = "논술형은 모의 국어·수학 경쟁력을 중심으로 보고, 영어는 최저 대응 가능성의 보조 지표로 반영했습니다."
    comment = f"[논술형 수시 사례] {evidence}"
    return {"name": "논술형", "score": score, "reason": reason, "comment": comment}


def score_regular_fit(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    ks = _safe_float(current.get("mock_ks_percentile"), 0.0)
    mp = _safe_float(current.get("mock_math_percentile"), 0.0)
    eng = _safe_float(current.get("mock_eng_grade"), 9.0)
    mock_trend = current.get("mock_trend", "판단불가")

    counts = _count_outcomes_by_type(
        top_cases, susi_df, jungsi_df,
        use_susi=False, use_jungsi=True,
    )
    bonus, evidence = _evidence_bonus(counts)

    english_adj = max(0.0, 100 - (eng - 1) * 12)

    # 정시형: 수능 당일 점수 기준 → 추세 보너스 없음
    score = round(ks * 0.55 + mp * 0.20 + english_adj * 0.10 + bonus, 1)
    score = min(score, 100.0)

    reason = "정시형은 모의 국수 종합지표와 수학 경쟁력을 중심으로 계산했습니다. (정시는 수능 당일 점수 기준으로 추세 보너스를 반영하지 않았습니다)"
    comment = f"[정시 사례] {evidence}"
    return {"name": "정시형", "score": score, "reason": reason, "comment": comment}


def score_minimum_requirement_fit(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    eng = _safe_float(current.get("mock_eng_grade"), 9.0)
    ks = _safe_float(current.get("mock_ks_percentile"), 0.0)

    # 최저학력기준 있는 수시 전형 전체 기준
    counts = _count_outcomes_by_type(
        top_cases, susi_df, jungsi_df,
        use_susi=True, use_jungsi=False,
    )
    bonus, evidence = _evidence_bonus(counts)

    english_adj = max(0.0, 100 - (eng - 1) * 15)
    score = round(english_adj * 0.65 + ks * 0.20 + bonus, 1)
    score = min(score, 100.0)

    reason = "최저 대응력은 영어 등급과 모의 종합 경쟁력을 중심으로, 수시 최저 충족 가능성을 참고용으로 계산했습니다."
    comment = f"[수시 전체 사례] {evidence}"
    return {"name": "최저 대응력", "score": score, "reason": reason, "comment": comment}


def build_fit_summary(
    current: dict,
    top_cases: pd.DataFrame | None = None,
    susi_df: pd.DataFrame | None = None,
    jungsi_df: pd.DataFrame | None = None,
) -> dict:
    scores = [
        score_school_record_fit(current, top_cases, susi_df, jungsi_df),
        score_comprehensive_fit(current, top_cases, susi_df, jungsi_df),
        score_essay_fit(current, top_cases, susi_df, jungsi_df),
        score_regular_fit(current, top_cases, susi_df, jungsi_df),
        score_minimum_requirement_fit(current, top_cases, susi_df, jungsi_df),
    ]

    strongest = max(scores, key=lambda x: x["score"]) if scores else {"name": "", "score": 0}
    weakest = min(scores, key=lambda x: x["score"]) if scores else {"name": "", "score": 0}

    return {
        "scores": scores,
        "strongest": strongest,
        "weakest": weakest,
    }