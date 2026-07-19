# -*- coding: utf-8 -*-
import sys, json, hashlib
sys.stdout.reconfigure(encoding="utf-8")

snap_path = "tests/golden/calculator_snapshots.json"
snap = json.loads(open(snap_path, encoding="utf-8").read())
ws = "data/workspace/unemployment-benefit"
for fname in ["index.html", "script.js"]:
    content = open(f"{ws}/{fname}", encoding="utf-8").read()
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    old = snap.get("unemployment-benefit", {}).get(fname, "")
    tag = "changed" if h != old else "same"
    snap.setdefault("unemployment-benefit", {})[fname] = h
    print(f"  {fname}: {tag}")
open(snap_path, "w", encoding="utf-8").write(json.dumps(snap, ensure_ascii=False, indent=2))
print("snapshot 갱신 완료")
