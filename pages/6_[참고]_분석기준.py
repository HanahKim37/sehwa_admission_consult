import streamlit as st
from modules.auth import require_login, render_logout_button

require_login()
render_logout_button()

st.title("📋 [참고] 분석 기준")

st.markdown("""
<div style="padding:14px 18px;border-radius:12px;background:#EFF6FF;border:1px solid #BFDBFE;margin-bottom:24px;">
    <div style="font-weight:700;color:#1D4ED8;margin-bottom:4px;">핵심 원칙</div>
    <div style="color:#1E3A8A;line-height:1.7;">
        9등급제와 5등급제를 <b>단순 숫자 대응으로 비교하지 않습니다.</b><br>
        비교의 기준은 <b>학교 내부 상대 위치(석차/총원)</b>와 <b>실제 졸업생 입시 결과</b>입니다.<br>
        본교는 상위권 학생 밀집도가 높으므로 외부 기준표가 아닌 <b>교내 위치</b>를 우선합니다.
    </div>
</div>
""", unsafe_allow_html=True)

# ── 내신 유사도 ────────────────────────────────────────────
st.markdown("### 📌 내신 유사도")
st.markdown("""
<div style="padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:8px;">
    <div style="font-size:0.85rem;color:#6B7280;margin-bottom:12px;">
        등급 숫자 직접 비교 없음 — 모든 항목은 <b>석차 ÷ 총원</b> 기반 상대위치(0~1)로 변환 후 비교
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:0.93rem;">
        <thead>
            <tr style="background:#F9FAFB;border-bottom:2px solid #E5E7EB;">
                <th style="padding:8px 12px;text-align:left;color:#374151;">항목</th>
                <th style="padding:8px 12px;text-align:center;color:#374151;">가중치</th>
                <th style="padding:8px 12px;text-align:left;color:#374151;">비고</th>
            </tr>
        </thead>
        <tbody>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">전교과 위치</td>
                <td style="padding:8px 12px;text-align:center;"><b>28%</b></td>
                <td style="padding:8px 12px;color:#6B7280;">가장 포괄적인 내신 지표</td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;background:#FAFAFA;">
                <td style="padding:8px 12px;">국수영 위치</td>
                <td style="padding:8px 12px;text-align:center;"><b>22%</b></td>
                <td style="padding:8px 12px;color:#6B7280;">핵심 과목군 경쟁력</td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">국어 위치</td>
                <td style="padding:8px 12px;text-align:center;">12%</td>
                <td style="padding:8px 12px;color:#6B7280;"></td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;background:#FAFAFA;">
                <td style="padding:8px 12px;">수학 위치</td>
                <td style="padding:8px 12px;text-align:center;">12%</td>
                <td style="padding:8px 12px;color:#6B7280;"></td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">영어 위치</td>
                <td style="padding:8px 12px;text-align:center;">10%</td>
                <td style="padding:8px 12px;color:#6B7280;"></td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;background:#FAFAFA;">
                <td style="padding:8px 12px;">사회 계열 위치</td>
                <td style="padding:8px 12px;text-align:center;">8%</td>
                <td style="padding:8px 12px;color:#6B7280;">데이터 없으면 자동 제외 후 재정규화</td>
            </tr>
            <tr>
                <td style="padding:8px 12px;">과학 계열 위치</td>
                <td style="padding:8px 12px;text-align:center;">8%</td>
                <td style="padding:8px 12px;color:#6B7280;">데이터 없으면 자동 제외 후 재정규화</td>
            </tr>
        </tbody>
    </table>
    <div style="margin-top:10px;font-size:0.83rem;color:#9CA3AF;">추세 보너스: 상승 +3점 / 유지 +1점 (유사도 내 소폭 반영)</div>
</div>
""", unsafe_allow_html=True)

# ── 모의고사 유사도 ────────────────────────────────────────
st.markdown("### 📌 모의고사 유사도")
st.markdown("""
<div style="padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:8px;">
    <div style="font-size:0.85rem;color:#6B7280;margin-bottom:12px;">
        9등급제 그대로 사용 — 백분위 및 등급 직접 비교
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:0.93rem;">
        <thead>
            <tr style="background:#F9FAFB;border-bottom:2px solid #E5E7EB;">
                <th style="padding:8px 12px;text-align:left;color:#374151;">항목</th>
                <th style="padding:8px 12px;text-align:center;color:#374151;">가중치</th>
            </tr>
        </thead>
        <tbody>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">국수 종합지표 (백분위)</td>
                <td style="padding:8px 12px;text-align:center;"><b>28%</b></td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;background:#FAFAFA;">
                <td style="padding:8px 12px;">수학 백분위</td>
                <td style="padding:8px 12px;text-align:center;"><b>24%</b></td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">국어 백분위</td>
                <td style="padding:8px 12px;text-align:center;">20%</td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;background:#FAFAFA;">
                <td style="padding:8px 12px;">영어 등급</td>
                <td style="padding:8px 12px;text-align:center;">12%</td>
            </tr>
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px 12px;">사회 등급</td>
                <td style="padding:8px 12px;text-align:center;">8%</td>
            </tr>
            <tr>
                <td style="padding:8px 12px;">과학 등급</td>
                <td style="padding:8px 12px;text-align:center;">8%</td>
            </tr>
        </tbody>
    </table>
    <div style="margin-top:10px;font-size:0.83rem;color:#9CA3AF;">추세 보너스: 상승 +3점 / 유지 +1점</div>
</div>
""", unsafe_allow_html=True)

# ── 통합 유사도 ────────────────────────────────────────────
st.markdown("### 📌 통합 유사도")
st.markdown("""
<div style="padding:16px 20px;border-radius:12px;background:#F0FDF4;border:1px solid #BBF7D0;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:8px;">
    <div style="font-size:1.1rem;font-weight:700;color:#166534;text-align:center;padding:8px 0;">
        통합 유사도 = 내신 유사도 × 0.50 &nbsp;+&nbsp; 모의 유사도 × 0.50
    </div>
    <div style="font-size:0.85rem;color:#4B5563;text-align:center;margin-top:6px;">
        유사 졸업생 상위 10명 추출 기준 — 비교 근거가 없는 경우 후순위로 자동 이동
    </div>
</div>
""", unsafe_allow_html=True)

# ── 전형 적합도 ────────────────────────────────────────────
st.markdown("### 📌 전형 적합도")

cols = st.columns(2)

with cols[0]:
    st.markdown("""
<div style="padding:16px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:12px;height:100%;">
    <div style="font-weight:700;font-size:0.97rem;margin-bottom:8px;color:#1D4ED8;">📚 교과형</div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.7;">
        기준: 전교과·국수영 교내 상대 위치<br>
        추세 보너스: <span style="color:#DC2626;font-weight:600;">없음</span><br>
        <span style="color:#6B7280;font-size:0.82rem;">누적 내신 성적 기준 → 추세 무관</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="padding:16px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:12px;">
    <div style="font-weight:700;font-size:0.97rem;margin-bottom:8px;color:#7C3AED;">✏️ 논술형</div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.7;">
        기준: 모의 국어·수학 백분위 중심<br>
        영어: 최저 대응 가능성 보조 지표<br>
        추세 보너스: <span style="color:#DC2626;font-weight:600;">없음</span><br>
        <span style="color:#6B7280;font-size:0.82rem;">논술 시험 실력 기준 → 추세 무관</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="padding:16px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:12px;">
    <div style="font-weight:700;font-size:0.97rem;margin-bottom:8px;color:#B45309;">🛡️ 최저 대응력</div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.7;">
        기준: 영어 등급(65%) + 국수 종합지표(20%)<br>
        추세 보너스: <span style="color:#DC2626;font-weight:600;">없음</span>
    </div>
</div>
""", unsafe_allow_html=True)

with cols[1]:
    st.markdown("""
<div style="padding:16px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:12px;">
    <div style="font-weight:700;font-size:0.97rem;margin-bottom:8px;color:#059669;">🗂️ 종합형</div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.7;">
        기준: 전과목 구조 + 국어·수학 위치<br>
        추세 보너스: <span style="color:#059669;font-weight:600;">상승 +4 / 유지 +2</span><br>
        <span style="color:#6B7280;font-size:0.82rem;">성장 흐름이 실제 평가 요소</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="padding:16px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:12px;">
    <div style="font-weight:700;font-size:0.97rem;margin-bottom:8px;color:#DC2626;">📊 정시형</div>
    <div style="font-size:0.88rem;color:#374151;line-height:1.7;">
        기준: 모의 국수 종합지표(55%) + 수학(20%)<br>
        영어: 보조 지표(10%)<br>
        추세 보너스: <span style="color:#DC2626;font-weight:600;">없음</span><br>
        <span style="color:#6B7280;font-size:0.82rem;">수능 당일 점수 기준 → 추세 무관</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Evidence Bonus ─────────────────────────────────────────
st.markdown("### 📌 실적 반영 보너스 (Evidence Bonus)")
st.markdown("""
<div style="padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #E5E7EB;box-shadow:0 1px 4px rgba(0,0,0,0.05);margin-bottom:8px;">
    <div style="font-size:0.88rem;color:#374151;line-height:1.9;">
        유사 졸업생들의 <b>실제 합격·등록 결과</b>를 전형 적합도에 반영합니다.<br>
        <span style="display:inline-block;margin-top:4px;padding:3px 10px;border-radius:6px;background:#FEF3C7;color:#92400E;font-size:0.83rem;">표본 3건 미만</span> → 반영 제외 (0점)<br>
        <span style="display:inline-block;margin-top:4px;padding:3px 10px;border-radius:6px;background:#D1FAE5;color:#065F46;font-size:0.83rem;">표본 3건 이상</span> → 합격비율 × 최대 15점
    </div>
</div>
""", unsafe_allow_html=True)

# ── 하단 주의 문구 ─────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="padding:14px 18px;border-radius:10px;background:#F9FAFB;border:1px solid #E5E7EB;font-size:0.83rem;color:#6B7280;line-height:1.8;">
    ⚠️ 본 분석 기준은 외부 입시표나 전국 평균이 아닌 <b>본교 졸업생 데이터 기반</b>입니다.<br>
    ⚠️ 결과는 진학 상담을 위한 <b>참고용 예측 자료</b>이며 실제 전형 결과와 차이가 있을 수 있습니다.
</div>
""", unsafe_allow_html=True)
