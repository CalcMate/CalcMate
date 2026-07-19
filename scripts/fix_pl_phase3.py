# -*- coding: utf-8 -*-
"""Phase 3 — 콘텐츠 최종 정리 + 템플릿 오염 제거.

수정 대상:
  [A] 육아휴직_급여_계산기
      - faq[2].answer: 코드 변수명 4종 → 자연어 + 실제 계산 예시
      - article_content: 구 HTML Form 제거 / 구 계산 원리(14,400,000원) 교체 / article FAQ[2] 업데이트
  [B] severance-pay (grep 결과 동일 패턴)
      - faq[2].answer: 'avg_monthly_wage * (total_days / 365)' → 자연어
      - article_content: 구 HTML Form + 결과 섹션 제거

계산 예시: Python mirror 함수 실행 결과 사용 (수기 계산 금지).
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
WORKSPACE = ROOT / "data" / "workspace"
SNAPSHOT_PATH = ROOT / "tests" / "golden" / "calculator_snapshots.json"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()

# ── 0. 계산 예시 (Phase 2 Python mirror — test_parental_leave_compute.py 동일 상수) ──
GEN_RATE  = 0.80
GEN_CEIL  = 1_500_000
GEN_FLOOR = 700_000
SP_CEILINGS = [2_000_000, 2_500_000, 3_000_000, 3_500_000, 4_000_000, 4_500_000]

def _pl_ex(wage, use_sp, month):
    raw   = wage * (1.00 if use_sp else GEN_RATE)
    ceil  = SP_CEILINGS[month - 1] if use_sp else GEN_CEIL
    return {"raw": round(raw), "applied": round(min(max(raw, GEN_FLOOR), ceil)), "ceiling": ceil}

ex1 = _pl_ex(3_000_000, 0, 1)   # 일반 300만
ex2 = _pl_ex(1_800_000, 0, 1)   # 일반 180만
ex3 = _pl_ex(3_000_000, 1, 1)   # 6+6 1개월 300만
ex4 = _pl_ex(2_500_000, 1, 3)   # 6+6 3개월 250만

assert ex1 == {"raw": 2_400_000, "applied": 1_500_000, "ceiling": 1_500_000}, ex1
assert ex2 == {"raw": 1_440_000, "applied": 1_440_000, "ceiling": 1_500_000}, ex2
assert ex3 == {"raw": 3_000_000, "applied": 2_000_000, "ceiling": 2_000_000}, ex3
assert ex4 == {"raw": 2_500_000, "applied": 2_500_000, "ceiling": 3_000_000}, ex4

sp_wage, sp_days = 3_000_000, 730
sp_result = round(sp_wage * (sp_days / 365))
assert sp_result == 6_000_000, sp_result

print("=" * 60)
print(" 0. 예시 계산 검증 PASS")
print("=" * 60)
print(f"  [육아휴직] 일반 300만 → {ex1['applied']:,}원 (상한 {ex1['ceiling']:,}원 적용)")
print(f"  [육아휴직] 일반 180만 → {ex2['applied']:,}원")
print(f"  [육아휴직] 6+6 1개월 300만 → {ex3['applied']:,}원 (1개월 상한 {ex3['ceiling']:,}원 적용)")
print(f"  [육아휴직] 6+6 3개월 250만 → {ex4['applied']:,}원 (3개월 상한 {ex4['ceiling']:,}원 미달)")
print(f"  [퇴직금]   {sp_wage:,}원×{sp_days}일 → {sp_result:,}원")
print()

# ── helper ────────────────────────────────────────────────────────────────────
def tracked_replace(text, old, new, label, required=True):
    cnt = text.count(old)
    if cnt == 0:
        if required:
            for kw in old.split()[:3]:
                idx = text.find(kw)
                if idx >= 0:
                    print(f"    [debug] '{kw}' at {idx}: {repr(text[max(0,idx-20):idx+50])}")
            print(f"  ❌ {label}: 패턴 미발견 — 스크립트 중단")
            raise ValueError(f"패턴 없음: {label!r}")
        else:
            print(f"  [SKIP] {label}: 이미 수정됨")
            return text
    text = text.replace(old, new)
    print(f"  [OK] {label}: {cnt}곳 교체")
    return text

def regen_workspace(calc_rec, slug_dir_name):
    out_dir = WORKSPACE / slug_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    result = generate_calculator(calc_rec, cfg)
    for fname, content in result.items():
        if not isinstance(content, str):
            continue
        (out_dir / fname).write_text(content, encoding="utf-8")
    return out_dir

def update_snapshot(snap, slug, out_dir):
    if slug not in snap:
        snap[slug] = {}
    for fname in ["script.js", "index.html", "style.css"]:
        fpath = out_dir / fname
        if not fpath.exists():
            continue
        new_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
        old_hash = snap[slug].get(fname, "없음")
        snap[slug][fname] = new_hash
        changed = "변경" if old_hash != new_hash else "동일"
        print(f"  [{changed}] {slug}/{fname}: {str(old_hash)[:12]}... → {new_hash[:12]}...")

# ── 새 텍스트 ────────────────────────────────────────────────────────────────
NEW_PL_FAQ2 = (
    f"육아휴직급여는 통상임금(기본급과 고정수당을 합산한 월 임금)을 기준으로 "
    f"제도별 지급률을 적용하여 계산됩니다. "
    f"일반 육아휴직급여는 통상임금의 80%(상한 {GEN_CEIL:,}원/월, 하한 {GEN_FLOOR:,}원/월), "
    f"6+6 부모 육아휴직 특례는 통상임금의 100%(개월수별 상한, 7개월부터 일반 전환)가 "
    f"적용됩니다(고용보험법 시행령 제95조·제95조의2). "
    f"예시: 통상임금 300만원 기준으로 일반은 상한 적용 후 월 {ex1['applied']:,}원, "
    f"6+6 특례 1개월차는 1개월 상한 적용 후 월 {ex3['applied']:,}원입니다."
)

NEW_CALC_SECTION = (
    "\n\n<h2>계산 원리</h2>\n"
    "<p>육아휴직급여는 통상임금(기본급과 고정수당을 합산한 월 임금)을 기준으로 "
    "제도별 지급률과 상한·하한을 적용하여 산정됩니다.</p>\n"
    "<ul>\n"
    "    <li><strong>일반 육아휴직급여</strong>: 통상임금 × 80%, "
    f"상한 {GEN_CEIL:,}원/월, 하한 {GEN_FLOOR:,}원/월 "
    "(고용보험법 시행령 제95조)</li>\n"
    "    <li><strong>6+6 부모 육아휴직 특례</strong>(2024년 1월 시행): "
    "통상임금 × 100%, 개월수별 상한 1개월 200만원~6개월 450만원. "
    "7개월부터 일반 전환(고용보험법 시행령 제95조의2)</li>\n"
    "</ul>\n\n"
    "<h2>계산 예시</h2>\n"
    "<ul>\n"
    f"    <li><strong>일반 / 통상임금 300만원</strong>: "
    f"3,000,000원 × 80% = {ex1['raw']:,}원 → 상한({ex1['ceiling']:,}원) 적용 → 월 {ex1['applied']:,}원</li>\n"
    f"    <li><strong>일반 / 통상임금 180만원</strong>: "
    f"1,800,000원 × 80% = 월 {ex2['applied']:,}원</li>\n"
    f"    <li><strong>6+6 특례 1개월차 / 통상임금 300만원</strong>: "
    f"3,000,000원 × 100% = {ex3['raw']:,}원 → 1개월 상한({ex3['ceiling']:,}원) 적용 → 월 {ex3['applied']:,}원</li>\n"
    f"    <li><strong>6+6 특례 3개월차 / 통상임금 250만원</strong>: "
    f"2,500,000원 × 100% = 월 {ex4['applied']:,}원 "
    f"(3개월 상한 {ex4['ceiling']:,}원 미달)</li>\n"
    "</ul>"
)

NEW_ART_FAQ2_TEXT = (
    "육아휴직급여는 통상임금(기본급과 고정수당을 합산한 월 임금)을 기준으로 "
    "제도별 지급률을 적용하여 계산됩니다. "
    "일반 육아휴직급여는 통상임금의 80%(상한 150만원/월, 하한 70만원/월), "
    "6+6 부모 육아휴직 특례는 통상임금의 100%(개월수별 상한, 7개월부터 일반 전환)가 "
    "적용됩니다(고용보험법 시행령 제95조·제95조의2). "
    f"예시: 통상임금 300만원 기준으로 일반은 상한 적용 후 월 {ex1['applied']:,}원, "
    f"6+6 특례 1개월차는 1개월 상한 적용 후 월 {ex3['applied']:,}원입니다."
)

# ══════════════════════════════════════════════════════════════════════════════
# A. 육아휴직급여 계산기
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print(" A. 육아휴직_급여_계산기")
print("=" * 60)

pl = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)
assert pl, "육아휴직_급여_계산기 없음"
pl_id = pl["id"]

# A-1. faq[2] 교체
faq = json.loads(pl.get("faq") or "[]")
old_faq2 = faq[2]["answer"]
assert "avg_monthly_wage" in old_faq2, f"faq[2] 코드 변수명 없음(이미 수정됨?): {old_faq2[:80]}"
print(f"  faq[2] 이전: {old_faq2[:80]}...")
faq[2]["answer"] = NEW_PL_FAQ2
print(f"  faq[2] 이후: {faq[2]['answer'][:80]}...")

# A-2. article_content 수정
art = pl.get("article_content") or ""

OLD_INTRO = (
    "육아휴직 급여 계산기로 월 평균 임금과 휴직 기간을 입력하고 정확한 급여를 예측하세요. "
    "국가 지원금과 회사 정책적 지원금을 포함하여 최대한 정확한 금액을 확인할 수 있습니다."
)
NEW_INTRO = (
    "통상임금과 피보험단위기간, 6+6 특례 해당 여부를 입력하면 예상 월 육아휴직급여를 "
    "자동으로 계산합니다. 일반 육아휴직급여와 6+6 부모 육아휴직 특례(2024년 1월 시행)를 모두 지원합니다."
)
art = tracked_replace(art, OLD_INTRO, NEW_INTRO, "intro 문단")

# A-2b. 구 HTML Form + 결과 섹션 제거 (두 줄 개행 포함)
OLD_FORM_BLOCK = (
    "\n\n<h2>입력</h2>\n"
    "<p>아래의 입력 폼에 월 평균 임금, 휴직 기간, 정부 지원 비율, 회사 정책 지원 비율을 입력하세요.</p>\n"
    "<form>\n"
    "    <label for=\"avg_monthly_wage\">월 평균 임금 (원):</label>\n"
    "    <input type=\"number\" id=\"avg_monthly_wage\" name=\"avg_monthly_wage\"><br>\n"
    "    \n"
    "    <label for=\"leave_months\">휴직 기간 (개월):</label>\n"
    "    <input type=\"number\" id=\"leave_months\" name=\"leave_months\"><br>\n"
    "    \n"
    "    <label for=\"government_support_percentage\">정부 지원 비율 (%):</label>\n"
    "    <input type=\"number\" id=\"government_support_percentage\" name=\"government_support_percentage\"><br>\n"
    "    \n"
    "    <label for=\"company_policy_support_percentage\">회사 정책 지원 비율 (%):</label>\n"
    "    <input type=\"number\" id=\"company_policy_support_percentage\" name=\"company_policy_support_percentage\"><br>\n"
    "    \n"
    "    <input type=\"submit\" value=\"계산하기\">\n"
    "</form>\n\n"
    "<h2>결과</h2>\n"
    "<p>입력하신 기준에 따라 육아휴직 급여가 계산됩니다. 정확한 수치가 필요합니다.</p>"
)
art = tracked_replace(art, OLD_FORM_BLOCK, "", "구 HTML Form + 결과 섹션")

# A-2c. 구 계산 원리 → 새 계산 원리 + 예시 (두 줄 개행 포함)
OLD_CALC = (
    "\n\n<h2>계산 원리</h2>\n"
    "<p>육아휴직 급여는 근로자가 육아휴직을 사용할 때 받게 되는 급여를 의미합니다. "
    "이 급여는 사용자가 입력한 월 평균 임금에 휴직 개월 수를 곱한 다음, "
    "정부에서 지원하는 비율과 회사에서 제공하는 정책 지원 비율을 더하여 최종 급여를 도출합니다. "
    "예를 들어, 월 평균 임금이 3,000,000원이고, 휴직 기간이 6개월, 정부 지원 비율이 50%, "
    "회사 지원 비율이 30%일 경우, 계산식은 다음과 같습니다. "
    "여기서 총 지원 비율은 80%가 되어, 3,000,000원의 6개월치에 해당하는 "
    "18,000,000원을 80%로 계산하면 최종 급여는 14,400,000원이 됩니다.</p>"
)
art = tracked_replace(art, OLD_CALC, NEW_CALC_SECTION, "구 계산 원리 → 새 계산 원리+예시")

# A-2d. article FAQ[2] — 구 방식 설명 → Phase 2 설명 (C-13)
OLD_ART_FAQ2 = (
    "<li><strong>육아휴직 급여는 어떻게 계산되나요?</strong><br>\n"
    "    육아휴직 급여는 월 평균 임금에 휴직 개월 수를 곱한 후, "
    "국가 지원 비율과 회사 지원 비율을 더하여 최종 금액을 계산합니다.</li>"
)
NEW_ART_FAQ2 = (
    "<li><strong>육아휴직급여는 어떻게 계산되나요?</strong><br>\n"
    "    " + NEW_ART_FAQ2_TEXT + "</li>"
)
art = tracked_replace(art, OLD_ART_FAQ2, NEW_ART_FAQ2, "article FAQ[2] 구 설명 → Phase 2 설명")

# A-3. DB 저장
repo.update(pl_id, {
    "faq": json.dumps(faq, ensure_ascii=False),
    "article_content": art,
})
print("  [OK] DB 저장 완료")

# A-4. workspace 재생성
pl_updated = repo.get_by_id(pl_id)
out_dir_pl = regen_workspace(pl_updated, "육아휴직_급여_계산기")
print("  [OK] workspace 재생성 완료")

# ══════════════════════════════════════════════════════════════════════════════
# B. severance-pay
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(" B. severance-pay")
print("=" * 60)

sp_calc = next((c for c in calcs if c.get("slug") == "severance-pay"), None)
assert sp_calc, "severance-pay 없음"
sp_id = sp_calc["id"]

# B-1. faq[2] 교체
sp_faq = json.loads(sp_calc.get("faq") or "[]")
sp_faq2_idx = next(
    (i for i, f in enumerate(sp_faq) if "avg_monthly_wage" in f.get("answer", "")),
    None
)
if sp_faq2_idx is None:
    print("  [SKIP] faq — 코드 변수명 이미 제거됨")
else:
    old_sp_faq2 = sp_faq[sp_faq2_idx]["answer"]
    print(f"  faq[{sp_faq2_idx}] 이전: {old_sp_faq2[:80]}...")
    sp_faq[sp_faq2_idx]["answer"] = (
        f"퇴직금은 평균임금에 총 근무일수를 365로 나눈 값을 곱하여 계산합니다"
        f"(근로자퇴직급여보장법 제8조). 공식: 평균임금 × (총 근무일수 ÷ 365). "
        f"예시: 평균 월임금 {sp_wage:,}원으로 2년({sp_days}일) 근무 시 → "
        f"{sp_wage:,} × ({sp_days} ÷ 365) = {sp_result:,}원."
    )
    print(f"  faq[{sp_faq2_idx}] 이후: {sp_faq[sp_faq2_idx]['answer'][:80]}...")

# B-2. article_content — 구 HTML Form + 결과 섹션 제거 (연속 블록)
sp_art = sp_calc.get("article_content") or ""

OLD_SP_BLOCK = (
    "\n\n<h2>퇴직금 계산기 입력폼 안내</h2>\n"
    "<p>아래의 입력폼에 정보를 입력해 주세요.</p>\n"
    "<ul>\n"
    "    <li><strong>평균 월급 (원):</strong> 매달 받는 평균 급여를 입력합니다.</li>\n"
    "    <li><strong>입사일:</strong> 근무를 시작한 날짜를 선택합니다.</li>\n"
    "    <li><strong>퇴사일:</strong> 근무를 마친 날짜를 선택합니다.</li>\n"
    "</ul>\n\n"
    "<form>\n"
    "    <label for=\"avg_monthly_wage\">평균 월급:</label>\n"
    "    <input type=\"number\" id=\"avg_monthly_wage\" required>\n"
    "    \n"
    "    <label for=\"start_date\">입사일:</label>\n"
    "    <input type=\"date\" id=\"start_date\" required>\n"
    "    \n"
    "    <label for=\"end_date\">퇴사일:</label>\n"
    "    <input type=\"date\" id=\"end_date\" required>\n"
    "    \n"
    "    <button type=\"submit\">퇴직금 계산</button>\n"
    "</form>\n\n"
    "<h2>퇴직금 계산 결과</h2>\n"
    "<p>계산된 퇴직금은 사용자가 입력한 평균 월급과 근무일수에 따라 달라집니다. "
    "정확한 결과는 입력한 데이터에 따라 달라질 수 있습니다.</p>"
)
sp_art = tracked_replace(sp_art, OLD_SP_BLOCK, "", "구 HTML Form + 결과 섹션 (연속)")

# B-3. DB 저장
repo.update(sp_id, {
    "faq": json.dumps(sp_faq, ensure_ascii=False),
    "article_content": sp_art,
})
print("  [OK] DB 저장 완료")

# B-4. workspace 재생성
sp_updated = repo.get_by_id(sp_id)
out_dir_sp = regen_workspace(sp_updated, "severance-pay")
print("  [OK] workspace 재생성 완료")

# ══════════════════════════════════════════════════════════════════════════════
# C. Golden 스냅샷 갱신
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(" C. Golden 스냅샷 갱신")
print("=" * 60)
snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
update_snapshot(snap, "육아휴직_급여_계산기", out_dir_pl)
update_snapshot(snap, "severance-pay", out_dir_sp)
SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("  [OK] 스냅샷 파일 저장")

# ══════════════════════════════════════════════════════════════════════════════
# D. 검증
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(" D. 검증 (FORBIDDEN 패턴 0건)")
print("=" * 60)

pl_final  = repo.get_by_id(pl_id)
sp_final  = repo.get_by_id(sp_id)
pl_html   = (out_dir_pl / "index.html").read_text(encoding="utf-8")
sp_html   = (out_dir_sp / "index.html").read_text(encoding="utf-8")
pl_db_str = json.dumps({"faq": pl_final.get("faq"), "art": pl_final.get("article_content")}, ensure_ascii=False)
sp_db_str = json.dumps({"faq": sp_final.get("faq"), "art": sp_final.get("article_content")}, ensure_ascii=False)

# 퇴직금 index.html: <article>…</article> 내부만 추출 (계산기 form/JS는 정당한 avg_monthly_wage 사용)
import re as _re
sp_article_match = _re.search(r'<article[^>]*>(.*?)</article>', sp_html, _re.DOTALL)
sp_article_html  = sp_article_match.group(1) if sp_article_match else ""
sp_faq_match     = _re.search(r'<section[^>]*class="[^"]*faq[^"]*"[^>]*>(.*?)</section>', sp_html, _re.DOTALL)
sp_faq_html      = sp_faq_match.group(1) if sp_faq_match else ""

# 육아휴직은 전체 HTML (avg_monthly_wage 0건이어야 함)
FORBIDDEN_ALL = [
    "government_support_percentage",
    "company_policy_support_percentage",
    "leave_months",
    "14,400,000",
]
FORBIDDEN_PL_ONLY = [
    "avg_monthly_wage",  # 퇴직금 계산기는 정당하게 사용 — DB/article만 검사
]
FORBIDDEN_SP_DB = [
    "avg_monthly_wage",  # 퇴직금 DB(faq+article)에서만
    "total_days / 365",  # JS 코드 표현 (DB에 노출 안 돼야 함)
]

sources_all = {
    "육아휴직 index.html": pl_html,
    "육아휴직 DB":         pl_db_str,
    "퇴직금 DB":           sp_db_str,
    "퇴직금 article 섹션": sp_article_html,
    "퇴직금 FAQ 섹션":     sp_faq_html,
}

fail = False
for phrase in FORBIDDEN_ALL:
    for src_name, src_text in sources_all.items():
        cnt = src_text.count(phrase)
        if cnt > 0:
            print(f"  ❌ [{src_name}] '{phrase}': {cnt}건 잔존")
            fail = True

for phrase in FORBIDDEN_PL_ONLY:
    for src_name, src_text in {"육아휴직 index.html": pl_html, "육아휴직 DB": pl_db_str}.items():
        cnt = src_text.count(phrase)
        if cnt > 0:
            print(f"  ❌ [{src_name}] '{phrase}': {cnt}건 잔존")
            fail = True

for phrase in FORBIDDEN_SP_DB:
    for src_name, src_text in {
        "퇴직금 DB": sp_db_str,
        "퇴직금 article 섹션": sp_article_html,
        "퇴직금 FAQ 섹션": sp_faq_html,
    }.items():
        cnt = src_text.count(phrase)
        if cnt > 0:
            print(f"  ❌ [{src_name}] '{phrase}': {cnt}건 잔존")
            fail = True

if not fail:
    print("  ✅ 모든 FORBIDDEN 패턴 0건")

# C-13 일관성
pl_faq2_txt = json.loads(pl_final.get("faq") or "[]")[2]["answer"]
pl_art_txt  = pl_final.get("article_content") or ""
c13_kw1 = "통상임금의 80%"
c13_kw2 = "통상임금의 100%"
c13_ok = (
    c13_kw1 in pl_faq2_txt and c13_kw2 in pl_faq2_txt and
    c13_kw1 in pl_art_txt  and c13_kw2 in pl_art_txt  and
    "avg_monthly_wage" not in pl_faq2_txt and
    "avg_monthly_wage" not in pl_art_txt
)
print(f"\n  C-13 일관성 (faq⟺article 80%/100% 일치): {'✅ PASS' if c13_ok else '❌ FAIL'}")
if not c13_ok:
    print(f"    faq[2] kw1={c13_kw1 in pl_faq2_txt}, kw2={c13_kw2 in pl_faq2_txt}")
    print(f"    art    kw1={c13_kw1 in pl_art_txt},  kw2={c13_kw2 in pl_art_txt}")
    print(f"    no var faq={('avg_monthly_wage' not in pl_faq2_txt)}, art={('avg_monthly_wage' not in pl_art_txt)}")

print()
if fail or not c13_ok:
    sys.exit(1)

print("=== Phase 3 완료. 다음: pytest tests/ ===")
