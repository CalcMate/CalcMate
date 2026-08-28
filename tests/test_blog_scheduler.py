# -*- coding: utf-8 -*-
"""
tests/test_blog_scheduler.py — Blog Scheduler Adapter 테스트

검증:
1. BlogScheduleRequest 검증
2. Golden 10 10건 Scheduler Dry-Run
3. Intent별 구조 검증
4. DB 불변성 (article_content hash)
5. WordPress 호출 0
6. Image Pipeline 호출 0
7. isolated output 생성
8. 잘못된 slug/intent 거부
"""
import hashlib
import json
import os
import sqlite3
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def golden10_slugs():
    return [
        "severance-pay", "weekly-holiday-allowance", "unemployment-benefit",
        "four-insurances", "annual-leave-allowance", "severance-pay-documents",
        "육아휴직_급여_계산기", "연말정산_환급액_계산기",
        "unemployment-benefit-howto", "four-insurances-documents",
    ]


@pytest.fixture
def golden10_intents():
    return {
        "severance-pay": "eligibility",
        "weekly-holiday-allowance": "howto",
        "unemployment-benefit": "eligibility",
        "four-insurances": "calculator",
        "annual-leave-allowance": "howto",
        "severance-pay-documents": "documents",
        "육아휴직_급여_계산기": "eligibility",
        "연말정산_환급액_계산기": "calculator",
        "unemployment-benefit-howto": "howto",
        "four-insurances-documents": "documents",
    }


@pytest.fixture
def db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "blog_auto.db")


@pytest.fixture
def cfg():
    """Mock config (no OPENAI_API_KEY = mock path)."""
    return {"MAX_RETRY_COUNT": 1, "QUALITY_GATE": {}, "QUALITY_SCORE": {}}


@pytest.fixture
def golden10_hashes(db_path, golden10_slugs):
    """Golden 10 article_content hash 기록."""
    hashes = {}
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for slug in golden10_slugs:
        c.execute("SELECT article_content FROM calculators WHERE slug=?", (slug,))
        row = c.fetchone()
        if row and row[0]:
            hashes[slug] = hashlib.sha256(row[0].encode()).hexdigest()[:16]
    conn.close()
    return hashes


# ============================================================
# TEST 1: BlogScheduleRequest 검증
# ============================================================

class TestBlogScheduleRequest:
    """BlogScheduleRequest 검증 테스트."""

    def test_valid_request(self):
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        req = BlogScheduleRequest(slug="severance-pay", intent="eligibility")
        errors = req.validate()
        assert errors == [], f"Unexpected errors: {errors}"

    def test_invalid_intent(self):
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        req = BlogScheduleRequest(slug="severance-pay", intent="invalid")
        errors = req.validate()
        assert any("Invalid intent" in e for e in errors)

    def test_empty_slug(self):
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        req = BlogScheduleRequest(slug="", intent="eligibility")
        errors = req.validate()
        assert any("slug is empty" in e for e in errors)

    def test_not_golden10(self):
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        req = BlogScheduleRequest(slug="nonexistent", intent="eligibility")
        errors = req.validate()
        assert any("Not in Golden 10" in e for e in errors)

    def test_intent_mismatch(self):
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        req = BlogScheduleRequest(slug="severance-pay", intent="documents")
        errors = req.validate()
        assert any("Intent mismatch" in e for e in errors)

    def test_all_golden10_valid(self, golden10_intents):
        """Golden 10 10건 모두 valid request 생성 가능."""
        from modules.blog_scheduler_adapter import BlogScheduleRequest
        for slug, intent in golden10_intents.items():
            req = BlogScheduleRequest(slug=slug, intent=intent)
            errors = req.validate()
            assert errors == [], f"{slug}/{intent}: {errors}"


# ============================================================
# TEST 2: Golden 10 10건 Scheduler Dry-Run
# ============================================================

class TestGolden10SchedulerDryRun:
    """Golden 10 10건 전체 Scheduler Dry-Run."""

    def test_all_10_produced(self, cfg, golden10_slugs):
        """10건 모두 produced > 0."""
        from modules.blog_scheduler_adapter import run_blog_once
        result = run_blog_once(cfg, max_count=10)
        assert result["produced"] == 10, f"Expected 10, got {result['produced']}"
        assert result["reason"] == ""

    def test_all_10_success(self, cfg):
        """10건 모두 SUCCESS 상태."""
        from modules.blog_scheduler_adapter import run_blog_once
        result = run_blog_once(cfg, max_count=10)
        for r in result["results"]:
            assert r["status"] == "SUCCESS", f"{r['slug']}: {r['status']}"

    def test_no_db_write(self, cfg):
        """DB write = 0."""
        from modules.blog_scheduler_adapter import run_blog_once
        result = run_blog_once(cfg, max_count=10)
        assert result.get("db_write", 0) == 0

    def test_no_wp_call(self, cfg):
        """WordPress call = 0."""
        from modules.blog_scheduler_adapter import run_blog_once
        result = run_blog_once(cfg, max_count=10)
        assert result.get("wordpress_call", 0) == 0

    def test_no_image_call(self, cfg):
        """Image call = 0."""
        from modules.blog_scheduler_adapter import run_blog_once
        result = run_blog_once(cfg, max_count=10)
        assert result.get("image_call", 0) == 0

    def test_isolated_output_created(self, cfg):
        """isolated output 디렉토리에 10건 생성."""
        from modules.blog_scheduler_adapter import run_blog_once, _output_dir
        run_blog_once(cfg, max_count=10)
        out = _output_dir(cfg)
        created = [d.name for d in out.iterdir() if d.is_dir() and d.name != "__pycache__"]
        assert len(created) >= 10, f"Expected >=10 dirs, got {len(created)}"


# ============================================================
# TEST 3: DB 불변성
# ============================================================

class TestDBInvariance:
    """Scheduler Dry-Run 후 DB 변경 없음."""

    def test_article_content_hash_unchanged(self, cfg, golden10_hashes):
        """Golden 10 article_content hash가 동일."""
        from modules.blog_scheduler_adapter import run_blog_once
        run_blog_once(cfg, max_count=10)

        conn = sqlite3.connect(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "blog_auto.db"))
        c = conn.cursor()
        for slug, expected_hash in golden10_hashes.items():
            c.execute("SELECT article_content FROM calculators WHERE slug=?", (slug,))
            row = c.fetchone()
            if row and row[0]:
                actual_hash = hashlib.sha256(row[0].encode()).hexdigest()[:16]
                assert actual_hash == expected_hash, \
                    f"{slug} content changed: {expected_hash} → {actual_hash}"
        conn.close()


# ============================================================
# TEST 4: Intent별 구조 검증
# ============================================================

class TestIntentStructure:
    """각 intent별 H2 구조 검증."""

    def test_eligibility_structure(self, cfg):
        """eligibility → 지급 대상 / 근로시간 조건 / 제외 대상 포함."""
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "severance-pay", "eligibility")
        assert result["success"]
        import re
        html = open(result["result"]["output"], encoding="utf-8").read()
        h2s = [re.sub(r'<[^>]+>', '', h).strip()
               for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)]
        assert any("지급 대상" in h or "대상" in h for h in h2s), \
            f"eligibility missing '지급 대상': {h2s}"

    def test_howto_structure(self, cfg):
        """howto → 이용 절차 포함."""
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "weekly-holiday-allowance", "howto")
        assert result["success"]
        import re
        html = open(result["result"]["output"], encoding="utf-8").read()
        h2s = [re.sub(r'<[^>]+>', '', h).strip()
               for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)]
        assert any("이용 절차" in h or "절차" in h for h in h2s), \
            f"howto missing '이용 절차': {h2s}"

    def test_documents_structure(self, cfg):
        """documents → 필수 서류 포함."""
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "severance-pay-documents", "documents")
        assert result["success"]
        import re
        html = open(result["result"]["output"], encoding="utf-8").read()
        h2s = [re.sub(r'<[^>]+>', '', h).strip()
               for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)]
        assert any("서류" in h for h in h2s), \
            f"documents missing '서류': {h2s}"

    def test_calculator_structure(self, cfg):
        """calculator → 계산 원리 포함."""
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "four-insurances", "calculator")
        assert result["success"]
        import re
        html = open(result["result"]["output"], encoding="utf-8").read()
        h2s = [re.sub(r'<[^>]+>', '', h).strip()
               for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)]
        assert any("계산" in h for h in h2s), \
            f"calculator missing '계산': {h2s}"


# ============================================================
# TEST 5: 단일 Dry-Run
# ============================================================

class TestSingleDryRun:
    """단일 콘텐츠 Dry-Run."""

    def test_severance_pay_dry_run(self, cfg):
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "severance-pay", "eligibility")
        assert result["success"]
        assert result["result"]["article_len"] > 0
        assert result["result"]["protection_ok"] is True

    def test_single_invalid_slug(self, cfg):
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "nonexistent", "eligibility")
        assert not result["success"]
        assert any("Golden 10" in e for e in result["errors"])

    def test_single_invalid_intent(self, cfg):
        from modules.blog_scheduler_adapter import run_blog_dry_run
        result = run_blog_dry_run(cfg, "severance-pay", "bogus")
        assert not result["success"]
        assert any("Invalid intent" in e for e in result["errors"])


# ============================================================
# TEST 6: Calculator line 분리
# ============================================================

class TestCalculatorLineSeparation:
    """Blog adapter가 calculator write path를 호출하지 않음."""

    def test_no_db_write_in_blog_line(self, cfg):
        """Blog line이 calculators 테이블을 수정하지 않음."""
        from modules.blog_scheduler_adapter import run_blog_once
        import hashlib
        import sqlite3

        # 실행 전 DB hash
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "blog_auto.db")
        before = hashlib.md5(open(db_path, "rb").read()).hexdigest()

        result = run_blog_once(cfg, max_count=10)

        # 실행 후 DB hash
        after = hashlib.md5(open(db_path, "rb").read()).hexdigest()
        assert before == after, f"DB changed: {before} → {after}"
        assert result.get("db_write", 0) == 0


# ============================================================
# TEST 7: Golden 10 hash 불변성 (run_blog_once 후)
# ============================================================

class TestGolden10HashAfterRun:
    """Scheduler Dry-Run 후 Golden 10 hash 불변."""

    def test_hash_unchanged_after_full_run(self, cfg, golden10_hashes):
        from modules.blog_scheduler_adapter import run_blog_once
        run_blog_once(cfg, max_count=10)

        conn = sqlite3.connect(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "blog_auto.db"))
        c = conn.cursor()
        for slug, expected in golden10_hashes.items():
            c.execute("SELECT article_content FROM calculators WHERE slug=?", (slug,))
            row = c.fetchone()
            if row and row[0]:
                actual = hashlib.sha256(row[0].encode()).hexdigest()[:16]
                assert actual == expected, f"{slug}: {expected} → {actual}"
        conn.close()
