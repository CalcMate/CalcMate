# -*- coding: utf-8 -*-
"""
tests/test_blog_schedule_slots.py
P1 — BLOG_SCHEDULE.publish_slots → Blog Scheduler 연결 테스트

Blog Scheduler가 BLOG_SCHEDULE.publish_slots를
공식 Source of Truth로 사용하는지 검증한다.
"""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _make_cfg(tmp: Path, line: str = "", blog_schedule: dict = None,
              publish_schedule: dict = None) -> dict:
    cfg = {"_root": str(tmp)}
    if line:
        cfg["scheduler_line"] = line
    if blog_schedule:
        cfg["BLOG_SCHEDULE"] = blog_schedule
    if publish_schedule:
        cfg["PUBLISH_SCHEDULE"] = publish_schedule
    return cfg


# ================================================================
# Test 1 — Blog slot source
# ================================================================

class TestBlogSlotSource:
    """Blog Scheduler가 BLOG_SCHEDULE.publish_slots를 사용하는지 검증."""

    def test_blog_reads_publish_slots(self, tmp_path):
        """scheduler_line='blog' → BLOG_SCHEDULE.publish_slots 사용."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "09:00", "end": "09:30"},
                    {"start": "14:00", "end": "14:30"},
                    {"start": "20:00", "end": "20:30"},
                ]
            },
        )
        day_type, slots = get_slots_for(cfg, d=date(2099, 6, 15))  # Sunday
        assert len(slots) == 3
        assert slots[0]["start"] == "09:00"
        assert slots[1]["start"] == "14:00"
        assert slots[2]["start"] == "20:00"

    def test_blog_ignores_publish_schedule(self, tmp_path):
        """Blog 라인이 PUBLISH_SCHEDULE을 무시하는지 검증."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "10:00", "end": "10:30"},
                ]
            },
            publish_schedule={
                "weekday": [{"start": "06:00", "end": "06:30"}],
                "weekend": [{"start": "07:00", "end": "07:30"}],
            },
        )
        day_type, slots = get_slots_for(cfg, d=date(2099, 6, 15))
        # Blog는 publish_slots(10:00)를 사용해야 하고, PUBLISH_SCHEDULE(06:00/07:00)을 무시
        assert slots[0]["start"] == "10:00"

    def test_calculator_ignores_blog_schedule(self, tmp_path):
        """Calculator 라인이 BLOG_SCHEDULE을 무시하는지 검증."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="calculator",
            blog_schedule={
                "publish_slots": [
                    {"start": "10:00", "end": "10:30"},
                ]
            },
            publish_schedule={
                "weekday": [{"start": "06:00", "end": "06:30"}],
                "weekend": [{"start": "07:00", "end": "07:30"}],
            },
        )
        day_type, slots = get_slots_for(cfg, d=date(2099, 6, 17))  # Tuesday
        # Calculator는 PUBLISH_SCHEDULE(06:00)을 사용
        assert slots[0]["start"] == "06:00"


# ================================================================
# Test 2 — Config 변경 반영
# ================================================================

class TestConfigChangeReflection:
    """config 변경 시 Blog schedule이 실제로 변경되는지 검증."""

    def test_config_change_reflected(self, tmp_path):
        """publish_slots 변경 → schedule 변경 반영 확인."""
        from modules.scheduler import get_slots_for

        cfg1 = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "09:00", "end": "09:30"},
                    {"start": "14:00", "end": "14:30"},
                    {"start": "20:00", "end": "20:30"},
                ]
            },
        )
        _, slots1 = get_slots_for(cfg1, d=date(2099, 6, 15))
        assert len(slots1) == 3
        assert slots1[0]["start"] == "09:00"

        cfg2 = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "10:00", "end": "10:30"},
                    {"start": "15:00", "end": "15:30"},
                    {"start": "21:00", "end": "21:30"},
                ]
            },
        )
        _, slots2 = get_slots_for(cfg2, d=date(2099, 6, 15))
        assert len(slots2) == 3
        assert slots2[0]["start"] == "10:00"
        assert slots2[1]["start"] == "15:00"
        assert slots2[2]["start"] == "21:00"


# ================================================================
# Test 3 — Calculator isolation
# ================================================================

class TestCalculatorSlotIsolation:
    """Blog 설정 변경이 Calculator schedule에 영향 없는지 검증."""

    def test_blog_config_does_not_affect_calculator(self, tmp_path):
        """Blog publish_slots 변경 → Calculator schedule 동일 유지."""
        from modules.scheduler import get_slots_for

        base_ps = {
            "weekday": [{"start": "06:00", "end": "06:30"}],
            "weekend": [{"start": "07:00", "end": "07:30"}],
        }

        cfg1 = _make_cfg(
            tmp_path, line="calculator",
            blog_schedule={"publish_slots": [{"start": "09:00", "end": "09:30"}]},
            publish_schedule=base_ps,
        )
        _, calc_slots1 = get_slots_for(cfg1, d=date(2099, 6, 17))

        cfg2 = _make_cfg(
            tmp_path, line="calculator",
            blog_schedule={"publish_slots": [{"start": "22:00", "end": "22:30"}]},
            publish_schedule=base_ps,
        )
        _, calc_slots2 = get_slots_for(cfg2, d=date(2099, 6, 17))

        # Blog 슬롯이 달라도 Calculator는 동일
        assert calc_slots1[0]["start"] == calc_slots2[0]["start"] == "06:00"


# ================================================================
# Test 4 — Empty slots
# ================================================================

class TestEmptySlots:
    """publish_slots가 비어 있을 때 fallback 동작 검증."""

    def test_empty_blog_slots_fallback(self, tmp_path):
        """BLOG_SCHEDULE.publish_slots=[] → 기본 슬롯 생성."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={"publish_slots": []},
        )
        _, slots = get_slots_for(cfg, d=date(2099, 6, 15))
        # 빈 slots → default_slots(1) → 1개 슬롯
        assert len(slots) == 1
        assert "start" in slots[0]
        assert "end" in slots[0]

    def test_missing_blog_schedule_fallback(self, tmp_path):
        """BLOG_SCHEDULE 미설정 → 기본 슬롯 생성."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(tmp_path, line="blog")
        _, slots = get_slots_for(cfg, d=date(2099, 6, 15))
        assert len(slots) == 1

    def test_empty_publish_slots_key_fallback(self, tmp_path):
        """BLOG_SCHEDULE에 publish_slots 키 없음 → 기본 슬롯 생성."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={"mode": "draft"},
        )
        _, slots = get_slots_for(cfg, d=date(2099, 6, 15))
        assert len(slots) == 1


# ================================================================
# Test 5 — Invalid slot handling
# ================================================================

class TestInvalidSlots:
    """잘못된 시간 형식 처리 검증."""

    def test_invalid_time_format_still_generates(self, tmp_path):
        """잘못된 시간 형식 → available_slots가 필터링하거나 기본값 사용."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "25:99", "end": "26:00"},  # 잘못된 시간
                ]
            },
        )
        # get_slots_for 자체는 슬롯을 그대로 반환 (filtering은 available_slots에서 수행)
        _, slots = get_slots_for(cfg, d=date(2099, 6, 15))
        assert len(slots) == 1  # 일단 슬롯은 반환
        assert slots[0]["start"] == "25:99"


# ================================================================
# Test 6 — Schedule output in blog path
# ================================================================

class TestScheduleOutput:
    """Blog Scheduler가 생성하는 today_schedule.json이 Blog 전용 경로에 저장되는지 검증."""

    def test_blog_schedule_in_blog_dir(self, tmp_path):
        """Blog schedule 생성 → data/schedule/blog/ 하위에 저장."""
        from modules.scheduler import generate_today_schedule, _schedule_path
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [
                    {"start": "10:00", "end": "10:30"},
                    {"start": "15:00", "end": "15:30"},
                ]
            },
        )
        sched = generate_today_schedule(cfg, d=date(2099, 6, 15))

        # Blog 전용 경로에 저장되었는지 확인
        sched_path = _schedule_path(cfg)
        assert "blog" in str(sched_path.as_posix())
        assert sched_path.exists()

        # slot 값이 publish_slots와 일치하는지 확인
        pending = [e for e in sched["schedule"] if e["status"] == "pending"]
        assert len(pending) == 2
        # scheduled_time이 10:00~10:30 또는 15:00~15:30 범위 내인지
        for entry in pending:
            t = entry["scheduled_time"]
            h, m = map(int, t.split(":"))
            minutes = h * 60 + m
            assert (600 <= minutes <= 630) or (900 <= minutes <= 930), \
                f"Scheduled time {t} not in expected slots"

    def test_calculator_schedule_not_affected(self, tmp_path):
        """Blog schedule 생성 후 Calculator schedule 경로에 파일 없음."""
        from modules.scheduler import generate_today_schedule, _schedule_path
        cfg_blog = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [{"start": "10:00", "end": "10:30"}]
            },
        )
        generate_today_schedule(cfg_blog, d=date(2099, 6, 15))

        # Calculator 경로에는 파일이 없어야 함
        calc_cfg = _make_cfg(tmp_path)
        calc_path = _schedule_path(calc_cfg)
        assert not calc_path.exists()


# ================================================================
# Test 7 — weekday_only behavior
# ================================================================

class TestWeekdayOnly:
    """weekday_only 옵션이 제대로 동작하는지 검증."""

    def test_weekday_only_on_weekday(self, tmp_path):
        """weekday_only=True + 평일 → 슬롯 있음."""
        from modules.scheduler import get_slots_for
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [{"start": "10:00", "end": "10:30"}],
                "weekday_only": True,
            },
        )
        _, slots = get_slots_for(cfg, d=date(2099, 6, 17))  # Tuesday
        assert len(slots) == 1

    def test_weekday_only_on_weekend(self, tmp_path):
        """weekday_only=True + 주말 → publish_slots 비활성화 → fallback."""
        from modules.scheduler import get_slots_for, default_slots
        cfg = _make_cfg(
            tmp_path, line="blog",
            blog_schedule={
                "publish_slots": [{"start": "10:00", "end": "10:30"}],
                "weekday_only": True,
            },
        )
        _, slots = get_slots_for(cfg, d=date(2099, 6, 14))  # Sunday
        # weekday_only=True且周末 → slots=[] → fallback → default_slots(1)
        expected = default_slots(1)
        assert len(slots) == 1  # fallback
        assert slots[0]["start"] == expected[0]["start"]  # fallback 슬롯과 동일


# ================================================================
# Test 8 — failure_mode
# ================================================================

class TestBlogFailureMode:
    """Blog 라인의 failure_mode 분리 검증."""

    def test_blog_failure_mode_default(self, tmp_path):
        """Blog 라인: BLOG_SCHEDULE.failure_mode 미설정 → 기본값."""
        from modules.scheduler import failure_mode
        cfg = _make_cfg(tmp_path, line="blog", blog_schedule={})
        assert failure_mode(cfg) == "retry_in_slot"

    def test_blog_failure_mode_custom(self, tmp_path):
        """Blog 라인: BLOG_SCHEDULE.failure_mode 설정 시 해당 값 사용."""
        from modules.scheduler import failure_mode
        cfg = _make_cfg(tmp_path, line="blog", blog_schedule={"failure_mode": "none"})
        assert failure_mode(cfg) == "none"

    def test_calculator_failure_mode_independent(self, tmp_path):
        """Calculator 라인: PUBLISH_SCHEDULE.failure_mode 사용."""
        from modules.scheduler import failure_mode
        cfg = _make_cfg(
            tmp_path, line="calculator",
            publish_schedule={"failure_mode": "next_slot"},
        )
        assert failure_mode(cfg) == "next_slot"
