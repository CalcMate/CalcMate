# -*- coding: utf-8 -*-
"""
modules/calculator_template_engine.py — 계산기 HTML 생성 엔진 (v12.0)

calculators.input_schema / output_schema (dict 또는 JSON 문자열)을 받아
자가완결 HTML 계산기(폼+결과영역+JS)를 생성한다. AI 미사용(결정적).

formula_js 가 주어지면 계산 로직으로 사용, 없으면 입력값 합계를 임시 표시.
"""
import json
import html as _html

_LABELS = {
    "salary": "월급(원)", "months": "근속개월수", "years": "근속연수",
    "hourly_wage": "시급(원)", "weekly_hours": "주당 근로시간",
    "height_cm": "키(cm)", "weight_kg": "몸무게(kg)",
    "amount": "금액(원)", "rate": "비율(%)", "days": "일수",
}


def _to_dict(schema):
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, str) and schema.strip():
        try:
            return json.loads(schema)
        except Exception:
            return {}
    return {}


def _label(key: str) -> str:
    return _LABELS.get(key, key.replace("_", " "))


def _input_type(spec) -> str:
    s = str(spec).lower()
    if "number" in s or "int" in s or "float" in s:
        return "number"
    if "date" in s:
        return "date"
    return "text"


def build_calculator_html(name: str, input_schema, output_schema,
                          formula_js: str = "", el_id: str = "salarymate_calc") -> str:
    """스키마 기반 계산기 HTML(인라인 CSS/JS) 반환."""
    ins = _to_dict(input_schema)
    outs = _to_dict(output_schema)
    name_e = _html.escape(name or "계산기")

    input_rows = []
    for k, spec in ins.items():
        t = _input_type(spec)
        input_rows.append(
            f'<div class="sm-row"><label for="{el_id}_{k}">{_html.escape(_label(k))}</label>'
            f'<input type="{t}" id="{el_id}_{k}" data-key="{k}" placeholder="0"></div>'
        )
    output_rows = []
    for k in outs:
        output_rows.append(
            f'<div class="sm-out-row"><span>{_html.escape(_label(k))}</span>'
            f'<strong id="{el_id}_out_{k}" data-key="{k}">-</strong></div>'
        )

    in_keys = list(ins.keys())
    out_keys = list(outs.keys())
    # 기본 계산 로직: formula_js 없으면 입력 합계를 첫 출력에 표시(임시)
    default_js = (
        "const v={};IN.forEach(k=>{v[k]=parseFloat(document.getElementById(EID+'_'+k).value)||0;});"
        "let sum=Object.values(v).reduce((a,b)=>a+b,0);"
        "OUT.forEach((k,i)=>{document.getElementById(EID+'_out_'+k).textContent="
        "(i===0?Math.round(sum).toLocaleString():'-');});"
    )
    calc_js = formula_js.strip() or default_js

    return f"""<div class="salarymate-calc" id="{el_id}">
  <style>
    #{el_id}{{max-width:480px;margin:16px auto;padding:20px;border:1px solid #e3e8ef;border-radius:12px;font-family:system-ui,'Malgun Gothic',sans-serif;background:#fff}}
    #{el_id} h3{{margin:0 0 12px;font-size:18px}}
    #{el_id} .sm-row{{display:flex;justify-content:space-between;align-items:center;margin:8px 0}}
    #{el_id} .sm-row label{{font-size:14px;color:#374151}}
    #{el_id} .sm-row input{{width:55%;padding:8px;border:1px solid #cbd5e1;border-radius:8px}}
    #{el_id} button{{width:100%;margin-top:14px;padding:11px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-size:15px;cursor:pointer}}
    #{el_id} .sm-result{{margin-top:14px;padding:12px;background:#f1f5f9;border-radius:8px}}
    #{el_id} .sm-out-row{{display:flex;justify-content:space-between;padding:4px 0}}
    #{el_id} .sm-out-row strong{{color:#2563eb}}
  </style>
  <h3>🧮 {name_e}</h3>
  {''.join(input_rows) or '<p>입력 항목이 없습니다.</p>'}
  <button type="button" onclick="{el_id}_calc()">계산하기</button>
  <div class="sm-result">{''.join(output_rows) or '<div class="sm-out-row"><span>결과</span><strong>-</strong></div>'}</div>
  <script>
    function {el_id}_calc(){{
      const EID="{el_id}";const IN={json.dumps(in_keys, ensure_ascii=False)};const OUT={json.dumps(out_keys, ensure_ascii=False)};
      try{{ {calc_js} }}catch(e){{console.error(e);}}
    }}
  </script>
</div>"""
