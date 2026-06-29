"""
config_loader.py — config.yaml 로드 및 검증 + secrets.yaml 병합

설정 로딩 일원화:
  - config.yaml  : 일반 설정(모델/예산/Google/WP URL 등)
  - secrets.yaml : 민감정보(API 키/앱 비밀번호/봇 토큰) — .gitignore 대상, 추적 안 함
  런타임에서 두 파일을 Merge(secrets 우선)하여 기존 flat 키(cfg["OPENAI_API_KEY"] 등)를
  그대로 사용. 호출부 코드 무변경(하위 호환).
"""
import yaml
import os
import sys

REQUIRED_MODELS = [
    "MODEL_ORCHESTRATOR", "MODEL_PLANNER", "MODEL_WRITER",
    "MODEL_EDITOR", "MODEL_CLEANER"
]

# config.yaml이 아닌 config/secrets.yaml에 보관하는 민감정보 키(flat).
# 저장(쓰기) 시 이 키들은 config.yaml에서 제거되고 secrets.yaml로 이동한다.
SECRET_KEYS = (
    "OPENAI_API_KEY",
    "CLAUDE_API_KEY",
    "GEMINI_API_KEY",
    "WORDPRESS_APP_PASSWORD",
    "WORDPRESS_PASSWORD",     # 구 키(하위호환). _normalize가 APP_PASSWORD로 승격.
    "TELEGRAM_BOT_TOKEN",
)


def _secrets_path_for(config_path: str) -> str:
    """config.yaml 경로 기준 같은 폴더의 secrets.yaml 경로."""
    return os.path.join(os.path.dirname(os.path.abspath(config_path)), "secrets.yaml")


def load_secrets(config_path: str = None) -> dict:
    """secrets.yaml 전체를 dict로 반환(없으면 {}). 중첩 섹션 포함."""
    if config_path is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base, "config", "config.yaml")
    sp = _secrets_path_for(config_path)
    if os.path.exists(sp):
        with open(sp, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def merge_secrets(cfg: dict, config_path: str = None) -> dict:
    """secrets.yaml의 최상위 scalar 키를 cfg에 병합(secrets 우선).
    중첩 섹션(wordpress_profiles / ai_keys 등)은 cfg에 합치지 않음
    (site_repository가 파일에서 직접 읽으므로 불필요)."""
    if cfg is None:
        cfg = {}
    secrets = load_secrets(config_path)
    for k, v in secrets.items():
        if isinstance(v, (dict, list)):
            continue  # 중첩 섹션은 제외
        cfg[k] = v
    return cfg


def save_secrets_flat(updates: dict, config_path: str = None):
    """민감정보 flat 키를 secrets.yaml에 병합 저장(기존 중첩 섹션/타 키 보존)."""
    if config_path is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base, "config", "config.yaml")
    sp = _secrets_path_for(config_path)
    data = {}
    if os.path.exists(sp):
        with open(sp, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    for k, v in updates.items():
        data[k] = v
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    with open(sp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def split_secrets(cfg: dict) -> tuple[dict, dict]:
    """cfg를 (일반설정, 민감정보)로 분리. config.yaml 저장 직전 사용.
    반환된 일반설정에는 SECRET_KEYS가 제거되어 있음."""
    public, secret = {}, {}
    for k, v in cfg.items():
        if k in SECRET_KEYS:
            secret[k] = v
        else:
            public[k] = v
    return public, secret


def load_config(path: str = None) -> dict:
    if path is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "config", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg = merge_secrets(cfg, path)   # secrets.yaml 병합(secrets 우선)
    cfg = _normalize(cfg)
    _validate(cfg)
    return cfg


def _normalize(cfg: dict) -> dict:
    """키명 정규화. WordPress 앱 비밀번호 키를 WORDPRESS_APP_PASSWORD로 단일화.
    구 키(WORDPRESS_PASSWORD)는 하위호환으로 자동 승격."""
    if cfg is None:
        cfg = {}
    legacy = cfg.get("WORDPRESS_PASSWORD")
    if legacy and not cfg.get("WORDPRESS_APP_PASSWORD"):
        cfg["WORDPRESS_APP_PASSWORD"] = legacy
    return cfg


def is_wordpress_ready(cfg: dict) -> bool:
    """WordPress 발행에 필요한 설정이 모두 갖춰졌는지 판정.
    미구축(빈 값/placeholder) 시 False → 파이프라인은 발행을 건너뛰고 대기."""
    url = (cfg.get("WORDPRESS_URL") or "").strip()
    user = (cfg.get("WORDPRESS_USERNAME") or "").strip()
    pw = (cfg.get("WORDPRESS_APP_PASSWORD") or cfg.get("WORDPRESS_PASSWORD") or "").strip()
    if not url or not user or not pw:
        return False
    # placeholder/예시 값은 미구성으로 취급
    if "example.com" in url or user in ("temp", "admin") and pw in ("temp", "REDACTED_WP_PASSWORD"):
        return False
    return True


def _validate(cfg: dict):
    missing = [k for k in REQUIRED_MODELS if not (cfg.get(k) or "").strip()]
    if missing:
        raise ConfigError(f"config.yaml에 아래 MODEL 항목이 공란입니다: {missing}\n"
                          f"공급사 공식 문서 기준 최신 모델명을 입력하세요.")
    # WORDPRESS_URL은 더 이상 필수가 아님 — WordPress 미구축 상태에서도 대기 동작.
    # (발행 단계에서 is_wordpress_ready로 판정 후 건너뜀)


class ConfigError(Exception):
    pass
