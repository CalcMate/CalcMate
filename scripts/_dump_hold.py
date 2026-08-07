import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from datetime import datetime

cfg = load_config()
db  = get_db_adapter(cfg)
today = datetime.now().strftime("%Y-%m-%d")
all_arts = db._primary.get_all("articles", force_refresh=True)
today_arts = [a for a in all_arts if str(a.get("발행일시","")).startswith(today)
              and "주휴수당" in str(a.get("정책명",""))]

if not today_arts:
    print("오늘 주휴수당 기록 없음")
else:
    a = today_arts[0]
    print("=== 주휴수당 HOLD 1건 전체 필드 ===")
    for k, v in a.items():
        val = str(v)[:200] if v else "(비어있음)"
        print(f"  {k}: {val}")
