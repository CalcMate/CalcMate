# -*- coding: utf-8 -*-
"""
modules/telegram_ops.py — 텔레그램 운영 알림 고도화 (v12 Lite, 신규)

기존 telegram_notifier.send()를 그대로 재사용(원본 미변경).
오류 알림 / 예산 경고 / 일일 요약 / 발행 승인 요청 메시지를 표준화.
키 미설정 시 telegram_notifier가 알아서 무동작(graceful).
"""
from datetime import date

from . import telegram_notifier as TN
from .logger import get_logger

LOG = get_logger()


def notify_error(cfg: dict, where: str, err) -> None:
    TN.send(cfg, f"❌ [오류] {where}\n{str(err)[:300]}")


def notify_budget(cfg: dict, used: float, limit: float, level: str = "warn") -> None:
    pct = (used / limit * 100) if limit else 0
    icon = "⛔" if level == "stop" else "⚠️"
    msg = ("일 예산 한도 도달 — 자동 일시정지" if level == "stop"
           else "일 예산 80% 도달 — 주의")
    TN.send(cfg, f"{icon} [예산] {msg}\n사용 ${used:.3f} / ${limit} ({pct:.0f}%)")


def daily_summary(cfg: dict, stats: dict) -> None:
    """stats: {published, failed, cost, tokens, ...}"""
    TN.send(cfg, (
        f"📊 [일일 요약] {date.today().isoformat()}\n"
        f"발행 {stats.get('published', 0)} · 실패 {stats.get('failed', 0)} · "
        f"대기 {stats.get('pending', 0)}\n"
        f"오늘 비용 ${stats.get('cost', 0):.3f} · 토큰 {stats.get('tokens', 0):,}"
    ))


def notify_publish_request(cfg: dict, title: str, url: str = "") -> None:
    TN.send(cfg, f"📝 [발행 승인 요청] {title}\n{url}".strip())


def notify(cfg: dict, message: str) -> None:
    TN.send(cfg, message)
