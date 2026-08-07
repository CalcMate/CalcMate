# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.sheets_adapter import SheetsAdapter
from collections import Counter

cfg = load_config()
sa = SheetsAdapter(cfg)
sa._connect()

sheets = {ws.title: ws for ws in sa._with_retry(sa._sh.worksheets)}

# ── 마스터_DB 분석 ──
print("=" * 50)
print("마스터_DB 분석")
print("=" * 50)
ws = sheets["마스터_DB"]
rows = sa._with_retry(ws.get_all_records)
statuses = Counter(r.get("상태값","") for r in rows)
print(f"총 데이터행: {len(rows)}")
print("상태값 분포:")
for s, n in statuses.most_common():
    print(f"  [{s}]: {n}건")
print("\n날짜별 분포 (ID 앞 8자리=날짜):")
dates = Counter(str(r.get("ID",""))[:8] for r in rows if r.get("ID"))
for d, n in sorted(dates.items()):
    print(f"  {d}: {n}건")
print("\n계산기 관련 여부 (정책명에 '계산' 포함):")
calc_rows = [r for r in rows if "계산" in str(r.get("정책명",""))]
non_calc = [r for r in rows if "계산" not in str(r.get("정책명",""))]
print(f"  계산기 관련: {len(calc_rows)}건")
print(f"  블로그/기타: {len(non_calc)}건")

# ── 운영로그 분석 ──
print()
print("=" * 50)
print("운영로그 분석")
print("=" * 50)
ws2 = sheets["운영로그"]
logs = sa._with_retry(ws2.get_all_records)
print(f"총 로그행: {len(logs)}")
results = Counter(r.get("가동 결과 (성공/오류)","") for r in logs)
print("가동결과 분포:")
for s, n in results.most_common():
    print(f"  [{s}]: {n}건")
# 날짜별
log_dates = Counter(str(r.get("실행일시",""))[:10] for r in logs if r.get("실행일시"))
print("날짜별:")
for d, n in sorted(log_dates.items()):
    print(f"  {d}: {n}건")

# ── calculators 분석 ──
print()
print("=" * 50)
print("calculators 시트")
print("=" * 50)
ws3 = sheets["calculators"]
calcs = sa._with_retry(ws3.get_all_records)
print(f"총 계산기: {len(calcs)}건")
for c in calcs:
    print(f"  [{c.get('slug','')}] {c.get('name','')} | 상태: {c.get('status','')} | published_url: {str(c.get('published_url',''))[:50]}")
