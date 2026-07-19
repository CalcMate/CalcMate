# -*- coding: utf-8 -*-
"""SP-2 - 계산기 DB faq 필드 상세 확인 및 캐시/TTL 확인"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)

print("="*70)
print(" severance-pay faq 필드 원문 확인")
print("="*70)
try:
    calc_repo = CalculatorRepository(db)
    calcs = calc_repo.get_all()
    sp = next((c for c in calcs if c.get("slug") == "severance-pay"), None)
    if sp:
        faq_raw = sp.get("faq") or ""
        # JSON 파싱 시도
        try:
            faq_parsed = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
            print(f"FAQ 항목 수: {len(faq_parsed)}개")
            for i, item in enumerate(faq_parsed, 1):
                q = item.get("question") or item.get("q") or ""
                a = item.get("answer") or item.get("a") or ""
                print(f"\n  [{i}] Q: {q}")
                print(f"      A: {a}")
                if "34조" in a or "34조" in q:
                    print(f"      *** 제34조 발견 ***")
        except Exception:
            print(f"FAQ (원문):\n{faq_raw}")
    else:
        print("severance-pay DB 항목 없음")
except Exception as e:
    import traceback; traceback.print_exc()

# 캐시 파일 확인
print("\n" + "="*70)
print(" 캐시/TTL 파일 내 제34조 확인")
print("="*70)

import glob
CACHE_PATTERNS = [
    "data/**/*.json",
    "data/**/*.cache",
    ".cache/**/*",
    "tmp/**/*",
]
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NORM_TARGET = re.sub(r"\s+", "", "근로기준법 제34조")

found_caches = []
for pattern in CACHE_PATTERNS:
    for fpath in ROOT.glob(pattern):
        if not fpath.is_file():
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            if NORM_TARGET in re.sub(r"\s+", "", content):
                found_caches.append(str(fpath.relative_to(ROOT)))
        except Exception:
            pass

if found_caches:
    print(f"캐시 파일에서 발견: {len(found_caches)}건")
    for f in found_caches:
        print(f"  - {f}")
else:
    print("캐시/tmp 파일에서 발견 없음")

# 다른 계산기 faq 필드에 forbidden_articles 관련 오류 있는지 점검
print("\n" + "="*70)
print(" 전체 계산기 DB faq 필드 법령 오류 스캔")
print("="*70)
FORBIDDEN_MAP = {
    "severance-pay":       ["근로기준법 제34조"],
    "육아휴직_급여_계산기": ["고용보험법 제40조", "근로기준법 제74조"],
    "연말정산_환급액_계산기": ["소득세법 제55조", "소득세법 제63조"],
}
try:
    for c in calcs:
        slug = c.get("slug", "")
        faq = str(c.get("faq") or "")
        forbidden_list = FORBIDDEN_MAP.get(slug, [])
        if not forbidden_list:
            continue
        faq_norm = re.sub(r"\s+", "", faq)
        hits = [f for f in forbidden_list if re.sub(r"\s+", "", f) in faq_norm]
        status = f"[발견: {hits}]" if hits else "[없음]"
        print(f"  {slug:40s} {status}")
except Exception as e:
    print(f"오류: {e}")
