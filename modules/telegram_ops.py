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

# 이벤트별 ON/OFF 게이팅. config.yaml의 TELEGRAM_EVENTS(dict)로 제어.
# 미설정 시 기본 True(하위호환 — 기존 동작 유지).
EVENT_KEYS = ("error", "budget", "daily_summary", "publish_request", "quality_critical_hold",
              "publish_success")


def _enabled(cfg: dict, event: str) -> bool:
    """해당 이벤트 알림이 켜져 있는지. 설정 없으면 True(기본 ON)."""
    return bool((cfg.get("TELEGRAM_EVENTS") or {}).get(event, True))


def notify_error(cfg: dict, where: str, err) -> None:
    if not _enabled(cfg, "error"):
        return
    TN.send(cfg, f"❌ [오류] {where}\n{str(err)[:300]}")


def notify_budget(cfg: dict, used: float, limit: float, level: str = "warn") -> None:
    if not _enabled(cfg, "budget"):
        return
    pct = (used / limit * 100) if limit else 0
    icon = "⛔" if level == "stop" else "⚠️"
    msg = ("일 예산 한도 도달 — 자동 일시정지" if level == "stop"
           else "일 예산 80% 도달 — 주의")
    TN.send(cfg, f"{icon} [예산] {msg}\n사용 ${used:.3f} / ${limit} ({pct:.0f}%)")


def daily_summary(cfg: dict, stats: dict) -> None:
    """stats: {published, failed, cost, tokens, ...}"""
    if not _enabled(cfg, "daily_summary"):
        return
    TN.send(cfg, (
        f"📊 [일일 요약] {date.today().isoformat()}\n"
        f"발행 {stats.get('published', 0)} · 실패 {stats.get('failed', 0)} · "
        f"대기 {stats.get('pending', 0)}\n"
        f"오늘 비용 ${stats.get('cost', 0):.3f} · 토큰 {stats.get('tokens', 0):,}"
    ))


def notify_publish_request(cfg: dict, title: str, url: str = "") -> None:
    if not _enabled(cfg, "publish_request"):
        return
    TN.send(cfg, f"📝 [발행 승인 요청] {title}\n{url}".strip())


def notify_quality_hold(cfg: dict, name: str, slug: str = "",
                        critical_gates=None, last_at: str = "") -> None:
    """Critical 반복실패로 품질 HOLD된 계산기 알림(작업지시서 C)."""
    if not _enabled(cfg, "quality_critical_hold"):
        return
    gates = ", ".join(critical_gates or []) or "-"
    TN.send(cfg, (
        f"🚫 [품질 HOLD] Critical 반복실패로 발행 보류\n"
        f"계산기: {name} ({slug})\n"
        f"미해결 Critical Gate: {gates}\n"
        f"마지막 시도: {last_at}\n"
        f"상태: 품질보류 (자동 재도전 대상 — 프롬프트 개선 시 재평가)"
    ))


def notify_publish_success(cfg: dict, site: str = "", calculator: str = "", keyword: str = "",
                           title: str = "", published_at: str = "", url: str = "") -> None:
    """정상 발행 완료 알림(개발/테스트 편의). 'publish_success' 이벤트로 게이팅 —
    운영 전환 시 config에서 publish_success=false로 끄면 절대 발송하지 않는다(코드 분기 없이 설정 기반).
    URL이 없으면 해당 줄을 생략한다."""
    if not _enabled(cfg, "publish_success"):
        return
    lines = ["✅ 발행 완료", ""]
    for label, value in (("사이트", site), ("계산기", calculator), ("키워드", keyword),
                         ("제목", title), ("발행시간", published_at), ("URL", url)):
        if value:
            lines += [label, str(value), ""]
    TN.send(cfg, "\n".join(lines).rstrip())


def notify(cfg: dict, message: str) -> None:
    TN.send(cfg, message)


# 알림 레벨 표준(Sprint 1 §4). INFO/WARNING/ERROR/CRITICAL.
_LEVEL_ICON = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}


def notify_level(cfg: dict, level: str, title: str, detail="", event: str = "error") -> None:
    """레벨(INFO/WARNING/ERROR/CRITICAL) + 이벤트키 게이팅 표준 알림.

    Sprint 1에서 추가되는 모든 운영 알림의 단일 진입점(raw send 직접호출 금지).
      - event: TELEGRAM_EVENTS 게이팅 키(미설정 시 ON=기본). 신규 알림은 기존 키에 매핑:
          · 자동화 정지/루프 예외/스레드 종료 → "error"
          · 품질 HOLD(legal 미검증 / 재시도 한도 초과) → "quality_critical_hold"
          · 예산 초과 → "budget"
    메시지 형식: "<아이콘> [LEVEL] title\n detail"
    """
    if not _enabled(cfg, event):
        return
    icon = _LEVEL_ICON.get(str(level).upper(), "")
    body = f"{icon} [{str(level).upper()}] {title}".strip()
    if detail:
        body += f"\n{str(detail)[:400]}"
    TN.send(cfg, body)
