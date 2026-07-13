# -*- coding: utf-8 -*-
"""
scripts/reverify_forbidden.py — legal_basis forbidden_articles 혼입 재검증 하니스

실제 프로덕션 writer 경로(calculator_pipeline._write_article)를 그대로 호출해
지정 계산기(slug)를 N회 생성하고, publish_quality._check_g8로 G8 통과/실패 및
forbidden_articles(예: 제34조/제74조) 혼입 여부를 집계한다.

사용: python scripts/reverify_forbidden.py [N]
"""
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.config_loader import load_config
from modules import calculator_pipeline as CP
from modules.publish_quality import _check_g8
from modules.registry_loader import load_registry

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8

# 대상: 퇴직금, 육아휴직. keyword/seo/formula는 8회 고정(변인=article 생성 비결정성만).
TARGETS = [
    {
        "slug": "severance-pay",
        "keyword": "퇴직금 계산법",
        "formula": "1일 평균임금 × 30 × (재직일수 / 365)",
        "seo": {"seo_title": "퇴직금 계산법 총정리 | 평균임금·재직일수 기준",
                "seo_description": "퇴직금이 어떻게 계산되는지 평균임금과 재직일수 기준으로 쉽게 설명합니다."},
    },
    {
        "slug": "육아휴직_급여_계산기",
        "keyword": "육아휴직 급여 계산법",
        "formula": "통상임금 기반 정률 지급(상·하한은 시행령, 본문 금액 미언급)",
        "seo": {"seo_title": "육아휴직 급여 계산법 | 지급 조건과 기준",
                "seo_description": "육아휴직 급여 지급 조건과 계산 기준을 최신 안내 기준으로 설명합니다."},
    },
]

FAQ = [
    {"question": "누가 받을 수 있나요?", "answer": "요건을 충족하면 받을 수 있습니다."},
    {"question": "언제 신청하나요?", "answer": "정해진 기한 내 신청합니다."},
]


def classify(g8_fails):
    """_check_g8 반환을 forbidden 혼입 / 필수 누락으로 분류."""
    forbidden, missing = [], []
    for f in g8_fails:
        d = f.get("detail", "")
        if d.startswith("금지된 조항 등장"):
            forbidden.append(d)
        else:
            missing.append(d)
    return forbidden, missing


def main():
    cfg = load_config(str(ROOT / "config" / "config.yaml"))
    reg = load_registry()
    outdir = ROOT / "docs" / "experiments" / "runs"
    outdir.mkdir(parents=True, exist_ok=True)
    all_results = {}

    print(f"# forbidden 재검증 — N={N}  writer={cfg.get('WRITER_PROVIDER')}/{cfg.get('MODEL_WRITER')}")
    print(f"# prompt sha1[:8]={CP._prompt_version()}  ({datetime.now().isoformat(timespec='seconds')})\n")

    for t in TARGETS:
        slug = t["slug"]
        entry = reg.get(slug) or {}
        calc = {"slug": slug, "name": entry.get("name", slug), "formula": t["formula"]}
        forbidden_list = entry.get("forbidden_articles") or []
        print(f"## {calc['name']} (slug={slug})")
        print(f"   정답: {entry.get('law')} {entry.get('article')} / forbidden={forbidden_list}")
        runs = []
        pass_n = 0
        for i in range(1, N + 1):
            try:
                html, _tok = CP._write_article(cfg, calc, t["keyword"], t["seo"], FAQ, None)
            except Exception as e:
                print(f"   run{i}: 생성 오류 {e}")
                runs.append({"run": i, "error": str(e)})
                continue
            g8 = _check_g8(html, calc)
            forbidden_hit, missing = classify(g8)
            ok = len(g8) == 0
            pass_n += int(ok)
            (outdir / f"{slug}_run{i}.html").write_text(html or "", encoding="utf-8")
            runs.append({"run": i, "pass": ok, "len": len(html or ""),
                         "forbidden": forbidden_hit, "missing": missing})
            tag = "PASS" if ok else "FAIL"
            extra = ""
            if forbidden_hit:
                extra += f"  [금지혼입 {len(forbidden_hit)}]"
            if missing:
                extra += f"  [누락 {len(missing)}]"
            print(f"   run{i}: {tag}  len={len(html or '')}{extra}")
        print(f"   → G8 통과 {pass_n}/{N}\n")
        all_results[slug] = {"pass": pass_n, "n": N, "forbidden_articles": forbidden_list, "runs": runs}

    (outdir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("== 요약 ==")
    for slug, r in all_results.items():
        fb = sum(1 for x in r["runs"] if x.get("forbidden"))
        print(f"{slug}: G8 {r['pass']}/{r['n']}  · forbidden 혼입 run 수={fb}")


if __name__ == "__main__":
    main()
