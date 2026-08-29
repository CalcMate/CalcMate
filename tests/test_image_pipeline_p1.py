# -*- coding: utf-8 -*-
"""tests/test_image_pipeline_p1.py — P1 검증

- P1-2: Topic DNA 정규화 파라미터(Global Default → Topic Override) 해석
- P1-1: raw asset 자동 정규화 CLI 경로 + E2E(raw → rembg/필요시 → halo → DNA 정규화 → 합성)
"""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from image_pipeline import svg_template  # noqa: E402
from image_pipeline.pipeline import CalcImagePipeline  # noqa: E402

REF_ASSETS = BASE / "calcmate_v1_reference" / "assets"


def _make_raw_rgba_with_halo(path: Path, halo_alpha: int = 60) -> Path:
    """반투명 halo 잔상이 있는 RGBA 에셋 생성 (rembg 없이 halo 정리 경로 검증).

    halo_alpha=60: 기본 임계값 40을 넘지만 퇴직금 override 90 미만 →
    override가 실제 적용됨을 검증하는 데 사용.
    """
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    # halo 먼저, 불투명 코어를 그 위에 (코어 alpha=255, 둘레에 반투명 링 잔존)
    img.paste(Image.new("RGBA", (170, 230), (128, 128, 128, halo_alpha)), (65, 35))
    img.paste(Image.new("RGBA", (140, 200), (30, 120, 200, 255)), (80, 50))
    img.save(path)
    return path


# ── P1-2: DNA 파라미터 해석 ─────────────────────────────────────────

def test_dna_normalize_uses_defaults():
    """override가 없는 주제(연말정산)는 Global Default를 사용한다."""
    dna = svg_template.TOPIC_DNA["yearend_tax"]
    p = svg_template.resolve_asset_normalize_params(dna, "character")
    assert p["alpha_threshold"] == 40
    assert p["erosion_iterations"] == 2
    assert p["canvas_size"] == 800
    assert p["crop_upper_body_ratio"] is None


def test_dna_normalize_topic_override():
    """퇴직금 여성 실측값(90/4/0.55)이 DNA에 등록되고 override된다."""
    dna = svg_template.TOPIC_DNA["severance"]
    p = svg_template.resolve_asset_normalize_params(dna, "character")
    assert p["alpha_threshold"] == 90
    assert p["erosion_iterations"] == 4
    assert p["crop_upper_body_ratio"] == 0.55
    # hero는 override 없음 → 기본값 유지
    ph = svg_template.resolve_asset_normalize_params(dna, "hero")
    assert ph["alpha_threshold"] == 40
    assert ph["erosion_iterations"] == 2


def test_asset_file_accessor_both_schemas():
    """구버전(문자열)과 신규({file, normalize}) 스키마가 모두 동작한다."""
    assert (svg_template.get_asset_file(svg_template.TOPIC_DNA["yearend_tax"], "character")
            == "yearend_tax_character_male_normalized.png")
    assert (svg_template.get_asset_file(svg_template.TOPIC_DNA["severance"], "character")
            == "severance_character_female_normalized.png")
    assert (svg_template.get_asset_file(svg_template.TOPIC_DNA["severance"], "hero")
            == "severance_trophy_normalized.png")


def test_unverified_topic_still_blocked():
    """미검증 주제는 require_template 게이트로 계속 차단된다."""
    with pytest.raises(ValueError):
        svg_template.require_template("weekly_holiday")


# ── P1-1: CLI ──────────────────────────────────────────────────────

def test_cli_has_raw_assets_flag():
    """--raw-assets가 CLI에 노출되고 기존 옵션이 유지된다."""
    proc = subprocess.run(
        [sys.executable, "-m", "image_pipeline.pipeline", "--help"],
        capture_output=True, text=True, cwd=BASE,
    )
    assert proc.returncode == 0
    assert "--raw-assets" in proc.stdout
    assert "--keys" in proc.stdout
    assert "--assets" in proc.stdout
    assert "--out" in proc.stdout


# ── P1-1: raw → 정규화 → 합성 E2E ─────────────────────────────────

def test_raw_asset_auto_normalization_end_to_end(tmp_path):
    """raw asset(RGBA+halo) → DNA 파라미터 정규화 → 합성 → Master/Body/Thumb + QA.

    - character만 raw에서 정규화(퇴직금 override 90/4/0.55 적용),
    - hero는 검증된 정규화 에셋 복사본(read 경로) 사용 — 혼합 경로 검증.
    """
    # raw_assets/<topic>/character.png convention
    raw_dir = tmp_path / "raw"
    topic_dir = raw_dir / "severance"
    topic_dir.mkdir(parents=True)
    raw_char = topic_dir / "character.png"
    _make_raw_rgba_with_halo(raw_char)

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    shutil.copy2(REF_ASSETS / "severance_trophy_normalized.png",
                 assets_dir / "severance_trophy_normalized.png")

    pipe = CalcImagePipeline(assets_dir=assets_dir, output_dir=tmp_path / "out",
                             raw_assets_dir=raw_dir)
    report = pipe.run(["severance"])
    r = report["results"]["severance"]
    assert r["all_qa_ok"], r["qa"]

    # 정규화 에셋이 assets_dir에 생성됨 (참조 패키지 아님)
    norm = assets_dir / "severance_character_female_normalized.png"
    assert norm.exists()

    # 3종 출력 정상
    assert Image.open(r["files"]["master"]).size == (1920, 1080)
    assert Image.open(r["files"]["body"]).size == (800, 450)
    assert Image.open(r["files"]["thumb"]).size == (512, 512)

    # halo 정리 확인: 임계값 90 적용 → 반투명 halo(alpha 60)가 제거됐어야 한다
    alpha = np.array(Image.open(norm).convert("RGBA"))[:, :, 3]
    semi = int(((alpha > 0) & (alpha < 90)).sum())
    assert semi / alpha.size < 0.01


def test_reference_package_write_guard(tmp_path):
    """raw 정규화 출력이 참조 패키지에 기록되면 예외로 차단된다.

    (검증 에셋이 존재하는 주제는 early-return이라 raw 경로에 도달하지 않으므로
    가드 메서드를 직접 검증한다.)
    """
    from image_pipeline.pipeline import REFERENCE_ASSETS_DIR

    pipe = CalcImagePipeline(output_dir=tmp_path / "out")
    with pytest.raises(ValueError, match="참조 패키지"):
        pipe._ensure_writable_target(REFERENCE_ASSETS_DIR / "new_topic_character_normalized.png")
    # 참조 패키지 밖은 통과
    pipe._ensure_writable_target(tmp_path / "assets" / "x.png")


def test_flat_raw_convention_fallback(tmp_path):
    """기존 convention(raw_assets_dir/<정규화 파일명>)도 탐색된다.

    기본 임계값 40으로 halo(alpha 20)가 제거되는 기본값 경로도 함께 검증.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    _make_raw_rgba_with_halo(raw_dir / "yearend_tax_character_male_normalized.png", halo_alpha=20)

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)

    pipe = CalcImagePipeline(assets_dir=assets_dir, output_dir=tmp_path / "out",
                             raw_assets_dir=raw_dir)
    report = pipe.run(["yearend_tax"])
    assert report["results"]["yearend_tax"]["all_qa_ok"]
    assert (assets_dir / "yearend_tax_character_male_normalized.png").exists()
