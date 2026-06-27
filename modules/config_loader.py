"""
config_loader.py — config.yaml 로드 및 검증
"""
import yaml
import os
import sys

REQUIRED_MODELS = [
    "MODEL_ORCHESTRATOR", "MODEL_PLANNER", "MODEL_WRITER",
    "MODEL_EDITOR", "MODEL_CLEANER"
]

def load_config(path: str = None) -> dict:
    if path is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "config", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
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
