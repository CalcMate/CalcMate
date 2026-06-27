"""
health_check.py — PART 5-F: 헬스체크 모듈 (v11.6 기준)
v11.7: Service Account 전용 검증 추가 (기존 함수 100% 보존)
"""
import json, time
from pathlib import Path
from datetime import datetime

RESULT_PATH = Path(__file__).parent / "data" / "logs" / "health_last.json"


def run(cfg: dict) -> dict:
    results = {}
    # CRITICAL 항목 (기존 유지)
    results["openai"]       = _check_openai(cfg)
    results["claude"]       = _check_claude(cfg)
    results["gemini"]       = _check_gemini(cfg)
    results["google_sheet"] = _check_sheet(cfg)
    results["google_drive"] = _check_drive(cfg)
    # ★ v11.7 추가: Service Account 파일 존재 및 유효성 검증
    results["service_account"] = _check_service_account(cfg)
    # WARNING 항목
    results["wordpress"] = _check_wordpress(cfg)
    results["timestamp"] = datetime.now().isoformat()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def _check_openai(cfg) -> dict:
    try:
        from openai import OpenAI
        c = OpenAI(api_key=cfg["OPENAI_API_KEY"])
        c.models.list()
        return {"status": "OK", "level": "CRITICAL"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def _check_claude(cfg) -> dict:
    try:
        import anthropic
        c = anthropic.Anthropic(api_key=cfg["CLAUDE_API_KEY"])
        c.models.list()
        return {"status": "OK", "level": "CRITICAL"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def _check_gemini(cfg) -> dict:
    try:
        from google import genai
        client = genai.Client(api_key=cfg["GEMINI_API_KEY"])
        # 모델 목록 1건 조회로 연결/인증 확인
        next(iter(client.models.list()), None)
        return {"status": "OK", "level": "CRITICAL"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def _check_sheet(cfg) -> dict:
    try:
        from modules.sheet_sync import read_test
        ok = read_test(cfg)
        return {"status": "OK" if ok else "FAIL", "level": "CRITICAL"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def _check_drive(cfg) -> dict:
    try:
        from googleapiclient.discovery import build as gbuild
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            cfg["GOOGLE_SERVICE_ACCOUNT_FILE"],
            scopes=["https://www.googleapis.com/auth/drive.readonly"])
        svc = gbuild("drive", "v3", credentials=creds)
        svc.files().list(pageSize=1).execute()
        return {"status": "OK", "level": "CRITICAL"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def _check_wordpress(cfg) -> dict:
    try:
        import requests
        url = cfg.get("WORDPRESS_URL", "").rstrip("/") + "/wp-json/wp/v2/posts?per_page=1"
        r = requests.get(url, timeout=5)
        return {"status": "OK" if r.status_code == 200 else "FAIL", "level": "WARNING"}
    except Exception as e:
        return {"status": "FAIL", "level": "WARNING", "error": str(e)}


# ★ v11.7 신규: Service Account JSON 파일 자체 유효성 검증
def _check_service_account(cfg) -> dict:
    """
    credentials.json 파일 존재 여부 + 필수 필드 보유 여부 확인.
    Google API 실제 호출 없이 파일 레벨에서 검증.
    """
    try:
        import json as _json
        cred_file = cfg.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
        cred_path = Path(__file__).parent / cred_file
        if not cred_path.exists():
            return {"status": "FAIL", "level": "CRITICAL",
                    "error": f"{cred_file} 파일이 없습니다. 마법사에서 업로드하세요."}
        with open(cred_path, encoding="utf-8") as f:
            data = _json.load(f)
        required = ["type", "project_id", "private_key", "client_email"]
        missing = [k for k in required if k not in data]
        if missing:
            return {"status": "FAIL", "level": "CRITICAL",
                    "error": f"credentials.json 필수 필드 누락: {missing}"}
        if data.get("type") != "service_account":
            return {"status": "FAIL", "level": "CRITICAL",
                    "error": "credentials.json type이 service_account가 아닙니다."}
        return {"status": "OK", "level": "CRITICAL",
                "info": f"project_id={data.get('project_id')}, client_email={data.get('client_email')}"}
    except Exception as e:
        return {"status": "FAIL", "level": "CRITICAL", "error": str(e)}


def critical_passed(results: dict) -> bool:
    for k, v in results.items():
        if isinstance(v, dict) and v.get("level") == "CRITICAL" and v.get("status") != "OK":
            return False
    return True
