# -*- coding: utf-8 -*-
"""
image_pipeline/content_connector.py — P3: 콘텐츠 Pipeline → Image Pipeline 연결

콘텐츠 파이프라인이 결정한 topic(calculator slug/이름/topic_key)을
이미지 생산 표준 v1의 Topic DNA에 연결하고, ImageJob으로 변환해
이미 검증된 P1/P2 파이프라인(CalcImagePipeline + PollinationsProvider)을
호출한다. WordPress/게시 관련 코드는 일절 사용하지 않는다.

흐름:
    Content data
        ↓ resolve_topic_key (slug/이름/key → TOPIC_DNA key)
        ↓ ImageJob
        ↓ [선택] PollinationsProvider (기존 raw 재사용, --force 재생성)
        ↓ CalcImagePipeline (raw → rembg → halo → DNA 정규화 → 합성 → QA)
        ↓ ImageJobResult (IMAGE_PENDING / IMAGE_READY / IMAGE_FAILED)

원칙:
  - 검증된 Topic(require_template PASS)만 자동 이미지 생산.
  - pending Topic → IMAGE_PENDING (자동 생성/임의 좌표/기본 템플릿 강제 없음).
  - unknown topic → IMAGE_FAILED ("unknown topic").
  - 이미지 생성 실패를 성공으로 기록하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import svg_template

# 콘텐츠 파이프라인 식별자(calculator slug / 표시명 / topic_key) → TOPIC_DNA key
CONTENT_TOPIC_ALIASES: dict[str, str] = {
    # topic_key 직접 사용
    "yearend_tax": "yearend_tax",
    "severance": "severance",
    "weekly_holiday": "weekly_holiday",
    "unemployment_benefit": "unemployment_benefit",
    "annual_leave": "annual_leave",
    # calculator slug (data/phase5-c/requests 기준)
    "severance-pay": "severance",
    "weekly-holiday-allowance": "weekly_holiday",
    "unemployment-benefit": "unemployment_benefit",
    "annual-leave-allowance": "annual_leave",
    "연말정산_환급액_계산기": "yearend_tax",
    # 표시명
    "연말정산": "yearend_tax",
    "퇴직금": "severance",
    "주휴수당": "weekly_holiday",
    "실업급여": "unemployment_benefit",
    "연차수당": "annual_leave",
}


class ImageStatus(Enum):
    IMAGE_PENDING = "IMAGE_PENDING"
    IMAGE_GENERATING = "IMAGE_GENERATING"
    IMAGE_READY = "IMAGE_READY"
    IMAGE_FAILED = "IMAGE_FAILED"


@dataclass
class ImageJob:
    """콘텐츠 → 이미지 파이프라인 전달 객체 (최소 데이터만)."""

    topic_key: str
    calculator_id: str = ""
    title: str = ""
    output_dir: str | Path | None = None
    assets_dir: str | Path | None = None
    raw_assets_dir: str | Path | None = None
    generate_assets: bool = False
    force_assets: bool = False


@dataclass
class ImageJobResult:
    topic_key: str
    status: ImageStatus
    all_qa_ok: bool = False
    files: dict = field(default_factory=dict)
    qa: dict = field(default_factory=dict)
    error: str | None = None


# ── Topic resolve ──────────────────────────────────────────────────

def resolve_topic_key(topic_or_slug: str) -> str:
    """콘텐츠 식별자(슬러그/표시명/topic_key)를 TOPIC_DNA key로 변환한다.

    unknown → ValueError ("unknown topic").
    """
    if not topic_or_slug:
        raise ValueError("unknown topic: 빈 식별자")
    key = CONTENT_TOPIC_ALIASES.get(topic_or_slug)
    if key:
        return key
    # 토픽 키 자체가 DNA에 있는 경우 (별칭표에 없는 새 키)
    if topic_or_slug in svg_template.TOPIC_DNA:
        return topic_or_slug
    raise ValueError(f"unknown topic: {topic_or_slug}")


def extract_topic_from_content(data: dict) -> str:
    """콘텐츠 request 데이터에서 topic 식별자를 추출해 TOPIC_DNA key로 변환."""
    for field_name in ("topic_key", "topic", "slug", "calc_name", "name"):
        v = data.get(field_name)
        if v:
            try:
                return resolve_topic_key(str(v))
            except ValueError:
                continue
    raise ValueError("unknown topic: 콘텐츠 데이터에서 topic 식별 불가")


# ── Job 실행 ───────────────────────────────────────────────────────

def build_image_job(topic_or_slug: str, calculator_id: str = "",
                    title: str = "", **kwargs) -> ImageJob:
    """검증된 topic만 ImageJob 생성. pending/unknown은 이 단계에서 걸러낸다."""
    key = resolve_topic_key(topic_or_slug)
    # pending template은 자동 이미지 생산 진입 차단 (require_template 게이트 유지)
    svg_template.require_template(key)
    return ImageJob(topic_key=key, calculator_id=calculator_id, title=title, **kwargs)


def run_image_job(job: ImageJob) -> ImageJobResult:
    """ImageJob을 실행해 ImageJobResult를 반환한다.

    - generate_assets=True: PollinationsProvider로 raw asset 확보 (P2 재사용, 재사용/force 정책 유지)
    - 이후 CalcImagePipeline로 Master/Body/Thumbnail + QA (P1 재사용)
    - WordPress 관련 호출 없음 — 로컬 파일 + QA 결과까지만.
    """
    if job.topic_key not in svg_template.TOPIC_DNA:
        return ImageJobResult(topic_key=job.topic_key, status=ImageStatus.IMAGE_FAILED,
                              error=f"unknown topic: {job.topic_key}")
    if svg_template.TOPIC_DNA[job.topic_key].get("template") != "validated":
        return ImageJobResult(
            topic_key=job.topic_key, status=ImageStatus.IMAGE_PENDING,
            error=f"pending template: {job.topic_key} — 템플릿 좌표 검증 전까지 자동 생산 불가",
        )

    try:
        from .pollinations_provider import DEFAULT_RAW_ASSETS_DIR, PollinationsProvider
        from .pipeline import CalcImagePipeline

        raw_assets_dir = job.raw_assets_dir
        if job.generate_assets:
            if raw_assets_dir is None:
                raw_assets_dir = DEFAULT_RAW_ASSETS_DIR
            provider = PollinationsProvider(raw_assets_dir)
            provider.generate_topic_assets(job.topic_key, force=job.force_assets)

        pipe = CalcImagePipeline(assets_dir=job.assets_dir, output_dir=job.output_dir,
                                 raw_assets_dir=raw_assets_dir)
        report = pipe.run([job.topic_key])
        r = report["results"][job.topic_key]

        if r["all_qa_ok"]:
            return ImageJobResult(topic_key=job.topic_key, status=ImageStatus.IMAGE_READY,
                                  all_qa_ok=True, files=r["files"], qa=r["qa"])
        return ImageJobResult(topic_key=job.topic_key, status=ImageStatus.IMAGE_FAILED,
                              all_qa_ok=False, files=r["files"], qa=r["qa"],
                              error="final QA 실패")
    except (KeyError, ValueError, FileNotFoundError, RuntimeError) as e:
        return ImageJobResult(topic_key=job.topic_key, status=ImageStatus.IMAGE_FAILED,
                              error=str(e))


# ── CLI (콘텐츠 request JSON 1건 → 이미지 생산) ─────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="콘텐츠 데이터 → Topic DNA → image_pipeline (P3 connector)")
    parser.add_argument("--request", help="콘텐츠 request JSON 경로 (calculator_id/slug/title 포함)")
    parser.add_argument("--slug", help="topic 식별자 직접 지정 (슬러그/표시명/topic_key)")
    parser.add_argument("--out", default=None, help="출력 디렉터리")
    parser.add_argument("--assets", default=None, help="정규화 에셋 디렉터리")
    parser.add_argument("--raw-assets", default=None, help="raw asset 디렉터리")
    parser.add_argument("--generate-assets", action="store_true",
                        help="Pollinations로 raw asset 자동 생성")
    parser.add_argument("--force-assets", action="store_true",
                        help="기존 raw asset이 있어도 재생성")
    args = parser.parse_args(argv)

    if args.request:
        data = json.loads(Path(args.request).read_text(encoding="utf-8"))
        topic = extract_topic_from_content(data)
        calculator_id = str(data.get("calculator_id", ""))
        title = str((data.get("seo") or {}).get("seo_title", "") or data.get("calc_name", ""))
    elif args.slug:
        topic = args.slug
        calculator_id, title = "", ""
    else:
        print("[content_connector] --request 또는 --slug 필요", file=sys.stderr)
        return 1

    try:
        job = build_image_job(
            topic, calculator_id=calculator_id, title=title,
            output_dir=args.out, assets_dir=args.assets, raw_assets_dir=args.raw_assets,
            generate_assets=args.generate_assets, force_assets=args.force_assets,
        )
    except ValueError as e:
        print(f"[content_connector] {e}", file=sys.stderr)
        return 1

    result = run_image_job(job)
    print(f"[{result.topic_key}] {result.status.value} all_qa_ok={result.all_qa_ok}")
    for kind, path in result.files.items():
        print(f"  {kind:<6} {path}")
    if result.error:
        print(f"  error: {result.error}", file=sys.stderr)
    return 0 if result.status == ImageStatus.IMAGE_READY else 1


if __name__ == "__main__":
    sys.exit(main())
