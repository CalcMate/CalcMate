# -*- coding: utf-8 -*-
"""
Phase 5-E 이미지 재생성 v2 — 18장 FAIL 이미지 개선 재생성

개선 사항:
  - 한국어 완전 제거 → 순수 영어 프롬프트
  - flat vector illustration 스타일 강제
  - 텍스트 포함 물체(계산기 키, 문서 내용) 대신 추상 실루엣/아이콘 사용
  - no-text suffix 강화 유지
  - PASS된 2장(01-thumb, 03-thumb)은 건드리지 않음
"""
from __future__ import annotations
import shutil
import sys
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

BASE = Path(__file__).parent.parent
IMAGES_DIR = BASE / "data" / "phase5-c" / "images"

NO_TEXT = (
    ", no text, no letters, no words, no numbers, no digits, "
    "no typography, no labels, no captions, no logos, no watermarks, "
    "no UI elements, no characters, no alphabet, "
    "text-free illustration, clean visual only, no written language, "
    "no inscriptions, no script, no glyphs, no symbols that resemble letters"
)

STYLE_FLAT = (
    "flat vector illustration style, clean minimal design, "
    "professional Korean business context, soft pastel colors, "
    "simple shapes only, no photorealism"
)

THUMB_GEN = (1024, 1024)
THUMB_OUT  = (512, 512)
BODY_GEN  = (1280, 720)
BODY_OUT  = (800, 450)

MAX_ATTEMPTS = 3
SEED_BASE    = 31415


TARGETS = [
    # ── 01 severance-pay eligibility ─────────────────────────────────────────
    # thumb은 PASS — 건드리지 않음
    {
        "slug_dir": "severance-pay",
        "filename": "severance-pay_eligibility_20260816_body.webp",
        "prompt": (
            "Korean office professional reviewing employment paperwork, "
            "desk with documents and pen, calm warm workplace scene, "
            "soft blue and white tones, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 02 weekly-holiday-allowance howto ────────────────────────────────────
    {
        "slug_dir": "weekly-holiday-allowance",
        "filename": "weekly-holiday-allowance_howto_20260816_thumb.webp",
        "prompt": (
            "Simple weekly calendar icon with checkmark, minimal clean design, "
            "pastel blue and white color palette, icon style, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "weekly-holiday-allowance",
        "filename": "weekly-holiday-allowance_howto_20260816_body.webp",
        "prompt": (
            "Office worker at desk looking at weekly schedule planner, "
            "laptop and coffee cup nearby, calm professional setting, "
            "warm soft colors, side profile, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 03 unemployment-benefit eligibility ──────────────────────────────────
    # thumb은 PASS — 건드리지 않음
    {
        "slug_dir": "unemployment-benefit",
        "filename": "unemployment-benefit_eligibility_20260816_body.webp",
        "prompt": (
            "Unemployed professional holding a support application form, "
            "employment office waiting area, calm hopeful atmosphere, "
            "blue and white tones, simple scene, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 04 four-insurances calculator ────────────────────────────────────────
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_calculator_20260816_thumb.webp",
        "prompt": (
            "Four shield protection icons in a circle, "
            "insurance concept, blue and white minimal icon design, "
            "clean geometric shapes, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_calculator_20260816_body.webp",
        "prompt": (
            "Korean HR professional at desk with insurance documents, "
            "laptop open, pen in hand, calm office environment, "
            "blue and white professional illustration, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 05 annual-leave-allowance howto ──────────────────────────────────────
    {
        "slug_dir": "annual-leave-allowance",
        "filename": "annual-leave-allowance_howto_20260816_thumb.webp",
        "prompt": (
            "Simple calendar icon with leaf and sun symbol, "
            "annual leave vacation concept, clean flat icon, "
            "green and white pastel colors, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "annual-leave-allowance",
        "filename": "annual-leave-allowance_howto_20260816_body.webp",
        "prompt": (
            "Office worker planning vacation time on a wall calendar, "
            "happy relaxed expression, plant and window in background, "
            "warm cheerful office setting, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 06 severance-pay documents ────────────────────────────────────────────
    {
        "slug_dir": "severance-pay",
        "filename": "severance-pay_documents_20260816_thumb.webp",
        "prompt": (
            "Stack of blank official documents with a seal stamp icon, "
            "clean minimal paperwork concept, blue and white, "
            "professional flat icon design, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "severance-pay",
        "filename": "severance-pay_documents_20260816_body.webp",
        "prompt": (
            "HR manager passing a sealed envelope to a departing employee, "
            "formal professional handover scene in office corridor, "
            "respectful calm atmosphere, blue and grey tones, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 07 육아휴직 급여 계산기 eligibility ──────────────────────────────────
    {
        "slug_dir": "육아휴직_급여_계산기",
        "filename": "육아휴직_급여_계산기_eligibility_20260816_thumb.webp",
        "prompt": (
            "Young mother with baby in arms smiling, "
            "parental leave concept, warm pastel colors, "
            "soft rounded flat design, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "육아휴직_급여_계산기",
        "filename": "육아휴직_급여_계산기_eligibility_20260816_body.webp",
        "prompt": (
            "Working parent on parental leave at home with baby and laptop, "
            "cozy home office setting, warm yellow and white tones, "
            "family and work balance illustration, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 08 연말정산 환급액 계산기 calculator ─────────────────────────────────
    {
        "slug_dir": "연말정산_환급액_계산기",
        "filename": "연말정산_환급액_계산기_calculator_20260816_thumb.webp",
        "prompt": (
            "Tax refund concept with coins and piggy bank, "
            "year-end tax settlement symbol, clean flat icon design, "
            "gold and blue colors, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "연말정산_환급액_계산기",
        "filename": "연말정산_환급액_계산기_calculator_20260816_body.webp",
        "prompt": (
            "Financial professional reviewing tax return on laptop, "
            "coins and documents on desk, year-end calculation scene, "
            "professional calm office environment, blue and gold tones, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 09 unemployment-benefit howto ─────────────────────────────────────────
    {
        "slug_dir": "unemployment-benefit",
        "filename": "unemployment-benefit_howto_20260816_thumb.webp",
        "prompt": (
            "Step process arrow icons showing application flow, "
            "employment benefit application steps concept, "
            "blue arrow flow diagram style, minimal flat icons, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "unemployment-benefit",
        "filename": "unemployment-benefit_howto_20260816_body.webp",
        "prompt": (
            "Person submitting application form at government employment office counter, "
            "professional staff assisting, calm helpful atmosphere, "
            "blue and white government office setting, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
    # ── 10 four-insurances documents ──────────────────────────────────────────
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_documents_20260816_thumb.webp",
        "prompt": (
            "Four official blank form sheets fanned out neatly, "
            "clean minimal document icon concept, "
            "blue and white professional flat design, square format, "
            + STYLE_FLAT
        ),
        "gen_size": THUMB_GEN,
        "out_size": THUMB_OUT,
    },
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_documents_20260816_body.webp",
        "prompt": (
            "HR manager at laptop registering new employee for social insurance, "
            "clean modern office, clipboard and pen nearby, "
            "professional calm workspace, blue and grey soft tones, "
            + STYLE_FLAT
        ),
        "gen_size": BODY_GEN,
        "out_size": BODY_OUT,
    },
]


def _download(prompt: str, gen_size: tuple[int, int], seed: int) -> bytes | None:
    w, h = gen_size
    encoded = urllib.parse.quote(prompt + NO_TEXT)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={w}&height={h}&nologo=true&seed={seed}"
    )
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
        print(f"  warning  HTTP {r.status_code}, size={len(r.content)}")
        return None
    except Exception as e:
        print(f"  warning  request failed: {e}")
        return None


def _resize_save(data: bytes, out_path: Path, out_size: tuple[int, int]) -> dict:
    try:
        img = Image.open(BytesIO(data))
        img = img.convert("RGB")
        img = img.resize(out_size, Image.LANCZOS)
        img.save(out_path, format="WEBP", quality=85)
        kb = round(out_path.stat().st_size / 1024, 1)
        return {"ok": True, "w": out_size[0], "h": out_size[1], "size_kb": kb}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def regen_one(target: dict, idx: int) -> dict:
    slug_dir = IMAGES_DIR / target["slug_dir"]
    slug_dir.mkdir(parents=True, exist_ok=True)
    dest = slug_dir / target["filename"]
    bak  = dest.with_suffix(".bak2.webp")

    if dest.exists() and not bak.exists():
        shutil.copy2(dest, bak)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        seed = SEED_BASE + idx * 10_000 + attempt * 1_000
        print(f"  attempt {attempt}/{MAX_ATTEMPTS} (seed={seed})...")
        data = _download(target["prompt"], target["gen_size"], seed)
        if data is None:
            continue
        result = _resize_save(data, dest, target["out_size"])
        if not result["ok"]:
            print(f"  warning  resize failed: {result.get('error')}")
            continue
        print(f"  OK: {dest.name} ({result['w']}x{result['h']}, {result['size_kb']}KB)")
        return {"status": "ok", "filename": target["filename"], **result}

    print(f"  HOLD: {target['filename']} -- {MAX_ATTEMPTS} attempts failed, keeping original")
    if bak.exists() and not dest.exists():
        shutil.copy2(bak, dest)
    return {"status": "hold", "filename": target["filename"]}


def main() -> int:
    print(f"Phase 5-E v2 image regen -- {len(TARGETS)} images")
    print("=" * 70)

    results = []
    for i, t in enumerate(TARGETS, 1):
        print(f"[{i}/{len(TARGETS)}] {t['filename']}")
        r = regen_one(t, i)
        results.append(r)
        print()

    ok   = [r for r in results if r["status"] == "ok"]
    hold = [r for r in results if r["status"] == "hold"]

    print("=" * 70)
    print(f"success: {len(ok)}/{len(TARGETS)}")
    if hold:
        print(f"HOLD ({len(hold)}):")
        for h in hold:
            print(f"  - {h['filename']}")

    return 0 if not hold else 1


if __name__ == "__main__":
    sys.exit(main())
