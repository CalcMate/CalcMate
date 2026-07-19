# -*- coding: utf-8 -*-
"""SP-2 재생성 후 골든 스냅샷 업데이트 (sha256, 중첩 dict 형식)"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "tests" / "golden" / "calculator_snapshots.json"
WORKSPACE = ROOT / "data" / "workspace"

TARGETS = ["severance-pay", "연말정산_환급액_계산기", "육아휴직_급여_계산기"]
FILES = ["script.js", "index.html", "style.css"]

def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

for slug in TARGETS:
    if slug not in snap:
        snap[slug] = {}
    for fname in FILES:
        fpath = WORKSPACE / slug / fname
        if not fpath.exists():
            continue
        new_hash = sha256_file(fpath)
        old_hash = snap[slug].get(fname, "없음")
        snap[slug][fname] = new_hash
        changed = "변경" if old_hash != new_hash else "동일"
        print(f"  [{changed}] {slug}/{fname}: {old_hash[:12]}... → {new_hash[:12]}...")

SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("\n골든 스냅샷 업데이트 완료.")
