# -*- coding: utf-8 -*-
"""
modules/app_generator.py — 계산기 정적 앱(HTML/CSS/JS) 생성기 (SalaryMate)

calculators 메타데이터로 index.html / style.css / script.js 생성(GitHub Pages 배포용).
- UI: templates/calculators/calculator_v1.html (모든 계산기 동일 UI, 변수 치환)
- 입력폼: calculator_form_engine (input_schema 없으면 자동 생성)
- 노출 정책: site_mode_manager (광고/관련계산기/공유/리포트)
- 수식: formula_engine 정의를 클라이언트 JS로 변환

데이터 접근은 Repository 경유. 기존 호출 호환: generate_calculator(calc) (cfg 선택).
"""
import html as _html
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import yaml

from .formula_engine import validate_formula

_log = logging.getLogger(__name__)
_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

_TPL = Path(__file__).resolve().parent.parent / "templates" / "calculators" / "calculator_v1.html"

# _LABELS 제거 (P2-2-C) — 모든 레이블은 registry v3 field_labels에서 공급됨.
_JS_FUNCS = {"min": "Math.min", "max": "Math.max", "round": "Math.round",
             "abs": "Math.abs", "int": "Math.trunc", "float": "Number"}

# Phase C: 입력폼 예시값 (placeholder)
_PLACEHOLDERS = {
    "hourly_wage": "10030", "weekly_hours": "40",
    "daily_wage": "67000",  "unused_days": "5",
    "avg_monthly_wage": "3000000", "avg_daily_wage": "100000",
    "monthly_salary": "3000000", "monthly_wage": "3000000",
    "age": "35", "employment_months": "24",
    "total_salary": "40000000", "family_count": "1", "paid_tax": "1000000",
    "insured_days": "365", "leave_month": "1", "use_6plus6": "0",
}

# STEP 16-Y/17-D: 계산기별 결과 안내(NOTICE) 문구. 공용 기본값("...근로계약...")이
# 노무/급여 외 분야(부동산·세금 등)에 부적절하고, 같은 노무/급여 분야에서도
# 계산기마다 실제 결과를 좌우하는 핵심 개념이 달라(퇴직금=평균임금,
# 연차수당=통상임금 등) 계산기별 최소 문구로 교체한다. 여기 없는 slug는
# 아래 fallback 문구를 그대로 사용해 다른 계산기에는 영향 없다.
_NOTICE_BY_SLUG: dict = {
    "real-estate-brokerage-fee": "본 계산 결과는 참고용이며, 실제 중개보수는 거래 유형·거래금액 및 관련 법령에서 정한 상한요율에 따라 달라질 수 있습니다.",
    "severance-pay": "본 계산 결과는 참고용이며, 실제 퇴직금은 평균임금 산정 방식 및 관련 법령에 따라 달라질 수 있습니다.",
    "annual-leave-allowance": "본 계산 결과는 참고용이며, 실제 연차수당은 통상임금 산정 방식 및 관련 법령에 따라 달라질 수 있습니다.",
    "weekly-holiday-allowance": "본 계산 결과는 참고용이며, 실제 주휴수당은 소정근로시간 및 관련 법령에 따라 달라질 수 있습니다.",
    "unemployment-benefit": "본 계산 결과는 참고용이며, 실제 수급액은 이직 사유·수급자격 판정 및 관련 법령에 따라 달라질 수 있습니다.",
    "four-insurances": "본 계산 결과는 참고용이며, 실제 공제액은 매년 고시되는 보험료율 및 관련 법령에 따라 달라질 수 있습니다.",
    "연말정산_환급액_계산기": "본 계산 결과는 참고용이며, 실제 환급액(또는 납부액)은 소득·공제 항목 및 관련 세법 적용에 따라 달라질 수 있습니다.",
    "육아휴직_급여_계산기": "본 계산 결과는 참고용이며, 실제 육아휴직 급여는 통상임금 및 관련 법령에 따라 달라질 수 있습니다.",
    "freelancer-tax-3p3": "본 계산 결과는 참고용이며, 실제 세액은 소득 규모 및 관련 세법 적용에 따라 달라질 수 있습니다.",
    "jeonse-vs-monthly": "본 계산 결과는 참고용이며, 실제 유불리는 전월세전환율 등 시장 조건에 따라 달라질 수 있습니다.",
    "annual-leave-remaining": "본 계산 결과는 참고용이며, 실제 연차일수는 출근율 및 관련 법령에 따라 달라질 수 있습니다.",
}

# Phase C: 계산기별 관련 글 데이터 (정적, 계산기 지원용 블로그 Set)
_RELATED_POSTS = {
    "weekly-holiday-allowance": [
        {"tag": "노무", "title": "주휴수당 완벽 가이드 — 지급 조건부터 계산법까지",
         "desc": "주 15시간 이상 근무 시 주휴수당 발생 조건과 계산법을 상세히 설명합니다.",
         "href": "/blog/weekly-holiday-allowance-guide/"},
        {"tag": "노무", "title": "최저시급으로 주휴수당 계산하는 방법 (2026년)",
         "desc": "2026년 최저임금 기준 주휴수당 계산 예시와 실수령액을 정리합니다.",
         "href": "/blog/minimum-wage-weekly-holiday/"},
    ],
    "severance-pay": [
        {"tag": "퇴직", "title": "퇴직금 계산법 완벽 정리 — 평균임금 산정부터 지급까지",
         "desc": "근로자퇴직급여 보장법 제8조 기준 퇴직금 계산 방법을 상세히 설명합니다.",
         "href": "/blog/severance-pay-guide/"},
        {"tag": "퇴직", "title": "퇴직금 받고 실업급여 신청하는 방법 — 연계 절차",
         "desc": "퇴직금 수령 후 실업급여 신청까지 필요한 서류와 절차를 안내합니다.",
         "href": "/blog/severance-unemployment-benefit/"},
    ],
    "annual-leave-allowance": [
        {"tag": "연차", "title": "연차수당 계산법과 사용 촉진 제도 — 수당 면제 조건",
         "desc": "미사용 연차수당 계산과 사용촉진제도에 따른 수당 면제 조건을 설명합니다.",
         "href": "/blog/annual-leave-allowance-guide/"},
        {"tag": "연차", "title": "연차 25일 상한 제도 — 초과 연차의 법적 처리 방법",
         "desc": "법정 최대 연차 25일을 초과하는 경우 처리 방법과 수당 계산을 안내합니다.",
         "href": "/blog/annual-leave-limit-25days/"},
    ],
    "unemployment-benefit": [
        {"tag": "실업급여", "title": "실업급여 신청 조건과 절차 완벽 가이드",
         "desc": "고용보험법 제40조 기준 구직급여 수급 자격과 신청 방법을 안내합니다.",
         "href": "/blog/unemployment-benefit-guide/"},
        {"tag": "실업급여", "title": "자발적 퇴사 후 실업급여 받는 방법 — 예외 조건",
         "desc": "자발적 퇴사 시 실업급여 수급 가능한 예외 케이스와 필요 서류를 설명합니다.",
         "href": "/blog/voluntary-resign-unemployment-benefit/"},
    ],
    "four-insurances": [
        {"tag": "4대보험", "title": "4대보험 요율 완벽 정리 — 2025년 국민연금·건강·고용·산재",
         "desc": "2025년 기준 4대보험 각 요율과 근로자·사업주 부담 비율을 상세히 설명합니다.",
         "href": "/blog/four-insurance-rates-2025/"},
        {"tag": "4대보험", "title": "4대보험 가입 의무와 미가입 시 불이익 — 법적 안내",
         "desc": "4대보험 가입 의무와 미가입 시 사업주에게 부과되는 과태료를 안내합니다.",
         "href": "/blog/four-insurance-obligation/"},
    ],
    "연말정산_환급액_계산기": [
        {"tag": "연말정산", "title": "연말정산 환급액 최대화 전략 — 공제 항목 총정리",
         "desc": "소득세법 제137조 기준 연말정산에서 환급액을 최대화할 수 있는 공제 항목을 설명합니다.",
         "href": "/blog/yearend-tax-refund-maximize/"},
        {"tag": "연말정산", "title": "연말정산 간소화서비스 사용법과 서류 준비 체크리스트",
         "desc": "국세청 홈택스 연말정산 간소화서비스 활용법과 필요 서류 목록을 안내합니다.",
         "href": "/blog/yearend-tax-simplified-service/"},
    ],
    "육아휴직_급여_계산기": [
        {"tag": "육아휴직", "title": "6+6 부모 육아휴직 특례 — 신청 조건과 급여 계산",
         "desc": "2024년 시행된 6+6 부모 육아휴직 특례의 조건과 월별 급여 계산 방법을 안내합니다.",
         "href": "/blog/6plus6-parental-leave-guide/"},
        {"tag": "육아휴직", "title": "육아휴직 급여 신청 절차 — 서류부터 지급까지",
         "desc": "육아휴직 급여 신청에 필요한 서류, 신청 기한, 지급 일정을 단계별로 설명합니다.",
         "href": "/blog/parental-leave-benefit-apply/"},
    ],
}


def _pj(v, default):
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v) if v else default
    except Exception:
        return default


def _label(k, labels=None):
    # registry field_labels 병합 결과 우선, 없으면 키 이름 변환 fallback
    if labels and k in labels and str(labels[k]).strip():
        return str(labels[k])
    return str(k).replace("_", " ")


def _effective_labels(calc: dict) -> dict:
    """registry v3 field_labels(primary) + DB labels(override) 병합.
    미매핑 키는 _label()에서 str(k).replace('_',' ')로 변환."""
    from .registry_loader import load_registry_v3
    slug = str(calc.get("slug", ""))
    reg_fl = (load_registry_v3().get(slug) or {}).get("field_labels") or {}
    db_labels = _pj(calc.get("labels"), {})
    return {**reg_fl, **db_labels}  # DB가 registry보다 우선


def _to_js(expr: str) -> str:
    s = str(expr)
    for fn, jsfn in _JS_FUNCS.items():
        s = re.sub(rf"\b{fn}\s*\(", f"{jsfn}(", s)
    # Python floor division (//) → JS Math.floor(a / b)
    # JS에서 // 는 한 줄 주석이므로 반드시 변환해야 함
    s = re.sub(r'(\([^()]*\)|\w+)\s*//\s*(\d+(?:\.\d+)?|\w+)', r'Math.floor(\1 / \2)', s)
    return s


# ── Design System v2 (마스터 시안 + assets) ──────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_TPL_V2 = _BASE_DIR / "templates" / "calculators" / "calculator_v2.html"
_ASSETS = _BASE_DIR / "templates" / "calculators" / "assets"
# components.js는 init을 실행하므로 마지막(다른 모듈 정의 후)
_JS_ORDER = ["analytics.js", "number_input.js", "result_save.js", "share.js", "pwa.js",
             "faq.js", "related.js", "components.js"]
# ── calculator_registry (legal_basis.draft.yaml + registry_auto.yaml, schema_version 2) ────
# Phase D: registry가 유일 소스(관련계산기/compute 분기의 하드코딩 폴백은 제거됨).
def _registry() -> dict:
    """slug → registry entry dict. 실제 로드/merge/캐시는 registry_loader가 단일 담당
    (legal_basis.draft.yaml=큐레이션 우선 + registry_auto.yaml=자동생성). 로드 실패 시 {}."""
    from .registry_loader import load_registry
    return load_registry()


def _compute_type(calc) -> str:
    """registry compute_type 유일 소스(Phase D: slug=="severance-pay" 하드코딩 폴백 제거).
    미등록 계산기는 일반 기본값 single(특수취급 없음 — date_based는 registry에만 존재)."""
    ct = (_registry().get(str(calc.get("slug", ""))) or {}).get("compute_type")
    return str(ct) if ct else "single"


def _validation_mode(calc) -> str:
    """registry validation_mode 유일 소스(Phase D: slug 하드코딩 폴백 제거).
    미등록 계산기는 일반 기본값 formula(skip은 registry에만 존재)."""
    vm = (_registry().get(str(calc.get("slug", ""))) or {}).get("validation_mode")
    return str(vm) if vm else "formula"


def _split_label(k, labels=None):
    """'시급(원)' → ('시급','원'). 괄호 없으면 (label,''). labels(registry 병합 결과) 우선."""
    lab = _label(k, labels)
    m = re.match(r"^(.*)\((.+)\)\s*$", lab)
    return (m.group(1).strip(), m.group(2).strip()) if m else (lab, "")


def _form_fields_v2(ins, labels=None) -> str:
    rows = []
    for k, spec in ins.items():
        label, unit = _split_label(k, labels)
        spec_str = str(spec)
        if spec_str.lower().startswith("select:"):
            # STEP 17-A: 선택형(enum) 입력. input_schema 값 형식: "select:값1=텍스트1,값2=텍스트2"
            # 다른 계산기의 기존 타입 문자열("integer"/"number"/"date" 등)은 이 접두사를 쓰지 않으므로 영향 없음.
            options_html = []
            for pair in spec_str.split(":", 1)[1].split(","):
                if "=" not in pair:
                    continue
                val, text = pair.split("=", 1)
                options_html.append(
                    f'<option value="{_html.escape(val.strip())}">{_html.escape(text.strip())}</option>')
            rows.append(
                f'<div class="sm-field">'
                f'<label class="sm-label" for="in_{k}">{_html.escape(label)}</label>'
                f'<div class="sm-input-wrap">'
                f'<select class="sm-input" id="in_{k}" name="in_{k}">'
                f'{"".join(options_html)}'
                f'</select>'
                f'</div></div>')
        elif "date" in spec_str.lower():
            rows.append(
                f'<div class="sm-field">'
                f'<label class="sm-label" for="in_{k}">{_html.escape(label)}</label>'
                f'<div class="sm-input-wrap">'
                f'<input class="sm-input" type="date" id="in_{k}" name="in_{k}">'
                f'</div></div>')
        else:
            u = f'<span class="sm-unit">{_html.escape(unit)}</span>' if unit else ""
            ph = _PLACEHOLDERS.get(k, "0")
            rows.append(
                f'<div class="sm-field">'
                f'<label class="sm-label" for="in_{k}">{_html.escape(label)}</label>'
                f'<div class="sm-input-wrap">'
                f'<input class="sm-input" type="text" inputmode="numeric" '
                f'data-comma id="in_{k}" name="in_{k}" placeholder="예) {ph}">'
                f'{u}</div></div>')
    return "\n".join(rows)


def _faq_items_v2(calc) -> str:
    faq = _pj(calc.get("faq"), [])
    if not isinstance(faq, list) or not faq:
        return '<p style="font-size:14px;color:#6B7280">등록된 FAQ가 없습니다.</p>'
    items = []
    for f in faq:
        if not isinstance(f, dict):
            continue
        q = _html.escape(str(f.get("question", f.get("q", ""))))
        a = _html.escape(str(f.get("answer", f.get("a", ""))))
        items.append(
            f'<div class="sm-faq-item"><button class="sm-faq-q" onclick="toggleFaq(this)">{q}'
            f'<span class="sm-faq-icon">+</span></button><div class="sm-faq-a">{a}</div></div>')
    return "\n".join(items)


def _related_triples(cur: str):
    """관련 계산기 (slug, emoji, 표시명) 리스트(cur 제외, 순서 유지).
    registry(related_slugs+emoji+card_label)가 유일 소스(Phase D: _RELATED 폴백 제거). 미등록이면 빈 리스트.
    ※ card_label 기본값은 name(정식명칭)이라, 짧은 카드명이 필요한 계산기는 registry에서 override."""
    reg = _registry()
    slugs = (reg.get(cur) or {}).get("related_slugs") or []
    out = []
    for s in slugs:
        if s == cur:
            continue
        e = reg.get(s) or {}
        label = e.get("card_label") or e.get("name") or s
        out.append((s, str(e.get("emoji") or ""), str(label)))
    return out


def _related_items_v2(calc) -> str:
    cur = str(calc.get("slug", ""))
    # href: 형제 계산기 폴더 상대경로(../{slug}/). target=_self: 미리보기 iframe 자체가 이동
    # (대시보드 상위 프레임은 안 튐). ※ 지시서의 _top은 §2 의도와 반대라 _self로 적용함.
    items = [f'<a class="sm-related-item" href="../{slug}/" target="_self">'
             f'<span class="sm-related-emoji">{emoji}</span>'
             f'<span class="sm-related-name">{_html.escape(nm)}</span></a>'
             for slug, emoji, nm in _related_triples(cur)]
    return "\n".join(items)


def _show_flags(cfg) -> dict:
    """show_* 노출 플래그 단일 소스. _sm_config(SM_CONFIG)와 render_* 섹션 함수가 공유.
    SITE_MODE로 광고/CPA 기본값 파생, SHOW_* 명시 시 그 값 우선."""
    c = cfg if isinstance(cfg, dict) else {}
    def b(key, default):
        return bool(c.get(key, default))
    site_mode = str(c.get("SITE_MODE", "pre_adsense"))
    mode_ads = site_mode in ("adsense", "full")
    mode_cpa = site_mode in ("cpa", "full")
    return {
        "show_adsense": b("SHOW_ADSENSE", mode_ads),
        "show_cpa": b("SHOW_CPA", mode_cpa),
        "show_share": b("SHOW_SHARE", True),
        "show_pwa": b("SHOW_PWA", True),
        "show_result_save": b("SHOW_RESULT_SAVE", True),
        "show_faq": b("SHOW_FAQ", True),
        "show_notice": b("SHOW_NOTICE", True),
        "show_related": b("SHOW_RELATED", True),
        "show_detail": b("SHOW_DETAIL", True),
        "show_article": b("SHOW_ARTICLE", True),
        "_site_mode": site_mode,  # 내부용(SM_CONFIG에는 site_mode로 별도 노출)
    }


def _sm_config(calc, cfg) -> dict:
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    labels = _effective_labels(calc)  # registry v3 field_labels primary, _LABELS fallback
    inputs = []
    for k, spec in ins.items():
        label, unit = _split_label(k, labels)
        inputs.append({"name": k, "label": label,
                       "type": ("date" if "date" in str(spec).lower() else "number"), "unit": unit})
    outputs = [{"key": k, "label": _split_label(k, labels)[0], "unit": _split_label(k, labels)[1] or "원"} for k in outs]
    primary = list(outs.keys())[0] if outs else "result"
    c = cfg if isinstance(cfg, dict) else {}
    flags = _show_flags(cfg)
    return {
        # 기능(계산/렌더용)
        "name": calc.get("name", "계산기"), "slug": str(calc.get("slug", "")),
        "primaryOutput": primary,
        "resultUnit": (outputs[0]["unit"] if outputs else "원"),
        "inputs": inputs, "outputs": outputs,
        # 노출 플래그(flat, 대시보드 설정 연동) — _show_flags 단일 소스
        "show_adsense": flags["show_adsense"],
        "show_cpa": flags["show_cpa"],
        "show_share": flags["show_share"],
        "show_pwa": flags["show_pwa"],
        "show_result_save": flags["show_result_save"],
        "show_faq": flags["show_faq"],
        "show_notice": flags["show_notice"],
        "show_related": flags["show_related"],
        "show_detail": flags["show_detail"],
        "show_article": flags["show_article"],
        # 정책/메타
        "site_mode": flags["_site_mode"],
        "result_export_type": str(c.get("RESULT_EXPORT_TYPE", "png")),
        "kakao_js_key": str(c.get("KAKAO_JS_KEY", "")),
        "calculator_version": str(c.get("CALCULATOR_VERSION", "2.0.0")),
        "law_version": str(c.get("LAW_VERSION", "2026-07")),
        "ga4_id": str(c.get("GA4_MEASUREMENT_ID", "")),
    }


def _read_assets_js() -> str:
    parts = []
    for f in _JS_ORDER:
        p = _ASSETS / f
        parts.append(p.read_text(encoding="utf-8") if p.exists() else "")
    return "\n".join(parts)


def _ub_days_table_js(rows: list) -> str:
    """소정급여일수 행 리스트 → JS 배열 리터럴. months_hi None → Infinity."""
    parts = []
    for r in rows:
        hi = r.get("months_hi")
        hi_js = "Infinity" if hi is None else str(int(hi))
        parts.append(f"{{lo:{int(r['months_lo'])},hi:{hi_js},d:{int(r['days'])}}}")
    return "[" + ",".join(parts) + "]"


# ── JS computeResult 공통 헬퍼 ──────────────────────────────────────────────

def _js_open() -> str:
    """모든 계산기 JS의 공통 시작 줄."""
    return "window.computeResult = function(inputs){\n"


def _js_close() -> str:
    """모든 계산기 JS의 공통 종료 줄 (return out은 각 분기에서 처리)."""
    return "};\n"


def _js_read(field: str, default: int = 0) -> str:
    """inputs에서 단일 필드를 읽는 JS 변수 선언."""
    return f'  var {field} = inputs["{field}"] || {default};\n'


def _js_init_out() -> str:
    """out 객체 + notices 배열 초기화."""
    return "  var out = {};\n  out.notices = [];\n"


def _compute_js(calc) -> str:
    """계산기별 computeResult(inputs) 생성. 기존 formula/퇴직금 date분기 로직 유지.
    registry의 compute_rules가 있으면 입력 검증(양수/최솟값/최저임금) 코드를 자동 주입한다."""
    if str(calc.get("slug", "")) == "unemployment-benefit":
        ub_reg = (_registry().get("unemployment-benefit") or {})
        ba = ub_reg.get("benefit_amounts") or {}
        daily_max = int(ba.get("daily_max", 66000))
        min_wage = int(ba.get("min_wage_hourly", 10030))
        daily_min = round(min_wage * 8 * 0.8)
        bdt = ub_reg.get("benefit_days_table") or {}
        u50_js = _ub_days_table_js(bdt.get("under_50") or [])
        a50_js = _ub_days_table_js(bdt.get("age_50_plus") or [])
        return (
            _js_open()
            + _js_read("avg_daily_wage")
            + _js_read("age")
            + _js_read("employment_months")
            + '  if (avg_daily_wage <= 0 || age <= 0 || employment_months <= 0) { return null; }\n'
            + _js_init_out()
            + (
            # UB-3: 피보험단위기간 6개월(약 180일) 미만 → 수급 불가 (고용보험법 제40조)
            '  if (employment_months < 6) {\n'
            '    out["daily_benefit"] = 0;\n'
            '    out["benefit_days"] = 0;\n'
            '    out["total_benefit"] = 0;\n'
            '    out.notices.push("피보험단위기간이 180일(약 6개월) 미만이면 구직급여를 받을 수 없습니다 (고용보험법 제40조).");\n'
            '    out._formula = employment_months + "개월 — 6개월 미만으로 수급 불가";\n'
            '    return out;\n'
            '  }\n'
            f'  var DAILY_MAX = {daily_max};\n'
            f'  var DAILY_MIN = {daily_min};\n'
            '  var raw_daily = avg_daily_wage * 0.6;\n'
            '  var daily_benefit = Math.min(Math.max(raw_daily, DAILY_MIN), DAILY_MAX);\n'
            f'  var under50 = {u50_js};\n'
            f'  var age50p = {a50_js};\n'
            '  var table = (age >= 50) ? age50p : under50;\n'
            '  var benefit_days = table[table.length - 1].d;\n'
            '  for (var i = 0; i < table.length; i++) {\n'
            '    if (employment_months >= table[i].lo && employment_months < table[i].hi) {\n'
            '      benefit_days = table[i].d; break;\n'
            '    }\n'
            '  }\n'
            '  var total_benefit = daily_benefit * benefit_days;\n'
            '  out["daily_benefit"] = daily_benefit;\n'
            '  out["benefit_days"] = benefit_days;\n'
            '  out["total_benefit"] = total_benefit;\n'
            # UB-7: notices — 수급 가능 케이스에서만 상한/하한 안내 (180일 미만은 이미 return됨)
            '  if (raw_daily < DAILY_MIN) {\n'
            '    out.notices.push("기초일액(" + Math.round(raw_daily).toLocaleString() + "원)이 하한액보다 낮아 하한액(" + DAILY_MIN.toLocaleString() + "원)이 적용됩니다 (고용보험법 제46조 제2항).");\n'
            '  } else if (raw_daily > DAILY_MAX) {\n'
            '    out.notices.push("기초일액(" + Math.round(raw_daily).toLocaleString() + "원)이 상한액을 초과하여 상한액(" + DAILY_MAX.toLocaleString() + "원)이 적용됩니다 (고용노동부 고시).");\n'
            '  }\n'
            # UB-6: _formula — 케이스별(하한/상한/정상) 단계 표시
            '  var _ub_formula;\n'
            '  if (raw_daily < DAILY_MIN) {\n'
            '    _ub_formula = "기초일액 " + Math.round(raw_daily).toLocaleString() + "원 → 하한액 적용(" + DAILY_MIN.toLocaleString() + "원) → " + Math.round(daily_benefit).toLocaleString() + "원/일 × " + benefit_days + "일 = " + Math.round(total_benefit).toLocaleString() + "원";\n'
            '  } else if (raw_daily > DAILY_MAX) {\n'
            '    _ub_formula = "기초일액 " + Math.round(raw_daily).toLocaleString() + "원 → 상한액 적용(" + DAILY_MAX.toLocaleString() + "원) → " + Math.round(daily_benefit).toLocaleString() + "원/일 × " + benefit_days + "일 = " + Math.round(total_benefit).toLocaleString() + "원";\n'
            '  } else {\n'
            '    _ub_formula = "기초일액 " + Math.round(raw_daily).toLocaleString() + "원/일 × " + benefit_days + "일 = " + Math.round(total_benefit).toLocaleString() + "원";\n'
            '  }\n'
            '  out._formula = _ub_formula;\n'
            '  return out;\n};\n'
            )
        )
    if str(calc.get("slug", "")) == "four-insurances":
        fi_reg = (_registry().get("four-insurances") or {})
        ir = fi_reg.get("insurance_rates") or {}
        NP_RATE  = float(ir.get("np_rate",  0.045))
        NP_MIN   = int(ir.get("np_min",   390000))
        NP_MAX   = int(ir.get("np_max",   6170000))
        HI_RATE  = float(ir.get("hi_rate",  0.03545))
        LTC_RATE = float(ir.get("ltc_rate", 0.1296))
        EI_RATE  = float(ir.get("ei_rate",  0.009))
        np_pct   = f"{NP_RATE  * 100:g}"
        hi_pct   = f"{HI_RATE  * 100:g}"
        ltc_pct  = f"{LTC_RATE * 100:g}"
        ei_pct   = f"{EI_RATE  * 100:g}"
        return (
            _js_open()
            + _js_read("monthly_salary")
            + '  if (monthly_salary <= 0) { return null; }\n'
            + '  var out = {};\n'
            # FI-2: 국민연금 기준소득월액 상한/하한 클램프 (국민연금법 제88조)
            f'  var NP_MIN = {NP_MIN};\n'
            f'  var NP_MAX = {NP_MAX};\n'
            '  var np_base = Math.min(Math.max(monthly_salary, NP_MIN), NP_MAX);\n'
            f'  var national_pension = np_base * {NP_RATE};\n'
            # FI-1: 건강보험 먼저 계산 → 장기요양은 반드시 health_insurance에 곱 (급여 직접 곱 금지)
            f'  var health_insurance = monthly_salary * {HI_RATE};\n'
            f'  var long_term_care = health_insurance * {LTC_RATE};\n'
            f'  var employment_insurance = monthly_salary * {EI_RATE};\n'
            # FI-3: total에 4종 모두 합산
            '  var total = national_pension + health_insurance + long_term_care + employment_insurance;\n'
            '  out["national_pension"] = national_pension;\n'
            '  out["health_insurance"] = health_insurance;\n'
            '  out["long_term_care"] = long_term_care;\n'
            '  out["employment_insurance"] = employment_insurance;\n'
            '  out["total"] = total;\n'
            # FI-9: notices — 우선순위별 별도 배열 → concat으로 명시적 순서 확정
            # 순서: [1] 국민연금 상·하한, [2] 산재보험 안내
            '  var _np_notices = [];\n'
            '  var _si_notices = [];\n'
            '  if (monthly_salary < NP_MIN) {\n'
            '    _np_notices.push("월급여(" + monthly_salary.toLocaleString() + "원)가 기준소득월액 하한(" + NP_MIN.toLocaleString() + "원)보다 낮아 국민연금은 하한 기준으로 계산됩니다 (국민연금법 제88조).");\n'
            '  } else if (monthly_salary > NP_MAX) {\n'
            '    _np_notices.push("월급여(" + monthly_salary.toLocaleString() + "원)가 기준소득월액 상한(" + NP_MAX.toLocaleString() + "원)을 초과하여 국민연금은 상한 기준으로 계산됩니다 (국민연금법 제88조).");\n'
            '  }\n'
            '  _si_notices.push("산재보험은 사업주가 전액 부담합니다 — 근로자 급여에서 공제되지 않습니다 (산업재해보상보험법 제13조).");\n'
            '  out.notices = [].concat(_np_notices, _si_notices);\n'
            # FI-8: _formula — 5단계 순서 표시 (장기요양 단계에 건강보험료 금액 명시)
            '  var np_label = (monthly_salary < NP_MIN ? NP_MIN.toLocaleString() : (monthly_salary > NP_MAX ? NP_MAX.toLocaleString() : monthly_salary.toLocaleString()));\n'
            f'  out._formula = "국민연금 " + np_label + "원 × {np_pct}% = " + Math.round(national_pension).toLocaleString() + "원 | 건강보험 " + monthly_salary.toLocaleString() + "원 × {hi_pct}% = " + Math.round(health_insurance).toLocaleString() + "원 | 장기요양 건강보험료 " + Math.round(health_insurance).toLocaleString() + "원 × {ltc_pct}% = " + Math.round(long_term_care).toLocaleString() + "원 | 고용보험 " + monthly_salary.toLocaleString() + "원 × {ei_pct}% = " + Math.round(employment_insurance).toLocaleString() + "원";\n'
            '  return out;\n};\n'
        )
    if str(calc.get("slug", "")) == "real-estate-brokerage-fee":
        # STEP 16(신규 계산기 생성 라인 검증, 수동): 공인중개사법 시행규칙 제20조 별표1.
        # deal_type: 1=매매·교환, 2=임대차(전세·월세는 환산보증금을 미리 계산해 입력).
        # 거래금액 구간별 상한요율 + 하위 2개 구간은 정액 한도액과 비교해 더 낮은 금액 적용.
        return (
            _js_open()
            + _js_read("deal_type")
            + _js_read("deal_amount")
            + '  if (deal_amount <= 0 || (deal_type !== 1 && deal_type !== 2)) { return null; }\n'
            + _js_init_out()
            + '  var rate, cap;\n'
            + '  if (deal_type === 1) {\n'
            + '    if (deal_amount < 50000000) { rate = 0.006; cap = 250000; }\n'
            + '    else if (deal_amount < 200000000) { rate = 0.005; cap = 800000; }\n'
            + '    else if (deal_amount < 900000000) { rate = 0.004; cap = null; }\n'
            + '    else if (deal_amount < 1200000000) { rate = 0.005; cap = null; }\n'
            + '    else if (deal_amount < 1500000000) { rate = 0.006; cap = null; }\n'
            + '    else { rate = 0.007; cap = null; }\n'
            + '  } else {\n'
            + '    if (deal_amount < 50000000) { rate = 0.005; cap = 200000; }\n'
            + '    else if (deal_amount < 100000000) { rate = 0.004; cap = 300000; }\n'
            + '    else if (deal_amount < 600000000) { rate = 0.003; cap = null; }\n'
            + '    else if (deal_amount < 1200000000) { rate = 0.004; cap = null; }\n'
            + '    else if (deal_amount < 1500000000) { rate = 0.005; cap = null; }\n'
            + '    else { rate = 0.006; cap = null; }\n'
            + '  }\n'
            + '  var raw_fee = deal_amount * rate;\n'
            + '  var fee = (cap !== null) ? Math.min(raw_fee, cap) : raw_fee;\n'
            + '  out["brokerage_fee"] = Math.round(fee);\n'
            + '  var appliedRatePct = Math.round(rate * 1000) / 10;\n'
            + '  var typeLabel = (deal_type === 1) ? "매매·교환" : "임대차(전세·월세)";\n'
            + '  var capNote = (cap !== null) ? (", 한도액 " + cap.toLocaleString() + "원 적용") : "";\n'
            + '  out._formula = typeLabel + " 거래금액 " + deal_amount.toLocaleString() + "원 \\u2014 상한요율 " + appliedRatePct + "%(공인중개사법 시행규칙 제20조 별표1)" + capNote + " = " + Math.round(fee).toLocaleString() + "원";\n'
            + '  return out;\n'
            + _js_close()
        )
    if str(calc.get("slug", "")) == "annual-leave-allowance":
        # AL-1: 입력 검증 — 음수/0 → null
        # AL-5: notices — 법정 상한(25일) 초과 경고
        # AL-6: _formula — "통상임금(일급) N원 × M일 = Y원"
        return (
            _js_open()
            + _js_read("daily_wage")
            + _js_read("unused_days")
            + '  if (daily_wage <= 0 || unused_days <= 0) { return null; }\n'
            + '  var out = {};\n'
            + '  out["annual_leave_allowance"] = (daily_wage * unused_days);\n'
            + '  var notices = [];\n'
            + '  if (unused_days > 25) {\n'
            + '    notices.push("입력하신 미사용 연차(" + unused_days + "일)가 법정 상한(25일)을 초과합니다. 사용자가 추가로 부여한 약정 연차가 있는 경우 25일을 초과할 수 있습니다(근로기준법 제60조제4항).");\n'
            + '  }\n'
            + '  out.notices = notices;\n'
            + '  out._formula = "통상임금(일급) " + daily_wage.toLocaleString() + "원 × " + unused_days + "일 = " + Math.round(daily_wage * unused_days).toLocaleString() + "원";\n'
            + '  return out;\n'
            + _js_close()
        )
    if str(calc.get("slug", "")) == "annual-leave-remaining":
        # ALR-1(STEP 15-E): 근로기준법 제60조 제1항(1년 미만, 매월 개근 시 1일, 최대 11일)
        # + 제4항(3년 이상 계속근로 시 2년마다 1일 가산, 25일 상한) 통합 계산.
        # 입력: months_of_service(총 근속개월수), used_days(이미 사용한 연차일수).
        # ⚠️ STEP 15-E-R 시점 기준 DB calculators.input_schema는 아직 years_of_service라
        # 실제 폼 필드가 연결되지 않음 — 이 분기만으로는 완결되지 않고 별도 DB 갱신 필요.
        return (
            _js_open()
            + _js_read("months_of_service")
            + _js_read("used_days")
            + '  if (months_of_service < 0 || used_days < 0) { return null; }\n'
            + _js_init_out()
            + '  var total_days;\n'
            + '  if (months_of_service < 12) {\n'
            + '    total_days = Math.min(months_of_service, 11);\n'
            + '  } else {\n'
            + '    var years = Math.floor(months_of_service / 12);\n'
            + '    total_days = 15 + Math.min(Math.max(0, Math.floor((years - 1) / 2)), 10);\n'
            + '  }\n'
            + '  out["total_days"] = total_days;\n'
            + '  out["remaining_days"] = total_days - used_days;\n'
            + '  out._formula = (months_of_service < 12)\n'
            + '    ? (months_of_service + "개월 근속 — 매월 1일씩 최대 11일(근로기준법 제60조 제2항) = " + total_days + "일")\n'
            + '    : (months_of_service + "개월(" + Math.floor(months_of_service / 12) + "년) 근속 — 15일 + 2년마다 1일 가산, 25일 상한(근로기준법 제60조 제1항·제4항) = " + total_days + "일");\n'
            + '  return out;\n'
            + _js_close()
        )
    if str(calc.get("slug", "")) == "육아휴직_급여_계산기":
        # PL-1..15 Phase 2: 판정-계산 분리 구조 (determine_leave_mode / calculate_general / calculate_6plus6)
        pl_reg  = (_registry().get("육아휴직_급여_계산기") or {})
        plb     = pl_reg.get("parental_leave_benefit") or {}
        gen     = plb.get("general")        or {}
        sp      = plb.get("special_6plus6") or {}
        MIN_INSURED = int(plb.get("min_insured_days", 180))
        GEN_RATE    = float(gen.get("rate",    0.80))
        GEN_CEIL    = int(gen.get("ceiling",   1_500_000))
        GEN_FLOOR   = int(gen.get("floor",     700_000))
        SP_RATE     = float(sp.get("rate",     1.00))
        SP_MAX_MO   = int(sp.get("max_months", 6))
        SP_CEILS    = list(sp.get("monthly_ceilings") or [2_000_000, 2_500_000, 3_000_000, 3_500_000, 4_000_000, 4_500_000])
        sp_ceils_js = "[" + ",".join(str(int(c)) for c in SP_CEILS) + "]"
        gen_rate_pct = f"{GEN_RATE * 100:g}%"
        sp_rate_pct  = f"{SP_RATE  * 100:g}%"
        return (
            _js_open()
            # ① 입력 검증: 통상임금·피보험단위기간·개월차 모두 양수 필수
            + _js_read("monthly_wage")
            + _js_read("insured_days")
            + '  var use_6plus6   = inputs["use_6plus6"]   || 0;\n'
            + _js_read("leave_month")
            + '  if (monthly_wage <= 0 || insured_days <= 0 || leave_month <= 0) { return null; }\n'
            + _js_init_out()
            + (
            # ② 수급자격 확인 (피보험단위기간 180일 — 고용보험법 제70조 제1항)
            f'  var MIN_INSURED = {MIN_INSURED};\n'
            '  if (insured_days < MIN_INSURED) {\n'
            '    out["monthly_allowance"] = 0;\n'
            '    out.notices.push("피보험단위기간이 " + insured_days + "일로 180일 미만이면 육아휴직급여를 받을 수 없습니다(고용보험법 제70조 제1항).");\n'
            '    out._formula = "피보험단위기간 " + insured_days + "일 — 180일 미만으로 수급 불가";\n'
            '    return out;\n'
            '  }\n'
            # 상수 (legal_basis.draft.yaml parental_leave_benefit 외부화)
            f'  var GEN_RATE  = {GEN_RATE};\n'
            f'  var GEN_CEIL  = {GEN_CEIL};\n'
            f'  var GEN_FLOOR = {GEN_FLOOR};\n'
            f'  var SP_RATE   = {SP_RATE};\n'
            f'  var SP_MAX_MO = {SP_MAX_MO};\n'
            f'  var SP_CEILS  = {sp_ceils_js};\n'
            # ③ 판정 함수 — 추가 특례 제도 변경 시 이 함수만 수정
            '  function determine_leave_mode(use_sp, mo) {\n'
            '    if (use_sp >= 1 && mo >= 1 && mo <= SP_MAX_MO) { return "SPECIAL_6_PLUS_6"; }\n'
            '    return "GENERAL";\n'
            '  }\n'
            # ④ 계산 함수: calculate_general (통상임금 × 80%, 상한/하한 클램프)
            '  function calculate_general(wage) {\n'
            '    var raw = wage * GEN_RATE;\n'
            '    var applied = Math.min(Math.max(raw, GEN_FLOOR), GEN_CEIL);\n'
            f'    return {{ raw: raw, applied: applied, ceiling: GEN_CEIL, floor: GEN_FLOOR, rate_pct: "{gen_rate_pct}" }};\n'
            '  }\n'
            # ④ 계산 함수: calculate_6plus6 (통상임금 × 100%, 월별 상한 클램프)
            '  function calculate_6plus6(wage, mo) {\n'
            '    var raw = wage * SP_RATE;\n'
            '    var ceiling = SP_CEILS[mo - 1];\n'
            '    var applied = Math.min(Math.max(raw, GEN_FLOOR), ceiling);\n'
            f'    return {{ raw: raw, applied: applied, ceiling: ceiling, floor: GEN_FLOOR, rate_pct: "{sp_rate_pct}" }};\n'
            '  }\n'
            # ③ 판정 실행
            '  var mode = determine_leave_mode(use_6plus6, leave_month);\n'
            # 7개월 이후 자동 일반 전환 notice
            '  if (use_6plus6 >= 1 && leave_month > SP_MAX_MO) {\n'
            '    out.notices.push("6+6 특례는 1～" + SP_MAX_MO + "개월에만 적용됩니다. " + leave_month + "개월째는 일반 육아휴직급여(통상임금 80%)가 적용됩니다(고용보험법 시행령 제95조의2).");\n'
            '  }\n'
            # ④ 계산 실행 / ⑤ 지급률 적용 / ⑥ 상한·하한 클램프
            '  var cr = (mode === "SPECIAL_6_PLUS_6") ? calculate_6plus6(monthly_wage, leave_month) : calculate_general(monthly_wage);\n'
            '  out["monthly_allowance"] = cr.applied;\n'
            # ⑦ notices: 상한·하한 적용 안내
            '  var _mn = [];\n'
            '  if (cr.raw > cr.ceiling) {\n'
            '    _mn.push("통상임금 기준 급여(" + Math.round(cr.raw).toLocaleString() + "원)가 상한액(" + cr.ceiling.toLocaleString() + "원)을 초과하여 상한액이 적용됩니다(고용보험법 시행령 제95조).");\n'
            '  } else if (cr.raw < cr.floor) {\n'
            '    _mn.push("통상임금 기준 급여(" + Math.round(cr.raw).toLocaleString() + "원)가 하한액(" + cr.floor.toLocaleString() + "원)보다 낮아 하한액이 적용됩니다(고용보험법 시행령 제95조).");\n'
            '  }\n'
            '  out.notices = [].concat(out.notices, _mn);\n'
            # ⑧ _formula
            '  var ml = (mode === "SPECIAL_6_PLUS_6") ? ("6+6 특례 " + leave_month + "개월차") : "일반";\n'
            '  var fs = ml + " — 통상임금 " + monthly_wage.toLocaleString() + "원 × " + cr.rate_pct + " = " + Math.round(cr.raw).toLocaleString() + "원";\n'
            '  if (cr.raw > cr.ceiling) { fs += " → 상한 적용(" + cr.ceiling.toLocaleString() + "원) → " + Math.round(cr.applied).toLocaleString() + "원"; }\n'
            '  else if (cr.raw < cr.floor) { fs += " → 하한 적용(" + cr.floor.toLocaleString() + "원) → " + Math.round(cr.applied).toLocaleString() + "원"; }\n'
            '  out._formula = fs;\n'
            # ⑨ 반환
            '  return out;\n'
            '};\n'
            )
        )
    if str(calc.get("slug", "")) == "연말정산_환급액_계산기":
        yt_reg = (_registry().get("연말정산_환급액_계산기") or {})
        fi_reg = (_registry().get("four-insurances") or {})
        ir     = fi_reg.get("insurance_rates") or {}
        # 4대보험 요율
        NP_RATE  = float(ir.get("np_rate",  0.045))
        NP_MIN   = int(ir.get("np_min",   390_000))
        NP_MAX   = int(ir.get("np_max",   6_170_000))
        HI_RATE  = float(ir.get("hi_rate",  0.03545))
        LTC_RATE = float(ir.get("ltc_rate", 0.1296))
        EI_RATE  = float(ir.get("ei_rate",  0.009))
        # 근로소득공제 구간
        ldt  = yt_reg.get("labor_deduction_table") or {}
        ld_brackets = ldt.get("brackets") or [
            {"limit": 5_000_000,   "rate": 0.70, "base": 0},
            {"limit": 15_000_000,  "rate": 0.40, "base": 3_500_000},
            {"limit": 45_000_000,  "rate": 0.15, "base": 7_500_000},
            {"limit": 100_000_000, "rate": 0.05, "base": 12_000_000},
            {"limit": None,        "rate": 0.02, "base": 14_750_000},
        ]
        LD_MAX = int(ldt.get("max_deduction", 20_000_000))
        # 세율 구간
        itb = yt_reg.get("income_tax_brackets") or {}
        tax_brackets = itb.get("brackets") or [
            {"limit": 14_000_000,    "rate": 0.06, "deduction": 0},
            {"limit": 50_000_000,    "rate": 0.15, "deduction": 1_260_000},
            {"limit": 88_000_000,    "rate": 0.24, "deduction": 5_760_000},
            {"limit": 150_000_000,   "rate": 0.35, "deduction": 15_440_000},
            {"limit": 300_000_000,   "rate": 0.38, "deduction": 19_940_000},
            {"limit": 500_000_000,   "rate": 0.40, "deduction": 25_940_000},
            {"limit": 1_000_000_000, "rate": 0.42, "deduction": 35_940_000},
            {"limit": None,          "rate": 0.45, "deduction": 65_940_000},
        ]
        # 세액공제 한도
        tcl = yt_reg.get("tax_credit_limits") or {}
        CREDIT_THRESHOLD = int(tcl.get("credit_threshold", 1_300_000))
        CREDIT_RATE_LOW  = float(tcl.get("credit_rate_low",  0.55))
        CREDIT_RATE_HIGH = float(tcl.get("credit_rate_high", 0.30))
        CREDIT_BASE_HIGH = int(tcl.get("credit_base_high", 715_000))
        # 인적공제
        PER_PERSON = int((yt_reg.get("personal_deduction") or {}).get("per_person", 1_500_000))
        # JS embed: 근로소득공제 구간 배열
        ld_js_rows = []
        prev = 0
        for b in ld_brackets:
            lim = b.get("limit")
            ld_js_rows.append(
                f'{{lim:{lim if lim is not None else "Infinity"},rate:{b["rate"]},base:{b["base"]},prev:{prev}}}'
            )
            if lim is not None:
                prev = lim
        ld_js = "[" + ",".join(ld_js_rows) + "]"
        # JS embed: 세율 구간 배열
        tb_js_rows = []
        for b in tax_brackets:
            lim = b.get("limit")
            tb_js_rows.append(
                f'{{lim:{lim if lim is not None else "Infinity"},rate:{b["rate"]},ded:{b["deduction"]}}}'
            )
        tb_js = "[" + ",".join(tb_js_rows) + "]"
        # 세액공제 한도 구간
        tcl_limits = tcl.get("limits") or [
            {"salary_max": 33_000_000,  "fixed": 740_000,  "reduce_rate": None,  "base": None,    "ref": None,         "floor": None},
            {"salary_max": 70_000_000,  "fixed": None,      "reduce_rate": 0.008, "base": 740_000, "ref": 33_000_000,   "floor": 660_000},
            {"salary_max": 120_000_000, "fixed": None,      "reduce_rate": 0.5,   "base": 660_000, "ref": 70_000_000,   "floor": 500_000},
            {"salary_max": None,        "fixed": None,      "reduce_rate": 0.5,   "base": 500_000, "ref": 120_000_000,  "floor": 200_000},
        ]
        tcl_js_rows = []
        for seg in tcl_limits:
            sm = seg.get("salary_max")
            fx = seg.get("fixed")
            rr = seg.get("reduce_rate")
            ba = seg.get("base")
            rf = seg.get("ref")
            fl = seg.get("floor")
            tcl_js_rows.append(
                f'{{sm:{sm if sm is not None else "Infinity"},'
                f'fx:{fx if fx is not None else "null"},'
                f'rr:{rr if rr is not None else "null"},'
                f'ba:{ba if ba is not None else "null"},'
                f'rf:{rf if rf is not None else "null"},'
                f'fl:{fl if fl is not None else "null"}}}'
            )
        tcl_js = "[" + ",".join(tcl_js_rows) + "]"
        return (
            _js_open()
            + _js_read("total_salary")
            + '  var family_count  = inputs["family_count"]  || 1;\n'
            + _js_read("paid_tax")
            + '  if (total_salary <= 0) { return null; }\n'
            + '  family_count = Math.max(1, Math.round(family_count));\n'
            + _js_init_out()
            + (
            # 4대보험 요율 상수
            f'  var NP_RATE={NP_RATE}; var NP_MIN={NP_MIN}; var NP_MAX={NP_MAX};\n'
            f'  var HI_RATE={HI_RATE}; var LTC_RATE={LTC_RATE}; var EI_RATE={EI_RATE};\n'
            f'  var LD_MAX={LD_MAX}; var PER_PERSON={PER_PERSON};\n'
            f'  var CREDIT_THRESHOLD={CREDIT_THRESHOLD};\n'
            f'  var CREDIT_RATE_LOW={CREDIT_RATE_LOW}; var CREDIT_RATE_HIGH={CREDIT_RATE_HIGH};\n'
            f'  var CREDIT_BASE_HIGH={CREDIT_BASE_HIGH};\n'
            # ②근로소득공제 계산 함수
            f'  var LD_TBL={ld_js};\n'
            '  function laborDeduction(s) {\n'
            '    for (var i=0;i<LD_TBL.length;i++) {\n'
            '      if (s <= LD_TBL[i].lim) {\n'
            '        return Math.min(LD_TBL[i].base + (s - LD_TBL[i].prev) * LD_TBL[i].rate, LD_MAX);\n'
            '      }\n'
            '    }\n'
            '    return LD_MAX;\n'
            '  }\n'
            # ⑦산출세액 계산 함수
            f'  var TAX_TBL={tb_js};\n'
            '  function incomeTax(t) {\n'
            '    if (t <= 0) { return 0; }\n'
            '    for (var i=0;i<TAX_TBL.length;i++) {\n'
            '      if (t <= TAX_TBL[i].lim) {\n'
            '        return Math.max(0, Math.round(t * TAX_TBL[i].rate - TAX_TBL[i].ded));\n'
            '      }\n'
            '    }\n'
            '    return Math.max(0, Math.round(t * 0.45 - 65940000));\n'
            '  }\n'
            # ⑧근로소득세액공제 한도 계산 함수
            f'  var TCL_TBL={tcl_js};\n'
            '  function creditLimit(s) {\n'
            '    for (var i=0;i<TCL_TBL.length;i++) {\n'
            '      if (s <= TCL_TBL[i].sm) {\n'
            '        if (TCL_TBL[i].fx !== null) { return TCL_TBL[i].fx; }\n'
            '        return Math.max(TCL_TBL[i].ba - (s - TCL_TBL[i].rf) * TCL_TBL[i].rr, TCL_TBL[i].fl);\n'
            '      }\n'
            '    }\n'
            '    return 200000;\n'
            '  }\n'
            '  function earnedCredit(gt) {\n'
            '    if (gt <= CREDIT_THRESHOLD) { return Math.round(gt * CREDIT_RATE_LOW); }\n'
            '    return Math.round(CREDIT_BASE_HIGH + (gt - CREDIT_THRESHOLD) * CREDIT_RATE_HIGH);\n'
            '  }\n'
            # ① 총급여
            '  var gross = total_salary;\n'
            # ② 근로소득공제
            '  var labor_ded = Math.round(laborDeduction(gross));\n'
            # ③ 근로소득금액
            '  var labor_income = gross - labor_ded;\n'
            # ④ 인적공제
            '  var personal_ded = Math.min(family_count * PER_PERSON, labor_income);\n'
            # ⑤ 4대보험공제
            '  var monthly = gross / 12;\n'
            '  var np_base = Math.min(Math.max(monthly, NP_MIN), NP_MAX);\n'
            '  var np_m  = np_base  * NP_RATE;\n'
            '  var hi_m  = monthly  * HI_RATE;\n'
            '  var ltc_m = hi_m     * LTC_RATE;\n'
            '  var ei_m  = monthly  * EI_RATE;\n'
            '  var ins_ded = Math.round((np_m + hi_m + ltc_m + ei_m) * 12);\n'
            # ⑥ 과세표준
            '  var taxable = Math.max(0, labor_income - personal_ded - ins_ded);\n'
            # ⑦ 산출세액
            '  var gross_tax = incomeTax(Math.round(taxable));\n'
            # ⑧ 세액공제
            '  var raw_credit = earnedCredit(gross_tax);\n'
            '  var cl = Math.round(creditLimit(gross));\n'
            '  var tax_credit = Math.min(raw_credit, cl);\n'
            # ⑨ 결정세액
            '  var determined = Math.max(0, gross_tax - tax_credit);\n'
            # ⑩ 지방소득세
            '  var local_tax = Math.round(determined * 0.10);\n'
            # ⑪ 환급/추가납부
            '  var refund = Math.round(paid_tax) - determined;\n'
            '  out["estimated_refund"] = refund;\n'
            # _detail 11단계
            '  out._detail = [\n'
            '    {label:"①총급여",                value:gross.toLocaleString()+"원"},\n'
            '    {label:"②근로소득공제",           value:labor_ded.toLocaleString()+"원 차감"},\n'
            '    {label:"③근로소득금액",           value:labor_income.toLocaleString()+"원"},\n'
            '    {label:"④인적공제",              value:(-personal_ded).toLocaleString()+"원 ("+family_count+"명)"},\n'
            '    {label:"⑤4대보험공제(연간)",      value:(-ins_ded).toLocaleString()+"원"},\n'
            '    {label:"⑥과세표준",              value:Math.round(taxable).toLocaleString()+"원"},\n'
            '    {label:"⑦산출세액",              value:gross_tax.toLocaleString()+"원"},\n'
            '    {label:"⑧근로소득세액공제",       value:(-tax_credit).toLocaleString()+"원"},\n'
            '    {label:"⑨결정세액",              value:determined.toLocaleString()+"원"},\n'
            '    {label:"⑩지방소득세(10%)",       value:local_tax.toLocaleString()+"원"},\n'
            '    {label:"⑪기납부세액",            value:Math.round(paid_tax).toLocaleString()+"원"},\n'
            '  ];\n'
            # notices
            '  out.notices.push("4대보험료는 현재 기준 요율로 자동 계산한 예상값이며 실제 원천징수영수증과 차이가 있을 수 있습니다.");\n'
            '  out.notices.push("본 계산 결과는 참고용 예상치이며, 실제 연말정산 결과는 국세청 홈택스 및 회사 정산 결과와 다를 수 있습니다.");\n'
            '  if (refund >= 0) {\n'
            '    out.notices.push("환급 예상: 기납부세액이 결정세액보다 " + refund.toLocaleString() + "원 많아 환급될 것으로 보입니다.");\n'
            '  } else {\n'
            '    out.notices.push("추가납부 예상: 결정세액이 기납부세액보다 " + (-refund).toLocaleString() + "원 많아 추가 납부가 필요할 것으로 보입니다.");\n'
            '  }\n'
            # _formula (1줄 요약)
            '  out._formula = "총급여 "+gross.toLocaleString()+"원 → 과세표준 "+Math.round(taxable).toLocaleString()+'
            '"원 → 산출세액 "+gross_tax.toLocaleString()+"원 → 결정세액 "+determined.toLocaleString()+'
            '"원 → "+(refund>=0?"환급 "+refund.toLocaleString()+"원":"추가납부 "+(-refund).toLocaleString()+"원");\n'
            '  return out;\n};\n'
            )
        )
    if str(calc.get("slug", "")) == "freelancer-tax-3p3":
        # 소득세법 제127조: 원천징수세액 = gross × 3.3%, 실수령액 = gross × 96.7%
        # 원천징수는 선납(최종 세액 아님) — notice로 안내
        return (
            _js_open()
            + _js_read("gross_income")
            + '  if (gross_income <= 0) { return null; }\n'
            + _js_init_out()
            + '  var withholding = Math.round(gross_income * 0.033);\n'
            + '  var net = gross_income - withholding;\n'
            + '  out["withholding_tax"] = withholding;\n'
            + '  out["net_income"] = net;\n'
            + '  out.notices.push("원천징수액은 최종 세액이 아닙니다. 매년 5월 종합소득세 신고 시 실제 세액으로 정산됩니다 (소득세법 제127조).");\n'
            + '  out._formula = "총수입 " + gross_income.toLocaleString() + "원 × 3.3% = 원천징수 " + withholding.toLocaleString() + "원 | 실수령액 " + net.toLocaleString() + "원";\n'
            + '  return out;\n};\n'
        )
    if _compute_type(calc) == "date_based":   # 날짜 기반(입사일/퇴사일 → total_days)
        return (
            _js_open()
            + '  var s = new Date(inputs["start_date"]); var e = new Date(inputs["end_date"]);\n'
            # SP-3: 날짜 미입력/Invalid Date → null (입력 오류)
            + '  if (isNaN(s.getTime()) || isNaN(e.getTime())) { return null; }\n'
            + '  var total_days = Math.floor((e - s) / (1000*60*60*24));\n'
            + _js_read("avg_monthly_wage")
            # SP-4: 평균임금 0 이하 → null (입력 오류)
            + '  if (avg_monthly_wage <= 0) { return null; }\n'
            + _js_init_out()
            + (
            # SP-1: 재직 1년(365일) 미만 → 0원 + notice (근로자퇴직급여보장법 제8조)
            '  if (total_days < 365) {\n'
            '    out["severance_pay"] = 0;\n'
            '    out.notices.push("계속근로기간이 1년 미만이면 퇴직금 지급 의무가 없습니다 (근로자퇴직급여보장법 제8조).");\n'
            '    out._detail = [{label:"재직일수", value:(total_days > 0 ? total_days : 0) + "일 (1년 미만)"}];\n'
            '    out._formula = total_days + "일 근무 — 1년(365일) 미만으로 퇴직금 미발생";\n'
            '    return out;\n'
            '  }\n'
            '  out["severance_pay"] = avg_monthly_wage * (total_days / 365);\n'
            '  out._detail = [{label:"재직일수", value:total_days + "일"}];\n'
            '  out._formula = avg_monthly_wage.toLocaleString() + "원 × (" + total_days + "÷365) = " + Math.round(avg_monthly_wage * (total_days / 365)).toLocaleString() + "원";\n'
            '  return out;\n};\n'
            )
        )
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    formula = _pj(calc.get("formula"), calc.get("formula", ""))
    fmap = _formula_map(formula, outs)
    reads = "".join(f'  var {n} = inputs["{n}"] || 0;\n' for n in ins.keys())

    slug = str(calc.get("slug", ""))
    rules = (_registry().get(slug) or {}).get("compute_rules") or {}
    validation = _compute_validation_js(rules, fmap) if rules else ""

    if validation:
        # 검증 블록 있음: reads → notices 초기화 → 검증 → 수식 → _formula → return
        out_key = next(iter(fmap))
        out_expr = _to_js(next(iter(fmap.values())))
        in_keys = list(ins.keys())
        if len(in_keys) == 2:
            # 기존 2-input 계산기(예: 주휴수당) 문구 그대로 유지 — 회귀 방지.
            formula_str = (f"{in_keys[0]}.toLocaleString() + '원 × (' "
                           f"+ {in_keys[1]} + '÷40×8) = ' "
                           f"+ Math.round({out_expr}).toLocaleString() + '원'")
        else:
            # STEP 28-7: 위 2-input 전용 문구("A × (B÷40×8)")는 특정 계산기의 실제
            # 수식 형태를 그대로 박아둔 것이라 입력 개수가 다르면 재사용할 수 없다.
            # 입력 개수/출력 개수에 관계없이 항상 안전하게 동작하도록, 실제 계산식과
            # 다른 가짜 수식을 만드는 대신 입력값·산출값을 라벨과 함께 그대로 나열한다
            # (다중 출력도 첫 번째만이 아니라 전부 포함).
            labels = _effective_labels(calc)
            in_join = (
                " + ', ' + ".join(f"'{_label(k, labels)}: ' + {k}.toLocaleString()" for k in in_keys)
                if in_keys else "''"
            )
            out_join = " + ', ' + ".join(
                f"'{_label(k, labels)}: ' + Math.round({_to_js(expr)}).toLocaleString()"
                for k, expr in fmap.items()
            )
            formula_str = f"({in_join}) + ' → ' + ({out_join})"
        # fmap의 모든 출력 key를 처리 (단일/다중 출력 공통)
        out_lines = "".join(
            f'  out["{k}"] = ({_to_js(expr)});\n' for k, expr in fmap.items()
        )
        body = (
            "  var out = {};\n"
            "  out.notices = [];\n"
            + validation
            + out_lines
            + f'  out._formula = {formula_str};\n'
        )
    else:
        body = "  var out = {};\n" + "".join(
            f'  out["{k}"] = ({_to_js(expr)});\n' for k, expr in fmap.items())

    return "window.computeResult = function(inputs){\n" + reads + body + "  return out;\n};\n"


def _compute_validation_js(rules: dict, fmap: dict) -> str:
    """compute_rules YAML → JS 검증 코드 블록 생성.
    양수 입력 체크 → 최솟값(주 시간 등) 체크 → 최저임금 경고 순."""
    lines = []
    positive = rules.get("positive_inputs") or []
    if positive:
        cond = " || ".join(f"{n} <= 0" for n in positive)
        lines.append(f"  if ({cond}) {{ return null; }}\n")

    min_hours = rules.get("min_weekly_hours")
    min_hours_field = "weekly_hours"
    min_hours_law = rules.get("min_weekly_hours_law", "")
    if min_hours is not None:
        out_key = next(iter(fmap))
        notice_msg = (f"주 {min_hours}시간 미만 근무 시 주휴수당이 발생하지 않습니다"
                      + (f" ({min_hours_law})." if min_hours_law else "."))
        lines.append(
            f"  if ({min_hours_field} < {min_hours}) {{\n"
            f'    out["{out_key}"] = 0;\n'
            f'    out.notices.push("{notice_msg}");\n'
            f'    out._formula = "주 " + {min_hours_field} + "시간 미만({min_hours}시간 기준) — 주휴수당 미발생";\n'
            f"    return out;\n"
            f"  }}\n"
        )

    min_wage = rules.get("min_wage")
    min_wage_year = rules.get("min_wage_year", "")
    min_wage_field = rules.get("min_wage_field", "")
    if min_wage and min_wage_field:
        label_str = f"{min_wage_year}년 최저임금({min_wage:,}원)" if min_wage_year else f"최저임금({min_wage:,}원)"
        lines.append(
            f"  if ({min_wage_field} < {min_wage}) {{\n"
            f'    out.notices.push("입력한 시급(" + {min_wage_field}.toLocaleString() + "원)이 {label_str}보다 낮습니다.");\n'
            f"  }}\n"
        )

    return "".join(lines)


def _formula_map(formula, output_schema) -> dict:
    if isinstance(formula, dict):
        return formula
    keys = list((output_schema or {}).keys())
    return {(keys[0] if keys else "result"): formula}


def _effective_form(calc: dict, cfg: dict = None):
    """(form_schema, [field_names]) 반환. input_schema 우선, 없으면 Form Engine."""
    ins = _pj(calc.get("input_schema"), {})
    if ins:
        fields = [{"type": ("date" if "date" in str(ins[k]).lower() else "number"),
                   "label": _label(k), "name": k} for k in ins]
        return {"fields": fields}, list(ins.keys())
    try:
        from .calculator_form_engine import generate_form_schema
        sch = generate_form_schema(cfg or {}, calc.get("name", ""))
    except Exception:
        sch = {"fields": [{"type": "number", "label": "값1", "name": "value1"}]}
    return sch, [f.get("name") for f in sch.get("fields", [])]


# ── JS (design v2: 공통 컴포넌트 모듈 + 계산기별 computeResult) ────
def generate_js(calc: dict, cfg: dict = None) -> str:
    """script.js = 공통 컴포넌트 모듈 + 계산기별 computeResult() + Phase D 동적 설정."""
    parts = [_read_assets_js(), "\n\n", _compute_js(calc)]
    # Phase D-3: CTA Rule Engine 설정
    cta_js = _cta_rules_js(calc)
    if cta_js:
        parts.append("\n" + cta_js)
    # Phase D-4: Dynamic FAQ 설정
    faq_js = _dynamic_faq_js(calc)
    if faq_js:
        parts.append(faq_js)
    return "".join(parts)


# ── CSS (공개 계산기용 라이트 테마) ───────────────────────────────
def generate_css(calc: dict = None) -> str:
    """style.css = design_system.css(공식 마스터 시안). 모든 계산기 공통(UI 불변)."""
    p = _ASSETS / "design_system.css"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ── 섹션 빌더 ─────────────────────────────────────────────────────
def _form_html(calc, cfg):
    sch, _ = _effective_form(calc, cfg)
    try:
        from .calculator_form_engine import build_form_html
        return build_form_html(sch, "in")
    except Exception:
        return "<p>입력 항목이 없습니다.</p>"


def _result_html(calc):
    outs = _pj(calc.get("output_schema"), {})
    rows = "".join(f'<div class="r"><span>{_html.escape(_label(k))}</span>'
                   f'<strong id="out_{k}">-</strong></div>' for k in outs)
    return rows or '<div class="r"><span>결과</span><strong id="out_result">-</strong></div>'


def _faq_html(calc):
    faq = _pj(calc.get("faq"), [])
    if not isinstance(faq, list) or not faq:
        return "<p>등록된 FAQ가 없습니다.</p>"
    return "".join(
        f'<details><summary>{_html.escape(str(f.get("question", f.get("q",""))))}</summary>'
        f'<p>{_html.escape(str(f.get("answer", f.get("a",""))))}</p></details>'
        for f in faq if isinstance(f, dict))


def _explanation_html(calc):
    desc = _html.escape(calc.get("seo_desc") or calc.get("seo_description") or "")
    formula = calc.get("formula", "")
    parts = [f"<p>{desc}</p>"] if desc else []
    if formula:
        parts.append(f'<p class="sm-sub">계산식: <code>{_html.escape(str(formula))}</code></p>')
    return "".join(parts) or "<p>입력값을 넣고 계산하기를 누르세요.</p>"


def _related_html(calc):
    """site_mode에 따라 관련계산기/광고/공유/리포트 노출."""
    try:
        from . import site_mode_manager as SM
        ads, related = SM.is_ads_enabled(), SM.is_related_enabled()
        share, report = SM.is_share_enabled(), SM.is_report_enabled()
    except Exception:
        ads = related = share = report = False
    blocks = []
    if ads:
        blocks.append('<section class="sm-card"><div class="sm-ad">광고 영역 (AdSense)</div></section>')
    if related:
        blocks.append('<section class="sm-card sm-related"><h2>관련 계산기</h2>'
                      '<a href="../">CalcMate 계산기 모음 →</a></section>')
    if share:
        blocks.append('<section class="sm-card"><h2>공유</h2>'
                      '<a href="#" onclick="navigator.share&&navigator.share({title:document.title,url:location.href});return false">🔗 공유하기</a></section>')
    if report:
        blocks.append('<section class="sm-card"><h2>상세 리포트</h2>'
                      '<a href="#">📄 PDF 리포트 받기</a></section>')
    return "\n".join(blocks)


# ── 섹션 렌더 함수(show_*=False면 감싸는 태그 포함 전체 생략) ────────
# 원칙: HTML 생성 경로는 generate_html() 하나. 이 함수들은 조각만 반환하고
# generate_html이 플레이스홀더에 조립. show=True 산출물은 기존 템플릿과 byte 동일.
def render_adsense_slot(cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_adsense"]:
        return ""
    return ('  <!-- [광고 슬롯 — 기본 숨김, 대시보드 show_adsense로만 노출] -->\n'
            '  <div class="sm-adsense"><!-- 애드센스 승인 후 활성화 --></div>')


# ── Phase D: Placeholder Engine ───────────────────────────────────────────────
_PH_SCHEMA_CACHE: dict = {}
_CTA_RULES_CACHE: dict = {}


def _load_yaml_cached(path: Path, cache: dict) -> dict:
    key = str(path)
    if key not in cache:
        try:
            cache[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            cache[key] = {}
    return cache[key]


def _placeholder_schema(slug: str) -> dict:
    """계산기별 플레이스홀더 화이트리스트 반환 (expose/formatter/fallback)."""
    all_schemas = _load_yaml_cached(_DOCS_DIR / "placeholder_schemas.yaml", _PH_SCHEMA_CACHE)
    return all_schemas.get(str(slug)) or {}


def _cta_rules(slug: str) -> dict:
    """계산기별 CTA 규칙 반환 (default + rules 리스트)."""
    all_rules = _load_yaml_cached(_DOCS_DIR / "cta_rules.yaml", _CTA_RULES_CACHE)
    return all_rules.get(str(slug)) or {}


def _apply_article_placeholders(article_html: str, slug: str) -> str:
    """article_content 내 {variable} 패턴을 <span data-ph> 로 변환.

    3분기 규칙:
      - 변수 존재 + expose:true  → <span data-ph="var" data-fmt="fmt">fallback</span>
      - 변수 expose:false        → 빌드 오류 로그 + PLACEHOLDER_SECURITY 마킹
      - 변수 미정의(스키마 없음) → 빌드 오류 로그 + PLACEHOLDER_ERROR 마킹
    """
    schema = _placeholder_schema(slug)
    errors = []

    def _replace(m):
        var = m.group(1)
        if var not in schema:
            msg = f"[SP-8] PLACEHOLDER_ERROR: '{{{var}}}' not in schema for '{slug}'"
            _log.error(msg)
            errors.append(msg)
            return f'<span class="sm-ph-error">[PLACEHOLDER_ERROR:{var}]</span>'
        spec = schema[var]
        if not spec.get("expose", True):
            msg = f"[SP-8] PLACEHOLDER_SECURITY: '{{{var}}}' expose=false blocked in '{slug}'"
            _log.error(msg)
            errors.append(msg)
            return f'<span class="sm-ph-error">[PLACEHOLDER_SECURITY:{var}]</span>'
        fmt = str(spec.get("formatter", "text"))
        fallback = _html.escape(str(spec.get("fallback", var)))
        return (f'<span data-ph="{_html.escape(var)}" '
                f'data-fmt="{_html.escape(fmt)}">{fallback}</span>')

    result = re.sub(r'\{([A-Za-z_][A-Za-z0-9_]*)\}', _replace, article_html)
    if errors:
        _log.error("[Phase D] %d placeholder error(s) in '%s': %s", len(errors), slug, errors)
    return result


def _cta_rules_js(calc: dict) -> str:
    """window.SM_CTA_RULES — 계산기별 CTA 룰 JS 객체 생성 (D-3 Rule Engine)."""
    slug = str(calc.get("slug", ""))
    rules_data = _cta_rules(slug)
    if not rules_data:
        return ""
    return f"window.SM_CTA_RULES = {json.dumps(rules_data, ensure_ascii=False)};\n"


def _dynamic_faq_js(calc: dict) -> str:
    """window.SM_DYNAMIC_FAQ — 계산기별 조건부 FAQ 항목 JS 객체 생성 (D-4).

    우선순위 (여러 조건 겹칠 때):
      1 = 법적 예외 (수급불가 케이스)
      2 = 상한/하한 적용
      3 = 결과 관련 (환급/추가납부/발생/미발생)
      4 = 일반 (정적 FAQ — JS 불필요, HTML에 이미 있음)
    """
    slug = str(calc.get("slug", ""))
    faq_map = {
        "weekly-holiday-allowance": [
            {"priority": 1, "condition": "outputs.weekly_holiday_pay === 0 && (outputs.notices||[]).length > 0",
             "q": "주 15시간 미만인데 주휴수당이 0원인 이유는?",
             "a": "주휴수당은 1주 소정 근로시간이 15시간 이상인 근로자에게만 발생합니다 (근로기준법 제18조제3항). "
                  "주 15시간 미만 근로자는 주휴수당 지급 의무가 없습니다."},
            {"priority": 3, "condition": "outputs.weekly_holiday_pay > 0",
             "q": "계산된 주휴수당이 실제 지급액과 다를 수 있나요?",
             "a": "본 계산기는 법정 기준으로 산출한 예상치입니다. 실제 지급액은 근로계약서 내용 및 사업장 규정에 따라 달라질 수 있습니다."},
        ],
        "severance-pay": [
            {"priority": 1, "condition": "outputs.severance_pay === 0 && (outputs.notices||[]).length > 0",
             "q": "1년 미만 근무라서 퇴직금이 0원인 이유는?",
             "a": "근로자퇴직급여보장법 제8조에 따라 계속근로기간이 1년 미만인 경우 퇴직금 지급 의무가 없습니다. "
                  "1년 이상 근무 후 퇴직 시 퇴직금이 발생합니다."},
            {"priority": 3, "condition": "outputs.severance_pay > 0",
             "q": "퇴직금 수령 후 실업급여도 받을 수 있나요?",
             "a": "퇴직금과 실업급여는 별개입니다. 퇴직금을 수령한 후에도 고용보험 수급 자격을 충족하면 실업급여를 신청할 수 있습니다."},
        ],
        "annual-leave-allowance": [
            {"priority": 2, "condition": "inputs.unused_days > 25",
             "q": "미사용 연차가 25일을 초과한 경우 수당은 어떻게 계산하나요?",
             "a": "근로기준법 제60조 제4항에 따라 법정 연차는 최대 25일까지 인정됩니다. "
                  "25일 초과분은 취업규칙이나 단체협약에 따른 약정 연차이므로 별도 규정을 확인하세요."},
            {"priority": 3, "condition": "outputs.annual_leave_allowance > 0",
             "q": "연차수당을 받을 때 세금이 공제되나요?",
             "a": "연차수당은 근로소득에 해당하므로 소득세와 4대보험이 공제됩니다. 실수령액은 세후 금액으로 계산하세요."},
        ],
        "unemployment-benefit": [
            {"priority": 1, "condition": "outputs.total_benefit === 0 && (outputs.notices||[]).length > 0",
             "q": "피보험단위기간 6개월 미만이라 실업급여를 받을 수 없나요?",
             "a": "고용보험법 제40조에 따라 이직 전 18개월 이내에 피보험단위기간이 합산 180일(약 6개월) 이상이어야 구직급여를 수급할 수 있습니다. "
                  "복수의 직장에서 근무한 기간을 합산할 수 있습니다."},
            {"priority": 2, "condition": "(outputs.notices||[]).some(function(n){return n.indexOf('상한')>=0 || n.indexOf('하한')>=0;})",
             "q": "구직급여 상한액/하한액이 적용됐는데 왜 그런가요?",
             "a": "구직급여는 1일 상한액(66,000원)과 하한액(최저임금의 80%)이 법으로 정해져 있습니다(고용보험법 제46조). "
                  "실제 임금과 무관하게 이 범위 내에서 지급됩니다."},
            {"priority": 3, "condition": "outputs.total_benefit > 0",
             "q": "실업급여는 언제부터 받을 수 있나요?",
             "a": "퇴직 후 고용센터에 수급자격 신청(워크넷 구직 등록 후)을 하면 약 7~14일의 처리 기간 이후 지급이 시작됩니다. "
                  "자발적 퇴사는 원칙적으로 실업급여 수급이 불가합니다."},
        ],
        "four-insurances": [
            {"priority": 2, "condition": "(outputs.notices||[]).some(function(n){return n.indexOf('상한')>=0 || n.indexOf('하한')>=0;})",
             "q": "국민연금 기준소득월액 상한/하한이 적용됐는데 왜 그런가요?",
             "a": "국민연금은 기준소득월액에 상한(6,170,000원)과 하한(390,000원)이 있습니다(국민연금법 제88조). "
                  "실제 월급과 무관하게 이 범위 내에서 보험료가 산정됩니다."},
            {"priority": 3, "condition": "outputs.total > 0",
             "q": "사업주가 부담하는 4대보험료는 얼마인가요?",
             "a": "사업주는 근로자와 동일하게 국민연금·건강보험·고용보험을 분담합니다. "
                  "산재보험은 사업주가 100% 부담하며 근로자 공제 없습니다."},
        ],
        "연말정산_환급액_계산기": [
            {"priority": 2, "condition": "(outputs.notices||[]).some(function(n){return n.indexOf('상한')>=0 || n.indexOf('하한')>=0;})",
             "q": "4대보험료가 상한/하한으로 조정된 이유는?",
             "a": "국민연금은 기준소득월액 상한(6,170,000원)/하한(390,000원) 범위에서 계산됩니다. "
                  "건강보험·고용보험은 실제 월급 기준이며 상한이 없습니다."},
            {"priority": 3, "condition": "outputs.estimated_refund > 0",
             "q": "환급금은 언제 받을 수 있나요?",
             "a": "2월 말 연말정산 완료 후 3월 급여일에 환급금이 지급되는 것이 일반적입니다. "
                  "회사마다 지급 시기가 다를 수 있으며, 직접 신고한 경우 5월 종합소득세 신고 후 환급됩니다."},
            {"priority": 3, "condition": "outputs.estimated_refund < 0",
             "q": "추가납부액을 줄이려면 어떻게 해야 하나요?",
             "a": "연금저축·IRP·의료비·교육비·기부금 등 세액공제 항목을 최대한 활용하면 결정세액을 낮출 수 있습니다. "
                  "연간 계획적인 공제 항목 관리가 중요합니다."},
        ],
        "육아휴직_급여_계산기": [
            {"priority": 1, "condition": "outputs.monthly_allowance === 0 && (outputs.notices||[]).length > 0",
             "q": "피보험단위기간 180일 미만이라 육아휴직 급여를 받을 수 없나요?",
             "a": "고용보험법 제70조 제1항에 따라 육아휴직 개시일 이전 피보험단위기간이 합산 180일 이상이어야 합니다. "
                  "복수 사업장 근무 기간을 합산할 수 있습니다."},
            {"priority": 2, "condition": "(outputs.notices||[]).some(function(n){return n.indexOf('상한')>=0;})",
             "q": "통상임금이 높은데 상한액이 적용된 이유는?",
             "a": "일반 육아휴직급여는 월 최대 150만원(고용보험법 시행령 제95조), "
                  "6+6 특례는 1~6개월차별로 200만~450만원의 상한이 적용됩니다."},
            {"priority": 3, "condition": "outputs.monthly_allowance > 0",
             "q": "6+6 부모 육아휴직 특례란 무엇인가요?",
             "a": "2024년 1월 시행된 제도로 부모가 함께 육아휴직을 사용할 때 최대 6개월간 급여를 높게 지급하는 특례입니다. "
                  "배우자도 육아휴직 중이어야 하며, 순서는 무관합니다(고용보험법 시행령 제95조의2)."},
        ],
    }
    items = faq_map.get(slug, [])
    if not items:
        return ""
    return f"window.SM_DYNAMIC_FAQ = {json.dumps(items, ensure_ascii=False)};\n"


# ── Phase E: SEO · Analytics · 수익화 ────────────────────────────────────────

# E-1/E-4 내부링크: 계산기 키워드 → (상대 href, 앵커 텍스트 변형 리스트)
_INTERNAL_LINK_MAP = {
    "weekly-holiday-allowance": (
        "../weekly-holiday-allowance/",
        ["주휴수당 계산기", "주휴수당 계산", "주휴수당 자동 계산"],
    ),
    "severance-pay": (
        "../severance-pay/",
        ["퇴직금 계산기", "퇴직금 계산", "퇴직금 자동 산정"],
    ),
    "annual-leave-allowance": (
        "../annual-leave-allowance/",
        ["연차수당 계산기", "연차수당 계산", "연차수당 자동 산정"],
    ),
    "unemployment-benefit": (
        "../unemployment-benefit/",
        ["실업급여 계산기", "구직급여 계산", "실업급여 자동 계산"],
    ),
    "four-insurances": (
        "../four-insurances/",
        ["4대보험 계산기", "4대보험료 계산", "4대보험 자동 계산"],
    ),
    "연말정산_환급액_계산기": (
        "../연말정산_환급액_계산기/",
        ["연말정산 계산기", "연말정산 환급액 계산", "연말정산 시뮬레이션"],
    ),
    "육아휴직_급여_계산기": (
        "../육아휴직_급여_계산기/",
        ["육아휴직 급여 계산기", "육아휴직 급여 계산", "육아휴직 급여 시뮬레이션"],
    ),
}

# 키워드 → slug 매핑 (길이 내림차순: 긴 키워드 우선 매칭)
_KW_SLUG = [
    ("주휴수당", "weekly-holiday-allowance"),
    ("연차수당", "annual-leave-allowance"),
    ("실업급여", "unemployment-benefit"),
    ("구직급여", "unemployment-benefit"),
    ("4대보험", "four-insurances"),
    ("연말정산", "연말정산_환급액_계산기"),
    ("육아휴직", "육아휴직_급여_계산기"),
    ("퇴직금", "severance-pay"),
]

# _SLUG_ORDER 제거 (P2-2-C) — _auto_internal_links가 _INTERNAL_LINK_MAP에서 직접 도출.


def _auto_internal_links(html: str, cur_slug: str, site_url: str = "") -> str:
    """article_content HTML에서 자매 계산기 첫 출현 키워드를 내부링크로 변환.

    규칙:
      - 현재 계산기 자기 자신 제외
      - 각 타겟 계산기는 첫 출현만 링크 (중복 방지)
      - 기존 <a>…</a> 내부 텍스트는 건드리지 않음
      - 앵커 텍스트는 소스 슬러그 인덱스 기반으로 다양화
    """
    src_idx = list(_INTERNAL_LINK_MAP).index(cur_slug) if cur_slug in _INTERNAL_LINK_MAP else 0
    linked: set = set()
    in_anchor = 0
    base = site_url.rstrip("/") if site_url else ""

    tokens = re.split(r'(<[^>]+>)', html)
    result = []
    for token in tokens:
        if token.startswith('<'):
            tag_lower = token.lower().lstrip('<').split()[0] if token.lstrip('<') else ''
            if tag_lower == 'a':
                in_anchor += 1
            elif tag_lower == '/a':
                in_anchor = max(0, in_anchor - 1)
            result.append(token)
        elif in_anchor > 0:
            result.append(token)
        else:
            for kw, slug in _KW_SLUG:
                if slug == cur_slug or slug in linked or kw not in token:
                    continue
                href_rel, variants = _INTERNAL_LINK_MAP[slug]
                href = f"{base}/{slug}/" if base else href_rel
                anchor = _html.escape(variants[src_idx % len(variants)])
                linked.add(slug)
                # kw 바로 뒤에 " 계산기"가 오면 함께 소비해 anchor 중복 방지
                kw_ext = kw + " 계산기"
                match_kw = kw_ext if kw_ext in token else kw
                token = token.replace(
                    match_kw,
                    f'<a href="{_html.escape(href)}" class="sm-internal-link">{anchor}</a>',
                    1,
                )
            result.append(token)
    return "".join(result)


def _render_ga4_script(cfg: dict = None) -> str:
    """E-1: GA4 gtag.js 스크립트 블록. GA4_MEASUREMENT_ID 미설정 시 빈 문자열."""
    ga4_id = str((cfg or {}).get("GA4_MEASUREMENT_ID", ""))
    if not ga4_id:
        return ""
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={_html.escape(ga4_id)}"></script>\n'
        f'<script>window.dataLayer=window.dataLayer||[];'
        f'function gtag(){{dataLayer.push(arguments);}}'
        f'gtag("js",new Date());gtag("config","{_html.escape(ga4_id)}");</script>'
    )


def render_canonical(calc: dict, cfg: dict = None) -> str:
    site_url = str((cfg or {}).get("SITE_URL", "https://salarymate.github.io"))
    slug = str(calc.get("slug", ""))
    if not slug:
        return ""
    return f'<link rel="canonical" href="{site_url.rstrip("/")}/{slug}/">'


def render_json_ld(calc: dict, cfg: dict = None) -> str:
    """E-3: JSON-LD 구조화 데이터 (FAQPage + Organization + BreadcrumbList).
    Rich Results Test 통과 기준으로 생성."""
    site_url = str((cfg or {}).get("SITE_URL", "https://salarymate.github.io"))
    slug = str(calc.get("slug", ""))
    name = calc.get("name", "계산기")
    category = calc.get("category", "계산기")
    faq = _pj(calc.get("faq"), [])

    schemas = []

    # ① FAQPage (FAQ 항목이 있을 때만)
    if isinstance(faq, list) and faq:
        entities = []
        for f in faq:
            if not isinstance(f, dict):
                continue
            q = str(f.get("question", f.get("q", "")))
            a = str(f.get("answer",   f.get("a", "")))
            if q and a:
                entities.append({"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": a}})
        if entities:
            schemas.append({"@context": "https://schema.org", "@type": "FAQPage",
                             "mainEntity": entities})

    # ② Organization
    schemas.append({
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "CalcMate",
        "url": site_url,
        "description": "급여·노무 계산기 모음 — 퇴직금·주휴수당·실업급여·4대보험·연말정산·육아휴직",
    })

    # ③ BreadcrumbList
    calc_url = f"{site_url.rstrip('/')}/{slug}/"
    schemas.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "CalcMate", "item": site_url},
            {"@type": "ListItem", "position": 2, "name": category,
             "item": f"{site_url}/#calculators"},
            {"@type": "ListItem", "position": 3, "name": name, "item": calc_url},
        ],
    })

    blocks = []
    for schema in schemas:
        blocks.append(
            '<script type="application/ld+json">\n'
            + json.dumps(schema, ensure_ascii=False, indent=2)
            + '\n</script>'
        )
    return "\n".join(blocks)


def render_adsense_slot_2(cfg: dict = None) -> str:
    """E-6: 2번째 AdSense 슬롯 — 관련글/관련계산기 이후(페이지 하단). CLS 방지 min-height 확보."""
    if not _show_flags(cfg)["show_adsense"]:
        return ""
    return ('  <!-- [광고 슬롯 2 — 페이지 하단, E-6 배치 최적화] -->\n'
            '  <div class="sm-adsense sm-adsense-2"><!-- 애드센스 승인 후 활성화 --></div>')


def render_article(calc: dict, cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_article"]:
        return ""
    name = calc.get("name", "계산기")
    desc = calc.get("seo_description") or calc.get("seo_desc") or f"{name} 자동 계산"
    slug = str(calc.get("slug", ""))
    article = str(calc.get("article_content", "") or "") \
        or f"<h2>{_html.escape(name)}</h2><p>{_html.escape(desc)}</p>"
    # Phase D-1/D-2: {variable} → <span data-ph> 변환 (빌드 시 유효성 검증 포함)
    article = _apply_article_placeholders(article, slug)
    # E-4: 자매 계산기 내부링크 자동화 + 앵커 텍스트 다양화
    article = _auto_internal_links(article, slug, str((cfg or {}).get("SITE_URL", "")))
    return ('  <!-- ⑧ 본문 -->\n'
            '  <section class="sm-card sm-article">\n'
            f'    {article}\n'
            '  </section>')


def render_cpa_slot(cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_cpa"]:
        return ""
    return ('  <!-- [CPA 슬롯 — 기본 숨김, 대시보드 show_cpa로만 노출] -->\n'
            '  <div class="sm-cpa"><!-- 수익화 단계 2 이후 활성화 --></div>')


# ── Phase C: 추가 섹션 렌더 함수 ──────────────────────────────────
_CTA1 = {
    "weekly-holiday-allowance":  ("연차수당도 계산해 보기",   "/annual-leave-allowance/"),
    "severance-pay":             ("실업급여도 계산해 보기",   "/unemployment-benefit/"),
    "unemployment-benefit":      ("퇴직금도 계산해 보기",     "/severance-pay/"),
    "four-insurances":           ("주휴수당도 계산해 보기",   "/weekly-holiday-allowance/"),
    "annual-leave-allowance":    ("연차잔여일도 계산해 보기", "/annual-leave-remaining/"),
    "육아휴직_급여_계산기":      ("실업급여도 확인해 보기",   "/unemployment-benefit/"),
    "연말정산_환급액_계산기":    ("4대보험도 계산해 보기",    "/four-insurances/"),
    "freelancer-tax-3p3":        ("연말정산도 계산해 보기",   "/연말정산_환급액_계산기/"),
    "annual-leave-remaining":    ("연차수당도 계산해 보기",   "/annual-leave-allowance/"),
}


def render_result_cta(calc: dict, cfg: dict = None) -> str:
    """결과 카드 내 CTA — CA-CTA-1 확정 매핑표 기준 (slug 정확 일치)."""
    slug = str(calc.get("slug", ""))
    _base = str((cfg or {}).get("SITE_URL", "")).rstrip("/")
    def _u(path): return f"{_base}{path}" if _base else path
    cta1 = _CTA1.get(slug)
    if cta1:
        label, path = cta1
        links = [(label, _u(path)), ("전체 계산기 보기", _u("/"))]
        text = label
    else:
        links = [("전체 계산기 보기", _u("/"))]
        text = "더 알아보기"
    link_html = "".join(
        f'<a class="sm-result-cta-link" href="{_html.escape(href)}">{_html.escape(lbl)}</a>'
        for lbl, href in links
    )
    return (
        '    <div id="sm-result-cta" class="sm-result-cta">\n'
        f'      <p class="sm-result-cta-text">{_html.escape(text)}</p>\n'
        f'      <div class="sm-result-cta-links">{link_html}</div>\n'
        '    </div>'
    )


def render_inline_cta(calc: dict, cfg: dict = None) -> str:
    """본문 중간 CTA (Article 섹션 직후)."""
    if not _show_flags(cfg).get("show_article", True):
        return ""
    name = calc.get("name", "계산기")
    short = name.replace(" 계산기", "").replace("계산기", "").strip() or name
    return (
        '  <!-- Phase C: 본문 중간 CTA -->\n'
        '  <div class="sm-inline-cta">\n'
        f'    <p class="sm-inline-cta-title">지금 바로 {_html.escape(short)} 계산해 보세요</p>\n'
        '    <p class="sm-inline-cta-sub">무료 · 회원가입 불필요 · 결과 즉시 확인</p>\n'
        '    <a class="sm-inline-cta-btn" href="#" '
        'onclick="window.scrollTo({top:0,behavior:\'smooth\'});return false;">'
        '계산 바로 하기 ↑</a>\n'
        '  </div>'
    )


def render_related_posts(calc: dict, cfg: dict = None) -> str:
    """관련 글 카드 섹션 — V1: 블로그 미운영, 섹션 비활성."""
    return ""
    slug = str(calc.get("slug", ""))  # noqa: F401 — V2 활성화 시 아래 로직 복원
    posts = _RELATED_POSTS.get(slug, [])
    if not posts:
        return ""
    items = "".join(
        f'      <a class="sm-post-card" href="{_html.escape(p["href"])}">\n'
        f'        <span class="sm-post-tag">{_html.escape(p["tag"])}</span>\n'
        f'        <p class="sm-post-title">{_html.escape(p["title"])}</p>\n'
        f'        <p class="sm-post-desc">{_html.escape(p["desc"])}</p>\n'
        f'      </a>\n'
        for p in posts
    )
    return (
        '  <!-- Phase C: 관련 글 -->\n'
        '  <section class="sm-card" id="related-posts-card">\n'
        '    <h2 class="sm-card-title">관련 글</h2>\n'
        '    <div class="sm-posts-grid">\n'
        f'{items}'
        '    </div>\n'
        '  </section>'
    )


def render_top_nav(cfg: dict = None) -> str:
    """계산기 상세 페이지 상단(Hero) 홈/계산기 목록 링크.
    404 페이지(site_generator.generate_404)와 동일한 경로 관례(SITE_URL/, SITE_URL/#calculators)를 재사용."""
    site_url = str((cfg or {}).get("SITE_URL", "")).rstrip("/")
    home_url = f"{site_url}/" if site_url else "/"
    list_url = f"{site_url}/#calculators" if site_url else "/#calculators"
    return (
        '    <nav class="sm-hero-nav" aria-label="사이트 내비게이션">\n'
        f'      <a class="sm-hero-nav-link" href="{_html.escape(home_url)}">홈</a>\n'
        f'      <a class="sm-hero-nav-link" href="{_html.escape(list_url)}">계산기 목록</a>\n'
        '    </nav>'
    )


# STEP 28-10: Footer 문구 범용화 — _NOTICE_BY_SLUG(line 49)와 동일 원칙.
# 여기 없는 slug는 아래 fallback(기존 노무 문구) 그대로 사용해 다른 계산기에는
# 전혀 영향 없다. 실제 문구 콘텐츠 확정은 별도 콘텐츠 STEP에서 진행 — 이번엔
# override 가능한 구조만 추가하고 각 dict는 비워 둔다(기존 표시 문구 그대로 유지).
_FOOTER_CTA_TITLE_BY_SLUG: dict = {}
_FOOTER_CTA_SUB_BY_SLUG: dict = {}
_FOOTER_DISCLAIMER_BY_SLUG: dict = {}


def render_footer_cta(calc: dict, cfg: dict = None) -> str:
    """페이지 하단 CTA (전체 계산기 목록 및 주요 링크)."""
    site_url = str((cfg or {}).get("SITE_URL", "")).rstrip("/")
    home_url = site_url or "/"
    slug = str((calc or {}).get("slug", ""))
    title = _FOOTER_CTA_TITLE_BY_SLUG.get(slug, "CalcMate — 급여·노무 계산기 모음")
    sub = _FOOTER_CTA_SUB_BY_SLUG.get(slug, "퇴직금·주휴수당·실업급여·4대보험·연말정산·육아휴직까지")
    return (
        '  <!-- Phase C: 페이지 하단 CTA -->\n'
        '  <div class="sm-footer-cta">\n'
        f'    <p class="sm-footer-cta-title">{_html.escape(title)}</p>\n'
        f'    <p class="sm-footer-cta-sub">{_html.escape(sub)}</p>\n'
        '    <div class="sm-footer-cta-links">\n'
        f'      <a class="sm-footer-cta-link" href="{home_url}">전체 계산기</a>\n'
        f'      <a class="sm-footer-cta-link" href="{home_url}">다른 계산기 보기</a>\n'
        '    </div>\n'
        '  </div>'
    )


def render_site_footer(calc: dict = None, cfg: dict = None) -> str:
    """사이트 공용 footer — 사이트 5페이지와 동일 구조."""
    u = str((cfg or {}).get("SITE_URL", "")).rstrip("/")
    slug = str((calc or {}).get("slug", ""))
    disclaimer = _FOOTER_DISCLAIMER_BY_SLUG.get(slug, "본 계산기는 참고용이며 실제 지급액과 다를 수 있습니다.")
    _ls = "font-size:13px;color:var(--c-text-sub);text-decoration:none"
    links = "".join(
        f'<a href="{u}{path}" style="{_ls}">{label}</a>'
        for path, label in [
            ("/about/", "소개"),
            ("/privacy/", "개인정보처리방침"),
            ("/terms/", "이용약관"),
            ("/contact/", "문의하기"),
        ]
    )
    return (
        '\n  <!-- ⑫ Footer -->\n'
        '  <footer style="text-align:center;padding-top:var(--sp-3);'
        'border-top:1px solid var(--c-border);margin-top:var(--sp-3)">\n'
        '    <p style="font-size:13px;color:var(--c-text-light);margin-bottom:var(--sp-1)">'
        f'{_html.escape(disclaimer)}</p>\n'
        f'    <div style="font-size:16px;font-weight:800;color:var(--c-primary);'
        f'margin-bottom:var(--sp-1)">CalcMate</div>\n'
        f'    <nav style="display:flex;gap:var(--sp-2);justify-content:center;'
        f'flex-wrap:wrap;margin-bottom:var(--sp-1)">{links}</nav>\n'
        '    <p style="font-size:12px;color:var(--c-text-light)">© 2026 CalcMate. All rights reserved.</p>\n'
        '  </footer>'
    )


def render_faq(calc: dict, cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_faq"]:
        return ""
    # Phase D-4: #sm-dynamic-faq 컨테이너를 정적 FAQ 앞에 삽입
    # JS가 SM_DYNAMIC_FAQ 룰을 평가해 우선순위(1법적예외→2상한하한→3결과관련) 순으로 조건부 주입
    return ('  <!-- ⑨ FAQ -->\n'
            '  <section class="sm-card" id="faq-card">\n'
            '    <h2 class="sm-card-title">자주 묻는 질문</h2>\n'
            '    <div id="sm-dynamic-faq"></div>\n'
            f'    {_faq_items_v2(calc)}\n'
            '  </section>')


def render_related(calc: dict, cfg: dict = None, related_items: str = None) -> str:
    if not _show_flags(cfg)["show_related"]:
        return ""
    items = related_items if related_items is not None else _related_items_v2(calc)
    return ('  <!-- ⑩ 관련 계산기 -->\n'
            '  <section class="sm-card" id="related-card">\n'
            '    <h2 class="sm-card-title">관련 계산기</h2>\n'
            '    <div class="sm-related-grid">\n'
            f'      {items}\n'
            '    </div>\n'
            '  </section>')


# ── HTML (design v2 마스터 시안 치환) ─────────────────────────────
def generate_html(calc: dict, cfg: dict = None) -> str:
    """index.html = calculator_v2.html 시안에 계산기 데이터만 치환. UI는 모든 계산기 동일."""
    name = calc.get("name", "계산기")
    title = calc.get("seo_title") or name
    desc = calc.get("seo_description") or calc.get("seo_desc") or f"{name} 자동 계산"
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    labels = _effective_labels(calc)  # registry v3 field_labels primary, _LABELS fallback
    primary = list(outs.keys())[0] if outs else "result"
    plabel, punit = _split_label(primary, labels)
    # 다중 출력: primary 이후 출력들을 결과 카드 내 추가 행으로 표시
    extra_out_keys = list(outs.keys())[1:]
    if extra_out_keys:
        extra_rows_html = '    <div class="sm-result-extra">\n'
        for k in extra_out_keys:
            klabel, kunit = _split_label(k, labels)
            extra_rows_html += (
                f'      <div class="sm-result-extra-row">'
                f'<span class="sm-result-extra-label">{_html.escape(klabel)}</span>'
                f'<span><span class="sm-result-extra-value" id="out_{_html.escape(k)}">-</span>'
                f'<span class="sm-result-extra-unit">{_html.escape(kunit or "원")}</span></span>'
                f'</div>\n'
            )
        extra_rows_html += '    </div>'
    else:
        extra_rows_html = ""
    category = calc.get("category", "") or "계산기"
    emoji = ("💰" if ("급여" in category or "노무" in category)
             else "🏢" if ("보험" in category or "고용" in category) else "🧮")
    short = name.replace(" 계산기", "").replace("계산기", "").strip() or name
    repl = {
        "TITLE": _html.escape(title), "DESCRIPTION": _html.escape(desc),
        "CATEGORY": f"{emoji} {_html.escape(category)}", "NAME": _html.escape(name),
        "TOP_NAV": render_top_nav(cfg),
        "HERO_SUB": _html.escape(desc), "FORM_FIELDS": _form_fields_v2(ins, labels),
        "CALC_BTN": _html.escape(f"{short} 계산하기"),
        "RESULT_LABEL": _html.escape(plabel if plabel.startswith("예상") else f"예상 {plabel}"),
        "PRIMARY_OUT": _html.escape(primary), "RESULT_UNIT": _html.escape(punit or "원"),
        "EXTRA_OUTPUT_ROWS": extra_rows_html,
        # STEP 16-Y/17-D: _NOTICE_BY_SLUG에 등록된 계산기만 전용 문구 사용, 나머지는
        # 기존 공용 기본값 그대로(다른 계산기에는 전혀 영향 없음).
        "NOTICE": _NOTICE_BY_SLUG.get(
            calc.get("slug"),
            "본 계산 결과는 참고용이며, 실제 지급액은 근로계약·관련 법령에 따라 달라질 수 있습니다.",
        ),
        # 섹션은 render_* 함수가 조립(show_*=False면 태그 포함 전체 생략)
        "ADSENSE_SLOT": render_adsense_slot(cfg),
        "ARTICLE_SECTION": render_article(calc, cfg),
        "CPA_SLOT": render_cpa_slot(cfg),
        "FAQ_SECTION": render_faq(calc, cfg),
        "RELATED_SECTION": render_related(calc, cfg),
        # Phase C 추가 섹션
        "RESULT_CTA": render_result_cta(calc, cfg),
        "INLINE_CTA": render_inline_cta(calc, cfg),
        "RELATED_POSTS_SECTION": render_related_posts(calc, cfg),
        "FOOTER_CTA": render_footer_cta(calc, cfg),
        "SITE_FOOTER": render_site_footer(calc, cfg),
        # Phase E 추가
        "GA4_SCRIPT": _render_ga4_script(cfg),
        "CANONICAL": render_canonical(calc, cfg),
        "JSON_LD": render_json_ld(calc, cfg),
        "ADSENSE_SLOT_2": render_adsense_slot_2(cfg),
        "SM_CONFIG": json.dumps(_sm_config(calc, cfg), ensure_ascii=False),
    }
    if _TPL_V2.exists():
        html = _TPL_V2.read_text(encoding="utf-8")
        for k, v in repl.items():
            html = html.replace("{{" + k + "}}", v)
        return html
    # 폴백(v2 템플릿 없을 때) — 최소 구조
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_html.escape(title)}</title><link rel="stylesheet" href="style.css"></head><body>'
            f'<div class="sm-wrap"><h1>{_html.escape(name)}</h1></div>'
            f'<script>window.SM_CONFIG={repl["SM_CONFIG"]};</script>'
            f'<script src="script.js"></script></body></html>')


def _generate_tier2b(calc: dict, cfg: dict = None) -> dict:
    """Tier2-B 계산기(예: military-discharge-date) 전용 경로.
    표준 폼/수식 기반 생성기를 타지 않고, App Factory가 저장해 둔
    app_templates.html_template을 그대로 사용한다(scripts/_rebuild_site.py의
    기존 Tier2-B 분기와 동일한 방식 — 새 로직 아님, 재사용)."""
    tpl_id = calc.get("template_id")
    html = ""
    if tpl_id:
        try:
            from adapters.db.factory import get_db_adapter
            from repositories.template_repository import TemplateRepository
            tpl = TemplateRepository(get_db_adapter(cfg or {})).get_by_id(tpl_id)
            html = (tpl or {}).get("html_template") or ""
        except Exception as e:
            _log.warning("Tier2-B 템플릿 로드 실패(slug=%s): %s", calc.get("slug", ""), e)
    return {
        "index.html": html, "style.css": "", "script.js": "",
        "_formula_valid": bool(html),
        "_formula_msg": ("Tier2-B — DB 템플릿 직접 사용(재생성 아님)" if html
                         else "Tier2-B 템플릿 로드 실패 — template_id 확인 필요"),
    }


def generate_calculator(calc: dict, cfg: dict = None) -> dict:
    """index.html / style.css / script.js 3파일 dict 반환(+수식 검증). cfg 선택(Form Engine용).
    registry v3의 tier_subtype == "B"(Tier2-B)면 표준 생성기를 건너뛰고
    _generate_tier2b()로 위임 — 표준 계산기 경로는 이 분기와 완전히 무관하게 그대로 동작."""
    from .registry_loader import load_registry_v3
    _slug = str(calc.get("slug", ""))
    if (load_registry_v3().get(_slug) or {}).get("tier_subtype") == "B":
        return _generate_tier2b(calc, cfg)

    ins = _pj(calc.get("input_schema"), {})
    formula = _pj(calc.get("formula"), calc.get("formula", ""))
    if _validation_mode(calc) == "skip":
        # 날짜기반: _compute_js가 start_date/end_date로 계산(formula 필드 미사용) →
        # 옛 formula의 total_days 등 미존재 변수 참조로 뜨는 불필요 경고 제외(DB formula는 무변경)
        # 분기조건은 registry(validation_mode) 유일 소스(Phase D: 슬러그 하드코딩 폴백 제거됨)
        ok, msg = True, "날짜기반 계산(코드 내장) — 수식 검증 제외"
    else:
        ok, msg = validate_formula(formula, ins) if formula else (True, "수식 없음")
    return {
        "index.html": generate_html(calc, cfg),
        "style.css": generate_css(calc),
        "script.js": generate_js(calc, cfg),
        "_formula_valid": ok,
        "_formula_msg": msg,
    }


def render_inline_calculator(files: dict) -> str:
    """generate_calculator()의 {index.html, style.css, script.js}를 문서 골격 없는
    자체완결 조각으로 변환. 대시보드 미리보기와 WordPress 삽입이 공유하는 단일 함수.

    - <link rel=stylesheet href=style.css> → 인라인 <style>{css}</style>
    - <script src=script.js> → 인라인 <script>{js}</script>
    - <html>/<head>/<body> 골격 제거, <body> 내부(=sm-wrap 조각 + SM_CONFIG + 스크립트)만 반환.
    """
    html = files.get("index.html", "") or ""
    css = files.get("style.css", "") or ""
    js = files.get("script.js", "") or ""
    # 외부 참조 인라인화(css는 골격 제거 후 <style>로 prepend, js는 그 자리 치환)
    html = html.replace('<link rel="stylesheet" href="style.css">', "")
    html = html.replace('<script src="script.js"></script>', f"<script>{js}</script>")
    # 문서 골격 제거: <body>...</body> 내부만 취함
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    inner = m.group(1).strip() if m else html
    return f"<style>{css}</style>\n{inner}"
