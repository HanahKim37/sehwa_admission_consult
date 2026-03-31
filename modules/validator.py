# modules/validator.py
from typing import Dict, Any, List


def validate_basic_info(data: Dict[str, Any]) -> List[str]:
    errors = []
    basic = data.get("basic_info", {})

    if not basic.get("student_id"):
        errors.append("학번이 추출되지 않았습니다.")
    if not basic.get("name"):
        errors.append("이름이 추출되지 않았습니다.")

    return errors


def _count_filled_values(records, keys):
    count = 0
    for row in records:
        for key in keys:
            val = row.get(key)
            if val not in (None, "", "-"):
                count += 1
    return count


def validate_grade_records(data: Dict[str, Any]) -> List[str]:
    errors = []
    grade_records = data.get("grade_records", [])

    if not grade_records:
        errors.append("내신고사 데이터가 없습니다.")
        return errors

    filled = _count_filled_values(
        grade_records,
        ["kor_score", "kor_grade", "math_score", "math_grade", "eng_score", "eng_grade", "all_grade"]
    )

    if filled == 0:
        errors.append("내신고사 값이 거의 추출되지 않았습니다.")
    elif filled < 8:
        errors.append("내신고사 추출값이 매우 적습니다. 확인이 필요합니다.")

    return errors


def validate_mock_records(data: Dict[str, Any]) -> List[str]:
    errors = []
    mock_records = data.get("mock_records", [])

    if not mock_records:
        errors.append("전국연합학력평가 데이터가 없습니다.")
        return errors

    filled = _count_filled_values(
        mock_records,
        ["kor_score", "kor_percentile", "math_score", "math_percentile", "eng_grade", "ks_percentile"]
    )

    if filled == 0:
        errors.append("전국연합학력평가 값이 거의 추출되지 않았습니다.")
    elif filled < 10:
        errors.append("전국연합학력평가 추출값이 매우 적습니다. 확인이 필요합니다.")

    return errors


def build_validation_report(data: Dict[str, Any]) -> Dict[str, Any]:
    errors = []
    errors.extend(validate_basic_info(data))
    errors.extend(validate_grade_records(data))
    errors.extend(validate_mock_records(data))

    if len(errors) == 0:
        status = "정상"
    elif len(errors) <= 2:
        status = "일부 누락"
    else:
        status = "확인 필요"

    return {
        "status": status,
        "messages": errors,
    }