from __future__ import annotations

def build_strength_summary(current: dict, fit_result: dict) -> str:
    strongest = fit_result.get("strongest", {}).get("name", "")
    return f"본 학생은 현재 입력된 성적 기준으로 {strongest} 전형에서 비교적 강점을 보입니다."

def build_weakness_summary(current: dict, fit_result: dict) -> str:
    weakest = fit_result.get("weakest", {}).get("name", "")
    return f"다만 {weakest} 관련 요소는 추가 점검이 필요합니다."

def build_strategy_summary(similar_cases, fit_result: dict) -> str:
    strongest = fit_result.get("strongest", {}).get("name", "")
    return f"유사 사례와 현재 성적 구조를 종합하면, {strongest} 중심 전략을 우선 검토하는 것이 적절합니다."

def get_report_disclaimer_lines() -> list[str]:
    return [
        "본 보고서는 9등급제와 5등급제의 차이를 단순 환산하지 않고, 본교 학생들의 학교 내부 상대 위치와 실제 졸업생 입시 결과를 바탕으로 비교·분석한 참고용 자료입니다.",
        "본 결과는 진학 상담 지원을 위한 예측 자료로서 실제 전형 결과와 차이가 있을 수 있으며, 상담 자료로만 활용합니다.",
    ]
