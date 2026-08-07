import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository
cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
art_repo  = ArticleRepository(db)

SLUGS = ["weekly-holiday-allowance","unemployment-benefit","severance-pay"]
print("=== calculators 테이블 현황 ===")
all_calcs = calc_repo.get_all()
for s in SLUGS:
    hit = [c for c in all_calcs if c.get("slug")==s]
    print(f"  {s}: {len(hit)}건 → {hit[0].get('id','') if hit else 'NOT FOUND'}, status={hit[0].get('status','') if hit else '-'}")

print()
print("=== 마스터_DB 현황 (3개 계산기 관련) ===")
all_arts = art_repo.get_all()
calc_ids = [c.get("id","") for c in all_calcs if c.get("slug") in SLUGS]
related = [a for a in all_arts if a.get("calculator_id") in calc_ids]
print(f"  총 관련 기사: {len(related)}건")
for a in related:
    print(f"    ID={a.get('ID')} calc_id={a.get('calculator_id')} 상태={a.get('상태값')} 정책명={a.get('정책명','')[:30]}")
