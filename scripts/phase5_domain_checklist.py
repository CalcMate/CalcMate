# -*- coding: utf-8 -*-
"""
Phase 5 — 도메인 연결 상태 점검 스크립트
실행: python scripts/phase5_domain_checklist.py

확인 항목:
  1. calcmate.kr / calcmate.co.kr DNS 해석 (네임서버 연결 여부)
  2. WordPress 실서버 HTTPS 응답
  3. GitHub Pages 계산기 앱 응답
  4. SSL 인증서 유효성
"""
import sys, socket, ssl, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from modules.config_loader import load_config

cfg = load_config()

DOMAINS = ["calcmate.kr", "calcmate.co.kr"]
WP_LIVE_URL = "https://calcmate.kr"          # 라이브 블로그 도메인 (Phase 5 완료 후)
GITHUB_USER = cfg.get("GITHUB_USER", "")    # config.yaml에 GITHUB_USER 추가 필요
GITHUB_REPO = cfg.get("GITHUB_REPO", "calcmate-calculators")
GITHUB_PAGES_URL = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/" if GITHUB_USER else ""

print("=" * 60)
print("Phase 5 — 도메인 연결 상태 점검")
print("=" * 60)

# ── 1. DNS 해석 ────────────────────────────────────────────────
print("\n[1] DNS 해석")
for domain in DOMAINS:
    try:
        ip = socket.gethostbyname(domain)
        print(f"  {domain} → {ip}  ✅")
    except Exception as e:
        print(f"  {domain} → 해석 실패 (네임서버 미전파 또는 미등록) ❌")

# ── 2. WordPress 실서버 HTTPS ───────────────────────────────────
print(f"\n[2] WordPress 실서버 ({WP_LIVE_URL})")
try:
    req = urllib.request.Request(f"{WP_LIVE_URL}/wp-json/wp/v2/posts?per_page=1",
                                  headers={"User-Agent": "CalcMate-Check/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"  HTTP {resp.status}  ✅  (WP REST API 응답)")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}  {'✅ (WP 응답)' if e.code in (200, 401, 403) else '❌'}")
except Exception as e:
    print(f"  연결 실패: {e}  ❌")

# ── 3. GitHub Pages 계산기 앱 ──────────────────────────────────
print(f"\n[3] GitHub Pages 계산기 앱")
if not GITHUB_USER:
    print("  [SKIP] config.yaml에 GITHUB_USER가 없습니다.")
    print("  추가 방법: config.yaml에 GITHUB_USER: your-github-username 추가")
elif not GITHUB_PAGES_URL:
    print("  [SKIP] GITHUB_PAGES_URL 구성 실패")
else:
    try:
        req = urllib.request.Request(GITHUB_PAGES_URL,
                                      headers={"User-Agent": "CalcMate-Check/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  {GITHUB_PAGES_URL}")
            print(f"  HTTP {resp.status}  ✅")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}  {'✅' if e.code == 200 else '❌'}")
    except Exception as e:
        print(f"  연결 실패: {e}  ❌")

# ── 4. SSL 인증서 ─────────────────────────────────────────────
print(f"\n[4] SSL 인증서 (calcmate.kr)")
try:
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(socket.socket(), server_hostname="calcmate.kr") as s:
        s.settimeout(5)
        s.connect(("calcmate.kr", 443))
        cert = s.getpeercert()
        subject = dict(x[0] for x in cert.get("subject", []))
        not_after = cert.get("notAfter", "")
        print(f"  발급 대상: {subject.get('commonName', '?')}")
        print(f"  만료일: {not_after}")
        print(f"  SSL 인증서 유효  ✅")
except Exception as e:
    print(f"  SSL 확인 실패: {e}  ❌")
    print("  Cloudflare SSL 모드를 Full로 설정했는지 확인하세요.")

print("\n" + "=" * 60)
print("점검 완료")
print()
print("Phase 5 완료 조건:")
print("  □ calcmate.kr DNS 해석 성공 (Cloudflare 네임서버 전파)")
print("  □ https://calcmate.kr WP REST API 응답")
print("  □ GitHub Pages 계산기 앱 정상 응답")
print("  □ SSL 인증서 유효 (Cloudflare → Full 모드)")
