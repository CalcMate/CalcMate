import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
cfg = load_config()
db = get_db_adapter(cfg)

ws = db._primary._ws("logs")
raw_headers = ws.row_values(1)
print("=== 운영로그 raw headers (repr) ===")
for i, h in enumerate(raw_headers):
    print(f"  [{i}] {repr(h)}")
