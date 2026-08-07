import sys, io, yaml
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.registry_loader import load_registry
r = load_registry()
jh = r.get("weekly-holiday-allowance", {})
print("=== weekly-holiday-allowance registry ===")
for k, v in jh.items():
    print(f"  {k}: {v}")
print()

# compute_rules 확인
cr = jh.get("compute_rules", {})
print("=== compute_rules ===")
if cr:
    for k2, v2 in cr.items():
        print(f"  {k2}: {v2}")
else:
    print("  (없음)")

# legal 정보
print()
print("=== legal_refs ===", jh.get("legal_refs", []))
print("=== law ===", jh.get("law", "(없음)"))
print("=== article ===", jh.get("article", "(없음)"))
print("=== writer_note (앞 200자) ===")
print(str(jh.get("writer_note",""))[:200])
