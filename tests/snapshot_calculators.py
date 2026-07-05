# -*- coding: utf-8 -*-
"""
tests/snapshot_calculators.py — 계산기 생성물 스냅샷 회귀 하니스 (작업지시서 D Phase B)

app_generator의 하드코딩(_RELATED / _compute_js / generate_calculator 슬러그 분기)을
registry(legal_basis.draft.yaml) 조회로 이관할 때 "출력이 바이트 단위로 동일함"을 기계적으로
보장하기 위한 안전망.

generate_calculator(calc, cfg)는 순수 함수(.now()/타임스탬프 출력 없음)이므로
같은 (calc, cfg) → 항상 같은 바이트. 이 성질을 이용해:
  - save  : 현재 출력의 sha256을 골든 스냅샷으로 저장(tests/golden/calculator_snapshots.json)
  - check : 현재 출력을 골든과 비교. 하나라도 다르면 어떤 계산기/어떤 산출물인지 출력 후 종료코드 1.

계산기당 5개 산출물 해시:
  index.html / style.css / script.js  (generate_calculator 3파일)
  related    (_related_items_v2 직접 호출 — _RELATED 이관 핀포인트)
  compute    (_compute_js 직접 호출        — 날짜분기 이관 핀포인트)

실 DB(CalculatorRepository.get_all())의 실데이터로 검증. read는 1회만.

사용:
  python -m tests.snapshot_calculators save    # 골든 저장(2-a)
  python -m tests.snapshot_calculators check   # 회귀 비교(2-b/2-c 후)
"""
import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_GOLDEN = Path(__file__).resolve().parent / "golden" / "calculator_snapshots.json"


def _sha(text) -> str:
    return hashlib.sha256((text if isinstance(text, str) else str(text)).encode("utf-8")).hexdigest()


def _gather() -> dict:
    """실 DB 계산기 전부에 대해 산출물 5종의 sha256을 계산. slug 정렬로 안정 순서."""
    from modules.config_loader import load_config
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    from modules import app_generator as ag

    cfg = load_config()
    calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
    snap = {}
    for calc in sorted(calcs, key=lambda c: str(c.get("slug", ""))):
        slug = str(calc.get("slug", ""))
        files = ag.generate_calculator(calc, cfg)
        snap[slug] = {
            "index.html": _sha(files.get("index.html", "")),
            "style.css": _sha(files.get("style.css", "")),
            "script.js": _sha(files.get("script.js", "")),
            "related": _sha(ag._related_items_v2(calc)),
            "compute": _sha(ag._compute_js(calc)),
        }
    return snap


def save() -> int:
    snap = _gather()
    _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN.write_text(json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    total = sum(len(v) for v in snap.values())
    print(f"[SNAPSHOT save] {len(snap)} calculators x 5 artifacts = {total} hashes → {_GOLDEN}")
    for slug, arts in snap.items():
        print(f"  {slug:26} " + " ".join(f"{k}={h[:8]}" for k, h in arts.items()))
    return 0


def check() -> int:
    if not _GOLDEN.exists():
        print(f"[SNAPSHOT check] 골든 없음: {_GOLDEN} — 먼저 save 실행")
        return 2
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    current = _gather()
    diffs = []
    for slug in sorted(set(golden) | set(current)):
        g, c = golden.get(slug, {}), current.get(slug, {})
        if slug not in golden:
            diffs.append(f"  + 새 계산기 {slug} (골든에 없음)")
            continue
        if slug not in current:
            diffs.append(f"  - 사라진 계산기 {slug} (현재에 없음)")
            continue
        for art in sorted(set(g) | set(c)):
            if g.get(art) != c.get(art):
                diffs.append(f"  ~ {slug} :: {art}  golden={str(g.get(art))[:8]} != current={str(c.get(art))[:8]}")
    total = sum(len(v) for v in current.values())
    if diffs:
        print(f"[SNAPSHOT check] FAIL — {len(diffs)}건 불일치 (총 {total} 해시 비교):")
        print("\n".join(diffs))
        return 1
    print(f"[SNAPSHOT check] PASS — {len(current)} calculators x 5 artifacts = {total} hashes 전부 동일")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "save":
        sys.exit(save())
    elif mode == "check":
        sys.exit(check())
    else:
        print("usage: python -m tests.snapshot_calculators [save|check]")
        sys.exit(2)
