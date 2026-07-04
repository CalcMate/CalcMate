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
    sys1 = ("너는 웹 계산기 기획자다. 주어진 계산기에 대해 입력/출력 스키마와 산식을 설계하라. "
            "순수 JSON만 반환: "
            '{"calculator_type":"","input_schema":{},"output_schema":{},"formula":""}\n'
            f"다음은 이미 등록된 계산기 목록이다:\n{existing_summary}\n"
            "위 목록과 기능·입력항목이 실질적으로 겹치지 않도록 설계하라. "
            "겹칠 경우 차별화된 입력/출력 스키마를 사용하라.")
    u1 = f"계산기명: {name}\n카테고리: {category}\n설명: {desc}"
    t1, m1, k1 = _chat(cfg, "orchestrator", sys1, u1, 800)
    spec = parse_json_lenient(t1)
    steps.append(("총괄(스펙)", m1, k1))

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
        "html": code.get("html", ""), "css": code.get("css", ""), "js": code.get("js", ""),
        "seo_title": seo.get("seo_title", ""), "seo_desc": seo.get("seo_desc", ""),
        "faq": seo.get("faq", []), "blog_draft": seo.get("blog_draft", ""),
        "image_prompt_thumbnail": imgp.get("image_prompt_thumbnail", ""),
        "image_prompt_body": imgp.get("image_prompt_body", ""),
        "_steps": steps,
        "_tokens": sum(s[2] for s in steps),
    }


def save_app(cfg: dict, app: dict, site_id: str = "") -> tuple:
    """생성 결과를 calculators + app_templates 시트에 저장(Repository 경유)."""
    db = get_db_adapter(cfg)
    calc_repo = CalculatorRepository(db)
    tpl_repo = TemplateRepository(db)
    name = app.get("name", "")
    try:
        _all = calc_repo.get_all()
        # 중복 체크(이름)
        if any(str(c.get("name", "")).strip().lower() == name.lower() for c in _all):
            return False, f"중복 계산기명: '{name}' 이미 등록됨"
        # 중복 체크(slug) — 이름은 달라도 slug가 겹치면 차단(배포 폴더/링크 충돌 방지)
        new_slug = _slug(name)
        if any(_slug(str(c.get("name", ""))) == new_slug for c in _all):
            return False, f"중복 슬러그: '{new_slug}' 이미 등록됨 (이름은 다르지만 slug 충돌)"
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
            "name": name, "slug": _slug(name), "category": app.get("category", ""),
            "calculator_type": app.get("calculator_type", "general"),
            "template_id": tpl_id, "site_id": site_id,
            "formula": app.get("formula", ""),
            "faq": json.dumps(app.get("faq", []), ensure_ascii=False),
            "input_schema": json.dumps(app.get("input_schema", {}), ensure_ascii=False),
            "output_schema": json.dumps(app.get("output_schema", {}), ensure_ascii=False),
            "seo_title": app.get("seo_title", ""), "seo_desc": app.get("seo_desc", ""),
            "status": "active",
        })
    except Exception as e:
        return False, f"저장 실패(시트 권한 확인): {e}"
    LOG.info("App Factory 저장 완료: %s (tpl=%s)", name, tpl_id)
    return True, f"✅ '{name}' 계산기 + 템플릿 저장 완료 (template_id={tpl_id})"
