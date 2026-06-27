"""
logger.py — 구조화 JSON 로그 + 토큰 비용 추적
v11.7: provider별 비용 분리 추적 추가 (기존 기능 100% 보존)
"""
import json, os, logging
from datetime import datetime, date
from pathlib import Path

BASE = Path(__file__).parent.parent / "data"

def get_logger(name: str = "pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log_file = BASE / "logs" / "pipeline.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(ch)
        logger.addHandler(fh)
    return logger


class BudgetTracker:
    """
    일/월 AI 비용 추적기 (v12: 입력/출력 단가 분리 + 모델별 집계 + 토큰 집계)

    - 입력/출력 토큰을 따로 받으면 in/out 단가로 정확 계산
    - 총 토큰만 있으면 모델별 blended 단가로 근사
    - 모델명을 prefix로 매칭(claude-3-5-sonnet-latest, gemini-2.5-flash 등 변형 대응)
    - 기존 daily/monthly/by_provider 구조 100% 보존 + by_model 추가
    """
    # USD per 1K tokens — (입력단가, 출력단가). blended는 둘 평균 근사로 사용.
    PRICE_IO = {
        "gpt-4o":            (0.0025, 0.01),
        "gpt-4o-mini":       (0.00015, 0.0006),
        "o1":                (0.015, 0.06),
        "claude-opus":       (0.015, 0.075),
        "claude-sonnet":     (0.003, 0.015),
        "claude-3-5-sonnet": (0.003, 0.015),
        "claude-haiku":      (0.0008, 0.004),
        "gemini-2.5-pro":    (0.00125, 0.01),
        "gemini-2.5-flash":  (0.0003, 0.0025),
        "gemini-1.5-pro":    (0.00125, 0.005),
        "gemini-1.5-flash":  (0.00015, 0.0006),
        "text-embedding-3-small": (0.00002, 0.00002),
        "text-embedding-3-large": (0.00013, 0.00013),
    }
    DEFAULT_IO = (0.005, 0.005)

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.path = BASE / "logs" / "budget.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── 단가/provider 추론 (prefix 매칭) ─────────────────────────
    @classmethod
    def _io_price(cls, model: str) -> tuple:
        m = (model or "").lower()
        # 정확 일치 우선, 없으면 prefix 포함 매칭
        if m in cls.PRICE_IO:
            return cls.PRICE_IO[m]
        for key, price in cls.PRICE_IO.items():
            if m.startswith(key) or key in m:
                return price
        return cls.DEFAULT_IO

    @staticmethod
    def _provider_of(model: str) -> str:
        m = (model or "").lower()
        if m.startswith(("gpt", "o1", "text-embedding", "dall-e")):
            return "openai"
        if m.startswith("claude"):
            return "claude"
        if m.startswith("gemini") or m.startswith("imagen"):
            return "gemini"
        return "openai"

    def _load(self):
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"daily": {}, "monthly": {}}
        self.data.setdefault("daily", {})
        self.data.setdefault("monthly", {})
        if "by_provider" not in self.data:
            self.data["by_provider"] = {
                "openai": {"daily": {}, "monthly": {}},
                "claude": {"daily": {}, "monthly": {}},
                "gemini": {"daily": {}, "monthly": {}},
            }
        # v12: 모델별 비용/토큰 집계
        self.data.setdefault("by_model", {})       # model -> {daily:{date:cost}, monthly:{m:cost}}
        self.data.setdefault("tokens", {"daily": {}, "monthly": {}})  # 토큰 합계

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record(self, model: str, tokens: int = 0,
               in_tokens: int = None, out_tokens: int = None) -> float:
        """비용 기록.

        in_tokens/out_tokens 가 주어지면 입력/출력 단가로 정확 계산,
        없으면 tokens(총합)에 blended 단가 적용(근사).
        실패한 호출도 누적 토큰을 넘겨 호출하면 비용에 반영된다.
        """
        price_in, price_out = self._io_price(model)
        if in_tokens is not None or out_tokens is not None:
            it = int(in_tokens or 0)
            ot = int(out_tokens or 0)
            cost = (it / 1000) * price_in + (ot / 1000) * price_out
            total_tok = it + ot
        else:
            total_tok = int(tokens or 0)
            blended = (price_in + price_out) / 2
            cost = (total_tok / 1000) * blended

        today = str(date.today())
        month = today[:7]

        self.data["daily"][today] = self.data["daily"].get(today, 0) + cost
        self.data["monthly"][month] = self.data["monthly"].get(month, 0) + cost

        provider = self._provider_of(model)
        pdata = self.data["by_provider"].setdefault(provider, {"daily": {}, "monthly": {}})
        pdata["daily"][today] = pdata["daily"].get(today, 0) + cost
        pdata["monthly"][month] = pdata["monthly"].get(month, 0) + cost

        mdata = self.data["by_model"].setdefault(model or "unknown", {"daily": {}, "monthly": {}})
        mdata["daily"][today] = mdata["daily"].get(today, 0) + cost
        mdata["monthly"][month] = mdata["monthly"].get(month, 0) + cost

        tk = self.data["tokens"]
        tk["daily"][today] = tk["daily"].get(today, 0) + total_tok
        tk["monthly"][month] = tk["monthly"].get(month, 0) + total_tok

        self._save()
        return cost

    def check_budget(self) -> dict:
        today = str(date.today())
        month = today[:7]
        daily_used = self.data["daily"].get(today, 0)
        monthly_used = self.data["monthly"].get(month, 0)
        return {
            "daily_used": round(daily_used, 4),
            "daily_limit": self.cfg.get("DAILY_AI_BUDGET", 5),
            "monthly_used": round(monthly_used, 4),
            "monthly_limit": self.cfg.get("MONTHLY_AI_BUDGET", 100),
            "daily_exceeded": daily_used >= self.cfg.get("DAILY_AI_BUDGET", 5),
            "monthly_exceeded": monthly_used >= self.cfg.get("MONTHLY_AI_BUDGET", 100),
        }

    # ── 조회 API (대시보드 비용 모니터용) ────────────────────────
    def get_daily_cost(self, day: str = None) -> float:
        return self.data["daily"].get(day or str(date.today()), 0)

    def get_monthly_cost(self, month: str = None) -> float:
        return self.data["monthly"].get(month or str(date.today())[:7], 0)

    def get_total_cost(self) -> float:
        return sum(self.data.get("monthly", {}).values())

    def get_today_tokens(self) -> float:
        """오늘 토큰 합계 (※ 기존 호환: 과거엔 비용을 반환했으나 v12부터 토큰)."""
        return self.data.get("tokens", {}).get("daily", {}).get(str(date.today()), 0)

    def get_provider_today(self, provider: str) -> float:
        today = str(date.today())
        return self.data.get("by_provider", {}).get(provider, {}).get("daily", {}).get(today, 0)

    def get_provider_month(self, provider: str) -> float:
        month = str(date.today())[:7]
        return self.data.get("by_provider", {}).get(provider, {}).get("monthly", {}).get(month, 0)

    def get_provider_breakdown(self, scope: str = "monthly") -> dict:
        """{provider: cost} — scope: 'daily'|'monthly'."""
        key = str(date.today()) if scope == "daily" else str(date.today())[:7]
        out = {}
        for prov, d in self.data.get("by_provider", {}).items():
            out[prov] = round(d.get(scope, {}).get(key, 0), 4)
        return out

    def get_model_breakdown(self, scope: str = "monthly") -> dict:
        """{model: cost} — scope: 'daily'|'monthly'."""
        key = str(date.today()) if scope == "daily" else str(date.today())[:7]
        out = {}
        for model, d in self.data.get("by_model", {}).items():
            v = d.get(scope, {}).get(key, 0)
            if v:
                out[model] = round(v, 4)
        return out
