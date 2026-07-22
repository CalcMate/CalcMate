# -*- coding: utf-8 -*-
"""Phase D SP-8 검증:
1. {variable} 패턴이 생성된 HTML에 잔존하지 않는지 (미치환/오타 차단 확인)
2. PLACEHOLDER_ERROR / PLACEHOLDER_SECURITY 마킹이 없는지
3. 변수명/코드 표현식 노출 없는지 (Phase C 기준 유지)
"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

SUSPECT_CODE = re.compile(r"(\{\{[A-Z_]+\}\}|eval\(|inputs\[|outputs\[|CFG\.|_detail\b|_formula\b)")
SUSPECT_PH   = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")  # 미치환 {variable}
SUSPECT_ERR  = re.compile(r"PLACEHOLDER_(ERROR|SECURITY):")

cfg = load_config()
calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()

all_ok = True
for calc in calcs:
    slug = calc.get("slug", "")
    files = generate_calculator(calc, cfg)
    html = files.get("index.html", "")
    # script 태그 내용 제외 (JS는 정상)
    html_no_script = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)

    issues = []
    for pat, label in [
        (SUSPECT_CODE, "코드노출"),
        (SUSPECT_PH,   "미치환플레이스홀더"),
        (SUSPECT_ERR,  "PH오류마킹"),
    ]:
        hits = pat.findall(html_no_script)
        if hits:
            issues.append(f"{label}: {hits[:3]}")

    if issues:
        print(f"FAIL {slug}: {'; '.join(issues)}")
        all_ok = False
    else:
        print(f"OK   {slug}")

print()
print("SP-8 PASS" if all_ok else "SP-8 FAIL")
sys.exit(0 if all_ok else 1)
