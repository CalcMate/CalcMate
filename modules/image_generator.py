"""
modules/image_generator.py — STEP 10: 이미지 생성 (100% 전면 무료 API 전환 버전)
"""
import io
import requests
from pathlib import Path
from PIL import Image
import urllib.parse
from .logger import get_logger

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "outputs"
LOG = get_logger()

def generate(post_id: str, seo_data: dict, cfg: dict) -> dict:
    thumb_url = _generate_free_image(post_id, "thumb", seo_data.get("image_prompt_thumbnail", ""), cfg)
    body_url  = _generate_free_image(post_id, "body",  seo_data.get("image_prompt_body", ""),  cfg)
    # 폴백: Pollinations 실패 시 브랜드 템플릿 이미지 생성(항상 결과 보장)
    title = seo_data.get("seo_title", "") or seo_data.get("main_keyword", "")
    if not thumb_url:
        thumb_url = _fallback(post_id, "thumb", title, cfg)
    if not body_url:
        body_url = _fallback(post_id, "body", title, cfg)
    return {"thumbnail_url": thumb_url or "실패", "body_image_url": body_url or "실패"}


def _fallback(post_id: str, kind: str, title: str, cfg: dict) -> str | None:
    try:
        from . import image_fallback
        fpath = image_fallback.generate_brand_image(post_id, kind, title)
        if not fpath:
            return None
        return str(Path(fpath).absolute())
    except Exception as e:
        LOG.warning("이미지 폴백 실패: %s", e)
        return None

def _generate_free_image(post_id: str, kind: str, prompt: str, cfg: dict) -> str | None:
    try:
        if not prompt:
            prompt = "Beautiful digital art landscape"
            
        encoded_prompt = urllib.parse.quote(prompt)
        if kind == "thumb":
            url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=512&height=512&nologo=true"
        else:
            url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=800&height=450&nologo=true"
            
        LOG.info("무료 이미지 생성 요청 중 (%s)", kind)
        response = requests.get(url, timeout=60)
        
        if response.status_code != 200:
            LOG.error("[image_generator] 무료 이미지 서버 응답 에러: %s", response.status_code)
            return None
            
        img = Image.open(io.BytesIO(response.content))
        
        fname = f"{post_id}_{kind}.webp"
        fpath = OUTPUT_DIR / fname
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        img.save(str(fpath), format="WEBP")
        LOG.info("무료 로컬 이미지 저장 성공: %s", fpath.absolute())
        
        return str(fpath.absolute())
        
    except Exception as e:
        LOG.error("[image_generator] %s 무료 이미지 생성 실패: %s", kind, e)
        return None

def _upload(fpath: Path, cfg: dict) -> str | None:
    # 이 함수는 삭제 금지 원칙에 따라 코드만 남겨두고 호출하지 않음.
    from adapters.storage.factory import get_storage_adapter
    storage = get_storage_adapter(cfg)
    folder = cfg.get("GOOGLE_DRIVE_ROOT_ID", "images")
    return storage.save_file(fpath, fpath.name, folder=folder)