# -*- coding: utf-8 -*-
"""modules/revision_detector.py — 법령 변경 감지기 (Sprint B-2, Detect Only)

정부 공식 원본을 조회해 이전 조회본과 hash를 비교하고, 변경 시 Telegram으로 '감지'만 알린다.
자동 수정은 하지 않는다: legal_master / registry / Writer / WordPress 를 절대 건드리지 않는다.
감지 상태(hash/etag/change_type)는 legal_master가 아니라 별도 파일에 둔다(SSOT 불변 원칙).

흐름:  fetch_official → source_hash → 이전 hash 비교 → 변경 여부 → (변경 시) Telegram + 상태 갱신
정지(비용 0): ETag 304 또는 hash 동일이면 재판독/알림 없이 PASS.

상태 파일: data/legal/revision_state.json
  { entity_id: {source_hash, etag, number_fingerprint, last_checked, last_changed, change_type} }
"""
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path

import requests

from . import telegram_ops
from .logger import get_logger

LOG = get_logger()

# change_type 분류(사용자 지시): 이후 자동수정 로직 단순화를 위한 태그.
CHANGE_TYPES = ("rate_changed", "article_changed", "wording_changed", "abolished", "new_article")


def _state_path(cfg: dict) -> Path:
    root = Path(cfg.get("_root", "."))
    d = root / "data" / "legal"
    d.mkdir(parents=True, exist_ok=True)
    return d / "revision_state.json"


def _load_state(cfg: dict) -> dict:
    p = _state_path(cfg)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(cfg: dict, state: dict):
    _state_path(cfg).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _extract_numbers(text: str) -> list:
    """요율/금액 등 수치 지문(rate_changed 판정용). 정렬된 유니크 리스트."""
    nums = re.findall(r"\d[\d,]*\s*%|\d[\d,]*\s*원|\d[\d,]{2,}", text or "")
    return sorted({re.sub(r"\s+", "", n) for n in nums})


def classify_change(old_nums: list, new_nums: list, old_content: str, new_content: str) -> list:
    """변경 종류 휴리스틱(Detect Only — 정밀 판정은 후속 AI 단계). 최소 1개 반환."""
    types = []
    if set(old_nums or []) != set(new_nums or []):
        types.append("rate_changed")                 # 수치(요율/금액) 변화
    # 폐지/신설 신호(원문 키워드 휴리스틱)
    nc = new_content or ""
    if re.search(r"삭제\s*<|삭제\s*>|폐지|삭제한다", nc) and "삭제" not in (old_content or ""):
        types.append("abolished")
    if re.search(r"신설|본조신설", nc) and "신설" not in (old_content or ""):
        types.append("new_article")
    # 수치 동일 + 내용 변경 → 문구 변경
    if not types:
        types.append("wording_changed")
    return types


def fetch_official(url: str, etag: str = None, timeout: int = 15) -> dict:
    """공식 소스 조회. ETag 조건부 요청으로 재조회 비용 절감.
    반환: {status: 'ok'|'not_modified'|'error', content?, etag?, error?}"""
    if not url:
        return {"status": "error", "error": "no_url"}
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}
    if resp.status_code == 304:
        return {"status": "not_modified"}
    if resp.status_code != 200:
        return {"status": "error", "error": f"HTTP {resp.status_code}"}
    return {"status": "ok", "content": resp.text, "etag": resp.headers.get("ETag")}


def detect_revisions(cfg: dict, only: list = None, fetch=fetch_official) -> dict:
    """legal_master 전 엔티티의 공식 소스를 조회해 변경 감지(Detect Only).
    fetch 주입 가능(테스트용). legal_master/registry 등은 절대 수정하지 않는다.
    반환: {checked, unchanged, changed:[...], baseline:[...], skipped:[...], errors:[...]}"""
    from .registry_loader import load_legal_master
    lm = load_legal_master(force=True)
    state = _load_state(cfg)
    now = datetime.now().isoformat(timespec="seconds")
    rep = {"checked": 0, "unchanged": 0, "changed": [], "baseline": [], "skipped": [], "errors": []}

    for eid, entity in lm.items():
        if only and eid not in only:
            continue
        v = (entity or {}).get("verification") or {}
        url = v.get("source_url")
        if not url:
            rep["skipped"].append({"entity": eid, "reason": "no_source_url"})
            continue
        rep["checked"] += 1
        st = state.get(eid, {})
        fetched = fetch(url, st.get("etag"))
        if fetched["status"] == "not_modified":
            rep["unchanged"] += 1
            st["last_checked"] = now
            state[eid] = st
            continue
        if fetched["status"] == "error":
            rep["errors"].append({"entity": eid, "error": fetched.get("error")})
            continue

        content = fetched.get("content", "")
        new_hash = compute_hash(content)
        new_nums = _extract_numbers(content)
        law_ref = f"{entity.get('law','')} {entity.get('article','')}".strip()

        if not st:   # 최초 baseline — 알림 없음
            state[eid] = {"source_hash": new_hash, "etag": fetched.get("etag"),
                          "number_fingerprint": new_nums, "last_checked": now,
                          "last_changed": None, "change_type": []}
            rep["baseline"].append({"entity": eid, "law": law_ref})
            continue

        if new_hash == st.get("source_hash"):
            rep["unchanged"] += 1
            st["last_checked"] = now
            st["etag"] = fetched.get("etag") or st.get("etag")
            state[eid] = st
            continue

        # 변경 감지 — Detect Only: 상태 갱신 + 알림만(legal_master 미수정)
        change_type = classify_change(st.get("number_fingerprint", []), new_nums,
                                      st.get("_last_content", ""), content)
        state[eid] = {"source_hash": new_hash, "etag": fetched.get("etag"),
                      "number_fingerprint": new_nums, "last_checked": now,
                      "last_changed": now, "change_type": change_type,
                      "prev_hash": st.get("source_hash")}
        item = {"entity": eid, "law": law_ref, "change_type": change_type,
                "impacted": _impacted(eid)}
        rep["changed"].append(item)
        _notify_change(cfg, item)

    _save_state(cfg, state)
    if rep["changed"]:
        _notify_summary(cfg, rep)
    LOG.info("[revision] 감지 완료: 검사 %d / 변경없음 %d / 변경 %d / baseline %d / skip %d / err %d",
             rep["checked"], rep["unchanged"], len(rep["changed"]), len(rep["baseline"]),
             len(rep["skipped"]), len(rep["errors"]))
    return rep


def _impacted(entity_id: str) -> list:
    """참고용: 영향 계산기(Sprint B-3에서 본격화). legal_refs 역인덱스(View)."""
    try:
        from .registry_loader import load_registry_v3
        reg = load_registry_v3()
        return [slug for slug, r in reg.items()
                if entity_id in (r.get("legal_refs") or [])]
    except Exception:
        return []


def _notify_change(cfg: dict, item: dict) -> None:
    try:
        imp = ", ".join(item.get("impacted") or []) or "-"
        telegram_ops.notify_level(
            cfg, "WARNING", f"법령 변경 감지: {item['law']}",
            f"change_type={', '.join(item['change_type'])} · 영향 계산기(참고): {imp}\n"
            f"(감지만 — 자동 수정 없음. 확인 후 조치 필요)",
            event="legal_revision")
    except Exception as e:
        LOG.warning("[revision] 변경 알림 실패(무시): %s", e)


def _notify_summary(cfg: dict, rep: dict) -> None:
    try:
        laws = "\n".join(f"• {c['law']} ({', '.join(c['change_type'])})" for c in rep["changed"][:15])
        telegram_ops.notify_level(
            cfg, "WARNING", f"법령 변경 감지 요약 — {len(rep['changed'])}건",
            laws, event="legal_revision")
    except Exception as e:
        LOG.warning("[revision] 요약 알림 실패(무시): %s", e)
