# -*- coding: utf-8 -*-
"""7종 계산기 + 사이트 페이지 _site 재생성"""
import os, sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules import app_generator as AG
from modules import site_generator as SG

cfg = load_config()
repo = CalculatorRepository(get_db_adapter(cfg))
calcs = repo.get_all()

BASE = Path(__file__).resolve().parent.parent
SITE_DIR = BASE / "data" / "workspace" / "_site"
SITE_DIR.mkdir(parents=True, exist_ok=True)

errors = []

# ─── 1. 사이트 공통 페이지 재생성 ───────────────────────────────────────
print("=== 사이트 공통 페이지 재생성 ===")
try:
    site_pages = SG.generate_all(cfg)
    for path, content in site_pages.items():
        fp = SITE_DIR / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        print(f"  [OK] {path}")
except Exception as e:
    print(f"  [ERROR] site pages: {e}")
    errors.append(f"site: {e}")

# ─── 2. 계산기 7종 재생성 ────────────────────────────────────────────────
print("\n=== 계산기 7종 재생성 ===")
for c in calcs:
    slug = c.get("slug", "")
    try:
        files = AG.generate_calculator(c, cfg)
        slug_dir = SITE_DIR / slug
        slug_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in files.items():
            if fname in ("index.html", "style.css", "script.js"):
                (slug_dir / fname).write_text(content, encoding="utf-8")
        print(f"  [OK] {slug}")
    except Exception as e:
        print(f"  [ERROR] {slug}: {e}")
        errors.append(f"{slug}: {e}")

# ─── 3. 요약 ─────────────────────────────────────────────────────────────
print(f"\n=== 완료: {len(calcs)}종 계산기, {len(site_pages)}개 사이트 페이지 ===")
if errors:
    print("에러:")
    for e in errors:
        print(f"  - {e}")
else:
    print("에러 없음")
