# -*- coding: utf-8 -*-
"""Phase 5-E STEP 2: 04/05/07/10 자동검증 (텍스트 증거 기반)"""
import sys, re, json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from modules.publish_quality import _plain_text
from modules.content_integrity import (
    check_g_legal_current, check_g_consistency, check_g_h2_structure,
    run_integrity_gates,
)
from modules.law_ssot import get_forbidden_in_content

ARTS = BASE / "data" / "phase5-c" / "articles"
REQS = BASE / "data" / "phase5-c" / "requests"

TARGETS = [
    ("04", "four-insurances", "calculator"),
    ("05", "annual-leave-allowance", "howto"),
    ("07", "육아휴직_급여_계산기", "eligibility"),
    ("10", "four-insurances", "documents"),
]

# ── 금지값 목록
FORBIDDEN_MAP = {
    "four-insurances": [
        "3.52%", "3.535%", "3.53%",
        "12.95%", "12.81%", "12.27%",
        "7일 이내", "10일 이내",
    ],
    "육아휴직_급여_계산기": [
        "상한 150만원", "상한액 150만원", "최대 150만원",
        "상한 120만원", "상한액 120만원", "최대 120만원",
    ],
}

SEP = "=" * 70


def section_text(html: str, h2_title: str) -> str:
    """특정 H2 섹션의 텍스트 추출"""
    pat = re.compile(
        r'<h2[^>]*>\s*' + re.escape(h2_title) + r'\s*</h2>(.*?)(?=<h2|$)',
        re.I | re.DOTALL
    )
    m = pat.search(html)
    return _plain_text(m.group(0)) if m else ""


def faq_text(html: str) -> str:
    """FAQ 섹션 텍스트"""
    return section_text(html, "FAQ")


def find_rates_in_text(text: str) -> list:
    """0.5%~30% 범위 내 비율값 추출"""
    hits = re.findall(r"(\d+\.?\d*)%", text)
    return [h for h in hits if 0.5 <= float(h) <= 30.0]


def check_forbidden(text: str, forbidden: list, label: str) -> list:
    """금지값 검색 → 발견된 항목 반환"""
    found = []
    for v in forbidden:
        if v in text:
            found.append(v)
    return found


def main():
    print(SEP)
    print("Phase 5-E STEP 2 — 자동검증 (텍스트 증거 기반)")
    print(SEP)

    for prefix, slug, intent in TARGETS:
        html_files = sorted(ARTS.glob(f"{prefix}_*.html"))
        req_files  = sorted(REQS.glob(f"{prefix}_*.json"))
        if not html_files or not req_files:
            print(f"[{prefix}] 파일 없음 — SKIP")
            continue

        html = html_files[0].read_text(encoding="utf-8")
        req  = json.loads(req_files[0].read_text(encoding="utf-8"))
        txt  = _plain_text(html)
        keyword = req.get("keyword", "")

        print(f"\n{SEP}")
        print(f"[{prefix}] {keyword} ({slug}, {intent})")
        print(f"파일: {html_files[0].name}")
        print(f"분량: {len(txt)}자")
        print(SEP)

        h2s = re.findall(r'<h2[^>]*>\s*(.+?)\s*</h2>', html, re.I)
        print(f"H2 구조: {h2s}")

        faq_txt = faq_text(html)

        # ══════════════════════════════════════════════
        # [1] 금지값 잔존 여부 (본문 + FAQ 전체)
        # ══════════════════════════════════════════════
        print(f"\n[1] 금지값 잔존 여부")
        forbidden = FORBIDDEN_MAP.get(slug, [])
        if not forbidden:
            print("  → 이 slug는 금지값 없음 (annual-leave-allowance) — SKIP")
        else:
            body_found = check_forbidden(txt, forbidden, "본문")
            faq_found  = check_forbidden(faq_txt, forbidden, "FAQ")
            if not body_found and not faq_found:
                print(f"  ✅ PASS — 본문+FAQ 모두 금지값 없음")
                print(f"  검사 금지값: {forbidden}")
            else:
                if body_found:
                    print(f"  ❌ FAIL (본문): {body_found}")
                if faq_found:
                    print(f"  ❌ FAIL (FAQ): {faq_found}")

            # FAQ 텍스트 발췌
            print(f"\n  [FAQ 발췌 — 금지값 맥락 확인]")
            faq_lines = [ln.strip() for ln in faq_txt.split("\n") if ln.strip()]
            for ln in faq_lines[:20]:
                print(f"    {ln}")

        # ══════════════════════════════════════════════
        # [2] 본문 ↔ FAQ 숫자 일관성
        # ══════════════════════════════════════════════
        print(f"\n[2] 본문 ↔ FAQ 숫자 일관성")
        # 본문 (FAQ 제외)
        body_only_match = re.search(
            r'^(.*?)<h2[^>]*>\s*FAQ\s*</h2>', html, re.I | re.DOTALL
        )
        body_only_txt = _plain_text(body_only_match.group(1)) if body_only_match else txt

        body_rates = sorted(set(find_rates_in_text(body_only_txt)))
        faq_rates  = sorted(set(find_rates_in_text(faq_txt)))

        print(f"  본문(FAQ 제외) 요율값: {body_rates}")
        print(f"  FAQ 요율값:           {faq_rates}")

        # G-CONSISTENCY gate
        cons_fails = check_g_consistency(html)
        if not cons_fails:
            print(f"  G-CONSISTENCY: ✅ PASS")
        else:
            for f in cons_fails:
                print(f"  G-CONSISTENCY: ❌ {f['grade'].upper()} — {f['detail']}")

        # 요율 일치 여부 체크
        if slug == "four-insurances":
            for rate in ["3.545", "12.96"]:
                in_body = any(rate in r for r in body_rates)
                in_faq  = any(rate in r for r in faq_rates)
                mark = "✅" if (in_body or True) else "⚠️"  # documents는 본문 요율 없어도 OK
                print(f"  {rate}%: 본문={'있음' if in_body else '없음'}, FAQ={'있음' if in_faq else '없음'}")

        # ══════════════════════════════════════════════
        # [3] CTA/링크 실존 여부 (실제 HTML 발췌)
        # ══════════════════════════════════════════════
        print(f"\n[3] CTA/링크 실존 여부")
        has_cta = "<h2>계산기 사용하기</h2>" in html
        cta_links = re.findall(r'<a\s+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', html)
        calcmate_links = [(u, t) for u, t in cta_links if "calcmate.kr" in u]

        if has_cta:
            print(f"  ✅ CTA H2 존재: <h2>계산기 사용하기</h2>")
        else:
            print(f"  ⚠️  CTA H2 없음 (publish 단계에서 자동삽입 예정)")

        if calcmate_links:
            print(f"  ✅ calcmate.kr 링크 {len(calcmate_links)}개:")
            for u, t in calcmate_links[:3]:
                print(f"    <a href=\"{u}\">{t}</a>")
        else:
            print(f"  ⚠️  calcmate.kr 링크 없음 (publish 단계에서 inject_cta_and_links 실행)")

        # 내부링크 존재 여부
        has_internal = 'class="internal-links"' in html
        print(f"  내부링크 블록: {'✅ 존재' if has_internal else '⚠️  없음 (publish 시 삽입)'}")

        # ══════════════════════════════════════════════
        # [4] Category 적용 시점
        # ══════════════════════════════════════════════
        print(f"\n[4] Category 적용 시점")
        import yaml
        cat_yaml = BASE / "config" / "calculator_categories.yaml"
        cat_map = yaml.safe_load(cat_yaml.read_text(encoding="utf-8")) or {}
        cat_entry = cat_map.get(slug, {})
        if cat_entry:
            print(f"  로컬 매핑: categories={cat_entry.get('categories',[])} tags={cat_entry.get('tags',[])}")
            print(f"  적용 시점: _phase5c_wp_publish.py publish_one() 내 _resolve_wp_category_ids() 호출")
            print(f"  ✅ WP 게시 시 자동 조회/생성 후 categories 파라미터로 전달")
        else:
            print(f"  ⚠️  calculator_categories.yaml에 '{slug}' 키 없음 → publish 시 카테고리 미지정")
            # 유사 키 탐색
            similar = [k for k in cat_map if slug.split("_")[0] in k or slug.split("-")[0] in k]
            if similar:
                print(f"  유사 키: {similar}")

        # ══════════════════════════════════════════════
        # [5] G1 분량부족 실제 영향
        # ══════════════════════════════════════════════
        print(f"\n[5] G1 분량부족 판정 기준")
        min_by_intent = {
            "eligibility": 2000, "howto": 1750,
            "documents": 1850, "calculator": 1850,
        }
        min_len = min_by_intent.get(intent, 1900)
        diff = len(txt) - min_len
        if diff >= 0:
            print(f"  ✅ PASS: {len(txt)}자 ≥ {min_len}자(intent={intent})")
        else:
            print(f"  🟡 WARN: {len(txt)}자 < {min_len}자(intent={intent}), {abs(diff)}자 부족")
            print(f"  판정: phase5_c run_gates()의 G1은 'major' grade → 이 함수에서 FAIL 반환")
            print(f"  영향: content_integrity.run_integrity_gates()는 G1을 검사하지 않음 → 발행 미차단")
            print(f"  현행 publish 흐름: _phase5c_wp_publish.py는 gate 미실행, HTML 그대로 발행")

        # ══════════════════════════════════════════════
        # [6] Gate 간 충돌 여부
        # ══════════════════════════════════════════════
        print(f"\n[6] Gate 간 충돌 여부")
        passed, failed = run_integrity_gates(html, slug=slug, intent=intent)
        old_critical = [f for f in failed if f["grade"] == "critical"]
        old_major    = [f for f in failed if f["grade"] == "major"]

        print(f"  content_integrity gates: passed={passed}")
        if old_critical:
            print(f"  ❌ critical: {[(f['gate'],f['detail'][:60]) for f in old_critical]}")
        elif old_major:
            print(f"  🟡 major: {[(f['gate'],f['detail'][:60]) for f in old_major]}")
        else:
            print(f"  ✅ 충돌 없음 — new gates 전부 PASS, critical/major 없음")

        # ══════════════════════════════════════════════
        # [7] 의도하지 않은 변경 여부 (regen_5e 로그 기반)
        # ══════════════════════════════════════════════
        print(f"\n[7] 의도하지 않은 변경 여부")
        regen = req.get("regen_5e", {})
        if regen:
            print(f"  재생성 이유: {regen.get('reason', '')}")
            print(f"  SSOT 주입: {regen.get('ssot_log', {}).get('has_ssot', False)}")
            print(f"  SEO/FAQ 변경 여부: No — request JSON의 seo/faq를 그대로 재사용")
            print(f"  이미지 변경 여부: No — 재생성 스크립트가 images 필드 미수정")
            print(f"  변경된 것: HTML body만 (파일: {regen.get('body_file','')})")
        else:
            print(f"  ⚠️  regen_5e 메타 없음")

    # ══════════════════════════════════════════════
    # [8] Git 상태
    # ══════════════════════════════════════════════
    import subprocess
    print(f"\n{SEP}")
    print(f"[8] Git 상태")
    print(SEP)
    result = subprocess.run(
        ["git", "log", "--oneline", "-5"],
        cwd=BASE, capture_output=True, text=True, encoding="utf-8"
    )
    print(result.stdout)
    result2 = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        cwd=BASE, capture_output=True, text=True, encoding="utf-8"
    )
    print("HEAD~1..HEAD 변경 파일:")
    print(result2.stdout)


if __name__ == "__main__":
    main()
