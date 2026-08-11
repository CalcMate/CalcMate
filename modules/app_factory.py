# -*- coding: utf-8 -*-
"""
modules/app_factory.py — 계산기 자동 생성 (v12.0)

흐름: GPT(총괄 spec) → Claude(코드 HTML/CSS/JS) → GPT(SEO/FAQ/블로그초안)
      → Gemini(이미지 프롬프트) → calculators + app_templates 저장
      → v3 Registry 즉시 기록(status=HOLD) → legal 검증 → READY 전환

모든 AI 호출은 ai_roles(=ai_provider) 경유, 데이터 저장은 Repository 경유.
gspread/Drive 직접 호출 없음.
"""
import json
import re
from datetime import datetime
from pathlib import Path

# v3 Registry 경로 (docs/registry/*.yaml SSOT)
_REG_DIR = Path(__file__).resolve().parent.parent / "docs" / "registry"

# Contract Schema 경로 (docs/contract_schema/ — CA-2-4)
_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "docs" / "contract_schema"

# category → _af yaml 파일명(확장자 제외). 미매핑은 labor_af 폴백.
_CATEGORY_AF_YAML_MAP: dict[str, str] = {
    "세금/정부혜택": "tax_af",
    "노무/급여": "labor_af",
    "고용/보험": "employment_af",
    "노무/급여/보험": "insurance_af",
    "부동산/임대": "realty_af",
}

from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.template_repository import TemplateRepository
from .ai_roles import make_provider
from .json_utils import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()

# App Factory 세션 초기화 대상 키 (폐기 & 초기화 버튼에서 사용)
AF_SESSION_DISCARD_KEYS: tuple[str, ...] = (
    "af_result",                  # AI 생성 결과 전체
    "af_name",                    # 계산기명 입력
    "af_cat",                     # 카테고리 입력
    "af_desc",                    # 설명 입력
    "af_tier",                    # Tier 라디오 선택
    "af_slug",                    # slug 입력
    "af_keyword",                 # 키워드 입력
    "af_tier_suggest",            # AI Tier 추천 상태
    "_af_last_slug_for",          # slug 자동완성 내부 추적
    "af_seo",                     # SEO 제목 표시 (af_result 소멸 시 자동 소멸)
    "af_discard_confirm",         # 폐기 확인 대화창 플래그
    # ── Contract 모드(Mode B) 전용 키 ───────────────────────────
    "af_contract",                # build_contract() 결과 객체
    "af_contract_slug_pre",       # 생성 전 확정 slug
    "af_contract_input_fields",   # 확정 입력 필드 (쉼표 구분 문자열)
    "af_contract_output_fields",  # 확정 출력 필드 (쉼표 구분 문자열)
    "af_contract_formula",        # 확정 formula (str 또는 JSON)
    "af_contract_test_cases",     # 검증 케이스 (JSON 배열 문자열)
    # ── Formula lifecycle 보조 키 (CA-3-1/CA-3-4) ────────────
    "af_formula_confirmed_text",  # operator_confirmed 시점의 raw formula
    "af_formula_validation",      # [🔍 Formula 검증] 결과 dict
    "af_formula_ai_suggested_text",  # AI 제안 추적 (ai_suggested 수정 감지용)
    "_af_ai_suggest_override",    # 2-click 덮어쓰기 확인 플래그
)


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", (text or "").strip()).strip("_").lower()
    return s or datetime.now().strftime("%H%M%S")


def _pj(v, default=None):
    """JSON 문자열/딕셔너리 안전 파싱(기존 계산기 input_schema 요약용)."""
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v) if v else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def _strip_fence(text: str) -> str:
    """```html ... ``` 코드블록 펜스 제거."""
    s = (text or "").strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    return s


def _chat(cfg, role, system, user, max_tokens=1200):
    provider, model = make_provider(cfg, role)
    text, tokens = provider.chat(system, user, model, max_tokens=max_tokens)
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception as _e:
        LOG.warning("토큰 비용 기록/조회 실패: %s", _e)
    return text, model, tokens


def _category_to_af_yaml(category: str) -> str:
    """category → _af yaml 파일명(확장자 제외). 미매핑 시 labor_af 폴백."""
    return _CATEGORY_AF_YAML_MAP.get(str(category).strip(), "labor_af")


def _next_display_order() -> int:
    """v3 registry 전체(기존+_af 파일 포함) 최대 display_order + 1. 없으면 10."""
    from .registry_loader import load_registry_v3, invalidate
    invalidate()
    v3 = load_registry_v3(force=True)
    orders = [e.get("display_order", 0) for e in v3.values()
              if isinstance(e.get("display_order"), int)]
    return max(orders, default=9) + 1


def _build_v3_entry(app: dict, slug: str, tier: int = 2, contract: dict = None) -> dict:
    """v3 Registry(docs/registry/*_af.yaml)에 기록할 엔트리 생성.
    기존 8개 계산기 형식과 동일 스키마 + status/tier/source 추가.
    contract: Mode B(generate_app_with_contract) 경로에서만 전달. None이면 Mode A(기존 동작 유지)."""
    _c = contract or {}
    ins = app.get("input_schema", {}) or {}
    outs = app.get("output_schema", {}) or {}
    date_fields, compute_type, validation_mode, difficulty = _infer_registry_meta(
        ins, outs, app.get("formula", ""))
    name = app.get("name", "")
    desc = (app.get("description", "") or app.get("seo_desc", "") or "").strip()
    card_desc = (desc[:45] + "…") if len(desc) > 45 else desc
    entry = {
        "name": name,
        "slug": slug,
        "category": app.get("category", ""),
        "emoji": "🧮",
        "card_label": name,
        "compute_type": compute_type,
        "date_fields": date_fields,
        "validation_mode": validation_mode,
        "field_labels": app.get("labels", {}) or {},
        "input_labels": list(_c.get("input_fields", []) or []),
        "output_labels": list(_c.get("output_fields", []) or []),
        "display_order": _next_display_order(),
        "card_desc": card_desc,
        "difficulty": difficulty,
        "difficulty_status": "provisional",
        "status": "HOLD",
        "tier": tier,
        "source": "app_factory",
        "content": {"evergreen": True, "update_cycle": None, "content_caveat": None},
        "related_slugs": [],
        "legal_refs": list(_c.get("legal_refs", []) or []),
        "writer_context": {
            "emphasize": [],
            "example_patterns": [desc[:60]] if desc else [],
            "calculation_story": [],
        },
        "contract_source": {
            "contract_slug":    _c.get("slug", ""),
            "input_fields":     list(_c.get("input_fields",     []) or []),
            "output_fields":    list(_c.get("output_fields",    []) or []),
            "formula_status":   _c.get("formula_status",   "not_generated"),
            "test_cases_status":_c.get("test_cases_status","not_generated"),
        } if _c else None,
    }
    if app.get("compute_rules"):
        entry["compute_rules"] = app["compute_rules"]
    return entry


def _write_registry_v3(slug: str, entry: dict, category: str) -> None:
    """docs/registry/<category>_af.yaml에 slug 엔트리를 추가.
    _af.yaml은 App Factory 전용 — 기존 registry/*.yaml은 절대 수정하지 않음.
    기존 v3 slug(기존 8개 포함)와 중복 시 ValueError."""
    import yaml
    from .registry_loader import load_registry_v3, invalidate

    # 기존 v3 slug 보호 — 기존 8개 + 이미 등록된 _af 엔트리 모두 포함
    existing_v3 = load_registry_v3(force=True)
    if slug in existing_v3:
        raise ValueError(f"v3 Registry에 이미 존재하는 slug: '{slug}'")

    yaml_name = _category_to_af_yaml(category)
    yaml_file = _REG_DIR / f"{yaml_name}.yaml"

    # 기존 _af 파일 로드 (없으면 빈 dict)
    try:
        existing = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        if not isinstance(existing, dict):
            existing = {}
    except FileNotFoundError:
        existing = {}

    existing[slug] = entry
    _AF_HEADER = (
        f"# registry/{yaml_name}.yaml — App Factory 자동생성 계산기 (v3 SSOT)\n"
        "# ⚠️ 이 파일은 App Factory(modules/app_factory)가 자동으로 씁니다. 직접 편집 주의.\n"
        "# status: HOLD = legal 검증 대기 중 (index/sitemap 비노출)\n"
        "# status: READY = 공개 (index/sitemap 포함, CalcMate 정적 사이트 빌드 대상)\n"
    )
    body = yaml.dump(existing, allow_unicode=True, sort_keys=False, default_flow_style=False)
    yaml_file.write_text(_AF_HEADER + "\n" + body, encoding="utf-8")
    invalidate()
    LOG.info("v3 Registry 기록(HOLD): %s → %s", slug, yaml_file.name)


def _delete_from_registry_v3(slug: str, category: str) -> bool:
    """_af.yaml에서 slug 엔트리를 제거. 파일 없거나 slug 없으면 False 반환."""
    import yaml
    from .registry_loader import invalidate

    yaml_name = _category_to_af_yaml(category)
    yaml_file = _REG_DIR / f"{yaml_name}.yaml"
    if not yaml_file.exists():
        return False

    try:
        existing = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return False

    if not isinstance(existing, dict) or slug not in existing:
        return False

    del existing[slug]
    _AF_HEADER = (
        f"# registry/{yaml_name}.yaml — App Factory 자동생성 계산기 (v3 SSOT)\n"
        "# ⚠️ 이 파일은 App Factory(modules/app_factory)가 자동으로 씁니다. 직접 편집 주의.\n"
        "# status: HOLD = legal 검증 대기 중 (index/sitemap 비노출)\n"
        "# status: READY = 공개 (index/sitemap 포함, CalcMate 정적 사이트 빌드 대상)\n"
    )
    body = yaml.dump(existing, allow_unicode=True, sort_keys=False, default_flow_style=False)
    yaml_file.write_text(_AF_HEADER + "\n" + body, encoding="utf-8")
    invalidate()
    LOG.info("v3 Registry 엔트리 제거: %s → %s", slug, yaml_file.name)
    return True


def promote_to_ready(slug: str) -> tuple:
    """App Factory 계산기의 v3 status를 HOLD → READY로 전환.
    legal 검증 완료 후 호출. 기존 8개 계산기(source != app_factory)에는 동작 거부."""
    import yaml
    from .registry_loader import load_registry_v3, invalidate

    v3 = load_registry_v3(force=True)
    entry = v3.get(slug)
    if entry is None:
        return False, f"v3 Registry에 '{slug}' 없음"
    if entry.get("source") != "app_factory":
        return False, f"'{slug}'은 App Factory 생성 계산기가 아닙니다 (기존 계산기 수정 금지)"
    if entry.get("status") == "READY":
        return True, f"'{slug}'은 이미 READY 상태입니다"

    # 체크리스트 🔴 필수 항목 완료 여부 검증
    checklist = entry.get("review_checklist") or []
    if checklist:
        incomplete = [i.get("label", i.get("id", "?")) for i in checklist
                      if i.get("severity") == "critical" and not i.get("checked")]
        if incomplete:
            return False, (f"🔴 필수 검토 항목 미완료 ({len(incomplete)}개): "
                           f"{incomplete} — 대시보드에서 체크 완료 후 재시도")

    category = entry.get("category", "")
    yaml_name = _category_to_af_yaml(category)
    yaml_file = _REG_DIR / f"{yaml_name}.yaml"

    try:
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return False, f"Registry 파일 읽기 실패: {e}"
    if not isinstance(data, dict) or slug not in data:
        return False, f"'{slug}'이 {yaml_file.name}에 없음"

    data[slug]["status"] = "READY"
    _AF_HEADER = (
        f"# registry/{yaml_name}.yaml — App Factory 자동생성 계산기 (v3 SSOT)\n"
        "# ⚠️ 이 파일은 App Factory(modules/app_factory)가 자동으로 씁니다. 직접 편집 주의.\n"
        "# status: HOLD = legal 검증 대기 중 (index/sitemap 비노출)\n"
        "# status: READY = 공개 (index/sitemap 포함, CalcMate 정적 사이트 빌드 대상)\n"
    )
    body = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    yaml_file.write_text(_AF_HEADER + "\n" + body, encoding="utf-8")
    invalidate()
    LOG.info("v3 Registry HOLD→READY: %s", slug)
    return True, f"✅ '{slug}' HOLD → READY 전환 완료. 사이트 재빌드 후 index/sitemap에 반영됩니다."


def build_contract(
    slug: str,
    name: str,
    category: str = "",
    tier: str = "Tier2-A",
    input_fields: list = None,
    output_fields: list = None,
    formula=None,
    formula_status: str = None,
    scope_exclusions: list = None,
    test_cases: list = None,
    desc: str = "",
    legal_refs: list = None,
) -> dict:
    """운영자가 확정한 계산기 스펙을 Contract 객체로 생성.

    Contract는 AI 생성 결과의 기준점이다 — slug/필드명/formula가 AI에 의해
    변경됐는지 validate_against_contract()로 검증한다.

    slug:             확정 URL 식별자 (소문자 영문-숫자-하이픈)
    input_fields:     확정 입력 필드명 리스트 (예: ["years_of_service", "used_days"])
    output_fields:    확정 출력 필드명 리스트 (예: ["total_days", "remaining_days"])
    formula:          확정 수식 (str 또는 dict)
    formula_status:   명시적 상태 ("not_generated"/"ai_suggested"/"pending_validation"/"operator_confirmed").
                      None이면 formula 존재 여부로 자동 도출:
                        formula 있음 → "pending_validation"
                        formula 없음 → "not_generated"
    scope_exclusions: 명시적 제외 조건 (화면 안내문 표시용)
    test_cases:       검증 케이스 [{"input": {...}, "expected": {...}}]
    desc:             계산기 설명 (AI 생성 시 u1/u3 프롬프트에 삽입됨)
    legal_refs:       법령 entity_id 리스트 (legal_master/*.yaml의 entity_id)
    """
    has_formula = formula is not None and formula != ""
    if formula_status is None:
        derived_status = "pending_validation" if has_formula else "not_generated"
    else:
        derived_status = formula_status
    return {
        "slug": str(slug).strip().lower(),
        "name": str(name).strip(),
        "category": str(category).strip(),
        "tier": str(tier).strip(),
        "input_fields": list(input_fields or []),
        "output_fields": list(output_fields or []),
        "formula": formula,
        "formula_status": derived_status,
        "scope_exclusions": list(scope_exclusions or []),
        "test_cases": list(test_cases or []),
        "test_cases_status": "operator_confirmed" if test_cases else "not_generated",
        "desc": str(desc).strip(),
        "legal_refs": list(legal_refs or []),
    }


def check_hold_rules(contract: dict) -> dict:
    """Pre-generation Soft Gate — CA-1A §5 hold_rules 중 HOLD-1/2/3 평가.

    생성 전 운영자에게 위험 요소를 알리기 위한 경고 함수.
    Hard block이 아님. 운영자가 경고를 확인하고 진행 여부를 결정한다.

    반환: {
        "held": bool,           # True이면 경고 있음 (생성 진행은 운영자 결정)
        "rules": list[str],     # 발동된 rule id 목록 (예: ["HOLD-1", "HOLD-3"])
        "messages": list[str],  # 운영자에게 표시할 경고 메시지
    }
    """
    from modules.review_center import CRITICAL_CATEGORIES
    from modules.registry_loader import load_legal_master

    rules, messages = [], []

    # HOLD-1: formula 미확정 또는 검증 미완료 (operator_confirmed만 통과)
    if contract.get("formula_status", "not_generated") != "operator_confirmed":
        rules.append("HOLD-1")
        messages.append(
            "HOLD-1: formula가 운영자 확정 상태가 아닙니다. "
            "수식 없이 생성하면 AI가 임의 수식을 사용할 수 있습니다."
        )

    # HOLD-2: critical category + test_cases 미확정
    if (contract.get("test_cases_status", "not_generated") == "not_generated"
            and contract.get("category", "") in CRITICAL_CATEGORIES):
        rules.append("HOLD-2")
        messages.append(
            f"HOLD-2: '{contract.get('category', '')}' 카테고리는 법령 계산기입니다. "
            "테스트 케이스 없이 생성하면 수식 정확성을 사전 검증할 수 없습니다."
        )

    # HOLD-3: legal_refs entity의 confidence=medium (경고)
    legal_refs = contract.get("legal_refs") or []
    if legal_refs:
        lm = load_legal_master()
        medium_refs = [
            ref for ref in legal_refs
            if (lm.get(ref) or {}).get("confidence") == "medium"
        ]
        if medium_refs:
            rules.append("HOLD-3")
            messages.append(
                f"HOLD-3: 참조 법령 {medium_refs}의 confidence=medium — "
                "법적 불확실성이 있습니다. 내용을 확인하고 진행하세요."
            )

    return {
        "held": bool(rules),
        "rules": rules,
        "messages": messages,
    }


def validate_against_contract(contract: dict, ai_app: dict) -> dict:
    """AI 생성 결과를 Contract와 비교하여 불일치 항목을 반환.

    slug, input/output 필드명, formula 세 축을 비교한다.
    불일치가 있으면 status_hint="INVALID" + messages에 상세 내용을 담아 반환.
    저장(save_app)을 직접 차단하지 않으며 운영자 검토 후 진행하도록 설계됨.

    반환: {
        "valid": bool,
        "slug_mismatch": bool,
        "slug_contract": str,
        "slug_ai": str,
        "schema_drift": dict,   # detect_schema_drift() 결과
        "formula_changed": bool,
        "status_hint": "VALID" | "INVALID",
        "messages": list[str],
    }
    """
    from .formula_engine import detect_schema_drift

    messages = []

    contract_slug = str(contract.get("slug", "")).strip().lower()
    ai_slug = str(ai_app.get("slug", "") or "").strip().lower()
    slug_mismatch = bool(ai_slug and ai_slug != contract_slug)
    if slug_mismatch:
        messages.append(f"slug 불일치: Contract={contract_slug!r} → AI={ai_slug!r}")

    drift = detect_schema_drift(contract, ai_app)
    for change in drift.get("changes", []):
        t = change.get("type", "")
        f_c, f_a = change.get("contract"), change.get("ai")
        if "input_missing" in t:
            messages.append(f"입력 필드 누락: Contract의 {f_c!r}가 AI 결과에 없음")
        elif "input_extra" in t:
            messages.append(f"입력 필드 추가: AI가 {f_a!r}를 추가 (Contract에 없음)")
        elif "output_missing" in t:
            messages.append(f"출력 필드 누락: Contract의 {f_c!r}가 AI 결과에 없음")
        elif "output_extra" in t:
            messages.append(f"출력 필드 추가: AI가 {f_a!r}를 추가 (Contract에 없음)")

    contract_formula = contract.get("formula")
    ai_formula = ai_app.get("formula")
    formula_changed = False
    if contract_formula is not None:
        def _norm(f):
            if isinstance(f, dict):
                return json.dumps(f, ensure_ascii=False, sort_keys=True)
            return str(f or "").strip()
        formula_changed = _norm(contract_formula) != _norm(ai_formula)
        if formula_changed:
            messages.append("formula 변경: AI가 Contract 확정 formula를 수정했습니다")

    valid = not slug_mismatch and not drift["drifted"] and not formula_changed
    return {
        "valid": valid,
        "slug_mismatch": slug_mismatch,
        "slug_contract": contract_slug,
        "slug_ai": ai_slug,
        "schema_drift": drift,
        "formula_changed": formula_changed,
        "status_hint": "VALID" if valid else "INVALID",
        "messages": messages,
    }


# ── CA-3-3: Type D 식별 키워드 ─────────────────────────────────────────────
_TYPE_D_FLOW_KEYWORDS: frozenset = frozenset({
    "매년 변경", "별표", "테이블", "나이·피보험기간",
})


def _is_type_d_flow(calc_flows: list) -> bool:
    """calculation_flow에 Type D 식별자(연도 변경/별표/테이블)가 있으면 True."""
    for item in (calc_flows or []):
        for kw in _TYPE_D_FLOW_KEYWORDS:
            if kw in str(item):
                return True
    return False


def suggest_formula(
    cfg: dict,
    name: str,
    category: str = "",
    desc: str = "",
    input_fields: list = None,
    output_fields: list = None,
    legal_refs: list = None,
    calculation_flow: list = None,
    scope_exclusions: list = None,
    slug: str = None,
) -> dict:
    """Contract 기반 AI Formula 제안 (CA-3-3).

    기존 generate_app() 전체 생성과 무관한 독립 함수.
    AI 호출 1회 (max_tokens=300).

    반환 status:
      "ai_suggested"  — AI 제안 성공
      "not_generated" — 차단/실패

    반환 형식:
    {
        "success": bool,
        "formula": str | dict | None,
        "reason":  str,
        "assumptions": list,
        "warnings":    list[str],
        "status":  "ai_suggested" | "not_generated",
    }

    중요: success=True 라도 "operator_confirmed"가 아니다.
    최종 확정은 반드시 운영자 행동(Dashboard [✅ Formula 확정])으로 이루어진다.
    """
    from modules.formula_engine import CUSTOM_COMPUTE_SLUGS, validate_formula

    input_fields = list(input_fields or [])
    output_fields = list(output_fields or [])

    def _fail(reason: str, warnings: list = None) -> dict:
        LOG.info("suggest_formula 실패: %s", reason)
        return {
            "success": False, "formula": None, "reason": reason,
            "assumptions": [], "warnings": list(warnings or []),
            "status": "not_generated",
        }

    # ── Type D 차단 1: CUSTOM_COMPUTE_SLUGS ───────────────────────
    if slug and slug in CUSTOM_COMPUTE_SLUGS:
        return _fail(
            "이 계산기는 커스텀 계산 로직이 필요하여 AI Formula 자동 제안을 지원하지 않습니다.",
            ["CUSTOM_COMPUTE_SLUGS 대상 계산기"],
        )

    # ── 필수 입력 확인 ─────────────────────────────────────────────
    if not input_fields:
        return _fail("input_fields가 비어 있습니다. Formula 제안에 필요합니다.")
    if not output_fields:
        return _fail("output_fields가 비어 있습니다. Formula 제안에 필요합니다.")

    # ── legal_master에서 calculation_flow 조회 ──────────────────────
    calc_flows = list(calculation_flow or [])
    if legal_refs and not calc_flows:
        try:
            from modules.registry_loader import load_legal_master
            lm = load_legal_master()
            for ref in legal_refs:
                calc_flows.extend((lm.get(ref) or {}).get("calculation_flow") or [])
        except Exception as _e:
            LOG.warning("legal_master 로드 실패: %s", _e)

    # ── Type D 차단 2: calculation_flow 키워드 기반 ─────────────────
    if _is_type_d_flow(calc_flows):
        return _fail(
            "이 계산기는 테이블/법령 기준값 또는 연도별 변경 데이터가 필요하여 "
            "AI Formula 자동 제안을 지원하지 않습니다.",
            ["calculation_flow에 테이블/매년 변경 항목 포함"],
        )

    # ── Prompt 구성 ────────────────────────────────────────────────
    multi_output = len(output_fields) > 1
    if multi_output:
        output_format_rule = (
            f"5. 복수 출력이므로 JSON 형식으로 반환: "
            + json.dumps({k: "산술식" for k in output_fields}, ensure_ascii=False)
            + " (출력 변수 목록과 키 이름 일치)\n"
        )
    else:
        output_format_rule = "5. 단일 출력: 산술 표현식 문자열\n"

    sys_suggest = (
        "너는 계산기 Formula 제안 도우미다.\n"
        "제공된 Contract와 법적 근거 정보만 사용한다.\n"
        "존재하지 않는 입력 변수나 출력 변수를 만들지 않는다.\n"
        "제공되지 않은 법률 규칙, 요율, 기준값을 임의로 생성하지 않는다.\n"
        "계산 규칙이 충분하지 않으면 Formula를 추측하지 않는다.\n"
        "AI의 제안은 운영자의 최종 확정이 아니며, 검증되지 않은 Formula임을 전제로 한다.\n\n"
        f"입력 변수(이것만 사용 가능): {', '.join(input_fields)}\n"
        f"출력 변수: {', '.join(output_fields)}\n"
        + (f"카테고리: {category}\n" if category else "")
        + (f"설명: {desc}\n" if desc else "")
        + (
            "법령 계산 흐름(참고):\n"
            + "\n".join(f"  - {f}" for f in calc_flows)
            + "\n"
            if calc_flows else ""
        )
        + "\n규칙:\n"
        "1. 입력 변수 목록 외 변수 절대 금지\n"
        "2. 대입문(=), 세미콜론(;), 함수 정의, 외부 함수 호출 금지\n"
        "3. 허용 함수: min, max, round, abs, int, float 만\n"
        "4. calculation_flow에 없는 상수·요율 추가 금지\n"
        + output_format_rule
        + "\n반드시 아래 JSON 형식으로만 응답하라:\n"
        '{"formula": "...", "reason": "...", "assumptions": [], "warnings": []}\n'
        "계산 근거가 불충분하면:\n"
        '{"formula": null, "reason": "근거 부족 이유", "assumptions": [], "warnings": ["..."]}'
    )
    u_suggest = f"계산기명: {name}"

    # ── AI 호출 (1회, max_tokens=300) ─────────────────────────────
    try:
        raw_text, _, _ = _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)
    except Exception as exc:
        LOG.error("suggest_formula AI 호출 실패: %s", exc)
        return _fail(f"AI 호출 실패: {exc}", [str(exc)])

    # ── 빈 응답 처리 ───────────────────────────────────────────────
    if not raw_text or not raw_text.strip():
        return _fail("AI가 빈 응답을 반환했습니다.")

    # ── 응답 파싱 (JSON 우선, raw string 폴백) ─────────────────────
    parsed_formula = None
    reason = ""
    assumptions: list = []
    warnings: list = []

    try:
        obj = parse_json_lenient(raw_text)
        if isinstance(obj, dict):
            parsed_formula = obj.get("formula")
            reason = str(obj.get("reason") or "")
            assumptions = list(obj.get("assumptions") or [])
            warnings = list(obj.get("warnings") or [])
        else:
            parsed_formula = str(obj).strip() if obj is not None else None
    except Exception:
        parsed_formula = raw_text.strip().strip("\"'")

    # ── formula null/빈 처리 ───────────────────────────────────────
    if parsed_formula is None or parsed_formula == "" or parsed_formula == "null":
        return _fail(reason or "AI가 Formula를 생성하지 못했습니다.", warnings)

    # ── dict formula: JSON 문자열이면 파싱 ─────────────────────────
    if isinstance(parsed_formula, str) and parsed_formula.strip().startswith("{"):
        try:
            parsed_formula = json.loads(parsed_formula)
        except Exception:
            pass

    # ── R-2: dict formula 출력 키 검증 ────────────────────────────
    if isinstance(parsed_formula, dict) and output_fields:
        expected_keys = set(output_fields)
        actual_keys = set(parsed_formula.keys())
        extra = actual_keys - expected_keys
        if extra:
            return _fail(
                f"AI가 정의되지 않은 출력 변수를 사용했습니다: {extra}",
                [f"output_fields에 없는 키: {extra}"],
            )

    # ── R-1: 입력 변수 검증 (validate_formula 재사용) ──────────────
    schema = {f: "number" for f in input_fields}
    ok, msg = validate_formula(parsed_formula, schema)
    if not ok:
        return _fail(
            f"AI Formula 변수 검증 실패: {msg}",
            [f"변수 검증 오류: {msg}"],
        )

    return {
        "success": True,
        "formula": parsed_formula,
        "reason": reason,
        "assumptions": assumptions,
        "warnings": warnings,
        "status": "ai_suggested",
    }


def generate_app_with_contract(cfg: dict, contract: dict) -> dict:
    """Contract 기반 계산기 생성.

    generate_app()을 호출한 뒤 Contract와 비교 — AI 결과의 slug/필드명/formula가
    Contract를 벗어나면 _contract_validation["valid"]=False로 기록한다.
    운영자가 불일치를 검토·수정한 후 save_app()을 호출하도록 설계됨.
    자동 저장 없음, 자동 승인 없음.
    """
    name = contract.get("name", "")
    category = contract.get("category", "")
    tier_str = contract.get("tier", "Tier2-A")
    tier_int = 1 if tier_str == "Tier1" else 2
    desc = contract.get("desc", "")

    result = generate_app(cfg, name, category=category, desc=desc, tier=tier_int,
                          _contract=contract)

    validation = validate_against_contract(contract, result)
    result["_contract"] = contract
    result["_contract_validation"] = validation
    result["_schema_drift"] = validation["schema_drift"]

    if not validation["valid"]:
        LOG.warning(
            "Contract 불일치 — 운영자 검토 필요: %s → %s",
            name, validation["messages"],
        )
    return result


def _build_contract_enforcement_prompt(contract: dict) -> str:
    """Contract 기반 생성 시 sys1에 삽입되는 스펙 고정 지시문.

    Contract의 input_fields/output_fields/formula/test_cases를 AI에게 명시적으로 전달해
    AI가 Contract를 무시하거나 필드를 누락하는 것을 방지한다.
    """
    input_fields = contract.get("input_fields") or []
    output_fields = contract.get("output_fields") or []
    formula = contract.get("formula")
    test_cases = contract.get("test_cases") or []

    lines = [
        "━━━━ CONTRACT LOCK — 운영자 사전 확정 사양 (절대 변경 금지) ━━━━",
        "아래 스펙은 운영자가 법령·취업규칙에 근거해 AI 호출 전에 확정한 것이다.",
        "AI는 이 스펙을 그대로 구현해야 한다. 협상·간소화·자체 재설계 금지.",
        "",
        f"[고정 입력 필드 {len(input_fields)}개] input_schema 키를 정확히 아래와 일치시켜라:",
        "  " + ", ".join(input_fields),
        "  (키 이름 변경·추가·삭제 절대 금지)",
        "",
        f"[고정 출력 필드 {len(output_fields)}개] output_schema 키를 정확히 아래와 일치시켜라:",
        "  " + ", ".join(output_fields),
        "  (키 이름 변경·추가·삭제 절대 금지)",
        f"  ※ 특히 출력 필드 {len(output_fields)}개를 모두 output_schema에 포함해야 한다 — 하나라도 누락 금지.",
    ]

    if formula is not None:
        formula_str = (json.dumps(formula, ensure_ascii=False)
                       if isinstance(formula, dict) else str(formula))
        lines += [
            "",
            "[고정 Formula] 아래 수식을 그대로 사용해야 한다:",
            f"  {formula_str}",
            "  (변수명·출력 키명·계산 구조 변경 금지)",
            "  (구현 불가 시 임의 수정 말고 생성 실패로 처리할 것)",
        ]

    if test_cases:
        lines += [
            "",
            f"[검증 케이스 {len(test_cases)}개] 아래 입력에 대해 expected 결과가 반드시 나와야 한다:",
        ]
        for tc in test_cases:
            lines.append(f"  입력 {tc.get('input')} → 예상 {tc.get('expected')}")
        lines.append("  (참고가 아니라 필수 통과 기준 — 이 값이 나오지 않으면 formula가 틀린 것이다)")

    lines += [
        "",
        "【핵심 규칙】",
        "1. input_schema 키는 위 고정 입력 필드와 완전히 일치해야 한다.",
        "2. output_schema 키는 위 고정 출력 필드와 완전히 일치해야 하며, 하나라도 빠뜨리면 오답이다.",
        "3. formula는 위에 명시된 것을 그대로 사용한다. 자체 재설계 금지.",
        "4. Contract는 협상 대상이 아니다 — 이 규칙을 어긴 응답은 계약 위반이다.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def generate_app(cfg: dict, name: str, category: str = "", desc: str = "", tier: int = 2,
                 _contract: dict = None) -> dict:
    """계산기 1종을 AI로 생성하여 dict 반환(저장은 save_app).

    _contract: Contract 기반 생성 시 내부적으로 전달되는 확정 스펙 dict.
               Mode A(자동 생성) 호출 시 전달하지 않음 — 기존 동작 그대로 유지.
               Mode B(generate_app_with_contract) 호출 시만 사용.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("계산기명을 입력하세요.")
    steps = []  # (단계, 모델, 토큰)

    # [0] 기존 계산기 목록 로드 — 사전 중복 확인 + GPT 컨텍스트
    try:
        existing = CalculatorRepository(get_db_adapter(cfg)).get_all()
    except Exception:
        existing = []

    # [0-A] 사전 중복 차단 — AI 호출 전, 이름 일치 시 즉시 중단 (AI 토큰 낭비 방지)
    _name_norm = re.sub(r"\s+", "", name).lower()
    for _c in existing:
        if re.sub(r"\s+", "", _c.get("name", "")).lower() == _name_norm:
            raise ValueError(
                f"이미 등록된 계산기와 이름이 동일합니다: '{_c.get('name')}'. "
                "AI 호출 없이 차단됩니다. 다른 이름을 사용하거나 기존 계산기를 검토하세요."
            )

    # [1] 기존 계산기 목록 요약(중복 회피 컨텍스트) — sys1에 주입
    existing_summary = "\n".join(
        f"- {c.get('name','')} ({c.get('category','')}): 입력항목 {list(_pj(c.get('input_schema'), {}).keys())}"
        for c in existing
    ) or "(없음)"

    # 1) 총괄(GPT): 스펙 설계 (입력/출력 스키마 + 산식)
    _tier_note = (
        "[Tier2 — 단순 산술/일반 공식] 복잡한 조건분기·날짜 계산 최소화. 수식으로 표현 가능한 계산 위주."
        if tier == 2 else
        "[Tier1 — 법령/조건분기/복잡 계산] 다단계 조건, 날짜 기반, 법령 규정 적용이 필요한 계산."
    )
    # Contract 기반 생성(Mode B)일 때 CONTRACT LOCK 섹션을 sys1에 삽입
    _contract_lock_section = (
        _build_contract_enforcement_prompt(_contract) + "\n\n"
    ) if _contract else ""

    sys1 = (
        f"너는 웹 계산기 기획자다. 주어진 계산기에 대해 입력/출력 스키마와 산식을 설계하라.\n"
        f"계산기 Tier: {_tier_note}\n"
        f"{_contract_lock_section}"
        "요구사항:\n"
        "1. formula 규칙:\n"
        "   - 단일 출력: input_schema 변수만 사용한 단일 산술 표현식(문자열).\n"
        "   - 복수 출력: {출력키: 산술식} JSON 객체. 각 식은 반드시 input_schema 변수만 사용.\n"
        "     (다른 출력키 참조 절대 금지. 예: net_income = gross * 0.967, gross - withholding 방식 금지)\n"
        "   대입문(=), 세미콜론(;), 함수 정의, 미정의 함수 호출 금지.\n"
        "   허용 함수: min, max, round, abs, int, float 만 사용 가능.\n"
        "2. input_schema/output_schema의 모든 키는 반드시 한국어 라벨을 'labels' 필드에 매핑하라 "
        '(예: {"monthly_salary": "월급"}).\n'
        "3. 반드시 아래 JSON 형식으로만 응답하라 — 설명문·거부 메시지 절대 금지:\n"
        '{"calculator_type":"","input_schema":{},"output_schema":{},"formula":"또는{}","labels":{}}\n'
        f"다음은 이미 등록된 계산기 목록이다:\n{existing_summary}\n"
        "위 목록을 참고해 겹치지 않는 스키마를 설계하라. "
        "어떠한 경우에도 위 JSON 형식으로만 응답하라."
    )
    u1 = f"계산기명: {name}\n카테고리: {category}\n설명: {desc}"
    t1, m1, k1 = _chat(cfg, "orchestrator", sys1, u1, 800)
    spec = parse_json_lenient(t1)
    steps.append(("총괄(스펙)", m1, k1))

    # [2] 저장 전 formula 검증 (실패 시 실패사유 알려주고 1회 재시도)
    from .formula_engine import validate_formula
    ok, msg = validate_formula(spec.get("formula", ""), spec.get("input_schema", {}))
    if not ok:
        retry_sys = sys1 + (f"\n\n[재설계] 직전 응답의 formula가 검증 실패했다(사유: {msg}). "
                            "요구사항(단일 산술 표현식 · input_schema 변수만 · 허용 함수만)을 반드시 지켜 다시 설계하라.")
        try:
            t1b, m1b, k1b = _chat(cfg, "orchestrator", retry_sys, u1, 800)
            steps.append(("총괄(재시도)", m1b, k1b))
            spec2 = parse_json_lenient(t1b)
            ok2, msg2 = validate_formula(spec2.get("formula", ""), spec2.get("input_schema", {}))
            if ok2:
                spec, ok, msg = spec2, ok2, msg2   # 유효하면 재시도 결과 채택
            else:
                ok, msg = ok2, msg2                # 여전히 실패 → 원 spec 유지, 검증결과만 갱신
        except Exception as e:
            msg = f"{msg} / 재시도 오류: {e}"
    spec["_formula_valid"] = ok
    spec["_formula_msg"] = msg

    # 2) 코드(Claude): 단일 자가완결 HTML (인라인 CSS/JS) — JSON 미사용(견고)
    sys2 = ("너는 프론트엔드 개발자다. 아래 스펙으로 동작하는 계산기를 "
            "단일 HTML 문서로 만들어라. <style>와 <script>를 인라인으로 포함하고, "
            "입력폼+계산버튼+결과영역을 갖춘다. 설명/마크다운 코드블록 없이 HTML 코드만 출력하라.")
    u2 = (f"계산기명: {name}\n"
          f"input_schema: {json.dumps(spec.get('input_schema', {}), ensure_ascii=False)}\n"
          f"output_schema: {json.dumps(spec.get('output_schema', {}), ensure_ascii=False)}\n"
          f"formula: {spec.get('formula','')}")
    t2, m2, k2 = _chat(cfg, "code", sys2, u2, 4000)
    code = {"html": _strip_fence(t2), "css": "", "js": ""}  # CSS/JS는 HTML에 인라인
    steps.append(("코드(HTML)", m2, k2))

    # 3) 작성(GPT): SEO + FAQ + 블로그 초안
    sys3 = ("너는 SEO 카피라이터다. 아래 계산기에 대한 SEO와 FAQ, 블로그 초안을 작성하라. "
            "순수 JSON만 반환: "
            '{"seo_title":"","seo_desc":"","faq":[{"q":"","a":""}],"blog_draft":""}')
    u3 = f"계산기명: {name}\n카테고리: {category}\n설명: {desc}"
    t3, m3, k3 = _chat(cfg, "writer", sys3, u3, 1500)
    seo = parse_json_lenient(t3)
    steps.append(("작성(SEO/FAQ/초안)", m3, k3))

    # 4) 이미지(Gemini): 이미지 프롬프트
    sys4 = ("너는 이미지 프롬프트 디자이너다. 썸네일/본문용 영문 이미지 프롬프트를 만들어라. "
            "순수 JSON만 반환: {\"image_prompt_thumbnail\":\"\",\"image_prompt_body\":\"\"}")
    try:
        t4, m4, k4 = _chat(cfg, "image", sys4, f"계산기: {name} ({category})", 400)
        imgp = parse_json_lenient(t4)
        steps.append(("이미지 프롬프트", m4, k4))
    except Exception as e:
        LOG.warning("이미지 프롬프트 생성 실패(무시): %s", e)
        imgp = {"image_prompt_thumbnail": "", "image_prompt_body": ""}

    return {
        "name": name, "category": category, "description": desc,
        "calculator_type": spec.get("calculator_type", "general"),
        "input_schema": spec.get("input_schema", {}),
        "output_schema": spec.get("output_schema", {}),
        "formula": spec.get("formula", ""),
        "labels": spec.get("labels", {}),
        "html": code.get("html", ""), "css": code.get("css", ""), "js": code.get("js", ""),
        "seo_title": seo.get("seo_title", ""), "seo_desc": seo.get("seo_desc", ""),
        "faq": seo.get("faq", []), "blog_draft": seo.get("blog_draft", ""),
        "image_prompt_thumbnail": imgp.get("image_prompt_thumbnail", ""),
        "image_prompt_body": imgp.get("image_prompt_body", ""),
        "_formula_valid": spec.get("_formula_valid", True),
        "_formula_msg": spec.get("_formula_msg", ""),
        "_steps": steps,
        "_tokens": sum(s[2] for s in steps),
        "tier": tier,
    }


def suggest_idea(cfg: dict, keyword: str = "") -> dict:
    """기존 계산기 목록을 참고해 AI가 새 계산기 아이디어(이름/카테고리/설명)를 제안.
    keyword가 주어지면 그 키워드를 중심으로 구체화, 없으면 자유 제안."""
    try:
        existing = CalculatorRepository(get_db_adapter(cfg)).get_all()
    except Exception:
        existing = []
    existing_summary = "\n".join(
        f"- {c.get('name','')} ({c.get('category','')})" for c in existing
    ) or "(없음)"
    keyword = (keyword or "").strip()
    keyword_line = (
        f"\n사용자가 준 키워드: \"{keyword}\" — 이 키워드를 중심으로 "
        "계산기 아이디어를 구체화하라." if keyword else
        "\n키워드가 주어지지 않았으므로 자유롭게 새 아이디어를 제안하라."
    )
    sys0 = (
        "너는 대한민국 노무/급여/세금/정부혜택 분야 웹 계산기 기획자다. "
        "아래는 이미 존재하는 계산기 목록이다:\n" + existing_summary + "\n"
        "이 목록과 겹치지 않는 새로운 실용적인 계산기 아이디어 1개를 제안하라. "
        "직장인이 실제로 검색할 만한 주제로 한정한다."
        + keyword_line +
        "\n순수 JSON만 반환: {\"name\":\"\",\"category\":\"\",\"desc\":\"\"}"
    )
    # 기존 sys1과 동일 provider/모델(orchestrator) 재사용
    text, _m, _k = _chat(cfg, "orchestrator", sys0, "새 계산기 아이디어 1개를 제안하라.", 400)
    d = parse_json_lenient(text)
    return {"name": d.get("name", ""), "category": d.get("category", ""), "desc": d.get("desc", "")}


def _infer_registry_meta(input_schema: dict, output_schema: dict, formula) -> tuple:
    """registry 자동추론(작업지시서 E §3): (date_fields, compute_type, validation_mode, difficulty).
    - date_fields: input_schema 값에 'date' 포함하는 키(app_generator의 date 판정과 동일 기준)
    - compute_type: date 필드 있으면 date_based / formula가 dict거나 출력 2+면 dict / 그 외 single
    - validation_mode: date_based면 skip(날짜 코드계산, formula 미사용), 아니면 formula
    - difficulty: date_based→date_based / dict→multi_output / 그 외 simple
    ※ compute_type의 single/dict는 현재 코드가 소비 안 함(date_based만 소비) — 추론 오차 리스크 낮음."""
    ins = input_schema or {}
    outs = output_schema or {}
    date_fields = [k for k, v in ins.items() if "date" in str(v).lower()]
    if date_fields:
        compute_type = "date_based"
    elif isinstance(formula, dict) or len(outs) >= 2:
        compute_type = "dict"
    else:
        compute_type = "single"
    validation_mode = "skip" if compute_type == "date_based" else "formula"
    difficulty = {"date_based": "date_based", "dict": "multi_output"}.get(compute_type, "simple")
    return date_fields, compute_type, validation_mode, difficulty


def _build_registry_entry(app: dict, slug: str) -> dict:
    """save_app이 registry_auto.yaml에 쓸 자동 엔트리(작업지시서 E §3).
    identity/compute/labels/meta는 자동, legal 전체는 null(사람이 나중에 채움), needs_human_legal=true."""
    ins = app.get("input_schema", {}) or {}
    outs = app.get("output_schema", {}) or {}
    date_fields, compute_type, validation_mode, difficulty = _infer_registry_meta(
        ins, outs, app.get("formula", ""))
    name = app.get("name", "")
    entry = {
        "slug": slug,
        "name": name,
        "category": app.get("category", ""),
        "emoji": "🧮",
        "card_label": name,
        "compute_type": compute_type,
        "date_fields": date_fields,
        "validation_mode": validation_mode,
        "field_labels": app.get("labels", {}) or {},
        "difficulty": difficulty,
        "difficulty_status": "provisional",
        "needs_human_legal": True,
        # legal — 전부 null/빈값(사람이 legal_basis.draft.yaml로 승격하며 채움)
        "law": None, "article": None, "authority": None,
        "related_articles": [],
        "writer_note": None,
        "reviewer_expectation": [],
        "forbidden_articles": [],
        "forbidden_phrases": [],
        "confidence": None,
        "last_verified": None,
        "verification_source": [],
        "content": {"evergreen": None, "update_cycle": None},
        "related_slugs": [],
    }
    if app.get("compute_rules"):
        entry["compute_rules"] = app["compute_rules"]
    return entry


_CALC_INDEX_PATH = Path(__file__).resolve().parent.parent / "docs" / "calculator_index.json"


def _write_calculator_index(cfg: dict) -> None:
    """slug ↔ 한글 name 매핑을 docs/calculator_index.json에 전량 재생성(개발 편의용 인덱스).
    ※ 순수 참조 문서 — 기존 로직(registry/파이프라인/UI)은 이 파일을 읽지 않는다.
       slug=내부식별자(폴더/URL), name=화면표시(한글)의 대응을 한눈에 보기 위한 것."""
    repo = CalculatorRepository(get_db_adapter(cfg))
    idx = {}
    for c in repo.get_all():
        s = str(c.get("slug", "")).strip()
        if s:
            idx[s] = {"name": c.get("name", ""), "category": c.get("category", "")}
    _CALC_INDEX_PATH.write_text(
        json.dumps(idx, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _update_contract_registry(calc_slug: str, contract: dict, generated_at: str) -> None:
    """docs/contract_schema/registry.yaml에 calc_slug 항목 추가/갱신."""
    import yaml
    registry_path = _SCHEMA_DIR / "registry.yaml"
    if registry_path.exists():
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    instances = data.get("instances") or {}
    instances[calc_slug] = {
        "contract_slug":      contract.get("slug", calc_slug),
        "generated_at":       generated_at,
        "formula_status":     contract.get("formula_status", "not_generated"),
        "test_cases_status":  contract.get("test_cases_status", "not_generated"),
    }
    data["instances"] = instances
    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _save_contract_instance(calc_slug: str, contract: dict) -> None:
    """Contract 전체를 docs/contract_schema/instances/{calc_slug}.yaml에 영속화.

    calc_slug : 계산기 slug (Registry v3 key, 파일 인덱스 기준)
    contract  : build_contract() 반환 dict. None/빈 dict이면 noop.
    저장 순서: instances/ 파일 → registry.yaml 인덱스 갱신.
    실패 시 예외를 발생시킨다 — 호출자(save_app)가 LOG.warning으로 처리.
    """
    import yaml
    from datetime import timezone, timedelta
    if not contract:
        return
    KST = timezone(timedelta(hours=9))
    generated_at = datetime.now(KST).isoformat()
    instance = dict(contract)
    instance["generated_at"] = generated_at
    instances_dir = _SCHEMA_DIR / "instances"
    instances_dir.mkdir(parents=True, exist_ok=True)
    instance_path = instances_dir / f"{calc_slug}.yaml"
    with open(instance_path, "w", encoding="utf-8") as f:
        yaml.dump(instance, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    _update_contract_registry(calc_slug, contract, generated_at)
    LOG.info("Contract Instance 저장 완료: %s → %s", calc_slug, instance_path)


def _delete_contract_instance(calc_slug: str) -> bool:
    """Contract Instance를 docs/contract_schema/instances/{calc_slug}.yaml에서 삭제.

    파일이 없으면 조용히 False 반환(오류 없음).
    registry.yaml 항목도 함께 제거.
    반환: True=파일이 존재해 삭제됨, False=파일 없었음.
    """
    import yaml
    instance_path = _SCHEMA_DIR / "instances" / f"{calc_slug}.yaml"
    existed = instance_path.exists()
    if existed:
        instance_path.unlink()
        LOG.info("Contract Instance 파일 삭제: %s", instance_path)
    registry_path = _SCHEMA_DIR / "registry.yaml"
    if registry_path.exists():
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        instances = data.get("instances") or {}
        if calc_slug in instances:
            del instances[calc_slug]
            data["instances"] = instances
            with open(registry_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            LOG.info("Contract Registry 항목 제거: %s", calc_slug)
    return existed


def save_app(cfg: dict, app: dict, site_id: str = "", slug: str = None) -> tuple:
    """생성 결과를 calculators + app_templates 시트에 저장(Repository 경유).
    slug: 신규 계산기의 영문 식별자(폴더/URL/내부참조). 미지정 시 _slug(name)로 폴백(하위호환).
    ※ 기존 계산기 slug는 절대 변경하지 않음 — 이 함수는 '신규 저장' 경로에만 관여."""
    db = get_db_adapter(cfg)
    calc_repo = CalculatorRepository(db)
    tpl_repo = TemplateRepository(db)
    name = app.get("name", "")
    new_slug = (slug or "").strip().lower() or _slug(name)   # 명시 영문 slug 우선, 없으면 기존 방식
    try:
        _all = calc_repo.get_all()
        # 중복 체크(이름)
        if any(str(c.get("name", "")).strip().lower() == name.lower() for c in _all):
            return False, f"중복 계산기명: '{name}' 이미 등록됨"
        # 중복 체크(slug) — DB + v3 Registry 모두 확인(기존 8개 포함)
        if any(str(c.get("slug", "")).strip().lower() == new_slug for c in _all):
            return False, f"중복 슬러그: '{new_slug}' 이미 등록됨 (DB)"
    except Exception as e:
        return False, f"기존 계산기 조회 실패(시트 권한 확인): {e}"
    try:
        from .registry_loader import load_registry_v3
        if new_slug in load_registry_v3(force=True):
            return False, f"중복 슬러그: '{new_slug}' 이미 v3 Registry에 존재"
    except Exception:
        pass

    try:
        # 템플릿 먼저 저장 → template_id 확보
        tpl_id = tpl_repo.save({
            "template_name": f"{name} 템플릿",
            "template_type": app.get("calculator_type", "general"),
            "html_template": app.get("html", ""),
            "seo_template": json.dumps(
                {"seo_title": app.get("seo_title", ""), "seo_desc": app.get("seo_desc", ""),
                 "css": app.get("css", ""), "js": app.get("js", "")}, ensure_ascii=False),
            "faq_template": json.dumps(app.get("faq", []), ensure_ascii=False),
            "status": "active",
        })
        _formula = app.get("formula", "")
        _formula_stored = (json.dumps(_formula, ensure_ascii=False)
                           if isinstance(_formula, dict) else (_formula or ""))
        calc_repo.save({
            "name": name, "slug": new_slug, "category": app.get("category", ""),
            "calculator_type": app.get("calculator_type", "general"),
            "template_id": tpl_id, "site_id": site_id,
            "formula": _formula_stored,
            "labels": json.dumps(app.get("labels", {}), ensure_ascii=False),
            "faq": json.dumps(app.get("faq", []), ensure_ascii=False),
            "input_schema": json.dumps(app.get("input_schema", {}), ensure_ascii=False),
            "output_schema": json.dumps(app.get("output_schema", {}), ensure_ascii=False),
            "seo_title": app.get("seo_title", ""), "seo_desc": app.get("seo_desc", ""),
            "status": "active",
        })
    except Exception as e:
        return False, f"저장 실패(시트 권한 확인): {e}"
    # [Step A] registry_auto.yaml — 스테이징 레이어(기존 경로 유지)
    _v3_warn = ""
    try:
        from .registry_loader import add_auto_entry
        add_auto_entry(new_slug, _build_registry_entry(app, new_slug))
        LOG.info("registry_auto 엔트리 기록(스테이징): %s", new_slug)
    except Exception as _re:
        LOG.warning("registry_auto 기록 실패(무시): %s", _re)
    # [Step B] v3 Registry 즉시 기록 — 프로덕션 SSOT(Plan A: save_app() 즉시)
    # 실패해도 계산기 DB 저장은 유효(경고 반환)
    try:
        _tier = app.get("tier", 2)
        _v3_entry = _build_v3_entry(app, new_slug, tier=_tier, contract=app.get("_contract"))
        _write_registry_v3(new_slug, _v3_entry, app.get("category", ""))
        LOG.info("v3 Registry 기록(HOLD): %s", new_slug)
    except Exception as _v3e:
        _v3_warn = f" ⚠️ v3 Registry 기록 실패({_v3e}) — 사이트 관리 탭에서 수동 확인 필요"
        LOG.warning("v3 Registry 기록 실패(계산기 저장은 완료됨): %s", _v3e)
    # [Step B'] Contract Instance 영속화 (Mode B만 해당, Registry 성공 시)
    # Registry 실패(_v3_warn 있음) 시 Contract Instance도 저장하지 않아 고아 파일 방지.
    if not _v3_warn and app.get("_contract"):
        try:
            _save_contract_instance(new_slug, app["_contract"])
        except Exception as _cie:
            LOG.warning("Contract Instance 저장 실패(무시): %s", _cie)
    # calculator_index.json 갱신(개발 편의용)
    try:
        _write_calculator_index(cfg)
    except Exception as _ie:
        LOG.warning("calculator_index 갱신 실패(무시): %s", _ie)
    LOG.info("App Factory 저장 완료: %s (tpl=%s)", name, tpl_id)
    _msg = f"✅ '{name}' 계산기 + 템플릿 저장 완료 (template_id={tpl_id})"
    _msg += " | v3 Registry HOLD 등록 완료. legal 검증 후 READY 전환 필요." if not _v3_warn else _v3_warn
    # [Step C] 검토 체크리스트 자동 추출 + _af.yaml에 저장
    if not _v3_warn:
        try:
            from modules.review_center import extract_checklist
            _tier_str = f"Tier{_tier}-A" if _tier == 2 else "Tier1"
            _checklist = extract_checklist(app, tier=_tier_str, category=app.get("category", ""))
            save_af_checklist(new_slug, _checklist)
            LOG.info("검토 체크리스트 저장 완료: %s (%d 항목)", new_slug, len(_checklist))
        except Exception as _ce:
            LOG.warning("체크리스트 저장 실패(무시): %s", _ce)
    return True, _msg


def delete_app(cfg: dict, slug: str) -> tuple[bool, str]:
    """App Factory 계산기 전체 삭제 (테스트 정리용).
    삭제 대상: calculators + app_templates (DB), registry_auto.yaml, _af.yaml v3 Registry.
    기존 8개 계산기(source != app_factory) 보호 — v3에 있는데 source가 app_factory가 아니면 거부."""
    from .registry_loader import load_registry_v3, invalidate, remove_auto_entry

    v3 = load_registry_v3(force=True)
    entry_v3 = v3.get(slug)
    if entry_v3 is not None and entry_v3.get("source") != "app_factory":
        return False, f"'{slug}'은 App Factory 계산기가 아닙니다(source={entry_v3.get('source')!r}) — 삭제 거부"

    db = get_db_adapter(cfg)
    calc_repo = CalculatorRepository(db)

    rows = db.get_where("calculators", {"slug": slug})
    if not rows:
        return False, f"calculators에서 '{slug}' 조회 실패 — 이미 삭제됐거나 존재하지 않음"

    row = rows[0]
    calc_id = row.get("id")
    tpl_id = row.get("template_id")
    category = row.get("category", "")

    if tpl_id:
        try:
            db.delete("app_templates", tpl_id)
            LOG.info("app_templates 삭제 완료: %s", tpl_id)
        except Exception as e:
            LOG.warning("app_templates 삭제 실패(계속 진행): %s", e)

    try:
        calc_repo.delete(calc_id)
        LOG.info("calculators 삭제 완료: %s (%s)", slug, calc_id)
    except Exception as e:
        return False, f"calculators 삭제 실패: {e}"

    try:
        removed = remove_auto_entry(slug)
        LOG.info("registry_auto 엔트리 제거: %s (%s)", slug, "제거됨" if removed else "없었음")
    except Exception as e:
        LOG.warning("registry_auto 엔트리 제거 실패(계속 진행): %s", e)

    try:
        _cat = entry_v3.get("category", category) if entry_v3 else category
        removed_v3 = _delete_from_registry_v3(slug, _cat)
        LOG.info("v3 Registry 엔트리 제거: %s (%s)", slug, "제거됨" if removed_v3 else "없었음")
    except Exception as e:
        LOG.warning("v3 Registry 엔트리 제거 실패(계속 진행): %s", e)

    # Contract Instance 정리 (없으면 조용히 종료 — delete_app() 성공/실패에 영향 없음)
    try:
        _delete_contract_instance(slug)
    except Exception as e:
        LOG.warning("Contract Instance 정리 실패(계속 진행): %s", e)

    try:
        _write_calculator_index(cfg)
    except Exception as e:
        LOG.warning("calculator_index 재생성 실패(무시): %s", e)

    invalidate()
    LOG.info("App Factory 계산기 삭제 완료: %s (calc_id=%s, tpl_id=%s)", slug, calc_id, tpl_id)
    return True, f"✅ '{slug}' 삭제 완료 (calc_id={calc_id}, tpl_id={tpl_id})"


def get_af_checklist(slug: str) -> list[dict]:
    """Registry v3에서 slug의 review_checklist 반환. 없으면 []."""
    from .registry_loader import load_registry_v3
    v3 = load_registry_v3(force=True)
    entry = v3.get(slug, {})
    return list(entry.get("review_checklist", []) or [])


def save_af_checklist(slug: str, checklist: list[dict]) -> None:
    """_af.yaml에서 slug 엔트리의 review_checklist를 갱신."""
    import yaml
    from .registry_loader import load_registry_v3, invalidate

    v3 = load_registry_v3(force=True)
    entry = v3.get(slug)
    if entry is None or entry.get("source") != "app_factory":
        raise ValueError(f"'{slug}'은 App Factory 계산기가 아니거나 존재하지 않음")

    category = entry.get("category", "")
    yaml_name = _category_to_af_yaml(category)
    yaml_file = _REG_DIR / f"{yaml_name}.yaml"

    try:
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise RuntimeError(f"Registry 파일 읽기 실패: {e}")

    if not isinstance(data, dict) or slug not in data:
        raise ValueError(f"'{slug}'이 {yaml_file.name}에 없음")

    data[slug]["review_checklist"] = checklist
    _AF_HEADER = (
        f"# registry/{yaml_name}.yaml — App Factory 자동생성 계산기 (v3 SSOT)\n"
        "# ⚠️ 이 파일은 App Factory(modules/app_factory)가 자동으로 씁니다. 직접 편집 주의.\n"
        "# status: HOLD = legal 검증 대기 중 (index/sitemap 비노출)\n"
        "# status: READY = 공개 (index/sitemap 포함, CalcMate 정적 사이트 빌드 대상)\n"
    )
    body = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    yaml_file.write_text(_AF_HEADER + "\n" + body, encoding="utf-8")
    invalidate()
    LOG.info("체크리스트 갱신: %s", slug)
