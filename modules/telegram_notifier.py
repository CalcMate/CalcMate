"""
telegram_notifier.py — 텔레그램 알림 발송
"""
import requests
from .logger import get_logger

LOG = get_logger()


def send(cfg: dict, message: str):
    token = cfg.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = cfg.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"[블로그자동화]\n{message}"},
            timeout=5,
        )
    except Exception as e:
        # 알림 실패가 파이프라인을 막지 않도록 흡수하되, 원인은 반드시 기록
        LOG.warning("텔레그램 알림 발송 실패: %s", e,
                    exc_info=(cfg.get("LOG_LEVEL", "INFO") == "DEBUG"))
