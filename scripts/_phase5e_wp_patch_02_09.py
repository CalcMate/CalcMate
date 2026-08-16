# -*- coding: utf-8 -*-
"""02/09 H2 패치 후 WP PUT 재업로드"""
from __future__ import annotations
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from scripts._phase5e_wp_update import update_one, SESSION, _CAT_MAP

PATCH = [
    ("02", "weekly-holiday-allowance", "주휴수당 계산법",   316),
    ("09", "unemployment-benefit",     "실업급여 신청방법", 333),
]

for prefix, slug, kw, pid in PATCH:
    update_one(prefix, slug, kw, pid)

print("\n패치 완료")
