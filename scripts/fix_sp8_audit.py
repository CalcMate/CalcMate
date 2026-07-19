# -*- coding: utf-8 -*-
"""SP-8 전수 감사 수정: 4개 계산기 구 form 제거 + 주휴수당 faq[2] 자연어 교체.

수정 항목:
  1. 주휴수당  article_content — 구 form + 결과해설 섹션 제거
  2. 실업급여  article_content — 구 form + 결과해설 섹션 제거
  3. 4대보험   article_content — 구 form + 결과 ul 섹션 제거
  4. 연차수당  article_content — 구 form + 결과해설 섹션 제거
  5. 주휴수당  faq[2].answer  — 코드 스타일 공식 → 자연어 교체
"""
import sys, os, json, re, hashlib
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

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def tracked_replace(text: str, old: str, new: str, label: str) -> str:
    cnt = text.count(old)
    if cnt == 0:
        raise ValueError(f"❌ tracked_replace({label}): 패턴 없음 — old=\n{repr(old[:120])}")
    result = text.replace(old, new, 1)
    print(f"  ✔ {label} (패턴 {cnt}건 → 1회 교체)")
    return result

def regen_workspace(calc_rec: dict, slug_dir: str):
    out_dir = WORKSPACE / slug_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    result = generate_calculator(calc_rec, cfg)
    for fname, content in result.items():
        if isinstance(content, str):
            (out_dir / fname).write_text(content, encoding="utf-8")
    print(f"  ✔ workspace 재생성: {slug_dir}")

def update_snapshot(snap: dict, dir_name: str):
    for fname in ["index.html", "script.js", "style.css"]:
        fpath = WORKSPACE / dir_name / fname
        if not fpath.exists():
            continue
        h = hashlib.md5(fpath.read_bytes()).hexdigest()
        if dir_name not in snap:
            snap[dir_name] = {}
        snap[dir_name][fname] = h
    print(f"  ✔ golden 갱신: {dir_name}")

# ── 정확한 제거 블록 정의 ─────────────────────────────────────────────────────

# 1. 주휴수당
WH_REMOVE = (
    '\n\n<h2>계산기 입력 폼 안내</h2>\n'
    '<p>아래의 입력 폼에 시급과 주간 근무 시간을 입력해 주세요. '
    '계산 결과를 통해 여러분의 주휴수당을 손쉽게 확인할 수 있습니다.</p>\n\n'
    '<form id="wage-calculator">\n'
    '    <label for="hourly_wage">시급(원):</label>\n'
    '    <input type="number" id="hourly_wage" name="hourly_wage" required>\n'
    '    <br>\n'
    '    <label for="weekly_hours">주간 근무 시간(시간):</label>\n'
    '    <input type="number" id="weekly_hours" name="weekly_hours" required>\n'
    '    <br>\n'
    '    <button type="submit">계산하기</button>\n'
    '</form>\n\n'
    '<h2>결과 해설</h2>\n'
    '<p>계산한 주휴수당은 근로자의 권리 중 하나로, 이는 일정 조건을 충족해야 지급됩니다. '
    '주 15시간 이상 근무하는 근로자에게 해당하며, 근로자가 주휴일에 출근하지 않고도 '
    '소정의 근로시간을 채웠을 때 지급됩니다. 계산된 주휴수당은 여러분의 주급에 추가하여 '
    '지급되며, 이를 통해 근로자는 추가적인 소득을 얻을 수 있습니다.</p>'
)

# 2. 실업급여
UB_REMOVE = (
    '\n\n<h2>1. 입력: 계산기 입력폼 안내</h2>\n'
    '<p>아래 입력 폼에 평균 일급, 나이, 고용 기간(개월)을 입력해주시기 바랍니다. '
    '피보험단위기간이 6개월(약 180일) 미만이면 수급 불가 안내가 표시됩니다.</p>\n'
    '<form>\n'
    '    <label for="avg_daily_wage">평균 일급:</label>\n'
    '    <input type="number" id="avg_daily_wage" name="avg_daily_wage" required>\n\n'
    '    <label for="age">나이:</label>\n'
    '    <input type="number" id="age" name="age" required>\n\n'
    '    <label for="employment_months">고용 기간(개월):</label>\n'
    '    <input type="number" id="employment_months" name="employment_months" required>\n\n'
    '    <button type="submit">계산하기</button>\n'
    '</form>\n\n'
    '<h2>2. 결과: 결과 해설</h2>\n'
    '<p>일 구직급여, 소정급여일수, 총 수령 예상액이 표시됩니다. '
    '예시: 평균 일급 100,000원, 35세, 가입 24개월인 경우 — 일 구직급여 64,192원(하한액 적용), '
    '소정급여일수 150일, 총 수령 예상액 9,628,800원.</p>'
)

# 3. 4대보험
FI_REMOVE = (
    '\n\n<h2>입력</h2>\n'
    '<p>아래 입력폼에 월급여를 입력해 주세요.</p>\n'
    '<form>\n'
    '    <label for="monthly_salary">월급여 (원): </label>\n'
    '    <input type="number" id="monthly_salary" name="monthly_salary" required>\n'
    '    <button type="submit">계산하기</button>\n'
    '</form>\n\n'
    '<h2>결과</h2>\n'
    '<p>결과는 아래와 같이 표시됩니다:</p>\n'
    '<ul>\n'
    '    <li>국민연금: <span id="national_pension">0</span> 원</li>\n'
    '    <li>건강보험: <span id="health_insurance">0</span> 원</li>\n'
    '    <li>장기요양보험: <span id="long_term_care">0</span> 원</li>\n'
    '    <li>고용보험: <span id="employment_insurance">0</span> 원</li>\n'
    '    <li>총 합계: <span id="total">0</span> 원</li>\n'
    '</ul>'
)

# 4. 연차수당
AL_REMOVE = (
    '\n\n<h2>계산기 입력폼 안내</h2>\n'
    '<p>아래 입력폼에 본인의 일급과 미사용 연차 일수를 입력해 주세요.</p>\n'
    '<form>\n'
    '    <label for="daily_wage">통상임금(일급, 원): </label>\n'
    '    <input type="number" id="daily_wage" name="daily_wage" required>\n'
    '    <br>\n'
    '    <label for="unused_days">미사용 연차 일수: </label>\n'
    '    <input type="number" id="unused_days" name="unused_days" required>\n'
    '    <br>\n'
    '    <button type="submit">계산하기</button>\n'
    '</form>\n\n'
    '<h2>결과 해설</h2>\n'
    '<p>입력한 통상임금(일급)과 미사용 연차 일수를 바탕으로 연차수당이 계산됩니다. '
    '예를 들어, 통상임금(일급)이 100,000원이고 미사용 연차가 5일이라면 연차수당은 500,000원이 됩니다. '
    '간편하게 계산을 통해 정확한 금액을 확인해 보세요.</p>'
)

# 5. 주휴수당 faq[2]
WH_FAQ2_OLD = "주휴수당은 시급에 주당 평균 근로시간의 비율을 곱하여 계산합니다. 공식은 '주휴수당 = 시급 x (주간 근무시간 / 40 x 8)'입니다."
WH_FAQ2_NEW = (
    "주휴수당은 시급에 주당 근무시간 비율(주간 근무시간 ÷ 40)을 곱한 뒤 8을 곱하여 산출합니다. "
    "예를 들어 시급 10,000원, 주 40시간 근무라면 주휴수당은 10,000원 × 1 × 8시간 = 80,000원이 됩니다. "
    "주 15시간 미만 근로자는 주휴수당이 발생하지 않습니다(근로기준법 제55조, 제18조)."
)

# ── 실행 ─────────────────────────────────────────────────────────────────────

print("=" * 60)
print(" SP-8 전수 감사 수정 시작")
print("=" * 60)

def get_calc(slug):
    return next((c for c in calcs if c.get("slug") == slug), None)

# ── 1. 주휴수당 article_content ───────────────────────────────────────────────
print("\n[1/5] 주휴수당 article_content 구 form 제거")
wh = get_calc("weekly-holiday-allowance")
wh_art = wh["article_content"]
wh_art = tracked_replace(wh_art, WH_REMOVE, "", "주휴수당 구 form+결과섹션")
repo.update(wh["id"], {"article_content": wh_art})
print("  ✔ DB 저장")

# ── 2. 실업급여 article_content ──────────────────────────────────────────────
print("\n[2/5] 실업급여 article_content 구 form 제거")
ub = get_calc("unemployment-benefit")
ub_art = ub["article_content"]
ub_art = tracked_replace(ub_art, UB_REMOVE, "", "실업급여 구 form+결과섹션")
repo.update(ub["id"], {"article_content": ub_art})
print("  ✔ DB 저장")

# ── 3. 4대보험 article_content ──────────────────────────────────────────────
print("\n[3/5] 4대보험 article_content 구 form 제거")
fi = get_calc("four-insurances")
fi_art = fi["article_content"]
fi_art = tracked_replace(fi_art, FI_REMOVE, "", "4대보험 구 form+결과ul섹션")
repo.update(fi["id"], {"article_content": fi_art})
print("  ✔ DB 저장")

# ── 4. 연차수당 article_content ──────────────────────────────────────────────
print("\n[4/5] 연차수당 article_content 구 form 제거")
al = get_calc("annual-leave-allowance")
al_art = al["article_content"]
al_art = tracked_replace(al_art, AL_REMOVE, "", "연차수당 구 form+결과섹션")
repo.update(al["id"], {"article_content": al_art})
print("  ✔ DB 저장")

# ── 5. 주휴수당 faq[2] 자연어 교체 ──────────────────────────────────────────
print("\n[5/5] 주휴수당 faq[2] 코드 공식 → 자연어 교체")
calcs = repo.get_all()  # DB 재조회
wh2 = get_calc("weekly-holiday-allowance")
faq = json.loads(wh2["faq"])
if faq[2]["answer"] != WH_FAQ2_OLD:
    raise ValueError(f"faq[2] 패턴 불일치:\n  실제={repr(faq[2]['answer'][:100])}")
faq[2]["answer"] = WH_FAQ2_NEW
repo.update(wh2["id"], {"faq": json.dumps(faq, ensure_ascii=False)})
print("  ✔ faq[2] 자연어 교체 완료")
print("  ✔ DB 저장")

# ── 6. workspace 재생성 + golden 갱신 ───────────────────────────────────────
print("\n[Workspace 재생성 + Golden 갱신]")
calcs = repo.get_all()
snap  = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

REGEN_TARGETS = [
    ("weekly-holiday-allowance", "weekly-holiday-allowance"),
    ("unemployment-benefit",     "unemployment-benefit"),
    ("four-insurances",          "four-insurances"),
    ("annual-leave-allowance",   "annual-leave-allowance"),
]
for slug, dname in REGEN_TARGETS:
    rec = next((c for c in calcs if c.get("slug") == slug), None)
    regen_workspace(rec, dname)
    update_snapshot(snap, dname)

SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("  ✔ calculator_snapshots.json 저장")

print("\n" + "=" * 60)
print(" SP-8 수정 완료 — 검증(_verify_sp8.py)을 실행하세요")
print("=" * 60)
