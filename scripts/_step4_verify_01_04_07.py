# -*- coding: utf-8 -*-
"""01/04/07번 Gate 재검증 (STEP 4)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from modules.content_integrity import run_integrity_gates
from pathlib import Path

ARTICLES = [
    ("01", "data/phase5-c/articles/01_severance-pay_퇴직금_받는_조건.html",
     "severance-pay", "eligibility"),
    ("04", "data/phase5-c/articles/04_four-insurances_4대보험_계산.html",
     "four-insurances", "calculator"),
    ("07", "data/phase5-c/articles/07_육아휴직_급여_계산기_육아휴직_급여_조건.html",
     "육아휴직_급여_계산기", "eligibility"),
]

for no, path, slug, intent in ARTICLES:
    html = Path(path).read_text(encoding="utf-8")
    passed, failed = run_integrity_gates(html, slug=slug, intent=intent)
    crit  = [f for f in failed if f["grade"] == "critical"]
    major = [f for f in failed if f["grade"] == "major"]
    minor = [f for f in failed if f["grade"] == "minor"]
    if not crit and not major:
        status = "PASS" if not minor else "WARN(minor)"
    elif not crit:
        status = "WARN"
    else:
        status = "FAIL"
    print(f"{no}번 [{slug}] intent={intent} → {status}  CRIT={len(crit)} MAJOR={len(major)} MINOR={len(minor)}")
    for f in failed:
        print(f"  [{f['grade']}] {f['gate']}: {f['detail'][:120]}")
