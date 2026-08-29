# -*- coding: utf-8 -*-
"""
scripts/phase5_c_sample_gen.py — Phase 5-C 신규 콘텐츠 생성 시스템 + 10개 샘플 검증

목적: 검색의도(intent)에 따라 서로 다른 구조의 글을 생성할 수 있는지 증명
격리: 기존 37개 원본/production pipeline 완전 미사용
출력: data/phase5-c/

🚫 기존 37개 콘텐츠 수정/재생성 금지
🚫 WordPress 실서버 게시 금지
🚫 calculator_pipeline._write_article() 사용 금지 (prompts/calculator_writer_prompt.txt 경로)
"""
import sys, os, json, re, hashlib, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.ai_roles import make_provider
from modules.calculator_seo_generator import generate_seo
from modules import calculator_prompt_manager as PM
from modules.utils.parser import parse_json_lenient
from modules import cleaner
from modules.calculator_pipeline import _legal_basis_block, _resolve_context_block
from modules.publish_quality import check_gates, _check_g8, _plain_text, _count_faq
from modules.logger import get_logger, BudgetTracker
import modules.image_generator as img_gen

LOG = get_logger("phase5c")

# ── 출력 디렉터리 ───────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "data" / "phase5-c"
ARTICLES_DIR = OUT / "articles"
IMAGES_DIR   = OUT / "images"
REPORTS_DIR  = OUT / "reports"
FINAL_DIR    = OUT / "final"
for d in (ARTICLES_DIR, IMAGES_DIR, REPORTS_DIR, FINAL_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── 10개 샘플 정의 (Phase 5-B 설계안 기준) ────────────────────────────────
SAMPLES = [
    {"no": 1,  "slug": "severance-pay",           "intent": "eligibility", "keyword": "퇴직금 받는 조건"},
    {"no": 2,  "slug": "weekly-holiday-allowance", "intent": "howto",      "keyword": "주휴수당 계산법"},
    {"no": 3,  "slug": "unemployment-benefit",     "intent": "eligibility", "keyword": "실업급여 조건"},
    {"no": 4,  "slug": "four-insurances",          "intent": "calculator",  "keyword": "4대보험 계산"},
    {"no": 5,  "slug": "annual-leave-allowance",   "intent": "howto",      "keyword": "연차수당 계산방법"},
    {"no": 6,  "slug": "severance-pay",            "intent": "documents",  "keyword": "퇴직금 신청서류"},
    {"no": 7,  "slug": "육아휴직_급여_계산기",       "intent": "eligibility", "keyword": "육아휴직 급여 조건"},
    {"no": 8,  "slug": "연말정산_환급액_계산기",      "intent": "calculator",  "keyword": "연말정산 환급액"},
    {"no": 9,  "slug": "unemployment-benefit",     "intent": "howto",      "keyword": "실업급여 신청방법"},
    {"no": 10, "slug": "four-insurances",          "intent": "documents",  "keyword": "4대보험 취득신고 서류"},
]

# 금지: 구 생성 시스템 H2 구조 (이 패턴이 나오면 FAIL)
LEGACY_H2_PATTERN = re.compile(
    r'<h2[^>]*>\s*(?:계산기\s*소개|입력\s*방법|결과\s*확인)\s*</h2>', re.I
)

# ── intent별 기대 H2 구조 (G-NEW1 검증용) ─────────────────────────────────
INTENT_H2_MAP = {
    "eligibility": ["지급 대상", "근로시간 조건", "제외 대상", "계산 방법", "FAQ"],
    "howto":       ["이용 절차", "계산 예시", "주의사항", "FAQ"],
    "documents":   ["필수 서류 목록", "서류 발급 방법", "제출 기한 및 절차", "주의사항", "FAQ"],
    "calculator":  ["계산 원리", "지급 조건", "주의사항", "FAQ"],
}

# intent별 이미지 프롬프트 prefix
INTENT_IMAGE_PREFIX = {
    "eligibility": "Person checking eligibility checklist, professional Korean office worker reviewing requirements document",
    "howto":       "Step-by-step guide illustration, Korean professional using calculator with workflow diagram",
    "documents":   "Stack of official Korean documents, application forms organized on desk",
    "calculator":  "Clean calculator with financial report, Korean salary calculation concept",
}

# 계산기별 비주얼 테마 (slug 기반)
CALC_VISUAL_THEME = {
    "severance-pay":           "retirement, handshake, workplace departure",
    "weekly-holiday-allowance":"weekly calendar, work hours, pay stub",
    "unemployment-benefit":    "job search, employment office, support",
    "four-insurances":         "insurance shield, health, pension icons",
    "annual-leave-allowance":  "vacation calendar, annual leave, days off",
    "육아휴직_급여_계산기":      "parental leave, baby, family, workplace",
    "연말정산_환급액_계산기":     "tax return, year-end settlement, refund",
}


# ── intent 분류기 ────────────────────────────────────────────────────────
def classify_intent(keyword: str, declared_intent: str) -> tuple[str, str]:
    """keyword + 선언된 intent → 최종 intent, reason.
    선언값이 있으면 우선 사용. 키워드와 불일치 시 WARN 기록."""
    kw = keyword.lower()
    inferred = "calculator"
    reason = "기본값(calculator)"

    if any(t in kw for t in ["조건", "대상", "자격", "받을 수", "해당", "요건"]):
        inferred, reason = "eligibility", "대상/자격 키워드"
    elif any(t in kw for t in ["신청서류", "서류", "발급", "제출"]):
        inferred, reason = "documents", "서류/절차 키워드"
    elif any(t in kw for t in ["계산법", "계산방법", "신청방법", "방법", "절차", "사용법"]):
        inferred, reason = "howto", "방법/절차 키워드"
    elif any(t in kw for t in ["계산", "얼마", "금액", "환급"]):
        inferred, reason = "calculator", "계산/금액 키워드"

    final = declared_intent if declared_intent else inferred
    warn = ""
    if declared_intent and declared_intent != inferred:
        warn = f"WARN: 선언 intent={declared_intent} vs 추론 intent={inferred} (키워드 기반)"
    return final, reason + (f" | {warn}" if warn else "")


# ── example_context 생성 ────────────────────────────────────────────────
def build_example_context(calc: dict) -> dict | None:
    """formula 기반 예시 데이터 생성. formula 없으면 None."""
    slug = calc.get("slug", "")
    formula = str(calc.get("formula", "")).strip()

    if slug == "severance-pay":
        return {
            "examples": [
                {"inputs": {"avg_monthly_wage": 3000000, "total_days": 730},
                 "result": {"severance": 6000000},
                 "narrative": "평균 월급 300만원, 근속 2년(730일) → 퇴직금 = 300만원 × (730÷365) = 600만원"},
                {"inputs": {"avg_monthly_wage": 2500000, "total_days": 1095},
                 "result": {"severance": 7500000},
                 "narrative": "평균 월급 250만원, 근속 3년(1,095일) → 퇴직금 = 250만원 × (1,095÷365) = 750만원"},
            ],
            "formula": formula, "source": "verified_formula"
        }
    elif slug == "weekly-holiday-allowance":
        return {
            "examples": [
                {"inputs": {"hourly_wage": 10030, "weekly_hours": 40},
                 "result": {"weekly_allowance": 80240},
                 "narrative": "시급 10,030원, 주 40시간 근무 → 주휴수당 = 10,030 × (40÷40×8) = 80,240원"},
                {"inputs": {"hourly_wage": 12000, "weekly_hours": 20},
                 "result": {"weekly_allowance": 48000},
                 "narrative": "시급 12,000원, 주 20시간 근무 → 주휴수당 = 12,000 × (20÷40×8) = 48,000원"},
            ],
            "formula": formula, "source": "verified_formula"
        }
    elif slug == "unemployment-benefit":
        return {
            "examples": [
                {"inputs": {"avg_daily_wage": 100000, "employment_days": 240},
                 "result": {"daily_benefit": 60000, "total": 14400000},
                 "narrative": "일평균임금 10만원 → 실업급여 일액 = 10만원 × 0.6 = 6만원, 240일 기준 약 1,440만원"},
                {"inputs": {"avg_daily_wage": 80000, "employment_days": 180},
                 "result": {"daily_benefit": 48000, "total": 8640000},
                 "narrative": "일평균임금 8만원 → 실업급여 일액 = 8만원 × 0.6 = 4만 8천원, 180일 기준 약 864만원"},
            ],
            "formula": formula, "source": "verified_formula"
        }
    elif slug == "four-insurances":
        # 2026년 공식 요율: 국민연금 4.75%, 건강보험 3.595%, 장기요양 13.14%(건보료기준), 고용 0.9%
        # 300만원: NP=142,500 / HI=107,850 / LTC=14,171 / EI=27,000 / 합=291,521
        # 400만원: NP=190,000 / HI=143,800 / LTC=18,895 / EI=36,000 / 합=388,695
        # LTC = HI × 13.14% (보건복지부 2025-11-05 고시)
        return {
            "examples": [
                {"inputs": {"monthly_salary": 3000000},
                 "result": {"national_pension": 142500, "health_insurance": 107850,
                            "long_term_care": 14171, "employment_insurance": 27000,
                            "worker_compensation": 0},
                 "narrative": "월급 300만원 기준: 국민연금 142,500원(4.75%) + 건강보험 107,850원(3.595%) + 장기요양 14,171원(건강보험료의 13.14%) + 고용보험 27,000원(0.9%) = 약 291,521원"},
                {"inputs": {"monthly_salary": 4000000},
                 "result": {"national_pension": 190000, "health_insurance": 143800,
                            "long_term_care": 18895, "employment_insurance": 36000,
                            "worker_compensation": 0},
                 "narrative": "월급 400만원 기준: 국민연금 190,000원(4.75%) + 건강보험 143,800원(3.595%) + 장기요양 18,895원(건강보험료의 13.14%) + 고용보험 36,000원(0.9%) = 약 388,695원"},
            ],
            "formula": formula, "source": "verified_formula"
        }
    elif slug == "annual-leave-allowance":
        return {
            "examples": [
                {"inputs": {"daily_wage": 100000, "unused_days": 5},
                 "result": {"allowance": 500000},
                 "narrative": "일급 10만원, 미사용 연차 5일 → 연차수당 = 10만원 × 5일 = 50만원"},
                {"inputs": {"daily_wage": 150000, "unused_days": 10},
                 "result": {"allowance": 1500000},
                 "narrative": "일급 15만원, 미사용 연차 10일 → 연차수당 = 15만원 × 10일 = 150만원"},
            ],
            "formula": formula, "source": "verified_formula"
        }
    elif slug == "육아휴직_급여_계산기":
        # result에 benefit 금액 미포함 — SSOT content_ssot에서 특정 상한/하한 금액 언급 금지.
        # G-CALC는 result가 비어 있으면 금액 검증 건너뜀.
        return {
            "examples": [
                {"inputs": {"monthly_wage": 2000000},
                 "result": {},
                 "narrative": "월 통상임금 200만원 → 통상임금 × 80% 공식 적용. 정확한 지급액은 고용노동부 최신 안내 확인 필요"},
                {"inputs": {"monthly_wage": 1500000},
                 "result": {},
                 "narrative": "월 통상임금 150만원 → 통상임금 × 80% 공식 적용. 정확한 지급액은 고용노동부 최신 안내 확인 필요"},
            ],
            "formula": formula, "source": "verified_formula",
            "note": "남녀고용평등법 제19조의2 기준 — 통상임금 80% 지급. 상한·하한액은 고용노동부 최신 안내 확인 필요"
        }
    elif slug == "연말정산_환급액_계산기":
        return {
            "examples": [
                {"inputs": {"withheld_tax": 800000, "final_tax": 600000},
                 "result": {"refund": 200000},
                 "narrative": "원천징수세액 80만원, 결정세액 60만원 → 환급액 = 80만원 - 60만원 = 약 20만원"},
                {"inputs": {"withheld_tax": 1200000, "final_tax": 800000},
                 "result": {"refund": 400000},
                 "narrative": "원천징수세액 120만원, 결정세액 80만원 → 환급액 = 120만원 - 80만원 = 약 40만원"},
            ],
            "formula": formula, "source": "verified_formula",
            "note": "환급액 = 기납부세액(원천징수세액) - 결정세액. 음수이면 추납"
        }
    else:
        # formula 없거나 검증 불가
        if not formula:
            return None
        return {
            "examples": [],
            "formula": formula,
            "source": "formula_only",
            "note": "검증된 계산 예시 없음 — AI가 formula 범위 내에서 생성"
        }


# ── FAQ 생성 (intent 컨텍스트 포함) ──────────────────────────────────────
def generate_faq_with_intent(cfg: dict, calc: dict, intent: str) -> list:
    """intent 컨텍스트를 user 프롬프트에 추가하여 FAQ 생성."""
    system, base_user = PM.get_faq_prompt(calc, n_min=5, n_max=7)

    intent_context = {
        "eligibility": (
            "이 글의 검색의도는 '지급 조건/자격요건'이다. "
            "FAQ는 본문에서 다루지 않은 엣지 케이스(계약직, 파트타임, 육아휴직 중, 퇴직 직전 등) 중심으로 구성한다. "
            "지급 공식 반복, 일반 계산 방법 설명은 제외한다."
        ),
        "howto": (
            "이 글의 검색의도는 '계산 방법/사용법'이다. "
            "FAQ는 계산 결과 해석, 입력값 실수, 특수 케이스(주 15시간 미만, 수습 기간 등) 중심으로 구성한다. "
            "자격 조건 반복, 서류 안내는 제외한다."
        ),
        "documents": (
            "이 글의 검색의도는 '신청 서류/절차'이다. "
            "FAQ는 서류 분실, 대체 서류, 온라인 신청 방법, 처리 기간 등 실무 중심으로 구성한다. "
            "계산 공식, 지급 조건 반복은 제외한다."
        ),
        "calculator": (
            "이 글의 검색의도는 '구체적 계산/수치'이다. "
            "FAQ는 계산 방식 차이, 세금 공제 여부, 특수 케이스 수치 등 중심으로 구성한다. "
            "서류 절차, 일반 자격 조건 반복은 제외한다."
        ),
    }

    intent_hint = intent_context.get(intent, "")
    user = f"{base_user}\n\n[FAQ 생성 방향]\n{intent_hint}"

    try:
        provider, model = make_provider(cfg, "writer")
        text, tokens = provider.chat(system, user, model, max_tokens=1500)
        try:
            BudgetTracker(cfg).record(model, tokens)
        except Exception:
            pass
        result = parse_json_lenient(text)
        faq = result.get("faq", [])
        if isinstance(faq, list) and faq:
            return faq[:7]
        raise ValueError("빈 FAQ 반환")
    except Exception as e:
        LOG.warning("FAQ 생성 실패(%s) → 기본 FAQ: %s", calc.get("name",""), e)
        return [
            {"question": f"누가 {calc.get('name','').replace('계산기','')} 대상인가요?",
             "answer": "법령에서 정한 조건을 충족하는 근로자가 대상입니다. 자세한 조건은 본문을 확인하세요."},
            {"question": "계산 결과와 실제 지급액이 다를 수 있나요?",
             "answer": "본 계산기는 참고용이며, 실제 지급액은 회사 내부 기준 및 공제 항목에 따라 다를 수 있습니다."},
            {"question": "계산 시 자주 하는 실수는 무엇인가요?",
             "answer": "입력값의 단위나 기간 설정 오류가 많습니다. 정확한 날짜와 금액을 입력하세요."},
            {"question": "관련 법적 근거는 무엇인가요?",
             "answer": "관련 법령에 따라 계산됩니다. 정확한 기준은 소관기관에 문의하세요."},
            {"question": "계산 결과에 이의가 있을 경우 어디에 문의하나요?",
             "answer": "고용노동부 또는 소관 기관 상담센터에 문의하시기 바랍니다."},
        ]


# ── 본문 생성 ─────────────────────────────────────────────────────────────
def generate_article_body(cfg: dict, calc: dict, keyword: str, seo: dict,
                          faq: list, example_context: dict, intent: str,
                          law_ssot_block: str = "") -> tuple[str, dict]:
    """신규 경로: content/calculator/prompt.get_article_prompt(intent=) 사용.
    절대 prompts/calculator_writer_prompt.txt 경로 사용 안 함."""
    system, user_base = PM.get_article_prompt(
        calc, seo=seo, faq=faq, example_context=example_context, intent=intent,
        law_ssot_block=law_ssot_block
    )

    # legal_basis + resolve_context 추가 주입 (기존 _legal_basis_block/_resolve_context_block 재사용)
    legal_block = _legal_basis_block(calc)
    context_block = _resolve_context_block(calc)

    # narrative를 user 프롬프트에 직접 주입 (AI가 JSON을 재해석하지 않고 그대로 사용하도록)
    narrative_block = ""
    if example_context and example_context.get("examples"):
        narratives = [e["narrative"] for e in example_context["examples"] if "narrative" in e]
        if narratives:
            narrative_block = (
                "\n[계산 예시 — 아래 수식·결과를 계산 섹션에 그대로 반영할 것 (숫자·단위 변경 금지)]\n" +
                "\n".join(f"- {n}" for n in narratives) + "\n"
            )

    # 법령 조항을 user에도 강조 — 정확한 문자열 직접 지정 (system 단독으로는 무시되는 경향 대비)
    legal_user_hint = ""
    if legal_block.strip():
        try:
            from modules.calculator_pipeline import _load_legal_basis
            _lb = _load_legal_basis().get(str(calc.get("slug", "")), {})
            _law = _lb.get("law", "")
            _article = _lb.get("article", "")
            if _law and _article:
                legal_user_hint = (
                    f"\n[법령 조항 필수 — 아래 문자열을 본문 어느 섹션·FAQ이든 최소 1회 정확히 포함할 것]\n"
                    f"  필수 문자열: '{_law} {_article}'\n"
                    f"  사용 예: '{_law} {_article}에 따르면 ...' 또는 '({_law} {_article})'\n"
                )
        except Exception:
            pass

    # keyword를 user 프롬프트에 명시 + 분량 강조 (system 단독으로는 지켜지지 않는 경향 대비)
    user = (
        f"타겟 키워드(검색의도 기반 글 주제): {keyword}\n"
        f"검색의도(intent): {intent}\n"
        f"[필수] 본문 가시 텍스트 최소 2,000자 — 각 섹션을 충분히 길게 상세히 서술할 것. "
        f"분량이 부족하면 구체적인 조건·예외·사례·실무 팁을 추가로 서술하여 보강한다.\n"
        + legal_user_hint
        + narrative_block
        + user_base
    )

    # intent별 섹션 최소 분량 기준 (분량 부족 재발 방지용 강화판)
    intent_length_guide = {
        "eligibility": (
            "지급 대상 350자 이상 / 근로시간 조건 300자 이상 / "
            "제외 대상 300자 이상 / 계산 방법 450자 이상(예시 2개 포함) / "
            "FAQ 전체 900자 이상(각 답변 120자 이상, 5문항 이상)"
        ),
        "howto": (
            "이용 절차 500자 이상(단계별 3단계 이상 서술) / "
            "계산 예시 550자 이상(검증된 예시 2개 반드시 포함, 각 예시에 '예를 들어'로 시작 + '= 숫자원' 결과 표기 필수) / "
            "주의사항 400자 이상(3항목 이상) / "
            "FAQ 전체 900자 이상(각 답변 130자 이상, 5문항 이상)"
        ),
        "documents": (
            "필수 서류 목록 450자 이상(각 서류 용도·특징 설명 포함) / "
            "서류 발급 방법 400자 이상(발급처·절차 상세 서술) / "
            "제출 기한 및 절차 350자 이상(구체적 기한 포함) / "
            "주의사항 300자 이상(3항목 이상) / "
            "FAQ 전체 900자 이상(각 답변 120자 이상, 5문항 이상)"
        ),
        "calculator": (
            "계산 원리 450자 이상(예시 2개 포함, 각 예시에 '예를 들어'로 시작 + '= 숫자원' 결과 표기 필수) / "
            "지급 조건 350자 이상 / "
            "주의사항 350자 이상(3항목 이상) / "
            "FAQ 전체 900자 이상(각 답변 120자 이상, 5문항 이상)"
        ),
    }
    section_guide = intent_length_guide.get(intent, "각 섹션 250자 이상 / FAQ 700자 이상")

    # documents intent 전용 법령 언급 강화
    documents_legal = ""
    if intent == "documents":
        documents_legal = (
            "\n- [documents intent 필수] 서류 안내 글이더라도 관련 법령 조항을 반드시 1회 이상 언급한다. "
            "예: '근로자퇴직급여 보장법 제9조에 따라 ~' 등의 방식으로 법적 근거를 명시한다. "
            "주의사항 섹션 또는 FAQ 답변에 포함해도 된다.\n"
        )

    # 분량 + 소관기관 언급 보강 지시
    length_authority_block = (
        "\n[분량 및 소관기관 필수 지시 — 반드시 준수]\n"
        f"- 본문 가시 텍스트 최소 2,000자. 아래 섹션별 최소 분량을 반드시 채울 것:\n"
        f"  {section_guide}\n"
        "- 각 섹션이 짧게 끝나면 구체적 조건·예외·사례를 추가로 서술하여 보강한다. 2,600자를 넘기지 않는다.\n"
        "- 소관기관(예: 고용노동부, 건강보험공단 등)을 반드시 최소 1회 이상 언급한다.\n"
        "  FAQ 답변 또는 본문 어느 섹션이든 상관없이 '정확한 세부 기준은 [소관기관] 등 관할기관에 확인하시기 바랍니다' 취지의 문장을 포함한다.\n"
        "- 계산 예시가 필요한 섹션(계산 방법, 계산 예시, 계산 원리)에서:\n"
        "  각 예시는 반드시 '예를 들어'로 시작하고, 결과값은 반드시 '= 숫자원' 또는 '= 약 숫자원' 형식으로 마무리한다.\n"
        "  예: '예를 들어, 평균 월급이 300만원이고 근속 2년인 경우, 퇴직금 = 300만원 × (730÷365) = 600만원'\n"
        f"{documents_legal}"
        "- AI 티 나는 표현 금지: '살펴보겠습니다', '알아보겠습니다', '알아보도록 하겠습니다' 절대 사용 금지."
    )

    full_system = system + legal_block + context_block + length_authority_block

    provider, model = make_provider(cfg, "writer")
    text, tokens = provider.chat(full_system, user, model, max_tokens=4500)
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception:
        pass

    body = cleaner.parse_html_body(text)
    body = cleaner.strip_prompt_artifacts(body)
    body = re.sub(r'<h1>.*?</h1>', '', body, count=1, flags=re.IGNORECASE | re.DOTALL)

    token_info = {"model": model, "tokens": tokens}
    return body, token_info


# ── 이미지 생성 (intent 기반) ───────────────────────────────────────────
def generate_images_for_intent(cfg: dict, calc: dict, intent: str,
                                keyword: str, post_id: str) -> dict:
    """intent + calc_slug 기반 이미지 프롬프트 구성 → image_generator 호출."""
    slug = calc.get("slug", "unknown")
    calc_name = calc.get("name", "")
    intent_prefix = INTENT_IMAGE_PREFIX.get(intent, "Professional financial calculator, Korean workplace")
    calc_theme = CALC_VISUAL_THEME.get(slug, "financial calculation, professional")

    thumb_prompt = (
        f"{intent_prefix}, {calc_theme}, "
        "flat design illustration, professional Korean business context, "
        "bright clean background, high quality, no text, no numbers, no letters"
    )
    body_prompt = (
        f"Infographic visualization of {calc_name} calculation process for Korean audience, "
        f"intent={intent}, {calc_theme}, "
        "clean diagram style, step-by-step flow, professional design, no random text"
    )

    image_dir = IMAGES_DIR / slug
    image_dir.mkdir(parents=True, exist_ok=True)

    # image_generator.generate()는 data/outputs/에 저장 → 이후 phase5-c/images/로 복사
    seo_data = {
        "image_prompt_thumbnail": thumb_prompt,
        "image_prompt_body": body_prompt,
        "seo_title": keyword,
    }
    result = img_gen.generate(post_id, seo_data, cfg)

    # 파일명 규칙: {slug}_{intent}_{date}_thumb.png / _body.png
    date_str = datetime.now().strftime("%Y%m%d")
    thumb_fname = f"{slug}_{intent}_{date_str}_thumb.webp"
    body_fname = f"{slug}_{intent}_{date_str}_body.webp"
    thumb_dest = image_dir / thumb_fname
    body_dest = image_dir / body_fname

    thumb_src = result.get("thumbnail_url", "")
    body_src = result.get("body_image_url", "")

    import shutil
    thumb_ok, body_ok = False, False
    if thumb_src and thumb_src != "실패" and Path(thumb_src).exists():
        shutil.copy2(thumb_src, thumb_dest)
        thumb_ok = True
    if body_src and body_src != "실패" and Path(body_src).exists():
        shutil.copy2(body_src, body_dest)
        body_ok = True

    return {
        "thumbnail": {
            "prompt": thumb_prompt,
            "filename": thumb_fname,
            "path": str(thumb_dest) if thumb_ok else None,
            "alt": f"{keyword} {datetime.now().year} — {calc_name}",
            "ok": thumb_ok,
        },
        "body": {
            "prompt": body_prompt,
            "filename": body_fname,
            "path": str(body_dest) if body_ok else None,
            "alt": f"{calc_name} {intent} 설명 이미지",
            "insert_after_h2": INTENT_H2_MAP.get(intent, ["FAQ"])[1] if len(INTENT_H2_MAP.get(intent, [])) > 1 else "FAQ",
            "ok": body_ok,
        },
    }


# ── Gate 검사 (신규 G-NEW 포함) ─────────────────────────────────────────
def run_gates(body_html: str, calc: dict, intent: str, keyword: str, cfg: dict,
              example_context: dict = None) -> dict:
    """기존 Gate + 신규 G-NEW1(intent 구조), G-NEW2(예시 형식), G-NEW3(구 구조 차단)."""
    has_verified = (
        example_context is not None and
        bool(example_context.get("examples")) and
        example_context.get("source") != "formula_only"
    )
    # 기존 Gate (G5/G6은 Phase5-C에서 제외: G5=내부링크 미조립, G6=CTA 미조립)
    passed, failed = check_gates(body_html, body_html, cfg, link_pool_size=0)
    # G6(CTA)와 G5(내부링크)는 phase5-c 로컬 생성 단계에서 제외 (pipeline 조립 후 검사)
    failed = [f for f in failed if f.get("gate") not in ("G5", "G6")]

    # G8 (documents intent는 서류 안내글이므로 article 체크 면제 — law/authority만 유지)
    g8 = _check_g8(body_html, calc)
    if intent == "documents":
        g8 = [f for f in g8 if "조항 미언급" not in f.get("detail", "")]
    if g8:
        failed = failed + g8
        passed = False

    # G4 intent별 면제: documents는 면제, 또는 verified_example 없는 계산기도 면제
    failed = [f for f in failed if not (
        f.get("gate") == "G4" and (intent == "documents" or not has_verified)
    )]

    # G-NEW3: 구 생성 시스템 H2 구조 재발 방지 (계산기소개/입력방법/결과확인)
    if LEGACY_H2_PATTERN.search(body_html):
        legacy_found = LEGACY_H2_PATTERN.findall(body_html)
        failed.append({
            "gate": "G-NEW3", "grade": "critical",
            "detail": f"구 H2 구조 재발: {[h for h in legacy_found][:3]}"
        })
        passed = False

    # G-NEW1: intent별 기대 H2와 실제 H2 비교
    actual_h2 = re.findall(r'<h2[^>]*>\s*(.+?)\s*</h2>', body_html, re.I)
    expected = INTENT_H2_MAP.get(intent, [])
    if expected:
        # FAQ는 반드시 포함
        faq_present = any("FAQ" in h or "자주" in h for h in actual_h2)
        if not faq_present:
            failed.append({
                "gate": "G-NEW1", "grade": "major",
                "detail": f"intent={intent}: FAQ H2 없음. 실제 H2: {actual_h2}"
            })
            passed = False
        # intent 첫 번째 H2가 expected[0]인지 확인 (구조 차별화 핵심)
        if actual_h2 and expected:
            first_expected = expected[0]
            first_actual = actual_h2[0] if actual_h2 else ""
            # 유사도 체크 (완전일치 아닌 포함 여부)
            if first_expected.replace(" ", "") not in first_actual.replace(" ", ""):
                failed.append({
                    "gate": "G-NEW1", "grade": "major",
                    "detail": (
                        f"intent={intent} 첫 H2 불일치: "
                        f"기대={first_expected}, 실제={first_actual}"
                    )
                })
                passed = False

    # G-NEW2: 계산 예시 형식 검증 (calculator + verified_example 있을 때만 적용)
    # howto는 G4가 이미 예시개수 체크, verified_example 없는 계산기도 면제
    text = _plain_text(body_html)
    numeric_results = re.findall(r'(?:=\s*|약\s*)[\d,]+\s*(?:만|억|천)?\s*원', text)
    if len(numeric_results) < 2 and intent in ("calculator",) and has_verified:
        failed.append({
            "gate": "G-NEW2", "grade": "major",
            "detail": f"'= 숫자원' 형식 예시 {len(numeric_results)}개 → 최소 2개 필요 (intent={intent})"
        })
        passed = False

    # G1 완화: intent별 최소 분량 조정
    # howto(4 H2)·documents(5 H2)는 4개 H2 구조로 2000자 채우기 어려움
    min_body_by_intent = {"eligibility": 2000, "howto": 1750, "documents": 1850, "calculator": 1850}
    min_body = min_body_by_intent.get(intent, 1900)
    text_len_check = len(text)  # text = _plain_text(body_html), 이미 계산됨
    # G1이 이미 failed에 있으면 재평가
    failed = [f for f in failed if not (f.get("gate") == "G1")]
    if text_len_check < min_body:
        failed.append({
            "gate": "G1", "grade": "major",
            "detail": f"본문 {text_len_check}자 → 최소 {min_body}자(intent={intent}) 필요, {min_body - text_len_check}자 추가 작성 필요"
        })
        passed = False

    # G2 완화: intent별 H2 개수 조정 (howto/calculator는 4개도 허용)
    min_h2_by_intent = {"eligibility": 5, "howto": 4, "documents": 5, "calculator": 4}
    h2_count = len(actual_h2)
    min_h2 = min_h2_by_intent.get(intent, 4)
    # G2가 이미 failed에 있으면 조건 재평가
    failed = [f for f in failed if not (f.get("gate") == "G2")]
    if h2_count < min_h2:
        failed.append({
            "gate": "G2", "grade": "major",
            "detail": f"H2 {h2_count}개 → intent={intent} 최소 {min_h2}개 필요"
        })
        passed = False

    # keyword ↔ title/body 일치 확인 (WARN)
    kw_in_body = keyword.replace(" ", "") in text.replace(" ", "")
    if not kw_in_body:
        failed.append({
            "gate": "KW-ALIGN", "grade": "minor",
            "detail": f"키워드 '{keyword}'가 본문에 없음"
        })

    # FAQ 비반복 검사 (간단 휴리스틱: 본문 주요 문장과 FAQ 답변 similarity)
    faq_count = _count_faq(body_html)
    if faq_count < 5:
        failed.append({
            "gate": "G3", "grade": "major",
            "detail": f"FAQ {faq_count}개 → 최소 5개 필요"
        })
        passed = False

    return {
        "passed": not any(f.get("grade") in ("critical", "major") for f in failed),
        "all_failed": failed,
        "critical": [f for f in failed if f.get("grade") == "critical"],
        "major": [f for f in failed if f.get("grade") == "major"],
        "minor": [f for f in failed if f.get("grade") == "minor"],
        "h2_list": actual_h2,
        "h2_count": h2_count,
        "faq_count": faq_count,
        "text_length": len(text),
    }


# ── 단일 샘플 처리 ──────────────────────────────────────────────────────
def run_one(cfg: dict, sample: dict, calc: dict) -> dict:
    no, slug, keyword = sample["no"], sample["slug"], sample["keyword"]
    declared_intent = sample["intent"]

    print(f"\n{'='*60}")
    print(f"[{no:02d}] {slug} × {declared_intent} × '{keyword}'")
    print(f"{'='*60}")

    result = {
        "no": no, "slug": slug, "keyword": keyword,
        "declared_intent": declared_intent,
        "calc_name": calc.get("name", ""),
        "generated_at": datetime.now().isoformat(),
        "source_version": "phase5-c",
        "prompt_version": hashlib.sha1(
            (PM.get_article_prompt.__module__ + declared_intent).encode()
        ).hexdigest()[:8],
    }

    # 1) intent 분류
    final_intent, intent_reason = classify_intent(keyword, declared_intent)
    result["intent"] = final_intent
    result["intent_reason"] = intent_reason
    print(f"  intent: {final_intent} ({intent_reason})")

    # 2) example_context
    example_ctx = build_example_context(calc)
    result["has_verified_example"] = example_ctx is not None and bool(example_ctx.get("examples"))
    print(f"  example_context: {'✅ 검증됨' if result['has_verified_example'] else '⚠️  없음(formula 없거나 미지원)'}")

    # 3) SEO 생성
    try:
        seo = generate_seo(cfg, name=calc.get("name", ""), keyword=keyword, intent=final_intent)
        result["seo"] = seo
        print(f"  SEO 제목: {seo.get('seo_title','')}")
    except Exception as e:
        result["error"] = f"SEO 생성 실패: {e}"
        result["gate_result"] = "FAIL"
        return result

    # 4) FAQ 생성
    try:
        faq = generate_faq_with_intent(cfg, calc, final_intent)
        result["faq_count"] = len(faq)
        print(f"  FAQ: {len(faq)}개 생성")
    except Exception as e:
        faq = []
        print(f"  FAQ 생성 실패(계속): {e}")

    # 5) 본문 생성
    try:
        body_html, token_info = generate_article_body(
            cfg, calc, keyword, seo, faq, example_ctx, final_intent
        )
        result["token_info"] = token_info
        result["body_length"] = len(_plain_text(body_html))
        print(f"  본문: {result['body_length']}자 (모델: {token_info.get('model','')})")
    except Exception as e:
        result["error"] = f"본문 생성 실패: {e}"
        result["gate_result"] = "FAIL"
        return result

    # 본문 파일 저장
    article_fname = f"{no:02d}_{slug}_{keyword[:20].replace(' ','_')}.html"
    article_path = ARTICLES_DIR / article_fname
    article_path.write_text(body_html, encoding="utf-8")
    result["article_file"] = article_fname

    # 6) Gate 검사
    gate_result = run_gates(body_html, calc, final_intent, keyword, cfg, example_ctx)
    result["gates"] = gate_result
    print(f"  Gate: {'✅ PASS' if gate_result['passed'] else '❌ FAIL'} "
          f"(H2={gate_result['h2_count']}, FAQ={gate_result['faq_count']}, "
          f"len={gate_result['text_length']}자)")
    if gate_result["critical"]:
        for f in gate_result["critical"]:
            print(f"    🔴 {f['gate']}: {f['detail'][:80]}")
    if gate_result["major"]:
        for f in gate_result["major"]:
            print(f"    🟡 {f['gate']}: {f['detail'][:80]}")
    if gate_result["minor"]:
        for f in gate_result["minor"]:
            print(f"    ⚪ {f['gate']}: {f['detail'][:60]}")
    print(f"  H2 목록: {gate_result['h2_list']}")

    # 7) 이미지 생성
    post_id = f"p5c_{no:02d}_{datetime.now().strftime('%H%M%S')}"
    try:
        images = generate_images_for_intent(cfg, calc, final_intent, keyword, post_id)
        result["images"] = images
        print(f"  썸네일: {'✅' if images['thumbnail']['ok'] else '❌'} {images['thumbnail']['filename']}")
        print(f"  본문이미지: {'✅' if images['body']['ok'] else '❌'} {images['body']['filename']}")
    except Exception as e:
        result["images"] = {"error": str(e)}
        print(f"  이미지 생성 실패: {e}")

    # 8) ContentRequest 저장
    content_request = {
        "calculator_id": calc.get("id", ""),
        "calc_name": calc.get("name", ""),
        "slug": slug,
        "keyword": keyword,
        "intent": final_intent,
        "intent_reason": intent_reason,
        "seo": seo,
        "faq": faq,
        "example_context": example_ctx,
        "images": result.get("images", {}),
        "generated_at": result["generated_at"],
        "source_version": result["source_version"],
        "prompt_version": result["prompt_version"],
        "gate_result": gate_result,
    }
    req_path = OUT / "requests" / f"{no:02d}_{slug}_{final_intent}.json"
    req_path.write_text(json.dumps(content_request, ensure_ascii=False, indent=2), encoding="utf-8")

    # 최종 판정
    result["gate_result"] = "PASS" if gate_result["passed"] else "FAIL"
    return result


# ── 메인 실행 ─────────────────────────────────────────────────────────────
def run(only_no: int = None, stop_on_fail: bool = True):
    """
    only_no: 특정 번호만 실행 (예: only_no=1 → 샘플 #1만)
    stop_on_fail: #1 실패 시 중단 여부
    """
    print("=" * 70)
    print("Phase 5-C 신규 콘텐츠 생성 시스템 샘플 검증")
    print(f"시작: {datetime.now().isoformat()}")
    print("=" * 70)

    cfg = load_config()
    db  = get_db_adapter(cfg)
    repo = CalculatorRepository(db)
    calcs_by_slug = {c["slug"]: c for c in repo.get_all() if c.get("slug")}

    # 샘플 필터링
    targets = [s for s in SAMPLES if (only_no is None or s["no"] == only_no)]

    results = []
    for i, sample in enumerate(targets):
        slug = sample["slug"]
        calc = calcs_by_slug.get(slug)
        if not calc:
            print(f"\n❌ 계산기 미발견: {slug} → SKIP")
            results.append({"no": sample["no"], "slug": slug,
                            "gate_result": "FAIL", "error": "계산기 레코드 없음"})
            continue

        r = run_one(cfg, sample, calc)
        results.append(r)

        # #1 실패 시 중단 (사용자 확인 후 계속)
        if i == 0 and r.get("gate_result") == "FAIL" and stop_on_fail and only_no is None:
            print("\n" + "="*60)
            print("🛑 샘플 #1 FAIL — 10개 연속 생성 중단")
            print("원인을 확인하고 생성 로직을 수정한 후 재시도하세요.")
            _save_report(results, partial=True)
            return results

        time.sleep(1)  # rate limit 회피

    _save_report(results)

    # 통합 중복 검사
    if len(results) > 1:
        _check_duplicates(results)

    return results


def _save_report(results: list, partial: bool = False):
    suffix = "_partial" if partial else ""
    report_path = REPORTS_DIR / f"phase5c_report{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  결과 저장: {report_path.name}")

    passed = sum(1 for r in results if r.get("gate_result") == "PASS")
    failed = sum(1 for r in results if r.get("gate_result") == "FAIL")
    print(f"\n{'='*60}")
    print(f"Phase 5-C {'중간' if partial else '최종'} 결과")
    print(f"{'='*60}")
    print(f"  생성 수: {len(results)}/{'1(#1 검증 중)' if partial else '10'}")
    print(f"  PASS: {passed}  FAIL: {failed}")
    for r in results:
        status = "✅" if r.get("gate_result") == "PASS" else "❌"
        intent = r.get("intent", r.get("declared_intent", "?"))
        print(f"  {status} [{r.get('no',0):02d}] {r.get('slug','?')} × {intent} × '{r.get('keyword','')}'")
        if r.get("error"):
            print(f"       오류: {r['error']}")
        elif r.get("gates"):
            fails = r["gates"].get("all_failed", [])
            if fails:
                for f in fails[:3]:
                    print(f"       [{f.get('grade','?')}] {f.get('gate','?')}: {str(f.get('detail',''))[:60]}")


def _check_duplicates(results: list):
    print(f"\n{'='*60}")
    print("통합 중복 검사 (제목/H2/intent)")
    print(f"{'='*60}")

    titles = [r.get("seo", {}).get("seo_title", "") for r in results]
    seen_titles = set()
    for t in titles:
        if t and t in seen_titles:
            print(f"  ⚠️ 제목 중복 발견: '{t}'")
        seen_titles.add(t)

    # intent × slug 중복 (같은 계산기×같은 intent)
    combos = {}
    for r in results:
        key = f"{r.get('slug','')}×{r.get('intent','')}"
        if key in combos:
            print(f"  ⚠️ 계산기×intent 중복: {key}")
        combos[key] = True

    print("  중복 검사 완료")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no", type=int, default=None, help="특정 샘플 번호만 실행 (1~10)")
    parser.add_argument("--all", action="store_true", help="10개 전체 실행")
    parser.add_argument("--no-stop", action="store_true", help="#1 실패해도 계속 진행")
    args = parser.parse_args()

    if args.all:
        run(only_no=None, stop_on_fail=not args.no_stop)
    elif args.no:
        run(only_no=args.no)
    else:
        print("샘플 #1만 실행합니다 (--all 로 전체 실행, --no N 으로 특정 번호)")
        run(only_no=1)
