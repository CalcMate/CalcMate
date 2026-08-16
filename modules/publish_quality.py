# -*- coding: utf-8 -*-
"""
modules/publish_quality.py — 발행 글 품질 검수 (Gate → Score → Rewrite Contract)

기준: docs/QUALITY_STANDARD_V1.2.md. calculator_reviewer(계산기 앱 자체 품질, 7-DIMENSIONS)와는
**완전히 별개 시스템** — 이쪽은 calculator_pipeline이 조립한 '발행 글(article)'의 품질을 본다.

- 자동 Gate(G1~G7): 코드 결정론 판정. GPT 호출 이전 필터.
  · body_html(writer 초안) 기준: G1 길이 / G2 H2 / G3 FAQ / G4 예시 / G7 AI문체
  · final_html(파이프라인 조립본) 기준: G5 내부링크·href="#" / G6 CTA (조립 단계에서만 존재)
- AI Score(S1~S6): Gate 통과 후에만 GPT 채점.
- 반환: Rewrite Contract(§9). G6(CTA 중복)은 코드수정으로 즉시 제거 후 재검사.

WordPress/AI 호출 규칙: 이 모듈은 WP REST를 호출하지 않는다. GPT는 CALC_REVIEW_PROVIDER/MODEL 공유.
"""
import re
import html as _html
from datetime import datetime

from .ai_provider import build_provider
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()

# CTA 마커(파이프라인이 조립하는 "계산기 사용하기" 섹션). 파이프라인과 결합 피하려 상수로 둔다.
_CTA_HEADING_RE = re.compile(r'<h2[^>]*>\s*계산기 사용하기\s*</h2>', re.I)
_CTA_BLOCK_RE = re.compile(r'(?:<hr\s*/?>\s*)?<h2[^>]*>\s*계산기 사용하기\s*</h2>\s*<p>.*?</p>', re.I | re.S)

# §5 AI 문체 금지표현 기본값(config AI_STYLE_BLOCKLIST로 오버라이드 가능).
DEFAULT_AI_STYLE_BLOCKLIST = [
    "알아보겠습니다", "알아보도록 하겠습니다", "살펴보겠습니다",
    "완벽하게 이해", "이해하셨을 것입니다",
    "다양한 조건에 따라 달라질 수 있습니다",
]


# ── 파싱 유틸(bs4 미사용, 표준 re) ────────────────────────────────
def _plain_text(html: str) -> str:
    """HTML → 가시 텍스트. script/style 제거 후 태그 제거·엔티티 복원·공백 정규화."""
    if not html:
        return ""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _count_h2(html: str) -> int:
    return len(re.findall(r"<h2\b", html or "", re.I))


def _count_faq(html: str) -> int:
    """FAQ 문항 수. writer FAQ는 <dl><dt>질문</dt><dd>답</dd> 형식 → <dt> 개수.
    <dt>가 없으면 FAQ 카드 내 <summary>/질문 항목 폴백."""
    n = len(re.findall(r"<dt\b", html or "", re.I))
    if n:
        return n
    return len(re.findall(r"<summary\b", html or "", re.I))


def _count_examples(html: str) -> int:
    """계산 예시 개수(존재 여부 판정용 휴리스틱 — 품질은 S1이 판정).
    '예를 들어/예시/가정하면' 도입부 또는 '= 10,000원'/'= 50만원' 형태 계산식 등장 횟수.
    두 번째 예시 표현("또 다른 예시/예로", "두 번째 예시")과 한국어 단위형(만/억/천원)도 인식.
    마커 패턴은 예[시로] 필수 후치로 '예외/예방' 등 비예시 단어 오탐을 차단한다."""
    text = _plain_text(html)
    markers = re.findall(
        r"예를\s*들어|예시로|가정하(?:면|여|고)|계산해\s*보면"
        r"|또\s*다른\s*예[시로]|두\s*번째\s*예시",
        text
    )
    numeric = re.findall(
        r"=\s*[\d,]+\s*(?:만|억|천)?\s*원|[\d,]+\s*(?:만|억|천)?\s*원\s*[×xX*]",
        text
    )
    return len(markers) + len(numeric)


def _count_dead_links(html: str) -> int:
    return len(re.findall(r'href\s*=\s*"#"', html or "", re.I))


def _count_internal_links(html: str) -> int:
    """internal_link_engine 블록(<div class="internal-links">) 안의 유효 앵커 수.
    블록이 없으면 0. href="#"/빈 href는 제외(엔진이 이미 생략하지만 방어적으로)."""
    m = re.search(r'<div[^>]*class="[^"]*internal-links[^"]*"[^>]*>(.*?)</div>', html or "", re.I | re.S)
    if not m:
        return 0
    block = m.group(1)
    return len(re.findall(r'<a\s+[^>]*href\s*=\s*"(?!#|\s*")[^"]+"', block, re.I))


def _count_cta(html: str) -> int:
    """CTA(계산기 사용하기 섹션) 등장 횟수 = <h2>계산기 사용하기</h2> 개수."""
    return len(_CTA_HEADING_RE.findall(html or ""))


def _dedupe_cta(html: str, keep: int = 1) -> tuple:
    """CTA 블록이 keep개를 초과하면 초과분(헤딩+문단) 제거. (fixed_html, removed_count)."""
    blocks = list(_CTA_BLOCK_RE.finditer(html or ""))
    if len(blocks) <= keep:
        return html, 0
    removed = 0
    # 뒤에서부터 제거해 인덱스 밀림 방지
    out = html
    for m in reversed(blocks[keep:]):
        out = out[:m.start()] + out[m.end():]
        removed += 1
    return out, removed


def _match_ai_style_blocklist(text: str, cfg: dict) -> list:
    patterns = (cfg or {}).get("AI_STYLE_BLOCKLIST") or DEFAULT_AI_STYLE_BLOCKLIST
    return [p for p in patterns if p and p in text]


# ── Gate 판정 ─────────────────────────────────────────────────────
# 등급(§12): Critical=즉시조치, Major=부분/전체재생성, Minor=WARN 감점.
_GATE_GRADE = {"G1": "major", "G2": "major", "G3": "major", "G4": "major",
               "G5": "critical", "G6": "critical", "G7": "minor",
               "A1": "major", "A2": "critical", "A3": "major", "A4": "major"}

# A-1: 프롬프트 내부 지시어 헤딩 — CTA/행동유도/할인혜택/계산기연결
_A1_LABEL_H_RE = re.compile(
    r'<h[23][^>]*>\s*(?:\d+[\.\)]\s*)?'
    r'(?:CTA|행동\s*유도(?:\s*\(CTA\))?|할인\s*혜택|계산기\s*연결)'
    r'\s*</h[23]>',
    re.I
)
# A-1: 번호 prefix가 붙은 H2/H3
_A1_NUMBERED_H_RE = re.compile(r'<h[23][^>]*>\s*\d+[\.\)]\s+', re.I)

# A-3: SalaryMate에 실제 존재하는 계산기 slug SSOT (DB calculators 테이블과 동기화).
_VALID_CALC_SLUGS = frozenset({
    "annual-leave-allowance", "annual-leave-remaining",
    "four-insurances", "freelancer-tax-3p3", "jeonse-vs-monthly",
    "military-discharge-date", "severance-pay", "unemployment-benefit",
    "weekly-holiday-allowance",
    "연말정산_환급액_계산기", "육아휴직_급여_계산기",
})
_A3_CALC_LINK_RE = re.compile(
    r'href\s*=\s*"[^"]*?/calculator/([^/"]+)"', re.I
)

# A-4: 미채워진 플레이스홀더 — data-ph 속성 또는 {{...}}
_A4_PH_RE = re.compile(r'data-ph="|{{[^}]+}}')


def _count_prompt_artifacts(html: str) -> int:
    """A1: 프롬프트 지시어가 H2/H3 제목으로 노출된 개수(번호 prefix 포함)."""
    n = len(_A1_LABEL_H_RE.findall(html or ""))
    n += len(_A1_NUMBERED_H_RE.findall(html or ""))
    return n


def _count_hallucinated_calc_links(html: str) -> list:
    """A3: SSOT 외 계산기 slug 링크 목록. 빈 리스트=통과."""
    bad = []
    for m in _A3_CALC_LINK_RE.finditer(html or ""):
        slug = m.group(1)
        if slug not in _VALID_CALC_SLUGS:
            bad.append(slug)
    return bad


def _count_placeholders(html: str) -> int:
    """A4: 미채워진 data-ph 속성 또는 {{...}} 플레이스홀더 개수."""
    return len(_A4_PH_RE.findall(html or ""))


_G1_MIN_BY_INTENT = {
    "howto":       1750,
    "documents":   1850,
    "eligibility": 2000,
    "calculator":  1850,
}


def check_gates(body_html: str, final_html: str, cfg: dict, link_pool_size: int = 0,
                intent: str = None, has_verified: bool = False) -> tuple:
    """(passed: bool, failed_gates: list[dict]). 각 항목: {gate, detail, grade, ...}.
    body 기준 게이트는 body_html, 조립 기준 게이트(G5/G6)는 final_html을 본다.
    link_pool_size: inject_internal_links에 전달된 유효 후보 수(URL 보유). 미전달 시 0(G5 완화).
    intent: howto/documents/eligibility/calculator — G1/G4/G8/G-NEW2 분기에 사용.
    has_verified: 계산기에 검증된 예시가 존재하면 True — G4/G-NEW2 분기에 사용."""
    g = (cfg or {}).get("QUALITY_GATE", {}) or {}
    failed = []
    body_text = _plain_text(body_html)

    length = len(body_text)
    # G1: intent별 최소 분량(Phase 5-D). config 오버라이드 우선, 없으면 intent 맵 → default 1800.
    if intent and intent in _G1_MIN_BY_INTENT:
        min_len = _G1_MIN_BY_INTENT[intent]
    else:
        min_len = g.get("MIN_LENGTH", 1800)
    max_len = g.get("MAX_LENGTH", 2500)
    if not (min_len <= length <= max_len):
        if length < min_len:
            shortfall = min_len - length
            detail = (
                f"본문 {length}자 → 최소 {min_len}자(intent={intent or 'default'}) 필요"
                + (f", {shortfall}자 추가 작성 필요" if shortfall > 0 else "")
            )
        else:
            detail = f"본문 {length}자 → 최대 {max_len}자 초과, {length - max_len}자 단축 필요"
        failed.append({"gate": "G1", "grade": "major", "detail": detail})

    h2 = _count_h2(body_html)
    if not (g.get("MIN_H2", 5) <= h2 <= g.get("MAX_H2", 7)):
        failed.append({"gate": "G2", "grade": "major",
                       "detail": f"H2 {h2}개 → {g.get('MIN_H2',5)}~{g.get('MAX_H2',7)}개 필요"})

    faq = _count_faq(body_html)
    if faq < g.get("MIN_FAQ", 5):
        failed.append({"gate": "G3", "grade": "major",
                       "detail": f"FAQ {faq}개 → 최소 {g.get('MIN_FAQ',5)}개 필요"})

    ex = _count_examples(body_html)
    # G4 면제: documents intent(서류 안내글에 계산 예시 불필요) 또는 verified_example 없는 계산기
    _g4_exempt = (intent == "documents") or (not has_verified)
    if not _g4_exempt and ex < g.get("MIN_EXAMPLES", 2):
        failed.append({"gate": "G4", "grade": "major",
                       "detail": f"계산 예시 {ex}개 → 최소 {g.get('MIN_EXAMPLES',2)}개 필요"})

    dead = _count_dead_links(final_html)
    internal = _count_internal_links(final_html)
    min_int = g.get("MIN_INTERNAL_LINKS", 2)
    # Adaptive G5: 요구치 = min(가용 후보 수, MIN_INTERNAL_LINKS).
    # pool=0 → required=0(Cold Start 완전 면제), pool=1 → required=1(1→2 교착 해소),
    # pool≥2 → required=2(정상 G5 적용). href="#" dead link 검사는 pool 무관 항상 적용.
    required = min(link_pool_size, min_int)
    if dead > 0:
        LOG.warning("[G5] 실패 — href=\"#\" 데드링크 %d개 (internal=%d, pool=%d)",
                    dead, internal, link_pool_size)
        failed.append({"gate": "G5", "grade": "critical", "critical": True,
                       "detail": f'href="#" {dead}개 잔존'})
    elif internal < required:
        LOG.warning("[G5] 실패 — 내부링크 %d개 (최소 %d개 필요, pool=%d, dead=0)",
                    internal, required, link_pool_size)
        failed.append({"gate": "G5", "grade": "critical", "critical": True,
                       "detail": f"내부링크 {internal}개 → 최소 {required}개 필요"})
    elif link_pool_size == 0:
        LOG.warning("[G5] Adaptive G5 PASS — pool=0 (Cold Start, 내부링크 조건 면제)")
    elif link_pool_size < min_int:
        LOG.warning("[G5] Adaptive G5 PASS — pool=%d < 최소 %d, 요구치 완화(%d→%d)",
                    link_pool_size, min_int, min_int, required)

    cta = _count_cta(final_html)
    if cta != g.get("CTA_COUNT", 1):
        failed.append({"gate": "G6", "grade": "critical", "critical": True, "auto_fixable": (cta > g.get("CTA_COUNT", 1)),
                       "detail": f"CTA {cta}회 → 정확히 {g.get('CTA_COUNT',1)}회 필요"})

    style = _match_ai_style_blocklist(body_text, cfg)
    if style:
        failed.append({"gate": "G7", "grade": "minor",
                       "detail": f"AI 문체 금지표현 {len(style)}건: {', '.join(style[:3])}"})

    # G-NEW2: 계산 예시 "= 숫자원" 형식 검증 (Phase 5-D)
    # 적용: intent==calculator AND has_verified. 면제: intent==howto 또는 has_verified==False.
    _gnew2_apply = (intent == "calculator") and has_verified
    if _gnew2_apply:
        _numeric_results = re.findall(
            r'(?:=\s*|약\s*)[\d,]+\s*(?:만|억|천)?\s*원', body_text
        )
        if len(_numeric_results) < 2:
            failed.append({"gate": "G-NEW2", "grade": "major",
                           "detail": (f"'= 숫자원' 형식 예시 {len(_numeric_results)}개 "
                                      f"→ 최소 2개 필요 (intent=calculator, has_verified=True)")})

    # A1: 프롬프트 내부 지시어가 H2/H3에 노출된 경우
    art = _count_prompt_artifacts(body_html)
    if art:
        failed.append({"gate": "A1", "grade": "major",
                       "detail": f"H2/H3 프롬프트 지시어 {art}건 (번호 prefix 또는 CTA/행동유도 헤딩)"})

    # A2: body_html 단계에서 href="#" 데드링크 (cleaner 미적용 시 잔존 확인)
    body_dead = _count_dead_links(body_html)
    if body_dead:
        failed.append({"gate": "A2", "grade": "critical", "critical": True,
                       "detail": f'body_html에 href="#" 데드링크 {body_dead}개'})

    # A3: SSOT 외 계산기 링크(환각 계산기)
    hallucinated = _count_hallucinated_calc_links(body_html)
    if hallucinated:
        failed.append({"gate": "A3", "grade": "major",
                       "detail": f"존재하지 않는 계산기 링크: {', '.join(hallucinated[:5])}"})

    # A4: 미채워진 플레이스홀더
    ph = _count_placeholders(body_html)
    if ph:
        failed.append({"gate": "A4", "grade": "major",
                       "detail": f"미채워진 플레이스홀더 {ph}개 (data-ph 또는 {{{{...}}}})"})

    return (len(failed) == 0, failed)


_GRADE_ORDER = {"critical": 0, "major": 1, "minor": 2}


def _prioritize(failed: list) -> list:
    """failed_rules에 priority 부여. Critical 우선, 이후 등장 순. (안정 정렬)"""
    ordered = sorted(enumerate(failed), key=lambda x: (_GRADE_ORDER.get(x[1].get("grade", "major"), 1), x[0]))
    out = []
    for i, (_, rule) in enumerate(ordered, 1):
        r = dict(rule)
        r["priority"] = i
        out.append(r)
    return out


def _overall_severity(rules: list) -> str:
    grades = [r.get("grade", "major") for r in rules]
    if "critical" in grades:
        return "critical"
    if "major" in grades:
        return "major"
    return "minor"


# ── AI Score(S1~S6) — Gate 통과 후에만 ────────────────────────────
_SCORE_DIMS = ["s1", "s2", "s3", "s4", "s5", "s6"]
_SCORE_LABEL = {
    "s1": "계산 예시 품질(formula 일치·서로 다른 조건 2개)",
    "s2": "법적 근거 설명의 맥락 적합성(존재·정확성은 G8 소관)",
    "s3": "최신 기준 반영(적용 연도 명시)",
    "s4": "문체 자연스러움(G7 외)",
    "s5": "중복 콘텐츠 유사도",
    "s6": "사용자 검색 의도 충족(계산·예시·주의·FAQ 비중)",
}
# S2: 법적근거 '존재/정확성'은 G8(결정론)이 확정하므로 Score에서 재판정하지 않음 → critical 강등(major).
_SCORE_GRADE = {"s1": "major", "s2": "major", "s3": "major",
                "s4": "minor", "s5": "major", "s6": "minor"}


def _score_with_gpt(cfg: dict, body_html: str, calc: dict) -> dict:
    """S1~S6 GPT 채점. 반환 {scores:{s1..s6}, reason, failed:[{gate,detail,grade}]}."""
    calc = calc or {}
    year = datetime.now().year
    # S3는 '연도별로 바뀌는 수치'가 있는 계산기에만 적용연도 명시를 요구. evergreen(연도 무관)이면 면제.
    # (registry content.evergreen 기준 — G8/S2와 같은 철학: 해당 없는 걸 존재/형식으로 감점하지 않음)
    _entry = _load_legal_basis().get(str(calc.get("slug", "")).strip()) or {}
    _evergreen = bool((_entry.get("content") or {}).get("evergreen"))
    s3_line = (
        "S3 최신 기준 반영: 이 계산기는 연도별로 바뀌는 금액·요율이 없는 evergreen 계산기이므로 "
        "적용 연도 명시를 요구하지 않는다 — 이 항목으로 감점하지 말고 100점을 준다.\n"
        if _evergreen else
        f"S3 최신 기준 반영: 금액·요율 등 연도별로 바뀌는 수치를 언급할 때 적용 연도({year})가 명시됐는가.\n"
    )
    system = (
        "너는 계산기 소개글 품질 심사위원이다. 후하게 주지 말고 엄격히 평가한다.\n"
        f"올해는 {year}년이다. 아래 6개 항목을 각 0~100으로 채점하라.\n"
        "S1 계산 예시 품질: 제공된 예시가 formula와 일치하고 서로 다른 조건을 다루는가. "
        "예시 '개수'는 G4가 이미 검증하므로 개수 부족으로는 감점하지 말 것(품질만 본다).\n"
        "S2 법적 근거 설명의 맥락 적합성: 법령·조항의 '존재 여부와 정확성'은 다른 검증(G8)이 이미 "
        "확정하므로 여기서 판정하지 않는다. 오직 '인용된 법적 근거가 이 계산기에 왜 적용되는지 "
        "설명이 자연스럽고 맥락에 맞는가'만 평가한다. 법령이 인용되어 있으면 '표기 여부'로는 절대 "
        "감점하지 말 것(그건 G8 소관). 인용 자체가 없더라도 그 사유로 여기서 감점하지 말고 100점을 준다.\n"
        + s3_line +
        "S4 문체 자연스러움: 전반적으로 AI 티가 나거나 부자연스러운가. "
        "특정 금지표현 목록은 G7이 이미 검사하므로 여기서 재판정하지 말고 전반적 자연스러움만 본다.\n"
        "S5 중복 콘텐츠: 일반론 나열이 아니라 이 계산기 고유 정보를 담았는가.\n"
        "S6 검색 의도 충족: 법 설명 비중이 과하지 않고 '바로 계산→예시→주의사항→FAQ'에 무게가 실렸는가. "
        "각 섹션의 '존재 여부'는 Gate(G2/G3/G4) 소관이므로 존재로 감점하지 말고 비중·균형만 본다.\n"
        "순수 JSON만 반환:\n"
        '{"scores":{"s1":0,"s2":0,"s3":0,"s4":0,"s5":0,"s6":0},'
        '"reason":"200자 이내 핵심 감점 사유",'
        '"failed":[{"dim":"s5","detail":"고유 정보가 적고 일반론 위주"}]}'
    )
    user = (
        f"계산기명: {calc.get('name','')}\n"
        f"formula: {calc.get('formula','')}\n"
        f"본문(가시텍스트):\n{_plain_text(body_html)[:3000]}"
    )
    provider = build_provider(cfg.get("CALC_REVIEW_PROVIDER", "openai"), cfg)
    model = cfg.get("CALC_REVIEW_MODEL", "gpt-4o")
    text, tokens = provider.chat(system, user, model, max_tokens=500)
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception:
        pass
    d = parse_json_lenient(text) or {}
    scores = d.get("scores", {}) or {}
    vals = [float(scores.get(k, 0) or 0) for k in _SCORE_DIMS]
    normalized = int(max(0, min(100, round(sum(vals) / len(vals))))) if vals else 0
    failed = []
    for f in (d.get("failed", []) or []):
        dim = str(f.get("dim", "")).lower()
        failed.append({"gate": dim.upper(), "grade": _SCORE_GRADE.get(dim, "major"),
                       "detail": f.get("detail", _SCORE_LABEL.get(dim, dim))})
    return {"scores": scores, "normalized": normalized,
            "reason": str(d.get("reason", ""))[:200], "failed": failed, "model": model}


# ── G8: 결정론적 법적 근거 검증(GPT 미신뢰 — 코드가 직접 문자열 매칭) ──
def _load_legal_basis() -> dict:
    """G8용 legal_basis. registry_loader에 위임(legal_basis.draft.yaml + registry_auto.yaml merge).
    자동엔트리는 legal 전부 null → G8 required 검사 스킵(하위호환 그대로)."""
    from .registry_loader import load_registry
    return load_registry()


def _norm(s) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def _law_mentioned(law, ntext: str) -> bool:
    """정답 판정은 관대: 복합(·,/)이면 구성요소 중 하나라도 등장하면 통과.
    정식명(국민연금법)뿐 아니라 약칭(국민연금 — '법' 접미사 제거형)도 허용(4대보험 등 약칭 사용 대응)."""
    for comp in re.split(r"[·/]", str(law or "")):
        comp = _norm(re.sub(r"\(.*?\)", "", comp)).replace("(복합)", "")
        if not comp:
            continue
        if comp in ntext:
            return True
        core = comp[:-1] if comp.endswith("법") else comp   # 국민연금법 → 국민연금
        if len(core) >= 3 and core in ntext:
            return True
    return False


def _authority_mentioned(authority, ntext: str) -> bool:
    """기관명 토큰(부/청/처/원/위원회) 중 하나라도 등장하면 통과(복합 표기 대응)."""
    orgs = re.findall(r"[가-힣]+(?:부|청|처|원|위원회)", str(authority or ""))
    return any(_norm(o) in ntext for o in orgs) if orgs else True


def _check_g8(body_html: str, calc: dict, intent: str = None) -> list:
    """G8: legal_basis 대조. 반환=실패 rule 리스트(빈 리스트=통과, GPT 호출 전 결정론 판정).
    required(law/article/authority) 누락 또는 forbidden_articles/phrases 등장 → Critical.
    검사 범위: body_html(writer FAQ 포함). legal_basis 미등록 계산기는 미적용(하위호환).
    intent=documents → article 조항 번호 검사 면제(서류 안내글 특성)."""
    slug = str((calc or {}).get("slug", "")).strip()
    entry = _load_legal_basis().get(slug)
    if not entry:
        return []
    text = _plain_text(body_html)
    ntext = _norm(text)
    correct = f"{entry.get('law', '')} {entry.get('article', '')}".strip()
    fails = []

    # 1) required — 값이 채워진 필드만(article=null이면 제외). robust 매칭(오탐 방지).
    if entry.get("law") and not _law_mentioned(entry["law"], ntext):
        fails.append({"gate": "G8", "grade": "critical", "critical": True,
                      "detail": f"법령명 미언급: {entry['law']}"})
    # G8 article 면제: documents intent(서류 안내글에서 계산 조항 번호 강요 부자연스러움)
    _g8_article_exempt = (intent == "documents")
    if not _g8_article_exempt and entry.get("article") and _norm(entry["article"]) not in ntext:
        fails.append({"gate": "G8", "grade": "critical", "critical": True,
                      "detail": f"정확한 조항 미언급: '{correct}'를 명시할 것"})
    if entry.get("authority") and not _authority_mentioned(entry["authority"], ntext):
        fails.append({"gate": "G8", "grade": "critical", "critical": True,
                      "detail": f"소관기관 미언급: {entry['authority']}"})

    # 2) forbidden_articles — 정확일치(정규화). 등장 시 정답 조항까지 detail에 담아 재생성 강조.
    for fa in entry.get("forbidden_articles") or []:
        if _norm(fa) in ntext:
            fails.append({"gate": "G8", "grade": "critical", "critical": True,
                          "detail": f"금지된 조항 등장: {fa}. 이 계산기의 올바른 법적 근거는 "
                                    f"'{correct}'이며, 반드시 이 값만 사용하고 다른 조항 번호는 언급하지 말 것."})

    # 3) forbidden_phrases — 계산기별 확정형 표현(법적 정확성 이슈이므로 Critical).
    for fp in entry.get("forbidden_phrases") or []:
        if fp in text:
            fails.append({"gate": "G8", "grade": "critical", "critical": True,
                          "detail": f"확정형 표현 '{fp}' 등장 — 수급/지급 요건이 복합적이므로 "
                                    f"'가능성이 있습니다'/'심사 결과에 따라 달라질 수 있습니다'처럼 표현할 것."})
    return fails


# ── 공개 API: Gate → Score → Rewrite Contract ─────────────────────
def check_publish_quality(cfg: dict, body_html: str, final_html: str,
                          calc: dict = None, link_pool_size: int = 0,
                          intent: str = None, has_verified: bool = False) -> dict:
    """발행 글 품질 검수. Gate(코드) 실패면 GPT 미호출 REWRITE, 통과면 Score(GPT).

    반환(Rewrite Contract, §9 + 운영 필드):
      {result: PASS|WARN|REWRITE, score: int|None, severity: str|None,
       failed_rules: list|None, html: <G6 코드수정 반영본>, quality_review_model: str|None}
    link_pool_size: inject_internal_links에 전달된 유효 후보 수. calculator_pipeline이 전달.
    intent: howto/documents/eligibility/calculator — G1/G4/G8/G-NEW2 분기.
    has_verified: 계산기에 검증된 예시 존재 여부 — G4/G-NEW2 분기.
    """
    # G6 코드수정: CTA 중복이면 초과분 제거 후 그 결과로 판정/발행
    fixed_html, removed = _dedupe_cta(final_html or "", keep=(cfg or {}).get("QUALITY_GATE", {}).get("CTA_COUNT", 1))
    if removed:
        LOG.info("[품질] CTA 중복 %d개 코드수정 제거", removed)

    passed, failed = check_gates(body_html, fixed_html, cfg, link_pool_size=link_pool_size,
                                 intent=intent, has_verified=has_verified)
    # G8(결정론적 법적근거 검증) — 결과만 병합(GPT 호출 전). intent 전달로 documents 면제.
    g8 = _check_g8(body_html, calc, intent=intent)
    if g8:
        failed = failed + g8
        passed = False
    if not passed:
        rules = _prioritize(failed)
        return {"result": "REWRITE", "score": None, "severity": _overall_severity(rules),
                "failed_rules": rules, "html": fixed_html, "quality_review_model": None}

    # Gate 통과 → AI Score
    try:
        s = _score_with_gpt(cfg, body_html, calc)
    except Exception as e:
        LOG.warning("[품질] Score GPT 실패 → 보수적 REWRITE: %s", e)
        return {"result": "REWRITE", "score": None, "severity": "major",
                "failed_rules": [{"gate": "SCORE", "grade": "major", "detail": f"채점 오류:{e}", "priority": 1}],
                "html": fixed_html, "quality_review_model": None}

    score = s["normalized"]
    sc = (cfg or {}).get("QUALITY_SCORE", {}) or {}
    pass_th, warn_th = sc.get("PASS_THRESHOLD", 90), sc.get("WARN_THRESHOLD", 80)
    if score >= pass_th:
        result, rules = "PASS", None
    elif score >= warn_th:
        # WARN: 발행하되 개선후보. failed는 참고용으로만(재생성 트리거 아님).
        result = "WARN"
        rules = _prioritize(s["failed"]) if s["failed"] else None
    else:
        result, rules = "REWRITE", _prioritize(s["failed"])
    return {"result": result, "score": score,
            "severity": (_overall_severity(rules) if rules else None),
            "failed_rules": rules, "html": fixed_html, "quality_review_model": s["model"]}
