"""
Phase A 검증 — modules/rewrite_pipeline.py 상태 파일 관리 함수
검증 항목:
  1. _processed_path() — 경로 반환, 디렉터리 자동 생성
  2. _load_rewrite_processed() — 파일 없을 때 {} 반환
  3. _mark_processed() — 기록 후 내용 확인
  4. 중복 호출 — 기존 항목 보존 + 신규 항목 추가
  5. 파일 손상 시 {} 반환
  6. write_article_for_rewrite 래퍼 import 가능 여부
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = "[PASS]"
FAIL = "[FAIL]"
errors = []


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        print(f"{PASS} {name}")
    else:
        msg = f"{FAIL} {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ── 테스트용 최소 cfg ─────────────────────────────────────────────────────────

with tempfile.TemporaryDirectory() as tmpdir:
    cfg = {"_root": tmpdir, "DB_ADAPTER": "sqlite"}

    from modules.rewrite_pipeline import _processed_path, _load_rewrite_processed, _mark_processed

    # 1. _processed_path
    p = _processed_path(cfg)
    check("_processed_path 반환 타입 Path", isinstance(p, Path))
    check("_processed_path 디렉터리 생성", p.parent.exists(), str(p.parent))
    check("_processed_path 파일명", p.name == "rewrite_processed.json")

    # 2. _load_rewrite_processed — 파일 없을 때
    result = _load_rewrite_processed(cfg)
    check("_load_rewrite_processed 없을 때 {}", result == {}, str(result))

    # 3. _mark_processed — 첫 번째 기록
    _mark_processed(cfg, "min_wage_hourly__2026-08-01", "article-001", "success")
    check("_mark_processed 후 파일 존재", p.exists())
    data = json.loads(p.read_text(encoding="utf-8"))
    key = "min_wage_hourly__2026-08-01"
    check("_mark_processed 키 존재", key in data, str(list(data.keys())))
    check("_mark_processed result 값", data[key]["result"] == "success")
    check("_mark_processed article_id", data[key]["article_id"] == "article-001")
    check("_mark_processed processed_at 존재", bool(data[key].get("processed_at")))

    # 4. 중복 호출 — 기존 항목 보존 + 신규 항목 추가
    _mark_processed(cfg, "hi_rate__2026-07-15", "article-002", "success")
    data2 = json.loads(p.read_text(encoding="utf-8"))
    check("중복 호출 후 기존 항목 보존", key in data2)
    check("중복 호출 후 신규 항목 추가", "hi_rate__2026-07-15" in data2)

    # 5. _load_rewrite_processed — 기록 후 로딩
    loaded = _load_rewrite_processed(cfg)
    check("_load_rewrite_processed 로딩 일치", loaded == data2, str(loaded))

    # 6. 파일 손상 시 {} 반환
    p.write_text("NOT_JSON{{{", encoding="utf-8")
    corrupted = _load_rewrite_processed(cfg)
    check("파일 손상 시 {} 반환", corrupted == {}, str(corrupted))


# ── write_article_for_rewrite import 가능 여부 ───────────────────────────────

try:
    from modules.calculator_pipeline import write_article_for_rewrite
    import inspect
    sig = inspect.signature(write_article_for_rewrite)
    params = list(sig.parameters.keys())
    check("write_article_for_rewrite import 성공", True)
    check("write_article_for_rewrite sig: cfg", "cfg" in params)
    check("write_article_for_rewrite sig: failed_rules", "failed_rules" in params)
except Exception as e:
    check("write_article_for_rewrite import 성공", False, str(e))


# ── rewrite_pipeline import 전체 ─────────────────────────────────────────────

try:
    import modules.rewrite_pipeline as rp
    check("rewrite_pipeline 모듈 import 성공", True)
    check("collect_rewrite_candidates 존재", hasattr(rp, "collect_rewrite_candidates"))
    check("run_calculator_rewrite 존재", hasattr(rp, "run_calculator_rewrite"))
    check("_load_rewrite_processed 존재", hasattr(rp, "_load_rewrite_processed"))
    check("_mark_processed 존재", hasattr(rp, "_mark_processed"))
except Exception as e:
    check("rewrite_pipeline 모듈 import 성공", False, str(e))


# ── 결과 ─────────────────────────────────────────────────────────────────────

print()
if errors:
    print(f"❌ PHASE A 실패 ({len(errors)}건)")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print(f"✅ PHASE A PASS — 모든 검증 항목 통과")
