# -*- coding: utf-8 -*-
"""
modules/app_factory.py — 계산기 자동 생성 (v12.0)

흐름: GPT(총괄 spec) → Claude(코드 HTML/CSS/JS) → GPT(SEO/FAQ/블로그초안)
      → Gemini(이미지 프롬프트) → calculators + app_templates 저장

모든 AI 호출은 ai_roles(=ai_provider) 경유, 데이터 저장은 Repository 경유.
gspread/Drive 직접 호출 없음.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.template_repository import TemplateRepository
from .ai_roles import make_provider
from .json_utils import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()


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


def generate_app(cfg: dict, name: str, category: str = "", desc: str = "") -> dict:
    """계산기 1종을 AI로 생성하여 dict 반환(저장은 save_app)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("계산기명을 입력하세요.")
    steps = []  # (단계, 모델, 토큰)

    # [1] 기존 계산기 목록 요약(중복 회피 컨텍스트) — sys1에 주입
    try:
        existing = CalculatorRepository(get_db_adapter(cfg)).get_all()
    except Exception:
        existing = []
    existing_summary = "\n".join(
        f"- {c.get('name','')} ({c.get('category','')}): 입력항목 {list(_pj(c.get('input_schema'), {}).keys())}"
        for c in existing
    ) or "(없음)"

    # 1) 총괄(GPT): 스펙 설계 (입력/출력 스키마 + 산식)
    sys1 = (
        "너는 웹 계산기 기획자다. 주어진 계산기에 대해 입력/출력 스키마와 산식을 설계하라.\n"
        "요구사항:\n"
        "1. formula는 반드시 input_schema의 변수명만 사용한 '단일 산술 표현식'이어야 한다. "
        "대입문(=), 세미콜론(;), 함수 정의, 정의되지 않은 함수 호출 금지. "
        "허용 함수: min, max, round, abs, int, float 만 사용 가능. "
        "여러 단계 계산이 필요하면 하나의 표현식 안에 괄호로 중첩해서 표현하라.\n"
        "2. input_schema/output_schema의 모든 키는 반드시 한국어 라벨을 'labels' 필드에 매핑하라 "
        '(예: {"monthly_salary": "월급"}).\n'
        "3. 순수 JSON만 반환: "
        '{"calculator_type":"","input_schema":{},"output_schema":{},"formula":"","labels":{}}\n'
        f"다음은 이미 등록된 계산기 목록이다:\n{existing_summary}\n"
        "위 목록과 기능·입력항목이 실질적으로 겹치지 않도록 설계하라."
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
    return {
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
        # 중복 체크(slug) — 기존 '저장된 slug'와 비교(배포 폴더/링크 충돌 방지)
        if any(str(c.get("slug", "")).strip().lower() == new_slug for c in _all):
            return False, f"중복 슬러그: '{new_slug}' 이미 등록됨"
    except Exception as e:
        return False, f"기존 계산기 조회 실패(시트 권한 확인): {e}"

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
        calc_repo.save({
            "name": name, "slug": new_slug, "category": app.get("category", ""),
            "calculator_type": app.get("calculator_type", "general"),
            "template_id": tpl_id, "site_id": site_id,
            "formula": app.get("formula", ""),
            "labels": json.dumps(app.get("labels", {}), ensure_ascii=False),
            "faq": json.dumps(app.get("faq", []), ensure_ascii=False),
            "input_schema": json.dumps(app.get("input_schema", {}), ensure_ascii=False),
            "output_schema": json.dumps(app.get("output_schema", {}), ensure_ascii=False),
            "seo_title": app.get("seo_title", ""), "seo_desc": app.get("seo_desc", ""),
            "status": "active",
        })
    except Exception as e:
        return False, f"저장 실패(시트 권한 확인): {e}"
    # registry_auto.yaml에 자동 엔트리 기록(§3) — 실패해도 계산기 저장 자체는 유효(경고만).
    try:
        from .registry_loader import add_auto_entry
        add_auto_entry(new_slug, _build_registry_entry(app, new_slug))
        LOG.info("registry_auto 엔트리 기록: %s", new_slug)
    except Exception as _re:
        LOG.warning("registry_auto 기록 실패(무시, 계산기 저장은 완료됨): %s", _re)
    # calculator_index.json 갱신(slug↔한글 name 매핑, 개발 편의용 — 기존 로직은 이 파일을 읽지 않음).
    try:
        _write_calculator_index(cfg)
    except Exception as _ie:
        LOG.warning("calculator_index 갱신 실패(무시): %s", _ie)
    LOG.info("App Factory 저장 완료: %s (tpl=%s)", name, tpl_id)
    return True, f"✅ '{name}' 계산기 + 템플릿 저장 완료 (template_id={tpl_id})"
