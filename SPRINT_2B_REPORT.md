# SPRINT 2B v2 — 최종 보고서 (Dashboard & Structure)

> 작업일 2026-06-29 · 방식: **작업별 현황보고→승인→변경** 게이트 준수 · 전 작업 commit 체크포인트.
> 코어(12단계 파이프라인/Repository/Adapter/Collector) **무변경**. 변경은 `dashboard.py`(UI) + `telegram_ops.py`(helper) + 신규 문서에 한정.

## 커밋 이력
| 작업 | 커밋 | 내용 |
|------|------|------|
| PRE-01 | `c0c5bb1`→`07b09d3` | Secrets 분리(config→secrets.yaml) |
| 작업4 | `ed52043` | 운영센터 홈 개선 |
| 작업5 | `2a292d5` | Site Manager 개편 |
| 작업6 | `c2c4bc8` | 5단계 Site 생성 마법사 |
| 작업7 | `ae62243` | Site Settings Override |
| 작업9 | `399e317` | Telegram 게이팅+토글+설계문서 |
| 작업10 | `f5f4751` | AI Assistant 분석 보고서 |
| 작업8 | `a8a2cfa` | 통합 실행 버튼(Site/Platform 라우팅) |

---

## ① 프로젝트 구조 (2B 반영)
- **코드 변경 파일**: `dashboard.py`(UI 확장), `modules/telegram_ops.py`(이벤트 게이팅), `modules/config_loader.py`·`modules/setup_wizard.py`(PRE-01 secrets).
- **신규 파일**: `config/secrets.example.yaml`, `TELEGRAM_BIDIRECTIONAL_DESIGN.md`, `AI_ASSISTANT_ANALYSIS.md`, `SPRINT_2A_REPORT.md`, `SPRINT_2B_REPORT.md`.
- **신규 sites 컬럼**(어댑터 자동 추가): `platforms`, `features`, `daily_override`, `deleted_at`, `seo_keyword_count`, `seo_length`, `calc_active`, `image_mode`, `telegram_enabled`, `analytics_enabled`.
- **신규 config 키**: `TELEGRAM_EVENTS`, `SITE_RETENTION_DAYS`(읽기 기본 30).
- ⚠️ **2A 문서 현행화(ARCHITECTURE/FILE_STRUCTURE/ROADMAP)는 미적용** — 별도 작업 권장(2A 보고서 ① 참조). 이번 2B로 구조가 더 확장되어 우선순위 상승.

## ② Dashboard 개선 결과 (작업4)
운영센터 홈(`render_dashboard_home`) 재구성:
- **현재 Site 카드**(최상단 고정) + Site 변경 셀렉터(`current_site_id` 세션, sites 비면 SalaryMate fallback).
- **운영 5카드**: 시스템상태(health) / Workflow단계 / AI작업(활성모델) / 오늘 운영(발행·생성) / AI비용(Cost Manager).
- **Workflow 시각화**: 블로그(main.py STEP 실순서 10단계, 현재 단계 강조) + 계산기 파이프라인.
- **진행 현황**: 오늘 일정 진행률 + Retry/실패/진행중/ETA.

## ③ Site Manager 구조 (작업5)
사이트 관리 탭 확장(UI만, site_wizard 무변경):
- 현재 Site 셀렉터 · **Export/Import**(메타데이터, 자격증명 제외).
- **안전 삭제**: 즉시삭제 제거 → 보관(`archived`+`deleted_at`) → 보관기간(기본30일) → 복구 / `"DELETE"` 확인 후 영구삭제. 자동삭제 없음(만료 표시만).
- **복제(Clone)**: 인라인 프리필 폼 → `create_site`.

## ④ Site Wizard 구조 (작업6)
5단계 마법사(기존 단순 폼 병행):
Profile → Platform(WordPress·Calculator 독립 복수) → Feature(Platform별+공통) → Settings(Global→Override) → Pipeline 파생 확인 → 생성.
저장: `create_site`(base) + `update_site`(platforms/features JSON). Pipeline 실제 연결은 작업8.

## ⑤ Site Settings 구조 (작업7)
선택 Site 대상 Override 편집기:
- 그룹: AI / WordPress·SEO / Scheduler·Image / Telegram·Analytics / Calculator / Feature Flags.
- Global 기본값 표시 + 값 있으면 🔵 Override 뱃지 + Override 초기화(Global 복귀, 코어필드 보존).
- 저장은 `update_site`만(신규 컬럼). config.yaml(Global) 무변경. *런타임 소비는 후속*.

## ⑥ Workflow 개선 결과 (작업4+작업8)
- 시각화: 블로그/계산기 2개 파이프라인, 현재 STEP 강조(pipeline_status).
- **실행 라우팅(작업8)**: 통합 `▶ 실행` 1개 → 선택 Site의 platforms 기반 자동 결정(Calculator만/WordPress만/둘다 순차·선택/미설정 fallback). 기존 4버튼은 `🔧 고급 실행` 보존. **12단계 내부 무변경 — 진입점만.**

## ⑦ Telegram Audit 결과 (작업9)
- 역할: `telegram_notifier.send`(저수준 단일 choke) / `telegram_ops`(표준화 헬퍼). main·editor·calc는 raw send 직접 사용(혼재).
- 이벤트 현황: ✅비용80/100·오류·헬스·DLQ wired / ❌발행성공·시작종료·승인요청·일일요약 미배선.
- 개선: `telegram_ops`에 **이벤트 게이팅**(`TELEGRAM_EVENTS`, 기본 ON) + Settings **ON/OFF 토글** + `TELEGRAM_BIDIRECTIONAL_DESIGN.md`(설계만).
- 한계: 파이프라인 크리티컬 알림은 파일 무변경 위해 항상 발송. 미배선 이벤트는 후속(파이프라인 수정 필요).

## ⑧ AI Assistant 분석 (작업10)
→ `AI_ASSISTANT_ANALYSIS.md`. 요지: 단발 요청-응답(에이전트 루프 아님) · 승인게이트+백업+샌드박스 안전설계 우수 · 컨텍스트 하드코딩 키워드 한정 · 메모리 append만. P1 제안: 툴콜 연결, 대화 영속화.

## ⑨ Regression Test 결과
| 항목 | 작업8 전 | 작업8 후 |
|------|:---:|:---:|
| Dashboard 8그룹(17탭) | ✅ | ✅ |
| Calculator 생성(경로) | 🟢 | 🟢 |
| WordPress graceful skip | ✅ | ✅ |
| Scheduler 슬롯 | ✅ | ✅ |
| Telegram(게이팅/Test) | ✅ | ✅ |
| AI Assistant 도구 | ✅ | ✅ |
| Site Manager | ✅ | ✅ |
| Retry Queue | ✅ | ✅ |
| Cost Manager | ✅ | ✅ |
| 12단계 dry-run | ✅(health 6 OK) | ✅(health 6 OK) |
> 🟢 Calculator: 코드/탭 정상, 실제 생성은 API 비용·시트쓰기로 미실행(경로 정상).

## ⑩ 향후 개선 사항
1. **2A 문서 현행화**(ARCHITECTURE/FILE_STRUCTURE/ROADMAP — 17탭·삭제파일·신규모듈) — 우선.
2. Site Settings Override의 **런타임 소비 배선**(파이프라인이 site override 값 사용 — 파이프라인 수정 필요, 별도 Sprint).
3. Telegram **미배선 이벤트**(발행성공/시작종료/승인요청/일일요약) + **양방향**(설계문서 기준).
4. AI Assistant **툴콜 에이전트화** + 대화 영속화.
5. **git 히스토리 노출 키 재발급**(배포 전, 합의됨).
6. 테스트 스위트(pytest) 정식화.

## ⑪ 절대 건드리면 안 되는 핵심 구조
- 12단계 파이프라인 `main.run_once`/`_process_one` STEP/데이터 흐름.
- `ai_provider` 단일 AI 추상화 · `config_loader` 병합 로딩(secrets).
- Adapter/Repository 경계(`db.factory`/`storage.factory` + Repository 브릿지).
- `site_wizard.py`/`site_manager.py`/Collector — 본 Sprint 무변경 유지(UI에서 호출만).
- 계산기 자동 품질 루프 · Graceful Degradation · BudgetTracker→cost_manager.

---
> ✅ SPRINT 2B 완료. 코어 무변경, 회귀 전부 통과. 후속은 ⑩ 우선순위 순.
