# modules/pdf_parser.py
import re
from typing import List, Dict, Any, Optional, Tuple

import pdfplumber


TITLE_PATTERN = re.compile(r"20\d{2}학년도\s*2학년\s*성적\s*자료")
STUDENT_HEADER_PATTERN = re.compile(r"학번\s*(\d{5})\s*이름\s*([가-힣A-Za-z0-9]+)")

GRADE_ROW_TYPES = {"중간", "기말", "종합"}
MOCK_MONTHS = {"3월", "6월", "9월", "10월"}


def _clean_cell(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").strip()


def _to_float(v):
    if v in ("", None, "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def _to_int(v):
    if v in ("", None, "-"):
        return None
    try:
        return int(str(v).replace(",", ""))
    except Exception:
        return None


def _parse_rank_total(v) -> Tuple[Optional[int], Optional[int]]:
    s = _clean_cell(v)
    if not s:
        return None, None

    m = re.match(r"(\d+)\s*(?:\(\d+\))?\s*/\s*(\d+)", s)
    if m:
        return _to_int(m.group(1)), _to_int(m.group(2))

    m2 = re.match(r"(\d+)", s)
    if m2:
        return _to_int(m2.group(1)), None

    return None, None


def _extract_text_from_page(page) -> str:
    return page.extract_text() or ""


def _find_word_top(page, keyword: str) -> Optional[float]:
    words = page.extract_words()
    candidates = [w for w in words if keyword in w.get("text", "")]
    if not candidates:
        return None
    return min(w["top"] for w in candidates)


def _crop_section(page, top_keyword: str, bottom_keyword: Optional[str] = None):
    top = _find_word_top(page, top_keyword)
    if top is None:
        return None

    if bottom_keyword:
        bottom = _find_word_top(page, bottom_keyword)
        if bottom is None:
            bottom = page.height - 10
    else:
        bottom = page.height - 10

    y0 = max(top + 12, 0)
    y1 = max(bottom - 5, y0 + 10)

    return page.crop((0, y0, page.width, y1))


def _extract_best_table(crop) -> List[List[str]]:
    if crop is None:
        return []

    settings_candidates = [
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "intersection_tolerance": 8,
            "snap_tolerance": 6,
            "join_tolerance": 6,
        },
        {
            "vertical_strategy": "lines_strict",
            "horizontal_strategy": "lines_strict",
            "intersection_tolerance": 8,
            "snap_tolerance": 6,
            "join_tolerance": 6,
        },
        {
            "vertical_strategy": "text",
            "horizontal_strategy": "lines",
            "intersection_tolerance": 8,
            "snap_tolerance": 6,
            "join_tolerance": 6,
        },
    ]

    best_table = []
    best_score = -1

    for settings in settings_candidates:
        try:
            tables = crop.extract_tables(table_settings=settings) or []
        except Exception:
            tables = []

        for table in tables:
            cleaned = [[_clean_cell(c) for c in row] for row in table if row]
            score = sum(1 for row in cleaned for c in row if c)
            if score > best_score:
                best_score = score
                best_table = cleaned

    return best_table


def _extract_basic_info_from_text(text: str) -> Dict[str, Any]:
    result = {"student_id": "", "name": "", "track": "미정"}
    m = STUDENT_HEADER_PATTERN.search(text)
    if m:
        result["student_id"] = m.group(1).strip()
        result["name"] = m.group(2).strip()
    return result


def _normalize_grade_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """
    내신 표 구조를 행 단위로 정리.
    병합셀 때문에 학기칸이 비어 있으면 fill-down.
    1학기 중간 -> ... -> 2학기 종합 패턴이 다시 시작되면 다음 학년으로 간주.
    """
    if not table:
        return []

    rows = []
    current_semester = None
    current_school_year = 1
    seen_labels = []

    for raw in table:
        row = [_clean_cell(c) for c in raw]
        joined = " ".join(c for c in row if c)

        has_exam_type = any(c in GRADE_ROW_TYPES for c in row)
        has_semester = any(c in ("1학기", "2학기") for c in row)

        if not (has_exam_type or ("중간" in joined or "기말" in joined or "종합" in joined)):
            continue

        semester = None
        exam_type = None

        for c in row[:3]:
            if c in ("1학기", "2학기"):
                semester = c
            if c in GRADE_ROW_TYPES:
                exam_type = c

        if semester is None:
            semester = current_semester

        if exam_type is None:
            for k in ["중간", "기말", "종합"]:
                if k in joined:
                    exam_type = k
                    break

        if semester is None or exam_type is None:
            continue

        current_label = f"{semester} {exam_type}"
        if current_label == "1학기 중간" and seen_labels:
            if seen_labels[-1] == "2학기 종합":
                current_school_year += 1

        seen_labels.append(current_label)
        current_semester = semester

        def get(i):
            return row[i] if i < len(row) else ""

        kor_rank, total1 = _parse_rank_total(get(3))
        math_rank, total2 = _parse_rank_total(get(6))
        ksy_rank, total3 = _parse_rank_total(get(21))
        all_rank, total4 = _parse_rank_total(get(23))

        total_students = _to_int(get(24)) or total4 or total3 or total2 or total1

        rows.append({
            "school_year": current_school_year,
            "semester": semester,
            "exam_type": exam_type,
            "label": f"{current_school_year}학년 {semester} {exam_type}",
            "kor_score": _to_float(get(2)),
            "kor_rank": kor_rank,
            "kor_grade": _to_float(get(4)),
            "math_score": _to_float(get(5)),
            "math_rank": math_rank,
            "math_grade": _to_float(get(7)),
            "eng_score": _to_float(get(8)),
            "eng_grade": _to_float(get(9)),
            "soc_score": _to_float(get(10)),
            "soc_grade": _to_float(get(11)),
            "sci_score": _to_float(get(12)),
            "sci_grade": _to_float(get(13)),
            "ksy_grade": _to_float(get(20)),
            "ksy_rank": ksy_rank,
            "all_grade": _to_float(get(22)),
            "all_rank": all_rank,
            "total_students": total_students,
        })

    return rows


def _normalize_mock_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """
    모의고사 표 구조를 행 단위로 정리.
    월(3월/6월/9월/10월)과 국수영/탐 구분 열은 병합셀일 수 있으므로 fill-down.
    10월 뒤 다시 3월이 나오면 다음 학년으로 간주.
    """
    if not table:
        return []

    rows = []
    current_school_year = 1
    seen_month_labels = []
    current_ks_type = None

    for raw in table:
        row = [_clean_cell(c) for c in raw]
        joined = " ".join(c for c in row if c)

        month = None
        for c in row[:2]:
            if c in MOCK_MONTHS:
                month = c
        if month is None:
            for m in ["3월", "6월", "9월", "10월"]:
                if joined.startswith(m):
                    month = m
                    break

        if month is None:
            continue

        if month == "3월" and seen_month_labels:
            if seen_month_labels[-1] == "10월":
                current_school_year += 1
        seen_month_labels.append(month)

        def get(i):
            return row[i] if i < len(row) else ""

        ks_type_raw = get(18)
        if ks_type_raw:
            current_ks_type = ks_type_raw
        ks_type = current_ks_type

        rows.append({
            "school_year": current_school_year,
            "month": month,
            "label": f"{current_school_year}학년 {month}",
            "kor_score": _to_float(get(1)),
            "kor_percentile": _to_float(get(2)),
            "kor_rank": _to_int(get(3)),
            "kor_grade": _to_float(get(4)),
            "math_score": _to_float(get(5)),
            "math_percentile": _to_float(get(6)),
            "math_rank": _to_int(get(7)),
            "math_grade": _to_float(get(8)),
            "eng_score": _to_float(get(9)),
            "eng_rank": _to_int(get(10)),
            "eng_grade": _to_float(get(11)),
            "soc_score": _to_float(get(12)),
            "soc_grade": _to_float(get(13)),
            "sci_score": _to_float(get(14)),
            "sci_grade": _to_float(get(15)),
            "history_score": _to_float(get(16)),
            "history_grade": _to_float(get(17)),
            "ks_type": ks_type,
            "ks_score": _to_float(get(19)),
            "ks_rank": _to_int(get(20)),
            "ks_percentile": _to_float(get(21)),
            "total_rank": _to_int(get(22)),
            "total_students": _to_int(get(23)),
        })

    return rows


def parse_consult_page(page) -> Dict[str, Any]:
    text = _extract_text_from_page(page)
    basic = _extract_basic_info_from_text(text)

    grade_crop = _crop_section(page, "내신고사", "전국연합학력평가")
    mock_crop = _crop_section(page, "전국연합학력평가", "상담 내용")

    grade_table = _extract_best_table(grade_crop)
    mock_table = _extract_best_table(mock_crop)

    grade_rows = _normalize_grade_table(grade_table)
    mock_rows = _normalize_mock_table(mock_table)

    return {
        "basic_info": basic,
        "grade_records": grade_rows,
        "mock_records": mock_rows,
        "raw_text": text,
    }


def parse_pdf_students(file) -> List[Dict[str, Any]]:
    results = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = _extract_text_from_page(page)
            if not text.strip():
                continue

            if TITLE_PATTERN.search(text) or STUDENT_HEADER_PATTERN.search(text):
                results.append(parse_consult_page(page))
            else:
                if len(text.strip()) > 100:
                    results.append(parse_consult_page(page))

    return results