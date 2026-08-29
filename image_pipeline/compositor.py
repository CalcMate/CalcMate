# -*- coding: utf-8 -*-
"""
image_pipeline/compositor.py — SVG 렌더링 + Asset 합성 + 다운사이징 + QA

렌더러 정책:
  - 프로덕션(리눅스 서버): cairosvg (참조 세션과 동일).
  - 로컬(Windows 등 cairo DLL이 없는 환경): resvg-py 폴백.
    두 렌더러 모두 QA에서 한글 글리프 렌더 여부를 검증한다.

출력 규칙:
  - Master(1920x1080) 우선 생성 → Body(800x450)/Thumbnail(512x512)는
    LANCZOS 다운사이징. 작은 해상도를 먼저 만들고 확대하지 않는다.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from . import svg_template

MASTER_W, MASTER_H = 1920, 1080
BODY_W, BODY_H = 800, 450
THUMB_W, THUMB_H = 512, 512


# ── SVG → 이미지 렌더링 ───────────────────────────────────────────
def render_svg(svg_str: str, width: int, height: int) -> Image.Image:
    """SVG 문자열을 RGBA 이미지로 렌더링한다.

    cairosvg 우선, OSError(cairo 라이브러리 없음) 발생 시 resvg-py로 폴백.
    """
    try:
        import cairosvg
        png = cairosvg.svg2png(
            bytestring=svg_str.encode("utf-8"),
            output_width=width, output_height=height,
        )
        return Image.open(__import__("io").BytesIO(png)).convert("RGBA")
    except OSError:
        return _render_svg_resvg(svg_str, width, height)


def _render_svg_resvg(svg_str: str, width: int, height: int) -> Image.Image:
    """resvg-py 폴백 렌더러 (Windows 등 cairo DLL 미설치 환경)."""
    try:
        import io
        import resvg_py
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "SVG 렌더러 미설치: `pip install cairosvg`(리눅스) 또는 "
            "`pip install resvg-py`(로컬 Windows) 필요."
        ) from e
    family = svg_template.detect_korean_font()
    png = resvg_py.svg_to_bytes(
        svg_str, width=width, height=height, font_family=family,
    )
    return Image.open(io.BytesIO(png)).convert("RGBA")


# ── Asset 합성 ────────────────────────────────────────────────────
def composite_character(master: Image.Image, character_path: str | Path,
                        target_width: int, right_margin: int = 40,
                        bottom_margin: int = 40) -> Image.Image:
    """정규화된 캐릭터(800x800)를 Master 우측 하단에 합성.

    target_width는 SVG의 HeroObject 배치와 맞춰 주제별로 조정
    (연말정산 700, 퇴직금 620 — 실측 검증값).
    """
    master = master.convert("RGBA")
    char = Image.open(character_path).convert("RGBA")
    scale = target_width / char.width
    char_scaled = char.resize((target_width, int(char.height * scale)), Image.LANCZOS)
    x = master.width - right_margin - char_scaled.width
    y = master.height - bottom_margin - char_scaled.height
    master.paste(char_scaled, (x, y), char_scaled)
    return master


def composite_hero_object(master: Image.Image, object_path: str | Path,
                          target_width: int, position_x: int, position_y: int) -> Image.Image:
    """정규화된 Hero Object(트로피 등)를 Master의 지정 좌표에 합성.

    position_x/y는 Master(1920x1080) 기준 절대좌표 — SVG 템플릿과 함께
    설계하며, 캐릭터 포인팅 손가락이 오브젝트 중심부에 인접하도록 맞춘다.
    """
    master = master.convert("RGBA")
    obj = Image.open(object_path).convert("RGBA")
    scale = target_width / obj.width
    obj_scaled = obj.resize((target_width, int(obj.height * scale)), Image.LANCZOS)
    master.paste(obj_scaled, (position_x, position_y), obj_scaled)
    return master


# ── 다운사이징 ────────────────────────────────────────────────────
def make_body(master: Image.Image) -> Image.Image:
    """Body는 항상 800x450 (Master와 동일 16:9)."""
    return master.convert("RGB").resize((BODY_W, BODY_H), Image.LANCZOS)


def make_thumbnail(master: Image.Image) -> Image.Image:
    """썸네일은 1:1 (512x512). 입력은 1:1 전용 SVG 렌더 결과여야 함."""
    return master.convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)


# ── QA 체크 ───────────────────────────────────────────────────────
def qa_korean_glyphs(img: Image.Image, zone: tuple[int, int, int, int],
                     min_dark_px: int = 500) -> dict:
    """지정 영역에 한글 글리프(어두운 픽셀)가 렌더링됐는지 검사.

    zone: (x0, y0, x1, y1) — Master 좌표 기준 제목/부제 영역.
    폰트가 없는 환경에서는 글리프가 그려지지 않아 dark_px가 0에 가깝다.
    """
    arr = np.array(img.convert("L"))
    x0, y0, x1, y1 = zone
    region = arr[y0:y1, x0:x1]
    dark_px = int((region < 100).sum())
    return {"dark_px": dark_px, "ok": dark_px >= min_dark_px}


def qa_image(path: str | Path, expect_size: tuple[int, int]) -> dict:
    """저장된 이미지의 해상도/무결성 확인."""
    path = Path(path)
    img = Image.open(path)
    return {
        "path": str(path),
        "size": img.size,
        "size_ok": img.size == expect_size,
        "bytes": path.stat().st_size,
    }
