# -*- coding: utf-8 -*-
"""
modules/static_publisher.py — Content Result → 정적 HTML 파일 저장 (STEP 2)

책임은 정확히 다음으로 한정한다:
  1. Content Result 수신
  2. "/blog/{slug}/" 경로 결정
  3. 필요한 디렉터리 생성
  4. modules.site_generator._blog_page()로 HTML 빌드 호출
  5. index.html 저장

절대 하지 않는 것 (STEP 1/2 설계 원칙):
  - WordPress REST API 호출
  - WP post ID / media ID / category ID 사용
  - WP REST payload 생성
  - 기존 WordPress publisher 모듈 / blog_scheduler_adapter의 WP 발행 경로 호출

data/workspace/_site/{slug}/ (계산기 웹앱 페이지)는 이 모듈이 절대 건드리지 않는다.
항상 data/workspace/_site/blog/{slug}/ 아래에만 쓴다.
"""
from __future__ import annotations

from pathlib import Path

from modules import site_generator as SG

DEFAULT_SITE_DIR = Path(__file__).resolve().parent.parent / "data" / "workspace" / "_site"


def blog_output_path(site_dir: Path, slug: str) -> Path:
    """slug → data/workspace/_site/blog/{slug}/index.html 경로."""
    return Path(site_dir) / "blog" / slug / "index.html"


def publish_one(result: dict, cfg: dict, site_dir: Path = None) -> Path:
    """Content Result 1건을 정적 HTML로 저장하고 저장 경로를 반환한다."""
    site_dir = Path(site_dir) if site_dir is not None else DEFAULT_SITE_DIR
    html = SG._blog_page(result, cfg)
    out_path = blog_output_path(site_dir, result["slug"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def publish_all(results: list, cfg: dict, site_dir: Path = None) -> list:
    """Content Result 리스트를 모두 저장하고 저장 경로 리스트를 반환한다."""
    return [publish_one(r, cfg, site_dir=site_dir) for r in results]


def publish_golden10(cfg: dict, site_dir: Path = None) -> list:
    """Golden10 + DB에서 새로 조립한 Content Result 10건을 정적 HTML로 저장한다.

    JSON 스냅샷(data/static_blog/golden10_content.json)은 읽지 않는다 — 이 모듈은
    항상 GOLDEN_10 + DB(authoritative source)에서 직접 조립한 결과만 사용한다.
    """
    from modules.blog_content_assembler import assemble_all_golden10

    results = assemble_all_golden10(cfg)
    return publish_all(results, cfg, site_dir=site_dir)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.stdout.reconfigure(encoding="utf-8")

    from modules.config_loader import load_config

    _cfg = load_config()
    _paths = publish_golden10(_cfg)
    print(f"[OK] {len(_paths)}건 생성:")
    for p in _paths:
        print(f"  - {p}")
