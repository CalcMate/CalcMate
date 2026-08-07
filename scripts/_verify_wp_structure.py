# -*- coding: utf-8 -*-
"""WordPress에서 Draft HTML을 가져와 구조 검증 (H2/H1/CTA/링크/이미지)."""
import sys, re, json
try:
    import requests
except ImportError:
    print("[ERROR] requests not installed")
    sys.exit(1)

from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
cfg = load_config()

WP_URL  = cfg.get("WORDPRESS_URL", "").rstrip("/")
WP_USER = cfg.get("WORDPRESS_USERNAME", "")
WP_PW   = (cfg.get("WORDPRESS_APP_PASSWORD")
           or cfg.get("WORDPRESS_PASSWORD")
           or (cfg.get("wordpress") or {}).get("app_password", ""))

# 직전 실행에서 발행된 3건
POSTS = [
    (173, "주휴수당"),
    (176, "실업급여"),
    (179, "퇴직금"),
]

REQUIRED_H2 = ["계산기 소개", "입력 방법", "결과 확인", "계산 원리", "주의사항", "FAQ", "계산기 사용하기"]

print(f"WP: {WP_URL}\n")

all_ok = True
for pid, label in POSTS:
    try:
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts/{pid}?context=edit",
            auth=(WP_USER, WP_PW),
            timeout=15,
        )
    except Exception as e:
        print(f"[{label}] WP 연결 실패: {e}")
        all_ok = False
        continue

    if r.status_code != 200:
        print(f"[{label}] HTTP {r.status_code}")
        all_ok = False
        continue

    data = r.json()
    html = (data.get("content") or {}).get("raw") or (data.get("content") or {}).get("rendered", "")
    wp_status = data.get("status", "?")

    # H2 목록
    h2_raw = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S)
    h2_texts = [re.sub(r"<[^>]+>", "", h).strip() for h in h2_raw]
    missing_h2 = [req for req in REQUIRED_H2 if not any(req in t for t in h2_texts)]

    # H1 개수
    h1_count = len(re.findall(r"<h1\b", html, re.I))

    # CTA
    has_cta = bool(re.search(r"계산기\s*사용하기", html, re.I))

    # 내부링크 (href 중 external 아닌 것)
    all_hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    int_links = [h for h in all_hrefs
                 if h and not h.startswith("#") and "javascript" not in h.lower()]

    # 이미지 alt 공백 체크
    img_alts = re.findall(r'<img[^>]*alt=["\']([^"\']*)["\']', html, re.I)
    empty_alts = [a for a in img_alts if not a.strip()]

    # 이미지 위치 (body 내 이미지가 content 앞부분에 있는지)
    img_positions = [m.start() for m in re.finditer(r"<img\b", html, re.I)]

    issues = []
    if missing_h2:
        issues.append(f"H2누락={missing_h2}")
    if h1_count > 1:
        issues.append(f"H1중복={h1_count}개")
    if not has_cta:
        issues.append("CTA없음")
    if len(int_links) < 2:
        issues.append(f"내부링크부족({len(int_links)}개, 최소2)")
    if empty_alts:
        issues.append(f"alt공백이미지={len(empty_alts)}개")

    status_str = "OK" if not issues else "⚠️ " + " / ".join(issues)
    print(f"[{label}] pid={pid}  wp_status={wp_status}  {status_str}")
    print(f"  H2: {h2_texts}")
    print(f"  H1수: {h1_count}  CTA: {has_cta}  내부링크: {len(int_links)}개  이미지: {len(img_positions)}개(alt공백: {len(empty_alts)})")
    print()
    if issues:
        all_ok = False

print("=" * 60)
if all_ok:
    print("구조 검증 완료 — 모든 항목 정상")
else:
    print("일부 이슈 확인 필요")
