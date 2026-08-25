# -*- coding: utf-8 -*-
"""modules/site_snapshot.py — 계산기 웹앱 생성 결과의 확정 스냅샷(data/workspace/_site/{slug}/) 읽기/쓰기.

Phase B에서 dashboard.py 지역 함수로 도입된 로직을 그대로 옮긴 것 — 동작 변경 없음.
dashboard.py(수동 🧮 생성 버튼)와 modules/calc_webapp_pipeline.py(자동 스케줄러)가
동일 함수를 공유한다.
"""
import os
from pathlib import Path

_SNAPSHOT_FILES = ("index.html", "style.css", "script.js")


def site_slug_dir(cfg: dict, calc: dict) -> Path:
    base = Path(cfg.get("_root", "."))
    slug = (str(calc.get("slug", calc.get("id", "")))
            .strip().replace("/", "_").replace("\\", "_").replace("..", "_")
            or calc.get("id", ""))
    return base / "data" / "workspace" / "_site" / slug


def write_site_snapshot(cfg: dict, calc: dict, files: dict) -> str:
    outdir = site_slug_dir(cfg, calc)
    os.makedirs(outdir, exist_ok=True)
    for fn in _SNAPSHOT_FILES:
        content = files.get(fn)
        if content:      # Tier2-B 등 일부 파일이 없는 산출물 대응(빈 파일 생성 방지)
            (outdir / fn).write_text(content, encoding="utf-8")
    return str(outdir)


def read_site_snapshot(cfg: dict, calc: dict) -> dict:
    outdir = site_slug_dir(cfg, calc)
    out = {}
    for fn in _SNAPSHOT_FILES:
        p = outdir / fn
        if p.exists():
            out[fn] = p.read_text(encoding="utf-8")
    return out
