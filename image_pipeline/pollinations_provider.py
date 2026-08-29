# -*- coding: utf-8 -*-
"""
image_pipeline/pollinations_provider.py — P2: Pollinations Raw Asset Provider adapter

기존 `modules/image_generator.py`의 Pollinations 구현은 그대로 두고,
이미지 생산 표준 v1이 raw asset을 공급받을 수 있도록 얇은 adapter만 추가한다.

Provider 경계 (지시서 §4):
    Pollinations → raw files (여기까지만 Provider)
    raw files → image_pipeline (부터는 processing layer)

- endpoint/prompt 전달/nologo 컨벤션은 기존 image_generator와 동일하게 재사용한다.
- 생성 결과는 `raw_assets/<topic>/character.png|hero.png` 구조로 저장 (P1 resolver 입력 규격).
- 미검증 주제(pending)는 자동 생성하지 않는다 (require_template 게이트).
- HTTP/이미지 검증 실패 또는 partial 생성은 예외로 보고한다 — 잘못된 asset을
  정상 asset으로 취급하지 않는다.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

from . import svg_template

# raw asset 기본 저장 경로 (normalized asset과 분리 — data/phase5-followup/calc_v1)
DEFAULT_RAW_ASSETS_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "phase5-followup" / "calc_v1" / "raw_assets"
)

ASSET_KIND_FILENAME = {"character": "character.png", "hero": "hero.png"}
ASSET_KIND_SIZE = {"character": 1024, "hero": 1024}  # 정규화 다운스케일 여유분 (충분히 큼)


@dataclass
class RawAssetResult:
    """Provider가 반환하는 raw asset 결과 묶음."""

    topic_key: str
    character_path: Path | None = None
    hero_path: Path | None = None
    metadata: dict = field(default_factory=dict)

    def paths(self) -> dict:
        return {k: getattr(self, f"{k}_path") for k in ("character", "hero")}


def validate_raw_asset(path: str | Path) -> tuple[bool, str]:
    """이미지 파일 최소 검증 (지시서 §12).

    file exists / size > 0 / Pillow 로드 가능 / 유효 format / width,height > 0
    """
    p = Path(path)
    if not p.exists():
        return False, "파일 없음"
    if p.stat().st_size <= 0:
        return False, "빈 파일"
    try:
        with Image.open(p) as im:
            im.load()
            w, h = im.size
    except Exception as e:  # noqa: BLE001 — 손상/비이미지 파일
        return False, f"이미지 로드 실패: {e}"
    if w <= 0 or h <= 0:
        return False, f"유효하지 않은 크기 ({w}x{h})"
    return True, "ok"


def build_asset_prompt(dna: dict, asset_kind: str) -> str:
    """Topic DNA에서 prompt를 구성한다 (기존 Pollinations 한글 prompt 컨벤션 재사용).

    image_pipeline은 이 prompt를 알 필요가 없다 (Provider 경계).
    """
    if asset_kind == "character":
        return (
            f"{dna['character']} 직장인, 한국형 플랫 벡터 일러스트, 전신, "
            "단순한 단색 밝은 배경, 부드러운 자연스러운 포즈, 진한 네이비 외곽선, "
            "깔끔한 상업용 일러스트, 텍스트 없음, 숫자 없음, 워터마크 없음, 로고 없음"
        )
    return (
        f"{dna['hero']} 오브젝트, 한국형 플랫 벡터 일러스트, 중앙 구도, "
        "단순한 단색 밝은 배경, 진한 네이비 외곽선, 깔끔한 상업용 일러스트, "
        "텍스트 없음, 숫자 없음, 워터마크 없음, 로고 없음"
    )


class PollinationsProvider:
    """기존 Pollinations endpoint를 사용하는 얇은 Raw Asset Provider adapter."""

    def __init__(self, raw_assets_dir: str | Path | None = None,
                 timeout: int = 60):
        self.raw_assets_dir = Path(raw_assets_dir) if raw_assets_dir else DEFAULT_RAW_ASSETS_DIR
        self.timeout = timeout

    # ── public ────────────────────────────────────────────────────
    def generate_topic_assets(self, key: str, force: bool = False) -> RawAssetResult:
        """주제 1건의 required asset(character/hero)을 raw_assets/<key>/ 에 생성한다.

        - 미검증 주제는 require_template으로 차단.
        - 기존 raw asset이 유효하면 재사용 (중복 생성 방지), force=True면 재생성.
        - HTTP 실패/손상/partial 생성은 RuntimeError로 명확히 실패 처리.
        """
        dna = svg_template.require_template(key)
        required = list(dna.get("assets", {}).keys())
        if "character" not in required:
            raise ValueError(f"[{key}] DNA에 character 에셋 미등록 — asset 자동 생성 불가")

        for kind in required:
            path = self.raw_assets_dir / key / ASSET_KIND_FILENAME[kind]
            if not force and validate_raw_asset(path)[0]:
                print(f"  [raw-asset] {key}/{ASSET_KIND_FILENAME[kind]} 재사용 (기존 유효)")
                continue
            prompt = build_asset_prompt(dna, kind)
            size = ASSET_KIND_SIZE.get(kind, 1024)
            self._fetch_and_save(prompt, size, path, key, kind)

        # partial 생성 방지 — required 전부 존재해야 함
        missing = [
            k for k in required
            if not validate_raw_asset(self.raw_assets_dir / key / ASSET_KIND_FILENAME[k])[0]
        ]
        if missing:
            raise RuntimeError(
                f"[{key}] raw asset 부분 생성: 누락/손상 = {missing} "
                f"({self.raw_assets_dir / key}) — 이미지 생산을 진행하지 않음"
            )

        result = RawAssetResult(topic_key=key)
        for kind in required:
            setattr(result, f"{kind}_path", self.raw_assets_dir / key / ASSET_KIND_FILENAME[kind])
        result.metadata = {"provider": "pollinations", "sizes": ASSET_KIND_SIZE}
        return result

    # ── private ───────────────────────────────────────────────────
    def _fetch_and_save(self, prompt: str, size: int, path: Path, key: str, kind: str) -> None:
        """Pollinations 호출 → 검증 → PNG 저장. 실패 시 RuntimeError."""
        url = f"https://image.pollinations.ai/p/{quote(prompt)}?width={size}&height={size}&nologo=true"
        print(f"  [raw-asset] Pollinations 생성 중 ({key}/{kind}, {size}x{size})...")
        try:
            resp = requests.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"[{key}] Pollinations 요청 실패 ({kind}): {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(f"[{key}] Pollinations HTTP {resp.status_code} ({kind})")
        if not resp.content:
            raise RuntimeError(f"[{key}] Pollinations 빈 응답 ({kind})")

        try:
            img = Image.open(io.BytesIO(resp.content))
            img.load()
        except Exception as e:  # noqa: BLE001 — 손상/비이미지 응답
            raise RuntimeError(f"[{key}] Pollinations 응답이 유효한 이미지가 아님 ({kind}): {e}") from e

        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="PNG")
        ok, msg = validate_raw_asset(path)
        if not ok:
            raise RuntimeError(f"[{key}] 저장된 raw asset 검증 실패 ({kind}): {msg}")
