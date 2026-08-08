# -*- coding: utf-8 -*-
"""
modules/rewrite_pipeline.py — 계산기 블로그 자동 리라이트 파이프라인 (P2-3)

기존 컴포넌트 재사용:
  - modules/calculator_pipeline.write_article_for_rewrite (writer)
  - modules/calculator_seo_generator.generate_seo
  - modules/calculator_faq_generator.generate_faq
  - modules/publish_quality.check_publish_quality
  - modules/publisher.update_post
  - repositories/article_repository.ArticleRepository
  - repositories/calculator_repository.CalculatorRepository

신규:
  - collect_rewrite_candidates(cfg): RMS + time-based 후보 수집
  - run_calculator_rewrite(cfg, article_row, calc, reason): 리라이트 실행
  - _load_rewrite_processed, _mark_processed: RMS 이벤트 중복 방지
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository
from repositories.calculator_repository import CalculatorRepository
from .logger import get_logger

LOG = get_logger("rewrite")


# ── Phase A: 처리 완료 이벤트 파일 관리 ─────────────────────────────────────────


def _processed_path(cfg: dict) -> Path:
    """data/legal/rewrite_processed.json 절대 경로."""
    root = Path(cfg.get("_root", ".")).resolve()
    d = root / "data" / "legal"
    d.mkdir(parents=True, exist_ok=True)
    return d / "rewrite_processed.json"


def _load_rewrite_processed(cfg: dict) -> dict:
    """처리 완료 RMS 이벤트 dict 로드. 없으면 {}."""
    p = _processed_path(cfg)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _mark_processed(cfg: dict, rms_event_id: str, article_id: str, result: str) -> None:
    """RMS 이벤트 처리 완료 기록. result: 'success' | 'quality_fail' | 'wp_api_error' | 'skipped'.

    성공한 리라이트만 processed로 확정한다 — 실패 시 다음 스케줄에서 재도전 허용.
    호출 측에서 result='success' 인 경우에만 이 함수를 호출해야 한다.
    """
    processed = _load_rewrite_processed(cfg)
    processed[rms_event_id] = {
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "article_id": str(article_id),
        "result": result,
    }
    p = _processed_path(cfg)
    p.write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.debug("[rewrite] processed 기록: %s → %s", rms_event_id, result)


# ── Phase B: collect_rewrite_candidates ─────────────────────────────────────


def _rms_candidates(cfg: dict, processed: dict) -> list:
    """revision_state.json 기반 RMS 후보 목록 반환."""
    from .revision_detector import _load_state, _CHANGE_SEVERITY, _SEVERITY_RANK
    from .rms import IMPACT_MAP

    state = _load_state(cfg)
    if not state:
        LOG.debug("[rewrite][RMS] revision_state.json 없음 또는 빈 상태")
        return []

    art_repo = ArticleRepository(get_db_adapter(cfg))
    calc_repo = CalculatorRepository(get_db_adapter(cfg))
    try:
        all_rows = list(art_repo.get_all())
    except Exception as e:
        LOG.warning("[rewrite][RMS] article 조회 실패: %s", e)
        return []
    try:
        all_calcs_list = list(calc_repo.get_all())
    except Exception as e:
        LOG.warning("[rewrite][RMS] calculator 조회 실패: %s", e)
        return []

    # slug → calc 매핑
    all_calcs = {str(c.get("slug", "")): c for c in all_calcs_list if c.get("slug")}

    # REWRITE_CHANGE_SEVERITY_MIN: 설계 확정값 MEDIUM (wording_changed=LOW 제외)
    min_severity = _SEVERITY_RANK.get(
        str(cfg.get("REWRITE_CHANGE_SEVERITY_MIN", "MEDIUM")).upper(), 2
    )

    candidates = []
    for entity_id, st in state.items():
        change_types = st.get("change_type") or []
        if isinstance(change_types, str):
            change_types = [change_types]
        last_changed = str(st.get("last_changed") or "").strip()
        if not last_changed or not change_types:
            continue

        # severity 필터 — wording_changed(LOW=1)는 min_severity(MEDIUM=2) 미만으로 제외
        top_rank = max(
            (_SEVERITY_RANK.get(_CHANGE_SEVERITY.get(c, "LOW"), 1) for c in change_types),
            default=0,
        )
        if top_rank < min_severity:
            LOG.debug("[rewrite][RMS] severity 미달 SKIP: entity=%s types=%s", entity_id, change_types)
            continue

        # 중복 방지 — 성공 처리된 동일 RMS 이벤트 SKIP
        rms_event_id = f"{entity_id}__{last_changed}"
        if rms_event_id in processed:
            LOG.debug("[rewrite][RMS] 이미 처리됨 SKIP: %s", rms_event_id)
            continue

        affected_slugs = IMPACT_MAP.get(entity_id, [])
        if not affected_slugs:
            LOG.debug("[rewrite][RMS] 영향 계산기 없음 SKIP: entity=%s", entity_id)
            continue

        severity_str = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}.get(top_rank, "LOW")
        reason = {
            "type": "legal_change",
            "source": "RMS",
            "detected_at": datetime.now().isoformat(timespec="seconds"),
            "severity": severity_str,
            "entity_id": entity_id,
            "rms_event_id": rms_event_id,
            "change_type": change_types,
            "last_changed": last_changed,
            "affected_fields": [],
        }

        for slug in affected_slugs:
            calc = all_calcs.get(slug)
            if not calc:
                LOG.debug("[rewrite][RMS] slug 미존재 SKIP: %s", slug)
                continue
            cid = str(calc.get("id", ""))
            published = [
                r for r in all_rows
                if str(r.get("상태값", "")).strip() == "발행완료"
                and str(r.get("wp_post_id") or "").strip()
                and str(r.get("calculator_id", "")) == cid
            ]
            for row in published:
                candidates.append({
                    "article_id": str(row.get("ID", "")),
                    "calculator_id": cid,
                    "wp_post_id": str(row.get("wp_post_id", "")),
                    "slug": slug,
                    "reason": reason,
                    "severity_rank": top_rank,
                })

    return candidates


def _time_based_candidates(cfg: dict) -> list:
    """published_at 기준 REWRITE_STALE_DAYS 경과 후보. time-based 쿨다운 적용."""
    stale_days = int(cfg.get("REWRITE_STALE_DAYS", 365))
    cooldown_days = int(cfg.get("REWRITE_COOLDOWN_DAYS", 90))
    cutoff = (datetime.now() - timedelta(days=stale_days)).isoformat()

    art_repo = ArticleRepository(get_db_adapter(cfg))
    try:
        all_rows = list(art_repo.get_all())
    except Exception as e:
        LOG.warning("[rewrite][time] article 조회 실패: %s", e)
        return []

    candidates = []
    for row in all_rows:
        if str(row.get("상태값", "")).strip() != "발행완료":
            continue
        if not str(row.get("wp_post_id") or "").strip():
            continue

        published_at = str(row.get("published_at") or row.get("발행일시") or "").strip()
        if not published_at:
            continue
        # 날짜 비교 — ISO 문자열 사전순 비교로 충분 (YYYY-MM-DD... 형식)
        if published_at[:19] > cutoff[:19]:
            continue

        # 쿨다운 확인 — history의 최근 rewrite_success 이벤트 기준
        try:
            hist = json.loads(row.get("history") or "[]")
            if not isinstance(hist, list):
                hist = []
        except Exception:
            hist = []
        last_rewrite_ts = next(
            (e.get("ts") for e in reversed(hist) if e.get("event") == "rewrite_success"),
            None,
        )
        if last_rewrite_ts:
            try:
                last_dt = datetime.fromisoformat(last_rewrite_ts[:19])
                if (datetime.now() - last_dt).days < cooldown_days:
                    LOG.debug("[rewrite][time] 쿨다운 SKIP: article_id=%s", row.get("ID"))
                    continue
            except Exception:
                pass

        try:
            stale = (datetime.now() - datetime.fromisoformat(published_at[:19])).days
        except Exception:
            stale = stale_days

        reason = {
            "type": "time_based",
            "source": "scheduler",
            "detected_at": datetime.now().isoformat(timespec="seconds"),
            "severity": "LOW",
            "stale_days": stale,
        }
        candidates.append({
            "article_id": str(row.get("ID", "")),
            "calculator_id": str(row.get("calculator_id", "")),
            "wp_post_id": str(row.get("wp_post_id", "")),
            "slug": "",
            "reason": reason,
            "severity_rank": 1,
        })

    return candidates


def collect_rewrite_candidates(cfg: dict) -> list:
    """RMS + time-based 리라이트 후보 수집. DAILY_REWRITE_LIMIT 적용 후 반환.

    각 항목:
      {article_id, calculator_id, wp_post_id, slug, reason, severity_rank}
    """
    limit = int(cfg.get("DAILY_REWRITE_LIMIT", 1))
    processed = _load_rewrite_processed(cfg)

    rms = _rms_candidates(cfg, processed)
    timed = _time_based_candidates(cfg)

    LOG.info("[rewrite] RMS 후보 %d건, time-based 후보 %d건", len(rms), len(timed))

    # calculator_id 기준 중복 제거 — 동일 계산기에 여러 트리거 시 severity 높은 것 채택
    seen: dict[str, dict] = {}
    for c in sorted(rms + timed, key=lambda x: x["severity_rank"], reverse=True):
        cid = c["calculator_id"]
        if cid and cid not in seen:
            seen[cid] = c

    # "리라이트중" 상태 건 제외 (선점된 건 중복 클레임 방지)
    art_repo = ArticleRepository(get_db_adapter(cfg))
    try:
        running = {
            str(r.get("ID", ""))
            for r in art_repo.get_all()
            if str(r.get("상태값", "")).strip() == "리라이트중"
        }
    except Exception:
        running = set()

    final = [c for c in seen.values() if c["article_id"] not in running]

    # severity DESC → 일일 한도
    final.sort(key=lambda x: x["severity_rank"], reverse=True)
    LOG.info("[rewrite] 중복제거 후 %d건 → 한도 %d건 적용", len(final), limit)
    return final[:limit]


# ── Phase C: run_calculator_rewrite ─────────────────────────────────────────


def run_calculator_rewrite(cfg: dict, article_row: dict, calc: dict, reason: dict) -> dict:
    """단건 리라이트 실행.

    반환: {result, article_id, wp_post_id, quality_score, reason_type}
    result: 'SUCCESS' | 'FAILED'
    실패 시 WordPress 기존 게시물은 유지되고, DB 상태는 '발행완료'로 복원된다.
    """
    from .calculator_pipeline import write_article_for_rewrite
    from .calculator_seo_generator import generate_seo
    from .calculator_faq_generator import generate_faq
    from . import content_quality, publisher
    from .publish_quality import check_publish_quality
    from .app_generator import render_inline_calculator, generate_calculator
    from .internal_link_engine import (
        generate_related_calculators, generate_related_articles, inject_internal_links
    )
    from . import telegram_ops as tops
    from .logger import BudgetTracker

    article_id = str(article_row.get("ID", ""))
    wp_post_id = str(article_row.get("wp_post_id", ""))
    cid = str(article_row.get("calculator_id", ""))
    calc_name = calc.get("name", "")
    art_repo = ArticleRepository(get_db_adapter(cfg))

    LOG.info("[rewrite] 시작: article_id=%s calc=%s reason=%s",
             article_id, calc_name, reason.get("type"))

    # 1) 상태 선점 — "리라이트중" (동시 실행 시 동일 article 중복 클레임 방지)
    art_repo.update_status(article_id, "리라이트중",
                           {"rewrite_reason_type": reason.get("type", "")})
    art_repo.append_history(article_id, "rewrite_started", {
        "reason": reason,
        "old_quality_score": article_row.get("quality_score"),
        "ts": datetime.now().isoformat(timespec="seconds"),
    })

    def _restore_and_fail(fail_cause: str, extra: dict = None) -> dict:
        """실패 공통 처리 — DB 상태를 '발행완료'로 복원, history에 rewrite_failed 기록.
        WordPress 기존 게시물은 update_post를 호출하지 않았으므로 자동 유지된다."""
        art_repo.update_status(article_id, "발행완료", {})
        art_repo.append_history(article_id, "rewrite_failed", {
            "fail_cause": fail_cause,
            "reason_type": reason.get("type"),
            "ts": datetime.now().isoformat(timespec="seconds"),
            **(extra or {}),
        })
        LOG.warning("[rewrite] FAILED: %s | cause=%s | article_id=%s", calc_name, fail_cause, article_id)
        return {
            "result": "FAILED",
            "fail_cause": fail_cause,
            "article_id": article_id,
            "wp_post_id": wp_post_id,
        }

    try:
        # 2) SEO 생성 — keyword는 기존 정책명 유지. title은 update_post에서 미전송(None).
        keyword = str(article_row.get("정책명") or article_row.get("keyword") or calc_name).strip()
        seo = generate_seo(cfg, calc_name, keyword)

        # 3) FAQ — DB 저장본 우선, 없으면 신규 생성
        faq = []
        if calc.get("faq"):
            try:
                faq = json.loads(calc["faq"]) if isinstance(calc["faq"], str) else calc["faq"]
            except Exception:
                faq = []
        if not faq:
            faq = generate_faq(cfg, calc)

        # 4) Writer — write_article_for_rewrite는 calculator_pipeline._write_article 위임자
        body_html, _ = write_article_for_rewrite(cfg, calc, keyword, seo, faq, failed_rules=None)
        body_html = content_quality.improve_content(body_html)

        # 5) 위젯 + 내부링크 조립
        try:
            widget_cfg = {**cfg, "SHOW_ARTICLE": False, "SHOW_FAQ": False,
                         "SHOW_RELATED": False, "SHOW_ADSENSE": False,
                         "SHOW_CPA": False, "SHOW_PWA": False}
            widget = render_inline_calculator(generate_calculator(calc, widget_cfg))
        except Exception as _we:
            LOG.warning("[rewrite] 위젯 생성 실패(빈 문자열 대체): %s", _we)
            widget = ""

        rel_calc = generate_related_calculators(cfg, cid, 3)
        rel_art = generate_related_articles(cfg, keyword, 3)
        link_pool_size = (
            sum(1 for c in rel_calc if c.get("url")) +
            sum(1 for a in rel_art if a.get("title") and a.get("url"))
        )

        CTA_TEXT = "아래 CalcMate 계산기를 이용하면 자동으로 계산할 수 있습니다."
        final_html = (
            f"{body_html}\n<hr/>\n"
            f"<h2>계산기 사용하기</h2>\n<p>{CTA_TEXT}</p>\n{widget}"
        )
        try:
            final_html = inject_internal_links(final_html, rel_calc, rel_art)
        except Exception as _le:
            LOG.warning("[rewrite] 내부링크 주입 실패(무시): %s", _le)

        # 6) H-4 Quality Gate + 재시도
        rcfg = cfg.get("QUALITY_RETRY") or {}
        max_total = int(rcfg.get("MAX_TOTAL_RETRY", 3) or 3)
        qc = check_publish_quality(cfg, body_html, final_html, calc,
                                   link_pool_size=link_pool_size)
        q_retries = 0
        while qc.get("result") == "REWRITE" and q_retries < max_total:
            q_retries += 1
            LOG.debug("[rewrite] H-4 재시도 %d/%d: %s", q_retries, max_total, calc_name)
            body_html, _ = write_article_for_rewrite(
                cfg, calc, keyword, seo, faq, failed_rules=qc.get("failed_rules")
            )
            body_html = content_quality.improve_content(body_html)
            final_html = (
                f"{body_html}\n<hr/>\n"
                f"<h2>계산기 사용하기</h2>\n<p>{CTA_TEXT}</p>\n{widget}"
            )
            try:
                final_html = inject_internal_links(final_html, rel_calc, rel_art)
            except Exception:
                pass
            qc = check_publish_quality(cfg, body_html, final_html, calc,
                                       link_pool_size=link_pool_size)

        final_html = qc.get("html") or final_html  # G6 CTA 수정본

        if qc.get("result") == "REWRITE":
            LOG.warning("[rewrite] H-4 최종 FAIL — 기존 글 유지: %s (retries=%d)", calc_name, q_retries)
            return _restore_and_fail("quality_gate_fail",
                                     {"failed_rules": qc.get("failed_rules"),
                                      "retries": q_retries})

        # 7) WP 업데이트 — title=None(기존 SEO title/permalink 유지), content+excerpt만 갱신
        meta_desc = str(seo.get("seo_description") or "").strip()
        pub_result = publisher.update_post(
            cfg, wp_post_id,
            title=None,          # SEO title 보존 (설계 확정)
            content=final_html,
            excerpt=meta_desc if meta_desc else None,
        )

        if not pub_result.get("success"):
            LOG.warning("[rewrite] WP update 실패: %s", pub_result.get("error"))
            try:
                tops.notify_level(cfg, "WARNING",
                    f"리라이트 WP 실패: {calc_name}",
                    f"wp_post_id={wp_post_id} · {str(pub_result.get('error',''))[:100]}",
                    event="error")
            except Exception:
                pass
            # WP update 실패 → WordPress 게시물은 변경 없음(update_post가 실패했으므로)
            return _restore_and_fail("wp_api_error", {"error": str(pub_result.get("error", ""))[:200]})

        # 8) 성공 — DB 갱신
        new_fields = {
            "quality_score": qc.get("score"),
            "quality_status": qc.get("result", ""),
            "quality_reviewed_at": datetime.now().isoformat(),
        }
        art_repo.update_status(article_id, "발행완료", new_fields)
        art_repo.append_history(article_id, "rewrite_success", {
            "reason_type": reason.get("type"),
            "reason_source": reason.get("source"),
            "rms_event_id": reason.get("rms_event_id"),
            "new_quality_score": qc.get("score"),
            "wp_post_id": wp_post_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })

        # 9) RMS 이벤트 처리 완료 기록 — 성공한 경우에만 확정
        if reason.get("type") == "legal_change" and reason.get("rms_event_id"):
            _mark_processed(cfg, reason["rms_event_id"], article_id, "success")

        LOG.info("[rewrite] SUCCESS: %s (score=%s, wp=%s)", calc_name, qc.get("score"), wp_post_id)

        try:
            tops.notify_level(cfg, "INFO",
                f"리라이트 완료: {calc_name}",
                f"reason={reason.get('type')} · score={qc.get('score')} · wp={wp_post_id}",
                event="publish_success")
        except Exception:
            pass

        return {
            "result": "SUCCESS",
            "article_id": article_id,
            "wp_post_id": wp_post_id,
            "quality_score": qc.get("score"),
            "reason_type": reason.get("type"),
        }

    except Exception as e:
        LOG.error("[rewrite] 예외: %s | calc=%s", e, calc_name, exc_info=True)
        try:
            from . import telegram_ops as tops
            tops.notify_level(cfg, "ERROR",
                f"리라이트 예외: {calc_name}", str(e)[:200], event="error")
        except Exception:
            pass
        # 예외 시에도 WP 게시물은 건드리지 않은 상태 — _restore_and_fail이 DB만 복원
        return _restore_and_fail("exception", {"error": str(e)[:200]})
