# -*- coding: utf-8 -*-
"""
scripts/reverify_full.py — 7종 전체 품질 재검증 하니스 (writer 프롬프트 변경 회귀 확인)

실제 프로덕션 writer 경로(calculator_pipeline._write_article)로 각 계산기를 N회 생성하고,
publish_quality.check_publish_quality로 전체 품질(Gate G1~G8 + AI Score S1~S6)을 판정한다.

- G5(내부링크)/G6(CTA)는 파이프라인 '조립' 단계 게이트라 writer 프롬프트와 무관 →
  최소 final_html(내부링크 2 + CTA 1)을 합성해 통과시키고, writer 기여분만 측정한다.
- 집계: G8 통과율 / 결과분포(PASS/WARN/REWRITE) / REWRITE 드라이버(G4·S5 등) 빈도.

사용: python scripts/reverify_full.py [N]
"""
import io
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.config_loader import load_config
from modules import calculator_pipeline as CP
from modules.publish_quality import check_publish_quality, _check_g8
from modules.registry_loader import load_registry

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8

# A/B baseline: REVERIFY_STRIP_BLOCK=1 이면 writer 프롬프트에서 '[법령 조항 위치 규칙]' 블록을
# 제거하고 생성 → 블록 유무 대조군. (프로덕션 파일은 건드리지 않고 로드 결과만 패치)
import os as _os
if _os.environ.get("REVERIFY_STRIP_BLOCK") == "1":
    _orig_load = CP._load_prompt
    def _stripped():
        t = _orig_load()
        i = t.find("[법령 조항 위치 규칙")
        return t[:i].rstrip() + "\n" if i != -1 else t
    CP._load_prompt = _stripped
    print("### BASELINE 모드: [법령 조항 위치 규칙] 블록 제거하고 생성 ###")

# G5/G6 통과용 최소 조립 꼬리(writer 무관 게이트 오염 차단). 내부링크 2 + CTA 1.
ASSEMBLY_TAIL = (
    '<div class="internal-links">'
    '<a href="https://salarymate.example/a">관련 계산기 A</a>'
    '<a href="https://salarymate.example/b">관련 계산기 B</a>'
    '</div>'
    '<hr/><h2>계산기 사용하기</h2><p>아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다.</p>'
)

TARGETS = [
    ("weekly-holiday-allowance", "주휴수당 계산법", "시급 × (주당 근로시간 ÷ 40 × 8)"),
    ("annual-leave-allowance", "연차수당 계산법", "1일 통상임금 × 미사용 연차일수"),
    ("severance-pay", "퇴직금 계산법", "1일 평균임금 × 30 × (재직일수 / 365)"),
    ("unemployment-benefit", "실업급여 계산법", "1일 구직급여일액 × 소정급여일수"),
    ("four-insurances", "4대보험 계산법", "월 급여 × 각 보험 요율 합계(근로자 부담분)"),
    ("연말정산_환급액_계산기", "연말정산 환급액 계산법", "결정세액 − 기납부세액(원천징수) = 환급 또는 추가납부"),
    ("육아휴직_급여_계산기", "육아휴직 급여 계산법", "통상임금 기반 정률 지급(상·하한은 시행령)"),
]

FAQ = [
    {"question": "누가 받을 수 있나요?", "answer": "요건을 충족하면 받을 수 있습니다."},
    {"question": "언제 신청하나요?", "answer": "정해진 기한 내 신청합니다."},
]


def main():
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    reg = load_registry()
    _sub = "runs_baseline" if _os.environ.get("REVERIFY_STRIP_BLOCK") == "1" else "runs_full"
    outdir = ROOT / "docs" / "experiments" / _sub
    outdir.mkdir(parents=True, exist_ok=True)
    results = {}

    print(f"# 7종 전체 재검증 — N={N}  writer={cfg.get('WRITER_PROVIDER')}/{cfg.get('MODEL_WRITER')}"
          f"  score={cfg.get('CALC_REVIEW_PROVIDER')}/{cfg.get('CALC_REVIEW_MODEL')}")
    print(f"# prompt sha1[:8]={CP._prompt_version()}  ({datetime.now().isoformat(timespec='seconds')})\n")

    for slug, keyword, formula in TARGETS:
        entry = reg.get(slug) or {}
        calc = {"slug": slug, "name": entry.get("name", slug), "formula": formula}
        seo = {"seo_title": f"{keyword} 총정리 | 기준과 방법",
               "seo_description": f"{keyword}을(를) 기준과 예시로 쉽게 설명합니다."}
        forbidden = entry.get("forbidden_articles") or []
        print(f"## {calc['name']} (slug={slug}) — 정답 {entry.get('law')} {entry.get('article') or ''} / forbidden={forbidden}")
        runs = []
        g8_pass = 0
        res_ctr = Counter()
        drivers = Counter()
        for i in range(1, N + 1):
            try:
                body, _tok = CP._write_article(cfg, calc, keyword, seo, FAQ, None)
            except Exception as e:
                print(f"   run{i}: 생성오류 {e}")
                runs.append({"run": i, "error": f"gen:{e}"}); res_ctr["ERR"] += 1
                continue
            final_html = (body or "") + ASSEMBLY_TAIL
            g8 = _check_g8(body, calc)
            g8_ok = len(g8) == 0
            g8_pass += int(g8_ok)
            try:
                pub = check_publish_quality(cfg, body, final_html, calc)
            except Exception as e:
                print(f"   run{i}: 품질판정오류 {e}")
                runs.append({"run": i, "error": f"judge:{e}", "g8": g8_ok}); res_ctr["ERR"] += 1
                continue
            result = pub["result"]
            res_ctr[result] += 1
            rule_gates = [r.get("gate", "") for r in (pub.get("failed_rules") or [])]
            for gate in rule_gates:
                drivers[gate] += 1
            (outdir / f"{slug}_run{i}.html").write_text(body or "", encoding="utf-8")
            runs.append({"run": i, "result": result, "score": pub.get("score"),
                         "g8": g8_ok, "len": len(CP.cleaner.parse_html_body(body) or body or ""),
                         "drivers": rule_gates})
            print(f"   run{i}: {result:<7} score={pub.get('score')} g8={'OK' if g8_ok else 'X'} "
                  f"drivers={rule_gates}")
        results[slug] = {"name": calc["name"], "n": N, "g8_pass": g8_pass,
                         "results": dict(res_ctr), "drivers": dict(drivers), "runs": runs}
        print(f"   → G8 {g8_pass}/{N} · 결과 {dict(res_ctr)} · 드라이버 {dict(drivers)}\n")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (outdir / f"summary_{stamp}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== 전체 요약 ==")
    tot = Counter()
    tot_g8 = tot_n = 0
    g4 = s5 = 0
    for slug, r in results.items():
        tot.update(r["results"])
        tot_g8 += r["g8_pass"]; tot_n += r["n"]
        g4 += r["drivers"].get("G4", 0); s5 += r["drivers"].get("S5", 0)
        print(f"{r['name']:<16} G8 {r['g8_pass']}/{r['n']} · {r['results']} · G4={r['drivers'].get('G4',0)} S5={r['drivers'].get('S5',0)}")
    print(f"\n총 {tot_n}건 · G8통과 {tot_g8}/{tot_n} · 결과 {dict(tot)} · REWRITE드라이버 G4={g4} S5={s5}")
    print(f"summary: docs/experiments/runs_full/summary_{stamp}.json")


if __name__ == "__main__":
    main()
