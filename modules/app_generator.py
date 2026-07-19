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


def _label(k, labels=None):
    # 계산기별 labels(예: {"monthly_salary":"월급"}) 우선, 없으면 기존 _LABELS fallback
    if labels and k in labels and str(labels[k]).strip():
        return str(labels[k])
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
    """_LABELS의 '시급(원)' → ('시급','원'). 괄호 없으면 (label,''). labels(계산기별) 우선."""
    lab = _label(k, labels)
    m = re.match(r"^(.*)\((.+)\)\s*$", lab)
    return (m.group(1).strip(), m.group(2).strip()) if m else (lab, "")


def _form_fields_v2(ins, labels=None) -> str:
    rows = []
    for k, spec in ins.items():
        label, unit = _split_label(k, labels)
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
    return "\n".join(items[:4])


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
    labels = _pj(calc.get("labels"), {})
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
        "name": calc.get("name", "계산기"), "primaryOutput": primary,
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
            'window.computeResult = function(inputs){\n'
            '  var avg_daily_wage = inputs["avg_daily_wage"] || 0;\n'
            '  var age = inputs["age"] || 0;\n'
            '  var employment_months = inputs["employment_months"] || 0;\n'
            '  if (avg_daily_wage <= 0 || age <= 0 || employment_months <= 0) { return null; }\n'
            '  var out = {};\n'
            '  out.notices = [];\n'
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
    if _compute_type(calc) == "date_based":   # 날짜 기반(입사일/퇴사일 → total_days)
        return (
            'window.computeResult = function(inputs){\n'
            '  var s = new Date(inputs["start_date"]); var e = new Date(inputs["end_date"]);\n'
            # SP-3: 날짜 미입력/Invalid Date → null (입력 오류)
            '  if (isNaN(s.getTime()) || isNaN(e.getTime())) { return null; }\n'
            '  var total_days = Math.floor((e - s) / (1000*60*60*24));\n'
            '  var avg_monthly_wage = inputs["avg_monthly_wage"] || 0;\n'
            # SP-4: 평균임금 0 이하 → null (입력 오류)
            '  if (avg_monthly_wage <= 0) { return null; }\n'
            '  var out = {};\n'
            '  out.notices = [];\n'
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
        primary_label = _label(out_key)
        in_keys = list(ins.keys())
        formula_str = (f"{in_keys[0]}.toLocaleString() + '원 × (' "
                       f"+ {in_keys[1]} + '÷40×8) = ' "
                       f"+ Math.round({out_expr}).toLocaleString() + '원'"
                       if len(in_keys) == 2 else '""')
        body = (
            "  var out = {};\n"
            "  out.notices = [];\n"
            + validation
            + f'  out["{out_key}"] = ({out_expr});\n'
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


# ── 섹션 렌더 함수(show_*=False면 감싸는 태그 포함 전체 생략) ────────
# 원칙: HTML 생성 경로는 generate_html() 하나. 이 함수들은 조각만 반환하고
# generate_html이 플레이스홀더에 조립. show=True 산출물은 기존 템플릿과 byte 동일.
def render_adsense_slot(cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_adsense"]:
        return ""
    return ('  <!-- [광고 슬롯 — 기본 숨김, 대시보드 show_adsense로만 노출] -->\n'
            '  <div class="sm-adsense"><!-- 애드센스 승인 후 활성화 --></div>')


def render_article(calc: dict, cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_article"]:
        return ""
    name = calc.get("name", "계산기")
    desc = calc.get("seo_description") or calc.get("seo_desc") or f"{name} 자동 계산"
    article = str(calc.get("article_content", "") or "") \
        or f"<h2>{_html.escape(name)}</h2><p>{_html.escape(desc)}</p>"
    return ('  <!-- ⑧ 본문 -->\n'
            '  <section class="sm-card sm-article">\n'
            f'    {article}\n'
            '  </section>')


def render_cpa_slot(cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_cpa"]:
        return ""
    return ('  <!-- [CPA 슬롯 — 기본 숨김, 대시보드 show_cpa로만 노출] -->\n'
            '  <div class="sm-cpa"><!-- 수익화 단계 2 이후 활성화 --></div>')


def render_faq(calc: dict, cfg: dict = None) -> str:
    if not _show_flags(cfg)["show_faq"]:
        return ""
    return ('  <!-- ⑨ FAQ -->\n'
            '  <section class="sm-card" id="faq-card">\n'
            '    <h2 class="sm-card-title">자주 묻는 질문</h2>\n'
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
    labels = _pj(calc.get("labels"), {})
    primary = list(outs.keys())[0] if outs else "result"
    plabel, punit = _split_label(primary, labels)
    category = calc.get("category", "") or "계산기"
    emoji = ("💰" if ("급여" in category or "노무" in category)
             else "🏢" if ("보험" in category or "고용" in category) else "🧮")
    short = name.replace(" 계산기", "").replace("계산기", "").strip() or name
    repl = {
        "TITLE": _html.escape(title), "DESCRIPTION": _html.escape(desc),
        "CATEGORY": f"{emoji} {_html.escape(category)}", "NAME": _html.escape(name),
        "HERO_SUB": _html.escape(desc), "FORM_FIELDS": _form_fields_v2(ins, labels),
        "CALC_BTN": _html.escape(f"{short} 계산하기"),
        "RESULT_LABEL": _html.escape(plabel if plabel.startswith("예상") else f"예상 {plabel}"),
        "PRIMARY_OUT": _html.escape(primary), "RESULT_UNIT": _html.escape(punit or "원"),
        "NOTICE": "본 계산 결과는 참고용이며, 실제 지급액은 근로계약·관련 법령에 따라 달라질 수 있습니다.",
        # 섹션은 render_* 함수가 조립(show_*=False면 태그 포함 전체 생략)
        "ADSENSE_SLOT": render_adsense_slot(cfg),
        "ARTICLE_SECTION": render_article(calc, cfg),
        "CPA_SLOT": render_cpa_slot(cfg),
        "FAQ_SECTION": render_faq(calc, cfg),
        "RELATED_SECTION": render_related(calc, cfg),
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
