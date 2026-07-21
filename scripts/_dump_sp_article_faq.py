# -*- coding: utf-8 -*-
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()
sp = next(c for c in calcs if c.get("slug") == "severance-pay")
art = sp["article_content"]

m = re.search(r"공식은\s*['\"]", art)
if m:
    ctx = art[max(0, m.start()-100):m.end()+200]
    print(repr(ctx))
else:
    print("패턴 없음")
