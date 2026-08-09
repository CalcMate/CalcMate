# -*- coding: utf-8 -*-
"""
modules/review_center.py — Phase3-3 검토센터 핵심 로직

설계 기준: docs/PHASE3_3_DESIGN.md
- 체크리스트 자동 추출 (규칙 기반)
- Build 사전 QA 6단계
- slug 중복 차단
- Tier AI 추천
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# D-2: 법령 검토가 🔴 필수인 카테고리 목록
CRITICAL_CATEGORIES = frozenset({
    "세금/세법", "노동/고용법", "복지/사회보험", "병역/공무",
    "세금/정부혜택", "노무/급여", "고용/보험", "노무/급여/보험",
})

# D-4: Tier2-B 감지 키워드 (rule-based, AI 이전 단계)
TIER2B_KEYWORDS = ["날짜", "기간", "전역일", "만료일", "종료일", "d-day", "디데이", "복무", "개월수"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pj(v, default=None):
    """JSON 문자열/딕셔너리 안전 파싱. 순수 수식 문자열은 그대로 반환."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return default if default is not None else {}
        try:
            return json.loads(s)  # JSON dict/list인 경우
        except Exception:
            return v  # 수식 문자열 등은 그대로 반환
    return default if default is not None else {}


# ─────────────────────────────────────────────────────────────
# 1. 검토 체크리스트 자동 추출
# ─────────────────────────────────────────────────────────────

def extract_checklist(app: dict, tier: str = "Tier2-A", category: str = "") -> list[dict]:
    """
    계산기 데이터에서 검토 체크리스트 항목을 규칙 기반으로 추출.
    app: generate_app() 또는 DB 계산기 dict
    tier: "Tier2-A" | "Tier2-B" | "Tier1"
    category: 계산기 카테고리 문자열
    반환: list of ChecklistItem dict
    """
    items = []
    formula = _pj(app.get("formula"), "")
    legal_refs = app.get("legal_refs") or []
    compute_rules = _pj(app.get("compute_rules"), {})
    input_schema = _pj(app.get("input_schema"), {})

    is_date_based = (app.get("compute_type") == "date_based" or tier == "Tier2-B")

    # D-2: 카테고리 기반 법적 근거 등급 결정
    legal_severity = "critical" if (not category or category in CRITICAL_CATEGORIES) else "advisory"

    # ─ formula_accuracy: Tier2-A + formula 있는 경우
    if formula and not is_date_based:
        formula_str = (json.dumps(formula, ensure_ascii=False)
                       if isinstance(formula, dict) else str(formula))
        items.append({
            "id": "formula_accuracy",
            "severity": "critical",
            "label": "계산 공식 정확성",
            "display_value": formula_str[:400],
            "auto_source": "formula_field",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ legal_basis: 항상 추가 (등급은 카테고리로 결정)
    if not legal_refs:
        disp = "⚠️ legal_refs 미입력 — 근거 법령이 있으면 입력 필요"
        src = "legal_refs_empty"
    else:
        disp = str(legal_refs)
        src = "legal_refs_present"
    items.append({
        "id": "legal_basis",
        "severity": legal_severity,
        "label": "법적 근거 (법령/조항)",
        "display_value": disp,
        "auto_source": src,
        "checked": False, "checked_by": None, "checked_at": None,
    })

    # ─ rate_constant: formula에 소수점 상수 포함 시
    if formula and not is_date_based:
        constants = re.findall(r'\b\d+\.\d+\b', str(formula))
        if constants:
            items.append({
                "id": "rate_constant",
                "severity": "critical",
                "label": "적용 세율/계수 확인",
                "display_value": f"공식 내 상수: {constants}",
                "auto_source": "formula_constants",
                "checked": False, "checked_by": None, "checked_at": None,
            })

    # ─ base_year: 🔴 카테고리 계산기에만
    if legal_severity == "critical":
        items.append({
            "id": "base_year",
            "severity": "critical",
            "label": "기준 연도/시행일 확인",
            "display_value": "직접 확인 필요 — 법령 시행일 또는 세율 적용 연도",
            "auto_source": "critical_category",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ default_values: input_schema에 default 있는 경우
    defaults = {k: v.get("default") for k, v in input_schema.items()
                if isinstance(v, dict) and "default" in v}
    if defaults:
        items.append({
            "id": "default_values",
            "severity": "critical",
            "label": "기본 입력값 타당성",
            "display_value": str(defaults),
            "auto_source": "input_defaults",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ edge_cases: compute_rules 있는 경우
    if compute_rules:
        items.append({
            "id": "edge_cases",
            "severity": "critical",
            "label": "예외조건 처리 확인",
            "display_value": str(compute_rules)[:300],
            "auto_source": "compute_rules",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ 🟡 권장: SEO
    if app.get("seo_title"):
        items.append({
            "id": "seo_title",
            "severity": "advisory",
            "label": "SEO 제목 검토",
            "display_value": str(app["seo_title"]),
            "auto_source": "seo_title_field",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ 🟡 권장: FAQ
    faq_raw = app.get("faq") or app.get("faq_template")
    if faq_raw:
        faq = _pj(faq_raw, []) if isinstance(faq_raw, str) else faq_raw
        if isinstance(faq, list) and faq:
            faq_qs = [f.get("q", f.get("question", "")) for f in faq[:3]]
            items.append({
                "id": "faq_content",
                "severity": "advisory",
                "label": "FAQ 내용 검토",
                "display_value": str(faq_qs),
                "auto_source": "faq_field",
                "checked": False, "checked_by": None, "checked_at": None,
            })

    return items


def detect_tier2b_keywords(name: str, desc: str = "") -> bool:
    """이름/설명에서 Tier2-B 키워드 감지."""
    text = ((name or "") + " " + (desc or "")).lower()
    return any(kw in text for kw in TIER2B_KEYWORDS)


# ─────────────────────────────────────────────────────────────
# 2. Tier AI 추천
# ─────────────────────────────────────────────────────────────

def suggest_tier(cfg: dict, name: str, desc: str = "") -> dict:
    """
    AI(GPT-4o)가 계산기 이름/설명 기반으로 Tier 추천.
    반환: {"tier": str, "reason": str, "confidence": str}
    """
    from modules.app_factory import _chat
    from modules.json_utils import parse_json_lenient

    sys_prompt = (
        "너는 한국 웹 계산기 분류 전문가다.\n\n"
        "Tier2-A: 단순 산술/비율 공식으로 표현 가능. 날짜 계산 없음. 구간 요율 없음.\n"
        "         예: 원천징수(총액×3.3%), 전세 기회비용(금액×이율÷12)\n"
        "Tier2-B: 핵심 로직이 날짜 덧셈/기간 계산. 단순 산술로 표현 불가.\n"
        "         예: 복무 만료일, 육아휴직 종료일, D-Day 계산기\n"
        "Tier1:   날짜 계산, 구간별 누진 요율, 다단계 법령 분기 등 복잡한 로직.\n"
        "         예: 퇴직금(30일평균임금×근속연수), 실업급여(수급자격+구간급여)\n\n"
        'JSON만 반환: {"tier": "Tier2-A", "reason": "이유 1~2문장", "confidence": "high|medium|low"}'
    )
    user_prompt = f"계산기명: {name}\n설명: {desc or '(없음)'}"

    try:
        text, _, _ = _chat(cfg, "orchestrator", sys_prompt, user_prompt, 300)
        result = parse_json_lenient(text)
        tier = result.get("tier", "Tier2-A")
        if tier not in ("Tier2-A", "Tier2-B", "Tier1"):
            tier = "Tier2-A"
        return {
            "tier": tier,
            "reason": result.get("reason", ""),
            "confidence": result.get("confidence", "medium"),
        }
    except Exception as e:
        return {"tier": "Tier2-A", "reason": f"추천 실패: {e}", "confidence": "low"}


# ─────────────────────────────────────────────────────────────
# 3. slug 중복 차단
# ─────────────────────────────────────────────────────────────

def check_slug_conflict(slug: str, cfg: dict) -> tuple[str, bool, str]:
    """
    slug와 기존 Registry v3 + DB를 대조.
    반환: (slug, is_conflict, message)
    """
    from modules.registry_loader import load_registry_v3
    try:
        v3 = load_registry_v3(force=True)
        v3_slugs = set(v3.keys())
    except Exception:
        v3_slugs = set()

    try:
        from adapters.db.factory import get_db_adapter
        from repositories.calculator_repository import CalculatorRepository
        db_calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
        db_slugs = {c.get("slug", "") for c in db_calcs if c.get("slug")}
    except Exception:
        db_slugs = set()

    all_slugs = v3_slugs | db_slugs

    if slug and slug in all_slugs:
        return slug, True, f"'{slug}' 슬러그가 이미 존재합니다."
    return slug, False, ""


# ─────────────────────────────────────────────────────────────
# 4. Build 사전 QA 6단계 (D-4 반영)
# ─────────────────────────────────────────────────────────────

def pre_build_qa(calc: dict, cfg: dict) -> list[dict]:
    """
    Build 전 6단계 사전 검사.
    calc: DB 계산기 record (slug, formula, input_schema, output_schema 등)
    반환: [{"step": int, "label": str, "passed": bool, "skipped": bool, "detail": str}]
    """
    from modules.app_generator import generate_calculator

    results = []

    is_date_based = (str(calc.get("compute_type", "")) == "date_based" or
                     bool(calc.get("date_fields")))

    ins = _pj(calc.get("input_schema"), {})
    outs = _pj(calc.get("output_schema"), {})
    formula = _pj(calc.get("formula"), "")

    # ── Step 1: input_schema 존재 ──────────────────────────────
    passed1 = bool(ins)
    results.append({
        "step": 1, "label": "입력 스키마 존재",
        "passed": passed1, "skipped": False,
        "detail": (f"입력 항목 {len(ins)}개: {list(ins.keys())}"
                   if passed1 else "input_schema 없음 — generate_app() 재실행 필요"),
    })

    # ── Step 2: output_schema 존재 ────────────────────────────
    passed2 = bool(outs)
    results.append({
        "step": 2, "label": "출력 스키마 존재",
        "passed": passed2, "skipped": False,
        "detail": (f"출력 항목 {len(outs)}개: {list(outs.keys())}"
                   if passed2 else "output_schema 없음"),
    })

    if not (passed1 and passed2):
        for s, l in [(3, "HTML 출력 요소 1:1 대응"), (4, "JS 다중 출력 처리"),
                     (5, "복수 출력 완전성"), (6, "기본값 계산 실행")]:
            results.append({"step": s, "label": l, "passed": False, "skipped": True,
                            "detail": "Step 1/2 실패로 건너뜀"})
        return results

    # generate_calculator로 파일 생성 (Step 3~5에서 사용)
    try:
        files = generate_calculator(calc, cfg)
        html = files.get("index.html", "")
        js = files.get("script.js", "")
        gen_ok = True
    except Exception as e:
        gen_ok = False
        gen_err = str(e)
        html, js = "", ""

    if not gen_ok:
        for s, l in [(3, "HTML 출력 요소 1:1 대응"), (4, "JS 다중 출력 처리"),
                     (5, "복수 출력 완전성"), (6, "기본값 계산 실행")]:
            results.append({"step": s, "label": l, "passed": False, "skipped": False,
                            "detail": f"generate_calculator() 실패: {gen_err}"})
        return results

    # ── Step 3: output_schema ↔ HTML id="out_*" 1:1 대응 ─────
    if is_date_based:
        results.append({
            "step": 3, "label": "HTML 출력 요소 1:1 대응",
            "passed": True, "skipped": True,
            "detail": "날짜형 계산기 — HTML ID 직접 확인 필요 (D-4: 자동 검사 건너뜀)",
        })
    else:
        html_out_ids = set(re.findall(r'id="out_([^"]+)"', html))
        schema_keys = set(outs.keys())
        missing = schema_keys - html_out_ids
        extra = html_out_ids - schema_keys
        passed3 = not missing
        detail3 = (f"✅ {len(schema_keys)}개 출력 모두 HTML에 존재" if passed3 else
                   f"HTML에 없는 출력 ID: {missing}" +
                   (f" | HTML에만 있는 ID: {extra}" if extra else ""))
        results.append({"step": 3, "label": "HTML 출력 요소 1:1 대응",
                        "passed": passed3, "skipped": False, "detail": detail3})

    # ── Step 4: formula dict keys가 JS에서 처리되는지 ─────────
    if is_date_based:
        results.append({"step": 4, "label": "JS 다중 출력 처리",
                        "passed": True, "skipped": True,
                        "detail": "날짜형 계산기 — 자동 검사 건너뜀 (D-4)"})
    elif isinstance(formula, dict):
        js_out_keys = set(re.findall(r'out\["([^"]+)"\]', js))
        js_out_keys -= {"notices"}
        js_out_keys = {k for k in js_out_keys if not k.startswith("_")}
        missing_js = set(formula.keys()) - js_out_keys
        passed4 = not missing_js
        detail4 = (f"✅ formula dict {len(formula)}개 키 모두 JS에서 처리" if passed4 else
                   f"JS에서 누락된 출력 키: {missing_js}")
        results.append({"step": 4, "label": "JS 다중 출력 처리",
                        "passed": passed4, "skipped": False, "detail": detail4})
    else:
        results.append({"step": 4, "label": "JS 다중 출력 처리",
                        "passed": True, "skipped": False,
                        "detail": "단일 출력 formula — 해당 없음 (PASS)"})

    # ── Step 5: 복수 출력 완전성 ──────────────────────────────
    if is_date_based:
        results.append({"step": 5, "label": "복수 출력 완전성",
                        "passed": True, "skipped": True,
                        "detail": "날짜형 계산기 — 자동 검사 건너뜀 (D-4)"})
    else:
        schema_keys = set(outs.keys())
        html_out_ids = set(re.findall(r'id="out_([^"]+)"', html))
        passed5 = not (len(schema_keys) > 1 and len(html_out_ids) < len(schema_keys))
        detail5 = (f"✅ 출력 {len(schema_keys)}개, HTML {len(html_out_ids)}개 ID" if passed5 else
                   f"출력 {len(schema_keys)}개 중 HTML ID {len(html_out_ids)}개만 존재")
        results.append({"step": 5, "label": "복수 출력 완전성",
                        "passed": passed5, "skipped": False, "detail": detail5})

    # ── Step 6: 기본 입력값으로 계산 실행 ────────────────────
    try:
        from modules.formula_engine import execute_formula
        dummy = {}
        for k, v in ins.items():
            if isinstance(v, dict):
                raw = v.get("default", 1.0)
                try:
                    dummy[k] = float(raw) if raw not in (None, "") else 1.0
                except (TypeError, ValueError):
                    dummy[k] = 1.0
            else:
                dummy[k] = 1.0
        result6 = execute_formula(formula, dummy, outs if isinstance(outs, dict) else None)
        passed6 = isinstance(result6, dict) and result6
        detail6 = f"✅ 계산 성공: {str(result6)[:80]}" if passed6 else f"계산 결과 이상: {result6}"
    except Exception as e:
        passed6 = False
        detail6 = f"계산 오류: {e}"
    results.append({"step": 6, "label": "기본값 계산 실행",
                    "passed": passed6, "skipped": False, "detail": detail6})

    return results
