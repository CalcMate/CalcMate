# -*- coding: utf-8 -*-
"""article_content 원문 그대로 파일로 덤프."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from pathlib import Path

cfg = load_config()
db = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
pl = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)

art = pl.get("article_content") or ""
faq = json.loads(pl.get("faq") or "[]")

dump = Path(__file__).parent / "_parental_art_dump.txt"
dump.write_text(art, encoding="utf-8")
print(f"article_content → {dump} ({len(art)}자)")

faq_dump = Path(__file__).parent / "_parental_faq_dump.txt"
faq_dump.write_text(
    "\n\n".join(f"[{i}] Q: {f['question']}\nA: {f['answer']}" for i, f in enumerate(faq)),
    encoding="utf-8"
)
print(f"faq → {faq_dump}")
