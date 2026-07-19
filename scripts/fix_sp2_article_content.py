# -*- coding: utf-8 -*-
"""SP-2 — article_content 필드 법령 오류 수정"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

# (old_text, new_text) — 전체 문장 기준으로 교체
PATCHES = {
    "severance-pay": [
        (
            "근로기준법 제34조에 명시되어 있습니다. 이 조항에 따르면 1년 이상 근무한 근로자는 퇴직금을 받을 권리를 가집니다.",
            "근로자퇴직급여보장법 제8조에 명시되어 있습니다. 이 조항에 따르면 사용자는 계속근로기간 1년에 대하여 30일분 이상의 평균임금을 퇴직금으로 지급해야 하며, 1년 미만 근무자는 지급 의무가 발생하지 않습니다.",
        ),
    ],
    "육아휴직_급여_계산기": [
        (
            "근로기준법 제74조 및 고용보험법 제40조로, 이 법들은 육아휴직을 사용하는 근로자의 권익을 보호하기 위해 제정되었습니다.",
            "고용보험법 제70조(육아휴직 급여)로, 이 조항에 따라 피보험자가 30일 이상의 육아휴직을 부여받은 경우 고용노동부 장관이 육아휴직 급여를 지급합니다.",
        ),
    ],
}

print("="*70)
print(" SP-2 article_content 법령 오류 수정")
print("="*70)

for slug, patches in PATCHES.items():
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        print(f"\n[SKIP] {slug} — 계산기 없음")
        continue

    calc_id = calc.get("id", "")
    content = calc.get("article_content") or ""

    changed = False
    for old_text, new_text in patches:
        if old_text in content:
            content = content.replace(old_text, new_text)
            print(f"\n[수정] {slug}")
            print(f"  구: ...{old_text[:80]}...")
            print(f"  신: ...{new_text[:80]}...")
            changed = True
        else:
            print(f"\n[SKIP] {slug} — 대상 텍스트 없음: {old_text[:50]}...")

    if changed:
        calc_repo.update(calc_id, {"article_content": content})
        print(f"  → DB 업데이트 완료 (id={calc_id})")

print("\n" + "="*70)
print("article_content 수정 완료.")
