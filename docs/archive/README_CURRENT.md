# README_CURRENT.md — 블로그자동화 v12 실제 구현 현황

> 이 문서는 **기존 README.md를 참고하지 않고 실제 소스 코드를 직접 분석**하여 작성되었습니다.
> 작성일: **2026-06-21** / 분석 대상: `C:\Users\연수\Desktop\블로그자동_v12`
> 각 기능은 **✅ 구현 완료 / 🟡 부분 구현 / ❌ 미구현(stub·dead code)** 으로 구분합니다.

---

## 0. 한눈에 보기 (TL;DR)

- **핵심 12단계 파이프라인은 거의 전부 실제 코드로 구현**되어 있고, 실제 외부 API(OpenAI·Anthropic·Gemini·Pollinations·WordPress REST·Google Sheets·Google Drive)를 호출합니다. 가짜 더미 동작 모듈은 거의 없습니다.
- **STEP 11(WordPress 발행)은 현재 미동작**합니다. 단, 이는 **WordPress를 아직 구축하지 않은 의도된 상태**(`WORDPRESS_URL`/계정이 더미값)이므로 정상입니다. 추후 실제 WordPress 연결 시 **코드의 키 이름 불일치(`WORDPRESS_APP_PASSWORD` vs config `WORDPRESS_PASSWORD`)를 먼저 고쳐야** 글로벌 경로 발행이 가능합니다(잠재 버그).
- **콘텐츠 출력은 HTML + WebP 이미지 + 발행미리보기 .txt**가 전부입니다. **DOCX/콘텐츠 ZIP 출력은 없습니다** (ZIP은 로그·백업 전용).
- 이미지 생성은 **DALL-E/Imagen이 아니라 Pollinations 무료 엔진**입니다.
- `finance`/`affiliate` 수집기, `💰 비용 모니터` 탭, `⚠️ 오류 로그` 탭, `checkpoint`/`hub_manager`, `score_weights` 배선, `postgres`/`s3` 어댑터는 **미구현 또는 dead code**입니다.

---

## 1. 현재 구현된 기능 목록

| 구분 | 기능 | 상태 |
|------|------|------|
| 수집 | RSS 수집(정부정책 korea.kr) — `rss_collector` / `collector/policy` | ✅ |
| 수집 | 사이트별 수집기 라우팅(`collector/factory`, site_type) | ✅ (단 사이트 미등록 시 우회) |
| 수집 | 계산기 키워드 수집(`collector/calculator`) | 🟡 (DB 데이터 의존) |
| 수집 | 금융/제휴 수집기(`finance`/`affiliate`) | ❌ stub |
| 정제 | 행정용어 정제(`cleaner.clean_rss_item`, GPT) | ✅ |
| 중복검사 | 임베딩+코사인 3단계 판정(`duplicate_checker`) | ✅ |
| 전략 | M0 오케스트레이터 전략 + 점수엔진(`strategist`) | ✅ |
| 기획 | M1 SEO 기획(`planner`, Gemini) | ✅ |
| 작성 | M3 본문 초안(`writer`, source_type별 프롬프트) | ✅ |
| 검수 | M4 검수 + fallback(`editor`, Claude→GPT) | ✅ |
| 이미지 | 썸네일/본문 이미지 생성(`image_generator`, Pollinations) | ✅ |
| 저장 | Google Drive 업로드(`adapters/storage/drive`) | ✅ |
| 발행 | WordPress REST 발행(`publisher`) | 🟡 코드는 완성, 설정 버그로 상시 실패 |
| 기록 | Google Sheets 행/로그 기록(`sheet_sync` → adapters/repositories) | ✅ |
| 데이터 | DB 어댑터(Sheets/SQLite) | ✅ / Postgres ❌ stub |
| 데이터 | Storage 어댑터(Drive/Local) | ✅ / S3 ❌ stub |
| 운영 | 예산 선차단(`logger.BudgetTracker`) | ✅ (비용은 근사치) |
| 운영 | 헬스체크(`health_check.py`) | ✅ |
| 운영 | 텔레그램 알림(`telegram_notifier`) | ✅ |
| 운영 | DLQ 실패 누적 알림(`main._check_dlq`) | 🟡 알림만, 상태전이 X |
| 운영 | 백업(config/sheets/sqlite/outputs → zip)(`backup_manager`) | ✅ |
| 운영 | 스케줄 모드(무한 반복)(`main --schedule`) | ✅ |
| 분석 | 전략회의실(`strategy_room`, 운영 분석 보고서) | ✅ (메인 파이프라인엔 미포함) |
| 설정 | 초기 설정 마법사 6단계(`setup_wizard`) | ✅ |
| 설정 | Google Sheets/Drive 자동 생성(`google_provisioner`) | ✅ |
| UI | Streamlit 대시보드 8탭(`dashboard.py`) | 🟡 5개 동작 / 1개 표시전용 / 1개 플레이스홀더 / 1개 버그 |
| 운영 | 체크포인트 복구(`checkpoint`) | ❌ dead code(`clear()`만 호출) |
| 운영 | 허브 큐 생성(`hub_manager`) | ❌ dead code(호출처 없음) |

---

## 2. 실제 동작하는 기능 (✅ 검증된 동작)

- **RSS 수집** — `feedparser`로 `RSS_SOURCE_LIST`(현재 korea.kr 정책 RSS)를 실제로 가져옴.
- **AI 4단계(정제·전략·기획·작성·검수)** — OpenAI/Gemini/Anthropic을 실제 호출. fallback(`editor`)도 실제 동작.
- **중복검사** — OpenAI `text-embedding-3-small` 임베딩 + 코사인 유사도, 경계구간은 GPT 판정.
- **이미지 생성·업로드** — Pollinations로 WebP 생성 → `data/outputs/`에 저장 → Google Drive 업로드(공개 URL).
- **Google Sheets/Drive 자동 생성** — 마법사 2단계가 실제 폴더 4개 + 시트 7탭 + 헤더/서식 생성(`google_provisioner.provision`).
- **헬스체크** — OpenAI/Claude/Gemini/Sheet/Drive/서비스계정 연결을 실제 점검. CRITICAL 실패 시 `sys.exit(1)`.
- **예산 선차단** — 실행 시작 시 일/월 누적 비용이 한도 초과면 텔레그램 경고 후 즉시 중단.
- **대시보드 동작 탭** — 📊 현황 / 📋 발행 목록 / 🧠 전략회의실 / 🔧 설정 / 🏥 헬스체크 (Sheets 라이브 읽기 또는 config R/W).
- **전략회의실** — `gpt-4o`로 운영 데이터 분석 JSON 생성(`_parse_json_lenient`로 코드블록/잡텍스트 방어).
- **배치 실행 스크립트** — `run_dryrun.bat` 등(아래 8장) 실제 구동 확인됨.

> ⚠️ **WordPress 발행(STEP 11)은 "실제 동작"에서 제외**됩니다. 코드는 진짜 REST POST를 하지만 **WordPress가 아직 구축되지 않아(의도된 미설정)** 발행 대상이 없습니다(3장 참조).

---

## 3. 미완성 기능 (🟡 부분 / ❌ 미구현)

### 🟡 부분 구현
- **WordPress 발행(`publisher.py`)** — 코드는 완성된 REST POST이나 **WordPress를 아직 구축하지 않아 미동작(의도된 상태)**. `WORDPRESS_URL=https://example.com`, 계정 모두 더미값. 추후 실제 연결 시 주의할 **잠재 코드 버그 2건**: ① `publisher.py:34`가 `cfg["WORDPRESS_APP_PASSWORD"]`를 참조하나 config/마법사는 `WORDPRESS_PASSWORD`로 저장 → 글로벌 경로에서 `KeyError`(사이트별 등록 시엔 `site_repository`가 해당 키를 만들어줘서 회피됨). ② 이미지 URL을 `imgs['thumbnail_url']` 대괄호로 접근 → 이미지 실패 시 KeyError. (현재 `data/logs/pipeline.log`의 과거 크래시는 더미 설정 상태에서 발생한 것)
- **계산기 수집기(`collector/calculator.py`)** — 로직은 완성됐으나 `calculators` 시트/DB에 레코드가 있어야 산출. 현재 데이터 없으면 빈 리스트.
- **DLQ(`main._check_dlq`)** — 실패 타임스탬프를 `data/dlq/{id}.json`에 누적하고 임계 도달 시 텔레그램 경고만 함. **상태값을 "재처리대기"로 바꾸는 DB 전이는 없음**(별도로 `ArticleRepository.increment_fail`이 3회→재처리대기 전이를 갖지만 main의 except 경로에서 호출되지 않음). 또 예외 시 `마스터ID`가 비면 DLQ 파일이 안 생길 수 있음.
- **예산 비용 집계(`BudgetTracker`)** — 선차단은 동작하나 비용이 **근사치**: 가격표 하드코딩, 입/출력 토큰 미구분, 모델명 일부 불일치(`claude-sonnet-4-5` vs 실제 `gpt-4o` 등), 성공 경로에서 1회만 전체 토큰을 EDITOR 단가로 환산, 실패 호출 비용 미집계.
- **대시보드(`dashboard.py`)** — 8탭 중 일부만 완전 동작(4장 표 참조).

### ❌ 미구현 / Dead code
- **`collector/finance.py`, `collector/affiliate.py`** — `print("stub") + return []`. 완전 미구현.
- **`💰 비용 모니터` 탭** — 본문이 `st.info("비용 모니터 기능이 정상 가동 중입니다.")` 한 줄뿐. 집계 로직 없음(메시지는 사실과 다름).
- **`⚠️ 오류 로그` 탭** — `from modules.sheet_sync import get_sheet` 호출하나 **`get_sheet` 함수가 존재하지 않음** → 항상 예외 → "로그 로드 오류"만 표시.
- **`modules/checkpoint.py`** — `acquire_lock/load/save`가 어디서도 호출되지 않음. `main.py:225`의 `cp.clear()` 1곳만 사용 → docstring의 "체크포인트 복구"는 실제 미작동.
- **`modules/hub_manager.py`** — `generate_hub_queue/register_hub` 호출처 전무. 완전 dead code.
- **`adapters/db/postgres_adapter.py`, `adapters/storage/s3_adapter.py`** — 명시적 stub. 모든 메서드 `NotImplementedError`, `read_test() → False`.
- **`repositories/queue_repository.py`, `template_repository.py`** — 코드는 있으나 인스턴스화/호출되는 곳이 없음(dead code). (`app_factory_*` 시트 탭만 생성됨)
- **`modules/health_check.py`** — `modules/` 안의 버전은 미사용. 실제 사용되는 건 **루트 `health_check.py`**.
- **`config/score_weights.yaml`** — 파일·주석은 "대시보드에서 조정"이라 하나 **dashboard/strategist 어디서도 로드하지 않음**(strategist는 자체 `_load_weights`로 별도 로드 시도). 사실상 고아 설정.
- **내부 링크** — `writer`에 `related=[None,None,None]` 하드코딩 전달(`main.py:162`) → 내부링크 블록 항상 비어 있음.

---

## 4. 사용 중인 AI 모델 (config.yaml + ai_provider.py 기준)

| 역할 | STEP | Provider | 모델(config 값) |
|------|------|----------|------|
| Cleaner(정제) | 2 | OpenAI | `gpt-4o` (`MODEL_CLEANER`) |
| 중복검사 | 3 | OpenAI | `text-embedding-3-small` + `gpt-4o`(경계 판정) |
| Orchestrator(M0 전략) | 5 | OpenAI | `gpt-4o` (`MODEL_ORCHESTRATOR`) |
| Planner(M1 SEO) | 6 | Gemini | `gemini-2.5-flash` (`MODEL_PLANNER`) |
| Writer(M3 본문) | 7 | OpenAI | `gpt-4o-mini` (`MODEL_WRITER`) |
| Editor(M4 검수) | 8 | Anthropic | `claude-3-5-sonnet-latest` (`MODEL_EDITOR`) |
| Editor Fallback | 8 | OpenAI | `gpt-4o` (`MODEL_EDITOR_FALLBACK`) |
| Image(이미지) | 10 | Pollinations 무료 엔진 | API 키 없음 (`IMAGE_PROVIDER: free_pollinations`) |
| Strategy Room | 별도 | OpenAI | `gpt-4o` (`MODEL_ORCHESTRATOR`) |

- **provider 라우팅**: `ai_provider.build_provider_for_role()`은 `sites` 탭의 `research_ai/writing_ai/review_ai` 프로필(`AI_PROFILE_MAP`)이 있으면 우선 적용, 없으면 config.yaml의 `*_PROVIDER`/`MODEL_*`로 fallback.
- `AI_PROFILE_MAP`에는 `gemini_flash/gemini_pro/gpt4o/gpt4o_mini/claude_sonnet(claude-sonnet-4-6)/claude_haiku/claude_opus` 등이 매핑되어 있음.
- ⚠️ Gemini 호출은 `max_tokens`를 전달하지 않음(무시됨).

---

## 5. 사용 중인 API / 외부 서비스

| API/서비스 | 용도 | 호출 위치 |
|------------|------|-----------|
| **OpenAI API** | 정제·전략·작성·중복검사·임베딩·검수 fallback | `ai_provider.GPTProvider`, `duplicate_checker` |
| **Anthropic API** | 검수(M4) | `ai_provider.ClaudeProvider` |
| **Google Generative AI(Gemini)** | SEO 기획(M1) | `ai_provider.GeminiProvider` |
| **Pollinations** (`image.pollinations.ai`) | 이미지 생성(무료) | `image_generator._generate_free_image` |
| **WordPress REST API** (`/wp-json/wp/v2/posts`) | 글 발행(Basic Auth = Application Password) | `publisher._wordpress_api` |
| **Google Sheets API** (gspread) | DB(마스터_DB/운영로그/sites 등) | `adapters/db/sheets_adapter` |
| **Google Drive API** (v3) | 이미지/백업 업로드, 공개 URL | `adapters/storage/drive_adapter`, `google_provisioner` |
| **Telegram Bot API** | 운영 알림 | `telegram_notifier.send` |

- 인증: Google은 **서비스 계정**(`credentials.json`), WordPress는 **Application Password**(Basic Auth).
- 미사용/스텁: **AWS S3**(`boto3` 미사용 stub), **PostgreSQL**(`psycopg2` 주석처리 stub).

---

## 6. 실행 흐름도

### 6-1. 진입점 (`main.py main()`)
```
main()
 ├─ parse_args(): --dry-run | --schedule | --strategy-room | --instance
 ├─ load_config(config/config.yaml)  → ConfigError/FileNotFound 시 종료
 ├─ health_check.run(cfg)            → CRITICAL 실패 시 sys.exit(1)
 ├─ --dry-run        → 검증만 하고 종료
 ├─ --strategy-room  → run_strategy_room({}, cfg) 후 JSON 출력
 ├─ --schedule       → run_once() 반복 + 백업, RUN_INTERVAL_HOURS 간격 무한루프
 └─ (기본)           → run_once(cfg)
```

### 6-2. 핵심 12단계 (`main.py run_once()`)
```
[예산 체크] budget.check_budget() → 초과 시 텔레그램 알림 후 중단
STEP 1  수집     SiteManager.get_active_sites() → site별 get_collector().collect()
                 (사이트 없으면 rss_collector.collect() 레거시 fallback)  ※items[0] 1건만 처리
STEP 2  표준화   cleaner.clean_rss_item()                         [OpenAI gpt-4o]
STEP 3  1차중복  sheet_sync.get_recent_titles() + duplicate_checker.check_duplicate()
                 → 중복이면 "보류" 기록 후 종료                    [OpenAI 임베딩]
STEP 4  최근로드 history_loader.load_recent_titles(30)
STEP 5  M0 전략  strategist.design_strategy()                     [OpenAI gpt-4o]
STEP 6  M1 SEO   planner.plan_seo() + 2차중복(seo_title)          [Gemini flash]
STEP 7  M3 작성  writer.write_draft()                             [OpenAI gpt-4o-mini]
STEP 8  M4 검수  editor.edit() (+fallback)                        [Claude → GPT]
STEP 9  파싱     cleaner.parse_html_body()  ([BODY_HTML_START]..[END])
STEP 10 이미지   image_generator.generate()                       [Pollinations → Drive]
STEP 11 발행     publisher.publish()  ← ★현재 KeyError로 실패     [WordPress REST]
STEP 12 기록     sheet_sync.append_row()/append_log(), budget.record(), cp.clear()
   └ 예외 시: 로그 기록 + 텔레그램 알림 + _check_dlq()(실패 누적)
```

---

## 7. 폴더 구조 설명

```
블로그자동_v12/
├─ main.py                  # 12단계 파이프라인 오케스트레이터(진입점)
├─ dashboard.py             # Streamlit 운영 대시보드(8탭)
├─ health_check.py          # ★실제 사용되는 헬스체크 (main/dashboard가 import)
├─ credentials.json         # Google 서비스 계정 키
├─ requirements.txt
├─ INSTALL.md / README.md   # 기존 문서(부정확할 수 있음 — 본 문서로 대체)
│
├─ config/
│   ├─ config.yaml          # 메인 설정(모델/예산/Google/WP/RSS 등)  ※평문 API키 포함
│   ├─ secrets.yaml         # wordpress_profiles / ai_keys (gitignore 대상)
│   └─ score_weights.yaml   # 점수 가중치(현재 대시보드 미배선)
│
├─ modules/
│   ├─ collector/           # 수집기 패키지
│   │   ├─ base.py factory.py
│   │   ├─ policy.py        # ✅ RSS 수집(실동작)
│   │   ├─ calculator.py    # 🟡 계산기 키워드(DB 의존)
│   │   ├─ finance.py       # ❌ stub
│   │   └─ affiliate.py     # ❌ stub
│   ├─ ai_provider.py       # OpenAI/Claude/Gemini 추상화 + 역할 라우팅
│   ├─ cleaner.py strategist.py planner.py writer.py editor.py   # AI 단계들
│   ├─ duplicate_checker.py history_loader.py
│   ├─ image_generator.py   # Pollinations 이미지
│   ├─ publisher.py         # WordPress REST 발행(★버그)
│   ├─ sheet_sync.py db_manager.py site_manager.py              # DB 브릿지
│   ├─ logger.py            # 로깅 + BudgetTracker
│   ├─ backup_manager.py telegram_notifier.py config_loader.py
│   ├─ strategy_room.py     # 전략회의실(분석)
│   ├─ setup_wizard.py google_provisioner.py                    # 초기 설정/프로비저닝
│   ├─ rss_collector.py     # 레거시 RSS(사이트 미등록 시 fallback)
│   ├─ checkpoint.py        # ❌ dead code
│   ├─ hub_manager.py       # ❌ dead code
│   └─ health_check.py      # ❌ 미사용(루트 버전이 사용됨)
│
├─ adapters/
│   ├─ db/      base.py factory.py sheets_adapter.py(✅) sqlite_adapter.py(✅) postgres_adapter.py(❌stub)
│   └─ storage/ base.py factory.py drive_adapter.py(✅) local_adapter.py(✅) s3_adapter.py(❌stub)
│
├─ repositories/
│   ├─ article_repository.py(✅사용) site_repository.py(✅사용) calculator_repository.py(🟡1곳)
│   └─ queue_repository.py(❌) template_repository.py(❌)        # dead code
│
├─ scripts/                 # 배치파일 + 보수 스크립트(8장)
└─ data/
    ├─ logs/      # pipeline.log, budget.json, health_last.json
    ├─ outputs/   # {id}_thumbnail.webp, {id}_body.webp, *_발행미리보기.txt
    ├─ dlq/       # {post_id}.json (실패 누적)
    └─ checkpoints/  # (checkpoint 미사용으로 사실상 비활성)
```

---

## 8. 배치파일 설명 (`scripts/`)

> 모두 한국어 Windows 환경 대응을 위해 **cp949 인코딩 + CRLF 줄바꿈**으로 정리되어 있으며, `activate.bat` 대신 **venv 실행파일을 직접 호출**(`.venv\Scripts\python.exe`)합니다. (2026-06-21 수정 — 13장 참조)

| 파일 | 동작 | 비고 |
|------|------|------|
| `install.bat` | Python 확인 → venv 생성 → 의존성 설치 → 대시보드 실행 | 최초 설치용 |
| `run_dryrun.bat` | `python main.py --dry-run` | 설정 검증/헬스체크만 (실발행 없음) ✅검증됨 |
| `run_pipeline.bat` | `python main.py` | **실제 파이프라인 1회 실행(발행 시도)** |
| `run_schedule.bat` | `python main.py --schedule` | `RUN_INTERVAL_HOURS` 간격 무한 반복 |
| `run_strategy_room.bat` | `python main.py --strategy-room` | 전략회의실 즉시 실행(콘솔에 JSON) ✅검증됨 |
| `run_dashboard.bat` | `streamlit run dashboard.py` | 웹 대시보드 구동 ✅검증됨 |
| `repair_google_setup.py` | (배치 아님, py) 기존 Sheet/Drive 누락 탭·폴더 보수 | 멱등·데이터 보존 (13장) |

---

## 9. 설정파일(config.yaml) 설명

| 키 | 현재값 | 설명 |
|----|--------|------|
| `RUN_MODE` | `wordpress` | 발행 모드 |
| `ADSENSE_MODE` | `pre` | pre=승인전(학술형)/post=승인후(마케팅형) → editor 프롬프트 분기 |
| `DAILY_POST_COUNT` | `1` | 하루 발행 목표(현재 코드는 1건만 처리) |
| `RUN_INTERVAL_HOURS` | `24` | 스케줄 모드 반복 간격 |
| `DAILY_AI_BUDGET` / `MONTHLY_AI_BUDGET` | `5` / `100` | 일/월 AI 예산(USD) — 선차단 기준 |
| `DLQ_THRESHOLD` | `3` | 실패 누적 임계(텔레그램 경고) |
| `DUPLICATE_THRESHOLD` | `0.85` | 중복 차단 임계(코사인) |
| `ORCHESTRATOR/PLANNER/WRITER/EDITOR_PROVIDER` | openai/gemini/openai/claude | 역할별 provider |
| `EDITOR_FALLBACK_PROVIDER` | openai | 검수 실패 시 대체 |
| `MODEL_*` | (4장 참조) | 역할별 모델명 |
| `IMAGE_PROVIDER` / `MODEL_IMAGE` | `free_pollinations` / 무료엔진 | 이미지 생성 |
| `IMAGE_SIZE` / `IMAGE_QUALITY` | `auto` / `standard` | 이미지 옵션 |
| `DB_ADAPTER` / `STORAGE_ADAPTER` | `sheets` / `drive` | 활성 어댑터 |
| `SQLITE_PATH` | `data/blog_auto.db` | sqlite 선택 시 경로 |
| `GOOGLE_SHEET_ID` / `GOOGLE_DRIVE_ROOT_ID` / `GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID` | (실제값) | Google 리소스 ID |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `credentials.json` | 서비스 계정 |
| `RSS_SOURCE_LIST` | `[korea.kr/.../policy.xml]` | 기본 RSS(레거시 경로) |
| `RSS_MAX_ITEMS_PER_SOURCE` | `20` | 소스당 최대 수집 |
| `WORDPRESS_URL/USERNAME/PASSWORD` | example.com/temp/더미 | **WordPress 미구축(의도된 더미값)**. 연결 시 키명 `WORDPRESS_PASSWORD`↔코드 `WORDPRESS_APP_PASSWORD` 불일치 정리 필요 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 비어있음 | 알림 미설정 |
| `OPENAI/CLAUDE/GEMINI_API_KEY` | (실키, 평문) | ⚠️ 평문 저장 보안주의 |
| `ENABLE_STRATEGY_ROOM` | `true` | 전략회의실 on/off |
| `AUTO_TOPIC_EXPANSION` | `false` | 자동 주제 확장 플래그 |

- 검증: `config_loader._validate`가 `MODEL_*`(5종)·`WORDPRESS_URL` 공란이면 `ConfigError`.
- `secrets.yaml`(`wordpress_profiles`, `ai_keys`)은 `SiteRepository`만 로드(메인 config와 별도).

---

## 10. 로그 시스템 설명

- **로거**(`modules/logger.py get_logger`): 레벨 `DEBUG`, 포맷 `%(asctime)s [%(levelname)s] %(message)s`. **콘솔 + 파일**(`data/logs/pipeline.log`) 동시 출력. (docstring은 "JSON 구조화"라 하나 실제는 **평문 텍스트**)
- **예산 로그**(`BudgetTracker`): `data/logs/budget.json`에 daily/monthly + provider별 비용 누적. 가격표는 코드 하드코딩(근사치, 3장 참조).
- **헬스체크 결과**: `data/logs/health_last.json`.
- **운영 로그(시트)**: 파이프라인 실행 결과가 `sheet_sync.append_log` → `운영로그` 탭에 행으로 기록(로그ID/실행일시/마스터ID/대상정책명/가동결과/실패모듈/오류내용/발행URL/소요시간/토큰합계).
- **DLQ 로그**: `data/dlq/{post_id}.json` (실패 타임스탬프 배열).
- **대시보드 📡 실시간 로그 탭**: `data/logs/pipeline.log` 마지막 100줄 표시.

---

## 11. 출력물 종류

| 출력물 | 형식 | 생성 위치 | 비고 |
|--------|------|-----------|------|
| 본문 콘텐츠 | **HTML 문자열** | writer→editor→`cleaner.parse_html_body` | WordPress content로 전송 |
| 썸네일/본문 이미지 | **WebP 파일** | `data/outputs/{id}_thumbnail.webp`, `{id}_body.webp` | 512×512 / 800×450 |
| 이미지 공개 URL | Google Drive `uc?id=` URL | `drive_adapter.save_file` | 업로드 실패 시 로컬경로 폴백 |
| WordPress 게시물 | REST 게시물 | `publisher`(현재 실패) | status=publish |
| 발행 미리보기 | **.txt** | `data/outputs/*_발행미리보기.txt` | 발행 성공 시에만 |
| 시트 기록 | Google Sheets 행 | `마스터_DB`/`운영로그` | 발행/로그 |
| 백업 | **ZIP** | `data/backups/YYYY-MM-DD.zip` | config/sheets-csv/sqlite/outputs(.txt) — **콘텐츠 아님, 운영 백업용** |

> ❌ **DOCX 출력은 코드 어디에도 없습니다.** ❌ **콘텐츠 묶음 ZIP도 없습니다**(ZIP은 백업 전용).

---

## 12. 향후 확장 포인트

1. **WordPress 발행(WordPress 구축 후 진행)** — 현재는 WP 미구축으로 보류. 구축 시: ① 실제 도메인/Application Password 입력, ② `publisher.py`의 `WORDPRESS_APP_PASSWORD` ↔ config `WORDPRESS_PASSWORD` 키 통일, ③ 이미지 URL `.get()` 안전 접근.
2. **수집기 완성** — `finance`/`affiliate` 수집기 실제 구현, 계산기 수집을 위한 `calculators` 시트 데이터 입력.
3. **다건 처리** — 현재 `items[0]` 1건만 처리 → `DAILY_POST_COUNT`만큼 루프 확장.
4. **체크포인트/재시도 배선** — `checkpoint.save/load/acquire_lock` 실제 연결, DLQ를 상태전이(`increment_fail`)와 통합.
5. **비용 모니터 탭 구현** — `budget.json`을 읽어 일/월/provider별 비용 시각화(현재 플레이스홀더).
6. **오류 로그 탭 수정** — `sheet_sync.get_sheet` 추가 또는 `get_all_posts`/어댑터 직접 사용으로 교체.
7. **score_weights 배선** — 대시보드 편집 UI + strategist 로드 연결.
8. **어댑터 확장 실구현** — `postgres_adapter`, `s3_adapter` 채우기(현재 stub). DB를 sqlite/postgres로 전환 가능하게.
9. **dead code 정리/활용** — `hub_manager`(허브 큐), `queue/template_repository`(앱 팩토리) 연결 또는 제거.
10. **보안** — API 키를 config.yaml 평문에서 분리(secrets/환경변수). (`test_img.py` 하드코딩 키는 파일 삭제로 해결, 노출됐던 Gemini 키는 재발급 권장)
11. **비용 정확화** — 입/출력 토큰 분리 단가, 단계별 실제 모델로 기록.

---

## 13. 최근 수정된 내용

### 2026-06-21 (이번 작업 세션)
- **배치파일 6종 정상화**(`scripts/*.bat`): LF→CRLF, UTF-8→cp949 인코딩 변경, `activate.bat` 의존 제거 후 venv 실행파일 직접 호출(`.venv\Scripts\python.exe`/`streamlit.exe`). 한글 경로에서 `'d'/'블' is not recognized` 파싱 에러 및 `feedparser` 모듈 미인식 문제 해결.
- **전략회의실 JSON 파서 견고화**(`modules/strategy_room.py`): `_parse_json_lenient()` 추가 — 빈 응답 방어, ```` ```json ```` 코드블록 제거, 앞뒤 잡텍스트 제거 후 `{`~`}` 추출. LLM이 순수 JSON을 안 줄 때 `{}`로 빠지던 `Expecting value: line 1 column 1` 문제 해결.
- **대시보드 전략회의실 탭 신설**(`dashboard.py`): `🧠 전략회의실` 탭 추가 — 실행 버튼, 운영 데이터 자동 수집, 요약·전환조건·추천목록·토큰·원본 JSON 패널, 비활성/빈결과 안전 처리.
- **Google Sheet/Drive 구조 보수**(`scripts/repair_google_setup.py` 신규): 마법사 자동생성이 미완이던 상태를 멱등 복구 — 시트 누락 탭 4개 추가(총 7탭), 빈 탭 헤더 기록(기존 `운영로그` 데이터 보존), Drive `images/backups/placeholders` 폴더 생성, `GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID` 교정.

### 그 이전 (파일 수정시각 기준)
- `2026-06-20` — `image_generator.py`(Pollinations 무료 엔진), `sheet_sync.py`(어댑터 브릿지 전환). (`test_img.py`는 2026-06-21 삭제됨)
- `2026-06-20` — `main.py`, `editor.py`, `writer.py`, `planner.py`, `strategist.py`, `ai_provider.py`, `site_manager.py` 등 코어 파이프라인.
- `2026-06-19` — `google_provisioner.py`, `setup_wizard.py`, `db_manager.py` 등 설정/데이터 레이어.

---

## 부록 — 알려진 버그 우선순위

| 우선순위 | 위치 | 증상 |
|---------|------|------|
| ⏸ 보류(의도됨) | config WORDPRESS_* | WordPress 미구축 → 더미값. 정상 상태(구축 후 설정 예정) |
| 🟠 잠재 | `publisher.py:34` | WP 연결 시 `WORDPRESS_APP_PASSWORD`↔`WORDPRESS_PASSWORD` 키 불일치로 글로벌 발행 KeyError(지금은 무영향) |
| 🟠 높음 | `dashboard.py` ⚠️오류로그 탭 | `sheet_sync.get_sheet` 미정의 → 탭 사용 불가 |
| 🟠 높음 | `dashboard.py` 💰비용모니터 탭 | 플레이스홀더(st.info만), 메시지가 사실과 다름 |
| 🟡 중간 | `checkpoint`/`hub_manager` | dead code(복구·허브 기능 미작동) |
| 🟡 중간 | `config.yaml` | API 키/WP 비번 평문 저장(보안). (`test_img.py` 하드코딩 키는 삭제로 해결) |
| 🟡 중간 | `duplicate_checker` | 매 호출 전체 재임베딩(비용/지연) |
| ⚪ 낮음 | `writer` 내부링크 | `related=[None,None,None]` 고정 → 내부링크 미생성 |
```
