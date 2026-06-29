# FILE_STRUCTURE.md — 파일 구조 및 역할

> 실제 소스 코드 기준(2026-06-29, v12 Lite + SPRINT 2A/2B 반영). 상태: ✅완료 · 🟡부분 · ❌stub.

```
블로그자동_v12/
├─ main.py                  12단계 파이프라인 진입점(플래그 8종)
├─ dashboard.py             Streamlit 운영센터 8그룹 2단 네비(다크 SaaS, render_* 홈)
├─ health_check.py          ★실사용 헬스체크(OpenAI/Claude/Gemini/Sheet/Drive/WP/SA)
├─ requirements.txt / credentials.json / .gitignore
├─ assets/css/dashboard.css 다크/글래스 테마
├─ config/                  config.yaml(일반설정) · secrets.yaml(민감정보,gitignore) ·
│                           secrets.example.yaml · score_weights.yaml · site_mode.yaml
├─ prompts/calculator_writer_prompt.txt
├─ templates/
│   ├─ calculators/calculator_v1.html   계산기 공통 UI({{변수}} 치환)
│   └─ library/*.json (retirement/annual_leave/weekly_allowance/unemployment/insurance) 골드 템플릿
├─ modules/  (아래 표)
├─ repositories/  article·site·calculator·template _repository
├─ adapters/  db/{sheets,sqlite,postgres*} · storage/{drive,local,s3*}
├─ scripts/  install·run_pipeline·run_scheduler·run_dryrun·
│            run_strategy_room·run_dashboard·sync_cache(.bat)·repair_google_setup.py
├─ data/  logs(pipeline.log,budget.json,health_last.json) · outputs · schedule · cache · assistant(memory/tasks/backups)
└─ (문서) README·ARCHITECTURE·FILE_STRUCTURE·ROADMAP·MIGRATION_NOTES·CHANGELOG_AI·STABILITY_REPORT·
          TODO_NEXT·CALCULATOR_*·SPRINT_2A_REPORT·SPRINT_2B_REPORT·
          AI_ASSISTANT_ANALYSIS·TELEGRAM_BIDIRECTIONAL_DESIGN
```

## 루트
| 파일 | 역할 | 의존 |
|------|------|------|
| `main.py` | `parse_args`(--once/--schedule/--scheduler/--dry-run/--strategy-room/--calculator/--seed-calculators/--instance), `run_once`+`_process_one`(12단계) | 전 파이프라인 모듈, scheduler/calculator_pipeline(지연), health_check |
| `dashboard.py` | 운영센터 8그룹 2단 네비 + render_* SaaS 홈(현재Site카드/5KPI/Workflow/진행현황) + Site Manager/Wizard/Settings + 2단 캐시 + CSS 주입 | scheduler/site_wizard/app_*/ai_*/calculator_*/repositories/BudgetTracker/config_loader/main(지연) |
| `health_check.py` | 6서비스+서비스계정 점검 → health_last.json | openai/anthropic/google.genai/googleapiclient |

## modules/ — 파이프라인 단계
| 파일 | 역할 | 상태 |
|------|------|------|
| `cleaner.py` | STEP2 정제 + STEP9 파싱 | ✅ |
| `duplicate_checker.py` | STEP3 임베딩+코사인+AI judge | ✅ |
| `strategist.py` | STEP5 M0 전략 + M2 점수(키 정규화) | ✅ |
| `planner.py` | STEP6 SEO 기획(M1) | ✅ |
| `writer.py` | STEP7 본문(source_type별) | ✅ |
| `editor.py` | STEP8 검수(+GPT fallback) | ✅ |
| `image_generator.py` | STEP10 Pollinations→Drive | ✅ |
| `publisher.py` | STEP11 WordPress REST(미구축 대기) | 🟡 |
| `history_loader.py` | STEP4 최근 제목 | ✅ |

## modules/collector/
| 파일 | 역할 | 상태 |
|------|------|------|
| `base.py`·`factory.py` | 추상 + source_type 라우팅 | ✅ |
| `policy.py` | RSS 수집(feedparser) | ✅ |
| `calculator.py` | calculators DB→키워드 | ✅ |
| `finance.py`·`affiliate.py` | `return []` | ❌ stub |
| (상위)`rss_collector.py` | 레거시 RSS fallback | ✅ |

## modules/ — 계산기 엔진(SalaryMate)
| 파일 | 역할 | 상태 |
|------|------|------|
| `formula_engine.py` | 안전 수식 실행(AST, eval 금지)·검증·load/save | ✅ |
| `calculator_form_engine.py` | 입력폼 스키마/HTML(라이브러리 우선→AI), 7타입 | ✅ |
| `app_generator.py` | calculator_v1.html+Form+SiteMode→index/style/script | ✅ |
| `calculator_template_engine.py` | 스키마→단일 위젯 HTML(결정적) | ✅ |
| `calculator_reviewer.py` | review_calculator/approve/reject + `auto_review_and_fix`(검수·자동수정 루프) | ✅ |
| `calculator_seo_generator.py` | SEO(generate_seo/seo_title/meta_description) | ✅ |
| `calculator_faq_generator.py` | FAQ(question/answer 5~10) | ✅ |
| `calculator_content_generator.py` | 본문 generate_article + `auto_generate_all`(생성→**Reviewer 연결**→저장) | ✅ |
| `calculator_image_prompt_generator.py` | 썸네일/본문 프롬프트(Gemini→Writer) | ✅ |
| `calculator_prompt_manager.py` | 프롬프트 중앙관리+품질규칙 | ✅ |
| `calculator_pipeline.py` | 계산기→키워드→SEO/FAQ→본문+위젯+CTA+내부링크→발행 | ✅ |
| `calculator_seed.py`·`calculator_seeder.py` | 초기 5종 + 템플릿 시드(수식 포함) | ✅ |
| `app_factory.py` | 자동 계산기 생성(GPT→Claude→GPT→Gemini) | ✅ |
| `github_deployer.py` | GitHub Pages 배포(create_repo/deploy_app/get_deploy_url) | 🟡 토큰 필요 |
| `internal_link_engine.py` | 관련 계산기/글/CTA/inject | ✅ |
| `site_mode_manager.py` | pre/post/growth 모드 노출 플래그 | ✅ |

## modules/ — AI/공통/운영
| 파일 | 역할 |
|------|------|
| `ai_provider.py` | OpenAI/Claude/Gemini 추상화 + 역할 라우팅 + retry |
| `ai_roles.py` | 확장기능 역할표(총괄/리서치/코드/작성/검수/이미지) |
| `logger.py` | 로깅 + BudgetTracker(모델별 입출력 비용) |
| `config_loader.py` | config.yaml+secrets.yaml 병합(merge_secrets, secrets 우선) + 로드/검증 + WP 키 정규화 + is_wordpress_ready + split_secrets/save_secrets_flat |
| `utils/parser.py` | parse_json_lenient(LLM JSON) — 정규 위치 |
| `json_utils.py` | 위 shim(하위호환) |
| `sheet_sync.py`·`db_manager.py`·`site_manager.py` | Repository 브릿지 |
| `scheduler.py` | 슬롯/랜덤예약/today_schedule.json/실패모드3/즉시발행/요약 |
| `backup_manager.py` | config/시트/sqlite/outputs zip 백업 |
| `strategy_room.py` | 운영 분석 보고서 |
| `setup_wizard.py`·`google_provisioner.py` | 6단계 마법사 + Sheets/Drive 자동생성 |
| `site_wizard.py` | 사이트/계산기 생성·관리(6유형) |
| `ai_workspace.py` | 대시보드 AI 채팅 + 파일/Repository 도구 |
| `pipeline_status.py` | pipeline.log 파싱→단계 상태(tail) |
| `dashboard_cache.py` | SQLite 미러 읽기 캐시(read/refresh/invalidate, 라이브 폴백) |
| `telegram_notifier.py` | 텔레그램 알림 저수준 발송(키 없으면 무동작) |
| `telegram_ops.py` | 텔레그램 표준화 헬퍼 + 이벤트 게이팅(TELEGRAM_EVENTS) |
| `ai_assistant.py` | AI 운영비서(채팅+워크스페이스 파일도구+승인게이트+메모리+태스크+분석) |
| `cost_manager.py` | 일 예산 80%경고/100%정지/익일재개 |
| `retry_queue.py` | WP 발행 실패분 대기열(재발행) |
| `image_fallback.py` | Pollinations 실패 시 브랜드 템플릿 이미지(PIL) |

## repositories/ (AbstractDBAdapter 의존)
| 파일 | 역할 | 사용처 |
|------|------|--------|
| `article_repository.py` | 마스터_DB | sheet_sync·db_manager·calculator_pipeline |
| `site_repository.py` | sites + secrets WP/AI | site_manager·site_wizard |
| `calculator_repository.py` | calculators(create/delete/update_generated) | collector·site_wizard·app_*·calculator_* |
| `template_repository.py` | app_templates | app_factory·calculator_seed·ai_workspace |

## adapters/
| 파일 | 상태 |
|------|------|
| `db/sheets_adapter.py`(기본)·`db/sqlite_adapter.py` | ✅ (update가 신규 컬럼 자동 추가) |
| `db/postgres_adapter.py` | ❌ stub(NotImplementedError) |
| `storage/drive_adapter.py`(기본)·`storage/local_adapter.py` | ✅ |
| `storage/s3_adapter.py` | ❌ stub |

## scripts/ (.bat = cp949/CRLF, venv 직접호출)
install · run_pipeline(--once) · run_scheduler(--scheduler) · run_dryrun · run_strategy_room · run_dashboard(dashboard.py) · sync_cache(미러 워밍) · repair_google_setup.py(시트/드라이브 보수)

> 백업: `dashboard_backup.py`(성능작업 전), `dashboard_backup_ui.py`(UI작업 전).
