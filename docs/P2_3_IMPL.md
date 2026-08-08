# P2-3 구현 지시서 — 자동 리라이트 파이프라인

작성일: 2026-08-08  
기반 문서: `docs/P2_3_DESIGN.md` (확정 결정사항 반영 완료)  
상태: 구현 승인 대기

---

## 절대 규칙

- **코드 수정 범위**: `modules/rewrite_pipeline.py` (신규) + `main.py` (진입점 추가) + `modules/calculator_pipeline.py` (내부 함수 import 허용 여부 확인 후) + config key 문서화
- **건드리지 않는 것**: `modules/calculator_pipeline._write_article` 내부 로직, `modules/publisher.update_post` 내부 로직, Registry YAML, DB 스키마, WordPress, 계산 로직
- **테스트 없이 WP 실제 발행 금지**: WP 미구성 시 graceful skip (기존 `is_wordpress_ready()` 패턴 그대로 따름)
- 구현 완료 후 검증 스크립트 실행 → 보고. 실패 시 즉시 중단.

---

## 구현 단위 (Phase 순서)

```
Phase A: 공통 유틸 + 상태 파일 (rewrite_processed.json)
Phase B: collect_rewrite_candidates()
Phase C: run_calculator_rewrite()
Phase D: main.py 진입점 + config key
Phase E: 검증
```

---

## Phase A: 공통 유틸 + 상태 파일

### A-1. 신규 파일 생성

**`modules/rewrite_pipeline.py`** 생성.  
이 파일 하나에 모든 리라이트 로직을 넣는다. 다른 기존 파일은 건드리지 않는다.

파일 상단 선언:
```python
# -*- coding: utf-8 -*-
"""
modules/rewrite_pipeline.py — 계산기 블로그 자동 리라이트 파이프라인 (P2-3)

기존 컴포넌트 재사용:
  - modules/calculator_pipeline._write_article (writer)
  - modules/calculator_seo_generator.generate_seo
  - modules/calculator_faq_generator.generate_faq
  - modules/publish_quality.check_publish_quality
  - modules/publisher.update_post
  - repositories/article_repository.ArticleRepository
  - repositories/calculator_repository.CalculatorRepository

신규:
  - collect_rewrite_candidates(cfg): RMS + time-based 후보 수집
  - run_calculator_rewrite(cfg, article_row, calc, reason): 리라이트 실행
  - _load_rewrite_processed(cfg), _mark_processed(cfg, rms_event_id, ...): 이벤트 중복 방지
"""
```

### A-2. 처리 완료 이벤트 파일

경로: `data/legal/rewrite_processed.json`

```python
# 관리 함수 구현 (rewrite_pipeline.py 내부)

def _processed_path(cfg: dict) -> Path:
    root = Path(cfg.get("_root", "."))
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
    """RMS 이벤트 처리 완료 기록. 기존 파일에 append."""
    processed = _load_rewrite_processed(cfg)
    processed[rms_event_id] = {
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "article_id": str(article_id),
        "result": result,   # "success" | "quality_fail" | "wp_api_error" | "skipped"
    }
    _processed_path(cfg).write_text(
        json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

---

## Phase B: `collect_rewrite_candidates()`

### B-1. 함수 시그니처

```python
def collect_rewrite_candidates(cfg: dict) -> list[dict]:
    """RMS + time-based 리라이트 후보 수집. DAILY_REWRITE_LIMIT 적용 후 반환.

    각 항목:
      {article_id, calculator_id, wp_post_id, reason: {...}, severity}
    """
```

### B-2. RMS 후보 수집 (`_rms_candidates`)

```python
def _rms_candidates(cfg: dict, processed: dict) -> list[dict]:
    """revision_state.json 기반 RMS 후보 목록 반환."""
    from .revision_detector import _load_state, _CHANGE_SEVERITY, _SEVERITY_RANK
    from .rms import IMPACT_MAP

    state = _load_state(cfg)               # {entity_id: {last_changed, change_type, ...}}
    art_repo = ArticleRepository(get_db_adapter(cfg))
    rows = art_repo.get_all()

    min_severity = _SEVERITY_RANK.get(
        cfg.get("REWRITE_CHANGE_SEVERITY_MIN", "MEDIUM"), 2
    )

    candidates = []
    for entity_id, st in state.items():
        change_types = st.get("change_type") or []
        last_changed = st.get("last_changed") or ""
        if not last_changed or not change_types:
            continue

        # severity 필터 (wording_changed 제외)
        top_sev = max(
            (_SEVERITY_RANK.get(_CHANGE_SEVERITY.get(c, "LOW"), 1) for c in change_types),
            default=0,
        )
        if top_sev < min_severity:
            continue

        # 중복 실행 방지 — rms_event_id 기반
        rms_event_id = f"{entity_id}__{last_changed}"
        if rms_event_id in processed:
            LOG.debug("[rewrite] RMS 이벤트 이미 처리됨 — SKIP: %s", rms_event_id)
            continue

        # 영향 계산기 slug 목록
        affected_slugs = IMPACT_MAP.get(entity_id, [])
        if not affected_slugs:
            continue

        severity_str = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}.get(top_sev, "LOW")
        reason = {
            "type": "legal_change",
            "source": "RMS",
            "detected_at": datetime.now().isoformat(timespec="seconds"),
            "severity": severity_str,
            "entity_id": entity_id,
            "rms_event_id": rms_event_id,
            "change_type": change_types,
            "last_changed": last_changed,
            "affected_fields": [],   # 구현 단순화: 빈 리스트(필드 수준 추적은 Phase 2 이후)
        }

        for slug in affected_slugs:
            # 발행완료 + wp_post_id 보유 행 조회
            published = [
                r for r in rows
                if str(r.get("상태값", "")).strip() == "발행완료"
                and str(r.get("wp_post_id") or "").strip()
                and str(r.get("calculator_id") or "") == str(slug)  # slug = calculator_id 매핑 필요
            ]
            # 주의: articles.calculator_id는 UUID이고 slug는 문자열. 아래 §B-3 참조.
            for row in published:
                candidates.append({
                    "article_id": str(row.get("ID", "")),
                    "calculator_id": str(row.get("calculator_id", "")),
                    "wp_post_id": str(row.get("wp_post_id", "")),
                    "slug": slug,
                    "reason": reason,
                    "severity_rank": top_sev,
                })

    return candidates
```

### B-3. slug ↔ calculator_id 매핑 주의사항

`articles.calculator_id`는 DB UUID, IMPACT_MAP의 값은 slug 문자열.  
매핑: `CalculatorRepository.get_by_slug(slug)` 또는 `get_all()` 후 slug 필드로 필터.

```python
# _rms_candidates 내부 — slug→calculator_id 변환
calc_repo = CalculatorRepository(get_db_adapter(cfg))
all_calcs = {str(c.get("slug", "")): c for c in calc_repo.get_all() if c.get("slug")}

for slug in affected_slugs:
    calc = all_calcs.get(slug)
    if not calc:
        LOG.debug("[rewrite] slug 미존재 — SKIP: %s", slug)
        continue
    cid = str(calc.get("id", ""))
    published = [
        r for r in rows
        if str(r.get("상태값", "")).strip() == "발행완료"
        and str(r.get("wp_post_id") or "").strip()
        and str(r.get("calculator_id", "")) == cid
    ]
```

### B-4. time-based 후보 수집 (`_time_based_candidates`)

```python
def _time_based_candidates(cfg: dict) -> list[dict]:
    """published_at 기준 REWRITE_STALE_DAYS 경과 후보 목록."""
    from datetime import timedelta
    stale_days = int(cfg.get("REWRITE_STALE_DAYS", 365))
    cooldown_days = int(cfg.get("REWRITE_COOLDOWN_DAYS", 90))
    cutoff = (datetime.now() - timedelta(days=stale_days)).isoformat()

    art_repo = ArticleRepository(get_db_adapter(cfg))
    rows = art_repo.get_all()

    candidates = []
    for row in rows:
        if str(row.get("상태값", "")).strip() != "발행완료":
            continue
        if not str(row.get("wp_post_id") or "").strip():
            continue
        published_at = str(row.get("published_at") or row.get("발행일시") or "")
        if not published_at or published_at > cutoff:
            continue

        # 쿨다운 확인 — history의 최근 rewrite_success.ts 기준
        try:
            hist = json.loads(row.get("history") or "[]")
        except Exception:
            hist = []
        last_rewrite = next(
            (e.get("ts") for e in reversed(hist) if e.get("event") == "rewrite_success"),
            None,
        )
        if last_rewrite:
            last_dt = datetime.fromisoformat(last_rewrite)
            if (datetime.now() - last_dt).days < cooldown_days:
                LOG.debug("[rewrite] time-based 쿨다운 — SKIP: article_id=%s", row.get("ID"))
                continue

        stale = (datetime.now() - datetime.fromisoformat(published_at[:19])).days
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
            "reason": reason,
            "severity_rank": 1,   # LOW
        })

    return candidates
```

### B-5. 통합 + 우선순위 정렬

```python
def collect_rewrite_candidates(cfg: dict) -> list[dict]:
    limit = int(cfg.get("DAILY_REWRITE_LIMIT", 1))
    processed = _load_rewrite_processed(cfg)

    rms = _rms_candidates(cfg, processed)
    timed = _time_based_candidates(cfg)

    # calculator_id 기준 중복 제거 — 동일 계산기에 여러 트리거 존재 시 severity 높은 것 채택
    seen: dict[str, dict] = {}
    for c in sorted(rms + timed, key=lambda x: x["severity_rank"], reverse=True):
        cid = c["calculator_id"]
        if cid not in seen:
            seen[cid] = c

    # "리라이트중" 상태 건 제외
    art_repo = ArticleRepository(get_db_adapter(cfg))
    running = {
        str(r.get("ID", ""))
        for r in art_repo.get_all()
        if str(r.get("상태값", "")).strip() == "리라이트중"
    }
    final = [c for c in seen.values() if c["article_id"] not in running]

    # severity DESC 정렬 후 일일 한도 적용
    final.sort(key=lambda x: x["severity_rank"], reverse=True)
    LOG.info("[rewrite] 후보 %d건 수집 → 한도 %d건 적용", len(final), limit)
    return final[:limit]
```

---

## Phase C: `run_calculator_rewrite()`

### C-1. 함수 시그니처

```python
def run_calculator_rewrite(cfg: dict, article_row: dict, calc: dict, reason: dict) -> dict:
    """단건 리라이트 실행. 반환: {result, article_id, wp_post_id, quality_score, reason_type}

    reason dict 필수 필드: type, source, detected_at, severity
    article_row 필수 필드: ID, wp_post_id, calculator_id, 최종추천제목
    calc 필수 필드: id, name, slug, formula, faq
    """
```

### C-2. 상태 선점 → 생성 → 검증 → 발행 → 결과 기록

```python
def run_calculator_rewrite(cfg: dict, article_row: dict, calc: dict, reason: dict) -> dict:
    from adapters.db.factory import get_db_adapter
    from repositories.article_repository import ArticleRepository
    from .calculator_pipeline import _write_article, _assemble   # 내부 재사용
    from .calculator_seo_generator import generate_seo
    from .calculator_faq_generator import generate_faq
    from . import content_quality, publisher
    from .publish_quality import check_publish_quality
    from .logger import get_logger, BudgetTracker
    from . import telegram_ops as tops

    LOG = get_logger()
    art_repo = ArticleRepository(get_db_adapter(cfg))
    article_id = str(article_row.get("ID", ""))
    wp_post_id = str(article_row.get("wp_post_id", ""))
    cid = str(article_row.get("calculator_id", ""))
    calc_name = calc.get("name", "")

    # 1) 상태 선점 — "리라이트중"
    art_repo.update_status(article_id, "리라이트중",
                           {"rewrite_reason_type": reason.get("type", "")})
    art_repo.append_history(article_id, "rewrite_started", {
        "reason": reason,
        "old_quality_score": article_row.get("quality_score"),
        "ts": datetime.now().isoformat(timespec="seconds"),
    })

    def _restore_and_fail(fail_cause: str, extra: dict = None) -> dict:
        """실패 공통 처리: 상태 복원 + history 기록."""
        art_repo.update_status(article_id, "발행완료", {})
        art_repo.append_history(article_id, "rewrite_failed", {
            "fail_cause": fail_cause,
            "reason_type": reason.get("type"),
            "ts": datetime.now().isoformat(timespec="seconds"),
            **(extra or {}),
        })
        return {"result": "FAILED", "fail_cause": fail_cause,
                "article_id": article_id, "wp_post_id": wp_post_id}

    try:
        # 2) SEO — 기존 keyword(정책명) 유지, title은 새로 생성하나 update_post에서 미전송
        keyword = article_row.get("정책명") or calc_name
        seo = generate_seo(cfg, calc_name, keyword)

        # 3) FAQ — DB 저장본 우선 재사용, 없으면 생성
        faq = []
        if calc.get("faq"):
            try:
                faq = json.loads(calc["faq"]) if isinstance(calc["faq"], str) else calc["faq"]
            except Exception:
                faq = []
        if not faq:
            faq = generate_faq(cfg, calc)

        # 4) Writer — calculator_pipeline._write_article 재사용
        #    failed_rules=None (첫 생성), REWRITE 시 아래 루프에서 주입
        body_html, _ = _write_article(cfg, calc, keyword, seo, faq, failed_rules=None)
        body_html = content_quality.improve_content(body_html)

        # 5) 위젯/내부링크 조립 — _assemble은 calculator_pipeline 내부 클로저.
        #    대신 동일 로직을 직접 구현 (calculator_pipeline과 결합 방지):
        from .app_generator import generate_calculator, render_inline_calculator
        from .internal_link_engine import (generate_related_calculators,
                                           generate_related_articles, inject_internal_links)
        widget_cfg = dict(cfg)
        widget_cfg.update({"SHOW_ARTICLE": False, "SHOW_FAQ": False, "SHOW_RELATED": False,
                           "SHOW_ADSENSE": False, "SHOW_CPA": False, "SHOW_PWA": False})
        widget = render_inline_calculator(generate_calculator(calc, widget_cfg))
        rel_calc = generate_related_calculators(cfg, cid, 3)
        rel_art = generate_related_articles(cfg, keyword, 3)
        link_pool_size = (
            sum(1 for c in rel_calc if c.get("url")) +
            sum(1 for a in rel_art if a.get("title") and a.get("url"))
        )

        CTA_TEXT = "아래 CalcMate 계산기를 이용하면 자동으로 계산할 수 있습니다."
        final_html = f"{body_html}\n<hr/>\n<h2>계산기 사용하기</h2>\n<p>{CTA_TEXT}</p>\n{widget}"
        try:
            final_html = inject_internal_links(final_html, rel_calc, rel_art)
        except Exception as _e:
            LOG.warning("[rewrite] 내부링크 주입 실패(무시): %s", _e)

        # 6) H-4 Quality Gate + 재시도 (기존 MAX_TOTAL_RETRY 준수)
        rcfg = cfg.get("QUALITY_RETRY", {}) or {}
        max_total = int(rcfg.get("MAX_TOTAL_RETRY", 3) or 3)
        qc = check_publish_quality(cfg, body_html, final_html, calc,
                                   link_pool_size=link_pool_size)
        q_retries = 0
        while qc.get("result") == "REWRITE" and q_retries < max_total:
            q_retries += 1
            body_html, _ = _write_article(cfg, calc, keyword, seo, faq,
                                          failed_rules=qc.get("failed_rules"))
            body_html = content_quality.improve_content(body_html)
            final_html = f"{body_html}\n<hr/>\n<h2>계산기 사용하기</h2>\n<p>{CTA_TEXT}</p>\n{widget}"
            try:
                final_html = inject_internal_links(final_html, rel_calc, rel_art)
            except Exception:
                pass
            qc = check_publish_quality(cfg, body_html, final_html, calc,
                                       link_pool_size=link_pool_size)
        final_html = qc.get("html") or final_html  # G6 CTA 수정본

        if qc.get("result") == "REWRITE":
            LOG.warning("[rewrite] H-4 FAIL — 기존 글 유지: %s (calc=%s)", article_id, calc_name)
            return _restore_and_fail("quality_gate_fail",
                                     {"failed_rules": qc.get("failed_rules"),
                                      "retries": q_retries})

        # 7) WP 업데이트 — title=None(기존 title/permalink 유지), content+excerpt만 갱신
        meta_desc = seo.get("seo_description", "")
        pub_result = publisher.update_post(cfg, wp_post_id,
                                           content=final_html,
                                           excerpt=meta_desc)

        if not pub_result.get("success"):
            LOG.warning("[rewrite] WP update 실패: %s", pub_result.get("error"))
            try:
                tops.notify_level(cfg, "WARNING",
                    f"리라이트 WP 실패: {calc_name}",
                    f"wp_post_id={wp_post_id} · error={pub_result.get('error','')[:100]}",
                    event="rewrite_failed")
            except Exception:
                pass
            return _restore_and_fail("wp_api_error", {"error": pub_result.get("error", "")})

        # 8) 성공 — DB 갱신
        new_q_fields = {
            "quality_score": qc.get("score"),
            "quality_status": qc.get("result", ""),
            "quality_reviewed_at": datetime.now().isoformat(),
        }
        art_repo.update_status(article_id, "발행완료", new_q_fields)
        art_repo.append_history(article_id, "rewrite_success", {
            "reason_type": reason.get("type"),
            "reason_source": reason.get("source"),
            "rms_event_id": reason.get("rms_event_id"),
            "new_quality_score": qc.get("score"),
            "wp_post_id": wp_post_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })

        # 9) RMS 이벤트 처리 완료 기록
        if reason.get("type") == "legal_change" and reason.get("rms_event_id"):
            _mark_processed(cfg, reason["rms_event_id"], article_id, "success")

        LOG.info("[rewrite] 완료: %s (calc=%s, score=%s)", article_id, calc_name, qc.get("score"))
        try:
            tops.notify_level(cfg, "INFO",
                f"리라이트 완료: {calc_name}",
                f"reason={reason.get('type')} · score={qc.get('score')} · wp={wp_post_id}",
                event="rewrite_success")
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
        LOG.error("[rewrite] 예외 발생: %s (calc=%s)", e, calc_name, exc_info=True)
        try:
            tops.notify(cfg, f"❌ 리라이트 예외: {calc_name} — {e}")
        except Exception:
            pass
        return _restore_and_fail("exception", {"error": str(e)[:200]})
```

### C-3. `_write_article` import 처리

`calculator_pipeline._write_article`은 module-level 함수이지만 현재 `_`로 시작하는 내부 함수. import 가능 여부 확인 후 두 가지 중 선택:

**방법 A (권장)**: `calculator_pipeline.py`에 다음 한 줄 추가.
```python
# calculator_pipeline.py 하단
def write_article_for_rewrite(cfg, calc, keyword, seo, faq, failed_rules=None, intent=None):
    """rewrite_pipeline이 사용하는 외부 진입점. 내부 _write_article 위임."""
    return _write_article(cfg, calc, keyword, seo, faq, failed_rules, intent)
```
→ `rewrite_pipeline`에서 `from .calculator_pipeline import write_article_for_rewrite`

**방법 B**: `from .calculator_pipeline import _write_article` 직접 import (Python에서 가능하나 관습 위반).

구현 시 A 방법 선택. `calculator_pipeline.py` 하단에 위 래퍼 함수만 추가.

---

## Phase D: 진입점 + config

### D-1. `main.py` 진입점 추가

기존 `main.py` command 처리 블록에 `rewrite` 명령 추가:

```python
elif command == "rewrite":
    from modules.rewrite_pipeline import collect_rewrite_candidates, run_calculator_rewrite
    from repositories.calculator_repository import CalculatorRepository
    from adapters.db.factory import get_db_adapter

    dry_run = "--dry-run" in sys.argv
    only_slug = next((sys.argv[i+1] for i, a in enumerate(sys.argv)
                      if a == "--only-slug" and i+1 < len(sys.argv)), None)

    candidates = collect_rewrite_candidates(cfg)
    if only_slug:
        calc_repo = CalculatorRepository(get_db_adapter(cfg))
        target_calc = next((c for c in calc_repo.get_all()
                            if str(c.get("slug", "")) == only_slug), None)
        if target_calc:
            candidates = [c for c in candidates
                          if c["calculator_id"] == str(target_calc.get("id", ""))]

    print(f"[rewrite] 후보 {len(candidates)}건")
    for c in candidates:
        print(f"  - article_id={c['article_id']} | reason={c['reason']['type']} "
              f"| severity={c['reason']['severity']}")

    if dry_run:
        print("[rewrite] dry-run — 실제 실행 없음")
    else:
        calc_repo = CalculatorRepository(get_db_adapter(cfg))
        art_repo = ArticleRepository(get_db_adapter(cfg))
        for c in candidates:
            article_row = art_repo.get_by_id(c["article_id"])
            calc = calc_repo.get_by_id(c["calculator_id"])
            if not article_row or not calc:
                continue
            result = run_calculator_rewrite(cfg, article_row, calc, c["reason"])
            print(f"[rewrite] {result['result']} — {c['article_id']}")
```

### D-2. config.yaml 신규 키 (문서화)

```yaml
# config.yaml 에 추가할 키 (기본값 포함)
REWRITE_SCHEDULE:
  enabled: true
  daily_check_time: "06:30"

REWRITE_STALE_DAYS: 365          # time-based 기준 (일)
REWRITE_COOLDOWN_DAYS: 90        # time-based 쿨다운 (일)
REWRITE_DAILY_LIMIT: 1           # 일일 리라이트 상한 (건)
REWRITE_CHANGE_SEVERITY_MIN: "MEDIUM"  # RMS 최소 severity (wording_changed 제외)
```

기존 `QUALITY_RETRY.MAX_TOTAL_RETRY`(기본 3)를 리라이트에서도 그대로 준수.

### D-3. 스케줄러 연결 (선택 — Phase E 이후)

`scheduler.py`의 메인 루프에서 daily_check_time 도달 시 `collect_rewrite_candidates` + `run_calculator_rewrite` 호출. 신규 발행 슬롯보다 앞선 시각(06:30)으로 설정해 AI 예산 먼저 소비 후 신규 발행 여부 결정.

---

## Phase E: 검증

### E-1. dry-run 검증

```bash
python main.py rewrite --dry-run
```
- 후보 목록 출력 확인 (0건이어도 오류 없이 종료)
- `data/legal/rewrite_processed.json` 생성/로딩 정상 확인

### E-2. WP 미구성 상태 검증

```bash
# WORDPRESS_URL 미설정 상태에서
python main.py rewrite --only-slug weekly-holiday-allowance
```
- `publisher.update_post()` → `is_wordpress_ready()=False` → `{"success": False, "error": "WordPress 미구성"}` 반환
- `_restore_and_fail("wp_api_error", ...)` 경로 진입
- `articles` 상태값 `"발행완료"` 복원 확인
- `history` 에 `rewrite_failed` 이벤트 기록 확인

### E-3. 후보 없음 검증

- 발행완료 글이 없는 상태에서 `collect_rewrite_candidates(cfg)` → `[]` 반환, 오류 없음

### E-4. 검증 스크립트 생성

`scripts/_verify_rewrite_p23.py` 작성:
```python
"""
P2-3 리라이트 파이프라인 검증:
1. collect_rewrite_candidates() 호출 — 오류 없음 확인
2. _load_rewrite_processed() 로딩 확인
3. reason 필수 필드 존재 확인 (type/source/detected_at/severity)
4. 후보 0건이어도 정상 반환 확인
"""
```

---

## 구현 체크리스트

```
[ ] A-1: modules/rewrite_pipeline.py 파일 생성
[ ] A-2: _processed_path, _load_rewrite_processed, _mark_processed 구현
[ ] B-1~B-5: collect_rewrite_candidates 구현 (RMS + time-based + 통합)
[ ] C-1~C-3: run_calculator_rewrite 구현
[ ] C-3: calculator_pipeline.py 하단에 write_article_for_rewrite 래퍼 추가 (1줄)
[ ] D-1: main.py rewrite 명령 추가
[ ] D-2: config.yaml 신규 키 기본값 주석 추가
[ ] E-1: dry-run 검증
[ ] E-2: WP 미구성 검증
[ ] E-3: 후보 없음 검증
[ ] E-4: scripts/_verify_rewrite_p23.py 작성 + 실행
```

---

## 구현 범위 외 (이 지시서에 포함 안 됨)

- 스케줄러 자동 실행 연결 (Phase E 완료 후 별도 지시)
- `articles` 테이블 컬럼 추가 (`rewrite_count` 등) — 현재 `history` JSON으로 충분
- RMS 이벤트 push 방식 (인프라 없음, 폴링으로 대체됨)
- `affected_fields` 세분화 (빈 리스트로 구현 후 Phase 2에서 보강)

---

*기반 커밋: a04d697 (v2.0.0-registry)*
