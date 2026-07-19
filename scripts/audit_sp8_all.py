# -*- coding: utf-8 -*-
"""SP-8 공통 패턴 전수 점검 (Verified Audit) — 6개 Verified 계산기 대상.

점검 항목:
  1. article_content 내 구 HTML form (<form>/<input> 태그)
  2. FAQ/article_content 코드 변수명 노출 (snake_case 변수)
  3. 계산식 raw formula 노출 (variable_name OP value 패턴)
  4. 구 예시 금액 잔존 (각 계산기별 known-bad 금액)
  5. 템플릿 placeholder/변수 노출 ({{...}}, ${...} 등)

산출물:
  - 계산기별 PASS/FAIL 표
  - 발견 패턴 상세 목록
  - "SP-8 Audit PASS" 또는 수정 필요 목록
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

ROOT      = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

cfg   = load_config()
db    = get_db_adapter(cfg)
repo  = CalculatorRepository(db)
calcs = repo.get_all()

# ── 감사 대상 ─────────────────────────────────────────────────────────────────
TARGETS = [
    ("weekly-holiday-allowance", "주휴수당",   "weekly-holiday-allowance"),
    ("severance-pay",            "퇴직금",     "severance-pay"),
    ("unemployment-benefit",     "실업급여",   "unemployment-benefit"),
    ("four-insurances",          "4대보험",    "four-insurances"),
    ("annual-leave-allowance",   "연차수당",   "annual-leave-allowance"),
    ("육아휴직_급여_계산기",       "육아휴직",   "육아휴직_급여_계산기"),
]

# ── 패턴 정의 ─────────────────────────────────────────────────────────────────

# 1. 구 HTML form 패턴 — article_content 내 잔존 여부
FORM_PATTERNS = [
    (r'<form[\s>]', "구 <form> 태그"),
    (r'<input[^>]+(?:id|name)=["\'][a-z_]+["\']', "구 <input id/name> 태그"),
]

# 2. 코드 변수명 — snake_case + 계산기별 known-bad 목록
# "variable_name" 형태가 FAQ 답변 또는 article_content 순수 텍스트에 노출되면 bad
# 계산기 본체(input/JS)에서는 정당하게 사용하므로 DB+article 섹션만 검사
GLOBAL_CODE_VARS = [
    # 육아휴직 구 변수 (Phase 3에서 제거)
    "avg_monthly_wage",
    "government_support_percentage",
    "company_policy_support_percentage",
    "leave_months",
    # 일반 공식 잔재
    "total_days",
    "daily_benefit",
    "avg_daily_wage",
    "monthly_salary",
    "hourly_wage",
    "weekly_hours",
    "daily_wage",
    "unused_days",
    "monthly_wage",
    "insured_days",
    "employment_months",
]

# 3. raw formula 노출 패턴 — 코드 표현식이 사용자 텍스트에 노출
# e.g., "avg_monthly_wage * leave_months", "total_days / 365"
RAW_FORMULA_PATTERNS = [
    (r'[a-z_]{3,}\s*[\*\/\+\-]\s*[a-z_0-9.]{1,}', "raw formula (변수 OP 값/변수)"),
    (r"공식은\s*['\"`].*?[a-z_].*?['\"`]", "공식은 '...' 코드식"),
]

# 4. 계산기별 known-bad 예시 금액
KNOWN_BAD_AMOUNTS = {
    "weekly-holiday-allowance":  [],  # 특정 bad amount 없음
    "severance-pay":             [],  # 구 form 제거됨, bad amount 없음
    "unemployment-benefit":      ["최대 300일"],  # UB-2에서 제거됨
    "four-insurances":           ["106,500"],  # FI-6에서 교정됨 (106,350이 맞음)
    "annual-leave-allowance":    [],
    "육아휴직_급여_계산기":         ["14,400,000"],  # Phase 3에서 제거됨
}

# 5. 템플릿 placeholder 패턴
TEMPLATE_PATTERNS = [
    (r'\{\{[^}]+\}\}', "{{...}} 템플릿 변수"),
    (r'\$\{[^}]+\}',   "${...} JS 템플릿 변수"),
    (r'%\{[^}]+\}',    "%{...} 템플릿 변수"),
    (r'__[A-Z_]+__',   "__VAR__ 스타일 변수"),
]

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def extract_article(html: str) -> str:
    m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
    return m.group(1) if m else ""

def extract_faq_section(html: str) -> str:
    # FAQ accordion section
    m = re.search(r'class="[^"]*faq[^"]*"[^>]*>(.*?)</section>', html, re.DOTALL)
    return m.group(1) if m else ""

def find_hits(text: str, patterns, label_prefix="") -> list:
    """Returns list of (label, excerpt) for each hit."""
    hits = []
    for pat, desc in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            excerpt = text[max(0, m.start()-20):m.end()+30].replace("\n", " ")
            hits.append((f"{label_prefix}{desc}", repr(excerpt.strip())))
    return hits

# ── 메인 감사 루프 ─────────────────────────────────────────────────────────────

print("=" * 70)
print(" SP-8 Verified Audit — 6개 계산기 전수 점검")
print("=" * 70)

summary = {}  # slug → {pass: bool, issues: []}

for slug, name, dir_name in TARGETS:
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        print(f"\n  ⚠️  [{name}] DB 없음 — 스킵")
        continue

    issues = []

    # DB 소스
    faq_json     = calc.get("faq") or "[]"
    art_content  = calc.get("article_content") or ""
    faq_list     = json.loads(faq_json)
    faq_answers  = " ".join(f.get("answer", "") for f in faq_list)

    # workspace HTML
    html_path = WORKSPACE / dir_name / "index.html"
    html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    article_html = extract_article(html)
    faq_html     = extract_faq_section(html)

    # ── 검사 1: 구 HTML form in article_content ──
    for pat, desc in FORM_PATTERNS:
        for m in re.finditer(pat, art_content, re.IGNORECASE):
            ex = art_content[max(0, m.start()-10):m.end()+40].replace("\n", " ")
            issues.append(("HTML Form", desc, repr(ex.strip())))
        # article 섹션에서도
        for m in re.finditer(pat, article_html, re.IGNORECASE):
            ex = article_html[max(0, m.start()-10):m.end()+40].replace("\n", " ")
            issues.append(("HTML Form (article)", desc, repr(ex.strip())))

    # ── 검사 2: 코드 변수명 노출 in DB ──
    for var in GLOBAL_CODE_VARS:
        # DB faq answers
        if var in faq_answers:
            idx = faq_answers.find(var)
            ex  = faq_answers[max(0,idx-15):idx+len(var)+30].replace("\n"," ")
            issues.append(("코드 변수명 (DB faq)", var, repr(ex.strip())))
        # article_content
        if var in art_content:
            idx = art_content.find(var)
            ex  = art_content[max(0,idx-15):idx+len(var)+30].replace("\n"," ")
            issues.append(("코드 변수명 (DB article)", var, repr(ex.strip())))
        # article HTML 섹션
        if var in article_html:
            idx = article_html.find(var)
            ex  = article_html[max(0,idx-15):idx+len(var)+30].replace("\n"," ")
            issues.append(("코드 변수명 (HTML article)", var, repr(ex.strip())))
        # FAQ HTML 섹션
        if var in faq_html:
            idx = faq_html.find(var)
            ex  = faq_html[max(0,idx-15):idx+len(var)+30].replace("\n"," ")
            issues.append(("코드 변수명 (HTML faq)", var, repr(ex.strip())))

    # ── 검사 3: raw formula 노출 ──
    for src_name, src_text in [("DB faq", faq_answers), ("DB article", art_content),
                                ("HTML article", article_html), ("HTML faq", faq_html)]:
        hits = find_hits(src_text, RAW_FORMULA_PATTERNS, label_prefix=f"({src_name}) ")
        for label, ex in hits:
            issues.append(("Raw Formula", label, ex))

    # ── 검사 4: known-bad 금액 ──
    bad_amounts = KNOWN_BAD_AMOUNTS.get(slug, [])
    for amount in bad_amounts:
        for src_name, src_text in [("DB faq", faq_answers), ("DB article", art_content),
                                    ("HTML article", article_html), ("HTML faq", faq_html)]:
            if amount in src_text:
                idx = src_text.find(amount)
                ex  = src_text[max(0,idx-20):idx+len(amount)+30].replace("\n"," ")
                issues.append(("Known-bad 금액", f"({src_name}) '{amount}'", repr(ex.strip())))

    # ── 검사 5: 템플릿 placeholder ──
    for src_name, src_text in [("DB faq", faq_answers), ("DB article", art_content),
                                ("HTML article", article_html), ("HTML faq", faq_html)]:
        hits = find_hits(src_text, TEMPLATE_PATTERNS, label_prefix=f"({src_name}) ")
        for label, ex in hits:
            issues.append(("Template Var", label, ex))

    summary[slug] = {"name": name, "issues": issues}

# ── 출력 ─────────────────────────────────────────────────────────────────────
print()
print(f"{'계산기':<20} {'상태':<8} {'이슈 수'}")
print("-" * 50)

all_pass = True
for slug, name, _ in TARGETS:
    if slug not in summary:
        continue
    info   = summary[slug]
    issues = info["issues"]
    ok     = len(issues) == 0
    if not ok:
        all_pass = False
    status = "✅ PASS" if ok else f"❌ FAIL({len(issues)}건)"
    print(f"  {info['name']:<18} {status}")

print()
if all_pass:
    print("=" * 70)
    print(" SP-8 Audit: ✅ ALL PASS — 6개 계산기 전체 공통 템플릿 잔재 없음")
    print("=" * 70)
else:
    print("=" * 70)
    print(" SP-8 Audit: ❌ 발견 패턴 있음 — 상세 내역:")
    print("=" * 70)
    for slug, name, _ in TARGETS:
        if slug not in summary:
            continue
        issues = summary[slug]["issues"]
        if not issues:
            continue
        print(f"\n  [{summary[slug]['name']} / {slug}]")
        for category, label, excerpt in issues:
            print(f"    [{category}] {label}")
            print(f"      → {excerpt[:120]}")
