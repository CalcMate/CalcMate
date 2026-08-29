# -*- coding: utf-8 -*-
"""
image_pipeline/pipeline.py — CalcMate 이미지 생산 표준 v1 엔트리포인트

주제별 Topic DNA → SVG 템플릿 → Master(1920x1080) → Asset 합성
→ Body(800x450)/Thumbnail(512x512) 다운사이징 → 자동 QA.

실행 예:
    python -m image_pipeline.pipeline --keys yearend_tax severance
    python -m image_pipeline.pipeline --keys severance --out data/outputs/calc_v1
    python -m image_pipeline.pipeline --keys severance --raw-assets data/raw_assets \
        --assets data/phase5-followup/calc_v1/assets
    # P2: Pollinations로 raw asset 자동 생성 후 처리 (기존 raw 존재 시 재사용, --force-assets로 강제 재생성)
    python -m image_pipeline.pipeline --keys severance --generate-assets \
        --assets data/phase5-followup/calc_v1/assets --out data/phase5-followup/calc_v1

참고:
  - Phase5-E 기존 파이프라인(scripts/_phase5e_*.py, modules/image_generator.py,
    data/phase5-c/images)은 건드리지 않는다. 출력은 별도 디렉터리로만 생성.
  - Provider 경계: Pollinations(modules/image_generator.py 컨벤션 재사용)는 raw 파일까지만,
    이후 처리는 전부 image_pipeline이 담당한다.
  - 검증된 Asset(정규화 완료 PNG)은 assets_dir에서, 원본 AI Asset은
    raw_assets_dir에서 읽는다. 없으면 asset_processor로 정규화한다.
  - raw asset 탐색: raw_assets/<topic>/character.png|hero.png (권장),
    또는 raw_assets_dir/<정규화 파일명> (기존 convention) 순서로 찾는다.
  - 정규화 파라미터는 Topic DNA(.assets.<kind>.normalize)에서 결정되고
    Global Default → Topic Override 순서로 병합된다 (P1-2).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import svg_template
from . import asset_processor
from . import compositor

# 참조 패키지의 검증된 정규화 에셋 디렉터리 (v1 기본)
DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent.parent / "calcmate_v1_reference" / "assets"
# 참조 패키지(검증 완료 에셋 보관소) — raw 정규화 출력이 이곳에 기록되지 않도록 보호
REFERENCE_ASSETS_DIR = DEFAULT_ASSETS_DIR
# 이 세션 재현 출력 디렉터리 (Phase5-E와 분리)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "phase5-followup" / "calc_v1"

MASTER_W, MASTER_H = compositor.MASTER_W, compositor.MASTER_H

# Master 좌표 기준 QA 영역 (본문 SVG 1200x675의 제목/부제 영역 × 1.6)
TITLE_ZONE = (int(120 * 1.6), int(220 * 1.6), int(520 * 1.6), int(330 * 1.6))


class CalcImagePipeline:
    """주제별 이미지 생산 오케스트레이터."""

    def __init__(self, assets_dir: str | Path | None = None,
                 output_dir: str | Path | None = None,
                 raw_assets_dir: str | Path | None = None):
        self.assets_dir = Path(assets_dir) if assets_dir else DEFAULT_ASSETS_DIR
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.raw_assets_dir = Path(raw_assets_dir) if raw_assets_dir else None

    # ── Asset 준비 ────────────────────────────────────────────────
    def _find_raw_asset(self, key: str, asset_kind: str, file_name: str) -> Path:
        """raw asset 탐색 (P1-1).

        1) raw_assets/<topic>/character.png|hero.png  (권장 구조)
        2) raw_assets_dir/<정규화 파일명>             (기존 convention)
        """
        simple = {"character": "character.png", "hero": "hero.png"}[asset_kind]
        cand1 = self.raw_assets_dir / key / simple
        if cand1.exists():
            return cand1
        cand2 = self.raw_assets_dir / file_name
        if cand2.exists():
            return cand2
        raise FileNotFoundError(f"[{key}] 원본 에셋 없음: {cand1} 또는 {cand2}")

    def _ensure_writable_target(self, target: Path) -> None:
        """검증 완료 에셋 보관소(참조 패키지)에 새 파일이 기록되지 않도록 보호한다."""
        ref = REFERENCE_ASSETS_DIR.resolve()
        t = target.resolve()
        if t == ref or ref in t.parents:
            raise ValueError(
                f"정규화 출력이 참조 패키지(calcmate_v1_reference/assets)에 기록됩니다: {target}\n"
                "검증 완료 에셋 보관소를 보호하기 위해 쓰기 가능한 --assets 디렉터리를 지정하세요."
            )

    def _resolve_asset(self, key: str, asset_kind: str) -> Path:
        """정규화 에셋을 찾는다. 없으면 raw → 정규화 경로를 수행한다.

        asset_kind: "character" | "hero"

        Raw → rembg(필요 시) → halo cleanup → DNA 기반 정규화 → compositor
        순서를 강제한다 (Raw가 합성으로 우회하는 경로는 없다).
        정규화 파라미터는 Topic DNA(.assets.<kind>.normalize)에서 결정된다 (P1-2).
        """
        dna = svg_template.TOPIC_DNA[key]
        file_name = svg_template.get_asset_file(dna, asset_kind)
        if not file_name:
            raise FileNotFoundError(f"[{key}] DNA에 {asset_kind} 에셋 미등록")
        normalized = self.assets_dir / file_name

        if normalized.exists():
            return normalized

        if self.raw_assets_dir is None:
            raise FileNotFoundError(
                f"[{key}] 정규화 에셋 없음: {normalized} — --raw-assets 지정 필요"
            )

        raw = self._find_raw_asset(key, asset_kind, file_name)
        self._ensure_writable_target(normalized)

        params = svg_template.resolve_asset_normalize_params(dna, asset_kind)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        clean = self.output_dir / "tmp" / f"{key}_{asset_kind}_clean.png"
        asset_processor.clean_ai_asset(
            raw, clean,
            alpha_threshold=params["alpha_threshold"],
            erosion_iterations=params["erosion_iterations"],
        )
        if asset_kind == "character":
            return asset_processor.normalize_character(
                clean, normalized,
                canvas_size=params["canvas_size"],
                height_ratio=params["height_ratio"],
                bottom_margin=params["bottom_margin"],
                crop_upper_body_ratio=params.get("crop_upper_body_ratio"),
            )
        return asset_processor.normalize_hero_object(
            clean, normalized,
            canvas_size=params["canvas_size"],
            height_ratio=params["height_ratio"],
        )

    # ── 주제 1건 실행 ─────────────────────────────────────────────
    def run_topic(self, key: str) -> dict:
        dna = svg_template.require_template(key)
        out = self.output_dir / key
        out.mkdir(parents=True, exist_ok=True)

        report: dict = {"key": key, "display": dna["display"], "files": {}, "qa": {}}

        char_path = self._resolve_asset(key, "character")
        hero_path = self._resolve_asset(key, "hero") if "hero" in dna.get("assets", {}) else None

        # ── 1) Master (1920x1080) ────────────────────────────────
        body_svg = svg_template.build_body_svg(key)
        master = compositor.render_svg(body_svg, MASTER_W, MASTER_H)

        comp = dna["composite"]["character"]
        master = compositor.composite_character(
            master, char_path,
            target_width=comp["target_width"],
            right_margin=comp.get("right_margin", 40),
            bottom_margin=comp.get("bottom_margin", 40),
        )
        if hero_path is not None:
            hero_comp = dna["composite"]["hero"]
            master = compositor.composite_hero_object(
                master, hero_path,
                target_width=hero_comp["target_width"],
                position_x=hero_comp["x"], position_y=hero_comp["y"],
            )

        master_png = out / f"{key}_master.png"
        master.convert("RGB").save(master_png)
        report["files"]["master"] = str(master_png)

        # ── 2) Body (800x450) ────────────────────────────────────
        body = compositor.make_body(master)
        body_webp = out / f"{key}_body.webp"
        body.save(body_webp, format="WEBP", quality=90)
        report["files"]["body"] = str(body_webp)

        # ── 3) Thumbnail (1:1 전용 SVG → 512x512) ───────────────
        thumb_svg = svg_template.build_thumb_svg(key)
        thumb_master = compositor.render_svg(thumb_svg, 1080, 1080)

        tcomp = dna["composite"]["thumb_character"]
        thumb_master = compositor.composite_character(
            thumb_master, char_path,
            target_width=tcomp["target_width"],
            right_margin=tcomp.get("right_margin", 40),
            bottom_margin=tcomp.get("bottom_margin", 80),
        )
        if hero_path is not None and "thumb_hero" in dna.get("composite", {}):
            thero = dna["composite"]["thumb_hero"]
            thumb_master = compositor.composite_hero_object(
                thumb_master, hero_path,
                target_width=thero["target_width"],
                position_x=thero["x"], position_y=thero["y"],
            )

        thumb = compositor.make_thumbnail(thumb_master)
        thumb_webp = out / f"{key}_thumb.webp"
        thumb.save(thumb_webp, format="WEBP", quality=90)
        report["files"]["thumb"] = str(thumb_webp)

        # ── 4) 자동 QA ──────────────────────────────────────────
        qa = {
            "master": compositor.qa_image(master_png, (MASTER_W, MASTER_H)),
            "body": compositor.qa_image(body_webp, (compositor.BODY_W, compositor.BODY_H)),
            "thumb": compositor.qa_image(thumb_webp, (compositor.THUMB_W, compositor.THUMB_H)),
            "korean_glyphs": compositor.qa_korean_glyphs(master, TITLE_ZONE),
            "character_asset": asset_processor.qa_asset_clean(char_path),
        }
        if hero_path is not None:
            qa["hero_asset"] = asset_processor.qa_asset_clean(hero_path)
        report["qa"] = qa
        report["all_qa_ok"] = (
            qa["master"]["size_ok"] and qa["body"]["size_ok"]
            and qa["thumb"]["size_ok"] and qa["korean_glyphs"]["ok"]
            and qa["character_asset"]["halo_ok"]
            and qa.get("hero_asset", {}).get("halo_ok", True)
        )
        return report

    # ── 여러 주제 실행 ───────────────────────────────────────────
    def run(self, keys: list[str] | None = None) -> dict:
        if keys is None:
            keys = [k for k, v in svg_template.TOPIC_DNA.items() if v.get("template") == "validated"]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        results = {k: self.run_topic(k) for k in keys}
        return {"output_dir": str(self.output_dir), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CalcMate 이미지 생산 표준 v1")
    parser.add_argument("--keys", nargs="*", default=None,
                        help="주제 키 (기본: 템플릿 검증 완료 주제 전체)")
    parser.add_argument("--out", default=None, help="출력 디렉터리")
    parser.add_argument("--assets", default=None, help="정규화 에셋 디렉터리")
    parser.add_argument("--raw-assets", default=None,
                        help="원본 AI Asset 디렉터리 (raw_assets/<topic>/character.png 등). "
                             "정규화 에셋이 없으면 여기서 읽어 정규화 후 assets_dir에 기록")
    parser.add_argument("--generate-assets", action="store_true",
                        help="Pollinations로 raw asset 자동 생성 후 처리 (기존 유효 raw는 재사용). "
                             "--raw-assets 미지정 시 기본 raw_assets 경로 사용")
    parser.add_argument("--force-assets", action="store_true",
                        help="--generate-assets와 함께 사용: 기존 raw asset이 있어도 재생성")
    args = parser.parse_args(argv)

    raw_assets_dir = args.raw_assets
    if args.generate_assets:
        # P2: Pollinations Provider → raw_assets/<topic>/ (기존 modules/image_generator.py는 변경 없음)
        from .pollinations_provider import DEFAULT_RAW_ASSETS_DIR, PollinationsProvider
        if raw_assets_dir is None:
            raw_assets_dir = DEFAULT_RAW_ASSETS_DIR
        keys = args.keys or [k for k, v in svg_template.TOPIC_DNA.items()
                             if v.get("template") == "validated"]
        provider = PollinationsProvider(raw_assets_dir)
        for key in keys:
            provider.generate_topic_assets(key, force=args.force_assets)

    pipe = CalcImagePipeline(assets_dir=args.assets, output_dir=args.out,
                             raw_assets_dir=raw_assets_dir)
    try:
        report = pipe.run(args.keys)
    except (KeyError, ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"[pipeline] 실패: {e}", file=sys.stderr)
        return 1

    for key, r in report["results"].items():
        status = "OK" if r["all_qa_ok"] else "QA_FAIL"
        print(f"[{r['display']}] {status}")
        for kind, path in r["files"].items():
            print(f"  {kind:<6} {path}")
        if not r["all_qa_ok"]:
            print(f"  qa: {r['qa']}")

    print(f"\n출력: {report['output_dir']}")
    return 0 if all(r["all_qa_ok"] for r in report["results"].values()) else 2


if __name__ == "__main__":
    sys.exit(main())
