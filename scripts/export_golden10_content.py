# -*- coding: utf-8 -*-
"""
scripts/export_golden10_content.py — Golden10 + DB → data/static_blog/golden10_content.json 추출.

이 JSON은 재생성 가능한 snapshot/cache다. authoritative source가 아니다
(authoritative source는 GOLDEN_10 계약 + calculators DB). modules/static_publisher.py의
publish_golden10()도 이 파일을 읽지 않고 매번 DB에서 새로 조립한다 — 이 스크립트는
사람이 콘텐츠를 검토하거나 향후 WordPress 이전 시 참고할 수 있도록 스냅샷을 남기는
용도로만 존재한다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.blog_content_assembler import assemble_all_golden10

OUT_PATH = ROOT / "data" / "static_blog" / "golden10_content.json"


def main():
    cfg = load_config()
    results = assemble_all_golden10(cfg)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {len(results)}건 추출 -> {OUT_PATH}")
    for r in results:
        print(f"  - {r['slug']}: {r['title']}")


if __name__ == "__main__":
    main()
