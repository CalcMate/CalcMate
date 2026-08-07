# -*- coding: utf-8 -*-
import sys, io, re, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests, yaml, json

sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config

cfg = load_config()
wp_url = cfg.get("WORDPRESS_URL","").rstrip("/")
user = cfg.get("WORDPRESS_USERNAME","")
secrets = yaml.safe_load(open("config/secrets.yaml", encoding="utf-8"))
pw = secrets.get("WORDPRESS_APP_PASSWORD","")
token = base64.b64encode(f"{user}:{pw}".encode()).decode()
headers = {"Authorization": f"Basic {token}"}

resp = requests.get(f"{wp_url}/wp-json/wp/v2/posts/118", headers=headers, timeout=15)
data = resp.json()
raw_html = data.get("content", {}).get("raw", "") or data.get("content", {}).get("rendered", "")

# 본문에서 이미지 위치 확인 — 계산 원리 섹션 기준
h2_order = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.I|re.S)
print("H2 순서:", [h.strip() for h in h2_order])
print()

# 이미지 태그 전체
imgs_raw = re.findall(r"<img[^>]*/?>", raw_html, re.I)
for i, img in enumerate(imgs_raw):
    print(f"IMG {i+1} raw: {img[:200]}")
print()

# 본문에서 "계산 원리" 섹션 뒤에 이미지가 있는지 확인
calc_principle_pos = raw_html.lower().find("<h2>계산 원리</h2>")
faq_pos = raw_html.lower().find("<h2>faq</h2>")
for i, img in enumerate(imgs_raw):
    img_pos = raw_html.find(img[:50])
    if calc_principle_pos > 0:
        rel = "계산원리 앞" if img_pos < calc_principle_pos else ("FAQ 앞" if img_pos < faq_pos else "FAQ 뒤")
    else:
        rel = "위치미정"
    print(f"IMG{i+1} 위치: pos={img_pos}, {rel}")
