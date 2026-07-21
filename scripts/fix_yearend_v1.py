# -*- coding: utf-8 -*-
"""연말정산 계산기 v1 DB 업데이트 + workspace 재생성 + golden 갱신.

변경:
- input_schema: total_salary, family_count, paid_tax
- output_schema: estimated_refund
- labels: 한국어 레이블
- FAQ: SP-8 패턴 없는 자연어 8개
- article_content: 구 form 제거, 누진세율 v1 기준 자연어 + 예시 (Python mirror 결과)
- compute_js: app_generator._compute_js() 자동 생성
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

ROOT      = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"
SNAPSHOT  = ROOT / "tests" / "golden" / "calculator_snapshots.json"
SLUG      = "연말정산_환급액_계산기"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
yt    = next(c for c in calcs if c.get("slug") == SLUG)

# ── 1. input/output/labels ─────────────────────────────────────
INPUT_SCHEMA = json.dumps({
    "total_salary":  "number",
    "family_count":  "number",
    "paid_tax":      "number",
}, ensure_ascii=False)

OUTPUT_SCHEMA = json.dumps({
    "estimated_refund": "number",
}, ensure_ascii=False)

LABELS = json.dumps({
    "total_salary":      "연간 총급여(원)",
    "family_count":      "인적공제 대상 수(명)",
    "paid_tax":          "기납부 소득세액(원)",
    "estimated_refund":  "환급/추가납부 예상(원)",
}, ensure_ascii=False)

# ── 2. FAQ (SP-8 패턴 없는 자연어) ──────────────────────────────
FAQ = json.dumps([
    {
        "question": "연말정산 환급액이란 무엇인가요?",
        "answer": (
            "연말정산 환급액은 한 해 동안 매월 원천징수된 소득세 합계(기납부세액)가 "
            "실제 결정세액보다 많을 때 그 차액을 돌려받는 금액입니다. "
            "반대로 기납부세액이 결정세액보다 적으면 부족분을 추가 납부해야 합니다 "
            "(소득세법 제137조)."
        ),
    },
    {
        "question": "연말정산은 언제 하나요?",
        "answer": (
            "근로소득자의 연말정산은 다음 연도 1월에 원천징수의무자(회사)가 진행하며, "
            "2월분 급여 지급 시 환급 또는 추가 납부가 반영됩니다. "
            "중도 퇴직자는 퇴직 월의 급여 지급 시 정산합니다."
        ),
    },
    {
        "question": "환급 또는 추가납부는 어떻게 결정되나요?",
        "answer": (
            "총급여에서 근로소득공제(소득세법 제47조)를 뺀 근로소득금액을 구하고, "
            "인적공제·4대보험 공제액을 추가로 차감하면 과세표준이 나옵니다. "
            "과세표준에 누진세율(6%~45%)을 적용해 산출세액을 구하고, "
            "근로소득세액공제(소득세법 제59조)를 차감하면 결정세액이 됩니다. "
            "기납부세액에서 결정세액을 뺀 값이 양수면 환급, 음수면 추가납부입니다."
        ),
    },
    {
        "question": "기납부 소득세액은 어디서 확인하나요?",
        "answer": (
            "회사에서 매년 초 발급하는 근로소득 원천징수영수증의 '기납부세액' 항목을 확인하세요. "
            "국세청 홈택스(hometax.go.kr)에서도 연말정산 간소화 서비스를 통해 "
            "전년도 납부 내역을 조회할 수 있습니다."
        ),
    },
    {
        "question": "인적공제 대상 수는 어떻게 입력하나요?",
        "answer": (
            "본인을 포함하여 기본공제 대상 가족 수를 입력합니다. "
            "배우자, 직계존속(부모·조부모), 직계비속(자녀), 형제자매 중 "
            "소득 요건(연 100만원 이하)과 나이 요건을 충족하는 부양가족이 해당됩니다 "
            "(소득세법 제50조). 1인 가구는 '1'을 입력하세요."
        ),
    },
    {
        "question": "4대보험료는 어떻게 계산되나요?",
        "answer": (
            "이 계산기는 연간 총급여를 12로 나눈 월 급여 기준으로 "
            "국민연금(4.5%), 건강보험(3.545%), 장기요양보험(건강보험료의 12.96%), "
            "고용보험(0.9%)을 자동 계산하여 공제합니다. "
            "실제 원천징수영수증의 4대보험 공제액과 차이가 있을 수 있습니다."
        ),
    },
    {
        "question": "계산 결과가 실제 환급액과 다를 수 있나요?",
        "answer": (
            "네, 이 계산기는 소득세법 기준 기본 공제 항목(근로소득공제·인적공제·4대보험)만 "
            "반영합니다. 의료비·교육비·신용카드·주택자금·연금저축 등 추가 공제 항목과 "
            "자녀세액공제는 현재 버전에서 제외되어 있어 실제 정산액과 차이가 생길 수 있습니다. "
            "정확한 금액은 국세청 홈택스 연말정산 간소화 서비스를 이용하세요."
        ),
    },
    {
        "question": "연말정산의 법적 근거는 무엇인가요?",
        "answer": (
            "연말정산의 법적 근거는 소득세법 제137조(근로소득세액의 연말정산)입니다. "
            "이 조항에 따라 원천징수의무자는 해당 과세기간의 다음 연도 2월분 급여 지급 시 "
            "소득·세액공제를 반영해 최종 소득세를 정산합니다. "
            "세율은 소득세법 제55조, 근로소득공제는 제47조, 세액공제는 제59조에 근거합니다."
        ),
    },
], ensure_ascii=False)

# ── 3. article_content (SP-8 구 form 제거, 자연어 + 예시) ──────
# 예시 금액은 Python mirror(compute_year_end_settlement) 결과만 사용
# 예시1: 총급여 4,000만, 2인, 기납부 250만 → 환급 1,145,766원
# 예시2: 총급여 7,000만, 1인, 기납부 200만 → 추가납부 3,380,034원
ARTICLE = """<h1>2026년 연말정산 환급액 계산기</h1>
<p>연간 총급여액과 부양가족 수, 기납부 소득세액을 입력하면 환급 예상액 또는 추가 납부 예상액을 계산해 드립니다. 소득세법에 규정된 근로소득공제·인적공제·4대보험 공제·누진세율·근로소득세액공제를 모두 반영한 단계별 결과를 확인하세요.</p>

<h2>연말정산이란?</h2>
<p>근로소득자는 매월 급여에서 소득세를 원천징수한 뒤, 연말(다음 해 1~2월)에 실제 세액과 기납부세액을 비교하여 정산합니다. 이 과정을 연말정산이라 하며, 소득세법 제137조에 법적 근거가 있습니다. 기납부세액이 결정세액보다 많으면 환급, 적으면 추가 납부합니다.</p>

<h2>계산 방법 (11단계)</h2>
<p>이 계산기는 다음 순서로 세액을 산출합니다.</p>
<ol>
  <li><strong>총급여</strong> — 연간 총급여액을 기준으로 합니다.</li>
  <li><strong>근로소득공제</strong> — 총급여 구간별 공제율을 적용합니다(소득세법 제47조). 한도 2,000만원.</li>
  <li><strong>근로소득금액</strong> — 총급여에서 근로소득공제를 뺀 금액입니다.</li>
  <li><strong>인적공제</strong> — 본인 포함 기본공제 대상자 1인당 150만원을 차감합니다(소득세법 제50조).</li>
  <li><strong>4대보험 공제</strong> — 총급여를 12로 나눈 월 기준으로 국민연금·건강보험·장기요양·고용보험 연간 합계를 자동 계산합니다.</li>
  <li><strong>과세표준</strong> — 근로소득금액에서 인적공제와 4대보험 공제를 뺀 값입니다.</li>
  <li><strong>산출세액</strong> — 과세표준에 누진세율(6%~45%)을 적용합니다(소득세법 제55조).</li>
  <li><strong>근로소득세액공제</strong> — 산출세액에 따라 최대 66만~74만원 한도로 공제합니다(소득세법 제59조).</li>
  <li><strong>결정세액</strong> — 산출세액에서 세액공제를 뺀 최종 세액입니다.</li>
  <li><strong>지방소득세</strong> — 결정세액의 10%입니다.</li>
  <li><strong>환급/추가납부</strong> — 기납부세액에서 결정세액을 빼서 양수면 환급, 음수면 추가납부입니다.</li>
</ol>

<h2>계산 예시</h2>
<p><strong>예시 1 — 총급여 4,000만원, 부양가족 2인(본인 포함), 기납부세액 250만원</strong></p>
<ul>
  <li>근로소득공제: 1,125만원 → 근로소득금액 2,875만원</li>
  <li>인적공제: 300만원(2인) / 4대보험 공제: 약 376만원</li>
  <li>과세표준: 약 2,199만원 → 산출세액: 약 2,038,234원</li>
  <li>근로소득세액공제: 684,000원 → 결정세액: 1,354,234원</li>
  <li>기납부세액 250만원 - 결정세액 1,354,234원 = <strong>환급 1,145,766원</strong></li>
</ul>
<p><strong>예시 2 — 총급여 7,000만원, 1인 가구, 기납부세액 200만원</strong></p>
<ul>
  <li>근로소득공제: 1,325만원 → 근로소득금액 5,675만원</li>
  <li>인적공제: 150만원(1인) / 4대보험 공제: 약 658만원</li>
  <li>과세표준: 약 4,867만원 → 산출세액: 약 6,040,034원</li>
  <li>근로소득세액공제: 660,000원 → 결정세액: 5,380,034원</li>
  <li>기납부세액 200만원 - 결정세액 5,380,034원 = <strong>추가납부 3,380,034원</strong></li>
</ul>

<h2>주의사항</h2>
<p>이 계산기는 참고용 예상치이며, 실제 연말정산 결과는 국세청 홈택스 및 회사 정산 결과와 다를 수 있습니다. 의료비·교육비·신용카드·주택자금·연금저축 공제와 자녀세액공제는 현재 버전에서 제외되어 있습니다. 정확한 정산은 국세청 홈택스(hometax.go.kr)의 연말정산 간소화 서비스를 이용하세요.</p>"""

# ── 4. DB 업데이트 ─────────────────────────────────────────────
repo.update(yt["id"], {
    "input_schema":   INPUT_SCHEMA,
    "output_schema":  OUTPUT_SCHEMA,
    "labels":         LABELS,
    "faq":            FAQ,
    "article_content": ARTICLE,
})
print("✔ DB 업데이트 완료")

# ── 5. workspace 재생성 ────────────────────────────────────────
calcs = repo.get_all()
yt2   = next(c for c in calcs if c.get("slug") == SLUG)
out_dir = WORKSPACE / SLUG
out_dir.mkdir(parents=True, exist_ok=True)
result = generate_calculator(yt2, cfg)
for fname, content in result.items():
    if isinstance(content, str):
        (out_dir / fname).write_text(content, encoding="utf-8")
print("✔ workspace 재생성 완료")

# ── 6. golden snapshot 갱신 ────────────────────────────────────
snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
if SLUG not in snap:
    snap[SLUG] = {}
for fname in ["index.html", "script.js", "style.css"]:
    fpath = out_dir / fname
    if fpath.exists():
        snap[SLUG][fname] = hashlib.md5(fpath.read_bytes()).hexdigest()
SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("✔ golden snapshot 갱신 완료")
print("완료")
