# -*- coding: utf-8 -*-
"""tests/test_image_pipeline_p3.py — P3 검증

콘텐츠 데이터 → Topic DNA resolver → ImageJob → Pollinations(P2) → image_pipeline → QA.
실제 HTTP/WordPress 호출 없음 (전부 mock/검증).
"""
import io
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from image_pipeline import content_connector as cc  # noqa: E402
from image_pipeline.content_connector import (  # noqa: E402
    ImageJob,
    ImageStatus,
    build_image_job,
    extract_topic_from_content,
    resolve_topic_key,
    run_image_job,
)

REQ_JSON = BASE / "data" / "phase5-c" / "requests" / "08_연말정산_환급액_계산기_calculator.json"


def _fake_png_bytes(size: int = 512) -> bytes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (size // 2, size // 2), (30, 120, 200, 255)), (size // 4, size // 4))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResp:
    def __init__(self, status_code: int = 200, content: bytes = b""):
        self.status_code = status_code
        self.content = content


def _mock_requests(monkeypatch, sequence: list[tuple[str, int, bytes]]):
    state = {"i": 0, "kinds": []}

    def fake_get(url, timeout=60):
        i = state["i"]
        if i >= len(sequence):
            raise AssertionError(f"예상치 못한 HTTP 호출: {url}")
        kind, code, content = sequence[i]
        state["i"] += 1
        state["kinds"].append(kind)
        return _FakeResp(code, content)

    monkeypatch.setattr("image_pipeline.pollinations_provider.requests.get", fake_get)
    return state


# ── Test 1: Content topic → Topic DNA resolver ─────────────────────

def test_resolve_topic_key_aliases():
    assert resolve_topic_key("severance-pay") == "severance"
    assert resolve_topic_key("weekly-holiday-allowance") == "weekly_holiday"
    assert resolve_topic_key("unemployment-benefit") == "unemployment_benefit"
    assert resolve_topic_key("annual-leave-allowance") == "annual_leave"
    assert resolve_topic_key("연말정산_환급액_계산기") == "yearend_tax"
    assert resolve_topic_key("퇴직금") == "severance"
    assert resolve_topic_key("yearend_tax") == "yearend_tax"


def test_extract_topic_from_content():
    data = {"slug": "severance-pay", "calculator_id": "calc_x"}
    assert extract_topic_from_content(data) == "severance"
    data2 = {"calc_name": "연말정산 환급액 계산기"}
    with pytest.raises(ValueError):
        extract_topic_from_content(data2)  # 정확한 표시명 아님 → unknown


# ── Test 2: valid topic → ImageJob 생성 ────────────────────────────

def test_build_image_job_valid():
    job = build_image_job("severance-pay", calculator_id="calc_1", title="퇴직금 가이드",
                          generate_assets=True)
    assert job.topic_key == "severance"
    assert job.calculator_id == "calc_1"
    assert job.title == "퇴직금 가이드"
    assert job.generate_assets is True
    assert job.force_assets is False


# ── Test 3: pending topic → 이미지 생성 차단 ───────────────────────

def test_pending_topic_blocked(tmp_path, monkeypatch):
    _mock_requests(monkeypatch, [])  # HTTP 호출 금지
    job = ImageJob(topic_key="weekly_holiday", output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_PENDING
    assert result.all_qa_ok is False
    assert "pending" in (result.error or "")
    # build_image_job도 pending을 차단
    with pytest.raises(ValueError):
        build_image_job("weekly_holiday")


# ── Test 4: Content → Pollinations adapter 연결 ────────────────────

def test_content_to_pollinations_adapter(tmp_path, monkeypatch):
    """generate_assets=True → P2 Provider 호출 → raw 생성."""
    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job("yearend_tax", generate_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert (tmp_path / "raw" / "yearend_tax" / "character.png").exists()


# ── Test 5: 기존 raw asset 재사용 ──────────────────────────────────

def test_asset_reuse_no_api_call(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "yearend_tax"
    raw.mkdir(parents=True)
    (raw / "character.png").write_bytes(_fake_png_bytes())
    state = _mock_requests(monkeypatch, [])  # 호출 금지
    job = build_image_job("yearend_tax", generate_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert state["kinds"] == []


# ── Test 6: force-assets 동작 ──────────────────────────────────────

def test_force_assets_regenerates(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "yearend_tax"
    raw.mkdir(parents=True)
    (raw / "character.png").write_bytes(_fake_png_bytes())
    state = _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job("yearend_tax", generate_assets=True, force_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert state["kinds"] == ["character"]


# ── Test 7: Image Pipeline 호출 ────────────────────────────────────

def test_image_pipeline_call_ready(tmp_path, monkeypatch):
    """run_image_job → Master/Body/Thumbnail + QA → IMAGE_READY."""
    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job("yearend_tax", generate_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert result.all_qa_ok is True
    assert Image.open(result.files["master"]).size == (1920, 1080)
    assert Image.open(result.files["body"]).size == (800, 450)
    assert Image.open(result.files["thumb"]).size == (512, 512)


# ── Test 8: QA failure propagation ─────────────────────────────────

def test_qa_failure_propagates(tmp_path, monkeypatch):
    """final QA 실패는 IMAGE_FAILED로 전파 (성공으로 기록 금지)."""
    import image_pipeline.pipeline as pipe_mod

    def broken_qa(path, expect_size):
        return {"path": str(path), "size": (0, 0), "size_ok": False}

    monkeypatch.setattr(pipe_mod.compositor, "qa_image", broken_qa)
    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job("yearend_tax", generate_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_FAILED
    assert result.all_qa_ok is False
    assert "QA" in (result.error or "")


# ── Test 9: unknown topic 처리 ─────────────────────────────────────

def test_unknown_topic():
    with pytest.raises(ValueError, match="unknown topic"):
        resolve_topic_key("four-insurances")
    with pytest.raises(ValueError, match="unknown topic"):
        resolve_topic_key("calc_20260805121653_0065")  # 불투명 calculator_id

    result = run_image_job(ImageJob(topic_key="four-insurances"))
    assert result.status == ImageStatus.IMAGE_FAILED
    assert "unknown topic" in (result.error or "")


# ── Test 10: WordPress 호출 미발생 ─────────────────────────────────

def test_no_wordpress_usage(tmp_path, monkeypatch):
    """커넥터는 WordPress/Publisher/Gutenberg에 연결하지 않는다.

    sys.modules는 다른 테스트가 content_pipeline(wordpress 계열)을 이미
    import했을 수 있어 신뢰할 수 없으므로, 커넥터 실행 경로 모듈들의
    소스에 content_pipeline/wp 관련 호출이 없는지 검증한다.
    """
    for fname in ("content_connector.py", "pipeline.py", "pollinations_provider.py",
                  "svg_template.py", "compositor.py", "asset_processor.py"):
        src = (BASE / "image_pipeline" / fname).read_text(encoding="utf-8")
        assert "content_pipeline" not in src, f"{fname}에 content_pipeline 참조"
        assert "wp-json" not in src.lower()
        assert "upload_media" not in src
        assert "wp/v2" not in src.lower()
        assert "gutenberg" not in src.lower()

    # 커넥터 E2E가 정상 동작하는지 (WordPress 경유 없이 로컬 파일+QA까지만)
    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job("yearend_tax", generate_assets=True,
                          raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
                          output_dir=tmp_path / "out")
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert set(result.files) == {"master", "body", "thumb"}


# ── E2E: 실제 콘텐츠 request 1건 ───────────────────────────────────

@pytest.mark.skipif(not REQ_JSON.exists(), reason="콘텐츠 request JSON 없음")
def test_real_content_request_e2e(tmp_path, monkeypatch):
    """data/phase5-c/requests의 실제 콘텐츠 1건 → 이미지 생산 전체 체인."""
    data = __import__("json").loads(REQ_JSON.read_text(encoding="utf-8"))
    topic = extract_topic_from_content(data)
    assert topic == "yearend_tax"

    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    job = build_image_job(
        topic,
        calculator_id=str(data.get("calculator_id", "")),
        title=str((data.get("seo") or {}).get("seo_title", "")),
        generate_assets=True,
        raw_assets_dir=tmp_path / "raw", assets_dir=tmp_path / "assets",
        output_dir=tmp_path / "out",
    )
    result = run_image_job(job)
    assert result.status == ImageStatus.IMAGE_READY
    assert result.all_qa_ok is True
    assert len(result.files) == 3


# ── CLI ────────────────────────────────────────────────────────────

def test_content_connector_cli_help():
    proc = subprocess.run(
        [sys.executable, "-m", "image_pipeline.content_connector", "--help"],
        capture_output=True, text=True, cwd=BASE,
    )
    assert proc.returncode == 0
    for flag in ("--request", "--slug", "--out", "--assets", "--raw-assets",
                 "--generate-assets", "--force-assets"):
        assert flag in proc.stdout
