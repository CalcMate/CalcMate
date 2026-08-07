# -*- coding: utf-8 -*-
import sys, io, yaml
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from modules.calculator_image_prompt_generator import _image_pair

cfg = load_config()

# YAML registry에서 주휴수당 직접 읽기
with open(r"C:\Users\연수\Desktop\블로그자동_v12\docs\registry\labor.yaml", encoding="utf-8") as f:
    data = yaml.safe_load(f)

calcs = data if isinstance(data, list) else data.get("calculators", [])
juhyu = next((c for c in calcs if "주휴수당" in c.get("name","")), None)
if not juhyu:
    print("주휴수당 못찾음. 첫 5:", [c.get("name") for c in calcs[:5]])
    sys.exit(1)

print("calc name:", juhyu.get("name"))
prompts = _image_pair(cfg, juhyu)
print()
print("=== 썸네일 프롬프트 ===")
print(prompts.get("thumbnail", ""))
print()
print("=== 본문 이미지 프롬프트 ===")
print(prompts.get("body", ""))
