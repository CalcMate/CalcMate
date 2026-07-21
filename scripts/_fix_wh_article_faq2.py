# -*- coding: utf-8 -*-
"""주휴수당 article_content 내 embed FAQ HTML의 구 공식 교체."""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

ROOT      = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"
SNAPSHOT  = ROOT / "tests" / "golden" / "calculator_snapshots.json"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()

wh  = next(c for c in calcs if c.get("slug") == "weekly-holiday-allowance")
art = wh["article_content"]

OLD_ART_FAQ2 = (
    "<dd>A: 주휴수당은 시급에 주당 평균 근로시간의 비율을 곱하여 계산합니다. "
    "공식은 '주휴수당 = 시급 x (주간 근무시간 / 40 x 8)'입니다.</dd>"
)
NEW_ART_FAQ2 = (
    "<dd>A: 주휴수당은 시급에 주당 근무시간 비율(주간 근무시간 ÷ 40)을 곱한 뒤 8을 곱하여 산출합니다. "
    "예를 들어 시급 10,000원, 주 40시간 근무라면 주휴수당은 10,000원 × 1 × 8시간 = 80,000원이 됩니다. "
    "주 15시간 미만 근로자는 주휴수당이 발생하지 않습니다(근로기준법 제55조, 제18조).</dd>"
)

cnt = art.count(OLD_ART_FAQ2)
if cnt == 0:
    raise ValueError(f"패턴 없음: {repr(OLD_ART_FAQ2[:80])}")
print(f"  ✔ 패턴 {cnt}건 발견")

art = art.replace(OLD_ART_FAQ2, NEW_ART_FAQ2, 1)
repo.update(wh["id"], {"article_content": art})
print("  ✔ DB 저장")

# workspace 재생성
calcs = repo.get_all()
wh2 = next(c for c in calcs if c.get("slug") == "weekly-holiday-allowance")
out_dir = WORKSPACE / "weekly-holiday-allowance"
out_dir.mkdir(parents=True, exist_ok=True)
result = generate_calculator(wh2, cfg)
for fname, content in result.items():
    if isinstance(content, str):
        (out_dir / fname).write_text(content, encoding="utf-8")
print("  ✔ workspace 재생성")

# golden 갱신
snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
for fname in ["index.html", "script.js", "style.css"]:
    fpath = out_dir / fname
    if fpath.exists():
        snap["weekly-holiday-allowance"][fname] = hashlib.md5(fpath.read_bytes()).hexdigest()
SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("  ✔ golden 갱신")
print("완료")
