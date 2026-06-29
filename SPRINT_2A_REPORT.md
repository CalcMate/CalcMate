# SPRINT 2A v2 — Audit & Document 보고서

> 작업일 2026-06-29 · 모드: **읽기 전용**(코드/설정 무변경) · 기준 커밋 `885b04c`
> 본 파일은 운영자 요청으로 저장됨(SPRINT 2A 원칙상 보고서 출력만이나, 운영자 승인하에 파일화).

**감사 범위 확인:** Python 86개(.venv 제외) · 삭제 확인 완료 — `dashboard_ui_refactor.py`, `scripts/run_schedule.bat`, `scripts/run_dashboard_new.bat` 모두 부재(분석 제외). 8그룹 2단 네비(`dashboard.py:124` `NAV_GROUPS`) 실재 확인.

---

## ① 프로젝트 구조 — 문서 수정 필요 항목

4개 문서 모두 헤더 날짜 **2026-06-23** 으로, v12 Lite 마이그레이션(2026-06-27, 커밋 `6155846`·`0c69167`) **이전** 기준이다. `README.md`만 커밋 `f45165f`에서 부분 갱신되어 거의 현행, 나머지 3개는 stale.

### [README.md] — 경미 (대체로 현행)
- **현재 내용:** 헤더 `작성: 2026-06-23. (Python 81개 파일)`, `현재 버전: v12`
- **수정 필요:** 날짜→2026-06-27, 파일수 81→86, 버전 라벨에 **v12 Lite** 명시
- **사유:** Lite에서 5개 모듈(ai_assistant/cost_manager/retry_queue/image_fallback/telegram_ops) 추가로 파일 수 증가. 본문(8그룹/AI Assistant/Cost/Retry)은 이미 정확.

### [ARCHITECTURE.md] — stale (수정 필요 큼)
- **현재 내용 → 수정 필요:**
  - `dashboard.py(Streamlit 17탭 …)` → **8그룹 2단 네비**
  - UI Layer의 `dashboard_ui_refactor.py(SaaS 전용 미러)` 줄 → **삭제됨, 행 제거**
  - Business Layer 모듈 맵에 **ai_assistant · cost_manager · retry_queue · image_fallback · telegram_ops 누락** → 추가
  - 4.스케줄러 흐름: 예산 소진 시 `cost_manager` 일시정지 호출 누락 → 1줄 보강
- **사유:** 17탭/미러 UI는 Lite 통합·삭제로 폐기. 운영 자동화 5종 미반영.

### [FILE_STRUCTURE.md] — stale (수정 필요 가장 큼)
- **현재 내용 → 수정 필요:**
  - 트리·표의 `dashboard_ui_refactor.py`, `scripts/run_schedule`, `scripts/run_dashboard_new` (3건) → **모두 삭제됨, 행 제거**
  - `dashboard.py … 17탭` → **8그룹**
  - modules 표에 **신규 5파일 누락**: ai_assistant.py / cost_manager.py / retry_queue.py / image_fallback.py / telegram_ops.py → 추가
  - `Python 81개` → 86
- **사유:** 삭제 파일을 여전히 나열 → 신규 운영자 오인 위험.

### [ROADMAP.md] — stale (중간)
- **현재 내용 → 수정 필요:**
  - `Streamlit 17탭` → **8그룹**
  - 설정 항목 `발행방식(예약/Legacy)` → **Legacy 제거, 예약발행 단일화**
  - 운영/대시보드 ✅완료 목록에 **Cost Manager / Retry Queue / Image Fallback / Telegram 고도화 / AI Assistant 누락** → 완료로 추가
- **사유:** Lite에서 추가된 운영 자동화가 로드맵 완료란에 미기재. (P1 전부 ✅, AUTO_TOPIC_EXPANSION 미구현은 config 대조 결과 정확 — 유지)

---

## ② Prompt Catalog (작업 3)

| ID | 파일 | 변수명/위치 | 담당 AI역할 | 입력 변수 | 출력 | 모델 | 중복 |
|----|------|------------|------------|----------|------|------|------|
| P01 | writer.py | `SYSTEM_M3_POLICY` | Writer/M3(정책) | clean_*, seo_title, outline, faq… | HTML | gpt-4o-mini(config) | ⚠ |
| P02 | writer.py | `SYSTEM_M3_CALCULATOR` | Writer/M3(계산기) | 동일 | HTML | config | ⚠ |
| P03 | editor.py | `SYSTEM_M4_PRE` | Editor/M4(애드센스前) | draft_html | HTML | claude-sonnet-4-6 | ⚠ |
| P04 | editor.py | `SYSTEM_M4_POST` | Editor/M4(後) | draft_html | HTML | config | ⚠ |
| P05 | planner.py | `SYSTEM_M1` | Planner/M1 | clean_*, recent_titles | JSON | gemini-2.5-flash | 없음 |
| P06 | strategist.py | `SYSTEM_M0` | Orchestrator/M0 | clean_*, score, weights | JSON(7점수) | gpt-4o | ⚠ |
| P07 | strategist_calculator.py | `score_keyword().system` | 계산기 키워드 점수 | keyword, calculator_name | JSON(7항목) | gpt-4o | ⚠ |
| P08 | cleaner.py | `SYSTEM_CLEANER` | Cleaner/STEP2 | item.* | JSON(8필드) | gpt-4o | 없음 |
| P09 | duplicate_checker.py | `JUDGE_SYSTEM` | 중복 AI judge | similarity, doc_a/b | JSON | gpt-4o | 없음 |
| P10 | strategy_room.py | `SYSTEM_STRATEGY` | Strategy Room | recent_posts, ctr… | JSON | gpt-4o | 없음 |
| P11 | calculator_prompt_manager.py | `QUALITY`(공통주입) | 공통 품질규칙 | — | 텍스트조각 | n/a | ⚠ |
| P12 | calculator_prompt_manager.py | `get_seo_prompt()` | 계산기 SEO | name, formula, schema | JSON | config | ⚠ |
| P13 | calculator_prompt_manager.py | `get_faq_prompt()` | 계산기 FAQ | _ctx, n_min/max | JSON | config | ⚠ |
| P14 | calculator_prompt_manager.py | `get_article_prompt()` | 계산기 본문 | _ctx, seo, faq | HTML | config | ⚠ |
| P15 | calculator_prompt_manager.py | `get_cta_prompt()` | 계산기 CTA | _ctx | 텍스트 | config | 없음 |
| P16 | calculator_prompt_manager.py | `get_image_prompt()` | 계산기 이미지 | _ctx | JSON | config | ⚠ |
| P17 | calculator_seo_generator.py | `generate_seo()` 인라인 | 계산기 SEO(별도) | name, keyword, year | JSON | gpt-4o | ⚠ |
| P18 | calculator_content_generator.py | `generate_article()` 인라인검수 | 계산기 본문검수 | html | HTML | config | ⚠ |
| P19 | calculator_reviewer.py | `review_calculator().system` | 계산기 Reviewer | name, faq, formula, article | JSON(6항목) | gpt-4o(config) | ⚠ |
| P20 | calculator_form_engine.py | 인라인 system(l.63) | 입력폼 설계 | name, TYPES | JSON | config | 없음 |
| P21 | app_factory.py | `sys1` | App Factory 스펙 | name, category, desc | JSON | gpt-4o | 없음 |
| P22 | app_factory.py | `sys2` | App Factory 코드 | schema, formula | HTML | claude-sonnet-4-6 | 없음 |
| P23 | app_factory.py | `sys3` | App Factory 작성 | name, category | JSON | gpt-4o | ⚠ |
| P24 | app_factory.py | `sys4` | App Factory 이미지 | name, category | JSON | gemini-2.5-flash | ⚠ |
| P25 | prompts/calculator_writer_prompt.txt | 파일(`_load_prompt`) | 계산기 Pipeline Writer | name, seo, faq, CTA | HTML | gpt-4o | ⚠ |
| P26 | calculator_pipeline.py | `_load_prompt()` fallback | 계산기 Writer(fallback) | 동 P25 | HTML | gpt-4o | ⚠ |
| P27 | ai_workspace.py | `chat().system` | AI Workspace | context, messages | 텍스트 | 가변 | ⚠ |
| P28 | ai_assistant.py | `chat().system` | AI Assistant | ctx, messages | 텍스트 | gpt-4o/claude/gemini | ⚠ |

### 중복 의심 그룹
- **본문 작성기 (P01·P02·P14·P18·P25·P26):** 동일 페르소나("10년차 SEO 에디터")+`[BODY_HTML_START]…[END]` 래핑+유사 H2 구조. 계산기 본문이 PM/txt파일/fallback **3중 정의**.
- **계산기 SEO (P12·P17):** 거의 동일 프롬프트가 prompt_manager와 seo_generator에 **이중 정의**.
- **이미지 프롬프트 (P16·P24):** 동일 목적·동일 JSON 스키마가 PM·app_factory 양쪽.
- **0~100 채점 JSON (P06·P07·P19·P23):** 채점 스캐폴딩 사실상 동일.
- **대시보드 챗 (P27·P28):** ai_workspace와 ai_assistant가 같은 역할 시스템 프롬프트 중복.
- **공통 QUALITY(P11):** 단일 출처지만 P12~P16·P18·P19에 동일 문구 반복 주입.

---

## ③ Python Header / Docstring 누락 목록 (작업 2)

**Header**: 거의 전 파일 모듈 헤더 보유(양호). 부분/없음만 별도 표시. **Docstring 누락**은 공개(`_`없는) 함수 기준.

| 파일 | Header | Docstring 누락 공개함수 |
|------|--------|------------------------|
| main.py | 있음 | parse_args, main |
| dashboard.py | 있음 | load_css, load_cfg, cached_posts, cached_table, render_header, render_kpi_cards, render_pipeline_status, render_quick_actions, render_recent_activity, render_dashboard_home, render_model_selector |
| dashboard_backup.py | 있음 | load_cfg, render_model_selector |
| dashboard_backup_ui.py | 있음 | load_css, load_cfg, cached_posts, cached_table, render_model_selector |
| health_check.py | 있음 | run, critical_passed |
| modules/cleaner.py | 있음 | clean_rss_item |
| modules/strategist_calculator.py | 있음 | score_keyword |
| modules/image_generator.py | **부분** | generate |
| modules/history_loader.py | **부분** | load_recent_titles |
| modules/rss_collector.py | **부분** | collect |
| modules/collector/factory.py | 있음 | register, get_collector |
| modules/collector/{policy,calculator,finance,affiliate}.py | 있음 | collect (각) |
| modules/app_generator.py | 있음 | generate_js, generate_css, generate_html |
| modules/calculator_seo_generator.py | 있음 | generate_seo |
| modules/calculator_image_prompt_generator.py | 있음 | generate_thumbnail_prompt, generate_body_prompt |
| modules/calculator_prompt_manager.py | 있음 | get_seo_prompt, get_faq_prompt, get_article_prompt, get_cta_prompt, get_image_prompt |
| modules/calculator_seed.py | 있음 | seed_templates, seed_calculators, seed_all |
| modules/github_deployer.py | 있음 | is_configured |
| modules/site_mode_manager.py | 있음 | get_mode, is_ads_enabled, is_cpa_enabled, is_share_enabled, is_report_enabled, is_related_enabled, all_flags |
| modules/ai_provider.py | 있음 | chat, build_provider, retry_call |
| modules/ai_assistant.py | 있음 | list_directory, read_file, load_memory, save_memory, load_tasks, add_task, set_task_status, analyze_project, chat |
| modules/ai_workspace.py | 있음 | list_project_files, read_project_file, write_workspace_file, analyze_structure, query_repo |
| modules/cost_manager.py | 있음 | status |
| modules/retry_queue.py | 있음 | list_pending, remove |
| modules/telegram_ops.py | 있음 | notify_error, notify_budget, notify_publish_request, notify |
| modules/telegram_notifier.py | **부분** | send |
| modules/logger.py | 있음 | get_logger, check_budget, get_daily_cost, get_monthly_cost, get_total_cost, get_provider_today, get_provider_month |
| modules/config_loader.py | 있음 | load_config |
| modules/sheet_sync.py | 있음 | read_test, get_recent_titles, append_row, append_log, get_all_posts, update_status |
| modules/db_manager.py | 있음 | get_all_rows, get_pending_rows, get_top_pending, get_recent_published_titles, get_row_by_id, save_post_data, update_post_status, add_row_if_not_exists, increment_fail_count, read_test |
| modules/site_manager.py | 있음 | get_active_sites, get_by_id, get_wp_config, get_ai_config, register_site, update_status |
| modules/scheduler.py | 있음 | failure_mode, load_schedule, save_schedule |
| modules/strategy_room.py | **부분** | run_strategy_room |
| modules/setup_wizard.py | 있음 | config_exists, save_config, save_secrets, save_credentials, render_wizard |
| modules/site_wizard.py | 있음 | list_sites, list_calculators, create_calculator, set_site_status, update_site, delete_site, delete_calculator |
| modules/pipeline_status.py | 있음 | get_pipeline_state |
| adapters/db/factory.py | 있음 | get_db_adapter |
| adapters/db/{sheets,sqlite,postgres}_adapter.py | 있음 | get_all, get_where, insert, update, delete, read_test (각) |
| adapters/storage/factory.py | 있음 | get_storage_adapter |
| adapters/storage/{drive,local,s3}_adapter.py | 있음 | save_file, load_file, delete_file, backup_file, read_test (각) |
| repositories/article_repository.py | 있음 | get_all, get_pending, get_top_pending, get_recent_published_titles, get_by_id, save, update_status, upsert_by_policy_name, increment_fail |
| repositories/site_repository.py | 있음 | get_active_sites, get_by_id, get_by_type, get_all, get_wp_config, get_ai_config, save, update_status, update, delete, save_wp_profile |
| repositories/calculator_repository.py | **부분** | get_all, get_active, get_by_site, get_by_id, save, create, update, delete, publish |
| repositories/template_repository.py | 있음 | get_all, get_active, get_by_type, get_by_id, save, update |
| scripts/repair_google_setup.py | 있음 | repair |

> **Docstring 누락 없음(공개함수 전부 보유):** duplicate_checker, strategist, planner, writer, editor, publisher, collector/base, formula_engine, calculator_form_engine, calculator_template_engine, app_factory, calculator_reviewer, calculator_faq_generator, calculator_content_generator, calculator_pipeline, calculator_seeder, internal_link_engine, ai_roles, image_fallback, json_utils, utils/parser, backup_manager, google_provisioner, dashboard_cache, adapters/db/base, adapters/storage/base.
> **패턴:** Adapter/Repository CRUD 메서드와 dashboard `render_*`, ai_assistant/ai_workspace 도구 함수에 docstring 집중 누락. 가장 우선순위 높은 6파일 중 **dashboard.py가 누락 11건으로 최다**.

---

## ④ 프로젝트 건강도 점수표 (작업 11)

| 영역 | 점수 | 근거 |
|------|------|------|
| 구조 (계층 분리, 의존성 방향) | **85** | 명확한 5계층 + Adapter/Repository + `ai_provider` 단일화, Feature Freeze로 코어 보존. 감점: dashboard_backup*.py 2개 잔존, Calculator Builder·site_wizard 계산기 함수 dead code 잔존 |
| Dashboard (운영자 가시성, UX) | **82** | 8그룹 2단 네비, KPI4·Cost·Retry·Health·AI Assistant 통합. 감점: dashboard.py 단일 거대 파일, render_* docstring 전무, AI 호출 블로킹(roadmap P3) |
| AI 통합 (모델 배정, 비용 가시성) | **80** | config 중앙 모델 배정 + AI_ROLES + BudgetTracker 모델별 누적 + cost_manager 자동 정지/재개. 감점: 입출력 토큰 미분리(P3), 파이프라인 GPT 제외 목표 미적용(MIGRATION_NOTES §4) |
| Prompt 품질 (일관성, 중복, 관리) | **62** | calculator_prompt_manager로 일부 중앙화·QUALITY 공통규칙 존재. 감점: 본문/SEO/이미지/챗 프롬프트 6개 중복군(②), 파이프라인 프롬프트는 모듈별 산재 — 단일 레지스트리 부재 |
| 코드 품질 (표준화, 문서화) | **70** | 모듈 헤더 거의 전부 보유(강점). 감점: 공개함수 docstring 다수 누락(③ ~70여 함수), 백업 .py 커밋, 일부 헤더 '부분' |
| 유지보수성 (변경 용이성, 테스트) | **60** | Adapter 교체·Repository 브릿지로 변경 격리 우수. 감점: **pytest 정식 테스트 스위트 부재**(P3), dashboard 모놀리식, 프롬프트 중복으로 수정 분산 |
| 확장성 (Adapter 패턴, stub 전환 가능성) | **85** | factory+추상 base로 postgres/s3/finance/affiliate stub이 동일 인터페이스로 즉시 교체 가능. Site Mode·다중 플랫폼 구조 양호 |
| 문서 (정확성, 현행화) | **62** | README 현행·근거 기반 작성 원칙 양호. 감점: ARCHITECTURE/FILE_STRUCTURE/ROADMAP 3종 stale(17탭·삭제파일), 보고서성 .md 19개 난립(중복 정보) |
| **총점 평균** | **73.3** | 구조·확장성 강점, 프롬프트 중복·테스트 부재·문서 현행화가 하향 요인 |

---

## ⑤ 즉시 수정 가능한 사항 (코드 미변경 — 설정/문서 수준)

1. **🔴 보안 (최우선):** `config/config.yaml`에 OpenAI·Claude·Gemini **API 키 + WordPress 비밀번호가 평문**으로 존재하며 **git 추적 대상**(현재 `M config/config.yaml`). → 키는 `secrets.yaml`로 분리하고 `config.yaml`·`secrets.yaml`을 `.gitignore`에 추가, 노출된 3개 키는 **즉시 폐기·재발급** 권장. *(SPRINT 2A 금지조항 준수를 위해 본 감사에서는 수정/커밋하지 않음)*
2. **문서 현행화 (①):** ARCHITECTURE/FILE_STRUCTURE/ROADMAP의 17탭·삭제파일·신규 5모듈 반영. 텍스트 수정만으로 완료.
3. **`git status` 미커밋분:** `config.yaml`·`budget.json`·`health_last.json` 변경 + `data/workspace/` untracked. SPRINT 전제(현재 상태 커밋)는 **운영자가 시크릿 처리 후 직접 커밋** 권장(①의 보안 이슈 때문에 자동 커밋 보류).
4. **문서 정리:** 보고서성 .md 19개 중 README_CURRENT/SYSTEM_AUDIT/UI_REPORT/PERFORMANCE_REPORT 등 중복·구버전 통폐합(정보 단일화).

## ⑥ 절대 건드리면 안 되는 핵심 구조

- **12단계 파이프라인**: `main.run_once` / `_process_one` STEP 순서·데이터 흐름 (Feature Freeze 대상, RSS dry-run 회귀 확인됨)
- **AI 추상화 계층**: `ai_provider`(역할 라우팅+retry) 단일 진입점 — 모델 배정의 단일 출처
- **Adapter/Repository 경계**: `db.factory`/`storage.factory` + 4개 Repository 브릿지(`sheet_sync`/`db_manager`/`site_manager`) — gspread/Drive 직접호출 캡슐화 지점
- **계산기 자동 품질 루프**: `calculator_content_generator.auto_generate_all` → `calculator_reviewer.auto_review_and_fix`(PASS/REWRITE ×2 재생성) 연결
- **Graceful Degradation**: WP 미구축/시트403/AI429 무크래시 대기·폴백 처리
- **BudgetTracker → cost_manager**: 모델별 비용 누적 + 예산 80%경고/100%정지/익일재개 (스케줄러 루프 연동)

---

> ✅ **SPRINT 2A 완료. 코드/설정 무변경.** 운영자 검토·승인 후 SPRINT 2B 시작 권장.
> 가장 시급한 후속: **⑤-1 시크릿 분리/재발급** → **②의 본문 프롬프트 3중 중복 통합** → **테스트 스위트 도입**.
