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
from pathlib import Path

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
    '예를 들어/예시/가정하면' 도입부 또는 '= 10,000원' 형태 계산식 등장 횟수."""
    text = _plain_text(html)
    markers = re.findall(r"예를\s*들어|예시로|가정하(?:면|여|고)|계산해\s*보면", text)
    numeric = re.findall(r"=\s*[\d,]+\s*원|[\d,]+\s*원\s*[×xX*]", text)
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
               "G5": "critical", "G6": "critical", "G7": "minor"}


def check_gates(body_html: str, final_html: str, cfg: dict) -> tuple:
    """(passed: bool, failed_gates: list[dict]). 각 항목: {gate, detail, grade, ...}.
    body 기준 게이트는 body_html, 조립 기준 게이트(G5/G6)는 final_html을 본다."""
    g = (cfg or {}).get("QUALITY_GATE", {}) or {}
    failed = []
    body_text = _plain_text(body_html)

    length = len(body_text)
    if not (g.get("MIN_LENGTH", 1800) <= length <= g.get("MAX_LENGTH", 2500)):
        failed.append({"gate": "G1", "grade": "major",
                       "detail": f"본문 {length}자 → {g.get('MIN_LENGTH',1800)}~{g.get('MAX_LENGTH',2500)}자 필요"})

    h2 = _count_h2(body_html)
    if not (g.get("MIN_H2", 5) <= h2 <= g.get("MAX_H2", 7)):
        failed.append({"gate": "G2", "grade": "major",
                       "detail": f"H2 {h2}개 → {g.get('MIN_H2',5)}~{g.get('MAX_H2',7)}개 필요"})

    faq = _count_faq(body_html)
    if faq < g.get("MIN_FAQ", 5):
        failed.append({"gate": "G3", "grade": "major",
                       "detail": f"FAQ {faq}개 → 최소 {g.get('MIN_FAQ',5)}개 필요"})

    ex = _count_examples(body_html)
    if ex < g.get("MIN_EXAMPLES", 2):
        failed.append({"gate": "G4", "grade": "major",
                       "detail": f"계산 예시 {ex}개 → 최소 {g.get('MIN_EXAMPLES',2)}개 필요"})

    dead = _count_dead_links(final_html)
    internal = _count_internal_links(final_html)
    if dead > 0:
        failed.append({"gate": "G5", "grade": "critical", "critical": True,
                       "detail": f'href="#" {dead}개 잔존'})
    elif internal < g.get("MIN_INTERNAL_LINKS", 2):
        failed.append({"gate": "G5", "grade": "critical", "critical": True,
                       "detail": f"내부링크 {internal}개 → 최소 {g.get('MIN_INTERNAL_LINKS',2)}개 필요"})

    cta = _count_cta(final_html)
    if cta != g.get("CTA_COUNT", 1):
        failed.append({"gate": "G6", "grade": "critical", "critical": True, "auto_fixable": (cta > g.get("CTA_COUNT", 1)),
                       "detail": f"CTA {cta}회 → 정확히 {g.get('CTA_COUNT',1)}회 필요"})

    style = _match_ai_style_blocklist(body_text, cfg)
    if style:
        failed.append({"gate": "G7", "grade": "minor",
                       "detail": f"AI 문체 금지표현 {len(style)}건: {', '.join(style[:3])}"})

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
    "s2": "법적 근거 정확성(출처 표기)",
    "s3": "최신 기준 반영(적용 연도 명시)",
    "s4": "문체 자연스러움(G7 외)",
    "s5": "중복 콘텐츠 유사도",
    "s6": "사용자 검색 의도 충족(계산·예시·주의·FAQ 비중)",
}
_SCORE_GRADE = {"s1": "major", "s2": "critical", "s3": "major",
                "s4": "minor", "s5": "major", "s6": "minor"}


def _score_with_gpt(cfg: dict, body_html: str, calc: dict) -> dict:
    """S1~S6 GPT 채점. 반환 {scores:{s1..s6}, reason, failed:[{gate,detail,grade}]}."""
    calc = calc or {}
    year = datetime.now().year
    system = (
        "너는 계산기 소개글 품질 심사위원이다. 후하게 주지 말고 엄격히 평가한다.\n"
        f"올해는 {year}년이다. 아래 6개 항목을 각 0~100으로 채점하라.\n"
        "S1 계산 예시 품질: 제공된 formula와 일치하고, 서로 다른 조건의 예시가 2개 이상인가.\n"
        "S2 법적 근거 정확성: 법령·요율 언급 시 출처/근거가 명시됐는가(없이 단정하면 감점).\n"
        f"S3 최신 기준 반영: 금액·기간 기준에 적용 연도({year})가 명시됐는가.\n"
        "S4 문체 자연스러움: AI 티/부자연스러운 반복이 없는가.\n"
        "S5 중복 콘텐츠: 일반론 나열이 아니라 이 계산기 고유 정보를 담았는가.\n"
        "S6 검색 의도 충족: '바로 계산→예시→주의사항→FAQ' 흐름 대비 법 설명 비중이 과하지 않은가.\n"
        "순수 JSON만 반환:\n"
        '{"scores":{"s1":0,"s2":0,"s3":0,"s4":0,"s5":0,"s6":0},'
        '"reason":"200자 이내 핵심 감점 사유",'
        '"failed":[{"dim":"s2","detail":"법적 근거 미표기"}]}'
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
# calculator_pipeline 순환 import 회피 위해 독립 로더를 둔다.
_LEGAL_BASIS_PATH = Path(__file__).resolve().parent.parent / "docs" / "legal_basis.draft.yaml"
_legal_basis_cache = None


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


def _check_g8(body_html: str, calc: dict) -> list:
    """G8: legal_basis 대조. 반환=실패 rule 리스트(빈 리스트=통과, GPT 호출 전 결정론 판정).
    required(law/article/authority) 누락 또는 forbidden_articles/phrases 등장 → Critical.
    검사 범위: body_html(writer FAQ 포함). legal_basis 미등록 계산기는 미적용(하위호환)."""
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
    if entry.get("article") and _norm(entry["article"]) not in ntext:
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
def check_publish_quality(cfg: dict, body_html: str, final_html: str, calc: dict = None) -> dict:
    """발행 글 품질 검수. Gate(코드) 실패면 GPT 미호출 REWRITE, 통과면 Score(GPT).

    반환(Rewrite Contract, §9 + 운영 필드):
      {result: PASS|WARN|REWRITE, score: int|None, severity: str|None,
       failed_rules: list|None, html: <G6 코드수정 반영본>, quality_review_model: str|None}
    """
    # G6 코드수정: CTA 중복이면 초과분 제거 후 그 결과로 판정/발행
    fixed_html, removed = _dedupe_cta(final_html or "", keep=(cfg or {}).get("QUALITY_GATE", {}).get("CTA_COUNT", 1))
    if removed:
        LOG.info("[품질] CTA 중복 %d개 코드수정 제거", removed)

    passed, failed = check_gates(body_html, fixed_html, cfg)
    # G8(결정론적 법적근거 검증) — check_gates 시그니처 무변경, 결과만 병합(GPT 호출 전).
    g8 = _check_g8(body_html, calc)
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
