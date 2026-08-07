# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.sheets_adapter import SheetsAdapter

cfg = load_config()
sa = SheetsAdapter(cfg)
sa._connect()   # 명시적 연결

sheets = sa._with_retry(sa._sh.worksheets)
print(f"총 시트 수: {len(sheets)}")
print()
for ws in sheets:
    try:
        vals = sa._with_retry(ws.get_all_values)
        data_rows = len(vals)
        header = vals[0] if vals else []
        sample = vals[1] if len(vals) > 1 else []
        print(f"[{ws.title}]")
        print(f"  데이터행: {data_rows}")
        print(f"  헤더: {header[:6]}")
        if sample:
            print(f"  샘플1: {[str(v)[:30] for v in sample[:4]]}")
        print()
    except Exception as e:
        print(f"[{ws.title}] 오류: {e}\n")
