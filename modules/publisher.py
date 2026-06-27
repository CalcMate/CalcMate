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


def publish(post_id: str, seo_data: dict, html_body: str,
            image_urls: dict, cfg: dict) -> dict:
    """반환: {"wordpress": url, "status": "published"|"skipped_no_wp"}"""
    if not is_wordpress_ready(cfg):
        LOG.info("WordPress 미구성 — 발행 건너뜀(대기). 로컬 미리보기만 저장합니다.")
        preview = _save_preview(seo_data, html_body, link="(WordPress 미구성 — 미발행)")
        return {"wordpress": "", "status": "skipped_no_wp", "preview": str(preview)}

    url = _wordpress_api(seo_data, html_body, image_urls, cfg)
    return {"wordpress": url, "status": "published"}


def _wordpress_api(seo, html, imgs, cfg) -> str:
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
        auth=(cfg["WORDPRESS_USERNAME"], _app_password(cfg)),
        timeout=30,
    )
    resp.raise_for_status()
    link = resp.json().get("link", "")
    _save_preview(seo, html, link=link)
    return link


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
