# -*- coding: utf-8 -*-
"""D-1 demo: 연말정산 article_content에 {total_salary}/{estimated_refund} placeholder 삽입"""
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
repo = CalculatorRepository(get_db_adapter(cfg))
calcs = repo.get_all()
yt = next((c for c in calcs if c.get("slug") == "연말정산_환급액_계산기"), None)
assert yt, "연말정산 calculator not found"

art = str(yt.get("article_content", "") or "")
ph_line = (
    '<p class="sm-personalized-note" style="background:#EBF1F9;border-left:3px solid'
    ' #2C5AA0;padding:10px 14px;border-radius:4px;font-size:14px;color:#1E3F74;">'
    "입력하신 총급여 <strong>{total_salary}</strong> 기준 예상 환급액:"
    " <strong>{estimated_refund}</strong></p>"
)
# 첫 번째 닫는 </p> 뒤에 개인화 안내문 삽입
marker = "</p>"
idx = art.find(marker)
if idx >= 0:
    new_art = art[: idx + len(marker)] + "\n" + ph_line + art[idx + len(marker) :]
else:
    new_art = ph_line + "\n" + art

assert "{total_salary}" in new_art, "placeholder not inserted"
assert "{estimated_refund}" in new_art, "placeholder not inserted"
print("Inserted placeholders OK, length:", len(new_art))

yt["article_content"] = new_art
repo.save(yt)
print("Saved to DB OK")
