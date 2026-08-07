import requests
from requests.auth import HTTPBasicAuth
from modules.config_loader import load_config
from modules.publisher import _wp_auth

cfg = load_config('config/config.yaml')
base_url = cfg.get("WORDPRESS_URL", "").rstrip("/")
auth = HTTPBasicAuth(*_wp_auth(cfg))

# get post 99
url = f"{base_url}/wp-json/wp/v2/posts/99"
resp = requests.get(url, params={"context": "edit"}, auth=auth)
print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Content: {data['content']['rendered']}")
