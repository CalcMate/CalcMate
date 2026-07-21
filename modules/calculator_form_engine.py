# -*- coding: utf-8 -*-
"""
modules/calculator_form_engine.py — 계산기 입력폼 엔진 (SalaryMate)

계산기 이름을 분석해 입력폼 스키마를 자동 생성하고 HTML로 렌더.
지원 타입: text/number/currency/date/select/radio/checkbox
골드 템플릿(templates/library/*.json)이 매칭되면 그 fields를 우선 사용.
"""
import html as _html
import json
import re
from pathlib import Path

from .ai_provider import build_provider_for_role
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()
LIB = Path(__file__).resolve().parent.parent / "templates" / "library"
TYPES = ["text", "number", "currency", "date", "select", "radio", "checkbox"]

# 이름 키워드 → 라이브러리 파일 매칭
_LIB_HINT = {
    "퇴직": "retirement", "연차": "annual_leave", "주휴": "weekly_allowance",
    "실업": "unemployment", "4대보험": "insurance", "보험": "insurance",
    "육아휴직": "parental_leave",
}


def _from_library(name: str):
    for kw, key in _LIB_HINT.items():
        if kw in name:
            f = LIB / f"{key}.json"
            if f.exists():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    return None
    return None


def get_library_template(name: str):
    """이름에 매칭되는 골드 템플릿(dict) 또는 None."""
    return _from_library(name)


def _slug(label: str, i: int) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", label.encode("ascii", "ignore").decode()).strip("_").lower()
    return s or f"field_{i}"


def generate_form_schema(cfg: dict, name: str) -> dict:
    """계산기 이름 → 입력폼 스키마 {fields:[{type,label,name}]}.
    골드 템플릿 우선, 없으면 AI(MODEL_WRITER) 추론, 실패 시 기본 폼."""
    lib = _from_library(name)
    if lib and lib.get("fields"):
        fields = []
        for i, f in enumerate(lib["fields"]):
            fields.append({"type": f.get("type", "number"),
                           "label": f.get("label", ""),
                           "name": f.get("name") or _slug(f.get("label", ""), i)})
        return {"fields": fields, "_source": "library"}

    system = ("너는 웹폼 설계자다. 주어진 계산기에 필요한 입력 필드를 설계하라. "
              f"type은 {TYPES} 중 하나. 순수 JSON만 반환: "
              '{"fields":[{"type":"","label":"","name":""}]}')
    try:
        provider, model = build_provider_for_role("writing", cfg)
        text, tokens = provider.chat(system, f"계산기명: {name}", model, max_tokens=500)
        try: BudgetTracker(cfg).record(model, tokens)
        except Exception: pass
        d = parse_json_lenient(text)
        fields = []
        for i, f in enumerate(d.get("fields", [])):
            t = f.get("type", "number")
            fields.append({"type": t if t in TYPES else "text",
                           "label": f.get("label", f"입력 {i+1}"),
                           "name": f.get("name") or _slug(f.get("label", ""), i)})
        if fields:
            return {"fields": fields, "_source": "ai"}
        raise ValueError("빈 폼")
    except Exception as e:
        LOG.warning("폼 스키마 AI 생성 실패(%s)→기본: %s", name, e)
        return {"fields": [{"type": "number", "label": "값1", "name": "value1"},
                           {"type": "number", "label": "값2", "name": "value2"}],
                "_source": "default"}


def build_form_html(schema: dict, el_prefix: str = "in") -> str:
    """스키마 → 입력폼 HTML(라벨+입력). 타입별 위젯."""
    fields = (schema or {}).get("fields", [])
    rows = []
    for f in fields:
        t = f.get("type", "text"); label = _html.escape(f.get("label", "")); nm = f.get("name", "")
        fid = f"{el_prefix}_{nm}"
        if t in ("number", "currency"):
            inp = f'<input type="number" id="{fid}" data-key="{nm}" placeholder="0">'
        elif t == "date":
            inp = f'<input type="date" id="{fid}" data-key="{nm}">'
        elif t == "select":
            opts = "".join(f'<option value="{o}">{o}</option>' for o in f.get("options", ["선택1", "선택2"]))
            inp = f'<select id="{fid}" data-key="{nm}">{opts}</select>'
        elif t == "radio":
            inp = "".join(
                f'<label class="sm-rdo"><input type="radio" name="{fid}" value="{o}" data-key="{nm}">{o}</label>'
                for o in f.get("options", ["예", "아니오"]))
        elif t == "checkbox":
            inp = f'<input type="checkbox" id="{fid}" data-key="{nm}">'
        else:
            inp = f'<input type="text" id="{fid}" data-key="{nm}">'
        suffix = ' <span class="sm-unit">원</span>' if t == "currency" else ""
        rows.append(f'<div class="sm-row"><label for="{fid}">{label}</label>'
                    f'<span class="sm-inp">{inp}{suffix}</span></div>')
    return "".join(rows) or "<p>입력 항목이 없습니다.</p>"
