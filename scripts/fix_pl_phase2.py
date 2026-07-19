# -*- coding: utf-8 -*-
"""육아휴직급여 계산기 Phase 2 — 계산 엔진 교체.

변경 범위:
  DB: input_schema / output_schema / labels / formula 교체
  Workspace: index.html / style.css / script.js 재생성
  Golden: calculator_snapshots.json 해시 갱신

계산 엔진 (app_generator.py slug 분기):
  determine_leave_mode() → GENERAL | SPECIAL_6_PLUS_6
  calculate_general()    → 통상임금 × 80%, 상한 150만 / 하한 70만
  calculate_6plus6()     → 통상임금 × 100%, 월별 상한(1~6개월: 200~450만)
  insured_days < 180     → 수급 불가 notice (고용보험법 제70조 제1항)
  use_6plus6=1 + month>6 → 자동 일반 전환 notice

Phase 1 콘텐츠(faq, article_content) 무수정.
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

ROOT = Path(__file__).resolve().parent.parent

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
pl = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)
assert pl, "육아휴직_급여_계산기 없음"
calc_id = pl["id"]

# ══════════════════════════════════════════════════════════════════════════════
# 1. DB 스키마 교체
# ══════════════════════════════════════════════════════════════════════════════
NEW_INPUT_SCHEMA = {
    "monthly_wage":  "number",  # 통상임금(월)
    "insured_days":  "number",  # 피보험단위기간 — 수급자격 확인용 (고용보험법 제70조 제1항)
    "use_6plus6":    "number",  # 6+6 특례 해당 여부 (1=예, 0=아니오)
    "leave_month":   "number",  # 육아휴직 개월차 (1~12)
}
NEW_OUTPUT_SCHEMA = {
    "monthly_allowance": "number",  # 예상 월 육아휴직급여
}
NEW_LABELS = {
    "monthly_wage":      "통상임금(원)",
    "insured_days":      "피보험단위기간(일)",
    "use_6plus6":        "6+6 특례 해당(1=예/0=아니오)",
    "leave_month":       "육아휴직 개월차(개월)",
    "monthly_allowance": "예상 월 육아휴직급여(원)",
}
NEW_FORMULA = ""  # slug 전용 _compute_js 분기가 처리 — formula 필드 미사용

print("=" * 60)
print(" 1. DB 스키마 교체")
print("=" * 60)

prev_in  = pl.get("input_schema")  or ""
prev_out = pl.get("output_schema") or ""
print(f"  이전 input_schema:  {str(prev_in)[:80]}")
print(f"  이전 output_schema: {str(prev_out)[:80]}")

repo.update(calc_id, {
    "input_schema":  json.dumps(NEW_INPUT_SCHEMA,  ensure_ascii=False),
    "output_schema": json.dumps(NEW_OUTPUT_SCHEMA, ensure_ascii=False),
    "labels":        json.dumps(NEW_LABELS,         ensure_ascii=False),
    "formula":       NEW_FORMULA,
})

# 업데이트된 calc 재조회
pl_updated = repo.get_by_id(calc_id)
assert pl_updated, "재조회 실패"

print(f"  신규 input_schema:  {pl_updated.get('input_schema', '')[:80]}")
print(f"  신규 output_schema: {pl_updated.get('output_schema', '')[:80]}")
print()

# ══════════════════════════════════════════════════════════════════════════════
# 2. Workspace 재생성
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print(" 2. Workspace 재생성")
print("=" * 60)

out_dir = ROOT / "data" / "workspace" / "육아휴직_급여_계산기"
out_dir.mkdir(parents=True, exist_ok=True)

result = generate_calculator(pl_updated, cfg)
for fname, content in result.items():
    if not isinstance(content, str):
        print(f"  [{fname}] {content}")
        continue
    (out_dir / fname).write_text(content, encoding="utf-8")
    print(f"  [OK] {fname}  {len(content.encode('utf-8')):,} bytes")

print()

# ══════════════════════════════════════════════════════════════════════════════
# 3. Golden 스냅샷 갱신
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print(" 3. Golden 스냅샷 갱신")
print("=" * 60)

SNAPSHOT_PATH = ROOT / "tests" / "golden" / "calculator_snapshots.json"
snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
slug = "육아휴직_급여_계산기"
if slug not in snap:
    snap[slug] = {}

FILES = ["script.js", "index.html", "style.css"]
for fname in FILES:
    fpath = out_dir / fname
    if not fpath.exists():
        continue
    new_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
    old_hash = snap[slug].get(fname, "없음")
    snap[slug][fname] = new_hash
    changed = "변경" if (old_hash != new_hash and old_hash != "없음") else ("신규" if old_hash == "없음" else "동일")
    print(f"  [{changed}] {slug}/{fname}: {str(old_hash)[:12]}... → {new_hash[:12]}...")

SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print()

# ══════════════════════════════════════════════════════════════════════════════
# 4. 검증: 생성된 script.js 주요 패턴 확인
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print(" 4. script.js 검증")
print("=" * 60)

REQUIRED_PATTERNS = [
    ("inputs: monthly_wage",       '"monthly_wage"'),
    ("inputs: insured_days",        '"insured_days"'),
    ("inputs: use_6plus6",          '"use_6plus6"'),
    ("inputs: leave_month",         '"leave_month"'),
    ("output: monthly_allowance",   '"monthly_allowance"'),
    ("determine_leave_mode 함수",   "determine_leave_mode"),
    ("calculate_general 함수",      "calculate_general"),
    ("calculate_6plus6 함수",       "calculate_6plus6"),
    ("180일 수급자격 체크",          "MIN_INSURED"),
    ("일반 지급률 0.8",             "GEN_RATE"),
    ("일반 상한 1500000",           "GEN_CEIL"),
    ("일반 하한 700000",            "GEN_FLOOR"),
    ("특례 최대 6개월",             "SP_MAX_MO"),
    ("특례 월별 상한 배열",         "SP_CEILS"),
    ("전환 notice",                "개월째는 일반"),
]

js_text = (out_dir / "script.js").read_text(encoding="utf-8")
all_ok = True
for desc, pattern in REQUIRED_PATTERNS:
    found = pattern in js_text
    status = "OK" if found else "MISSING"
    if not found:
        all_ok = False
    print(f"  [{status}] {desc}: '{pattern}'")

print()
if all_ok:
    print("  ✅ 모든 패턴 확인 — Phase 2 workspace 생성 완료")
else:
    print("  ❌ 누락 패턴 있음 — app_generator.py 수정 확인 필요")
    sys.exit(1)

print("\n=== Phase 2 완료. 다음: pytest tests/ ===")
