import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.registry_loader import load_registry
reg = load_registry()
targets = []
for slug, entry in reg.items():
    n = entry.get("name","")
    if any(k in n for k in ["주휴","실업","퇴직"]):
        targets.append((slug, n, entry.get("category",""), entry.get("needs_human_legal","")))
for t in targets:
    print(f"slug={t[0]}  name={t[1]}  cat={t[2]}  needs_legal={t[3]}")
