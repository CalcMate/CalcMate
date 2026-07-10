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

# Sprint B-3: change_type → 영향도(Impact Level). HIGH일수록 재평가 우선.
_CHANGE_SEVERITY = {
    "rate_changed": "HIGH", "formula_changed": "HIGH", "abolished": "HIGH",
    "article_changed": "MEDIUM", "new_article": "MEDIUM",
    "wording_changed": "LOW",
}
_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
_RANK_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


def impact_level(change_types: list) -> str:
    """change_type 목록 → 최고 영향도(HIGH/MEDIUM/LOW/NONE)."""
    if not change_types:
        return "NONE"
    top = max(_SEVERITY_RANK[_CHANGE_SEVERITY.get(c, "LOW")] for c in change_types)
    return _RANK_SEVERITY[top]


def analyze_impact(entity_id: str, change_types: list) -> dict:
    """법령 변경 → 영향 분석(Detect→Analyze, 자동수정 없음).
    반환: {legal_id, change_type, affected:[{slug,name}], severity}."""
    from .registry_loader import find_impacted, calculator_name
    slugs = find_impacted(entity_id)
    return {
        "legal_id": entity_id,
        "change_type": change_types,
        "affected": [{"slug": s, "name": calculator_name(s)} for s in slugs],
        "severity": impact_level(change_types),
    }


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

        # 변경 감지 — Detect→Analyze. Detect Only: 상태 갱신 + 알림만(legal_master 미수정)
        change_type = classify_change(st.get("number_fingerprint", []), new_nums,
                                      st.get("_last_content", ""), content)
        state[eid] = {"source_hash": new_hash, "etag": fetched.get("etag"),
                      "number_fingerprint": new_nums, "last_checked": now,
                      "last_changed": now, "change_type": change_type,
                      "prev_hash": st.get("source_hash")}
        analysis = analyze_impact(eid, change_type)     # {legal_id, change_type, affected, severity}
        item = {"entity": eid, "law": law_ref, **analysis}
        rep["changed"].append(item)
        _notify_change(cfg, item)

    _save_state(cfg, state)
    # 재평가 우선순위: severity HIGH를 상단에(자동 실행 아님 — 표시만)
    rep["changed"].sort(key=lambda c: _SEVERITY_RANK.get(c.get("severity", "NONE"), 0), reverse=True)
    rep["reeval_candidates"] = [c["legal_id"] for c in rep["changed"]
                                if c.get("severity") in ("HIGH", "MEDIUM")]
    if rep["changed"]:
        _notify_summary(cfg, rep)
    LOG.info("[revision] 감지 완료: 검사 %d / 변경없음 %d / 변경 %d(HIGH=%d) / baseline %d / skip %d / err %d",
             rep["checked"], rep["unchanged"], len(rep["changed"]),
             sum(1 for c in rep["changed"] if c.get("severity") == "HIGH"),
             len(rep["baseline"]), len(rep["skipped"]), len(rep["errors"]))
    return rep


def _notify_change(cfg: dict, item: dict) -> None:
    """사람이 바로 이해하는 형태(법령 → 변경종류/영향도 → 영향 계산기 목록)."""
    try:
        names = [a["name"] for a in item.get("affected", [])]
        body = (f"변경: {', '.join(item['change_type'])} · 영향도 {item['severity']}\n"
                f"영향 계산기 {len(names)}개:\n" +
                ("\n".join(f" - {n}" for n in names[:10]) if names else " - (참조 계산기 없음)") +
                "\n(감지만 — 자동 수정 없음. 확인 후 조치)")
        telegram_ops.notify_level(cfg, "WARNING", f"법령 변경 감지: {item['law']}",
                                  body, event="legal_revision")
    except Exception as e:
        LOG.warning("[revision] 변경 알림 실패(무시): %s", e)


def _notify_summary(cfg: dict, rep: dict) -> None:
    try:
        lines = []
        for c in rep["changed"][:15]:
            n = len(c.get("affected", []))
            lines.append(f"• [{c['severity']}] {c['law']} ({', '.join(c['change_type'])}) → 계산기 {n}개")
        telegram_ops.notify_level(
            cfg, "WARNING", f"법령 변경 감지 요약 — {len(rep['changed'])}건 (재평가 대상 {len(rep['reeval_candidates'])})",
            "\n".join(lines), event="legal_revision")
    except Exception as e:
        LOG.warning("[revision] 요약 알림 실패(무시): %s", e)
