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


def _formula_map(formula, output_schema) -> dict:
    if isinstance(formula, dict):
        return formula
    keys = list((output_schema or {}).keys())
    return {(keys[0] if keys else "result"): formula}


def _effective_form(calc: dict, cfg: dict = None):
    """(form_schema, [field_names]) 반환. input_schema 우선, 없으면 Form Engine."""
    ins = _pj(calc.get("input_schema"), {})
    if ins:
        fields = [{"type": "number", "label": _label(k), "name": k} for k in ins]
        return {"fields": fields}, list(ins.keys())
    try:
        from .calculator_form_engine import generate_form_schema
        sch = generate_form_schema(cfg or {}, calc.get("name", ""))
    except Exception:
        sch = {"fields": [{"type": "number", "label": "값1", "name": "value1"}]}
    return sch, [f.get("name") for f in sch.get("fields", [])]


# ── JS ────────────────────────────────────────────────────────────
def generate_js(calc: dict, cfg: dict = None) -> str:
    _, names = _effective_form(calc, cfg)
    outs = _pj(calc.get("output_schema"), {})
    formula = _pj(calc.get("formula"), calc.get("formula", ""))
    fmap = _formula_map(formula, outs)
    read_lines = [f'  const {n} = parseFloat((document.getElementById("in_{n}")||{{}}).value) || 0;'
                  for n in names]
    calc_lines, set_lines = [], []
    for out_key, expr in fmap.items():
        calc_lines.append(f'  const out_{out_key} = ({_to_js(expr)});')
        set_lines.append(
            f'  var el_{out_key}=document.getElementById("out_{out_key}");'
            f' if(el_{out_key}) el_{out_key}.textContent = isFinite(out_{out_key}) '
            f'? Math.round(out_{out_key}).toLocaleString() : "-";')
    return ("function calculate() {\n" + "\n".join(read_lines) +
            "\n  try {\n" + "\n".join("  " + c for c in calc_lines) + "\n" +
            "\n".join("  " + s for s in set_lines) +
            '\n  } catch (e) { console.error(e); }\n}\n')


# ── CSS (공개 계산기용 라이트 테마) ───────────────────────────────
def generate_css(calc: dict = None) -> str:
    return """*{box-sizing:border-box}body{font-family:system-ui,'Malgun Gothic',sans-serif;background:#f6f8fb;margin:0;padding:0;color:#1f2937}
.sm-wrap{max-width:680px;margin:0 auto;padding:20px 16px 90px}
.sm-hero{padding:22px 4px 8px}.sm-hero h1{font-size:26px;margin:0 0 6px;letter-spacing:-.5px}
.sm-sub{color:#6b7280;font-size:14px;margin:0}
.sm-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:20px;margin:14px 0;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.sm-card h2{font-size:17px;margin:0 0 12px}
.sm-row{display:flex;justify-content:space-between;align-items:center;margin:10px 0;gap:10px}
.sm-row label{font-size:14px;color:#374151}.sm-inp{display:flex;align-items:center;gap:6px}
.sm-row input,.sm-row select{width:180px;max-width:55vw;padding:9px;border:1px solid #cbd5e1;border-radius:9px}
.sm-unit{color:#9ca3af;font-size:13px}.sm-rdo{margin-right:10px;font-size:14px}
.sm-btn{width:100%;margin-top:14px;padding:13px;border:0;border-radius:11px;background:#2563eb;color:#fff;font-size:16px;cursor:pointer}
.sm-btn:hover{background:#1d4ed8}
.sm-result .r,.r{display:flex;justify-content:space-between;padding:7px 0;font-size:16px;border-bottom:1px dashed #eef2f7}
.sm-result strong{color:#2563eb}
.sm-faq details{margin:8px 0;background:#f9fafb;border-radius:10px;padding:10px 12px}
.sm-faq summary{cursor:pointer;font-weight:600}
.sm-related a{display:inline-block;margin:4px 8px 4px 0;color:#2563eb}
.sm-ad{background:#fffbe6;border:1px dashed #facc15;border-radius:10px;padding:14px;text-align:center;color:#92660a}
.sm-foot{color:#9ca3af;font-size:12px;text-align:center;margin-top:18px}
.sm-mobile-cta{position:fixed;left:0;right:0;bottom:0;padding:10px 16px;background:rgba(255,255,255,.96);border-top:1px solid #e5e7eb}
.sm-mobile-cta button{width:100%;padding:13px;border:0;border-radius:11px;background:#16a34a;color:#fff;font-size:16px}
@media(min-width:700px){.sm-mobile-cta{display:none}}
"""


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


# ── HTML (v1 템플릿 치환, 없으면 인라인 폴백) ─────────────────────
def generate_html(calc: dict, cfg: dict = None) -> str:
    name = _html.escape(calc.get("name", "계산기"))
    title = _html.escape(calc.get("seo_title") or name)
    desc = _html.escape(calc.get("seo_description") or calc.get("seo_desc") or f"{name} 자동 계산")
    repl = {
        "TITLE": title, "DESCRIPTION": desc,
        "FORM_HTML": _form_html(calc, cfg), "RESULT_HTML": _result_html(calc),
        "EXPLANATION_HTML": _explanation_html(calc), "FAQ_HTML": _faq_html(calc),
        "RELATED_HTML": _related_html(calc),
    }
    if _TPL.exists():
        html = _TPL.read_text(encoding="utf-8")
        for k, v in repl.items():
            html = html.replace("{{" + k + "}}", v)
        return html
    # 폴백(템플릿 없을 때) — 최소 구조
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><link rel="stylesheet" href="style.css"></head><body>'
            f'<div class="sm-wrap"><div class="sm-hero"><h1>{name}</h1><p class="sm-sub">{desc}</p></div>'
            f'<section class="sm-card sm-form">{repl["FORM_HTML"]}'
            f'<button class="sm-btn" onclick="calculate()">계산하기</button></section>'
            f'<section class="sm-card sm-result">{repl["RESULT_HTML"]}</section>'
            f'<section class="sm-card sm-faq">{repl["FAQ_HTML"]}</section></div>'
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
