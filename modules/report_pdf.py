from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

BASE_DIR   = Path(__file__).resolve().parent.parent
ASSET_DIR  = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 한국어 폰트 ──────────────────────────────────────────────────────────
_FONT_SETS = [
    (Path(r"C:\Windows\Fonts\malgun.ttf"),       Path(r"C:\Windows\Fonts\malgunbd.ttf")),
    (Path(r"C:\Windows\Fonts\NanumGothic.ttf"),  Path(r"C:\Windows\Fonts\NanumGothicBold.ttf")),
    (Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
     Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")),
]
_KO, _KO_B = "Helvetica", "Helvetica-Bold"
for _n, _b in _FONT_SETS:
    if _n.exists():
        try:
            pdfmetrics.registerFont(TTFont("KoFont",      str(_n)))
            pdfmetrics.registerFont(TTFont("KoFont-Bold", str(_b) if _b.exists() else str(_n)))
            registerFontFamily("KoFont", normal="KoFont", bold="KoFont-Bold",
                               italic="KoFont", boldItalic="KoFont-Bold")
            _KO, _KO_B = "KoFont", "KoFont-Bold"
        except Exception:
            pass
        break

# ── 색상 팔레트 ──────────────────────────────────────────────────────────
CN    = colors.HexColor("#1E3A8A")
CB    = colors.HexColor("#2563EB")
CBL   = colors.HexColor("#DBEAFE")
CBG   = colors.HexColor("#EFF6FF")
CPU   = colors.HexColor("#7C3AED")
CPUG  = colors.HexColor("#F5F3FF")
CG    = colors.HexColor("#059669")
CGG   = colors.HexColor("#ECFDF5")
CR    = colors.HexColor("#DC2626")
CRG   = colors.HexColor("#FEF2F2")
CA    = colors.HexColor("#D97706")
CAG   = colors.HexColor("#FFFBEB")
CS    = colors.HexColor("#64748B")
CBR   = colors.HexColor("#CBD5E1")
CBR2  = colors.HexColor("#E2E8F0")
CLG   = colors.HexColor("#F8FAFC")
CT    = colors.HexColor("#1E293B")
CGY   = colors.HexColor("#9CA3AF")
CW    = colors.white

# ── 내신 9등급 ↔ 5등급 변환 공용 데이터 ────────────────────────────────────
_CONV_G9_CUM  = [0, 4, 11, 23, 40, 60, 77, 89, 96, 100]
_CONV_G9_BAND = [4, 7, 12, 17, 20, 17, 12, 7, 4]
_CONV_G5_CUM  = [0, 10, 34, 66, 90, 100]
_CONV_G5_BAND = [10, 24, 32, 24, 10]

def grade9_to_pct(g9: float) -> float:
    """9등급제 값 → 누적 백분위 (선형 보간)"""
    g9 = max(1.0, min(9.0, g9))
    n = min(9, max(1, int(g9)))
    return _CONV_G9_CUM[n - 1] + (g9 - n) * _CONV_G9_BAND[n - 1]

def pct_to_grade5(pct: float) -> float:
    """누적 백분위 → 5등급제 값 (선형 보간)"""
    pct = max(0.0, min(100.0, pct))
    for i in range(5):
        if pct <= _CONV_G5_CUM[i + 1] or i == 4:
            w = _CONV_G5_BAND[i]
            return (i + 1) + (pct - _CONV_G5_CUM[i]) / w
    return 5.0

# 3과목(1/3) + 4과목(1/4) 평균으로 나올 수 있는 모든 등급값 49개
CONV_GRADE_VALS: list[float] = sorted(set(
    1.0 + k / 12.0 for k in range(97) if k % 3 == 0 or k % 4 == 0
))

def get_conv_table_data() -> list[tuple[float, float, float]]:
    """[(9등급값, 5등급값, 누적백분위), ...] 49개"""
    return [
        (g, pct_to_grade5(grade9_to_pct(g)), grade9_to_pct(g))
        for g in CONV_GRADE_VALS
    ]

# ── 페이지 치수 ──────────────────────────────────────────────────────────
_PW, _PH = A4
_LM = _RM = 36
_CW = _PW - _LM - _RM   # ≈ 523 pt

# ── 스타일 ───────────────────────────────────────────────────────────────
_S: dict[str, ParagraphStyle] = {}

def _init_styles() -> None:
    if _S:
        return
    defs = [
        ("doc_title",   _KO_B, 17, CN,   23, TA_CENTER),
        ("doc_sub",     _KO,    9, CS,   13, TA_CENTER),
        ("doc_date",    _KO,    8, CS,   12, TA_RIGHT),
        ("stu_lbl",     _KO,    8, CS,   12, TA_LEFT),
        ("stu_val",     _KO_B, 10, CN,   14, TA_LEFT),
        ("sec_hdr",     _KO_B, 11, CT,   16, TA_LEFT),
        ("c_lbl",       _KO,    7, CS,   10, TA_LEFT),
        ("c_val",       _KO_B, 13, CN,   17, TA_LEFT),
        ("c_val_g",     _KO_B, 13, CG,   17, TA_LEFT),
        ("c_val_r",     _KO_B, 13, CR,   17, TA_LEFT),
        ("c_val_p",     _KO_B, 13, CPU,  17, TA_LEFT),
        ("c_val_a",     _KO_B, 13, CA,   17, TA_LEFT),
        ("th",          _KO_B,  8, CT,   11, TA_LEFT),
        ("th_c",        _KO_B,  8, CT,   11, TA_CENTER),
        ("td",          _KO,    8, CT,   12, TA_LEFT),
        ("td_c",        _KO,    8, CT,   12, TA_CENTER),
        ("td_g",        _KO_B,  8, CG,   12, TA_CENTER),
        ("td_r",        _KO_B,  8, CR,   12, TA_CENTER),
        ("td_a",        _KO_B,  8, CA,   12, TA_CENTER),
        ("td_b",        _KO_B,  8, CB,   12, TA_CENTER),
        ("body",        _KO,    9, CT,   14, TA_LEFT),
        ("body_b",      _KO_B,  9, CT,   14, TA_LEFT),
        ("small",       _KO,    7, CGY,  11, TA_LEFT),
        ("box_g_h",     _KO_B,  9, CG,   13, TA_LEFT),
        ("box_r_h",     _KO_B,  9, CR,   13, TA_LEFT),
        ("box_b_h",     _KO_B,  9, CB,   13, TA_LEFT),
        ("ch_b",        _KO_B,  9, CB,   13, TA_LEFT),   # counsel header blue
        ("ch_p",        _KO_B,  9, CPU,  13, TA_LEFT),   # counsel header purple
        ("ch_a",        _KO_B,  9, CA,   13, TA_LEFT),   # counsel header amber
        ("ch_g",        _KO_B,  9, CG,   13, TA_LEFT),   # counsel header green
        ("ch_r",        _KO_B,  9, CR,   13, TA_LEFT),   # counsel header red
        ("ch_s",        _KO_B,  9, CS,   13, TA_LEFT),   # counsel header slate
        ("ct",          _KO,    8, CT,   13, TA_LEFT),   # counsel body text
    ]
    for name, fn, sz, col, ld, align in defs:
        _S[name] = ParagraphStyle(
            f"R_{name}", fontName=fn, fontSize=sz,
            textColor=col, leading=ld, alignment=align,
        )


def _p(text, style: str | ParagraphStyle = "td") -> Paragraph:
    _init_styles()
    st = _S.get(style, _S["td"]) if isinstance(style, str) else style
    return Paragraph(str(text) if text is not None else "-", st)


# ── 포매터 ───────────────────────────────────────────────────────────────
def _fmt_grade(v) -> str:
    if v is None:
        return "-"
    try:
        g = float(v)
        if g != g:
            return "-"
        return f"{g:.2f}".rstrip("0").rstrip(".") + "등급"
    except Exception:
        return str(v)


def _pct_to_grade9(pct: float) -> int:
    if pct >= 96: return 1
    if pct >= 89: return 2
    if pct >= 77: return 3
    if pct >= 60: return 4
    if pct >= 40: return 5
    if pct >= 23: return 6
    if pct >= 11: return 7
    if pct >= 4:  return 8
    return 9


def _fmt_pct(v) -> str:
    if v is None:
        return "-"
    try:
        p = float(v)
        if p != p:
            return "-"
        pi = int(round(p))
        return f"{pi} ({_pct_to_grade9(pi)}등급)"
    except Exception:
        return str(v)


def _g(v) -> str:
    """등급 숫자만 (소수점 제거)"""
    if v is None:
        return "-"
    try:
        g = float(v)
        if g != g:
            return "-"
        return f"{g:.1f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)


def _bold_passing(txt: str) -> str:
    """수시/정시 요약 텍스트에서 합격 항목만 <b> 볼드로 감싼다.
    형식: '대학-학과(결과)' — 마지막 괄호 안의 결과값만 판별."""
    import re
    if not txt or txt == "-":
        return txt
    result = []
    for part in txt.split(" / "):
        part = part.strip()
        m = re.search(r'\(([^)]*)\)\s*$', part)
        if m:
            result_val = m.group(1)
            if "합" in result_val and "불합" not in result_val:
                result.append(f"<b>{part}</b>")
            else:
                result.append(part)
        else:
            result.append(part)
    return " / ".join(result)


def _grade_pos(grade_val, pos_val) -> str:
    """등급 + 상위 약 X% — 한 줄 인라인 스타일 (작은 회색 글씨)"""
    if grade_val is None:
        return "-"
    try:
        g = float(grade_val)
        if g != g:
            return "-"
        g_str = f"{g:.2f}".rstrip("0").rstrip(".")
        if pos_val is not None:
            try:
                top_pct = round((1 - float(pos_val)) * 100)
                # 인라인 XML: 상위% 부분만 작고 연하게
                return (f'{g_str}등급 '
                        f'<font size="7" color="#9CA3AF">(상위 약 {top_pct}%)</font>')
            except Exception:
                pass
        return f"{g_str}등급"
    except Exception:
        return str(grade_val)


def _pct_short(v) -> str:
    """백분위 숫자만"""
    if v is None:
        return "-"
    try:
        p = float(v)
        if p != p:
            return "-"
        return str(int(round(p)))
    except Exception:
        return str(v)


# ── 공통 테이블 스타일 ────────────────────────────────────────────────────
def _tbl_style(header_bg=CBL) -> TableStyle:
    return TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.4, CBR2),
        ("BACKGROUND",    (0, 0), (-1,  0), header_bg),
        ("FONTNAME",      (0, 0), (-1,  0), _KO_B),
        ("FONTNAME",      (0, 1), (-1, -1), _KO),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ])


# ── 섹션 헤더 (왼쪽 컬러 바) ─────────────────────────────────────────────
def _sec(title: str, line_color=CB) -> list:
    """섹션 헤더: 왼쪽 컬러 세로 바 + 굵은 제목"""
    _init_styles()
    bar = Table(
        [["", _p(title, "sec_hdr")]],
        colWidths=[5, _CW - 5],
    )
    bar.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), line_color),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (0, 0),   0),
        ("RIGHTPADDING",  (0, 0), (0, 0),   0),
        ("LEFTPADDING",   (1, 0), (1, 0),   8),
        ("RIGHTPADDING",  (1, 0), (1, 0),   4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [bar]


# ── 성적 카드 (4칸 한 줄) ────────────────────────────────────────────────
_C4W = _CW / 4   # 각 카드 outer width

def _score_card(label: str, value: str, bg=CLG, val_style="c_val") -> Table:
    _init_styles()
    w = _C4W - 6
    # 고정 rowHeights → 4카드 항상 같은 높이 보장
    t = Table([[_p(label, "c_lbl")], [_p(value, val_style)]],
              colWidths=[w], rowHeights=[16, 28])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("BOX",           (0, 0), (-1, -1), 0.6, CBR),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
        ("TOPPADDING",    (0, 0), (0, 0),    5),
        ("BOTTOMPADDING", (0, 0), (0, 0),    2),
        ("TOPPADDING",    (0, 1), (0, 1),    4),
        ("BOTTOMPADDING", (0, 1), (0, 1),    4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _card_row4(cards: list) -> Table:
    while len(cards) < 4:
        cards.append(_score_card("", ""))
    t = Table([cards], colWidths=[_C4W] * 4)
    t.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


# ── 상담 포인트 2×2 (equal height) ──────────────────────────────────────
def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", str(s))


def _approx_h(paras: list, cell_w: float, base_pad: int = 28) -> float:
    """셀 높이 추정 (pt). base_pad = top+bottom padding."""
    total = base_pad
    for p in paras:
        txt = _strip_tags(str(p.text) if hasattr(p, "text") else str(p))
        # 8pt font → 약 5.5pt/글자
        cpl = max(1, int(cell_w / 5.5))
        lines = max(1, -(-len(txt) // cpl))   # ceil division
        leading = getattr(p.style, "leading", 13) if hasattr(p, "style") else 13
        total += lines * leading + 2
    return float(total)


def _build_counseling_section(cdata: dict) -> list:
    if not cdata:
        return []
    _init_styles()

    half = _CW / 2 - 3

    # ── 카드 내용 빌드 ─────────────────────────────────────────────────
    # Card 1: 성적 구조
    gs = cdata.get("grade_structure", {})
    gs_type = gs.get("type", "")
    c1_accent = CB if gs_type == "내신강세" else (CPU if gs_type == "모의강세" else CG)
    c1_bg     = CBG if gs_type == "내신강세" else (CPUG if gs_type == "모의강세" else CGG)
    c1_hdr    = "ch_b" if gs_type == "내신강세" else ("ch_p" if gs_type == "모의강세" else "ch_g")
    c1 = [_p("성적 구조", c1_hdr),
          _p(gs.get("message", "-"), "ct")]

    # Card 2: 과목 강약
    ss = cdata.get("subject_strength", {})
    c2 = [_p("과목 강약", "ch_p"),
          _p(f"내신 강점  {ss.get('grade_strong', '-')}", "ct"),
          _p(f"내신 주의  {ss.get('grade_weak',   '-')}", "ct"),
          _p(f"모의 강점  {ss.get('mock_strong',  '-')}", "ct"),
          _p(f"모의 주의  {ss.get('mock_weak',    '-')}", "ct")]

    # Card 3: 유사 졸업생 등록 패턴
    pp   = cdata.get("pass_pattern", {})
    tot  = pp.get("total", 0)
    byt  = pp.get("by_type", {})
    c3 = [_p("유사 졸업생 등록 패턴", "ch_a")]
    if byt:
        c3.append(_p(f"합격 {tot}건 확인", "ct"))
        for t, n in sorted(byt.items(), key=lambda x: x[1], reverse=True):
            c3.append(_p(f"{t}  {n}건", "ct"))
    else:
        c3.append(_p("유사 졸업생 합격 결과 데이터가 없습니다.", "ct"))

    # Card 4: 추세 해석
    tr = cdata.get("trend", {})
    gt = tr.get("grade_trend", "-")
    mt = tr.get("mock_trend",  "-")
    icons = {"상승": "▲", "하락": "▼", "유지": "→"}
    has_up   = "상승" in (gt, mt)
    has_down = "하락" in (gt, mt)
    c4_accent = CG if (has_up and not has_down) else (CR if has_down else CS)
    c4_hdr    = "ch_g" if (has_up and not has_down) else ("ch_r" if has_down else "ch_s")
    c4 = [_p("추세 해석", c4_hdr),
          _p(f"내신 {icons.get(gt,'?')} {tr.get('grade_label','-')}  {tr.get('grade_comment','-')}", "ct"),
          _p(f"모의 {icons.get(mt,'?')} {tr.get('mock_label', '-')}  {tr.get('mock_comment', '-')}", "ct")]

    # ── 높이 계산 (4개 모두 같은 높이) ────────────────────────────────
    cell_w = half - 24   # padding 차감
    h1 = _approx_h(c1, cell_w)
    h2 = _approx_h(c2, cell_w)
    h3 = _approx_h(c3, cell_w)
    h4 = _approx_h(c4, cell_w)
    max_h = max(h1, h2, h3, h4) + 4   # 약간의 여유

    # ── 2×2 그리드 ─────────────────────────────────────────────────────
    # 셀 내용을 직접 리스트로 넣어 배경이 전체 셀을 채우도록
    grid = Table(
        [[c1, c2],
         [c3, c4]],
        colWidths=[half + 3, half + 3],
        rowHeights=[max_h, max_h],
    )
    grid.setStyle(TableStyle([
        # 배경색 (셀별)
        ("BACKGROUND",    (0, 0), (0, 0), c1_bg),
        ("BACKGROUND",    (1, 0), (1, 0), CPUG),
        ("BACKGROUND",    (0, 1), (0, 1), CAG),
        ("BACKGROUND",    (1, 1), (1, 1), CGG if (has_up and not has_down) else (CRG if has_down else CLG)),
        # 왼쪽 두꺼운 선 (accent bar 효과)
        ("LINEBEFORE",    (0, 0), (0, 0), 5, c1_accent),
        ("LINEBEFORE",    (1, 0), (1, 0), 5, CPU),
        ("LINEBEFORE",    (0, 1), (0, 1), 5, CA),
        ("LINEBEFORE",    (1, 1), (1, 1), 5, c4_accent),
        # 외곽선
        ("BOX",           (0, 0), (0, 0), 0.5, CBR),
        ("BOX",           (1, 0), (1, 0), 0.5, CBR),
        ("BOX",           (0, 1), (0, 1), 0.5, CBR),
        ("BOX",           (1, 1), (1, 1), 0.5, CBR),
        # 패딩
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1),  8),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        # 컬럼 간격
        ("RIGHTPADDING",  (0, 0), (0, -1),  4),
    ]))

    return [KeepTogether([*_sec("상담 포인트", line_color=CB), Spacer(1, 4), grid]), Spacer(1, 6)]


# ── Context 빌더 ─────────────────────────────────────────────────────────
def build_report_context(
    student: dict,
    similar_cases: list[dict],
    fit_result: dict,
    strength: str,
    weakness: str,
    strategy: str,
    disclaimer_lines: list[str],
    pinned_entries: list[dict] | None = None,
    passing_susi: list[dict] | None = None,
    passing_jungsi: list[dict] | None = None,
    counseling_data: dict | None = None,
    grade_similar_cases: list[dict] | None = None,
    mock_similar_cases: list[dict] | None = None,
) -> dict:
    return {
        "student":              student,
        "similar_cases":        similar_cases,
        "grade_similar_cases":  grade_similar_cases or [],
        "mock_similar_cases":   mock_similar_cases  or [],
        "fit_scores":           fit_result.get("scores", []),
        "strength":             strength,
        "weakness":             weakness,
        "strategy":             strategy,
        "disclaimer_lines":     disclaimer_lines,
        "pinned_entries":       pinned_entries  or [],
        "passing_susi":         passing_susi   or [],
        "passing_jungsi":       passing_jungsi or [],
        "counseling_data":      counseling_data or {},
    }


def render_report_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(ASSET_DIR)))
    template = env.get_template("report_template.html")
    return template.render(**context)


# ── 합격 안정권 분석 섹션 ────────────────────────────────────────────────
def _build_passing_section(passing_susi: list[dict], passing_jungsi: list[dict]) -> list:
    if not passing_susi and not passing_jungsi:
        return []

    # 사례코드별 그룹핑
    case_map: dict[str, dict] = {}
    for r in passing_susi:
        code = str(r.get("사례코드") or "-")
        if code not in case_map:
            case_map[code] = {"cat": str(r.get("구분", "")),
                              "grades": r,   # 성적 정보 (merged)
                              "susi": [], "jungsi": []}
        case_map[code]["susi"].append(r)
    for r in passing_jungsi:
        code = str(r.get("사례코드") or "-")
        if code not in case_map:
            case_map[code] = {"cat": str(r.get("구분", "")),
                              "grades": r,
                              "susi": [], "jungsi": []}
        case_map[code]["jungsi"].append(r)

    # 안정권 → 적정권 → 참고 순서
    cat_order = {"안정권": 0, "적정권": 1, "참고": 2}
    sorted_codes = sorted(case_map,
                          key=lambda c: cat_order.get(case_map[c]["cat"], 9))

    # 카테고리별 그룹 분리: 안정권 / 적정권 / 참고
    CAT_LABEL = {"안정권": "안정권", "적정권": "적정권", "참고": "참고"}
    CAT_HDR_BG = {
        "안정권": colors.HexColor("#A7F3D0"),  # 연초록
        "적정권": colors.HexColor("#BFDBFE"),  # 연파랑
        "참고":   colors.HexColor("#E2E8F0"),  # 연회색
    }

    def _make_cat_table(codes_for_cat: list) -> Table | None:
        if not codes_for_cat:
            return None
        HDR = [
            _p("사례코드",           "th"),
            _p("전교과\n(등급)",     "th_c"),
            _p("국수영\n(등급)",     "th_c"),
            _p("모의종합\n(백분위)", "th_c"),
            _p("수시 합격",          "th"),
            _p("정시 합격",          "th"),
        ]
        rows = [HDR]
        bgs: list = []
        for i, code in enumerate(codes_for_cat):
            info  = case_map[code]
            grade = info["grades"]
            row_bg = CLG if i % 2 == 0 else CW
            susi_txt = "<br/>".join(
                f"{r.get('college','-')}" +
                (f" / {r.get('department','')}" if r.get('department') else "") +
                (f" [{r.get('admission_name','')}]" if r.get('admission_name') else "")
                for r in info["susi"]
            ) or "-"
            jungsi_txt = "<br/>".join(
                f"{r.get('college','-')}" +
                (f" / {r.get('department','')}" if r.get('department') else "") +
                (f" ({r.get('gun','')}군)" if r.get('gun') else "")
                for r in info["jungsi"]
            ) or "-"
            rows.append([
                _p(code,                                            "body_b"),
                _p(_g(grade.get("all_grade")),                     "td_c"),
                _p(_g(grade.get("ksy_grade")),                     "td_c"),
                _p(_pct_short(grade.get("mock_ks_percentile")),    "td_c"),
                _p(susi_txt,   "td"),
                _p(jungsi_txt, "td"),
            ])
            bgs.append(("BACKGROUND", (0, i+1), (-1, i+1), row_bg))
        rest = (_CW - 194) / 2
        tbl = Table(rows, colWidths=[50, 50, 50, 44, rest, rest])
        cat_hdr_bg = CAT_HDR_BG.get(case_map[codes_for_cat[0]]["cat"], colors.HexColor("#6EE7B7"))
        sty = _tbl_style(header_bg=cat_hdr_bg)
        for cmd in bgs:
            sty.add(*cmd)
        tbl.setStyle(sty)
        return tbl

    # 카테고리별 코드 묶음
    cat_groups: dict[str, list] = {}
    for code in sorted_codes:
        cat = case_map[code]["cat"]
        cat_groups.setdefault(cat, []).append(code)

    blocks: list = [*_sec("합격 안정권 분석", line_color=CG), Spacer(1, 4)]
    for cat in ["안정권", "적정권", "참고"]:
        codes_in_cat = cat_groups.get(cat, [])
        if not codes_in_cat:
            continue
        blocks.append(_p(f"▶ {CAT_LABEL[cat]}", "body_b"))
        blocks.append(Spacer(1, 3))
        tbl = _make_cat_table(codes_in_cat)
        if tbl:
            blocks.append(tbl)
        blocks.append(Spacer(1, 8))
    blocks.append(Spacer(1, 4))

    return blocks


# ── 대학역추적 섹션 ──────────────────────────────────────────────────────
def _build_pinned_section(pinned: list[dict]) -> list:
    if not pinned:
        return []

    blocks: list = [*_sec("대학/학과 역추적", line_color=CA), Spacer(1, 5)]
    HALF = _CW / 2

    for pe in pinned:
        pc = int(pe.get("pass_count", 0) or 0)
        fc = int(pe.get("fail_count", 0) or 0)

        # 대학명 / 모집단위 / 전형명 명시적 표시
        colleges_raw  = pe.get("colleges", [])
        dept_raw      = pe.get("department", "") or ""
        adm_name_raw  = pe.get("admission_name", "") or ""
        colleges_str  = " · ".join(str(c) for c in colleges_raw) if colleges_raw else (pe.get("title", "-") or "-")
        info_parts    = []
        if dept_raw:
            info_parts.append(f"모집단위: {dept_raw}")
        if adm_name_raw:
            info_parts.append(f"전형명: {adm_name_raw}")
        info_str = "  |  ".join(info_parts) if info_parts else ""

        pin_hdr = Table(
            [[_p(colleges_str, "body_b"),
              _p(f"합격 {pc}명  /  불합격 {fc}명  /  총 {pc+fc}명", "small")]],
            colWidths=[_CW * 0.62, _CW * 0.38],
        )
        pin_hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), CAG),
            ("BOX",           (0, 0), (-1, -1), 0.5, CBR),
            ("LEFTPADDING",   (0, 0), (-1, -1),  9),
            ("TOPPADDING",    (0, 0), (-1, -1),  6),
            ("BOTTOMPADDING", (0, 0), (-1, -1),  6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        # 모집단위·전형명 서브헤더 (있을 때만)
        if info_str:
            pin_sub = Table(
                [[_p(info_str, "small")]],
                colWidths=[_CW],
            )
            pin_sub.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("TOPPADDING",    (0, 0), (-1, -1),  3),
                ("BOTTOMPADDING", (0, 0), (-1, -1),  4),
                ("LINEBEFORE",    (0, 0), (0, 0),    3, CA),
                ("BOX",           (0, 0), (-1, -1),  0.5, CBR),
            ]))

        def _stat_rows(prefix: str, count: int) -> list:
            rows: list = []
            if count == 0:
                return [[_p("데이터 없음", "small")]]
            is_pass = prefix == "pass"
            for gk, glabel in [(f"{prefix}_all_grade", "전교과"),
                               (f"{prefix}_ksy_grade", "국수영")]:
                gs = pe.get(gk)
                if gs:
                    cut = gs["max"] if is_pass else gs["min"]
                    p70 = gs["p70"] if is_pass else gs["p30"]
                    rows.append([_p(f"{glabel}: 커트 {cut:.2f} / 70%선 {p70:.2f} / 평균 {gs['mean']:.2f}등급", "td")])
            for su, label in [(f"{prefix}_suneung_kor_percentile", "수능 국어"),
                              (f"{prefix}_suneung_math_percentile", "수능 수학")]:
                sv = pe.get(su)
                if sv:
                    if is_pass:
                        rows.append([_p(f"{label}: 하한 {sv['min']:.0f} ({_pct_to_grade9(sv['min'])}등급) / 평균 {sv['mean']:.0f}", "td")])
                    else:
                        rows.append([_p(f"{label}: 최고 {sv['max']:.0f} ({_pct_to_grade9(sv['max'])}등급) / 평균 {sv['mean']:.0f}", "td")])
            se = pe.get(f"{prefix}_suneung_eng_grade")
            if se:
                g_val = se["max"] if is_pass else se["min"]
                rows.append([_p(f"수능 영어: {'커트' if is_pass else '커트'} {int(round(g_val))}등급 / 평균 {se['mean']:.1f}등급", "td")])
            if not rows:
                rows.append([_p("데이터 없음", "small")])
            return rows

        def _stat_tbl(header: str, hdr_style: str, bg: colors.Color,
                      accent: colors.Color, data_rows: list) -> Table:
            all_rows = [[_p(header, hdr_style)]] + data_rows
            inner = Table(all_rows, colWidths=[HALF - 7])
            inner.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), bg),
                ("LEFTPADDING",   (0, 0), (-1, -1),  8),
                ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
                ("TOPPADDING",    (0, 0), (0, 0),    5),
                ("BOTTOMPADDING", (0, 0), (0, 0),    2),
                ("TOPPADDING",    (0, 1), (-1, -1),  3),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ]))
            wrap = Table([["", inner]], colWidths=[4, HALF - 7])
            wrap.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (0, 0), accent),
                ("BOX",           (0, 0), (-1, -1), 0.5, CBR),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING",   (0, 0), (0, 0),   0),
                ("RIGHTPADDING",  (0, 0), (0, 0),   0),
                ("LEFTPADDING",   (1, 0), (1, 0),   0),
                ("RIGHTPADDING",  (1, 0), (1, 0),   0),
            ]))
            return wrap

        side = Table(
            [[_stat_tbl("합격자 통계", "box_g_h", CGG, CG,  _stat_rows("pass", pc)),
              _stat_tbl("불합격자 통계", "box_r_h", CRG, CR, _stat_rows("fail", fc))]],
            colWidths=[HALF, HALF],
        )
        side.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (0, 0),   3),
            ("RIGHTPADDING",  (1, 0), (1, 0),   0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        hdr_items = [pin_hdr]
        if info_str:
            hdr_items += [pin_sub]
        hdr_items += [Spacer(1, 3), side, Spacer(1, 8)]
        blocks.append(KeepTogether(hdr_items))

    return blocks


# ── PDF 내보내기 ─────────────────────────────────────────────────────────
def export_pdf(context: dict, output_path: str | None = None) -> str:
    _init_styles()
    stu = context["student"]

    if output_path is None:
        mmdd  = datetime.now().strftime("%m%d")
        sid   = str(stu.get("student_id", "")).replace(".0", "").strip()
        name  = str(stu.get("name",       "")).strip()
        fname = f"{mmdd} {sid} {name}.pdf".strip()
        output_path = str(OUTPUT_DIR / fname)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=_LM, rightMargin=_RM,
        topMargin=24, bottomMargin=28,
    )
    story: list = []

    # ══════════════════════════════════════════════════
    # 헤더
    # ══════════════════════════════════════════════════
    today    = datetime.now().strftime("%Y년 %m월 %d일")
    sid_str  = str(stu.get("student_id", "")).replace(".0", "").strip() or "-"
    name_str = str(stu.get("name",       "")).strip() or "-"
    trk_str  = str(stu.get("track",      "")).strip() or "-"

    story.append(_p("세화고등학교  진학상담 분석 보고서", "doc_title"))
    story.append(Spacer(1, 3))
    story.append(_p("본 보고서는 졸업생 입시 데이터를 기반으로 한 상담 참고 자료입니다.", "doc_sub"))
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width=_CW, thickness=1.2, color=CB, spaceAfter=5))

    stu_tbl = Table(
        [[_p("학번", "stu_lbl"), _p(sid_str,  "stu_val"),
          _p("이름", "stu_lbl"), _p(name_str, "stu_val"),
          _p("계열", "stu_lbl"), _p(trk_str,  "stu_val"),
          _p(today,  "doc_date")]],
        colWidths=[26, 80, 26, 80, 26, 80, None],
    )
    stu_tbl.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1),  6),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  4),
        ("TOPPADDING",    (0, 0), (-1, -1),  4),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBEFORE",    (2, 0), (2, 0),    0.5, CBR),
        ("LINEBEFORE",    (4, 0), (4, 0),    0.5, CBR),
    ]))
    story.append(stu_tbl)
    story.append(HRFlowable(width=_CW, thickness=0.4, color=CBR, spaceAfter=8))

    # ══════════════════════════════════════════════════
    # 1. 현재 학생 요약 — 4카드 한 줄
    # ══════════════════════════════════════════════════
    story.extend(_sec("현재 학생 요약", line_color=CB))
    story.append(Spacer(1, 4))

    # 전교과 등급 (상위 약 X% 포함)
    g_all = _grade_pos(stu.get("overall_grade") or stu.get("all_grade"), stu.get("all_pos"))
    # 국수영 등급 (상위 약 X% 포함)
    g_ksy = _grade_pos(stu.get("ksy_grade"), stu.get("ksy_pos"))
    # 모의 국수영 원점수 (카드3: 등수 포함) + 카드4: 원점수+백분위만 (등수 제외)
    try:
        ks_score = stu.get("mock_ks_score")
        ks_rank  = stu.get("mock_ks_rank")
        ks_pct   = stu.get("mock_ks_percentile")
        # 카드3 값: 원점수 + 등수
        if ks_score is not None:
            _s = f"{int(round(float(ks_score)))}점"
            if ks_rank is not None:
                _s += f" ({int(round(float(ks_rank)))}등)"
            mock_score_str = _s
        else:
            mock_score_str = "-"
        # 카드4 값: 원점수 + 백분위 (등수 없음)
        if ks_pct is not None:
            pct_int = int(round(float(ks_pct)))
            top_pct = 100 - pct_int
            mock_pct_str = (f'{pct_int} '
                            f'<font size="7" color="#9CA3AF">(상위 약 {top_pct}%)</font>')
        else:
            mock_pct_str = "-"
    except Exception:
        mock_score_str = "-"
        mock_pct_str   = "-"

    story.append(KeepTogether([
        _card_row4([
            _score_card("전교과 (등급)",   g_all,          bg=CBG),
            _score_card("국수영 (등급)",   g_ksy,          bg=CBG),
            _score_card("모의 국수영\n(원점수)", mock_score_str, bg=CPUG, val_style="c_val_p"),
            _score_card("국수 백분위",    mock_pct_str,   bg=CPUG, val_style="c_val_p"),
        ]),
        Spacer(1, 10),
    ]))

    # ══════════════════════════════════════════════════
    # 2. 유사 사례 — 내신 유사도 순 / 모의 유사도 순
    # ══════════════════════════════════════════════════
    def _sim_table(cases: list, header_color) -> list:
        """유사사례 리스트 → ReportLab 요소 반환."""
        if not cases:
            return []
        rows = [[
            _p("사례코드",      "th"),
            _p("수시 결과 요약", "th"),
            _p("정시 결과 요약", "th"),
            _p("유사 선택 이유",  "th"),
        ]]
        alt: list = []
        for i, row in enumerate(cases[:8]):
            bg = CLG if i % 2 == 0 else CW
            rows.append([
                _p(str(row.get("case_code",         "-") or "-"), "td"),
                _p(_bold_passing(str(row.get("susi_summary",   "-") or "-")), "td"),
                _p(_bold_passing(str(row.get("jungsi_summary", "-") or "-")), "td"),
                _p(str(row.get("similarity_reason", "-") or "-"), "small"),
            ])
            alt.append(("BACKGROUND", (0, i+1), (-1, i+1), bg))
        rest3 = (_CW - 52) / 3
        tbl = Table(rows, colWidths=[52, rest3, rest3, rest3])
        sty = _tbl_style(header_bg=header_color)
        for cmd in alt:
            sty.add(*cmd)
        tbl.setStyle(sty)
        return [tbl, Spacer(1, 8)]

    grade_cases = context.get("grade_similar_cases", [])
    mock_cases  = context.get("mock_similar_cases",  [])
    # 구분 데이터가 없으면 기존 similar_cases 폴백
    if not grade_cases and not mock_cases:
        grade_cases = context.get("similar_cases", [])

    if grade_cases or mock_cases:
        story.extend(_sec("유사 사례", line_color=CB))
        story.append(Spacer(1, 4))
        if grade_cases:
            story.append(_p("▶ 내신 유사도 순", "body_b"))
            story.append(Spacer(1, 3))
            story.extend(_sim_table(grade_cases, colors.HexColor("#BFDBFE")))
        if mock_cases:
            story.append(_p("▶ 모의 유사도 순", "body_b"))
            story.append(Spacer(1, 3))
            story.extend(_sim_table(mock_cases, colors.HexColor("#DDD6FE")))
        story.append(Spacer(1, 4))

    # ══════════════════════════════════════════════════
    # 3. 합격 안정권 분석
    # ══════════════════════════════════════════════════
    story.extend(_build_passing_section(
        context.get("passing_susi",   []),
        context.get("passing_jungsi", []),
    ))

    # ══════════════════════════════════════════════════
    # 4. 대학/학과 역추적
    # ══════════════════════════════════════════════════
    story.extend(_build_pinned_section(context.get("pinned_entries", [])))

    # ══════════════════════════════════════════════════
    # 5. 상담 포인트 (2×2 equal height)
    # ══════════════════════════════════════════════════
    story.extend(_build_counseling_section(context.get("counseling_data", {})))

    # ══════════════════════════════════════════════════
    # 내신 9등급 → 5등급 변환 참고표 (학생 기준 16행, 2단)
    # ══════════════════════════════════════════════════
    _conv_all = get_conv_table_data()   # 49개 전체

    # 현재 학생 전교과 등급(5등급제) 기준 중심 행 찾기 — 5등급 컬럼 기준 탐색
    _stu_g5_raw = stu.get("overall_grade") or stu.get("all_grade")
    _conv_center = None
    if _stu_g5_raw is not None:
        try:
            _sg5 = float(_stu_g5_raw)
            if 1.0 <= _sg5 <= 5.5:
                _conv_center = min(
                    range(len(_conv_all)),
                    key=lambda i: abs(_conv_all[i][1] - _sg5)
                )
        except Exception:
            pass

    # 슬라이스: 학생 행 기준으로 위 최대 14행 + 학생 행 + 아래 1행 = 최대 16행
    if _conv_center is not None:
        _sl_start = max(0, _conv_center - 14)
        _sl_end   = min(len(_conv_all), _conv_center + 2)   # +2: 본인 + 1 아래
    else:
        _sl_start, _sl_end = 0, min(16, len(_conv_all))
    _conv_rows_data = _conv_all[_sl_start:_sl_end]
    # 슬라이스 내 하이라이트 인덱스 재계산
    _conv_highlight = (_conv_center - _sl_start) if _conv_center is not None else None

    # 2단 분할
    _half = (len(_conv_rows_data) + 1) // 2
    _left  = _conv_rows_data[:_half]
    _right = _conv_rows_data[_half:]

    _cw   = (_CW - 8) / 6
    _csep = 8

    def _conv_cell(txt: str) -> Paragraph:
        return _p(txt, "td_c")

    _CHDR = colors.HexColor("#BFDBFE")
    _CHLG = colors.HexColor("#FEF9C3")   # 학생 해당 행 (연노랑)

    _conv_rows = [[
        _p("9등급", "th_c"), _p("5등급", "th_c"), _p("누적 백분위", "th_c"),
        _p("", "th_c"),
        _p("9등급", "th_c"), _p("5등급", "th_c"), _p("누적 백분위", "th_c"),
    ]]
    _conv_cmds: list = [
        ("BACKGROUND", (0, 0), (2, 0), _CHDR),
        ("BACKGROUND", (4, 0), (6, 0), _CHDR),
        ("BACKGROUND", (3, 0), (3, -1), CW),
        ("GRID",       (3, 0), (3, -1), 0.4, CW),
        ("LINEBEFORE", (4, 0), (4, -1), 0.5, CBR),
    ]

    for _ri in range(_half):
        _row_idx = _ri + 1
        _g9l, _g5l, _pl = _left[_ri]
        _row_bg  = CLG if _ri % 2 == 0 else CW
        _left_bg = _CHLG if _conv_highlight == _ri else _row_bg

        if _ri < len(_right):
            _g9r, _g5r, _pr = _right[_ri]
            _right_idx = _half + _ri
            _right_bg  = _CHLG if _conv_highlight == _right_idx else _row_bg
            _r_cells = [
                _conv_cell(f"{_g9r:.2f}"),
                _conv_cell(f"{_g5r:.2f}"),
                _conv_cell(f"상위 {_pr:.1f}%"),
            ]
        else:
            _right_bg = _row_bg
            _r_cells = [_conv_cell(""), _conv_cell(""), _conv_cell("")]

        _conv_rows.append([
            _conv_cell(f"{_g9l:.2f}"),
            _conv_cell(f"{_g5l:.2f}"),
            _conv_cell(f"상위 {_pl:.1f}%"),
            _conv_cell(""),
            *_r_cells,
        ])
        _conv_cmds += [
            ("BACKGROUND", (0, _row_idx), (2, _row_idx), _left_bg),
            ("BACKGROUND", (4, _row_idx), (6, _row_idx), _right_bg),
        ]

    conv_tbl = Table(
        _conv_rows,
        colWidths=[_cw, _cw, _cw, _csep, _cw, _cw, _cw],
    )
    csty = TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.4, CBR2),
        ("FONTNAME",      (0, 0), (-1, -1), _KO),
        ("FONTNAME",      (0, 0), (-1,  0), _KO_B),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (3, 0), (3, -1),  0),
        ("RIGHTPADDING",  (3, 0), (3, -1),  0),
        ("TOPPADDING",    (3, 0), (3, -1),  0),
        ("BOTTOMPADDING", (3, 0), (3, -1),  0),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])
    for _cmd in _conv_cmds:
        csty.add(*_cmd)
    conv_tbl.setStyle(csty)

    story.append(HRFlowable(width=_CW, thickness=0.4, color=CBR, spaceAfter=4))
    story.extend(_sec("내신 9등급 / 5등급 변환 참고표", line_color=CS))
    story.append(Spacer(1, 3))
    story.append(_p(
        "* 5등급제 경계 (2028~): 1등급 상위 10% / 2등급 ~34% / 3등급 ~66% / 4등급 ~90%"
        "  |  9등급제 비율: 4-7-12-17-20-17-12-7-4%",
        "small"))
    story.append(Spacer(1, 3))
    story.append(conv_tbl)
    story.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════
    # 면책 조항
    # ══════════════════════════════════════════════════
    disc_lines = context.get("disclaimer_lines", [])
    if disc_lines:
        story.append(HRFlowable(width=_CW, thickness=0.4, color=CBR, spaceAfter=3))
        for line in disc_lines:
            story.append(_p(line, "small"))

    doc.build(story)
    return output_path
