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

    # ─ formula_cap: formula에 min()/max() cap 함수가 포함된 경우 (법정 상한/하한 유지 확인)
    if formula and not is_date_based:
        formula_str_for_cap = (json.dumps(formula, ensure_ascii=False)
                               if isinstance(formula, dict) else str(formula))
        if re.search(r'\bmin\s*\(|\bmax\s*\(', formula_str_for_cap):
            items.append({
                "id": "formula_cap",
                "severity": "critical",
                "label": "공식 상한/하한(cap) 유지 확인",
                "display_value": (f"cap 함수 감지 — 아래 공식에서 min()/max() 적용 범위를 직접 확인:\n"
                                  f"{formula_str_for_cap[:400]}"),
                "auto_source": "formula_cap_detected",
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

    # ─ schema_match: Contract vs AI 생성 결과 필드명 비교 결과가 있을 때 (🔴 필수)
    # generate_app_with_contract()가 embed한 _schema_drift가 있는 경우에만 발생.
    # 드리프트 있으면 변경 내역을 표시, 없으면 일치 확인 메시지 표시.
    schema_drift = app.get("_schema_drift")
    if schema_drift is not None:
        if schema_drift.get("drifted"):
            change_lines = []
            for c in schema_drift.get("changes", []):
                t = c.get("type", "")
                if "input_missing" in t:
                    change_lines.append(f"입력 필드 누락: Contract의 {c['contract']!r}")
                elif "input_extra" in t:
                    change_lines.append(f"입력 필드 추가: AI의 {c['ai']!r} (Contract에 없음)")
                elif "output_missing" in t:
                    change_lines.append(f"출력 필드 누락: Contract의 {c['contract']!r}")
                elif "output_extra" in t:
                    change_lines.append(f"출력 필드 추가: AI의 {c['ai']!r} (Contract에 없음)")
            disp_drift = "⚠️ AI가 필드명을 변경했습니다:\n" + "\n".join(change_lines)
        else:
            disp_drift = "✅ Schema 일치 — Contract 확정 필드명과 동일"
        items.append({
            "id": "schema_match",
            "severity": "critical",
            "label": "Schema 일치 확인 (Contract vs AI 생성)",
            "display_value": disp_drift,
            "auto_source": "contract_schema_drift",
            "checked": False, "checked_by": None, "checked_at": None,
        })

    # ─ 🟡 권장: 화면 안내문 확인 (description / seo_desc)
    desc_text = (app.get("description") or app.get("desc") or app.get("seo_desc") or "")
    if desc_text:
        items.append({
            "id": "description_text",
            "severity": "advisory",
            "label": "화면 안내문 확인",
            "display_value": str(desc_text)[:200],
            "auto_source": "description_field",
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

def _extract_compute_result_fn(js: str) -> str:
    """script.js 전체 번들(공통 컴포넌트는 document/window DOM에 의존)에서
    순수 계산 로직인 window.computeResult 함수 블록만 중괄호 매칭으로 추출.
    app_generator.generate_js()는 [DOM 의존 컴포넌트 + computeResult + CTA/FAQ 설정] 순서로
    이어붙이므로, 전체를 그대로 실행하면 Node.js에 document가 없어 항상 실패한다."""
    marker = "window.computeResult"
    i = js.find(marker)
    if i == -1:
        return ""
    brace_start = js.find("{", i)
    if brace_start == -1:
        return ""
    depth = 0
    j = brace_start
    while j < len(js):
        if js[j] == "{":
            depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                if end < len(js) and js[end] == ";":
                    end += 1
                return js[i:end]
        j += 1
    return ""


def _js_smoke_test(js_content: str, ins: dict, date_fields: list) -> tuple:
    """실제 생성된 script.js에서 computeResult 함수만 추출해 Node.js로 실행,
    예외 없이 반환하는지 확인. 반환값의 정확성(기대값 비교)은 검증하지 않음 —
    실행 가능 여부만 보는 스모크 테스트.
    반환: (passed: bool|None, detail: str). passed=None이면 skip(환경상 실행 불가)."""
    import subprocess
    import tempfile
    import os as _os

    fn_src = _extract_compute_result_fn(js_content)
    if not fn_src:
        return False, "script.js에서 computeResult 함수를 찾지 못함(추출 실패)"

    dummy = {}
    date_pool = ["2015-01-01", "2024-01-01"]
    _di = 0
    for k, v in ins.items():
        # input_schema 값은 {"type":"date"} 딕셔너리가 아니라 "date"/"number" 같은
        # 단순 문자열인 경우가 실제로 더 흔함(app_generator._form_fields_v2와 동일 관례) — 둘 다 처리.
        is_date = (k in (date_fields or ())) or ("date" in str(v).lower())
        if is_date:
            dummy[k] = date_pool[min(_di, len(date_pool) - 1)]
            _di += 1
        elif isinstance(v, dict):
            raw = v.get("default", 1000)
            try:
                dummy[k] = float(raw) if raw not in (None, "") else 1000
            except (TypeError, ValueError):
                dummy[k] = 1000
        else:
            dummy[k] = 1000

    harness = (
        "globalThis.window = globalThis;\n" + fn_src + "\n"
        + f"var out = window.computeResult({json.dumps(dummy, ensure_ascii=False)});\n"
        + "process.stdout.write(JSON.stringify(out));\n"
    )
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(harness)
        # encoding 명시 필수: 생성된 JS에 한글 notice 문자열이 포함될 수 있어
        # Windows 기본 로케일(cp949)로 stdout/stderr를 디코딩하면 깨짐/예외 발생.
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
        if r.returncode != 0:
            return False, f"JS 실행 오류(더미 입력 {dummy}): {r.stderr.strip()[:200]}"
        try:
            parsed = json.loads(r.stdout.strip() or "null")
        except Exception:
            return False, f"JS 반환값 파싱 실패: {r.stdout.strip()[:200]}"
        return True, f"더미 입력 {dummy} → computeResult() 정상 실행, 반환: {str(parsed)[:150]}"
    except FileNotFoundError:
        return None, "Node.js 미설치 — 스모크 테스트 건너뜀(환경 제약)"
    except subprocess.TimeoutExpired:
        return False, "JS 실행 타임아웃(10초 초과) — 무한루프 가능성"
    finally:
        try:
            _os.unlink(path)
        except Exception:
            pass


def _extract_rate_constants(js_or_html: str) -> dict:
    """JS/HTML 안의 대문자 상수 선언(예: NP_RATE=0.045, DAILY_MAX = 66000)을 추출.
    요율/기준값 변경 감지(Step 8)용 — 완전한 파서가 아닌 휴리스틱."""
    consts = {}
    for m in re.finditer(r'\b([A-Z][A-Z0-9_]{2,})\s*=\s*([0-9]+(?:\.[0-9]+)?)', js_or_html or ""):
        consts[m.group(1)] = m.group(2)
    return consts


def pre_build_qa(calc: dict, cfg: dict, prev_files: dict = None) -> list[dict]:
    """
    Build 전 사전 검사(기존 6단계 + Phase E 확장 2단계).
    calc: DB 계산기 record (slug, formula, input_schema, output_schema 등)
    prev_files: 직전 확정 스냅샷(_site/{slug}/에서 읽은 {index.html,style.css,script.js}).
                없으면(None) Step 8은 비교 대상 없음으로 skip.
    반환: [{"step": int, "label": str, "passed": bool, "skipped": bool, "detail": str}]
    """
    from modules.app_generator import generate_calculator, _validation_mode
    from modules.registry_loader import load_registry_v3

    results = []

    # DB record 자체의 compute_type/date_fields는 비어있는 경우가 많아(확인됨) 불안정.
    # _validation_mode()는 app_generator.py가 실제 생성 시 쓰는 동일한 판별 기준(registry
    # validation_mode)이라 더 신뢰 가능 — 기존 두 조건에 OR로 추가(기존 감지 경로는 유지).
    is_date_based = (str(calc.get("compute_type", "")) == "date_based" or
                     bool(calc.get("date_fields")) or
                     _validation_mode(calc) == "skip")
    _slug = str(calc.get("slug", ""))
    is_tier2b = (load_registry_v3().get(_slug) or {}).get("tier_subtype") == "B"

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
                     (5, "복수 출력 완전성"), (6, "기본값 계산 실행"),
                     (7, "JS 실행 스모크 테스트"), (8, "요율/기준값 변경 감지")]:
            results.append({"step": s, "label": l, "passed": False, "skipped": True,
                            "detail": "Step 1/2 실패로 건너뜀"})
        return results

    # generate_calculator로 파일 생성 (Step 3~8에서 사용)
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
                     (5, "복수 출력 완전성"), (6, "기본값 계산 실행"),
                     (7, "JS 실행 스모크 테스트"), (8, "요율/기준값 변경 감지")]:
            results.append({"step": s, "label": l, "passed": False, "skipped": False,
                            "detail": f"generate_calculator() 실패: {gen_err}"})
        return results

    # ── Tier2-B(예: 군인 전역일)는 표준 폼/수식 전제인 Step 3~6이 애초에 맞지 않음.
    # 잘못된 FAIL 표시를 막기 위해 여기서 skip 처리하고 Step 7/8로 넘어간다.
    if is_tier2b:
        for s, l in [(3, "HTML 출력 요소 1:1 대응"), (4, "JS 다중 출력 처리"),
                     (5, "복수 출력 완전성"), (6, "기본값 계산 실행")]:
            results.append({"step": s, "label": l, "passed": True, "skipped": True,
                            "detail": "Tier2-B — 표준 폼/수식 기반 검사 대상 아님(DB 템플릿 직접 사용)"})
        _step7_tier2b = (True, "Tier2-B — 별도 script.js 없음(자체완결형 HTML), 스모크 테스트 대상 아님")
        results.append({"step": 7, "label": "JS 실행 스모크 테스트",
                        "passed": _step7_tier2b[0], "skipped": True, "detail": _step7_tier2b[1]})
        prev_content = (prev_files or {}).get("index.html") or ""
        if not prev_content:
            results.append({"step": 8, "label": "요율/기준값 변경 감지",
                            "passed": True, "skipped": True,
                            "detail": "직전 스냅샷 없음(최초 생성) — 비교 대상 없음"})
        else:
            _old_c = _extract_rate_constants(prev_content)
            _new_c = _extract_rate_constants(html)
            _changed = {k: (_old_c.get(k), _new_c.get(k)) for k in set(_old_c) | set(_new_c)
                       if _old_c.get(k) != _new_c.get(k)}
            if _changed:
                _d8 = "; ".join(f"{k}: {o} → {n}" for k, (o, n) in sorted(_changed.items()))
                results.append({"step": 8, "label": "요율/기준값 변경 감지",
                                "passed": False, "skipped": False,
                                "detail": f"이전 스냅샷 대비 상수 변경 감지(의도한 변경인지 확인 필요) — {_d8}"})
            else:
                results.append({"step": 8, "label": "요율/기준값 변경 감지",
                                "passed": True, "skipped": False,
                                "detail": "이전 스냅샷과 요율/기준값 동일"})
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
    # is_date_based 계산기는 Step 3~5와 동일한 이유(실제 계산이 formula 필드가 아니라
    # _compute_js()의 하드코딩 JS로 수행됨)로 execute_formula() 재현이 애초에 맞지 않는
    # 검사임 — Step 3~5와 일관되게 skip 처리(기존 알려진 한계, Phase E에서 수정 범위 아님).
    if is_date_based:
        results.append({"step": 6, "label": "기본값 계산 실행",
                        "passed": True, "skipped": True,
                        "detail": "날짜형 계산기 — 실제 계산은 하드코딩 JS(_compute_js)로 수행되어 "
                                  "formula 재현 검사가 맞지 않음(기존 알려진 한계, Step 3~5와 동일 사유로 skip)"})
    else:
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

    # ── Step 7: 실제 script.js 실행 스모크 테스트(Node.js) ───────
    if not (js or "").strip():
        results.append({"step": 7, "label": "JS 실행 스모크 테스트",
                        "passed": True, "skipped": True,
                        "detail": "script.js 없음 — 검사 대상 아님"})
    else:
        _p7, _d7 = _js_smoke_test(js, ins, calc.get("date_fields") or [])
        results.append({"step": 7, "label": "JS 실행 스모크 테스트",
                        "passed": True if _p7 is None else _p7,
                        "skipped": _p7 is None, "detail": _d7})

    # ── Step 8: 직전 스냅샷 대비 요율/기준값 변경 감지 ────────────
    prev_js = (prev_files or {}).get("script.js") or (prev_files or {}).get("index.html") or ""
    if not prev_js:
        results.append({"step": 8, "label": "요율/기준값 변경 감지",
                        "passed": True, "skipped": True,
                        "detail": "직전 스냅샷 없음(최초 생성) — 비교 대상 없음"})
    else:
        _old_c = _extract_rate_constants(prev_js)
        _new_c = _extract_rate_constants(js or html)
        _changed = {k: (_old_c.get(k), _new_c.get(k)) for k in set(_old_c) | set(_new_c)
                   if _old_c.get(k) != _new_c.get(k)}
        if _changed:
            _d8 = "; ".join(f"{k}: {o} → {n}" for k, (o, n) in sorted(_changed.items()))
            results.append({"step": 8, "label": "요율/기준값 변경 감지",
                            "passed": False, "skipped": False,
                            "detail": f"이전 스냅샷 대비 상수 변경 감지(의도한 변경인지 확인 필요) — {_d8}"})
        else:
            results.append({"step": 8, "label": "요율/기준값 변경 감지",
                            "passed": True, "skipped": False,
                            "detail": "이전 스냅샷과 요율/기준값 동일"})

    return results
