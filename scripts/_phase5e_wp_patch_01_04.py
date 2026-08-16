# -*- coding: utf-8 -*-
"""01/04번 법적 오류 패치 후 WP PUT 재업로드"""
from __future__ import annotations
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from scripts._phase5e_wp_update import update_one

PATCH = [
    ("01", "severance-pay",  "퇴직금 받는 조건", 313),
    ("04", "four-insurances", "4대보험 계산",     322),
]

for prefix, slug, kw, pid in PATCH:
    update_one(prefix, slug, kw, pid)

print("\n패치 완료")
