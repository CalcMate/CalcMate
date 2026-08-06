# -*- coding: utf-8 -*-
"""
modules/image_fallback.py — 이미지 폴백 (v12 Lite, 신규)

Pollinations 등 이미지 생성 실패 시 기본 브랜드 템플릿 이미지를 PIL로 생성.
image_generator가 실패(None) 시 호출. 외부 의존 없이 항상 성공.
"""
from pathlib import Path

from .logger import get_logger

LOG = get_logger()
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "outputs"

# 브랜드 색상
_BG = (8, 18, 36)
_ACCENT = (99, 102, 241)
_TEXT = (232, 237, 246)


def generate_brand_image(post_id: str, kind: str, title: str = "CalcMate") -> str | None:
    """브랜드 템플릿 이미지(webp) 생성 후 경로 반환. 실패 시 None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        w, h = (512, 512) if kind == "thumb" else (800, 450)
        img = Image.new("RGB", (w, h), _BG)
        d = ImageDraw.Draw(img)
        # 상단 액센트 바
        d.rectangle([0, 0, w, 8], fill=_ACCENT)
        # 폰트
        def F(sz):
            for p in [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf"]:
                try:
                    return ImageFont.truetype(p, sz)
                except Exception:
                    pass
            return ImageFont.load_default()
        brand = "🧮 CalcMate"
        d.text((w // 2, h // 2 - 40), "CalcMate", font=F(46 if kind == "thumb" else 56),
               fill=_TEXT, anchor="mm")
        t = (title or "")[:22]
        d.text((w // 2, h // 2 + 26), t, font=F(22 if kind == "thumb" else 26),
               fill=(154, 167, 189), anchor="mm")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        fpath = OUTPUT_DIR / f"{post_id}_{kind}_fallback.webp"
        img.save(str(fpath), format="WEBP")
        LOG.info("[image_fallback] 브랜드 이미지 생성: %s", fpath.name)
        return str(fpath)
    except Exception as e:
        LOG.warning("[image_fallback] 생성 실패: %s", e)
        return None
