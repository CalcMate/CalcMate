# -*- coding: utf-8 -*-
"""SP-8 수정 후 workspace 재생성 + golden 갱신."""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

ROOT      = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"
SNAPSHOT  = ROOT / "tests" / "golden" / "calculator_snapshots.json"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
snap  = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

TARGETS = [
    ("weekly-holiday-allowance", "weekly-holiday-allowance"),
    ("unemployment-benefit",     "unemployment-benefit"),
    ("four-insurances",          "four-insurances"),
    ("annual-leave-allowance",   "annual-leave-allowance"),
]

print("=" * 50)
for slug, dname in TARGETS:
    rec = next((c for c in calcs if c.get("slug") == slug), None)
    if not rec:
        print(f"  ❌ {slug}: DB 없음"); continue

    # workspace 재생성
    out_dir = WORKSPACE / dname
    out_dir.mkdir(parents=True, exist_ok=True)
    result = generate_calculator(rec, cfg)
    for fname, content in result.items():
        if isinstance(content, str):
            (out_dir / fname).write_text(content, encoding="utf-8")

    # golden 갱신
    if dname not in snap:
        snap[dname] = {}
    for fname in ["index.html", "script.js", "style.css"]:
        fpath = out_dir / fname
        if fpath.exists():
            snap[dname][fname] = hashlib.md5(fpath.read_bytes()).hexdigest()

    print(f"  ✔ {dname}: workspace 재생성 + golden 갱신")

SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("  ✔ calculator_snapshots.json 저장")
print("=" * 50)
print("완료")
