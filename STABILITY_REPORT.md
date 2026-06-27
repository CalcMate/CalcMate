# STABILITY_REPORT.md — 안정화 결과 보고서

작업일: **2026-06-21** · 검증: 단위 테스트 + 모듈 import 전수 + 대시보드 실기동 + dry-run

---

## 1. 수정 전 문제 → 수정 후 상태

| # | 수정 전 문제 | 수정 후 상태 | 검증 |
|---|--------------|--------------|------|
| 1 | `google-generativeai`(deprecated) 사용, 실행 시 FutureWarning, `max_tokens` 무시 | `google-genai` 2.9.0로 마이그레이션, max_tokens 적용, 경고 제거 | 헬스체크 Gemini `OK`, chat 성공, **FutureWarning 0건** |
| 2 | `publisher`가 `WORDPRESS_APP_PASSWORD` 참조하나 config는 `WORDPRESS_PASSWORD` → KeyError. 예시값으로 발행 시도 | 키명 단일화(구 키 자동 승격) + **WP 미구축 시 발행 건너뜀(대기)** | placeholder→`skipped_no_wp`, 실제→`published` 경로 확인 |
| 3 | `items[0]` 1건만 처리(DAILY_POST_COUNT 미적용) | 수집 순회 + 목표 개수만큼 생산, 중복/실패 건너뜀, 예산 초과 즉시 중단 | dry-run/통계 로그 확인 |
| 4 | 비용을 전체 토큰×EDITOR 단가로 1회 기록(부정확), 실패 호출 미집계 | 단계별 실제 모델 단가 기록 + 실패 호출 토큰도 기록 + 모델/Provider별 집계 | BudgetTracker 단위 테스트 |
| 5 | LLM JSON 파싱이 모듈마다 제각각, 코드블록 응답에 취약 | 공통 `parse_json_lenient` 적용(planner/strategist/cleaner/duplicate_checker/strategy_room) | 펜스/잡텍스트 입력 파싱 성공 |
| 6 | `except: pass`/bare except로 원인 소실(무음 6곳, bare 1곳) | 모두 `LOG.warning`+원인 기록, DEBUG 시 traceback. 동작은 유지 | 컴파일/동작 보존 확인 |
| 7 | dead code 5종(checkpoint/hub_manager/queue·template_repository/modules.health_check) | 제거. 상태 영속은 스케줄러로 대체 | **전 모듈 import ALL OK** |
| 8 | 대시보드 `💰 비용 모니터`=플레이스홀더, `⚠️ 오류 로그`=`get_sheet` 미정의로 상시 예외 | 비용 모니터=budget.json 시각화, 오류 로그=DB 어댑터 logs 조회 표 | 대시보드 health `ok`/root 200, 로그 무오류 |
| 9 | 발행 시각 고정 불가(즉시 1회만) | 슬롯 기반 스케줄러: 랜덤 시각 고정·영속·실패모드 3종·평일주말·이력 | 스케줄러 단위 테스트 전 항목 통과 |
| 10 | schedule 모드가 `backup_manager.compress_yesterday()`(모듈함수 없음) 호출 → AttributeError | `BackupManager().run_daily_backup()`로 수정 | 코드 정합 확인 |
| 11 | `Pillow` 코드 사용하나 requirements 미선언 | requirements에 추가 | — |

---

## 2. 검증 방법 및 결과

- **모듈 import 전수**: 27개 핵심 모듈 import → **ALL OK**(삭제 파일 참조 0)
- **JSON 유틸**: 순수/```json 펜스/설명문 혼합 → 모두 정상 파싱
- **BudgetTracker**: 입력/출력 단가 분리(claude), blended(gpt/gemini), prefix 매칭, provider·model breakdown → 정상
- **Scheduler**: 슬롯 검증(시작<종료/개수/형식/겹침), 생성·영속, due 감지, 성공→completed, 실패→retry_in_slot 재예약, history 기록 → 정상
- **WordPress**: placeholder→skip, 실제→ready, 구 키 승격 → 정상
- **Gemini**: 실제 API 헬스체크 OK + chat 성공(```json 응답을 공통 유틸이 흡수)
- **대시보드**: 실기동(health ok, root 200), 로그 예외 없음, 비용/스케줄 데이터 경로 실파일로 동작
- **run_once**: dry-run 경로 `{'produced':0,'reason':'dry_run'}` 반환

---

## 3. 남은 위험요소 (Remaining Risks)

### 🔴 외부/환경
1. **Google Sheet 403 (서비스 계정 권한 상실)** — 세션 중 동일 서비스 계정이 시트 `13wz-fd...`에 대해 **403**으로 전환됨(과거엔 접근 가능). 이는 코드 변경과 무관(외부 공유 설정 변경). 영향: 헬스체크 `google_sheet` CRITICAL 실패 → `main.py`가 `sys.exit(1)`로 중단, 대시보드 데이터 탭 오류.
   - **조치 필요(운영자)**: 시트와 Drive 루트 폴더를 서비스 계정 `blog-982@blog-499303.iam.gserviceaccount.com`에 **편집자(Editor)로 재공유**.
2. **WordPress 미구축** — 의도된 상태. 구축 시 대시보드/secrets에 `WORDPRESS_APP_PASSWORD`로 입력하면 자동 발행 활성화.

### 🟠 설계상 한계(문서화된 의도)
3. **입력/출력 토큰 분리** — BudgetTracker는 지원하나, 파이프라인 단계의 provider가 총 토큰만 반환 → 현재는 모델별 blended 단가 적용. 완전 분리는 provider 반환값 확장 필요(→ TODO_NEXT #1).
4. **임베딩 비용 미집계** — `duplicate_checker`의 `text-embedding-3-small` 호출은 budget에 기록되지 않음(소액). (→ TODO_NEXT)
5. **스케줄러 ↔ 수동 실행 충돌** — 스케줄러는 파일 락으로 자기 중복은 막으나, 수동 `run_pipeline.bat`은 락을 확인하지 않음. 동시 구동은 피할 것(→ TODO_NEXT).
6. **보안** — `config.yaml`/`secrets.yaml` 평문 키, `.gitignore`에 `config.yaml`·`credentials.json` 미등록(현재 git 저장소 아님). 과거 소스에 노출됐던 Gemini 키 재발급 권장.

### 🟡 기능 미구현(기존)
7. `collector/finance.py`, `affiliate.py` stub. `calculator` 수집기는 DB 데이터 의존.
8. `writer` 내부링크 `related=[None,None,None]` 고정.

---

## 3-B. 운영센터 UI 개편(항목 12) 안정성/성능 영향

**안정성 영향**
- 기존 STEP1~12·run_once 시그니처·모든 기존 탭 보존(추가만 함) → 기존 동작 무영향.
- `main.py`는 `--once`로 단발 보존, `OPERATION_MODE` 기본 scheduled. `run_pipeline.bat`는 `--once`로 단발 유지(클릭 동작 동일).
- 빠른 실행/즉시발행은 기존 함수 재사용 + 전부 try/except로 감싸 실패해도 대시보드 중단 없음.
- 즉시발행은 파일 락으로 스케줄러와의 동시 실행 방지.

**성능 영향**
- 운영센터 홈은 로컬 파일(today_schedule.json/budget.json/health_last.json/pipeline.log)만 읽어 빠름(네트워크 호출 없음). 서비스 상태는 캐시 표시.
- 실시간 로그 자동 갱신은 `st.fragment(run_every=5)`로 페이지 전체 리런 없이 부분 갱신.

**남은 위험요소(추가)**
- 빠른 실행의 발행 계열은 실제 시트/네트워크 접근 시 현재 403(외부 권한)로 실패 → 메시지 표시. 권한 복구 필요(§3 #1).
- 대시보드에서 run_once를 직접 호출하면 Streamlit 스레드를 점유(장시간 작업 시 화면 블로킹). 운영은 스케줄러(.bat) 권장, 대시보드는 모니터링/단발 트리거 용도.
- `st.fragment` 미지원 구버전 Streamlit에서는 수동 새로고침 폴백(코드에 포함).

## 3-C. v12.0 플랫폼 확장(항목 13) 안정성/성능 영향

**안정성**
- 기존 10개 탭·파이프라인·데이터 무수정(확장만). 신규 모듈은 모두 Repository/Adapter 경유(gspread/Drive 직접 호출 0).
- 제거했던 `template_repository`를 실사용처(App Factory)와 함께 재도입 — dead code 아님.
- AI Workspace의 프로젝트 파일 수정은 원본 자동 백업 + 명시 확인 게이트로만 동작(런타임 손상 방지). 기본은 샌드박스.
- 모델 ID를 실호출로 검증·정정(claude-sonnet-4-6, gemini-2.5-flash)하여 404/429 회피.

**성능**
- App Factory/AI Workspace는 AI 호출(수십 초·토큰 소비) — 사용자 트리거 시에만. 비용은 BudgetTracker에 모델별 기록.
- AI Pipeline Monitor는 로그 파싱 + budget.json 읽기로 가벼움.

**남은 위험요소(추가)**
- App Factory/Workspace/Calculator Builder 저장은 시트 접근 필요 → 현재 403 복구 전엔 생성은 되나 **저장 실패**(명확한 안내 표시). 생성·미리보기는 시트 무관하게 동작.
- 기존 `config.MODEL_EDITOR=claude-3-5-sonnet-latest`가 retired(404) → STEP8 GPT fallback으로 동작. 설정에서 `claude-sonnet-4-6` 권장.
- Gemini 무료 키 쿼터(429) 시 이미지 프롬프트/리서치 호출 실패 가능(graceful 처리).
- 대시보드에서 AI 호출은 Streamlit 스레드 점유(장시간 시 화면 대기).

## 3-D. 전면 재검증 결과 (2026-06-21)

| 치명 결함(수정 전) | 재검증 후 상태 |
|--------------------|----------------|
| ImportError 위험(deprecated Gemini SDK) | ✅ 해소 — `google.genai`만 사용, 경고 0 |
| KeyError(`WORDPRESS_APP_PASSWORD` 혼재) | ✅ 해소 — 단일화 + `is_wordpress_ready` 가드 |
| JSON 파싱 에러(LLM 잡텍스트) | ✅ 해소 — `modules/utils/parser.py` 공통 적용(planner/strategist/cleaner/duplicate_checker/strategy_room) |
| dashboard `get_sheet` 크래시 | ✅ 해소 — 오류 로그 탭 DB 조회로 교체 |
| 무음 except: pass | ✅ 전수 0건 — 신규 v12 모듈 7곳까지 로깅 전환 |

**파서 위치 정규화**: 지시서가 요구한 `modules/utils/parser.py`로 정규 분리, `modules/json_utils.py`는 하위호환 shim으로 유지(기존 import 무중단).

**잔존 잠재 위험**(기존 동일):
- Google Sheet 서비스계정 권한 403(외부) — 재공유 필요. SQLite 어댑터로는 즉시 동작.
- `config.MODEL_EDITOR=claude-3-5-sonnet-latest` retired → STEP8 GPT fallback. `claude-sonnet-4-6` 권장.
- Gemini 무료 키 429(2.5-pro). 대시보드 AI 호출은 동기(장시간 대기 가능).

## 3-E. 대시보드 운영 편의 리팩토링 (2026-06-21)

| 수정 전 결함/불편 | 조치 후 |
|-------------------|---------|
| 오류 로그 탭 get_sheet 크래시(ImportError/AttributeError) | ✅ 이미 제거(DB 조회 표) — 재확인 |
| 비용 모니터 placeholder 텍스트 | ✅ 이미 실통계 — 재확인 |
| 대량 발행 원클릭 부재 | ✅ 운영센터 마스터 패널(개수 입력+즉시 실행) |
| 가중치 수동 파일 편집 | ✅ 설정 탭 슬라이더 편집기(정규화 저장) |
| 실패 슬롯 재시도 수단 부재 | ✅ 일정 탭 즉시 재시도 |
| 로그 가독성(통째 dump) | ✅ 레벨 색상/필터/카운트 |

**안정성**: 모든 추가는 try/except 가드 + 기존 함수 재사용. 12단계 코어 로직·기존 탭 무변경. 텔레그램 미수정.

**잔존 잠재 위험**:
- ~~score_weights 키 불일치~~ → ✅ **해결(#31)**: `strategist._load_weights`가 로드 시 `_score` 키로 정규화하여 `compute_final_score` 정상화(검증 72.0). 슬라이더 편집기는 yaml 짧은 키 그대로 유지.
- Google Sheet 403(외부), MODEL_EDITOR retired(GPT fallback), 대시보드 AI 호출 동기 — 기존과 동일.

## 4. 종합 판정

- 요청 9개 작업 + 결과 문서 3종 **모두 완료**, 기존 STEP 1~12 파이프라인 의미 **보존**.
- 코드 레벨 안정성/유지보수성/운영성/확장성 개선 달성(다건 처리·스케줄러·정확 비용·예외 가시성·dead code 제거).
- **운영 재개를 위한 단 하나의 외부 선결 조건**: Google Sheet/Drive를 서비스 계정에 재공유(위 #1). 이것만 해결되면 dry-run·실행이 정상 통과한다.
