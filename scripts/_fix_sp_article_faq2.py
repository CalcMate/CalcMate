# -*- coding: utf-8 -*-
"""퇴직금 article_content 내 embed FAQ의 공식 표현 자연어 교체."""
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

sp  = next(c for c in calcs if c.get("slug") == "severance-pay")
art = sp["article_content"]

OLD = (
    "<dd>퇴직금은 평균 월급에 총 근무일수를 365로 나눈 값을 곱하여 계산합니다. "
    "공식은 '평균 월급 × (총 근무일 ÷ 365)'입니다.</dd>"
)
NEW = (
    "<dd>퇴직금은 평균임금에 총 재직일수를 365로 나눈 비율을 곱하여 산출합니다. "
    "예를 들어 평균임금 300만원, 재직 2년(730일)이라면 300만원 × 730 ÷ 365 = 600만원이 됩니다"
    "(근로자퇴직급여보장법 제8조).</dd>"
)

cnt = art.count(OLD)
if cnt == 0:
    raise ValueError(f"패턴 없음: {repr(OLD[:80])}")
print(f"  ✔ 패턴 {cnt}건 발견")

art = art.replace(OLD, NEW, 1)
repo.update(sp["id"], {"article_content": art})
print("  ✔ DB 저장")

# workspace 재생성
calcs = repo.get_all()
sp2 = next(c for c in calcs if c.get("slug") == "severance-pay")
out_dir = WORKSPACE / "severance-pay"
out_dir.mkdir(parents=True, exist_ok=True)
result = generate_calculator(sp2, cfg)
for fname, content in result.items():
    if isinstance(content, str):
        (out_dir / fname).write_text(content, encoding="utf-8")
print("  ✔ workspace 재생성")

# golden 갱신
snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
for fname in ["index.html", "script.js", "style.css"]:
    fpath = out_dir / fname
    if fpath.exists():
        snap["severance-pay"][fname] = hashlib.md5(fpath.read_bytes()).hexdigest()
SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print("  ✔ golden 갱신")
print("완료")
