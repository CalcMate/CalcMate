# -*- coding: utf-8 -*-
"""
image_pipeline/asset_processor.py — AI Asset 배경 제거 + halo 정리 + 정규화

참조: calcmate_v1_reference/scripts/pipeline_reference.py 의 검증된 파라미터를
팀 구조로 이식한 것. 임계값/침식횟수/비율 값은 실측 검증된 값이므로
근거 없이 바꾸지 말 것 (바꾸려면 결과 이미지로 재검증 후 바꿀 것).

핵심 원칙 (참조 README 이슈 #1/#2/#6):
  - "투명 PNG로 받았다"는 전제를 신뢰하지 않는다. 알파가 없거나(RGB 모드)
    체커보드가 픽셀로 박제된 경우 rembg(u2netp)로 배경 제거를 거친다.
  - halo(반투명 회색 잔상)는 이미지마다 파라미터가 다르다. 결과를 3배 확대해
    육안 확인하는 단계를 파이프라인에 포함한다.
  - AI가 상반신만 요청했어도 전신으로 오는 경우가 있어, 상반신 크롭 옵션을 둔다.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

# rembg는 무거운 의존성(onnxruntime)이므로 함수 내부에서 lazy import 한다.
# 사용 전 pip install rembg onnxruntime 필요.
_rembg_session = None


def _get_session():
    global _rembg_session
    if _rembg_session is None:
        try:
            from rembg import new_session
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "rembg 미설치: `pip install rembg onnxruntime` 후 재시도하세요."
            ) from e
        # onnxruntime가 기본으로 코어 수만큼 스레드를 띄우며 메모리 피크가 커져
        # 작은 버퍼 할당도 실패(OOM)하는 환경이 있었다. 스레드를 1로 제한한다.
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        # u2netp 경량모델. 정밀모델(bria-rmbg)은 메모리 부족(OOM) 이력이 있어
        # 메모리가 넉넉한 환경에서만 시도할 것.
        _rembg_session = new_session("u2netp")
    return _rembg_session


def clean_ai_asset(input_path: str | Path, output_path: str | Path,
                   alpha_threshold: int = 40,
                   erosion_iterations: int = 2,
                   force_rembg: bool = False) -> Path:
    """AI Asset 배경 제거 + halo 제거.

    - 입력 PNG에 알파가 있고(투명 배경 확인) force_rembg=False면
      rembg 없이 halo 정리만 수행한다.
    - 알파가 없거나(RGB/체커보드 박제) force_rembg=True면 rembg로 배경 제거 후
      halo 정리를 얹는다.

    alpha_threshold: 이 값보다 낮은 알파는 완전투명(0)으로 처리.
        연말정산(남)은 40, 퇴직금(여)은 90까지 필요했음 (손가락 주변 halo).
    erosion_iterations: 침식 반복 횟수. 남성 2회, 여성 4회.
        고정값 하나로 모든 이미지에 강제하지 말고, 처리 후 3배 확대 육안 확인 후
        halo가 남으면 올릴 것.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    img = Image.open(input_path)

    # ── 알파 채널 확인 (참조 이슈 #1) ─────────────────────────────
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if force_rembg or not has_alpha:
        session = _get_session()
        from rembg import remove
        rgba = img.convert("RGBA")
        result = remove(rgba, session=session)
    else:
        result = img.convert("RGBA")

    # 메모리 절약: uint8 배열을 float32로 복사하지 않고 int16 임시 배열만 사용한다.
    # (onnxruntime 세션이 상주하는 환경에서는 float32 사본이 OOM을 유발할 수 있음)
    arr = np.array(result)  # uint8 RGBA
    alpha = arr[:, :, 3].astype(np.int16)
    alpha_clean = np.where(alpha < alpha_threshold, 0, alpha)
    mask = (alpha_clean > 10).astype(np.uint8)
    eroded = ndimage.binary_erosion(mask, iterations=erosion_iterations).astype(np.uint8)
    alpha_final = (alpha_clean * eroded).astype(np.uint8)

    arr[:, :, 3] = alpha_final
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(output_path)
    return output_path


def normalize_character(input_path: str | Path, output_path: str | Path,
                        canvas_size: int = 800,
                        height_ratio: float = 0.75,
                        bottom_margin: int = 20,
                        crop_upper_body_ratio: float | None = None) -> Path:
    """Character Asset Standard v1 정규화.

    - 800x800 정사각형 투명 캔버스 (규격 임의 변경 금지)
    - 캐릭터 높이가 캔버스의 70~80% (기본 0.75)
    - 하단 중앙 정렬, 상하좌우 여백 필수

    crop_upper_body_ratio: AI가 전신으로 그려준 경우 위쪽 비율만큼 잘라
        상반신만 사용 (참조: 퇴직금 여성 캐릭터 0.55).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    img = Image.open(input_path).convert("RGBA")

    bbox = img.split()[-1].getbbox()
    if not bbox:
        raise ValueError(f"[normalize_character] 알파 bbox 없음: {input_path}")

    if crop_upper_body_ratio:
        x0, y0, x1, y1 = bbox
        crop_bottom = y0 + int((y1 - y0) * crop_upper_body_ratio)
        img = img.crop((x0, y0, x1, crop_bottom))
        bbox = img.split()[-1].getbbox()

    cropped = img.crop(bbox)
    target_h = int(canvas_size * height_ratio)
    w, h = cropped.size
    scale = target_h / h
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = (canvas_size - new_w) // 2
    y = canvas_size - new_h - bottom_margin
    canvas.paste(resized, (x, y), resized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def normalize_hero_object(input_path: str | Path, output_path: str | Path,
                          canvas_size: int = 500,
                          height_ratio: float = 0.75) -> Path:
    """곡선형 Hero Object(트로피/금고/시계 등) 정규화.

    캐릭터와 달리 중앙 정렬(하단 정렬 아님) — SVG 좌표 위 특정 지점에
    얹히는 방식이라 캔버스 중앙 기준이 다루기 쉽다.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    img = Image.open(input_path).convert("RGBA")

    bbox = img.split()[-1].getbbox()
    if not bbox:
        raise ValueError(f"[normalize_hero_object] 알파 bbox 없음: {input_path}")

    cropped = img.crop(bbox)
    target_h = int(canvas_size * height_ratio)
    w, h = cropped.size
    scale = target_h / h
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = (canvas_size - new_w) // 2
    y = (canvas_size - new_h) // 2
    canvas.paste(resized, (x, y), resized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def qa_asset_clean(path: str | Path, alpha_threshold: int = 40,
                   halo_dist: int = 4) -> dict:
    """정규화 완료 에셋의 halo 잔존 여부 자동 체크.

    반투명 경계(AA)는 불투명 코어와 인접하므로 halo가 아니다.
    halo란 불투명 코어에서 halo_dist px 이상 떨어진 '떠 있는 반투명
    픽셀'이다 (예: rembg가 남긴 반투명 회색 잔상).

    허용치 보정 근거: 참조 패키지에서 검증 완료된 확정 에셋(연말정산 남성
    캐릭터) 기준으로 halo_px 허용 상한을 캔버스 면적의 0.25%로 잡았다.
    손/머리카락 같은 얇은 특징의 소프트 AA 픽셀은 코어에서 멀어질 수
    있어 halo로 오판하지 않도록 여유를 둔다. 최종 판정은 3배 확대 육안
    확인을 병행한다 (참조 README 이슈 #2).
    """
    path = Path(path)
    img = Image.open(path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    core = alpha >= alpha_threshold
    dilated = ndimage.binary_dilation(core, iterations=halo_dist)
    semi = (alpha > 0) & (alpha < alpha_threshold)
    halo_px = int((semi & ~dilated).sum())
    w, h = img.size
    tolerance = max(100, int(w * h * 0.0025))
    bbox = img.split()[-1].getbbox()
    return {
        "path": str(path),
        "size": img.size,
        "alpha_bbox": bbox,
        "halo_px": halo_px,
        "halo_tolerance": tolerance,
        "semi_transparent_px": int(semi.sum()),
        "halo_ok": halo_px <= tolerance,
    }
