# -*- coding: utf-8 -*-
"""
modules/github_deployer.py — 계산기 GitHub Pages 자동 배포 (SalaryMate 확장, 신규)

생성된 계산기 정적 파일(index.html/style.css/script.js)을 GitHub 저장소에
업로드하고 GitHub Pages를 활성화하여 공개 URL을 반환한다.

환경설정(우선순위: cfg → 환경변수):
  GITHUB_TOKEN  : PAT (repo 권한)
  GITHUB_REPO   : 대상 저장소명(없으면 create_repo로 생성)

토큰 미설정 시 모든 함수는 (False, 안내메시지)로 graceful 처리(크래시 없음).
"""
import base64
import os

import requests

from .logger import get_logger

LOG = get_logger()
_API = "https://api.github.com"


def _token(cfg: dict) -> str:
    return (cfg.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()


def is_configured(cfg: dict) -> bool:
    return bool(_token(cfg))


def _headers(cfg: dict) -> dict:
    return {"Authorization": f"Bearer {_token(cfg)}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _owner(cfg: dict) -> str:
    r = requests.get(f"{_API}/user", headers=_headers(cfg), timeout=15)
    r.raise_for_status()
    return r.json()["login"]


def create_repo(cfg: dict, name: str, private: bool = False) -> tuple:
    """저장소 생성(이미 있으면 재사용). 반환: (ok, repo_full_name 또는 메시지)."""
    if not is_configured(cfg):
        return False, "GITHUB_TOKEN 미설정 — 배포 건너뜀"
    try:
        owner = _owner(cfg)
        # 존재 확인
        chk = requests.get(f"{_API}/repos/{owner}/{name}", headers=_headers(cfg), timeout=15)
        if chk.status_code == 200:
            return True, f"{owner}/{name}"
        r = requests.post(f"{_API}/user/repos", headers=_headers(cfg),
                          json={"name": name, "private": private, "auto_init": True}, timeout=20)
        r.raise_for_status()
        LOG.info("GitHub repo 생성: %s", r.json().get("full_name"))
        return True, r.json()["full_name"]
    except Exception as e:
        LOG.error("create_repo 실패: %s", e)
        return False, f"repo 생성 실패: {e}"


def _put_file(cfg: dict, full_name: str, path: str, content: str, branch: str = "main") -> bool:
    url = f"{_API}/repos/{full_name}/contents/{path}"
    headers = _headers(cfg)
    # 기존 파일 sha 확인(업데이트용)
    sha = None
    g = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
    if g.status_code == 200:
        sha = g.json().get("sha")
    body = {"message": f"deploy {path}",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=headers, json=body, timeout=20)
    r.raise_for_status()
    return True


def _enable_pages(cfg: dict, full_name: str, branch: str = "main", path: str = "/") -> None:
    url = f"{_API}/repos/{full_name}/pages"
    headers = _headers(cfg)
    try:
        requests.post(url, headers=headers,
                      json={"source": {"branch": branch, "path": path}}, timeout=20)
    except Exception as e:
        LOG.warning("Pages 활성화 경고(이미 켜졌을 수 있음): %s", e)


def deploy_app(cfg: dict, files: dict, repo: str = None, subdir: str = "") -> tuple:
    """files={'index.html':..,'style.css':..,'script.js':..} 업로드 + Pages 활성화.
    반환: (ok, deploy_url 또는 메시지)."""
    if not is_configured(cfg):
        return False, "GITHUB_TOKEN 미설정 — 배포 건너뜀(로컬 미리보기만 가능)"
    repo = repo or cfg.get("GITHUB_REPO") or "salarymate-calculators"
    ok, full = create_repo(cfg, repo)
    if not ok:
        return False, full
    try:
        prefix = (subdir.strip("/") + "/") if subdir else ""
        for fname, content in files.items():
            if fname.startswith("_"):
                continue
            _put_file(cfg, full, f"{prefix}{fname}", content)
        _enable_pages(cfg, full)
        return True, get_deploy_url(cfg, full, subdir)
    except Exception as e:
        LOG.error("deploy_app 실패: %s", e)
        return False, f"배포 실패: {e}"


def get_deploy_url(cfg: dict, full_name: str, subdir: str = "") -> str:
    """https://{owner}.github.io/{repo}/{subdir}/"""
    try:
        owner, repo = full_name.split("/", 1)
    except ValueError:
        owner, repo = "", full_name
    base = f"https://{owner}.github.io/{repo}/"
    return base + (subdir.strip("/") + "/" if subdir else "")
