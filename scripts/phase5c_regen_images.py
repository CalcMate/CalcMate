"""
Phase 5-C 이미지 재생성 — AI 텍스트 아티팩트 6장 교체
대상: four-insurances_calculator(2), four-insurances_documents_body(1),
       unemployment-benefit_howto_body(1), 연말정산_환급액_계산기(2)
"""
import sys
import shutil
import urllib.parse
import requests
from pathlib import Path
from PIL import Image

BASE = Path(__file__).parent.parent
IMAGES_DIR = BASE / "data" / "phase5-c" / "images"

NO_TEXT_SUFFIX = (
    ", no text, no letters, no words, no numbers, no typography, "
    "no labels, no logos, no watermark, no UI text, no captions, "
    "no characters, no alphabet, no symbols that look like text, "
    "text-free illustration, clean visual only"
)

# ── 재생성 대상 6장 정의 ─────────────────────────────────────────────────────
TARGETS = [
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_calculator_20260816_thumb.webp",
        "kind": "thumb",
        "prompt": (
            "Four social insurance types concept, clean flat design icons, "
            "health insurance shield, pension coin stack, employment safety net, "
            "industrial accident hard hat, professional Korean workplace context, "
            "bright clean white background, minimalist icon design, "
            "512x512 square format"
            + NO_TEXT_SUFFIX
        ),
    },
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_calculator_20260816_body.webp",
        "kind": "body",
        "prompt": (
            "Four Korean social insurance calculation infographic, "
            "four interconnected circles representing health, pension, employment, industrial insurance, "
            "percentage arrows flowing between circles, clean flat diagram, "
            "blue and green color palette, professional business visualization, "
            "wide horizontal infographic format"
            + NO_TEXT_SUFFIX
        ),
    },
    {
        "slug_dir": "four-insurances",
        "filename": "four-insurances_documents_20260816_body.webp",
        "kind": "body",
        "prompt": (
            "Official Korean insurance enrollment documents organized on clean desk, "
            "stacked application forms, official stamps, clipboard checklist, "
            "blue folder, professional office setting, flat lay composition, "
            "wide horizontal format, neutral background"
            + NO_TEXT_SUFFIX
        ),
    },
    {
        "slug_dir": "unemployment-benefit",
        "filename": "unemployment-benefit_howto_20260816_body.webp",
        "kind": "body",
        "prompt": (
            "Unemployment benefit application process infographic, "
            "step-by-step flow diagram with arrows, "
            "person at computer, document submission, approval checkmark, "
            "bank transfer icon, five connected steps with icons only, "
            "clean professional flat design, blue color theme, "
            "wide horizontal infographic"
            + NO_TEXT_SUFFIX
        ),
    },
    {
        "slug_dir": "연말정산_환급액_계산기",
        "filename": "연말정산_환급액_계산기_calculator_20260816_thumb.webp",
        "kind": "thumb",
        "prompt": (
            "Korean year-end tax settlement refund concept, "
            "hand holding coins with upward arrow, "
            "tax document and calculator on desk, "
            "green and blue professional colors, "
            "clean flat design illustration, square format"
            + NO_TEXT_SUFFIX
        ),
    },
    {
        "slug_dir": "연말정산_환급액_계산기",
        "filename": "연말정산_환급액_계산기_calculator_20260816_body.webp",
        "kind": "body",
        "prompt": (
            "Year-end tax refund calculation visualization, "
            "two hands exchanging money bills representing withholding tax vs final tax, "
            "balance scale showing overpaid tax returning, "
            "clean infographic with arrows and icons, "
            "professional blue and green color palette, wide horizontal"
            + NO_TEXT_SUFFIX
        ),
    },
]


def download_image(prompt: str, kind: str, attempt: int) -> bytes | None:
    encoded = urllib.parse.quote(prompt)
    if kind == "thumb":
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true&seed={attempt * 7919}"
    else:
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=450&nologo=true&seed={attempt * 7919}"
    try:
        r = requests.get(url, timeout=90)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
        print(f"  ⚠️  HTTP {r.status_code}, size={len(r.content)}")
        return None
    except Exception as e:
        print(f"  ⚠️  요청 실패: {e}")
        return None


def verify_image(path: Path) -> dict:
    """PIL로 파일 무결성 검사. 텍스트 아티팩트는 육안 확인 필요."""
    try:
        img = Image.open(path)
        img.verify()
        img2 = Image.open(path)
        w, h = img2.size
        size_kb = path.stat().st_size / 1024
        return {"ok": True, "w": w, "h": h, "size_kb": round(size_kb, 1)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def regen_one(target: dict, max_attempts: int = 2) -> dict:
    dest_path = IMAGES_DIR / target["slug_dir"] / target["filename"]
    backup_path = dest_path.with_suffix(".bak.webp")

    # 원본 백업
    if dest_path.exists() and not backup_path.exists():
        shutil.copy2(dest_path, backup_path)

    for attempt in range(1, max_attempts + 1):
        print(f"  생성 시도 {attempt}/{max_attempts}...")
        data = download_image(target["prompt"], target["kind"], attempt)
        if data is None:
            print(f"  ❌ 다운로드 실패 (시도 {attempt})")
            continue

        # 임시 저장
        tmp = dest_path.with_suffix(f".tmp{attempt}.webp")
        tmp.write_bytes(data)

        # 검증
        v = verify_image(tmp)
        if not v["ok"]:
            print(f"  ❌ PIL 검증 실패: {v.get('error')}")
            tmp.unlink(missing_ok=True)
            continue

        # 최종 교체
        shutil.move(str(tmp), str(dest_path))
        print(f"  ✅ 저장 완료: {dest_path.name} ({v['w']}x{v['h']}, {v['size_kb']}KB)")
        return {"status": "ok", "filename": target["filename"], **v}

    # 2회 모두 실패 → 백업 복원
    print(f"  ⚠️  {max_attempts}회 실패 → HOLD (원본 유지)")
    if backup_path.exists():
        shutil.copy2(backup_path, dest_path)
    return {"status": "hold", "filename": target["filename"]}


def main():
    print("=" * 60)
    print("Phase 5-C Image Regen -- AI Text Artifact 6 files")
    print("=" * 60)
    print(f"대상: {len(TARGETS)}장\n")

    results = []
    for i, target in enumerate(TARGETS, 1):
        print(f"[{i}/{len(TARGETS)}] {target['filename']}")
        r = regen_one(target)
        results.append(r)
        print()

    # 결과 요약
    ok = [r for r in results if r["status"] == "ok"]
    hold = [r for r in results if r["status"] == "hold"]

    print("=" * 60)
    print(f"재생성 성공: {len(ok)}/6")
    print(f"HOLD: {len(hold)}/6")
    if hold:
        for h in hold:
            print(f"  HOLD: {h['filename']}")

    return len(hold) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
