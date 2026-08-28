# -*- coding: utf-8 -*-
"""
tests/test_scheduler_line_isolation.py
P1 — Calculator/Blog Scheduler 라인별 상태 격리 테스트

lock / today_schedule.json / history.jsonl 가
Calculator vs Blog 라인에서 독립적으로 동작하는지 검증한다.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _make_cfg(tmp: Path, line: str = "") -> dict:
    """테스트용 cfg — _root를 tmp로 설정하여 실제 프로젝트 파일 건드리지 않음."""
    cfg = {"_root": str(tmp)}
    if line:
        cfg["scheduler_line"] = line
    return cfg


def _posix(path) -> str:
    """Path를 POSIX 문자열로 변환 (크로스 플랫폼 테스트용)."""
    return Path(path).as_posix()


# ================================================================
# Test 1 — Path isolation: Calculator vs Blog
# ================================================================

class TestSchedulerPathIsolation:
    """Calculator/Blog 라인이 서로 다른 lock/schedule/history 경로를 사용하는지 검증."""

    def test_calculator_paths(self, tmp_path):
        """scheduler_line 미설정(기본=calculator) → data/schedule/ 하위 파일 사용."""
        from modules.scheduler import _lock_path, _schedule_path, _history_path
        cfg = _make_cfg(tmp_path)
        assert _posix(_lock_path(cfg)).endswith("data/schedule/scheduler.lock")
        assert _posix(_schedule_path(cfg)).endswith("data/schedule/today_schedule.json")
        assert _posix(_history_path(cfg)).endswith("data/schedule/history.jsonl")

    def test_blog_paths(self, tmp_path):
        """scheduler_line='blog' → data/schedule/blog/ 하위 파일 사용."""
        from modules.scheduler import _lock_path, _schedule_path, _history_path
        cfg = _make_cfg(tmp_path, line="blog")
        assert _posix(_lock_path(cfg)).endswith("data/schedule/blog/scheduler.lock")
        assert _posix(_schedule_path(cfg)).endswith("data/schedule/blog/today_schedule.json")
        assert _posix(_history_path(cfg)).endswith("data/schedule/blog/history.jsonl")

    def test_calculator_and_blog_paths_are_different(self, tmp_path):
        """Calculator와 Blog의 lock/schedule/history 경로가 모두 다름을 검증."""
        from modules.scheduler import _lock_path, _schedule_path, _history_path
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")
        assert _lock_path(calc_cfg) != _lock_path(blog_cfg)
        assert _schedule_path(calc_cfg) != _schedule_path(blog_cfg)
        assert _history_path(calc_cfg) != _history_path(blog_cfg)

    def test_calculator_dir_is_parent_of_blog_dir(self, tmp_path):
        """Blog 디렉토리는 Calculator 디렉토리의 하위여야 한다 (기존 구조 유지)."""
        from modules.scheduler import _schedule_dir
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")
        calc_dir = _schedule_dir(calc_cfg)
        blog_dir = _schedule_dir(blog_cfg)
        assert blog_dir.parent == calc_dir


# ================================================================
# Test 2 — Write isolation: Calculator write → Blog unchanged
# ================================================================

class TestSchedulerWriteIsolation:
    """한 라인이 lock/schedule/history를 써도 다른 라인 파일이 변경되지 않음을 검증."""

    def test_calculator_lock_does_not_create_blog_lock(self, tmp_path):
        """Calculator lock 생성 → Blog lock 경로에 파일 없음."""
        from modules.scheduler import _lock_path, _acquire_lock, _release_lock
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        blog_lock = _lock_path(blog_cfg)
        assert not blog_lock.exists()

        acquired = _acquire_lock(calc_cfg)
        assert acquired, "Calculator lock 획득 실패"
        try:
            # Blog lock 경로에 파일이 없어야 함
            assert not blog_lock.exists(), \
                "Calculator lock이 Blog lock 경로를 생성함 — 격리 실패"
        finally:
            _release_lock(calc_cfg)

    def test_blog_lock_does_not_create_calculator_lock(self, tmp_path):
        """Blog lock 생성 → Calculator lock 경로에 파일 없음."""
        from modules.scheduler import _lock_path, _acquire_lock, _release_lock
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        calc_lock = _lock_path(calc_cfg)
        assert not calc_lock.exists()

        acquired = _acquire_lock(blog_cfg)
        assert acquired, "Blog lock 획득 실패"
        try:
            assert not calc_lock.exists(), \
                "Blog lock이 Calculator lock 경로를 생성함 — 격리 실패"
        finally:
            _release_lock(blog_cfg)

    def test_calculator_schedule_write_does_not_affect_blog(self, tmp_path):
        """Calculator schedule 저장 → Blog schedule 파일 없음."""
        from modules.scheduler import _schedule_path, save_schedule
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        blog_sched = _schedule_path(blog_cfg)
        assert not blog_sched.exists()

        test_sched = {"date": "2099-01-01", "schedule": []}
        save_schedule(calc_cfg, test_sched)

        assert not blog_sched.exists(), \
            "Calculator schedule 저장이 Blog schedule 경로에 영향 — 격리 실패"

    def test_blog_schedule_write_does_not_affect_calculator(self, tmp_path):
        """Blog schedule 저장 → Calculator schedule 파일 없음."""
        from modules.scheduler import _schedule_path, save_schedule
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        calc_sched = _schedule_path(calc_cfg)
        assert not calc_sched.exists()

        test_sched = {"date": "2099-01-01", "schedule": []}
        save_schedule(blog_cfg, test_sched)

        assert not calc_sched.exists(), \
            "Blog schedule 저장이 Calculator schedule 경로에 영향 — 격리 실패"

    def test_calculator_history_write_does_not_affect_blog(self, tmp_path):
        """Calculator history 기록 → Blog history 파일 없음."""
        from modules.scheduler import _history_path
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        blog_hist = _history_path(blog_cfg)
        assert not blog_hist.exists()

        # Calculator history에 직접 기록
        calc_hist = _history_path(calc_cfg)
        with open(calc_hist, "w", encoding="utf-8") as f:
            f.write(json.dumps({"test": "calc_only"}) + "\n")

        assert not blog_hist.exists(), \
            "Calculator history가 Blog history 경로에 기록됨 — 격리 실패"

    def test_blog_history_write_does_not_affect_calculator(self, tmp_path):
        """Blog history 기록 → Calculator history 파일 없음."""
        from modules.scheduler import _history_path
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        calc_hist = _history_path(calc_cfg)
        assert not calc_hist.exists()

        blog_hist = _history_path(blog_cfg)
        with open(blog_hist, "w", encoding="utf-8") as f:
            f.write(json.dumps({"test": "blog_only"}) + "\n")

        assert not calc_hist.exists(), \
            "Blog history가 Calculator history 경로에 기록됨 — 격리 실패"


# ================================================================
# Test 3 — Concurrent lock isolation
# ================================================================

class TestConcurrentLockIsolation:
    """Calculator와 Blog가 동시에 각각의 lock을 독립적으로 획득할 수 있는지 검증."""

    def test_both_can_acquire_lock_simultaneously(self, tmp_path):
        """Calculator lock과 Blog lock을 동시에 획득 가능해야 한다."""
        from modules.scheduler import _lock_path, _acquire_lock, _release_lock
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        calc_acquired = _acquire_lock(calc_cfg)
        blog_acquired = _acquire_lock(blog_cfg)

        assert calc_acquired, "Calculator lock 획득 실패"
        assert blog_acquired, "Blog lock 획득 실패 — 동시 lock 불가"

        # 각각의 lock 파일이 존재하는지 확인
        assert _lock_path(calc_cfg).exists()
        assert _lock_path(blog_cfg).exists()

        # 각각 독립적으로 해제
        _release_lock(calc_cfg)
        _release_lock(blog_cfg)

    def test_releasing_one_lock_does_not_release_the_other(self, tmp_path):
        """한 라인의 lock 해제가 다른 라인의 lock에 영향 없음을 검증."""
        from modules.scheduler import _lock_path, _acquire_lock, _release_lock
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        _acquire_lock(calc_cfg)
        _acquire_lock(blog_cfg)

        _release_lock(calc_cfg)

        # Calculator lock은 해제됨
        assert not _lock_path(calc_cfg).exists()
        # Blog lock은 여전히 유지됨
        assert _lock_path(blog_cfg).exists(), \
            "Calculator lock 해제가 Blog lock에 영향 — 격리 실패"

        _release_lock(blog_cfg)


# ================================================================
# Test 4 — schedule generation isolation
# ================================================================

class TestScheduleGenerationIsolation:
    """Calculator와 Blog가 독립적으로 schedule을 생성하고 로드하는지 검증."""

    def test_generate_does_not_cross_lines(self, tmp_path):
        """Calculator schedule 생성 → Blog schedule 경로에 파일 없음."""
        from modules.scheduler import generate_today_schedule, load_schedule, _schedule_path
        from datetime import date
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        blog_sched_path = _schedule_path(blog_cfg)
        assert not blog_sched_path.exists()

        # Calculator schedule 생성
        generate_today_schedule(calc_cfg, d=date(2099, 6, 15))

        # Blog schedule 경로에 파일이 없어야 함
        assert not blog_sched_path.exists(), \
            "Calculator schedule 생성이 Blog schedule 경로에 파일 생성 — 격리 실패"

        # Calculator schedule은 정상 로드됨
        sched = load_schedule(calc_cfg)
        assert sched is not None
        assert sched.get("date") == "2099-06-15"

    def test_blog_generate_does_not_affect_calculator(self, tmp_path):
        """Blog schedule 생성 → Calculator schedule 경로에 파일 없음."""
        from modules.scheduler import generate_today_schedule, load_schedule, _schedule_path
        from datetime import date
        calc_cfg = _make_cfg(tmp_path)
        blog_cfg = _make_cfg(tmp_path, line="blog")

        calc_sched_path = _schedule_path(calc_cfg)
        assert not calc_sched_path.exists()

        # Blog schedule 생성
        generate_today_schedule(blog_cfg, d=date(2099, 6, 15))

        # Calculator schedule 경로에 파일이 없어야 함
        assert not calc_sched_path.exists(), \
            "Blog schedule 생성이 Calculator schedule 경로에 파일 생성 — 격리 실패"

        # Blog schedule은 정상 로드됨
        sched = load_schedule(blog_cfg)
        assert sched is not None
        assert sched.get("date") == "2099-06-15"


# ================================================================
# Test 5 — cfg.scheduler_line default behavior
# ================================================================

class TestSchedulerLineDefault:
    """scheduler_line 미설정 시 기존 behavior(Calculator 경로)를 유지하는지 검증."""

    def test_default_line_uses_calculator_path(self, tmp_path):
        """scheduler_line 미설정 → data/schedule/ 사용 (기존行为 유지)."""
        from modules.scheduler import _lock_path, _schedule_path, _history_path
        cfg = _make_cfg(tmp_path)  # no line set
        assert "data/schedule/scheduler.lock" in _posix(_lock_path(cfg))
        assert "data/schedule/today_schedule.json" in _posix(_schedule_path(cfg))
        assert "data/schedule/history.jsonl" in _posix(_history_path(cfg))

    def test_empty_string_line_uses_calculator_path(self, tmp_path):
        """scheduler_line='' → data/schedule/ 사용."""
        from modules.scheduler import _lock_path
        cfg = _make_cfg(tmp_path, line="")
        assert "data/schedule/scheduler.lock" in _posix(_lock_path(cfg))

    def test_unknown_line_uses_calculator_path(self, tmp_path):
        """scheduler_line='unknown' → data/schedule/ 사용 (fallback)."""
        from modules.scheduler import _lock_path
        cfg = _make_cfg(tmp_path, line="unknown")
        assert "data/schedule/scheduler.lock" in _posix(_lock_path(cfg))
