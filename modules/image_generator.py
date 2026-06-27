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
    return {"thumbnail_url": thumb_url or "실패", "body_image_url": body_url or "실패"}

def _generate_free_image(post_id: str, kind: str, prompt: str, cfg: dict) -> str | None:
    try:
        if not prompt:
            prompt = "Beautiful digital art landscape"
            
        # 영문 프롬프트를 URL 주소 형식으로 안전하게 인코딩합니다.
        encoded_prompt = urllib.parse.quote(prompt)
        
        # 100% 무료 고화질 이미지 생성 엔드포인트 주소 구성
        # 썸네일은 1:1 비율(width=512, height=512), 본문은 16:9 비율(width=800, height=450)
        if kind == "thumb":
            url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=512&height=512&nologo=true"
        else:
            url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=800&height=450&nologo=true"
            
        print(f"🚀 무료 이미지 생성 요청 중 ({kind})...")
        response = requests.get(url, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ [image_generator] 무료 이미지 서버 응답 에러: {response.status_code}")
            return None
            
        # 받은 이미지 바이너리 데이터를 파일로 저장
        img = Image.open(io.BytesIO(response.content))
        
        fname = f"{post_id}_{kind}.webp"
        fpath = OUTPUT_DIR / fname
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        img.save(str(fpath), format="WEBP")
        print(f"✅ 무료 로컬 이미지 저장 성공: {fpath.absolute()}")
        
        try:
            return _upload(fpath, cfg)
        except Exception as e:
            # Drive 업로드 실패 시 로컬 경로로 폴백하되 원인 기록
            LOG.warning("이미지 Drive 업로드 실패 → 로컬 경로 사용 (%s): %s", kind, e,
                        exc_info=(cfg.get("LOG_LEVEL", "INFO") == "DEBUG"))
            return str(fpath.absolute())
        
    except Exception as e:
        print(f"❌ [image_generator] {kind} 무료 이미지 생성 실패: {e}")
        return None

def _upload(fpath: Path, cfg: dict) -> str | None:
    from adapters.storage.factory import get_storage_adapter
    storage = get_storage_adapter(cfg)
    folder = cfg.get("GOOGLE_DRIVE_ROOT_ID", "images")
    return storage.save_file(fpath, fpath.name, folder=folder)