# -*- coding: utf-8 -*-
"""
tools/dev_assistant.py — OpenRouter 보조 개발자 CLI

Claude Code 사용량이 많을 때 OpenRouter 모델로
CalcMate 코드 분석·리뷰·간단한 수정 제안을 수행한다.

이 스크립트는 직접 파일을 수정하지 않는다.
모든 응답은 사용자가 검토 후 적용한다.

사용법:
  python tools/dev_assistant.py                              # 대화형 모드
  python tools/dev_assistant.py --ping                      # 연결 테스트
  python tools/dev_assistant.py --file modules/app_factory.py
  python tools/dev_assistant.py --file modules/ai_provider.py \\
      --question "이 파일의 구조를 설명해줘"               # 1회 질의
  python tools/dev_assistant.py --model qwen/qwen2.5-coder-32b-instruct

환경변수 / config/secrets.yaml:
  OPENROUTER_API_KEY  필수
  OPENROUTER_MODEL    선택 (기본: deepseek/deepseek-r1-0528)
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── 상수 ──────────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "deepseek/deepseek-r1-0528"
LOG_PATH = ROOT / "data" / "logs" / "dev_assistant.jsonl"

# 보조 개발자 시스템 프롬프트
_SYSTEM = """너는 CalcMate(SalaryMate v12) 프로젝트의 보조 개발자다.

[프로젝트 개요]
- SalaryMate v12: Python/Streamlit 기반 한국 급여·노동법 계산기 플랫폼
- 핵심 모듈: formula_engine.py, app_factory.py, dashboard.py, ai_provider.py
- 계약 구조: Formula Lifecycle (not_generated → ai_suggested → pending_validation → operator_confirmed)
- 주요 계층: Registry(YAML) / Contract Instance(YAML) / App Factory / Formula Engine

[역할]
- 코드 분석, 리뷰, 설명
- 버그 원인 분석 및 수정 방향 제안
- 테스트 실패 원인 분석
- 소규모 수정 코드 제안 (적용은 사용자가 직접)

[제한]
- Registry / Contract 핵심 구조는 임의로 변경하지 않는다
- 대규모 리팩터링, 배포 구조 변경은 제안만 하고 결정은 사용자에게 맡긴다
- 한국어로 답변한다. 코드 블록은 언어 태그를 붙인다.
- 민감 정보(API Key, 비밀번호)는 절대 요청하지 않고 출력하지 않는다."""


# ── 키/모델 로드 ──────────────────────────────────────────────────────────────
def _load_api_key() -> str:
    """
    OPENROUTER_API_KEY를 다음 순서로 탐색:
    1. 환경변수 OPENROUTER_API_KEY
    2. config/secrets.yaml OPENROUTER_API_KEY
    """
    # 1. 환경변수 우선
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key

    # 2. secrets.yaml fallback
    secrets_path = ROOT / "config" / "secrets.yaml"
    if secrets_path.exists():
        try:
            import yaml
            data = yaml.safe_load(secrets_path.read_text(encoding="utf-8")) or {}
            key = (data.get("OPENROUTER_API_KEY") or "").strip()
            if key:
                return key
        except Exception:
            pass

    return ""


def _load_model(cli_model: str | None) -> str:
    """모델명을 CLI arg → env → secrets.yaml → 기본값 순으로 결정."""
    if cli_model:
        return cli_model.strip()
    env_model = os.environ.get("OPENROUTER_MODEL", "").strip()
    if env_model:
        return env_model
    secrets_path = ROOT / "config" / "secrets.yaml"
    if secrets_path.exists():
        try:
            import yaml
            data = yaml.safe_load(secrets_path.read_text(encoding="utf-8")) or {}
            m = (data.get("OPENROUTER_MODEL") or "").strip()
            if m:
                return m
        except Exception:
            pass
    return DEFAULT_MODEL


# ── 파일 컨텍스트 ─────────────────────────────────────────────────────────────
_READ_LIMIT = 40_000   # 문자 단위 컨텍스트 상한


def _read_file_safe(rel_or_abs: str) -> str:
    """CalcMate 프로젝트 내 파일을 안전하게 읽는다 (ROOT escape 금지)."""
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = (ROOT / rel_or_abs).resolve()
    else:
        p = p.resolve()

    if ROOT not in p.parents and p != ROOT:
        raise ValueError(f"프로젝트 외부 파일 접근 금지: {rel_or_abs}")
    if not p.exists():
        raise FileNotFoundError(f"파일 없음: {p}")
    if p.is_dir():
        raise IsADirectoryError(f"디렉터리는 직접 읽을 수 없음: {p}")

    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > _READ_LIMIT:
        text = text[:_READ_LIMIT] + f"\n\n... (이하 {len(text)-_READ_LIMIT}자 생략)"
    return text


def _build_context(files: list[str]) -> str:
    if not files:
        return ""
    parts = []
    for f in files:
        try:
            content = _read_file_safe(f)
            rel = str(Path(f))
            parts.append(f"[파일: {rel}]\n```\n{content}\n```")
        except (ValueError, FileNotFoundError, IsADirectoryError) as e:
            parts.append(f"[파일 로드 실패: {f}] {e}")
    return "\n\n".join(parts)


# ── 로깅 ──────────────────────────────────────────────────────────────────────
def _log(entry: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 핵심: OpenRouter 호출 ─────────────────────────────────────────────────────
def ask(question: str, context: str, model: str, api_key: str) -> tuple[str, int]:
    """OpenRouterProvider를 직접 호출하여 (응답, 토큰) 반환."""
    from modules.ai_provider import OpenRouterProvider
    provider = OpenRouterProvider(api_key)

    user_msg = question
    if context:
        user_msg = f"[참고 코드]\n{context}\n\n[질문]\n{question}"

    return provider.chat(
        system=_SYSTEM,
        user=user_msg,
        model=model,
        max_tokens=4096,
    )


# ── 연결 테스트 ───────────────────────────────────────────────────────────────
def ping(api_key: str, model: str) -> bool:
    """OpenRouter API 연결 및 모델 가용성을 최소 토큰으로 확인."""
    print(f"[ping] 모델: {model}")
    print(f"[ping] 엔드포인트: https://openrouter.ai/api/v1")
    try:
        resp, tokens = ask("Ping. 한 문장으로만 응답하라.", "", model, api_key)
        print(f"[ping] 응답: {resp[:120]}")
        print(f"[ping] 토큰: {tokens}")
        _log({"ts": datetime.now().isoformat(), "type": "ping",
              "model": model, "tokens": tokens, "ok": True})
        print("[ping] OK")
        return True
    except Exception as e:
        print(f"[ping] FAIL — {e}")
        _log({"ts": datetime.now().isoformat(), "type": "ping",
              "model": model, "ok": False, "error": str(e)})
        return False


# ── 1회 질의 ──────────────────────────────────────────────────────────────────
def one_shot(question: str, files: list[str], model: str, api_key: str):
    context = _build_context(files)
    print(f"\n[모델] {model}")
    if files:
        print(f"[컨텍스트] {', '.join(files)}")
    print("─" * 60)
    try:
        resp, tokens = ask(question, context, model, api_key)
        print(resp)
        print(f"\n─ 토큰: {tokens} ─")
        _log({"ts": datetime.now().isoformat(), "type": "one_shot",
              "model": model, "files": files, "tokens": tokens,
              "question_len": len(question), "ok": True})
    except Exception as e:
        print(f"[오류] {e}")
        _log({"ts": datetime.now().isoformat(), "type": "one_shot",
              "model": model, "files": files, "ok": False, "error": str(e)})


# ── 대화형 모드 ───────────────────────────────────────────────────────────────
def interactive(files: list[str], model: str, api_key: str):
    context = _build_context(files)
    print("=" * 60)
    print("  CalcMate 보조 개발자 (OpenRouter)")
    print(f"  모델 : {model}")
    if files:
        print(f"  파일 : {', '.join(files)}")
    print("  종료 : q / exit / quit")
    print("  파일 추가 : :file <경로>")
    print("=" * 60)

    session_files = list(files)

    while True:
        try:
            line = input("\n질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not line:
            continue
        if line.lower() in ("q", "exit", "quit"):
            print("종료합니다.")
            break

        # 인라인 파일 추가 명령
        if line.startswith(":file "):
            new_file = line[6:].strip()
            try:
                _ = _read_file_safe(new_file)
                session_files.append(new_file)
                context = _build_context(session_files)
                print(f"[파일 추가] {new_file}")
            except Exception as e:
                print(f"[파일 오류] {e}")
            continue

        try:
            resp, tokens = ask(line, context, model, api_key)
            print(f"\n{resp}")
            print(f"\n─ 토큰: {tokens} ─")
            _log({"ts": datetime.now().isoformat(), "type": "interactive",
                  "model": model, "files": session_files, "tokens": tokens,
                  "question_len": len(line), "ok": True})
        except Exception as e:
            print(f"[오류] {e}")
            _log({"ts": datetime.now().isoformat(), "type": "interactive",
                  "model": model, "files": session_files, "ok": False, "error": str(e)})


# ── 진입점 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="CalcMate OpenRouter 보조 개발자",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ping",     action="store_true", help="API 연결 테스트")
    parser.add_argument("--file",     action="append", default=[], metavar="PATH",
                        help="컨텍스트로 포함할 CalcMate 파일 (반복 가능)")
    parser.add_argument("--question", "-q", default="", metavar="Q",
                        help="1회 질문 (생략 시 대화형 모드)")
    parser.add_argument("--model",    default="", metavar="MODEL",
                        help=f"OpenRouter 모델명 (기본: {DEFAULT_MODEL})")
    args = parser.parse_args()

    api_key = _load_api_key()
    model   = _load_model(args.model or None)

    if not api_key:
        print("[오류] OPENROUTER_API_KEY가 설정되지 않았습니다.")
        print("  방법 1: config/secrets.yaml에 OPENROUTER_API_KEY: 'sk-or-v1-...' 추가")
        print("  방법 2: 환경변수  set OPENROUTER_API_KEY=sk-or-v1-...")
        print("  키 발급: https://openrouter.ai/keys")
        sys.exit(1)

    if args.ping:
        ok = ping(api_key, model)
        sys.exit(0 if ok else 1)

    if args.question:
        one_shot(args.question, args.file, model, api_key)
    else:
        interactive(args.file, model, api_key)


if __name__ == "__main__":
    main()
