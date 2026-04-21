from __future__ import annotations
import pandas as pd
import numpy as np


def _num(v):
    try:
        if v is None or pd.isna(v):
            return np.nan
        return float(v)
    except Exception:
        return np.nan


def _score_distance(a, b, scale=1.0):
    if pd.isna(a) or pd.isna(b):
        return np.nan
    return max(0.0, 100 - abs(a - b) * scale)


def _weighted_similarity(current: dict, row: pd.Series, items: list[tuple[str, str, float, float]]):
    total_score = 0.0
    used_weight = 0.0
    details = []

    for current_key, grad_key, scale, weight in items:
        a = _num(current.get(current_key))
        b = _num(row.get(grad_key))
        part = _score_distance(a, b, scale)

        if not pd.isna(part):
            total_score += part * weight
            used_weight += weight
            details.append(
                {
                    "항목": current_key,
                    "현재값": None if pd.isna(a) else round(a, 3),
                    "졸업생값": None if pd.isna(b) else round(b, 3),
                    "부분점수": round(part, 2),
                    "가중치": weight,
                }
            )

    if used_weight == 0:
        return 0.0, 0.0, details

    final_score = round(total_score / used_weight, 2)
    confidence = round(used_weight, 2)
    return final_score, confidence, details


def _pop_normalize(val: float, v_min: float, v_max: float) -> float:
    """
    졸업생 집단 내 범위(v_min~v_max)를 기준으로 0~100으로 정규화.
    → 상위권 학교처럼 all_pos가 0.8~1.0에 집중되어 있어도
      집단 내 상대적 차이를 의미 있게 펼쳐서 비교할 수 있게 함.
    """
    if pd.isna(val) or v_max <= v_min:
        return np.nan
    return float(max(0.0, min(100.0, (val - v_min) / (v_max - v_min) * 100)))


def calculate_grade_similarity(current: dict, graduates: pd.DataFrame) -> pd.DataFrame:
    if graduates.empty:
        return pd.DataFrame()

    # ── pos 컬럼: 졸업생 집단 내 범위로 재정규화 (0~100) ──
    # 이유: 상위권 학교에서 all_pos가 0.85~1.0에 밀집 →
    #       절대값 비교 시 모든 쌍이 94~97로 수렴하는 문제 방지
    pos_cols = ["all_pos", "ksy_pos", "kor_pos", "math_pos", "eng_pos", "soc_pos", "sci_pos"]
    pos_ranges: dict[str, tuple[float, float]] = {}
    for col in pos_cols:
        if col in graduates.columns:
            vals = pd.to_numeric(graduates[col], errors="coerce").dropna()
            if len(vals) >= 2:
                pos_ranges[col] = (float(vals.min()), float(vals.max()))

    def _cur_norm(col: str) -> float:
        raw = _num(current.get(col))
        if col not in pos_ranges or pd.isna(raw):
            return raw
        v_min, v_max = pos_ranges[col]
        return _pop_normalize(raw, v_min, v_max)

    def _grad_norm(col: str, row: pd.Series) -> float:
        raw = _num(row.get(col))
        if col not in pos_ranges or pd.isna(raw):
            return raw
        v_min, v_max = pos_ranges[col]
        return _pop_normalize(raw, v_min, v_max)

    # 핵심 원칙: 등급 숫자 직접 비교 금지
    # → 모든 비교는 석차/총원 기반 상대위치(pos)로만 수행
    # → 5등급(현재생) vs 9등급(졸업생) 직접 비교 오류 방지
    POS_ITEMS = [
        ("all_pos",  0.28),   # 전교과 위치
        ("ksy_pos",  0.22),   # 국수영 위치
        ("kor_pos",  0.12),   # 국어 위치
        ("math_pos", 0.12),   # 수학 위치
        ("eng_pos",  0.10),   # 영어 위치
        ("soc_pos",  0.08),   # 사회 계열 위치
        ("sci_pos",  0.08),   # 과학 계열 위치
    ]

    rows = []
    for _, row in graduates.iterrows():
        total_score = 0.0
        used_weight = 0.0
        details = []

        # pos 항목 (정규화 적용)
        for col, weight in POS_ITEMS:
            a = _cur_norm(col)
            b = _grad_norm(col, row)
            part = _score_distance(a, b, 1.0)
            if not pd.isna(part):
                total_score += part * weight
                used_weight += weight
                details.append({
                    "항목": col,
                    "현재값": None if pd.isna(a) else round(a, 1),
                    "졸업생값": None if pd.isna(b) else round(b, 1),
                    "부분점수": round(part, 2),
                    "가중치": weight,
                })

        if used_weight == 0:
            score, confidence = 0.0, 0.0
        else:
            score = round(total_score / used_weight, 2)
            confidence = round(used_weight, 2)
            if current.get("grade_trend") == "상승":
                score += 3
            elif current.get("grade_trend") == "유지":
                score += 1
            score = round(min(score, 100), 2)

        rows.append({
            "student_id": row.get("student_id"),
            "name": row.get("name"),
            "track": row.get("track"),
            "grade_similarity": score,
            "grade_confidence": confidence,
            "grade_detail": details,
        })

    df = pd.DataFrame(rows)
    df["sort_key"] = np.where(df["grade_confidence"] > 0, 1, 0)
    df = df.sort_values(["sort_key", "grade_similarity", "grade_confidence"], ascending=[False, False, False])
    df = df.drop(columns=["sort_key"])
    return df


def calculate_mock_similarity(current: dict, graduates: pd.DataFrame) -> pd.DataFrame:
    """
    모의 유사도 계산.

    비교 우선순위:
    1) 현재 학생의 국수탐 4과목 백분위합(mock_ks_pct_sum)이 있으면
       → 졸업생의 국수탐2 백분위합(mock_ks_percentile)과 비교 (같은 스케일)
    2) 없으면 국어·수학 개별 백분위 직접 비교
    ※ 현재 학생의 PDF 단일 ks_percentile은 졸업생 백분위합과 스케일이 다르므로 절대 직접 비교 금지
    """
    if graduates.empty:
        return pd.DataFrame()

    # 교내 상대위치(mock_ks_pos): 졸업생 집단 범위로 정규화
    ks_pos_range: tuple | None = None
    if "mock_ks_pos" in graduates.columns:
        vals = pd.to_numeric(graduates["mock_ks_pos"], errors="coerce").dropna()
        if len(vals) >= 2:
            ks_pos_range = (float(vals.min()), float(vals.max()))

    # 현재 학생 4과목 백분위합 유무 확인
    cur_pct_sum = _num(current.get("mock_ks_pct_sum"))
    has_pct_sum = not pd.isna(cur_pct_sum)

    if has_pct_sum:
        # ── 케이스 1: 4과목 백분위합 기준 ──────────────────────────────────
        # scale=0.30: 합산 차이 100점 ≈ 개별 25점 차이와 동등한 감점
        # 영어/탐구 scale 30: 1등급 차이 → 70점(기존 82점)으로 패널티 강화
        mock_items = [
            ("mock_ks_pct_sum",     "mock_ks_percentile",  0.30, 0.36),
            ("mock_kor_percentile", "mock_kor_percentile", 1.2,  0.14),
            ("mock_math_percentile","mock_math_percentile",1.2,  0.14),
            ("mock_eng_grade",      "mock_eng_grade",       30,   0.10),
            ("mock_soc_grade",      "mock_soc_grade",       30,   0.10),
            ("mock_sci_grade",      "mock_sci_grade",       30,   0.10),
        ]
    else:
        # ── 케이스 2: 국수 개별 백분위 기준 ─────────────────────────────────
        # mock_ks_percentile(단일) vs mock_ks_percentile(합산) 비교 금지
        mock_items = [
            ("mock_kor_percentile", "mock_kor_percentile", 1.2, 0.26),
            ("mock_math_percentile","mock_math_percentile",1.2, 0.30),
            ("mock_eng_grade",      "mock_eng_grade",       30,  0.14),
            ("mock_soc_grade",      "mock_soc_grade",       30,  0.10),
            ("mock_sci_grade",      "mock_sci_grade",       30,  0.10),
        ]

    rows = []
    for _, row in graduates.iterrows():
        score, confidence, details = _weighted_similarity(current, row, mock_items)

        # ── 교내 상대위치 보정 (백분석차 기반) ──────────────────────────────
        cur_pos  = _num(current.get("mock_ks_pos"))
        grad_pos = _num(row.get("mock_ks_pos"))
        if ks_pos_range and not pd.isna(cur_pos) and not pd.isna(grad_pos):
            cur_norm  = _pop_normalize(cur_pos,  *ks_pos_range)
            grad_norm = _pop_normalize(grad_pos, *ks_pos_range)
            part = _score_distance(cur_norm, grad_norm, 1.0)
            if not pd.isna(part):
                pos_weight = 0.12
                score      = round((score * confidence + part * pos_weight) / (confidence + pos_weight), 2)
                confidence = round(confidence + pos_weight, 2)
                details.append({
                    "항목": "mock_ks_pos (교내위치)",
                    "현재값":   round(cur_norm, 1),
                    "졸업생값": round(grad_norm, 1),
                    "부분점수": round(part, 2),
                    "가중치":   pos_weight,
                })

        if confidence > 0:
            if current.get("mock_trend") == "상승":
                score += 3
            elif current.get("mock_trend") == "유지":
                score += 1

        score = round(min(score, 100), 2)

        rows.append({
            "student_id":      row.get("student_id"),
            "name":            row.get("name"),
            "track":           row.get("track"),
            "mock_similarity": score,
            "mock_confidence": confidence,
            "mock_detail":     details,
        })

    df = pd.DataFrame(rows)
    df["sort_key"] = np.where(df["mock_confidence"] > 0, 1, 0)
    df = df.sort_values(["sort_key", "mock_similarity", "mock_confidence"], ascending=[False, False, False])
    df = df.drop(columns=["sort_key"])
    return df


def calculate_total_similarity(grade_df: pd.DataFrame, mock_df: pd.DataFrame) -> pd.DataFrame:
    if grade_df.empty and mock_df.empty:
        return pd.DataFrame()

    if grade_df.empty:
        merged = mock_df.copy()
        merged["grade_similarity"] = 0.0
        merged["grade_confidence"] = 0.0
    elif mock_df.empty:
        merged = grade_df.copy()
        merged["mock_similarity"] = 0.0
        merged["mock_confidence"] = 0.0
    else:
        merge_keys = ["student_id"]
        if "name" in grade_df.columns and "name" in mock_df.columns:
            merge_keys.append("name")
        if "track" in grade_df.columns and "track" in mock_df.columns:
            merge_keys.append("track")

        merged = pd.merge(grade_df, mock_df, on=merge_keys, how="outer")

    merged["grade_similarity"] = pd.to_numeric(merged.get("grade_similarity", 0), errors="coerce").fillna(0)
    merged["mock_similarity"] = pd.to_numeric(merged.get("mock_similarity", 0), errors="coerce").fillna(0)
    merged["grade_confidence"] = pd.to_numeric(merged.get("grade_confidence", 0), errors="coerce").fillna(0)
    merged["mock_confidence"] = pd.to_numeric(merged.get("mock_confidence", 0), errors="coerce").fillna(0)

    merged["total_similarity"] = (
        merged["grade_similarity"] * 0.50 + merged["mock_similarity"] * 0.50
    ).round(2)

    merged["total_confidence"] = (
        merged["grade_confidence"] * 0.50 + merged["mock_confidence"] * 0.50
    ).round(2)

    merged["has_evidence"] = np.where(merged["total_confidence"] > 0, 1, 0)
    merged = merged.sort_values(
        ["has_evidence", "total_similarity", "total_confidence"],
        ascending=[False, False, False]
    ).drop(columns=["has_evidence"])

    return merged


def get_top_similar_cases(sim_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if sim_df.empty:
        return sim_df

    filtered = sim_df.copy()
    if "total_confidence" in filtered.columns:
        evidence_df = filtered[filtered["total_confidence"] > 0].copy()
        if not evidence_df.empty:
            filtered = evidence_df

    top = filtered.head(n).copy()
    top["case_code"] = [f"사례 {chr(65 + i)}" for i in range(len(top))]
    return top