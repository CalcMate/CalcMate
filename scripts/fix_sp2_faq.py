# -*- coding: utf-8 -*-
"""SP-2 — DB faq 법령 오류 수정 (3개 계산기)

수정 내용:
  severance-pay:           근로기준법 제34조 → 근로자퇴직급여보장법 제8조
  연말정산_환급액_계산기:  소득세법 제55조·제63조 → 소득세법 제137조
  육아휴직_급여_계산기:   근로기준법 제74조·고용보험법 제40조 → 고용보험법 제70조

조문 검증 근거:
  legal_basis.draft.yaml article 필드 (verification_source: [law.go.kr, easylaw.go.kr])
  - severance-pay:        근로자퇴직급여보장법 제8조 (계속근로기간 1년 이상 시 퇴직금 지급)
  - 연말정산_환급액_계산기: 소득세법 제137조 (근로소득에 대한 연말정산 — 원천징수의무자가 과세기간 다음 연도에 정산)
  - 육아휴직_급여_계산기:  고용보험법 제70조 (육아휴직 급여 — 30일 이상 부여받은 피보험자에게 지급)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

# ── 수정 정의 (Q·A 세트) ───────────────────────────────────────────────
PATCHES = {
    "severance-pay": {
        "faq_q": "퇴직금 지급 관련 법적 근거는 무엇인가요?",
        "old_keyword": "근로기준법 제34조",
        "new_answer": (
            "퇴직금 지급의 법적 근거는 근로자퇴직급여보장법 제8조에 명시되어 있습니다. "
            "이 조항에 따르면 사용자는 계속근로기간 1년에 대하여 30일분 이상의 평균임금을 "
            "퇴직금으로 지급해야 하며, 1년 미만 근무자는 지급 의무가 발생하지 않습니다."
        ),
    },
    "연말정산_환급액_계산기": {
        "faq_q": "연말정산 환급액에 대한 법적 근거는 무엇인가요?",
        "old_keyword": "소득세법 제55조",
        "new_answer": (
            "연말정산의 법적 근거는 소득세법 제137조(근로소득에 대한 연말정산)에 명시되어 있습니다. "
            "이 조항에 따라 원천징수의무자는 해당 과세기간의 다음 연도 2월에 근로소득을 지급할 때 "
            "1년간의 근로소득세를 정산하며, 기납부세액이 확정세액을 초과하는 경우 환급이 발생합니다."
        ),
    },
    "육아휴직_급여_계산기": {
        "faq_q": "육아휴직 급여와 관련된 법적 근거는 무엇인가요?",
        "old_keyword": "근로기준법 제74조",
        "new_answer": (
            "육아휴직 급여의 법적 근거는 고용보험법 제70조(육아휴직 급여)입니다. "
            "이 조항에 따라 피보험자가 30일 이상의 육아휴직을 부여받은 경우, "
            "고용노동부 장관은 육아휴직 급여를 지급합니다."
        ),
    },
}

print("="*70)
print(" SP-2 DB faq 법령 오류 수정")
print("="*70)

for slug, patch in PATCHES.items():
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        print(f"\n[SKIP] {slug} — 계산기 없음")
        continue

    calc_id = calc.get("id", "")
    faq_raw = calc.get("faq") or "[]"
    try:
        faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
    except Exception:
        print(f"\n[ERROR] {slug} — faq JSON 파싱 실패")
        continue

    # 법령 오류 항목 찾아서 교체
    changed = False
    for i, item in enumerate(faq):
        a = item.get("answer") or item.get("a") or ""
        if patch["old_keyword"] in a:
            q = item.get("question") or item.get("q") or ""
            print(f"\n[수정] {slug}")
            print(f"  Q: {q}")
            print(f"  구 A: {a}")
            print(f"  신 A: {patch['new_answer']}")
            if "question" in item:
                item["answer"] = patch["new_answer"]
            else:
                item["a"] = patch["new_answer"]
            changed = True

    if not changed:
        print(f"\n[SKIP] {slug} — '{patch['old_keyword']}' 발견 안 됨 (이미 수정됐거나 불일치)")
        continue

    new_faq_json = json.dumps(faq, ensure_ascii=False)
    calc_repo.update(calc_id, {"faq": new_faq_json})
    print(f"  → DB 업데이트 완료 (id={calc_id})")

print("\n" + "="*70)
print("수정 완료. 계산기 HTML 재생성을 별도로 실행하세요.")
