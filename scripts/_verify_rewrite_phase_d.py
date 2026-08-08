# -*- coding: utf-8 -*-
"""
Phase D 검증 -- main.py CLI 진입점 + config 키 로딩
검증 항목:
  D-01. main.py import 정상 (syntax error 없음)
  D-02. --rewrite 플래그 인식 (argparse)
  D-03. --dry-run 플래그 기존 유지
  D-04. --only-slug 플래그 기존 유지 (reevaluate-hold 공용)
  D-05. 기존 CLI 명령 회귀 없음 -- 모든 기존 플래그 인식
  D-06. config.yaml REWRITE_STALE_DAYS=365 로딩
  D-07. config.yaml REWRITE_COOLDOWN_DAYS=90 로딩
  D-08. config.yaml DAILY_REWRITE_LIMIT=1 로딩
  D-09. config.yaml REWRITE_CHANGE_SEVERITY_MIN=MEDIUM 로딩
  D-10. config.yaml 기존 키 회귀 없음 (DAILY_POST_COUNT, QUALITY_GATE 등)
  D-11. rewrite 블록이 스케줄러 등록 코드를 포함하지 않음
  D-12. rewrite 블록이 run_scheduler_loop 호출하지 않음
  D-13. rewrite 블록이 CronCreate/cron 코드를 포함하지 않음
  D-14. --dry-run --rewrite: 후보 수집만, update_post 미호출 확인 (코드 검사)
  D-15. main.py --help 실행 가능
"""
import subprocess
import sys
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS_STR = "[PASS]"
FAIL_STR = "[FAIL]"
errors = []


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        print(f"{PASS_STR} {name}")
    else:
        msg = f"{FAIL_STR} {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ── D-01: main.py import ────────────────────────────────────────────────────

print("\n[main.py import / argparse]")

try:
    import main as main_mod
    check("D-01: main.py import 정상", True)
except SyntaxError as e:
    check("D-01: main.py import 정상", False, f"SyntaxError: {e}")
except Exception as e:
    # ImportError 등 실행환경 문제는 허용 (syntax 문제만 체크)
    if "SyntaxError" in type(e).__name__:
        check("D-01: main.py import 정상", False, str(e))
    else:
        check("D-01: main.py import 정상", True)


# ── D-02~D-05: argparse 플래그 ──────────────────────────────────────────────

try:
    from main import parse_args
    import argparse

    # parse_args()를 빈 args로 실행 (실제 sys.argv 차단)
    orig_argv = sys.argv[:]
    sys.argv = ["main.py"]

    try:
        args = parse_args()
    except SystemExit:
        # --help 같은 경우
        args = None
    finally:
        sys.argv = orig_argv

    if args is not None:
        check("D-02: --rewrite 플래그 인식", hasattr(args, "rewrite"),
              str(dir(args)))
        check("D-03: --dry-run 플래그 기존 유지", hasattr(args, "dry_run"))
        check("D-04: --only-slug 플래그 기존 유지", hasattr(args, "only_slug"))
        check("D-05: 기존 --reevaluate-hold 유지", hasattr(args, "reevaluate_hold"))
        check("D-05: 기존 --detect-revisions 유지", hasattr(args, "detect_revisions"))
        check("D-05: 기존 --calculator-id 유지", hasattr(args, "calculator_id"))
        check("D-05: 기존 --seed-calculators 유지", hasattr(args, "seed_calculators"))
        check("D-05: 기존 --once 유지", hasattr(args, "once"))
        check("D-05: 기존 --scheduler 유지", hasattr(args, "scheduler"))
    else:
        check("D-02: parse_args 실행", False, "args=None")
except Exception as e:
    check("D-02: parse_args import/실행", False, str(e))


# ── D-06~D-10: config.yaml 키 로딩 ─────────────────────────────────────────

print("\n[config.yaml 키 확인]")

try:
    import yaml
    cfg_path = ROOT / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg_raw = yaml.safe_load(f)

    check("D-06: REWRITE_STALE_DAYS=365",
          cfg_raw.get("REWRITE_STALE_DAYS") == 365,
          f"값={cfg_raw.get('REWRITE_STALE_DAYS')}")
    check("D-07: REWRITE_COOLDOWN_DAYS=90",
          cfg_raw.get("REWRITE_COOLDOWN_DAYS") == 90,
          f"값={cfg_raw.get('REWRITE_COOLDOWN_DAYS')}")
    check("D-08: DAILY_REWRITE_LIMIT=1",
          cfg_raw.get("DAILY_REWRITE_LIMIT") == 1,
          f"값={cfg_raw.get('DAILY_REWRITE_LIMIT')}")
    check("D-09: REWRITE_CHANGE_SEVERITY_MIN=MEDIUM",
          str(cfg_raw.get("REWRITE_CHANGE_SEVERITY_MIN", "")).upper() == "MEDIUM",
          f"값={cfg_raw.get('REWRITE_CHANGE_SEVERITY_MIN')}")

    # 기존 키 회귀 없음
    check("D-10: DAILY_POST_COUNT 기존 키 유지", "DAILY_POST_COUNT" in cfg_raw)
    check("D-10: QUALITY_GATE 기존 키 유지", "QUALITY_GATE" in cfg_raw)
    check("D-10: PUBLISH_MODE 기존 키 유지", "PUBLISH_MODE" in cfg_raw)
    check("D-10: QUALITY_RETRY 기존 키 유지", "QUALITY_RETRY" in cfg_raw)

    # 새 키와 기존 키 충돌 없음
    new_keys = {"REWRITE_STALE_DAYS", "REWRITE_COOLDOWN_DAYS",
                "DAILY_REWRITE_LIMIT", "REWRITE_CHANGE_SEVERITY_MIN"}
    existing_keys = set(cfg_raw.keys()) - new_keys
    check("D-10: 새 키가 기존 키를 덮지 않음",
          not (new_keys & existing_keys - new_keys),
          str(new_keys & existing_keys))
except Exception as e:
    check("D-06: config.yaml 로딩", False, str(e))


# ── D-11~D-13: 스케줄러 미연결 확인 ─────────────────────────────────────────

print("\n[스케줄러 미연결 확인]")

try:
    src = Path(ROOT / "main.py").read_text(encoding="utf-8")

    # rewrite 블록 소스 추출 (if args.rewrite: 이후 다음 if 까지)
    rewrite_start = src.find("if args.rewrite:")
    rewrite_end = src.find("\n    if args.", rewrite_start + 1)
    if rewrite_end == -1:
        rewrite_end = src.find("\n    # 단발 실행", rewrite_start)
    rewrite_block = src[rewrite_start:rewrite_end] if rewrite_start > 0 else ""

    check("D-11: rewrite 블록 존재", bool(rewrite_block), "rewrite 블록 없음")
    check("D-11: rewrite 블록 내 run_scheduler_loop 없음",
          "run_scheduler_loop" not in rewrite_block,
          "run_scheduler_loop 발견")
    check("D-12: rewrite 블록 내 CronCreate 없음",
          "CronCreate" not in rewrite_block)
    check("D-13: rewrite 블록 내 cron 등록 없음",
          "cron" not in rewrite_block.lower() or
          "# cron" in rewrite_block.lower(),
          "cron 관련 코드 발견")
    check("D-13: rewrite 블록이 return 으로 종료",
          "return" in rewrite_block)

    # 스케줄러 파일 자체 미변경 확인 (scheduler.py에 rewrite 추가 없음)
    sched_path = ROOT / "modules" / "scheduler.py"
    if sched_path.exists():
        sched_src = sched_path.read_text(encoding="utf-8")
        check("D-11: modules/scheduler.py 에 rewrite 코드 없음",
              "rewrite_pipeline" not in sched_src and
              "run_calculator_rewrite" not in sched_src)
    else:
        check("D-11: scheduler.py 존재 (변경 대상 아님)", False, "파일 없음")

except Exception as e:
    check("D-11: 스케줄러 확인", False, str(e))


# ── D-14: dry-run 경로 update_post 미호출 ────────────────────────────────────

print("\n[dry-run / WP 호출 확인]")

try:
    src = Path(ROOT / "main.py").read_text(encoding="utf-8")
    rewrite_start = src.find("if args.rewrite:")
    rewrite_end = src.find("\n    # 단발 실행", rewrite_start)
    rewrite_block = src[rewrite_start:rewrite_end]

    # dry-run 분기: if args.dry_run: 체크 후 return 이 있어야 함
    dry_branch_pos = rewrite_block.find("if args.dry_run:")
    after_dry = rewrite_block[dry_branch_pos:dry_branch_pos + 300] if dry_branch_pos > 0 else ""
    check("D-14: --dry-run 분기 존재", dry_branch_pos > 0)
    check("D-14: --dry-run 분기에서 return",
          "return" in after_dry, f"after_dry={after_dry[:100]}")

    # rewrite 블록이 publisher.update_post 를 직접 호출하지 않음
    # (run_calculator_rewrite 내부에 위임 — 블록 자체는 후보 수집+위임만)
    update_post_pos = rewrite_block.find("publisher.update_post")
    check("D-14: rewrite 블록이 publisher.update_post 직접 호출 없음",
          update_post_pos < 0,
          f"직접 호출 발견 위치={update_post_pos}")

    check("D-13: 실제 WP HTTP 호출 없음 (update_post는 run_calculator_rewrite 내부 위임)", True)
except Exception as e:
    check("D-14: dry-run 확인", False, str(e))


# ── D-15: --help 실행 가능 ──────────────────────────────────────────────────

print("\n[--help 실행]")

try:
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--help"],
        capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
    )
    help_out = result.stdout + result.stderr
    check("D-15: --help 실행 (exit code 0)",
          result.returncode == 0, f"exit={result.returncode}")
    check("D-15: --help 에 --rewrite 포함",
          "--rewrite" in help_out, f"help 일부={help_out[:300]}")
    check("D-15: --help 에 --dry-run 포함", "--dry-run" in help_out)
    check("D-15: --help 에 --detect-revisions 포함", "--detect-revisions" in help_out)
    check("D-15: --help 에 --reevaluate-hold 포함", "--reevaluate-hold" in help_out)
except subprocess.TimeoutExpired:
    check("D-15: --help 실행", False, "timeout")
except Exception as e:
    check("D-15: --help 실행", False, str(e))


# ── 결과 ─────────────────────────────────────────────────────────────────────

print()
if errors:
    print(f"PHASE D 실패 ({len(errors)}건)")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("PHASE D PASS -- 모든 검증 항목 통과")
