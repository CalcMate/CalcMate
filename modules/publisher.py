"""
publisher.py — STEP 11: WordPress REST API 발행

WordPress 미구축 상태에서도 오류 없이 '대기(skip)'로 동작한다.
키명은 WORDPRESS_APP_PASSWORD로 단일화(구 WORDPRESS_PASSWORD 하위호환).
"""
import requests
from datetime import datetime
from pathlib import Path

from .config_loader import is_wordpress_ready
from .logger import get_logger

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "outputs"
LOG = get_logger()


def _app_password(cfg: dict) -> str:
    return (cfg.get("WORDPRESS_APP_PASSWORD") or cfg.get("WORDPRESS_PASSWORD") or "")


def _wp_auth(cfg: dict) -> tuple:
    """WordPress REST 인증 튜플. 모든 WP REST 호출이 이 헬퍼를 공유."""
    return (cfg.get("WORDPRESS_USERNAME", ""), _app_password(cfg))


def publish(post_id: str, seo_data: dict, html_body: str,
            image_urls: dict, cfg: dict) -> dict:
    """반환: {"wordpress": url, "status": "published"|"skipped_no_wp"}"""
    if not is_wordpress_ready(cfg):
        LOG.info("WordPress 미구성 — 발행 건너뜀(대기). 로컬 미리보기만 저장합니다.")
        preview = _save_preview(seo_data, html_body, link="(WordPress 미구성 — 미발행)")
        return {"wordpress": "", "status": "skipped_no_wp", "preview": str(preview)}

    res = _wordpress_api(seo_data, html_body, image_urls, cfg)
    res["status"] = "published"
    return res


def update_post(cfg, wp_post_id, title=None, content=None, excerpt=None) -> dict:
    """POST /wp-json/wp/v2/posts/{wp_post_id} — 기존 글 수정.

    None인 필드는 요청에서 아예 제외(미전송) → 해당 필드 수정 안 함.
    빈 문자열("")로 넘어온 필드는 그대로 전송 → 해당 필드를 비우는 의도로 처리한다.
    즉 None(미전송)과 ""(명시적 삭제/비움)를 구분한다.

    WordPress REST API 직접 호출은 이 함수와 _wordpress_api 에만 존재한다
    (dashboard 등 다른 계층은 publisher.update_post 만 호출).

    성공: {"success": True, "wp_post_id", "link", "modified", "status"}
    실패: {"success": False, "error": "..."}

    TODO(동시 수정 감지): 저장 직전 GET /posts/{id}로 현재 modified를 조회하여,
    편집 시작 시점의 modified와 다르면 "다른 곳에서 이미 수정됨" 경고 후 저장 중단
    (낙관적 잠금). 이번 범위 제외.
    """
    if not is_wordpress_ready(cfg):
        return {"success": False, "error": "WordPress 미구성 — 수정할 수 없습니다."}
    if not str(wp_post_id or "").strip():
        return {"success": False, "error": "wp_post_id가 없어 수정할 수 없습니다."}

    # None은 미전송(수정 안 함), ""는 전송(비움) — 구분해서 payload 구성
    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    if excerpt is not None:
        payload["excerpt"] = excerpt
    if not payload:
        return {"success": False, "error": "수정할 필드가 없습니다(title/content/excerpt 모두 None)."}

    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + f"/wp-json/wp/v2/posts/{wp_post_id}"
    try:
        resp = requests.post(
            url, json=payload,
            auth=_wp_auth(cfg),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "success": True,
            "wp_post_id": data.get("id", wp_post_id),
            "link": data.get("link", ""),
            "modified": data.get("modified", ""),
            "status": data.get("status", ""),
        }
    except Exception as e:
        LOG.warning("WordPress 글 수정 실패(post_id=%s): %s", wp_post_id, e)
        return {"success": False, "error": str(e)}


def _wp_error(resp) -> str:
    """WP REST 실패 응답 → 에러코드 문자열(운영 원인 파악용)."""
    code = resp.status_code
    if code == 401:
        return "authentication_failed"
    if code == 403:
        return "permission_denied"
    if code == 404:
        return "not_found"
    try:
        txt = resp.text
    except Exception:
        txt = ""
    return f"HTTP {code}: {txt[:200]}"


def get_post(cfg, wp_post_id) -> dict:
    """GET /wp-json/wp/v2/posts/{id} (context=edit). 삭제/수정 전 재조회용.

    성공: {"success": True, "wp_post_id", "status", "title", "link", "modified"}
    실패: {"success": False, "error", "wp_post_id"}
          (error: authentication_failed / permission_denied / not_found / "HTTP {code}: ...")
    """
    if not is_wordpress_ready(cfg):
        return {"success": False, "error": "WordPress 미구성", "wp_post_id": wp_post_id}
    if not str(wp_post_id or "").strip():
        return {"success": False, "error": "wp_post_id가 없습니다.", "wp_post_id": wp_post_id}
    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + f"/wp-json/wp/v2/posts/{wp_post_id}"
    try:
        resp = requests.get(url, params={"context": "edit"}, auth=_wp_auth(cfg), timeout=30)
        if resp.status_code != 200:
            return {"success": False, "error": _wp_error(resp), "wp_post_id": wp_post_id}
        data = resp.json()
        t = data.get("title", {})
        title = (t.get("raw") or t.get("rendered", "")) if isinstance(t, dict) else str(t)
        return {"success": True, "wp_post_id": data.get("id", wp_post_id),
                "status": data.get("status", ""), "title": title,
                "link": data.get("link", ""), "modified": data.get("modified", "")}
    except Exception as e:
        LOG.warning("WordPress 글 조회 실패(post_id=%s): %s", wp_post_id, e)
        return {"success": False, "error": str(e), "wp_post_id": wp_post_id}


def delete_post(cfg, wp_post_id, force=False) -> dict:
    """DELETE /wp-json/wp/v2/posts/{id}. force=False→휴지통(trash), force=True→영구삭제(deleted).

    성공 판정은 HTTP 코드만으로 하지 않는다: status_code in (200, 410)이어도 응답 JSON이
    기대 상태와 다르면 실패 처리한다.
      - force=False 성공: 응답 status == "trash"
      - force=True  성공: 응답 deleted is True  (WP 표준: {"deleted": true, "previous": {...}} —
        status:"deleted" 필드가 아니라 deleted 플래그로 판정)
    force=True는 함수만 제공하고 대시보드 UI에는 노출하지 않는다(4차 복원 대상 제외).

    성공: {"success": True, "wp_post_id", "wp_status", "force"}
    실패: {"success": False, "error"}
    """
    if not is_wordpress_ready(cfg):
        return {"success": False, "error": "WordPress 미구성 — 삭제할 수 없습니다."}
    if not str(wp_post_id or "").strip():
        return {"success": False, "error": "wp_post_id가 없어 삭제할 수 없습니다."}
    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + f"/wp-json/wp/v2/posts/{wp_post_id}"
    try:
        resp = requests.delete(url, params={"force": "true" if force else "false"},
                               auth=_wp_auth(cfg), timeout=30)
        if resp.status_code not in (200, 410):
            return {"success": False, "error": _wp_error(resp)}
        data = resp.json()
        if force:
            if data.get("deleted") is True:
                return {"success": True, "wp_post_id": wp_post_id, "wp_status": "deleted", "force": True}
            return {"success": False,
                    "error": f"unexpected_status: expected=deleted actual={data.get('deleted')!r}"}
        actual = data.get("status", "")
        if actual == "trash":
            return {"success": True, "wp_post_id": wp_post_id, "wp_status": "trash", "force": False}
        return {"success": False, "error": f"unexpected_status: expected=trash actual={actual!r}"}
    except Exception as e:
        LOG.warning("WordPress 글 삭제 실패(post_id=%s, force=%s): %s", wp_post_id, force, e)
        return {"success": False, "error": str(e)}


def _wordpress_api(seo, html, imgs, cfg) -> dict:
    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + "/wp-json/wp/v2/posts"
    imgs = imgs or {}
    thumb = imgs.get("thumbnail_url", "")
    body_img = imgs.get("body_image_url", "")
    # 이미지 생성 실패("실패"/빈값) 시 해당 <img>는 생략
    head_html = (f"<p style='text-align:center;'><img src='{thumb}' "
                 f"alt='{seo.get('alt_thumbnail','')}'/></p><br/>"
                 if thumb and thumb != "실패" else "")
    tail_html = (f"<br/><p style='text-align:center;'><img src='{body_img}' "
                 f"alt='{seo.get('alt_body_image','')}'/></p>"
                 if body_img and body_img != "실패" else "")
    full_content = f"{head_html}{html}{tail_html}"

    payload = {
        "title": seo.get("seo_title", ""),
        "status": "publish",
        "excerpt": seo.get("meta_description", ""),
        "content": full_content,
    }
    resp = requests.post(
        url, json=payload,
        auth=_wp_auth(cfg),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    link = data.get("link", "")
    _save_preview(seo, html, link=link)
    return {
        "wordpress": link,                                  # 하위호환 유지(기존 키)
        "wp_post_id": data.get("id", ""),                   # WordPress 숫자 글 ID
        "wp_permalink": data.get("link", ""),               # 영구링크(명확한 이름)
        "wp_status": data.get("status", ""),                # publish/draft 등
        "published_at": data.get("date") or datetime.now().isoformat(),
    }


def _save_preview(seo, html, link: str) -> Path:
    """발행 미리보기 텍스트 저장 (발행 성공/미구성 공통)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    preview = OUTPUT_DIR / f"{ts}_{seo.get('seo_title','post')[:30]}_발행미리보기.txt"
    preview.write_text(
        f"제목: {seo.get('seo_title','')}\n"
        f"메타설명: {seo.get('meta_description','')}\n"
        f"태그: {seo.get('tags_list','')}\n"
        f"본문 글자수(공백포함): {len(html)}\n"
        f"발행 URL: {link}\n",
        encoding="utf-8"
    )
    return preview
