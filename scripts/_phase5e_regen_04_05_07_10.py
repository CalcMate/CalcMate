# -*- coding: utf-8 -*-
"""
scripts/_phase5e_regen_04_05_07_10.py — Phase 5-E STEP 1: 04/05/07/10 재생성

목적:
  - LAW_SSOT 주입 확인 (G-LEGAL-CURRENT 통과 검증)
  - 파이프라인 경로 사용 (사람이 손으로 고치는 게 아님)
  - 새 Gate 5종 적용한 본문 생성

규칙:
  - 기존 request JSON(SEO/FAQ/example_context)은 재사용, body만 재생성
  - 07/10번 FAQ + example_context는 Phase 5-E 수정본 사용 (상한금액/구요율 제거 완료)
  - 이미지는 재생성하지 않음 (기존 파일 유지)
  - 완료 후 logs/content_pipeline/ 산하에 SSOT 참조 로그 저장
"""
from __future__ import annotations
import sys
import json
import re
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.law_ssot import get_ssot_prompt_block, get_forbidden_in_content
from modules.content_integrity import run_integrity_gates
from modules.publish_quality import _plain_text
from scripts.phase5_c_sample_gen import (
    generate_article_body,
    run_gates,
    ARTICLES_DIR,
)

REQUESTS_DIR = BASE / "data" / "phase5-c" / "requests"
LOG_DIR = BASE / "logs" / "content_pipeline"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# SSOT가 있는 slug 목록
_SSOT_SLUGS = {"four-insurances", "육아휴직_급여_계산기"}

# 재생성 대상
REGEN_TARGETS = [
    {"no": 4,  "file_prefix": "04",
     "req_glob": "04_four-insurances_calculator.json",
     "ssot_reason": "G-LEGAL-CURRENT: 구 요율(3.52%/12.95%) 검출"},
    {"no": 5,  "file_prefix": "05",
     "req_glob": "05_annual-leave-allowance_howto.json",
     "ssot_reason": "G-H2: 레거시 H2('계산기 이용 방법') 검출"},
    {"no": 7,  "file_prefix": "07",
     "req_glob": "07_육아휴직_급여_계산기_eligibility.json",
     "ssot_reason": "G-LEGAL-CURRENT: 구 상한금액(150만원/120만원) 검출"},
    {"no": 10, "file_prefix": "10",
     "req_glob": "10_four-insurances_documents.json",
     "ssot_reason": "G-LEGAL-CURRENT: 구 요율(3.52%) + '7일 이내' 검출"},
]


def load_request(prefix: str) -> tuple[dict, Path] | tuple[None, None]:
    """request JSON 로드"""
    matches = sorted(REQUESTS_DIR.glob(f"{prefix}_*.json"))
    if not matches:
        print(f"  [SKIP] request JSON 없음: {prefix}_*.json")
        return None, None
    path = matches[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, path


def find_existing_html(prefix: str) -> Path | None:
    """기존 HTML 파일 찾기"""
    matches = sorted(ARTICLES_DIR.glob(f"{prefix}_*.html"))
    return matches[0] if matches else None


def run_new_gates(body_html: str, slug: str, example_context: dict, intent: str) -> dict:
    """content_integrity.run_integrity_gates() 실행 → 요약 반환"""
    passed, failed = run_integrity_gates(
        body_html, slug=slug, example_context=example_context, intent=intent
    )
    critical = [f for f in failed if f.get("grade") == "critical"]
    major = [f for f in failed if f.get("grade") == "major"]
    return {
        "passed_gates": passed,
        "failed": failed,
        "critical": critical,
        "major": major,
        "all_clear": len(critical) == 0 and len(major) == 0,
    }


def regen_one(cfg: dict, calcs_by_slug: dict, target: dict) -> dict:
    no = target["no"]
    prefix = target["file_prefix"]
    ssot_reason = target["ssot_reason"]
    ts = datetime.now().isoformat()

    print(f"\n{'='*60}")
    print(f"[{prefix}] 재생성 시작 (원인: {ssot_reason})")
    print(f"{'='*60}")

    # 1. request JSON 로드
    req_data, req_path = load_request(prefix)
    if not req_data:
        return {"no": no, "status": "SKIP", "reason": "request JSON 없음"}

    slug = req_data.get("slug", "")
    keyword = req_data.get("keyword", "")
    intent = req_data.get("intent", "calculator")
    seo = req_data.get("seo", {})
    faq = req_data.get("faq", [])
    example_context = req_data.get("example_context")

    print(f"  slug: {slug}, keyword: {keyword}, intent: {intent}")
    print(f"  request JSON: {req_path.name}")

    # 2. calc 메타데이터 로드
    calc = calcs_by_slug.get(slug)
    if not calc:
        print(f"  [FAIL] DB에 calc 없음: {slug}")
        return {"no": no, "status": "FAIL", "reason": f"calc 없음: {slug}"}

    # 3. LAW_SSOT 블록 로드 (있는 slug만)
    ssot_block = ""
    ssot_log = {"slug": slug, "has_ssot": False, "injected_at": ts}
    if slug in _SSOT_SLUGS:
        ssot_block = get_ssot_prompt_block(slug)
        forbidden = get_forbidden_in_content(slug)
        ssot_log.update({
            "has_ssot": bool(ssot_block),
            "ssot_values": [
                {"item": f["item"], "current": f["current"], "forbidden": f["value"]}
                for f in forbidden
            ],
        })
        if ssot_block:
            print(f"  LAW_SSOT 주입: {slug} ({len(ssot_block)}자)")
            for f in forbidden:
                print(f"    금지값: {f['value']} (현행: {f['current']})")
        else:
            print(f"  LAW_SSOT: {slug}에 content_ssot 없음")
    else:
        print(f"  LAW_SSOT: {slug} — SSOT 없음, 순수 H2 구조 재생성")

    # 4. 기존 HTML 파악 (before)
    existing_html_path = find_existing_html(prefix)
    body_before = ""
    if existing_html_path:
        body_before = existing_html_path.read_text(encoding="utf-8")
        print(f"  기존 HTML: {existing_html_path.name} ({len(body_before)}자)")

    # 5. 본문 재생성
    print(f"  본문 재생성 중...")
    try:
        body_html, token_info = generate_article_body(
            cfg, calc, keyword, seo, faq, example_context, intent,
            law_ssot_block=ssot_block,
        )
    except Exception as e:
        print(f"  [FAIL] 본문 생성 실패: {e}")
        return {"no": no, "status": "FAIL", "reason": f"본문 생성 실패: {e}"}

    text_len = len(_plain_text(body_html))
    print(f"  생성 완료: {text_len}자 (모델: {token_info.get('model', '')})")

    # 6. HTML 저장 (기존 파일 덮어쓰기 or 신규 저장)
    if existing_html_path:
        out_path = existing_html_path
    else:
        # 파일명 새로 생성
        slug_safe = re.sub(r'[^\w\-]', '_', slug)
        kw_safe = keyword[:20].replace(' ', '_')
        out_path = ARTICLES_DIR / f"{prefix}_{slug_safe}_{kw_safe}.html"

    out_path.write_text(body_html, encoding="utf-8")
    print(f"  저장: {out_path.name}")

    # 7. 새 Gate 검증 (G-LEGAL-CURRENT, G-CONSISTENCY, G-H2 포함)
    print(f"  새 Gate 검증 (content_integrity)...")
    new_gate = run_new_gates(body_html, slug, example_context, intent)
    print(f"  새 Gate: {'ALL CLEAR' if new_gate['all_clear'] else 'FAIL'} "
          f"(passed={len(new_gate['passed_gates'])}, "
          f"critical={len(new_gate['critical'])}, major={len(new_gate['major'])})")
    for f in new_gate["critical"]:
        print(f"    🔴 {f['gate']}: {f['detail'][:80]}")
    for f in new_gate["major"]:
        print(f"    🟡 {f['gate']}: {f['detail'][:80]}")

    # 8. 기존 Gate 검증 (phase5_c_sample_gen.run_gates)
    print(f"  기존 Gate 검증 (phase5_c)...")
    try:
        old_gate = run_gates(body_html, calc, intent, keyword, cfg, example_context)
        print(f"  기존 Gate: {'PASS' if old_gate['passed'] else 'FAIL'} "
              f"(H2={old_gate['h2_count']}, FAQ={old_gate['faq_count']}, "
              f"len={old_gate['text_length']}자)")
        if old_gate["critical"]:
            for f in old_gate["critical"]:
                print(f"    🔴 {f['gate']}: {f['detail'][:80]}")
        if old_gate["major"]:
            for f in old_gate["major"]:
                print(f"    🟡 {f['gate']}: {f['detail'][:80]}")
    except Exception as e:
        print(f"  기존 Gate 실패(계속): {e}")
        old_gate = {"error": str(e)}

    # 9. request JSON에 regen 메타 추가
    req_data["regen_5e"] = {
        "regenerated_at": ts,
        "reason": ssot_reason,
        "ssot_log": ssot_log,
        "token_info": token_info,
        "body_file": out_path.name,
        "new_gate_result": new_gate,
        "old_gate_result": old_gate,
    }
    req_path.write_text(
        json.dumps(req_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  request JSON 업데이트: {req_path.name}")

    return {
        "no": no,
        "prefix": prefix,
        "slug": slug,
        "keyword": keyword,
        "status": "OK" if new_gate["all_clear"] else "GATE_FAIL",
        "body_file": out_path.name,
        "text_len": text_len,
        "new_gate_all_clear": new_gate["all_clear"],
        "new_gate_critical": [f["gate"] for f in new_gate["critical"]],
        "new_gate_major": [f["gate"] for f in new_gate["major"]],
        "old_gate_passed": old_gate.get("passed", False),
        "h2_list": old_gate.get("h2_list", []),
        "ssot_injected": bool(ssot_block),
    }


def main():
    print("=" * 70)
    print("Phase 5-E STEP 1: 04/05/07/10 재생성 (LAW_SSOT 주입)")
    print(f"시작: {datetime.now().isoformat()}")
    print("=" * 70)

    cfg = load_config()
    db = get_db_adapter(cfg)
    repo = CalculatorRepository(db)
    calcs_by_slug = {c["slug"]: c for c in repo.get_all() if c.get("slug")}

    results = []
    for target in REGEN_TARGETS:
        r = regen_one(cfg, calcs_by_slug, target)
        results.append(r)
        time.sleep(2)

    # 최종 보고
    print("\n" + "=" * 70)
    print("STEP 1 재생성 결과")
    print("=" * 70)
    for r in results:
        status_icon = "✅" if r.get("new_gate_all_clear") else "❌"
        print(f"[{r.get('prefix', r['no'])}] {status_icon} {r.get('keyword', '')} ({r.get('slug', '')})")
        print(f"       상태: {r.get('status', '?')} | 본문: {r.get('text_len', 0)}자")
        print(f"       SSOT주입: {r.get('ssot_injected', False)} | H2: {r.get('h2_list', [])}")
        if r.get("new_gate_critical"):
            print(f"       🔴 critical: {r['new_gate_critical']}")
        if r.get("new_gate_major"):
            print(f"       🟡 major: {r['new_gate_major']}")

    # SSOT 참조 로그 저장
    log_path = LOG_DIR / f"phase5e_regen_step1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(
        json.dumps({"step": "STEP1", "ran_at": datetime.now().isoformat(), "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n로그 저장: {log_path}")

    ok_count = sum(1 for r in results if r.get("new_gate_all_clear"))
    fail_count = len(results) - ok_count
    print(f"\n총계: 성공={ok_count} / Gate실패={fail_count}")
    print("\n[STEP 1 완료] 승인 후 STEP 2(자동검증) 진행 예정 — 여기서 중단.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
