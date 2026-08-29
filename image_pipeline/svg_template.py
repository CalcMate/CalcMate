# -*- coding: utf-8 -*-
"""
image_pipeline/svg_template.py — CalcMate 이미지 생산 표준 v1: SVG 템플릿 생성기

Topic DNA(주제별 색상/텍스트/오브젝트 배치)를 입력받아 SVG 문자열을 생성한다.
좌표계는 참조 패키지(calcmate_v1_reference/svg_templates/)에서 실측 검증된
1200x675(본문 16:9) / 1080x1080(썸네일 1:1) 그대로 유지한다.
Master 1920x1080 출력은 렌더 단계에서 벡터 1.6x 확대로 얻는다.

설계 원칙 (참조 README 이슈 #4/#5 반영):
  - 썸네일은 본문 좌표를 공유하지 않고 1:1 전용 좌표로 별도 설계.
  - 곡선형 오브젝트(트로피/금고 등)는 SVG에 좌표를 두지 않고
    합성 단계(compositor)에서 AI Asset PNG를 얹는다. 여기서는
    배치 좌표만 DNA.composite에 기록한다.
"""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys

# ── 폰트 탐지 ─────────────────────────────────────────────────────
_FONT_CACHE: str | None = None


def detect_korean_font() -> str:
    """SVG font-family에 쓸 CJK 폰트 패밀리 이름을 탐지한다 (캐시됨).

    - Windows: 시스템 폰트 디렉토리 기준 우선순위 (Noto Sans KR > Malgun Gothic > Gulim)
    - Linux/macOS: fc-list 로 설치된 CJK 폰트 이름 확인
      (참조 세션에서 "Noto Sans KR"로 넣었다가 실제 설치 이름이
       "Noto Sans CJK KR"이어서 한글이 □로 깨진 이력이 있음 — 이 함수로 방지)
    - 환경변수 CALCMATE_SVG_FONT 로 강제 지정 가능
    """
    global _FONT_CACHE
    if _FONT_CACHE:
        return _FONT_CACHE

    env = os.environ.get("CALCMATE_SVG_FONT")
    if env:
        _FONT_CACHE = env
        return env

    if sys.platform.startswith("win"):
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        if os.path.isdir(fonts_dir):
            listed = {f.lower() for f in os.listdir(fonts_dir)}
            for file_name, family in (
                ("notosanskr-vf.ttf", "Noto Sans KR"),
                ("notosanskr-regular.otf", "Noto Sans KR"),
                ("malgun.ttf", "Malgun Gothic"),
                ("gulim.ttc", "Gulim"),
            ):
                if file_name in listed:
                    _FONT_CACHE = family
                    return family
        _FONT_CACHE = "Malgun Gothic"
        return _FONT_CACHE

    if shutil.which("fc-list"):
        try:
            out = subprocess.run(
                ["fc-list", ":lang=ko", "family"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            for family in ("Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "Malgun Gothic"):
                if family.lower() in out.lower():
                    _FONT_CACHE = family
                    return family
        except Exception:
            pass

    _FONT_CACHE = "sans-serif"
    return _FONT_CACHE


def svg_font_family() -> str:
    """SVG font-family 속성 값 (예: \"'Noto Sans KR', sans-serif\")."""
    return f"'{detect_korean_font()}', sans-serif"


# ── Topic DNA 레지스트리 ───────────────────────────────────────────
# 참조 README "Topic DNA 확정값 (색상표)" 기반.
# `template`: "validated" = 본문/썸네일 템플릿 좌표가 실측 검증된 주제.
#              "pending"  = 색상 DNA만 확정, 템플릿 미제작 (v1 범위 외).
TOPIC_DNA: dict[str, dict] = {
    "yearend_tax": {
        "display": "연말정산",
        "character": "남성 직장인",
        "hero": "계산기+환급봉투",
        "primary": "#00A86B",
        "accent": "#FFD166",
        "bg": "#E6F7F1",
        "badge_text": "CalcMate 가이드",
        "title_lines": ["2026 연말정산", "최대 환급 완벽 가이드"],
        "subtitle": "놓치기 쉬운 공제 항목부터 절세 팁까지 한눈에!",
        "info_badges": [
            ("소득공제 항목", "맞춤 체크리스트"),
            ("환급금 계산", "모바일 간편 모의"),
        ],
        "calc_header": "환급 계산",
        "body_has_envelope": True,   # 봉투는 SVG 기하 오브젝트로 직접 그림
        "assets": {
            "character": "yearend_tax_character_male_normalized.png",
        },
        "composite": {
            # 본문(Master 1920x1080 좌표)
            "character": {"target_width": 700, "right_margin": 40, "bottom_margin": 40},
            # 썸네일(1080x1080 좌표)
            "thumb_character": {"target_width": 430, "right_margin": 40, "bottom_margin": 80},
        },
        "template": "validated",
    },
    "severance": {
        "display": "퇴직금",
        "character": "여성 직장인",
        "hero": "계산기+금고+AI트로피",
        "primary": "#1E56A0",
        "accent": "#FFD166",
        "bg": "#EAF0F8",
        "badge_text": "CalcMate 가이드",
        "title_lines": ["2026 퇴직금", "계산 완벽 가이드"],
        "subtitle": "내가 받을 퇴직금, 정확하게 계산해보세요!",
        "info_badges": [
            ("지급 조건", "자격 요건 체크"),
            ("퇴직금 계산", "모바일 간편 모의"),
        ],
        "calc_header": "퇴직금 계산",
        "body_has_envelope": False,  # 코드로 그렸던 트로피/금고는 제거됨 → AI Asset 사용
        "assets": {
            "character": {
                "file": "severance_character_female_normalized.png",
                # P1-2: 참조 세션 실측 검증값 등록 (docstring에만 있던 값을 DNA로 승격).
                # 퇴직금 여성 캐릭터는 손가락 주변 halo가 강해 임계값 90 / 침식 4회 /
                # 상반신 크롭 0.55가 필요했다.
                "normalize": {
                    "alpha_threshold": 90,
                    "erosion_iterations": 4,
                    "crop_upper_body_ratio": 0.55,
                },
            },
            "hero": {
                "file": "severance_trophy_normalized.png",
            },
        },
        "composite": {
            "character": {"target_width": 620, "right_margin": 40, "bottom_margin": 40},
            "hero": {"target_width": 230, "x": 1190, "y": 250},
            "thumb_character": {"target_width": 430, "right_margin": 40, "bottom_margin": 80},
            "thumb_hero": {"target_width": 170, "x": 600, "y": 250},
        },
        "template": "validated",
    },
    # ── 색상 DNA만 확정된 주제 (템플릿 미제작) ──────────────────────────
    "weekly_holiday": {
        "display": "주휴수당",
        "character": "직장인",
        "hero": "달력+시계",
        "primary": "#008080",
        "accent": "#FF6B6B",
        "bg": "#E0F4F4",
        "template": "pending",
    },
    "unemployment_benefit": {
        "display": "실업급여",
        "character": "직장인",
        "hero": "서류+돈봉투",
        "primary": "#5E6AD2",
        "accent": "#FF6F61",
        "bg": "#EDEFFB",
        "template": "pending",
    },
    "annual_leave": {
        "display": "연차수당",
        "character": "직장인",
        "hero": "달력+휴가아이콘",
        "primary": "#F59E0B",
        "accent": "#2ECC71",
        "bg": "#FEF3E2",
        "template": "pending",
    },
}


# ── Asset 정규화 파라미터 (P1-2: Global Default → Topic Override) ──────
# 참조 세션에서 실측 검증된 기본값. 주제별 override는
# TOPIC_DNA[.assets.<kind>.normalize]에 등록한다.
ASSET_NORMALIZE_DEFAULTS: dict[str, dict] = {
    "character": {
        "canvas_size": 800,          # Character Asset Standard v1 (규격 임의 변경 금지)
        "height_ratio": 0.75,        # 캐릭터 높이 70~80%
        "bottom_margin": 20,
        "alpha_threshold": 40,       # halo 임계값 (기본)
        "erosion_iterations": 2,     # halo 침식 횟수 (기본)
        "crop_upper_body_ratio": None,  # 전신 대응 상반신 크롭 (주제별 override)
    },
    "hero": {
        "canvas_size": 500,
        "height_ratio": 0.75,
        "alpha_threshold": 40,
        "erosion_iterations": 2,
    },
}


def get_asset_file(dna: dict, asset_kind: str) -> str | None:
    """assets.<kind> 값이 문자열(구버전) 또는 {file, normalize} 딕셔너리(신규)인
    경우를 모두 처리한다."""
    v = dna.get("assets", {}).get(asset_kind)
    if isinstance(v, dict):
        return v.get("file")
    return v


def resolve_asset_normalize_params(dna: dict, asset_kind: str) -> dict:
    """Global Default → Topic Override 순서로 병합한 정규화 파라미터를 반환한다.

    주제별 값이 없으면 기본값(ASSET_NORMALIZE_DEFAULTS)을 그대로 사용하고,
    있으면 해당 값으로 override한다.
    """
    params = dict(ASSET_NORMALIZE_DEFAULTS.get(asset_kind, {}))
    v = dna.get("assets", {}).get(asset_kind)
    if isinstance(v, dict):
        params.update(v.get("normalize") or {})
    return params


def require_template(key: str) -> dict:
    """템플릿이 실측 검증된 주제만 통과시킨다."""
    dna = TOPIC_DNA.get(key)
    if not dna:
        raise KeyError(f"알 수 없는 주제 키: {key} (사용 가능: {sorted(TOPIC_DNA)})")
    if dna.get("template") != "validated":
        raise ValueError(
            f"[{key}] {dna['display']}는 색상 DNA만 확정된 주제입니다. "
            "템플릿 좌표 확정 전까지 본문/썸네일 생성을 지원하지 않습니다."
        )
    return dna


# ── SVG 빌더 ──────────────────────────────────────────────────────
_OUTLINE = "#0A1128"


def _decorations_body() -> str:
    """본문 배경 장식(원 3개 + 별 2개) — 참조 검증 좌표."""
    return (
        f'<circle cx="100" cy="120" r="16" fill="#FFD166" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<circle cx="1100" cy="100" r="24" fill="#FFD166" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<circle cx="1130" cy="550" r="18" fill="#FFD166" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<path d="M 1050 180 L 1055 195 L 1070 200 L 1055 205 L 1050 220 L 1045 205 L 1030 200 L 1045 195 Z" '
        f'fill="#FFFFFF" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<path d="M 180 500 L 184 512 L 196 516 L 184 520 L 180 532 L 176 520 L 164 516 L 176 512 Z" '
        f'fill="#FFFFFF" stroke="{_OUTLINE}" stroke-width="2"/>'
    )


def _decorations_thumb() -> str:
    """썸네일 배경 장식 — 참조 검증 좌표."""
    return (
        f'<circle cx="90" cy="100" r="14" fill="#FFD166" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<circle cx="990" cy="90" r="20" fill="#FFD166" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<path d="M 950 160 L 954 172 L 966 176 L 954 180 L 950 192 L 946 180 L 934 176 L 946 172 Z" '
        f'fill="#FFFFFF" stroke="{_OUTLINE}" stroke-width="2"/>'
    )


def _badge_svg(dna: dict, x: int, y: int, w: int, h: int, font_size: int, cx: int, cy: int) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{dna["primary"]}" '
        f'stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<text x="{cx}" y="{cy}" font-family="{svg_font_family()}" font-size="{font_size}" '
        f'font-weight="bold" fill="#FFFFFF" text-anchor="middle">{html.escape(dna["badge_text"])}</text>'
    )


def _title_block_svg(dna: dict, x: int, title_sizes: list[int], y_positions: list[int],
                     subtitle: tuple[str, ...], sub_font: int, sub_y: int, bar: tuple[int, int, int, int]) -> str:
    """제목/부제/액센트 바 블록. y_positions는 각 title_line의 baseline."""
    parts = []
    bx, by, bw, bh = bar
    parts.append(
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{dna["accent"]}" rx="4"/>'
    )
    for line, size, y in zip(dna["title_lines"], title_sizes, y_positions):
        parts.append(
            f'<text x="{x}" y="{y}" font-family="{svg_font_family()}" font-size="{size}" '
            f'font-weight="900" fill="{_OUTLINE}">{html.escape(line)}</text>'
        )
    for i, line in enumerate(subtitle):
        parts.append(
            f'<text x="{x}" y="{sub_y + i * (sub_font + 10)}" font-family="{svg_font_family()}" '
            f'font-size="{sub_font}" font-weight="600" fill="#4A5568">{html.escape(line)}</text>'
        )
    return "".join(parts)


def _info_badge_svg(dna: dict, label: str, value: str, x: int, y: int, w: int, h: int,
                    label_size: int, value_size: int) -> str:
    """정보 배지 1개 (흰 카드 + 라벨/값)."""
    cx = x + w // 2
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#FFFFFF" '
        f'stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<text x="{cx}" y="{y + 26}" font-family="{svg_font_family()}" font-size="{label_size}" '
        f'fill="#718096" text-anchor="middle">{html.escape(label)}</text>'
        f'<text x="{cx}" y="{y + 48}" font-family="{svg_font_family()}" font-size="{value_size}" '
        f'font-weight="bold" fill="{dna["primary"]}" text-anchor="middle">{html.escape(value)}</text>'
    )


def _info_badges_svg(dna: dict, x: int, y: int, w: int, h: int, gap: int,
                     label_size: int, value_size: int) -> str:
    """정보 배지 2개 나란히 (본문용)."""
    return "".join(
        _info_badge_svg(dna, label, value, x + i * (w + gap), y, w, h, label_size, value_size)
        for i, (label, value) in enumerate(dna["info_badges"])
    )


def _calc_card_svg(dna: dict, extra: str = "", header_font: int = 26) -> str:
    """계산기 카드(흰 패널 + 버튼 9개). extra로 주제별 기하 오브젝트 삽입."""
    bg = dna["bg"]
    primary = dna["primary"]
    accent = dna["accent"]
    buttons = (
        f'<rect x="20" y="105" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="100" y="105" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="180" y="105" width="60" height="45" rx="6" fill="{primary}" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="20" y="165" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="100" y="165" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="180" y="165" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="20" y="225" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="100" y="225" width="60" height="45" rx="6" fill="#F0F4F8" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<rect x="180" y="225" width="60" height="45" rx="6" fill="{accent}" stroke="{_OUTLINE}" stroke-width="2"/>'
    )
    return (
        f'<rect x="15" y="15" width="260" height="340" rx="16" fill="{_OUTLINE}" opacity="0.1"/>'
        f'<rect x="0" y="0" width="260" height="340" rx="16" fill="#FFFFFF" stroke="{_OUTLINE}" stroke-width="3"/>'
        f'<rect x="20" y="20" width="220" height="65" rx="8" fill="{bg}" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<text x="220" y="62" font-family="{svg_font_family()}" font-size="{header_font}" font-weight="bold" '
        f'fill="{primary}" text-anchor="end">{html.escape(dna["calc_header"])}</text>'
        f'{buttons}'
        f'{extra}'
    )


def _refund_envelope_svg(primary: str, accent: str, w: int = 130, h: int = 86,
                         fold_y: int = 46, coin_cy: int = 50, coin_r: int = 16,
                         text_size: int = 14) -> str:
    """환급 봉투 (SVG 기하 오브젝트). 기본값은 참조 검증 좌표(130x86) 그대로.

    fold_y/coin_cy/coin_r/text_size는 썸네일(200x130)에서 참조 좌표와
    일치하도록 호출부에서 명시한다.
    """
    cx = w // 2
    return (
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" fill="{accent}" stroke="{_OUTLINE}" stroke-width="3"/>'
        f'<path d="M 0 0 L {cx} {fold_y} L {w} 0" fill="none" stroke="{_OUTLINE}" stroke-width="2.5"/>'
        f'<circle cx="{cx}" cy="{coin_cy}" r="{coin_r}" fill="{primary}" stroke="{_OUTLINE}" stroke-width="2"/>'
        f'<text x="{cx}" y="{coin_cy + 6}" font-family="{svg_font_family()}" font-size="{text_size}" '
        f'font-weight="bold" fill="#FFFFFF" text-anchor="middle">\u20a9</text>'
    )


# ── 본문(16:9) ────────────────────────────────────────────────────
def build_body_svg(key: str) -> str:
    """본문 템플릿 SVG 문자열 (1200x675 viewBox)."""
    dna = require_template(key)
    extra = ""
    if dna.get("body_has_envelope"):
        extra = (
            '<g transform="translate(150, 92)">'
            + _refund_envelope_svg(dna["primary"], dna["accent"])
            + "</g>"
        )

    # 좌측 정보 블록 (제목/부제/정보배지) + 우측 계산기 카드
    title = _title_block_svg(
        dna, x=120,
        title_sizes=[52, 52], y_positions=[240, 308],
        subtitle=(dna["subtitle"],), sub_font=22, sub_y=375,
        bar=(120, 270, 220, 45),
    )
    badges = _info_badges_svg(dna, x=120, y=420, w=170, h=60, gap=15,
                              label_size=14, value_size=18)
    card = _calc_card_svg(dna, extra=extra)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" width="1200" height="675">'
        f'<rect width="1200" height="675" fill="{dna["bg"]}"/>'
        f'{_decorations_body()}'
        f'{_badge_svg(dna, 120, 140, 160, 40, 18, 200, 166)}'
        f'{title}'
        f'{badges}'
        f'<g transform="translate(680, 180)">{card}</g>'
        f"</svg>"
    )


# ── 썸네일(1:1) ───────────────────────────────────────────────────
def build_thumb_svg(key: str) -> str:
    """썸네일 전용 템플릿 SVG 문자열 (1080x1080 viewBox).

    본문(16:9)과 좌표를 공유하지 않는다 (참조 README 이슈 #4).
    HeroObject-캐릭터가 서로 멀어져 "가리키는" 연출이 깨지는 문제를
    방지하기 위해 1:1 전용 배치를 쓴다.
    """
    dna = require_template(key)

    # 제목 블록 (본문보다 세로로 긴 1:1 레이아웃)
    title = (
        f'<rect x="70" y="195" width="220" height="42" fill="{dna["accent"]}" rx="4"/>'
        f'<text x="70" y="172" font-family="{svg_font_family()}" font-size="46" font-weight="900" '
        f'fill="{_OUTLINE}">{html.escape(dna["title_lines"][0])}</text>'
        f'<text x="70" y="228" font-family="{svg_font_family()}" font-size="46" font-weight="900" '
        f'fill="{_OUTLINE}">{html.escape(dna["title_lines"][1])}</text>'
    )
    # 추가 제목 줄 (2줄 이상인 주제용 — 예: "최대 환급 가이드")
    if len(dna["title_lines"]) >= 3:
        title += (
            f'<text x="70" y="284" font-family="{svg_font_family()}" font-size="40" font-weight="900" '
            f'fill="{_OUTLINE}">{html.escape(dna["title_lines"][2])}</text>'
        )

    # 부제 (1~2줄)
    sub_lines = [dna["subtitle"]]
    if len(dna["subtitle"]) > 24 and len(dna["title_lines"]) < 3:
        mid = len(dna["subtitle"]) // 2
        cut = dna["subtitle"].rfind(" ", 0, mid)
        if cut > 8:
            sub_lines = [dna["subtitle"][:cut], dna["subtitle"][cut + 1:]]
    subtitle = "".join(
        f'<text x="70" y="{340 + i * 34}" font-family="{svg_font_family()}" font-size="24" '
        f'font-weight="600" fill="#4A5568">{html.escape(line)}</text>'
        for i, line in enumerate(sub_lines[:2])
    )

    badge_y = 430 + max(0, len(sub_lines) - 1) * 20
    badges = (
        _info_badge_svg(dna, dna["info_badges"][0][0], dna["info_badges"][0][1],
                        70, badge_y, 230, 70, 16, 20)
        + _info_badge_svg(dna, dna["info_badges"][1][0], dna["info_badges"][1][1],
                          70, badge_y + 90, 230, 70, 16, 20)
    )

    # 계산기 카드 (1:1 전용: 스케일 축소 + 봉투/체크 장식)
    extra = ""
    if dna.get("body_has_envelope"):
        extra = (
            '<g transform="translate(-50, 140) rotate(-8)">'
            + _refund_envelope_svg(dna["primary"], dna["accent"], w=200, h=130,
                                   fold_y=70, coin_cy=75, coin_r=22, text_size=18)
            + "</g>"
            '<g transform="translate(210, -15)">'
            f'<circle cx="25" cy="25" r="28" fill="#2ECC71" stroke="{_OUTLINE}" stroke-width="3"/>'
            f'<path d="M 14 25 L 22 33 L 36 17" fill="none" stroke="#FFFFFF" stroke-width="4" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            "</g>"
        )
    card = _calc_card_svg(dna, extra=extra)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="1080" height="1080">'
        f'<rect width="1080" height="1080" fill="{dna["bg"]}"/>'
        f'{_decorations_thumb()}'
        f'{_badge_svg(dna, 70, 70, 150, 38, 17, 145, 94)}'
        f'{title}'
        f'{subtitle}'
        f'{badges}'
        f'<g transform="translate(560, 430) scale(0.62)">{card}</g>'
        f'<rect x="830" y="1010" width="180" height="46" rx="23" fill="{_OUTLINE}"/>'
        f'<text x="920" y="1039" font-family="{svg_font_family()}" font-size="20" font-weight="bold" '
        f'fill="#FFFFFF" text-anchor="middle">CALCMATE</text>'
        f"</svg>"
    )
