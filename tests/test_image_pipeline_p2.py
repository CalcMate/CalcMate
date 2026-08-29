# -*- coding: utf-8 -*-
"""tests/test_image_pipeline_p2.py — P2 검증

Pollinations Provider(adapter) → raw asset → image_pipeline 연결.
실제 HTTP API는 호출하지 않는다 (requests.get mock). 외부 API 테스트와 분리.
"""
import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from image_pipeline import svg_template  # noqa: E402
from image_pipeline.pollinations_provider import (  # noqa: E402
    PollinationsProvider,
    RawAssetResult,
    build_asset_prompt,
    validate_raw_asset,
)
from image_pipeline.pipeline import CalcImagePipeline  # noqa: E402

REF_ASSETS = BASE / "calcmate_v1_reference" / "assets"


def _fake_png_bytes(size: int = 512, core_alpha: int = 255) -> bytes:
    """불투명 코어 + 투명 배경의 RGBA PNG 바이트 (mock 응답용)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    core = Image.new("RGBA", (size // 2, size // 2), (30, 120, 200, core_alpha))
    img.paste(core, (size // 4, size // 4))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResp:
    def __init__(self, status_code: int = 200, content: bytes = b""):
        self.status_code = status_code
        self.content = content


def _mock_requests(monkeypatch, sequence: list[tuple[str, int, bytes]]):
    """호출 순서대로 응답을 분기한다 (URL은 percent-encoding이라 kind 매칭 불가).

    sequence: [(kind, status_code, content), ...] — 각 토픽의 required 순서
    (DNA assets 순서: character → hero)와 동일하게 소비된다.
    sequence를 모두 소비한 뒤 추가 호출이 있으면 AssertionError.
    """
    state = {"i": 0, "kinds": []}

    def fake_get(url, timeout=60):
        i = state["i"]
        if i >= len(sequence):
            raise AssertionError(f"예상치 못한 HTTP 호출: {url}")
        kind, code, content = sequence[i]
        state["i"] += 1
        state["kinds"].append(kind)
        if code == -1:  # 요청 자체가 호출되면 안 되는 경우
            raise AssertionError(f"예상치 못한 HTTP 호출: {kind}")
        return _FakeResp(code, content)

    monkeypatch.setattr("image_pipeline.pollinations_provider.requests.get", fake_get)
    return state


# ── Test 1: RawAssetResult 구조 ────────────────────────────────────

def test_raw_asset_result_structure():
    r = RawAssetResult(topic_key="yearend_tax",
                       character_path=Path("raw/yearend_tax/character.png"))
    assert r.topic_key == "yearend_tax"
    assert r.character_path.name == "character.png"
    assert r.hero_path is None
    assert r.paths()["character"] == r.character_path


# ── Test 2: raw asset 저장 경로 + 검증 ─────────────────────────────

def test_provider_saves_to_raw_assets_topic_structure(tmp_path, monkeypatch):
    state = _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    provider = PollinationsProvider(raw_assets_dir=tmp_path / "raw")
    result = provider.generate_topic_assets("yearend_tax")

    path = tmp_path / "raw" / "yearend_tax" / "character.png"
    assert path.exists()
    assert path.stat().st_size > 0
    assert result.character_path == path
    assert state["kinds"] == ["character"]
    assert result.hero_path is None


def test_validate_raw_asset(tmp_path):
    ok = tmp_path / "ok.png"
    ok.write_bytes(_fake_png_bytes())
    assert validate_raw_asset(ok) == (True, "ok")

    assert validate_raw_asset(tmp_path / "missing.png") == (False, "파일 없음")

    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert validate_raw_asset(empty) == (False, "빈 파일")

    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not-an-image-data")
    ok_flag, msg = validate_raw_asset(corrupt)
    assert not ok_flag and "이미지 로드 실패" in msg


# ── Test 3: prompt 구성 ────────────────────────────────────────────

def test_build_asset_prompt():
    dna = svg_template.TOPIC_DNA["yearend_tax"]
    cp = build_asset_prompt(dna, "character")
    assert "남성 직장인" in cp
    assert "텍스트 없음" in cp and "워터마크 없음" in cp
    hp = build_asset_prompt(dna, "hero")
    assert "계산기" in hp or "봉투" in hp


# ── Test 4: invalid asset 거부 / 재생성 ────────────────────────────

def test_provider_rejects_corrupt_existing_and_regenerates(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "yearend_tax"
    raw.mkdir(parents=True)
    (raw / "character.png").write_bytes(b"corrupt-data")  # 존재하지만 손상

    state = _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    provider = PollinationsProvider(raw_assets_dir=tmp_path / "raw")
    provider.generate_topic_assets("yearend_tax")  # 손상 → 재생성
    assert state["kinds"] == ["character"]
    assert validate_raw_asset(raw / "character.png") == (True, "ok")


# ── Test 5: partial asset 처리 ─────────────────────────────────────

def test_provider_partial_asset_raises(tmp_path, monkeypatch):
    """character 성공 / hero 실패 → 전체 실패로 처리 (부분 생산 금지)."""
    _mock_requests(monkeypatch, [
        ("character", 200, _fake_png_bytes()),
        ("hero", 500, b""),
    ])
    provider = PollinationsProvider(raw_assets_dir=tmp_path / "raw")
    with pytest.raises(RuntimeError, match="HTTP 500"):
        provider.generate_topic_assets("severance")
    # character raw는 남지만 이미지 생산은 진행되지 않는다 (호출부가 예외로 중단)


# ── Test 6: 중복 생성 방지 / force 재생성 ─────────────────────────

def test_provider_reuses_valid_asset_and_force_regenerates(tmp_path, monkeypatch):
    raw = tmp_path / "raw" / "yearend_tax"
    raw.mkdir(parents=True)
    (raw / "character.png").write_bytes(_fake_png_bytes())  # 유효한 기존 raw

    _mock_requests(monkeypatch, [])  # 호출 금지 (sequence 비움)
    provider = PollinationsProvider(raw_assets_dir=tmp_path / "raw")
    provider.generate_topic_assets("yearend_tax")  # force=False → 재사용

    state = _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    provider.generate_topic_assets("yearend_tax", force=True)  # 강제 재생성
    assert state["kinds"] == ["character"]


def test_unverified_topic_not_generated(tmp_path, monkeypatch):
    """미검증 주제(pending)는 자동 생성되지 않는다."""
    _mock_requests(monkeypatch, [])
    provider = PollinationsProvider(raw_assets_dir=tmp_path / "raw")
    with pytest.raises(ValueError):
        provider.generate_topic_assets("weekly_holiday")


# ── Test 7: raw asset → image_pipeline 연결 (E2E, HTTP 없음) ───────

def test_provider_to_pipeline_connection(tmp_path, monkeypatch):
    """Pollinations(mock) → raw → rembg/필요시 → DNA 정규화 → 합성 → QA."""
    _mock_requests(monkeypatch, [("character", 200, _fake_png_bytes())])
    raw_dir = tmp_path / "raw"
    provider = PollinationsProvider(raw_assets_dir=raw_dir)
    provider.generate_topic_assets("yearend_tax")

    assets_dir = tmp_path / "assets"
    pipe = CalcImagePipeline(assets_dir=assets_dir, output_dir=tmp_path / "out",
                             raw_assets_dir=raw_dir)
    report = pipe.run(["yearend_tax"])
    r = report["results"]["yearend_tax"]
    assert r["all_qa_ok"], r["qa"]
    assert (assets_dir / "yearend_tax_character_male_normalized.png").exists()
    assert Image.open(r["files"]["master"]).size == (1920, 1080)
    assert Image.open(r["files"]["body"]).size == (800, 450)
    assert Image.open(r["files"]["thumb"]).size == (512, 512)


# ── Test 8: CLI 회귀 ───────────────────────────────────────────────

def test_cli_has_generate_and_existing_flags():
    proc = subprocess.run(
        [sys.executable, "-m", "image_pipeline.pipeline", "--help"],
        capture_output=True, text=True, cwd=BASE,
    )
    assert proc.returncode == 0
    for flag in ("--keys", "--assets", "--out", "--raw-assets",
                 "--generate-assets", "--force-assets"):
        assert flag in proc.stdout
