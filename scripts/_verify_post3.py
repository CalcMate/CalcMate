# -*- coding: utf-8 -*-
import sys, io, re, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests, yaml

sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")
from modules.config_loader import load_config

cfg = load_config()
wp_url = cfg.get("WORDPRESS_URL","").rstrip("/")
user = cfg.get("WORDPRESS_USERNAME","")
secrets = yaml.safe_load(open("config/secrets.yaml", encoding="utf-8"))
pw = secrets.get("WORDPRESS_APP_PASSWORD","")
token = base64.b64encode(f"{user}:{pw}".encode()).decode()
headers = {"Authorization": f"Basic {token}"}

resp = requests.get(f"{wp_url}/wp-json/wp/v2/posts/121", headers=headers, timeout=15)
data = resp.json()
raw_html = data.get("content", {}).get("rendered", "")

h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", raw_html, re.I|re.S)
h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.I|re.S)
imgs_raw = re.findall(r"<img[^>]*/?>", raw_html, re.I)

print("=== H1 ===")
for h in h1s: print("  H1:", h.strip())
print()
print("=== H2 순서 ===")
for i,h in enumerate(h2s,1): print(f"  {i}. {h.strip()}")
print()
print(f"=== IMG 태그 ({len(imgs_raw)}개) ===")
for idx,img in enumerate(imgs_raw):
    m_alt = re.search(r'alt="([^"]*)"', img) or re.search(r"alt='([^']*)'", img)
    alt = m_alt.group(1) if m_alt else "NO_ALT"
    m_src = re.search(r'src="([^"]*)"', img) or re.search(r"src='([^']*)'", img)
    src = (m_src.group(1)[-50:]) if m_src else "?"
    print(f"  img{idx+1}: alt='{alt}'")
    print(f"          src=...{src}")
print()

# 이미지 위치 vs 계산 원리
calc_pos = raw_html.lower().find("<h2>계산 원리</h2>")
faq_pos = raw_html.lower().find("<h2>faq</h2>")
print(f"계산 원리 H2 pos: {calc_pos}")
print(f"FAQ H2 pos: {faq_pos}")
for idx,img in enumerate(imgs_raw):
    img_pos = raw_html.find(img[:40])
    if img_pos < 0:
        img_pos = raw_html.find(img[:20])
    zone = "계산원리 앞" if img_pos <= calc_pos else ("FAQ 앞(계산원리 뒤)" if img_pos < faq_pos else "FAQ 뒤")
    print(f"  img{idx+1} pos={img_pos} → {zone}")
