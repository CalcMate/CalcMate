# -*- coding: utf-8 -*-
"""
image_pipeline/wordpress_connector.py — P4: Image Pipeline → WordPress Media → Gutenberg → Draft

QA PASS 이미지(Master/Body/Thumbnail) 중 Body(800x450)/Thumb(512x512)만
WordPress Media로 업로드하고, wp:image Gutenberg 블록 + featured_media를 포함한
Draft(초안)만 생성한다. Publish/상태 변경 경로는 사용하지 않는다.

재사용 (기존 검증 구현):
  - WP REST 인증  : modules.publisher._wp_auth / is_wordpress_ready (전사 단일 인증 규약)
  - Media 업로드   : modules.publisher.upload_media와 동일 endpoint/Content-Disposition/
                    Content-Type/auth 규약. 단 HTTP 201 + media_id + source_url을
                    명시적으로 검증하기 위해 상태코드를 반환하는 thin wrapper를 둔다.
  - Gutenberg 블록 : modules.publisher._wordpress_api의 wp:image 블록 형식 재사용.
  - Draft 생성     : content_pipeline.wordpress_publisher.WordPressPublisher.create_draft와
                    동일 endpoint/payload(status="draft", featured_media) 규약.
                    P4 검증 요구(post_id/status/permalink/featured_media/content)를 위해
                    201 응답 전체를 반환한다.

흐름:
    ImageJobResult.files (master/body/thumb)
        ↓ Body(800x450) Media upload → HTTP 201
        ↓ Thumb(512x512) Media upload → HTTP 201
        ↓ wp:image Gutenberg 블록 생성 (body source_url + media_id)
        ↓ POST /wp-json/wp/v2/posts {status:"draft", featured_media:thumb_id}
        ↓ WordpressDraftResult

실패 정책 (Rollback 없음 — 기존 프로젝트는 업로드된 Media를 자동 삭제하지 않음):
  - Media 업로드 실패        → Draft 생성하지 않음
  - Body 성공 / Thumb 실패   → Draft 생성하지 않음
  - Gutenberg 생성 실패      → Draft 생성하지 않음
  - Draft 생성 실패          → 성공으로 기록하지 않음
"""
from __future__ import annotations

import json
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
from PIL import Image

from modules.publisher import _wp_auth, is_wordpress_ready

# Draft 이외의 상태를 허용하지 않는다 (P4 원칙: publish/future/private 절대 금지).
DRAFT_STATUS = "draft"
FORBIDDEN_STATUSES = ("publish", "future", "private", "pending")


@dataclass
class MediaUploadResult:
    """이미지 1건의 WordPress Media 업로드 결과."""

    kind: str                      # "body" | "thumb"
    path: str
    success: bool
    media_id: int | None = None
    source_url: str = ""
    status_code: int | None = None
    error: str | None = None


@dataclass
class WordpressDraftResult:
    """Body/Thumb 업로드 + Gutenberg + Draft 생성 전체 결과."""

    success: bool
    body_media_id: int | None = None
    thumb_media_id: int | None = None
    post_id: int | None = None
    status: str = ""
    permalink: str = ""
    featured_media: int | None = None
    content: str = ""
    media_results: list[MediaUploadResult] = field(default_factory=list)
    error: str | None = None


# ── 이미지 무결성 / MIME ───────────────────────────────────────────

def check_image_file(path: str | Path) -> tuple[bool, str, str]:
    """파일 존재 → Pillow 로드 → MIME 판별 (기존 upload_media 컨벤션).

    반환: (ok, error_msg, mime_type)
    """
    p = Path(path)
    if not p.exists():
        return False, f"파일 없음: {p}", ""
    if p.stat().st_size <= 0:
        return False, f"빈 파일: {p}", ""
    try:
        with Image.open(p) as im:
            im.load()
            w, h = im.size
    except Exception as e:  # noqa: BLE001 — 손상/비이미지 파일
        return False, f"이미지 무결성 실패: {e}", ""
    if w <= 0 or h <= 0:
        return False, f"유효하지 않은 크기 ({w}x{h})", ""
    mime_type, _ = mimetypes.guess_type(str(p))
    if not mime_type:
        mime_type = "image/webp"  # modules.publisher.upload_media와 동일한 폴백
    return True, "", mime_type


# ── Media 업로드 ───────────────────────────────────────────────────

def _post_media(path: Path, cfg: dict, auth: tuple | None = None):
    """POST /wp-json/wp/v2/media — modules.publisher.upload_media와 동일 규약.

    auth=None이면 modules.publisher._wp_auth(cfg) (전사 단일 인증).
    """
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = "image/webp"
    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + "/wp-json/wp/v2/media"
    headers = {
        "Content-Disposition": f"attachment; filename={path.name}",
        "Content-Type": mime_type,
    }
    with open(path, "rb") as f:
        return requests.post(
            url, data=f, headers=headers,
            auth=auth if auth is not None else _wp_auth(cfg),
            timeout=60,
        )


def upload_media_checked(kind: str, path: str | Path, cfg: dict,
                         auth: tuple | None = None) -> MediaUploadResult:
    """이미지 1건: 무결성 확인 → MIME 확인 → 업로드 → HTTP 201 확인.

    실패 시 success=False (성공으로 기록하지 않는다).
    """
    p = Path(path)
    ok, err, _mime = check_image_file(p)
    if not ok:
        return MediaUploadResult(kind=kind, path=str(p), success=False, error=err)
    try:
        resp = _post_media(p, cfg, auth=auth)
    except requests.RequestException as e:
        return MediaUploadResult(kind=kind, path=str(p), success=False,
                                 status_code=None, error=f"요청 실패: {e}")
    if resp.status_code != 201:
        return MediaUploadResult(kind=kind, path=str(p), success=False,
                                 status_code=resp.status_code,
                                 error=f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        return MediaUploadResult(kind=kind, path=str(p), success=False,
                                 status_code=resp.status_code,
                                 error="201 응답이 JSON이 아님")
    media_id = data.get("id")
    source_url = data.get("source_url", "")
    if not media_id or not source_url:
        return MediaUploadResult(kind=kind, path=str(p), success=False,
                                 status_code=resp.status_code,
                                 error=f"media_id/source_url 누락: {data}")
    return MediaUploadResult(kind=kind, path=str(p), success=True,
                             media_id=int(media_id), source_url=source_url,
                             status_code=resp.status_code)


# ── Gutenberg wp:image 블록 ────────────────────────────────────────

def build_gutenberg_image_block(src: str, alt: str, media_id: int | None) -> str:
    """wp:image Gutenberg 블록 (modules.publisher._wordpress_api 형식 재사용).

    예:
    <!-- wp:image {"id": 123} -->
    <figure class="wp-block-image"><img src="..." alt="..."/></figure>
    <!-- /wp:image -->
    """
    block_json = json.dumps({"id": int(media_id) if media_id else 0})
    return (
        f"<!-- wp:image {block_json} -->\n"
        f'<figure class="wp-block-image"><img src="{src}" alt="{alt}"/></figure>\n'
        f"<!-- /wp:image -->"
    )


def _merge_image_block(body_html: str, block: str) -> str:
    """기존 본문에 wp:image 블록을 삽입 (첫 </h2> 뒤, 없으면 맨 앞)."""
    if not body_html:
        return block
    m = re.search(r"</h2>", body_html)
    if m:
        pos = m.end()
        return body_html[:pos] + "\n\n" + block + "\n\n" + body_html[pos:]
    return block + "\n\n" + body_html


# ── Draft 생성 (status="draft" 강제) ───────────────────────────────

def create_draft(cfg: dict, title: str, content: str, excerpt: str = "",
                 featured_media: int | None = None,
                 auth: tuple | None = None) -> dict:
    """POST /wp-json/wp/v2/posts — Draft(초안)만 생성.

    content_pipeline.wordpress_publisher.create_draft와 동일 endpoint/payload 규약.
    상태는 DRAFT_STATUS로 고정 — publish/future/private 전달 불가.
    성공(201): id/status/link/featured_media/content 포함 dict 반환.
    실패: {"success": False, "error": ...} — 성공으로 기록하지 않는다.
    """
    if not is_wordpress_ready(cfg):
        return {"success": False, "error": "WordPress 미구성 (is_wordpress_ready=False)"}
    if not title or not content:
        return {"success": False, "error": "title/content 누락 — Draft 생성 불가"}

    payload = {
        "title": title,
        "status": DRAFT_STATUS,
        "content": content,
        "excerpt": excerpt,
    }
    if featured_media:
        payload["featured_media"] = int(featured_media)

    url = cfg.get("WORDPRESS_URL", "").rstrip("/") + "/wp-json/wp/v2/posts"
    try:
        resp = requests.post(
            url, json=payload,
            auth=auth if auth is not None else _wp_auth(cfg),
            timeout=30,
        )
    except requests.RequestException as e:
        return {"success": False, "error": f"Draft 요청 실패: {e}"}
    if resp.status_code != 201:
        return {"success": False, "error": f"Draft HTTP {resp.status_code}", "status_code": resp.status_code}
    data = resp.json()
    data["success"] = True
    return data


# ── 전체 연결 (files → Media → Gutenberg → Draft) ──────────────────

def connect_image_to_draft(cfg: dict, files: dict, title: str, alt: str = "",
                           excerpt: str = "", auth: tuple | None = None,
                           body_html: str = "") -> WordpressDraftResult:
    """ImageJobResult.files(master/body/thumb) → WordPress Draft 연결.

    - Master는 업로드 대상에서 제외 (본문=Body 800x450, 대표=Thumb 512x512).
    - Body → Thumb 순서로 업로드하며, 하나라도 실패하면 Draft를 생성하지 않는다.
    - 성공: featured_media = thumb media_id, content에 wp:image 블록 포함.
    """
    body_path = files.get("body")
    thumb_path = files.get("thumb")
    if not body_path or not thumb_path:
        return WordpressDraftResult(success=False,
                                    error=f"body/thumb 경로 필요: {sorted(files)}")

    result = WordpressDraftResult(success=False)
    media_results: list[MediaUploadResult] = []

    # 1) Body (800x450) → Media
    body_res = upload_media_checked("body", body_path, cfg, auth=auth)
    media_results.append(body_res)
    if not body_res.success:
        result.media_results = media_results
        result.error = f"Body Media 업로드 실패: {body_res.error}"
        return result

    # 2) Thumb (512x512) → Media
    thumb_res = upload_media_checked("thumb", thumb_path, cfg, auth=auth)
    media_results.append(thumb_res)
    if not thumb_res.success:
        result.media_results = media_results
        result.body_media_id = body_res.media_id
        result.error = f"Thumbnail Media 업로드 실패: {thumb_res.error}"
        return result

    result.media_results = media_results
    result.body_media_id = body_res.media_id
    result.thumb_media_id = thumb_res.media_id

    # 3) Gutenberg wp:image 블록 (본문 = Body source URL)
    block_alt = alt or title
    block = build_gutenberg_image_block(body_res.source_url, block_alt, body_res.media_id)
    content = _merge_image_block(body_html, block)
    result.content = content

    # 4) Draft (status="draft" 강제)
    draft = create_draft(cfg, title=title, content=content, excerpt=excerpt,
                         featured_media=thumb_res.media_id, auth=auth)
    if not draft.get("success"):
        result.error = draft.get("error", "Draft 생성 실패")
        return result

    result.success = True
    result.post_id = draft.get("id")
    result.status = draft.get("status", "")
    result.permalink = draft.get("link", "")
    result.featured_media = draft.get("featured_media")
    return result
