# CHANGELOG_AI.md — 안정화/고도화 작업 변경 이력

작업일: **2026-06-21** · 기준: 실제 코드 재검증 후 수정 · 원칙: 기존 파이프라인 동작 보존

범례: 🆕 신규 / ✏️ 수정 / 🗑️ 삭제

---

## [2026-07-04] 계산기 "파일 저장" 버그 수정 (커밋 `3ca475a`)

| 파일 | 변경 | 이유 / 영향 |
|------|------|-------------|
| ✏️ `dashboard.py` | "📥 파일 저장"(cm_dl) 콜백을 **계산기별 폴더 저장**으로 변경: `data/workspace/{slug}/index.html·style.css·script.js`(원본 파일명 유지, slug의 `/`·`\`·`..` sanitize) | **증상**: 대시보드 미리보기와 저장 파일 렌더 불일치. **원인**: `calc_{slug}_style.css` 형태로 저장되어 index.html의 `href="style.css"` 상대경로와 불일치 → CSS/JS 미적용. **수정**: 폴더 구조 + 원본 파일명 → 로컬 더블클릭·GitHub Pages 동일 렌더. `app_generator`/`calculator_v2.html`/`design_system.css`/`ai_workspace` 무변경(콜백 한정) |

검증: 폴더 생성 확인, 상대링크(style.css/script.js) 유지, 로컬 더블클릭 시 시안과 동일 렌더링 확인.

---

## 1. Gemini SDK 최신화 (google-generativeai → google-genai)

| 파일 | 변경 | 이유 / 영향 |
|------|------|-------------|
| ✏️ `modules/ai_provider.py` | `GeminiProvider`를 `google.genai.Client` 기반으로 재작성. `system_instruction`/`max_output_tokens`를 `GenerateContentConfig`로 전달 | deprecated SDK 제거 + 기존에 무시되던 `max_tokens` 적용. 영향: Planner(M1)·기타 Gemini 호출 |
| ✏️ `health_check.py` | `_check_gemini`를 `genai.Client().models.list()` 기반으로 교체 | 헬스체크 Gemini 점검 정상화, FutureWarning 제거 |
| ✏️ `requirements.txt` | `google-generativeai` → `google-genai`, `Pillow` 추가 | 의존성 정합화(Pillow는 image_generator에서 사용되나 미선언이었음) |

검증: 헬스체크 Gemini `OK`, Planner 경로 chat 성공, dry-run 로그에 **FutureWarning 0건 / generativeai 0건**.

---

## 2. WordPress 발행부 정비 (키명 단일화 + 미구축 대기)

| 파일 | 변경 | 이유 / 영향 |
|------|------|-------------|
| ✏️ `modules/config_loader.py` | `_normalize()`(구 `WORDPRESS_PASSWORD`→`WORDPRESS_APP_PASSWORD` 승격), `is_wordpress_ready()` 추가. `WORDPRESS_URL` 필수 검증 **제거** | WP 미구축 상태에서도 ConfigError 없이 기동 |
| ✏️ `modules/publisher.py` | `is_wordpress_ready()` False면 발행 **건너뜀(skipped_no_wp)** + 로컬 미리보기만 저장. 이미지 URL 안전 접근(실패 시 `<img>` 생략). 키명 `WORDPRESS_APP_PASSWORD` 단일화(구 키 하위호환) | KeyError/예시값 발행 시도 제거, 미구축 시 대기 |
| ✏️ `modules/setup_wizard.py` | `DEFAULT_CONFIG`에 `WORDPRESS_URL/USERNAME/APP_PASSWORD`(공란) 추가 | 키명 일관화 |
| (검증) `repositories/site_repository.py` | 이미 `WORDPRESS_APP_PASSWORD` 사용 — 변경 없음 | 사이트별 발행 경로 정합 확인 |

검증: placeholder(example.com)→`skipped_no_wp`, 실제 설정→`published` 경로, 구 키 자동 승격 단위 확인.

---

## 3. DAILY_POST_COUNT 실제 적용 (다건 처리)

| 파일 | 변경 | 이유 / 영향 |
|------|------|-------------|
| ✏️ `main.py` | `run_once(cfg, dry_run, max_count)`를 **수집 후 목표 개수만큼 순회**하도록 재작성. STEP 2~12를 `_process_one()`으로 분리 | `items[0]` 1건 고정 → 다건 |
| 〃 | 항목별 독립 try/except(한 건 실패가 전체 중단 안 함), 중복/실패 건 건너뛰기, **목표 도달 시 종료**, **매 항목 전 예산 재확인→초과 시 즉시 중단**, 처리 통계 로그 | 안정성/운영성 |
| 〃 | 같은 실행 내 중복 방지(메모리 `existing_titles` 갱신), WP 미구축 시 `검수대기` 상태로 기록 | 정합성 |

검증: `run_once(dry_run=True)` → `{'produced':0,'reason':'dry_run'}`. 통계 로그(`목표/생산/처리/중복/실패`) 출력.

---

## 4. 비용 기록 정확도 향상

| 파일 | 변경 | 이유 / 영향 |
|------|------|-------------|
| ✏️ `modules/logger.py` | `BudgetTracker` 재작성: 모델 prefix 매칭 단가표(`PRICE_IO` 입력/출력 분리), `record(model, tokens, in_tokens, out_tokens)`, `by_model`/`tokens` 집계, 조회 API(`get_provider_breakdown`/`get_model_breakdown`/`get_daily_cost` 등) | 모델별/Provider별 정확 귀속 + 입출력 단가 분리 지원 |
| ✏️ `main.py` `_process_one` | 단계별 **실제 모델**로 비용 기록(`_flush_costs`), **실패해도 누적 토큰 기록** | 기존: 전체 토큰을 EDITOR 단가로 1회 → 개선: 단계별 모델 단가 |

검증: claude in/out 분리 계산, gpt-4o/gemini blended, provider·model breakdown 단위 확인. 기존 budget.json 구조 자동 마이그레이션(by_model/tokens 추가).

> 한계: 파이프라인 단계는 provider가 총 토큰만 반환 → 입/출력 **분리는 API만 준비**, 실제 분리 적용은 provider 반환값 확장 필요(→ TODO_NEXT).

---

## 5. JSON 파싱 안정화 (공통 유틸)

| 파일 | 변경 |
|------|------|
| 🆕 `modules/json_utils.py` | `parse_json_lenient()`/`try_parse_json()` — 코드블록/잡텍스트 방어 |
| ✏️ `modules/strategy_room.py` | 로컬 `_parse_json_lenient` 제거 → 공통 유틸 import(별칭 보존) |
| ✏️ `modules/planner.py` `strategist.py` `cleaner.py` `duplicate_checker.py` | `json.loads(text.strip())` → `parse_json_lenient()` |

검증: 순수/```json 펜스/설명문 혼합 입력 모두 파싱 성공.

---

## 6. 예외 처리 개선

| 파일 | 변경 |
|------|------|
| ✏️ `modules/telegram_notifier.py` | `except: pass` → `LOG.warning`(+DEBUG 시 traceback) |
| ✏️ `modules/image_generator.py` | bare `except:` → 원인 로그 후 로컬 폴백 |
| ✏️ `modules/backup_manager.py` | `except ValueError: pass` → 스킵 사유 로그 |
| ✏️ `main.py` | 운영로그 기록 실패 `except: pass` → `LOG.warning` |
| ✏️ `modules/duplicate_checker.py` `strategy_room.py` | `print(...)` → `LOG.warning`(+DEBUG 시 traceback) |

동작 보존(흡수는 유지), 원인은 반드시 기록.

---

## 7. Dead Code 정리 (제거)

| 파일 | 조치 | 사유 |
|------|------|------|
| 🗑️ `modules/checkpoint.py` | 제거 + `main.py`에서 import/`cp.clear()` 제거 | `clear()`만 연결, `save/load/lock` 미사용 → "복구" 미작동. 상태 영속은 스케줄러 `today_schedule.json`로 대체 |
| 🗑️ `modules/hub_manager.py` | 제거 | 호출처 0 |
| 🗑️ `repositories/queue_repository.py` | 제거 | app_factory 미구현, 인스턴스화 0 |
| 🗑️ `repositories/template_repository.py` | 제거 | 동일 |
| 🗑️ `modules/health_check.py` | 제거 | 루트 `health_check.py`가 실사용. 중복 + 구 SDK 잔존 |

검증: 전체 모듈 import 테스트 **ALL OK**(broken import 0). (시트 탭 `app_factory_*`은 유지되어도 무해)

---

## 8. 대시보드 완성

| 파일 | 변경 |
|------|------|
| ✏️ `dashboard.py` `💰 비용 모니터` | 플레이스홀더 제거 → budget.json 기반(일/월/누적 비용, 예산 진행률, Provider/모델별, 토큰) |
| ✏️ `dashboard.py` `⚠️ 오류 로그` | 미정의 `get_sheet` 제거 → DB 어댑터 `logs` 조회, 표 출력(실행일시/마스터ID/대상/실패모듈/오류내용) |
| ✏️ `dashboard.py` `load_cfg` | `_root` 주입(스케줄러/백업 경로) |

검증: 대시보드 기동 health `ok`/root 200, 로그 예외 없음. BudgetTracker가 실제 budget.json 로드.

---

## 9. 글별 발행 시간 슬롯 스케줄러 (신규)

| 파일 | 변경 |
|------|------|
| 🆕 `modules/scheduler.py` | 슬롯 설정·검증·랜덤 시각 생성·`today_schedule.json` 영속·실패모드 3종(none/retry_in_slot/next_slot)·평일/주말 분리·이력(`history.jsonl`)·수동실행 충돌방지 락·`run_scheduler_loop` |
| ✏️ `main.py` | `--scheduler` 모드 추가(`run_scheduler_loop`), `run_once(max_count=1)` 연동, `cfg["_root"]` 주입, **schedule 모드 백업 버그 수정**(`BackupManager().run_daily_backup()`) |
| ✏️ `dashboard.py` | `📅 오늘 발행 일정` 탭(일정 표·진행률·생성/재생성/초기화 버튼·평일주말 슬롯 편집·검증·저장) |
| 🆕 `scripts/run_scheduler.bat` | 스케줄러 실행(cp949/CRLF) |

검증: 슬롯 검증(시작<종료/개수/형식/겹침), 생성·영속, due 감지, 성공→completed, 실패→retry_in_slot 재예약, history 기록 단위 확인.

---

## 11. 사이트/계산기 생성 마법사 (신규 — 코드 수정 없이 추가)

| 파일 | 변경 |
|------|------|
| 🆕 `modules/site_wizard.py` | 6유형(블로그/계산기/정책정보/금융/제휴마케팅/사용자정의) 생성 로직. 유형별 기본 설정(site_type·monetization·content_mode·AI 프로필) 자동 부여, sites/calculators 시트 자동 등록, WP 앱 비밀번호는 secrets.yaml에 저장, 검증(필수값/중복 도메인/중복 사이트명), 목록/상태변경/수정/삭제 |
| ✏️ `repositories/site_repository.py` | `delete(site_id)`, `save_wp_profile(...)` 추가 |
| ✏️ `dashboard.py` | `🌐 사이트 관리` 탭 — ➕ 사이트 추가(유형별 동적 폼) + 사이트/계산기 목록(활성/비활성/수정/삭제) |

- 유형→수집기 매핑: 블로그/사용자정의→custom(=RSS/policy), 정책정보→policy, 계산기→calculator, 금융→finance(stub), 제휴마케팅→affiliate(stub). stub 유형은 등록 시 안내 표시.
- "기본 프롬프트": 본문 프롬프트는 `writer`가 site_type로 선택하므로 별도 컬럼 없이 site_type/content_mode/AI 프로필 자동 설정으로 충족.
- 검증(단위 테스트): 블로그 등록, WP 누락/중복명/중복도메인/계산기 중복 차단, stub 안내, 목록/비활성/삭제, **동일 초 생성 site_id 충돌 버그 발견·수정(uuid 접미사)**.

## 12. 운영센터 UI 고도화 + 발행 스케줄 통합 개편

| 파일 | 변경 | 이유 |
|------|------|------|
| ✏️ `main.py` | `--once` 플래그 추가, `OPERATION_MODE`(scheduled 기본/legacy) 분기로 운영방식 통합. 플래그 없으면 OPERATION_MODE 따름 | 발행 일정 시스템을 기본 운영방식으로, RUN_INTERVAL_HOURS는 Legacy로 분리 |
| ✏️ `modules/scheduler.py` | `summarize()`(KPI 요약), `immediate_publish(mode=pull/add)`(즉시발행, 락) 추가 | 운영센터 KPI·즉시발행 |
| ✏️ `dashboard.py` | **🏠 운영센터(홈)** 신설: 빠른 실행 7버튼(즉시발행/파이프라인1회/발행1건/이미지재생성/전략회의실/헬스체크/백업) + KPI 카드 + 비용 + 서비스상태(캐시) + 최근오류5 + 일정요약. **📋 작업 보드(칸반 6열)**. 실시간 로그 **자동갱신(st.fragment 5초)**. 헬스체크 **카드형**. 설정에 **발행방식 라디오(OPERATION_MODE)**, DAILY_POST_COUNT는 슬롯 수로 자동 결정(읽기전용). 일정 탭에 **슬롯 수 입력 + 즉시발행 버튼** | 5초 상태파악·1클릭 실행·일정 실시간 관리 |
| ✏️ `scripts/run_pipeline.bat` | `main.py --once`로 변경(단발 실행 유지) | 하위호환(클릭 동작 보존) |

- **하위호환**: 기존 STEP1~12, run_once 시그니처, 모든 기존 탭(현황/발행목록/전략회의실/설정 등) 보존. config 키는 추가만(`OPERATION_MODE`), 기존 데이터 유지.
- 즉시발행: 확인창("정말 발행?") + 모드(당겨쓰기 기본/추가발행) + 운영로그·history 기록(예약시간="즉시실행").
- 빠른 실행은 모두 기존 함수 재사용(run_once/immediate_publish/run_strategy_room/health_check.run/BackupManager/image_generator).
- 운영센터 홈은 전부 로컬 파일(today_schedule.json/budget.json/health_last.json/pipeline.log)만 읽어 빠르게 로딩(서비스 상태는 마지막 헬스체크 캐시 표시, 실시간 재검사는 버튼).
- 검증: dashboard/main/scheduler compile OK, summarize·immediate_publish(pull/add) 단위 테스트, 대시보드 실기동(home 기본탭 렌더 무오류).

## 13. SalaryMate v12.0 — 플랫폼 확장 (Calculator Builder / AI Workspace / App Factory / AI Pipeline)

> 원칙: 기존 10개 탭·파이프라인·데이터 **무수정 유지**, 확장만. 모든 데이터 접근 Repository/Adapter 경유(gspread/Drive 직접 호출 없음).

| 파일 | 변경 | 이유 |
|------|------|------|
| 🆕 `modules/ai_roles.py` | 역할 체계(총괄/리서치/코드/작성/검수/이미지)→provider/model. config `AI_ROLES`로 편집 | 확장 기능 공통 AI 라우팅(기존 파이프라인 모델과 별개) |
| 🆕 `repositories/template_repository.py` | app_templates Repository **재도입**(App Factory가 사용) | task7서 제거했으나 실사용처 생겨 연결 |
| 🆕 `modules/app_factory.py` | 계산기 자동생성(GPT 스펙→Claude HTML→GPT SEO/FAQ→Gemini 이미지프롬프트) + calculators/app_templates 저장 | App Factory |
| 🆕 `modules/ai_workspace.py` | 채팅(역할별 모델) + 안전 파일도구(읽기/구조분석/샌드박스 생성/백업후 덮어쓰기) + Repository 조회 | AI Workspace |
| 🆕 `modules/pipeline_status.py` | pipeline.log 파싱→단계 상태(비침습적) + budget 비용/토큰 | AI Pipeline Monitor |
| ✏️ `dashboard.py` | 신규 4탭: `🧮 Calculator Builder`(CRUD), `🏭 App Factory`(자동생성+렌더 미리보기+저장), `💬 AI Workspace`(채팅/파일/데이터), `📊 AI Pipeline`(단계 시각화). 설정에 **AI 역할 편집** | 4기능 UI |

- **모델 ID 실검증·정정**: `claude-3-5-sonnet-latest`는 키에서 **retired(404)** → 코드역할 `claude-sonnet-4-6`로. `gemini-2.5-pro`는 키 쿼터 **429** → 리서치/이미지역할 `gemini-2.5-flash`로. (실호출로 확인)
- App Factory 코드생성은 JSON 대신 **단일 자가완결 HTML(raw)**로 받아 토큰 truncation/이스케이프 문제 회피(테스트 중 발견·수정).
- AI Workspace 파일 수정은 **원본 백업(data/workspace/backups/) 후** 확인 게이트로만 — 안전.
- 검증: 전 모듈 compile/import OK, ai_roles/ai_workspace/pipeline_status 단위 테스트, **App Factory 실제 생성 성공**(BMI 계산기: GPT 스펙→Claude 9KB HTML→GPT SEO+FAQ4), 대시보드 실기동 무오류.

### ⚠️ 부수 발견(기존 파이프라인 잠재)
- 기존 `config.MODEL_EDITOR=claude-3-5-sonnet-latest`도 retired → STEP 8에서 404 후 GPT fallback으로 동작(치명 아님). 권장: 설정에서 `claude-sonnet-4-6`로 교체.

## 14. SalaryMate 계산기 엔진 (Policy/RSS 유지 + Calculator 추가)

> 상세: `CALCULATOR_ENGINE.md`. 기존 RSS 파이프라인 무삭제, 계산기 콘텐츠 경로 추가. 전부 Repository/Adapter 경유.

- 🆕 `prompts/calculator_writer_prompt.txt`, `modules/strategist_calculator.py`, `modules/calculator_faq_generator.py`, `modules/calculator_seo_generator.py`, `modules/calculator_template_engine.py`, `modules/calculator_seed.py`, `modules/calculator_pipeline.py`
- ✏ `repositories/calculator_repository.py`(create/delete), `modules/collector/calculator.py`(키워드 확장), `main.py`(--calculator/--seed-calculators), `dashboard.py`(🧮 탭 시드/실행 버튼)
- 시드: app_templates 5종(basic/report/compare/wizard/diagnosis) + calculators 5종(주휴수당/퇴직금/연차수당/실업급여/4대보험)
- 검증: SQLite 어댑터로 전체 경로 실행 — 시드(5+5), 파이프라인 1건 생산(SEO+본문+계산기 위젯+CTA→articles 저장) 성공.

## 15. 전면 재검증 + JSON 파서 정규화 (2026-06-21)

8개 요구사항을 실제 코드로 전수 재검증한 결과 1~4·7·8·9는 이미 충족. 미충족 2건 보완:

| 요구 | 재검증 결과 | 조치 |
|------|------------|------|
| #1 Gemini | `google.generativeai` 잔존 0(주석 1줄만), `google.genai` 사용 | 유지 |
| #2 WordPress | `is_wordpress_ready`+`WORDPRESS_APP_PASSWORD` 단일화 | 유지 |
| #3 루프 | `run_once`+`_process_one` 다건 처리 | 유지 |
| #4 대시보드 | `get_sheet` 0, 비용/오류 탭 실데이터 | 유지 |
| **#5 파서** | `modules/json_utils.py`만 존재(요구 경로 불일치) | 🆕 `modules/utils/parser.py`로 **정규 분리** + `json_utils.py`는 재노출 shim. planner/strategist/cleaner/duplicate_checker/strategy_room을 `modules.utils.parser`로 repoint |
| **#6 무음 except** | 구버전 모듈은 처리됐으나 v12 신규 모듈 7곳에 `except: pass`(비용 best-effort) 잔존 | ✏ 7곳 모두 `LOG.warning(원인)`으로 변경. 전수 0건 |
| #7 비용 in/out | `PRICE_IO`+`in_tokens/out_tokens` | 유지 |
| #8 dead code | checkpoint/hub_manager/health_check/queue_repository **삭제됨**, template_repository는 App Factory·Workspace에서 **사용 중(연결 유지)** | 유지 |
| #9 스케줄러 | `modules/scheduler.py`(슬롯/평일주말/실패모드3/today_schedule.json) | 유지 |

- 신규: `modules/utils/__init__.py`, `modules/utils/parser.py`
- 수정: `modules/json_utils.py`(shim), planner/strategist/cleaner/duplicate_checker/strategy_room(import 경로), v12 모듈 7곳(except 로깅)
- 검증: 전체 compile OK, parser canonical+shim 동일성 확인, 핵심 모듈 import OK.

## 16. 대시보드 운영 편의 리팩토링 (2026-06-21, 텔레그램 제외)

라인 단위 재검증 후, 이미 된 것은 유지하고 빠진 4건만 보완(기존 12단계 코어 로직 무변경).

| 요구 | 재검증 | 조치 |
|------|--------|------|
| ①비용 모니터 placeholder 제거 | 이미 구현(budget.json 시각화) | 유지 |
| ②오류 로그 get_sheet 크래시 | 이미 수정(DB 조회 표) | 유지 |
| 2①원클릭 대량 발행 | 버튼은 있으나 개수 입력 없음 | 🆕 운영센터 상단 **🚀 마스터 발행 패널**(발행 개수 입력 + 즉시 실행, `run_once(max_count=N)`) |
| 2②score_weights 슬라이더 | 미구현 | 🆕 설정 탭 **⚖️ 가중치 슬라이더 편집기**(6항목, 저장 시 합계 1.0 정규화→`score_weights.yaml`) |
| 2③일정 탭 즉시 재시도 | 없음 | 🆕 실패 슬롯 선택 후 **🔁 즉시 재시도**(`execute_due_post`) |
| 2④실시간 로그 가독성 | 통째 dump | ✏ **레벨 색상 하이라이팅(ERROR빨강/WARN노랑/INFO초록) + 필터(전체/ERROR만/WARN+ERROR/INFO만) + 레벨별 카운트** |

- 수정 파일: `dashboard.py`(운영센터·설정·일정·실시간로그 4개 구역)
- 검증: compile OK, 대시보드 실기동(health ok, 로그 무오류), 기존 탭/파이프라인 보존
- 텔레그램 알림/테스트: 요구대로 **미수정**

## 17. 스코어링 키 정합화 (#31, 2026-06-21)

| 파일 | 변경 | 이유 |
|------|------|------|
| ✏ `modules/strategist.py` | `_load_weights`가 yaml 가중치 키를 AI 점수 키로 정규화(`traffic`→`traffic_score`). `_canonical_weight_keys()` 추가 | yaml 짧은 키 ↔ AI 점수 `_score` 키 불일치로 `compute_final_score`가 **항상 0**이던 기존 버그 해결 |

- 영향: STEP5 `final_score`가 실제 가중합으로 산출됨(예: 검증 72.0). 슬라이더 편집기는 yaml 짧은 키 그대로 유지(로드 시 자동 정규화) — 무중단.
- 검증: 실제 `score_weights.yaml` 로드→`compute_final_score`=72.0(기대값 일치), 멱등성·DEFAULT 경로 일치 확인. 코어 흐름(게이팅) 변경 없음(메트릭 정확도만 개선).

## 18. SalaryMate 계산기 플랫폼 확장 (신규 모듈 5종, 2026-06-22)

> 상세: `CALCULATOR_PLATFORM_REPORT.md`. 기존 RSS/발행 파이프라인 무삭제·무변경, 신규 모듈로만 확장.

- 🆕 `modules/formula_engine.py`(AST 안전 수식 실행, eval 금지), `app_generator.py`(HTML/CSS/JS 생성), `github_deployer.py`(GitHub Pages 배포, graceful), `internal_link_engine.py`(관련 계산기/글/CTA), `calculator_seeder.py`(초기 5종+수식)
- ✏ `dashboard.py`(🧮 계산기 관리 탭: 시드/수식편집·검증/미리보기/배포/상태/삭제/URL), `calculator_pipeline.py`(내부링크 자동 주입), `site_wizard.py`(content_mode 오버라이드=hybrid)
- 검증: formula 보안(악성코드 4종 차단)·실행(퇴직금 900만 정확), app_generator 3파일+JS변환, seeder 5종, 내부링크, github graceful 모두 SQLite로 end-to-end 통과. 기존 12단계 무변경.

## 19. 계산기 AI 자동생성 엔진 (신규 모듈 5종, 2026-06-22)

> 상세: `CALCULATOR_AI_AUTOGEN_REPORT.md`. 기존 RSS/발행 파이프라인·보호 파일 무변경, 신규 모듈로만 확장.

- 🆕 `modules/calculator_prompt_manager.py`(중앙 프롬프트+품질규칙), `calculator_content_generator.py`(본문+`auto_generate_all`), `calculator_image_prompt_generator.py`(썸네일/본문 프롬프트)
- ✏ `calculator_seo_generator.py`(+`generate_seo_title`/`generate_meta_description`, 기존 `generate_seo` 보존), `calculator_faq_generator.py`(question/answer 5~10개, q/a 하위호환), `app_generator.py`(FAQ q/a·question/answer 양쪽 허용)
- ✏ `repositories/calculator_repository.py`(`update_generated` — seo_title/seo_description/article_content/image_prompt_thumbnail/image_prompt_body/generated_at 저장)
- ✏ `dashboard.py` 🧮 계산기 관리: [SEO/FAQ/본문/이미지프롬프트/⚡전체 자동생성] 버튼 + 생성결과 미리보기
- ✏ `adapters/db/{sqlite,sheets}_adapter.py` `update`: **신규 컬럼 자동 추가**(insert와 동일, 기존 컬럼 불변) — 신규 생성 컬럼 저장 위해 필수
- AI 모델 규칙: SEO/FAQ/본문=`build_provider_for_role("writing")`(MODEL_WRITER), 검수=review(MODEL_EDITOR), 이미지=research(Gemini Flash)→writing fallback
- 검증: 5종(주휴/퇴직/연차/실업/4대보험) SEO/FAQ(8~9)/본문(1.7~2.7k자)/이미지 전부 생성 성공, 금지표현 0, DB 저장(어댑터 보강 후) 검증.

## 영향 범위 요약

- **신규 파일**: `modules/json_utils.py`, `modules/scheduler.py`, `modules/site_wizard.py`, `modules/ai_roles.py`, `modules/app_factory.py`, `modules/ai_workspace.py`, `modules/pipeline_status.py`, `repositories/template_repository.py`(재도입), `scripts/run_scheduler.bat`, (문서: CHANGELOG_AI/STABILITY_REPORT/TODO_NEXT/UI_REPORT)
- **삭제 파일**: `modules/checkpoint.py`, `modules/hub_manager.py`, `modules/health_check.py`, `repositories/queue_repository.py`, `repositories/template_repository.py`
- **핵심 수정**: `main.py`, `modules/logger.py`, `modules/ai_provider.py`, `modules/publisher.py`, `modules/config_loader.py`, `dashboard.py`, `health_check.py`, `requirements.txt`
- **신규 런타임 산출물**: `data/schedule/today_schedule.json`, `data/schedule/history.jsonl`
- **신규 config 키**: `PUBLISH_SCHEDULE`(enabled/failure_mode/weekday/weekend), `WORDPRESS_APP_PASSWORD`
- **호환성**: 구 `WORDPRESS_PASSWORD`·구 budget.json 자동 마이그레이션, 기존 STEP 1~12 의미 보존
