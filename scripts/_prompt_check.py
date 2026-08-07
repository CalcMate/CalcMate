# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config
from modules.calculator_image_prompt_generator import _image_pair

cfg = load_config()

# 주휴수당 계산기 최소 dict
juhyu = {
    "id": "calc_20260702221622_621a",
    "name": "주휴수당 계산기",
    "formula": "시급 x (주간근무시간 / 40 x 8)",
    "description": "주휴수당 자동 계산기",
}
p = _image_pair(cfg, juhyu)
print("=== 썸네일 프롬프트 ===")
print(p.get("thumbnail",""))
print()
print("=== 본문 이미지 프롬프트 ===")
print(p.get("body",""))
