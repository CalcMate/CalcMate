import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository
from datetime import datetime

cfg = load_config()
db  = get_db_adapter(cfg)
repo = ArticleRepository(db)

today = datetime.now().strftime("%Y-%m-%d")
all_arts = db._primary.get_all("articles", force_refresh=True)
today_arts = [a for a in all_arts if str(a.get("발행일시","")).startswith(today)]

print(f"오늘 마스터_DB 기록: {len(today_arts)}건")
for a in today_arts:
    qfr = a.get("quality_failed_rules","")
    try:
        rules = json.loads(qfr) if qfr else []
    except:
        rules = []
    print(f"\n  정책명={a.get('정책명','')[:30]}")
    print(f"  상태={a.get('상태값','')}, quality_status={a.get('quality_status','')}")
    if rules:
        for r in rules:
            print(f"    FAIL gate={r.get('gate')} grade={r.get('grade')} detail={r.get('detail','')[:80]}")
    else:
        print(f"  quality_failed_rules={qfr[:100] if qfr else '(없음)'}")
