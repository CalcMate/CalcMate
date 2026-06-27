"""
strategist.py — M0 총괄 오케스트레이터 (GPT) + M2 Strategy Engine (Python)

M0: GPT가 콘텐츠 전략 / 각도 / 회피 패턴 / 톤 결정
M2: Python이 7점수 계산 → final_score 산정

AI 역할 정의서 기준:
  M0 = ORCHESTRATOR_PROVIDER (기본: gpt4o)
  M2 = Python (score_weights.yaml)
"""
import json
import yaml
from pathlib import Path
from .ai_provider import build_provider_for_role, retry_call
from .utils.parser import parse_json_lenient

# ── 기본 가중치 (score_weights.yaml 로드 실패 시 fallback) ───────────────────
DEFAULT_WEIGHTS = {
    "traffic_score":     0.30,
    "cpc_score":         0.20,
    "competition_score": 0.20,
    "cluster_score":     0.10,
    "calculator_score":  0.10,
    "revenue_score":     0.10,
}

# ── M0 총괄 오케스트레이터 시스템 프롬프트 ───────────────────────────────────
SYSTEM_M0 = """너는 멀티사이트 콘텐츠 플랫폼의 총괄 오케스트레이터다.

모든 작업의 우선순위를 판단하고 각 AI에게 작업을 분배한다.
항상 비용 대비 효율을 고려한다. 불필요한 AI 호출을 최소화한다.
오류 발생 시 원인을 분석하고 재시도 또는 대체 경로를 결정한다.

최종 목표: 트래픽 / 애드센스 수익 / 콘텐츠 품질 / 자동화 안정성

[역할 경계]
- SEO 제목 생성, 본문 작성, 메타설명 생성은 절대 수행하지 마라.
- 전략 방향, 콘텐츠 각도, 회피 패턴, 편집 톤만 결정한다.

[7점수 체계 평가 기준]
- traffic_score    : 검색 트래픽 잠재량 (0~100)
- cpc_score        : 클릭당 광고 단가 수준 (0~100)
- competition_score: 경쟁도 역산 — 경쟁 낮을수록 높은 점수 (0~100)
- cluster_score    : 연관 키워드 클러스터 밀도 (0~100)
- calculator_score : 계산기/도구 연계 가능성 (0~100)
- revenue_score    : 수익화 전환 가능성 (0~100)

[AC 점수 공식]
AC_FINAL = (final_score × 0.5) + (ANGLE_FIT × 0.3) + (20 × 0.2)
ANGLE_FIT = content_angle 자체 채점 (0~100)

인사말·코드블록 없이 순수 JSON만 반환:
{"content_angle":"","avoid_patterns":["","",""],"editorial_tone":"","ac_final":0.0,\
"scores":{"traffic_score":0,"cpc_score":0,"competition_score":0,"cluster_score":0,"calculator_score":0,"revenue_score":0}}"""


def _canonical_weight_keys(w: dict) -> dict:
    """가중치 키를 AI 점수 키(traffic_score 등)와 일치시킨다.
    yaml 은 'traffic' 같은 짧은 키를 쓰므로 '_score' 접미사를 붙여 정규화.
    이미 '_score' 로 끝나면 그대로 둔다(멱등)."""
    out = {}
    for k, v in w.items():
        ck = k if str(k).endswith("_score") else f"{k}_score"
        out[ck] = v
    return out


def _load_weights(cfg: dict) -> dict:
    try:
        root = Path(cfg.get("_root", Path(__file__).parent.parent))
        path = root / "config" / "score_weights.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        w = data.get("score_weights", data.get("weights", {}))
        total = sum(w.values())
        if not (0.95 <= total <= 1.05):
            print(f"[M2] score_weights 합계={total:.2f} — DEFAULT 사용")
            return DEFAULT_WEIGHTS
        # ★ #31: AI 점수 키와 일치하도록 정규화 (traffic → traffic_score)
        return _canonical_weight_keys(w)
    except Exception as e:
        print(f"[M2] score_weights.yaml 로드 실패: {e} — DEFAULT 사용")
        return DEFAULT_WEIGHTS


def compute_final_score(scores: dict, weights: dict) -> float:
    """M2 Python Strategy Engine — 7점수 가중 합산"""
    return round(sum(float(scores.get(k, 0)) * w for k, w in weights.items()), 2)


def design_strategy(clean_data: dict, score: float,
                    recent_titles: list[str], cfg: dict,
                    site_cfg: dict = None) -> dict:
    """
    M0 오케스트레이터 호출 → 전략 설계
    M2 Python → final_score 계산
    site_cfg: sites 탭 해당 사이트 행 (있으면 orchestrator AI 프로필 적용)
    """
    weights = _load_weights(cfg)
    provider, model = build_provider_for_role("orchestrator", cfg, site_cfg)

    source_type = clean_data.get("source_type", "policy")
    site_id     = clean_data.get("site_id", "")

    user_msg = (
        f"콘텐츠명: {clean_data.get('clean_policy_name')}\n"
        f"핵심요약: {clean_data.get('clean_summary')}\n"
        f"카테고리: {clean_data.get('clean_category')}\n"
        f"수혜/대상: {clean_data.get('clean_target')}\n"
        f"소스 타입: {source_type}\n"
        f"사이트 ID: {site_id}\n"
        f"외부 입력 점수: {score}\n"
        f"점수 가중치: {json.dumps(weights, ensure_ascii=False)}\n"
        f"최근 발행 제목 30개: {json.dumps(recent_titles, ensure_ascii=False)}"
    )

    def _call():
        text, tokens = provider.chat(SYSTEM_M0, user_msg, model, max_tokens=700)
        raw = parse_json_lenient(text)
        # M2: Python이 AI 반환 점수로 final_score 재계산
        raw["final_score"] = compute_final_score(raw.get("scores", {}), weights)
        return raw, tokens

    result, tokens = retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))
    result["_tokens"]  = tokens
    result["_weights"] = weights
    return result
