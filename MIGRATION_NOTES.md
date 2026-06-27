# MIGRATION_NOTES.md — v12 → v12 Lite 변경 내역

작업일: 2026-06-27 · 원칙: **Feature Freeze**(기존 파이프라인/STEP/데이터 흐름 무변경) · 모든 단계 git 커밋 체크포인트.

## 커밋 체크포인트
| 커밋 | 내용 |
|------|------|
| `d0379bb` | backup: before v12 lite refactoring (git init, 125파일) |
| `ad47ec3` | feat: AI Assistant 탭 |
| `612ac75` | feat(ops): Cost Manager / Retry Queue / Image Fallback / Telegram |
| `6155846` | refactor(slim): Legacy 실행/RUN_INTERVAL_HOURS 제거 |
| `0c69167` | refactor(ui): 18탭 → 8그룹 통합 |

---

## 1. 신규 추가 (additive)
| 파일 | 역할 |
|------|------|
| `modules/ai_assistant.py` | AI 운영비서: 채팅(GPT/Claude/Gemini) · 워크스페이스 파일도구(read/write/create/list/search) · 승인 게이트 · 메모리 · Lite 태스크 · 프로젝트 분석기 |
| `modules/cost_manager.py` | 일 예산 80% 경고 / 100% 자동 일시정지 / 익일 자동 재개 |
| `modules/retry_queue.py` | WP 발행 실패분 `pending_posts` 저장 → 대시보드 재발행 |
| `modules/image_fallback.py` | Pollinations 실패 시 브랜드 템플릿 이미지(PIL) |
| `modules/telegram_ops.py` | 오류/예산/일일요약/발행승인 알림(telegram_notifier 재사용) |
| `dashboard.py` | 🤖 AI Assistant 탭, 💰 Revenue 탭에 Cost/Retry 섹션 |

## 2. 구조 슬림화 (제거)
| 대상 | 처리 |
|------|------|
| `scripts/run_schedule.bat` | 삭제 |
| Legacy 반복 실행(`main.py --schedule` + interval 루프) | 삭제 → 예약발행 스케줄러 단일화 |
| `RUN_INTERVAL_HOURS` | config/setup_wizard/dashboard에서 제거 |
| `dashboard_ui_refactor.py` (+ `.md`) | 삭제 |
| `scripts/run_dashboard_new.bat` | 삭제 |
| 대시보드 발행방식 'Legacy' 선택 | 제거(예약발행 고정) |

## 3. 통합
- **Dashboard 18탭 → 8그룹** 2단 네비게이션(그룹 → 하위 페이지). 기존 페이지/elif 블록은 **그대로 유지**(기능 보존).
  - Dashboard(운영센터/현황) · Content(발행목록/작업보드/AI Workspace/전략회의실) · Calculator(App Factory/계산기 관리) · Scheduler(일정/AI Pipeline/사이트 관리) · Revenue(비용+Cost+Retry) · Logs(오류/실시간/헬스) · Settings · AI Assistant
- **계산기 생성 = App Factory 단일화**: `🧮 Calculator Builder` 페이지는 네비에서 **비노출**(코드 보존, 추후 정리 가능).
- **실행 = `run_scheduler.bat` 단일**(상시), 단발은 `run_pipeline.bat`.

## 4. 변경하지 않은 것 (Feature Freeze 준수)
- 12단계 파이프라인 STEP 순서/데이터 흐름/`run_once`·`_process_one` — **무변경** (RSS dry-run 정상 회귀 확인)
- Writer/Editor/Publisher/Repository/Adapter/Collector — **무변경**
- 파이프라인 AI 모델 배정(정제/전략 등) — **무변경** (※ 지시서의 "GPT를 파이프라인에서 제외" 목표는 모델 재배정+재검증이 필요하여 본 라운드 미적용. 별도 작업 권장)
- image_generator는 **폴백만 추가**(실패 시 브랜드 이미지). 정상 경로 동일.
- scheduler 루프에 **비용 점검 호출만 추가**(STEP 무관, 예산 소진 시 일시정지).

## 5. 주의/후속
- `site_wizard`의 계산기 생성 함수는 코드상 잔존(네비 비노출로 사실상 미사용). 완전 삭제 시 별도 정리 PR 권장.
- 지시서의 파이프라인 모델 목표(정제/SEO=Gemini, 작성=GPT-4o-mini, 검수=Claude)와 현재 config 차이는 README/ROADMAP에 명시. 적용 원하면 config 변경 + 회귀 테스트 필요.
- 롤백: `git reset --hard d0379bb` (작업 전 상태).
