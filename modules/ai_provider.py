"""
ai_provider.py — AI Provider 추상화 레이어
지원: OpenAI(GPT) / Anthropic(Claude) / Google(Gemini)
site_id 기반 사이트별 AI 모델 라우팅 지원 (sites 탭 research_ai/writing_ai/review_ai)
"""
import time
from abc import ABC, abstractmethod

# ── AI 모델 슬롯 → provider/model 매핑 ───────────────────────────────────────
AI_PROFILE_MAP = {
    "gemini_flash":  {"provider": "gemini",  "model": "gemini-2.0-flash-exp"},
    "gemini_pro":    {"provider": "gemini",  "model": "gemini-2.5-pro"},
    "gpt4o":         {"provider": "openai",  "model": "gpt-4o"},
    "gpt4o_mini":    {"provider": "openai",  "model": "gpt-4o-mini"},
    "claude_sonnet": {"provider": "claude",  "model": "claude-sonnet-4-6"},
    "claude_haiku":  {"provider": "claude",  "model": "claude-haiku-4-5-20251001"},
    "claude_opus":   {"provider": "claude",  "model": "claude-opus-4-6"},
}

# ── Provider 클래스 ────────────────────────────────────────────────────────────
class AIProvider(ABC):
    @abstractmethod
    def chat(self, system: str, user: str, model: str, max_tokens: int = 4000) -> tuple[str, int]:
        """Returns (response_text, total_tokens)"""


class GPTProvider(AIProvider):
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)

    def chat(self, system: str, user: str, model: str, max_tokens: int = 4000):
        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": user}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content, resp.usage.total_tokens


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, system: str, user: str, model: str, max_tokens: int = 4000):
        resp = self.client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return resp.content[0].text, tokens


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        # google-genai (신규 SDK). 구 google-generativeai 는 deprecated.
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def chat(self, system: str, user: str, model: str, max_tokens: int = 4000):
        from google.genai import types
        resp = self.client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        usage = getattr(resp, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", 0) or 0
        return (resp.text or ""), tokens


# ── 팩토리 ────────────────────────────────────────────────────────────────────
def build_provider(provider_name: str, cfg: dict) -> AIProvider:
    p = provider_name.lower()
    if p in ("openai", "gpt"):
        return GPTProvider(cfg["OPENAI_API_KEY"])
    elif p == "claude":
        return ClaudeProvider(cfg["CLAUDE_API_KEY"])
    elif p == "gemini":
        return GeminiProvider(cfg["GEMINI_API_KEY"])
    raise ValueError(f"알 수 없는 provider: {provider_name}")


def build_provider_from_profile(profile: str, cfg: dict) -> tuple["AIProvider", str]:
    """
    AI 슬롯명(예: gemini_flash)으로 provider + model 반환.
    sites 탭의 research_ai / writing_ai / review_ai 값에 사용.
    """
    info = AI_PROFILE_MAP.get(profile)
    if not info:
        raise ValueError(f"알 수 없는 AI 프로필: {profile}")
    provider = build_provider(info["provider"], cfg)
    return provider, info["model"]


def build_provider_for_role(role: str, cfg: dict,
                             site_cfg: dict = None) -> tuple["AIProvider", str]:
    """
    role = "orchestrator" | "research" | "writing" | "review"
    site_cfg 있으면 sites 탭 AI 프로필 우선 적용.
    없으면 config.yaml ORCHESTRATOR_PROVIDER 등 fallback.
    """
    ROLE_SITE_KEY = {
        "research":     "research_ai",
        "writing":      "writing_ai",
        "review":       "review_ai",
    }
    ROLE_CFG_KEY = {
        "orchestrator": ("ORCHESTRATOR_PROVIDER", "MODEL_ORCHESTRATOR"),
        "research":     ("PLANNER_PROVIDER",      "MODEL_PLANNER"),
        "writing":      ("WRITER_PROVIDER",       "MODEL_WRITER"),
        "review":       ("EDITOR_PROVIDER",       "MODEL_EDITOR"),
    }

    # 사이트별 AI 프로필 우선
    if site_cfg and role in ROLE_SITE_KEY:
        profile = site_cfg.get(ROLE_SITE_KEY[role], "")
        if profile and profile in AI_PROFILE_MAP:
            return build_provider_from_profile(profile, cfg)

    # fallback: config.yaml
    prov_key, model_key = ROLE_CFG_KEY.get(role, ("WRITER_PROVIDER", "MODEL_WRITER"))
    provider = build_provider(cfg.get(prov_key, "openai"), cfg)
    model    = cfg.get(model_key, "gpt-4o")
    return provider, model


# ── 재시도 래퍼 ───────────────────────────────────────────────────────────────
def retry_call(fn, max_retries: int = 3, delays=(5, 10)):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delays[min(attempt, len(delays) - 1)])
            else:
                raise
