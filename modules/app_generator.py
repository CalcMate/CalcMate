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
import re
from datetime import datetime
from pathlib import Path

from .formula_engine import validate_formula

_TPL = Path(__file__).resolve().parent.parent / "templates" / "calculators" / "calculator_v1.html"

_LABELS = {
    "monthly_salary": "월급(원)", "salary": "급여(원)", "years": "근속연수",
    "months": "근속개월수", "hourly_wage": "시급(원)", "weekly_hours": "주당 근로시간",
    "daily_wage": "일급(원)", "unused_days": "미사용 연차(일)",
    "avg_monthly_wage": "평균 월임금(원)", "avg_daily_wage": "평균 일임금(원)",
    "age": "나이", "employment_months": "고용 개월수", "amount": "금액(원)",
    "national_pension": "국민연금", "health_insurance": "건강보험",
    "employment_insurance": "고용보험", "total": "합계", "severance_pay": "퇴직금",
    "weekly_allowance": "주휴수당", "annual_leave_allowance": "연차수당",
    "daily_benefit": "1일 구직급여", "total_benefit": "예상 총액",
}
_JS_FUNCS = {"min": "Math.min", "max": "Math.max", "round": "Math.round",
             "abs": "Math.abs", "int": "Math.trunc", "float": "Number"}


def _pj(v, default):
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v) if v else default
    except Exception:
        return default


def _label(k):
    return _LABELS.get(k, str(k).replace("_", " "))


def _to_js(expr: str) -> str:
    s = str(expr)
    for fn, jsfn in _JS_FUNCS.items():
        s = re.sub(rf"\b{fn}\s*\(", f"{jsfn}(", s)
    return s


# ── Design System v2 (마스터 시안 + assets) ──────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_TPL_V2 = _BASE_DIR / "templates" / "calculators" / "calculator_v2.html"
_ASSETS = _BASE_DIR / "templates" / "calculators" / "assets"
# components.js는 init을 실행하므로 마지막(다른 모듈 정의 후)
_JS_ORDER = ["number_input.js", "result_save.js", "share.js", "pwa.js",
             "faq.js", "related.js", "components.js"]
_RELATED = [("weekly-holiday-allowance", "💰", "주휴수당 계산기"),
            ("severance-pay", "💼", "퇴직금 계산기"),
            ("annual-leave-allowance", "📅", "연차수당 계산기"),
            ("unemployment-benefit", "📋", "실업급여 계산기"),
            ("four-insurances", "🏢", "4대보험 계산기")]


def _split_label(k):
    """_LABELS의 '시급(원)' → ('시급','원'). 괄호 없으면 (label,'')."""
    lab = _label(k)
    m = re.match(r"^(.*)\((.+)\)\s*$", lab)
    return (m.group(1).strip(), m.group(2).strip()) if m else (lab, "")


def _form_fields_v2(ins) -> str:
    rows = []
    for k, spec in ins.items():
        label, unit = _split_label(k)
        if "date" in str(spec).lower():
            rows.append(
                f'<div class="sm-field"><label class="sm-label" for="in_{k}">{_html.escape(label)}</label>'
                f'<div class="sm-input-wrap"><input class="sm-input" type="date" id="in_{k}"></div></div>')
        else:
            u = f'<span class="sm-unit">{_html.escape(unit)}</span>' if unit else ""
            rows.append(
                f'<div class="sm-field"><label class="sm-label" for="in_{k}">{_html.escape(label)}</label>'
                f'<div class="sm-input-wrap"><input class="sm-input" type="text" inputmode="numeric" '
                f'data-comma id="in_{k}" placeholder="0">{u}</div></div>')
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


def _related_items_v2(calc) -> str:
    cur = str(calc.get("slug", ""))
    items = [f'<a class="sm-related-item" href="#"><span class="sm-related-emoji">{emoji}</span>'
             f'<span class="sm-related-name">{_html.escape(nm)}</span></a>'
             for slug, emoji, nm in _RELATED if slug != cur]
    return "\n".join(items[:4])


def _sm_config(calc, cfg) -> dict:
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    inputs = []
    for k, spec in ins.items():
        label, unit = _split_label(k)
        inputs.append({"name": k, "label": label,
                       "type": ("date" if "date" in str(spec).lower() else "number"), "unit": unit})
    outputs = [{"key": k, "label": _split_label(k)[0], "unit": _split_label(k)[1] or "원"} for k in outs]
    primary = list(outs.keys())[0] if outs else "result"
    c = cfg if isinstance(cfg, dict) else {}
    def b(key, default):
        return bool(c.get(key, default))
    # SITE_MODE로 광고/CPA 파생(설정값만으로 제어). SHOW_ADSENSE/SHOW_CPA 명시 시 그 값 우선.
    site_mode = str(c.get("SITE_MODE", "pre_adsense"))
    mode_ads = site_mode in ("adsense", "full")
    mode_cpa = site_mode in ("cpa", "full")
    return {
        # 기능(계산/렌더용)
        "name": calc.get("name", "계산기"), "primaryOutput": primary,
        "resultUnit": (outputs[0]["unit"] if outputs else "원"),
        "inputs": inputs, "outputs": outputs,
        # 노출 플래그(flat, 대시보드 설정 연동)
        "show_adsense": b("SHOW_ADSENSE", mode_ads),
        "show_cpa": b("SHOW_CPA", mode_cpa),
        "show_share": b("SHOW_SHARE", True),
        "show_pwa": b("SHOW_PWA", True),
        "show_result_save": b("SHOW_RESULT_SAVE", True),
        "show_faq": b("SHOW_FAQ", True),
        "show_notice": b("SHOW_NOTICE", True),
        "show_related": b("SHOW_RELATED", True),
        "show_detail": b("SHOW_DETAIL", True),
        # 정책/메타
        "site_mode": site_mode,
        "result_export_type": str(c.get("RESULT_EXPORT_TYPE", "png")),
        "kakao_js_key": str(c.get("KAKAO_JS_KEY", "")),
        "calculator_version": str(c.get("CALCULATOR_VERSION", "2.0.0")),
        "law_version": str(c.get("LAW_VERSION", "2026-07")),
    }


def _read_assets_js() -> str:
    parts = []
    for f in _JS_ORDER:
        p = _ASSETS / f
        parts.append(p.read_text(encoding="utf-8") if p.exists() else "")
    return "\n".join(parts)


def _compute_js(calc) -> str:
    """계산기별 computeResult(inputs) 생성. 기존 formula/퇴직금 date분기 로직 유지."""
    slug = str(calc.get("slug", ""))
    if slug == "severance-pay":   # 날짜 기반(입사일/퇴사일 → total_days) — 로직 무변경
        return (
            'window.computeResult = function(inputs){\n'
            '  var s = new Date(inputs["start_date"]); var e = new Date(inputs["end_date"]);\n'
            '  var total_days = Math.floor((e - s) / (1000*60*60*24));\n'
            '  var avg_monthly_wage = inputs["avg_monthly_wage"] || 0;\n'
            '  var out = {};\n'
            '  out["severance_pay"] = (total_days > 0) ? avg_monthly_wage * (total_days / 365) : 0;\n'
            '  out._detail = [{label:"재직일수", value:(total_days > 0 ? total_days : 0) + "일"}];\n'
            '  return out;\n};\n'
        )
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    formula = _pj(calc.get("formula"), calc.get("formula", ""))
    fmap = _formula_map(formula, outs)
    reads = "".join(f'  var {n} = inputs["{n}"] || 0;\n' for n in ins.keys())
    body = "  var out = {};\n" + "".join(
        f'  out["{k}"] = ({_to_js(expr)});\n' for k, expr in fmap.items())
    return "window.computeResult = function(inputs){\n" + reads + body + "  return out;\n};\n"


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
    """script.js = 공통 컴포넌트 모듈 전체 + 계산기별 computeResult().
    calculate()/renderResult()는 공통(불변). 수식/퇴직금 date분기만 계산기별."""
    return _read_assets_js() + "\n\n" + _compute_js(calc)


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
                      '<a href="../">SalaryMate 계산기 모음 →</a></section>')
    if share:
        blocks.append('<section class="sm-card"><h2>공유</h2>'
                      '<a href="#" onclick="navigator.share&&navigator.share({title:document.title,url:location.href});return false">🔗 공유하기</a></section>')
    if report:
        blocks.append('<section class="sm-card"><h2>상세 리포트</h2>'
                      '<a href="#">📄 PDF 리포트 받기</a></section>')
    return "\n".join(blocks)


# ── HTML (design v2 마스터 시안 치환) ─────────────────────────────
def generate_html(calc: dict, cfg: dict = None) -> str:
    """index.html = calculator_v2.html 시안에 계산기 데이터만 치환. UI는 모든 계산기 동일."""
    name = calc.get("name", "계산기")
    title = calc.get("seo_title") or name
    desc = calc.get("seo_description") or calc.get("seo_desc") or f"{name} 자동 계산"
    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    primary = list(outs.keys())[0] if outs else "result"
    plabel, punit = _split_label(primary)
    category = calc.get("category", "") or "계산기"
    emoji = ("💰" if ("급여" in category or "노무" in category)
             else "🏢" if ("보험" in category or "고용" in category) else "🧮")
    short = name.replace(" 계산기", "").replace("계산기", "").strip() or name
    article = str(calc.get("article_content", "") or "") \
        or f"<h2>{_html.escape(name)}</h2><p>{_html.escape(desc)}</p>"
    repl = {
        "TITLE": _html.escape(title), "DESCRIPTION": _html.escape(desc),
        "CATEGORY": f"{emoji} {_html.escape(category)}", "NAME": _html.escape(name),
        "HERO_SUB": _html.escape(desc), "FORM_FIELDS": _form_fields_v2(ins),
        "CALC_BTN": _html.escape(f"{short} 계산하기"),
        "RESULT_LABEL": _html.escape(f"예상 {plabel}"),
        "PRIMARY_OUT": _html.escape(primary), "RESULT_UNIT": _html.escape(punit or "원"),
        "NOTICE": "본 계산 결과는 참고용이며, 실제 지급액은 근로계약·관련 법령에 따라 달라질 수 있습니다.",
        "ARTICLE_HTML": article,
        "FAQ_ITEMS": _faq_items_v2(calc), "RELATED_ITEMS": _related_items_v2(calc),
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


def generate_calculator(calc: dict, cfg: dict = None) -> dict:
    """index.html / style.css / script.js 3파일 dict 반환(+수식 검증). cfg 선택(Form Engine용)."""
    ins = _pj(calc.get("input_schema"), {})
    formula = _pj(calc.get("formula"), calc.get("formula", ""))
    ok, msg = validate_formula(formula, ins) if formula else (True, "수식 없음")
    return {
        "index.html": generate_html(calc, cfg),
        "style.css": generate_css(calc),
        "script.js": generate_js(calc, cfg),
        "_formula_valid": ok,
        "_formula_msg": msg,
    }
