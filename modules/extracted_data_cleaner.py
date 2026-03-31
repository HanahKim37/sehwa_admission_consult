# modules/extracted_data_cleaner.py
from typing import Dict, Any, List


def clean_basic_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    basic = data.get("basic_info", {})
    basic["student_id"] = str(basic.get("student_id", "")).strip()
    basic["name"] = str(basic.get("name", "")).strip()
    basic["track"] = str(basic.get("track", "미정")).strip() or "미정"
    data["basic_info"] = basic
    return data


def _normalize_numeric(value):
    if value in ("", "-", None):
        return None
    try:
        return float(value)
    except Exception:
        return value


def normalize_exam_records(data: Dict[str, Any]) -> Dict[str, Any]:
    grade_records: List[Dict[str, Any]] = data.get("grade_records", [])
    mock_records: List[Dict[str, Any]] = data.get("mock_records", [])

    for row in grade_records:
        for key, value in list(row.items()):
            if key == "label":
                continue
            row[key] = _normalize_numeric(value)

    for row in mock_records:
        for key, value in list(row.items()):
            if key == "label":
                continue
            row[key] = _normalize_numeric(value)

    data["grade_records"] = grade_records
    data["mock_records"] = mock_records
    return data


def normalize_extracted_student(data: Dict[str, Any]) -> Dict[str, Any]:
    data = clean_basic_fields(data)
    data = normalize_exam_records(data)
    return data