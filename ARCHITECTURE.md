# ARCHITECTURE.md — 블로그자동화 v12 / SalaryMate 구조

> 실제 소스 코드 기준(2026-06-29, v12 Lite + SPRINT 2A/2B 반영). 5계층 + 데이터 흐름.

---

## 1. 계층 구조 (5 Layer)

```
┌──────────────────────────────────────────────────────────────────┐
│ UI Layer       dashboard.py(Streamlit 8그룹 2단 네비, 다크 SaaS, render_*)│
│                setup_wizard(초기 설정 마법사)                        │
│                assets/css/dashboard.css · scripts/*.bat              │
├──────────────────────────────────────────────────────────────────┤
│ Business Layer main.py(run_once/_process_one: 12단계)               │
│   파이프라인   cleaner·strategist·planner·writer·editor·duplicate_   │
│               checker·image_generator·publisher·history_loader      │
│   수집기       collector/{policy,calculator,finance,affiliate,factory}│
│               + rss_collector                                       │
│   계산기엔진   formula_engine·calculator_form_engine·app_generator·  │
│               calculator_template_engine·calculator_reviewer·       │
│               calculator_{seo,faq,content,image_prompt}_generator·  │
│               calculator_prompt_manager·calculator_pipeline·        │
│               calculator_seed(er)·app_factory·github_deployer·      │
│               internal_link_engine·site_mode_manager                │
│   운영/확장   scheduler·backup_manager·strategy_room·site_wizard·    │
│               ai_workspace·pipeline_status·dashboard_cache·          │
│               ai_assistant·cost_manager·retry_queue·image_fallback· │
│               telegram_ops·telegram_notifier                        │
│   AI/공통     ai_provider·ai_roles·logger(BudgetTracker)·            │
│               config_loader(config.yaml+secrets.yaml 병합)·         │
│               utils/parser(+json_utils shim)                        │
├──────────────────────────────────────────────────────────────────┤
│ Repository     repositories/{article,site,calculator,template}_repo  │
│                + 브릿지 sheet_sync·db_manager·site_manager           │
├──────────────────────────────────────────────────────────────────┤
│ Adapter        db/{sheets,sqlite,postgres*}  storage/{drive,local,s3*}│
│                (factory가 config로 선택)   *=stub                    │
├──────────────────────────────────────────────────────────────────┤
│ External       OpenAI·Anthropic·Google GenAI(Gemini)·Pollinations·  │
│                WordPress REST·Google Sheets·Google Drive·GitHub API  │
└──────────────────────────────────────────────────────────────────┘
```

### 계층 책임
- **UI**: 운영자 조작/모니터링. 데이터는 Repository/Adapter 또는 로컬 파일(budget.json/health_last.json/today_schedule.json/dashboard_cache.db)로 접근.
- **Business**: 비즈니스 로직. `run_once`가 수집→12단계 오케스트레이션. 계산기 엔진은 별도 경로. AI 호출은 `ai_provider`로 단일화.
- **Repository**: 도메인 CRUD. 브릿지(`sheet_sync` 등)가 기존 호출부 보존.
- **Adapter**: 저장소 교체 지점. `DB_ADAPTER`/`STORAGE_ADAPTER`로 sheets↔sqlite, drive↔local 무중단 전환. gspread/Drive 직접 호출은 어댑터 내부에 캡슐화.
- **External**: 실제 외부 API.
- **보안(SPRINT 2B PRE-01)**: API키/앱비밀번호/봇토큰은 `config/secrets.yaml`(gitignore)에 분리. `config_loader.merge_secrets`가 런타임에 `config.yaml`과 병합(secrets 우선) → 기존 flat 키(`cfg["OPENAI_API_KEY"]` 등) 그대로 사용.

---

## 2. 메인 파이프라인 흐름 (RSS/정책)

```
Dashboard / .bat / Scheduler
        │
        ▼
main.run_once(cfg, max_count=N)   ─ 예산 선차단 → 수집 → 목표만큼 _process_one 루프
        ▼
SiteManager.get_active_sites() ─▶ collector.factory.get_collector(site_type)
        │ (사이트 없으면)              ├ policy(feedparser) ├ calculator(DB) ├ finance/affiliate(stub) └ custom→policy
        ▼ rss_collector.collect()
_process_one(item):
  STEP2 cleaner ▶ STEP3 dup_checker ▶ STEP5 strategist ▶ STEP6 planner
  ▶ STEP7 writer ▶ STEP8 editor ▶ STEP9 파싱 ▶ STEP10 image_generator
  ▶ STEP11 publisher ▶ STEP12 기록
        │              │                   │              │
     ai_provider   ai_provider         storage.factory  sheet_sync→ArticleRepository
     (OpenAI/Claude/Gemini)           →drive_adapter   →db.factory→sheets/sqlite
        │
     logger.BudgetTracker (모델별 비용 → data/logs/budget.json)
        ▼
   WordPress REST — 미구축 시 '검수대기' graceful skip
```

## 3. 계산기 플랫폼 흐름

```
계산기 등록 (seed/Builder/App Factory)
   │
   ├─ calculator_form_engine        입력폼 스키마(라이브러리 우선→AI)
   ├─ formula_engine                안전 수식 실행(AST, eval 금지)
   ▼
calculator_content_generator.auto_generate_all()
   SEO(seo_generator) → FAQ(faq_generator) → 본문(content_generator) → 이미지프롬프트
   ▼
calculator_reviewer.auto_review_and_fix()   ─ 검수(≥80 PASS/<80 REWRITE)
   │   REWRITE면 SEO/FAQ/본문 자동 재생성 ×최대2 → 재채점
   ▼  상태: AUTO_APPROVED / AUTO_REWRITTEN / NEEDS_REVIEW
CalculatorRepository.update_generated()  → calculators(시트/sqlite)
   ▼
app_generator.generate_calculator()  ─ calculator_v1.html + Form Engine + Site Mode
   → index.html/style.css/script.js
   ▼
github_deployer.deploy_app()  → GitHub Pages URL (토큰 시)
```
Site Mode(`site_mode_manager`): pre_adsense(전부 숨김)/post_adsense(광고·관련)/growth(전부) → 템플릿 렌더 시 광고/관련/공유/리포트 노출 제어.

## 4. 스케줄러 흐름

```
run_scheduler_loop (--scheduler)
   ▼ 폴링
ensure_today_schedule ─ 날짜 변경 시 generate_today_schedule
   (PUBLISH_SCHEDULE 평일/주말 슬롯 → 랜덤 예약시각) → today_schedule.json(영속)
   ▼
get_due_posts(now) ─▶ execute_due_post ─▶ run_once(max_count=1)
   상태 전이(pending→running→completed/failed/retry) + history.jsonl
   실패모드: none / retry_in_slot / next_slot
```

## 5. 대시보드 ↔ 백엔드 (읽기/트리거)

```
🏠 운영센터  render_dashboard_home(): header/KPI4/pipeline/quick·activity
            KPI=scheduler.summarize·BudgetTracker·repositories(2단 캐시)
            상태=health_last.json, 로그=pipeline.log tail
🧮 계산기 관리 app_generator·github_deployer·formula_engine·reviewer·seeder
🏭 App Factory app_factory(GPT→Claude→GPT→Gemini)→Calculator/TemplateRepository
💬 AI Workspace ai_workspace(ai_roles 채팅+파일/Repository 조회)
📊 AI Pipeline pipeline_status(pipeline.log 파싱)
2단 캐시: cached_posts/cached_table → dashboard_cache(SQLite 미러, 라이브 폴백)
```

---

## 6. 설계 원칙
- **Adapter→Repository 강제**: 데이터 접근은 Repository 경유. gspread/Drive 직접 호출은 어댑터 내부에만.
- **Graceful Degradation**: WP 미구축 / 시트 403 / AI 쿼터(429)에서 크래시 없이 대기·폴백·로깅.
- **확장-우선, 코어 보존**: 12단계 `run_once` 유지, 계산기/운영 기능은 별도 모듈·탭으로 확장.
- **AI 자동 품질**: 계산기 생성물은 Reviewer가 자동 검수·수정(사용자 승인 단계 없음).
- **비용 가시성**: 모든 AI 호출 BudgetTracker로 모델별 누적.
