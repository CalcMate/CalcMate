# -*- coding: utf-8 -*-
"""
Phase 5 — 도메인 전환 스크립트 (Cloudflare + Hostinger 연결 완료 후 실행)

변경 내용:
  config.yaml:
    WORDPRESS_URL:  http://salarymate.test  →  https://calcmate.kr
    SITE_URL:       (추가)                  →  https://calcmate.kr
    GITHUB_REPO:    (추가)                  →  calcmate-calculators
    GITHUB_USER:    (추가)                  →  <GitHub 계정명>
  secrets.yaml:
    wordpress.url:  http://salarymate.test  →  https://calcmate.kr

실행 전 반드시:
  1. python scripts/phase5_domain_checklist.py 로 연결 확인
  2. WordPress 실서버 HTTPS 정상 응답 확인
  3. SSL Full 모드 확인

사용법:
  python scripts/phase5_switch_domain.py --github-user YOUR_GITHUB_USER [--apply]
"""
import sys, argparse
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import yaml

LIVE_WP_URL   = "https://calcmate.kr"
LIVE_SITE_URL = "https://calcmate.kr"
LIVE_GITHUB_REPO = "calcmate-calculators"

def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def main():
    parser = argparse.ArgumentParser(description="Phase 5 도메인 전환")
    parser.add_argument("--github-user", required=True, help="GitHub 계정명 (예: johndoe)")
    parser.add_argument("--apply", action="store_true", help="실제 적용 (없으면 dry-run)")
    args = parser.parse_args()
    dry_run = not args.apply

    CONFIG_PATH  = BASE / "config" / "config.yaml"
    SECRETS_PATH = BASE / "config" / "secrets.yaml"

    cfg     = load_yaml(CONFIG_PATH)
    secrets = load_yaml(SECRETS_PATH)

    print("=" * 60)
    print(f"Phase 5 도메인 전환 — {'DRY-RUN' if dry_run else '실제 적용'}")
    print("=" * 60)

    # config.yaml 변경 사항
    cfg_changes = {
        "WORDPRESS_URL": LIVE_WP_URL,
        "SITE_URL":      LIVE_SITE_URL,
        "GITHUB_REPO":   LIVE_GITHUB_REPO,
        "GITHUB_USER":   args.github_user,
    }
    print("\nconfig.yaml 변경 예정:")
    for k, v in cfg_changes.items():
        old = cfg.get(k, "(없음)")
        print(f"  {k}: {old!r} → {v!r}")

    # secrets.yaml 변경 사항
    wp_section = secrets.get("wordpress", {})
    old_wp_url = wp_section.get("url", "(없음)")
    print(f"\nsecrets.yaml 변경 예정:")
    print(f"  wordpress.url: {old_wp_url!r} → {LIVE_WP_URL!r}")

    if dry_run:
        print("\n[DRY-RUN] 실제 변경 없음. --apply 추가 시 적용됩니다.")
    else:
        cfg.update(cfg_changes)
        # _root는 항상 현재 경로로 유지
        cfg["_root"] = str(BASE)
        save_yaml(CONFIG_PATH, cfg)
        print("\nconfig.yaml 업데이트 완료")

        wp_section["url"] = LIVE_WP_URL
        secrets["wordpress"] = wp_section
        save_yaml(SECRETS_PATH, secrets)
        print("secrets.yaml 업데이트 완료")

        print("\n다음 단계:")
        print("  1. python scripts/phase5_domain_checklist.py  # 연결 재확인")
        print("  2. python scripts/phase3_wp_rebrand.py --apply  # WP 브랜드 업데이트")
        print("  3. 회귀테스트: python -m pytest tests/ -v")

if __name__ == "__main__":
    main()
