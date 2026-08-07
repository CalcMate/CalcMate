# -*- coding: utf-8 -*-
import sys, io, re, base64, os
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

resp = requests.get(f"{wp_url}/wp-json/wp/v2/posts/118", headers=headers, timeout=15)
data = resp.json()
raw_html = data.get("content", {}).get("rendered", "")

h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", raw_html, re.I|re.S)
h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", raw_html, re.I|re.S)
imgs = re.findall(r"<img[^>]*/?>", raw_html, re.I)

print("=== H1 목록 ===")
for h in h1s:
    print("  H1:", h.strip())
print()
print("=== H2 목록 ===")
for i, h in enumerate(h2s, 1):
    print(f"  {i}. {h.strip()}")
print()
print(f"=== IMG 태그 수: {len(imgs)}")
for idx, img in enumerate(imgs):
    m = re.search(r'alt="([^"]*)"', img) or re.search(r"alt='([^']*)'", img)
    val = m.group(1) if m else "NO_ALT"
    src = re.search(r'src="([^"]*)"', img)
    src_val = src.group(1)[:60] if src else "?"
    print(f"  img{idx+1}: alt='{val}' src={src_val}")
print()
print("=== 제목:", data.get("title",{}).get("rendered",""))
print("=== status:", data.get("status",""))
