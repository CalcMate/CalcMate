# -*- coding: utf-8 -*-
"""repo.save() 지속성 테스트"""
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
repo = CalculatorRepository(get_db_adapter(cfg))
calcs = repo.get_all()
yt = next((c for c in calcs if c.get("slug") == "연말정산_환급액_계산기"), None)

art = str(yt.get("article_content", "") or "")
print("has {total_salary}:", "{total_salary}" in art)
print("art length:", len(art))

# placeholder 삽입 (script에서와 동일 방식)
ph_line = (
    '<p class="sm-personalized-note" style="background:#EBF1F9;border-left:3px solid'
    " #2C5AA0;padding:10px 14px;border-radius:4px;font-size:14px;color:#1E3F74;\">"
    "입력하신 총급여 <strong>{total_salary}</strong> 기준 예상 환급액:"
    " <strong>{estimated_refund}</strong></p>"
)
if "{total_salary}" not in art:
    idx = art.find("</p>")
    if idx >= 0:
        new_art = art[: idx + 4] + "\n" + ph_line + art[idx + 4 :]
    else:
        new_art = ph_line + "\n" + art
    print("Inserting placeholders via DB update...")
    yt["article_content"] = new_art
    # insert가 아닌 update로 기존 레코드 수정
    repo._db.update("calculators", yt["id"], {"article_content": new_art})
    print("update done")

    # 재로드 확인
    calcs2 = repo.get_all()
    yt2 = next((c for c in calcs2 if c.get("slug") == "연말정산_환급액_계산기"), None)
    art2 = str(yt2.get("article_content", "") or "")
    print("After save has {total_salary}:", "{total_salary}" in art2)
    print("After save art length:", len(art2))
else:
    print("Placeholders already present, no action needed.")
