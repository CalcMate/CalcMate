# -*- coding: utf-8 -*-
"""tests/test_image_pipeline_p4.py — P4 검증

image_pipeline 결과(Master/Body/Thumb) → WordPress Media 업로드 → Gutenberg wp:image
→ Draft 생성. 실제 WordPress HTTP 호출은 하지 않는다 (requests.post mock).
모든 산출물은 tmp_path에만 기록 — data/phase5-followup/calc_v1 참조 산출물 보호.
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from image_pipeline import wordpress_connector as wc  # noqa: E402
from image_pipeline.wordpress_connector import (  # noqa: E402
    MediaUploadResult,
    WordpressDraftResult,
    build_gutenberg_image_block,
    check_image_file,
    connect_image_to_draft,
    create_draft,
    upload_media_checked,
)

# 테스트용 WP 설정 (실제 secret 미사용)
CFG = {
    "WORDPRESS_URL": "http://wp.test",
    "WORDPRESS_USERNAME": "tester",
    "WORDPRESS_APP_PASSWORD": "app-pw",
}

MEDIA_URL = "http://wp.test/wp-json/wp/v2/media"
POSTS_URL = "http://wp.test/wp-json/wp/v2/posts"


def _make_webp(path: Path, size: tuple[int, int]) -> Path:
    img = Image.new("RGB", size, (30, 120, 200))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="WEBP", quality=90)
    return path


@pytest.fixture
def image_files(tmp_path):
    return {
        "master": str(_make_webp(tmp_path / "key_master.png", (1920, 1080))),
        "body": str(_make_webp(tmp_path / "key_body.webp", (800, 450))),
        "thumb": str(_make_webp(tmp_path / "key_thumb.webp", (512, 512))),
    }


class _FakeResp:
    def __init__(self, status_code: int, data: dict | None = None,
                 bad_json: bool = False):
        self.status_code = status_code
        self._data = data
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("bad json")
        return self._data


def _mock_posts(monkeypatch, media_responses: list[int],
                post_response: int | None = None, post_data: dict | None = None):
    """requests.post mock. media_responses는 media 호출 순서대로 상태코드 목록.

    반환 recorder: {"media_payloads": [...], "post_payloads": [...], "urls": [...]}
    """
    state = {"i": 0, "media_payloads": [], "post_payloads": [], "urls": [],
             "media_responses": media_responses, "post_response": post_response,
             "post_data": post_data}

    def fake_post(url, data=None, json=None, headers=None, auth=None, timeout=30):
        state["urls"].append(url)
        if url == MEDIA_URL:
            i = state["i"]
            assert i < len(media_responses), f"예상치 못한 media 호출: {url}"
            code = media_responses[i]
            state["i"] += 1
            state["media_payloads"].append({
                "filename": headers.get("Content-Disposition"),
                "content_type": headers.get("Content-Type"),
                "auth": auth,
            })
            if code != 201:
                return _FakeResp(code)
            return _FakeResp(201, {
                "id": 100 + i, "source_url": f"http://wp.test/wp-content/uploads/2026/08/img{i}.webp",
            })
        if url == POSTS_URL:
            assert post_response is not None, "예상치 못한 posts 호출"
            state["post_payloads"].append(json)
            if post_response != 201:
                return _FakeResp(post_response)
            data = post_data or {
                "id": 500, "status": "draft",
                "link": "http://wp.test/?p=500",
                "featured_media": json.get("featured_media"),
                "content": {"rendered": json.get("content", "")},
            }
            return _FakeResp(201, data)
        raise AssertionError(f"예상치 못한 URL: {url}")

    monkeypatch.setattr("image_pipeline.wordpress_connector.requests.post", fake_post)
    return state


# ── Test 1: Body media upload success ──────────────────────────────

def test_body_media_upload_success(tmp_path, monkeypatch):
    body = _make_webp(tmp_path / "k_body.webp", (800, 450))
    state = _mock_posts(monkeypatch, media_responses=[201])
    res = upload_media_checked("body", body, CFG)
    assert res.success is True
    assert res.kind == "body"
    assert res.status_code == 201
    assert res.media_id == 100
    assert res.source_url == "http://wp.test/wp-content/uploads/2026/08/img0.webp"
    assert state["i"] == 1
    # Content-Disposition / Content-Type 확인 (기존 upload_media 규약)
    assert "k_body.webp" in state["media_payloads"][0]["filename"]
    assert state["media_payloads"][0]["content_type"] == "image/webp"


# ── Test 2: Thumbnail media upload success ─────────────────────────

def test_thumb_media_upload_success(tmp_path, monkeypatch):
    thumb = _make_webp(tmp_path / "k_thumb.webp", (512, 512))
    state = _mock_posts(monkeypatch, media_responses=[201])
    res = upload_media_checked("thumb", thumb, CFG)
    assert res.success is True
    assert res.kind == "thumb"
    assert res.status_code == 201
    assert res.media_id == 100
    assert state["i"] == 1


# ── Test 3: Media HTTP failure (400/401/500) ───────────────────────

@pytest.mark.parametrize("code", [400, 401, 500])
def test_media_http_failure(tmp_path, monkeypatch, code):
    body = _make_webp(tmp_path / "k_body.webp", (800, 450))
    state = _mock_posts(monkeypatch, media_responses=[code])
    res = upload_media_checked("body", body, CFG)
    assert res.success is False
    assert res.status_code == code
    assert res.media_id is None
    assert f"HTTP {code}" in (res.error or "")


# ── Test 4: Invalid image failure (HTTP 호출 전 차단) ───────────────

def test_invalid_image_failure(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.webp"
    bad.write_bytes(b"not-an-image")
    state = _mock_posts(monkeypatch, media_responses=[])  # HTTP 호출 금지
    res = upload_media_checked("body", bad, CFG)
    assert res.success is False
    assert "무결성" in (res.error or "")
    assert state["i"] == 0  # 요청 자체가 발생하지 않음

    # 파일 없음
    res2 = upload_media_checked("body", tmp_path / "missing.webp", CFG)
    assert res2.success is False
    assert "파일 없음" in (res2.error or "")


# ── Test 5: Gutenberg wp:image insertion ───────────────────────────

def test_gutenberg_wp_image_insertion():
    block = build_gutenberg_image_block("http://wp.test/img.webp", "연말정산 계산기 안내", 123)
    assert block.startswith("<!-- wp:image")
    assert '"id": 123' in block
    assert '<figure class="wp-block-image">' in block
    assert 'src="http://wp.test/img.webp"' in block
    assert 'alt="연말정산 계산기 안내"' in block
    assert block.endswith("<!-- /wp:image -->")
    # 단순 <img> 삽입이 아니라 wp:image 블록임
    assert block.count("<!-- wp:image") == 1


# ── Test 6: Featured image mapping ──────────────────────────────────

def test_featured_image_mapping(monkeypatch, image_files):
    files = image_files
    state = _mock_posts(monkeypatch, media_responses=[201, 201],
                        post_response=201)
    result = connect_image_to_draft(CFG, files, title="[P4-E2E-TEST] 연말정산")
    assert result.success is True
    assert result.body_media_id == 100
    assert result.thumb_media_id == 101
    assert result.featured_media == 101  # Thumb media_id가 featured_media
    post_payload = state["post_payloads"][0]
    assert post_payload["featured_media"] == 101


# ── Test 7: Draft status enforcement ───────────────────────────────

def test_draft_status_enforcement(monkeypatch, image_files):
    files = image_files
    state = _mock_posts(monkeypatch, media_responses=[201, 201],
                        post_response=201)
    result = connect_image_to_draft(CFG, files, title="[P4-E2E-TEST] 연말정산")
    assert result.success is True
    assert result.status == "draft"
    assert state["post_payloads"][0]["status"] == "draft"


# ── Test 8: Publish status rejection ───────────────────────────────

def test_publish_status_rejection(monkeypatch, image_files):
    """Draft 외 상태가 posts payload에 실릴 수 없음을 검증."""
    files = image_files
    state = _mock_posts(monkeypatch, media_responses=[201, 201],
                        post_response=201)
    result = connect_image_to_draft(CFG, files, title="[P4-E2E-TEST] 연말정산")
    assert result.success is True
    for payload in state["post_payloads"]:
        assert payload["status"] == "draft"
        assert payload["status"] not in ("publish", "future", "private")

    # create_draft는 상태 파라미터를 받지 않는다 (호출부가 publish를 전달할 수 없음)
    import inspect
    sig = inspect.signature(create_draft)
    assert "status" not in sig.parameters


# ── Test 9: Partial media failure prevents draft ───────────────────

def test_partial_media_failure_prevents_draft(monkeypatch, image_files):
    """Body 성공 / Thumb 실패 → Draft 생성하지 않음."""
    files = image_files
    state = _mock_posts(monkeypatch, media_responses=[201, 500])
    result = connect_image_to_draft(CFG, files, title="[P4-E2E-TEST] 연말정산")
    assert result.success is False
    assert result.body_media_id == 100      # Body는 업로드됨
    assert result.thumb_media_id is None
    assert "Thumbnail" in (result.error or "")
    assert state["post_payloads"] == []     # posts 호출 없음


# ── Test 10: Full image → WP flow (mock E2E) ───────────────────────

def test_full_image_to_wp_flow_mock_e2e(monkeypatch, image_files):
    files = image_files
    state = _mock_posts(monkeypatch, media_responses=[201, 201],
                        post_response=201)
    result = connect_image_to_draft(
        CFG, files, title="[P4-E2E-TEST] 연말정산 환급액 계산기",
        alt="연말정산 환급액 계산기 본문 이미지",
        excerpt="테스트 초안 요약",
    )
    assert result.success is True
    assert result.body_media_id == 100
    assert result.thumb_media_id == 101
    assert result.post_id == 500
    assert result.status == "draft"
    assert result.permalink == "http://wp.test/?p=500"
    assert result.featured_media == 101
    # content에 wp:image 블록 + body 이미지 URL
    assert "<!-- wp:image" in result.content
    assert "wp-block-image" in result.content
    assert "http://wp.test/wp-content/uploads/2026/08/img0.webp" in result.content
    # media 2회 + posts 1회 호출 순서
    assert [u for u in state["urls"] if u == MEDIA_URL].count(MEDIA_URL) == 2
    assert state["urls"].count(POSTS_URL) == 1
    # media 요청의 auth가 전사 인증 규약을 사용
    for p in state["media_payloads"]:
        assert p["auth"] == ("tester", "app-pw")


# ── Test 11: WordPress authentication failure ──────────────────────

def test_auth_failure(tmp_path, monkeypatch, image_files):
    # Media 401
    body = _make_webp(tmp_path / "k_body.webp", (800, 450))
    _mock_posts(monkeypatch, media_responses=[401])
    res = upload_media_checked("body", body, CFG)
    assert res.success is False
    assert res.status_code == 401

    # Media 201, 201 → Draft 401
    _mock_posts(monkeypatch, media_responses=[201, 201], post_response=401)
    files = image_files
    result = connect_image_to_draft(CFG, files, title="[P4-E2E-TEST] 연말정산")
    assert result.success is False
    assert "Draft HTTP 401" in (result.error or "")
    assert result.post_id is None


# ── Test 12: Existing publisher compatibility ──────────────────────

def test_existing_publisher_compatibility():
    """modules.publisher의 인증/준비 판정을 그대로 재사용하는지 확인."""
    from modules.publisher import _wp_auth, is_wordpress_ready
    # 커넥터가 동일 헬퍼를 사용 (모듈 네임스페이스 공유)
    assert wc._wp_auth is _wp_auth
    assert wc.is_wordpress_ready is is_wordpress_ready
    # 미구성 설정 → Draft 생성 차단
    empty = {"WORDPRESS_URL": "", "WORDPRESS_USERNAME": "", "wordpress": {}}
    assert is_wordpress_ready(empty) is False
    r = create_draft(empty, title="t", content="c")
    assert r["success"] is False
    assert "미구성" in r["error"]
    # 구성된 설정 → _wp_auth 튜플 형식
    assert _wp_auth(CFG) == ("tester", "app-pw")


# ── Publish 경로 미사용 정적 검증 ──────────────────────────────────

def test_connector_source_has_no_publish_path():
    """P4 신규 커넥터에 publish/future 상태를 만드는 코드가 없어야 한다.

    주석/문서 문자열에는 'publish' 단어가 금지 정책 언급으로 존재할 수 있으므로
    payload 구성부(실행 코드)만 검사한다.
    """
    src = Path(wc.__file__).read_text(encoding="utf-8")
    # payload에 publish/future/private 상태를 세팅하는 실행 코드가 없어야 함
    for forbidden in ("status\": \"publish", "'status': 'publish'",
                      "status=\"publish\"", "status='publish'"):
        assert forbidden not in src
    # draft 상수는 반드시 draft
    assert wc.DRAFT_STATUS == "draft"
    # 금지 상태 denylist는 publish/future/private을 포함해야 함 (경로 차단용)
    assert "publish" in wc.FORBIDDEN_STATUSES
    assert "future" in wc.FORBIDDEN_STATUSES
    assert "private" in wc.FORBIDDEN_STATUSES
