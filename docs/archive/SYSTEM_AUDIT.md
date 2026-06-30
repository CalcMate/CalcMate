# SYSTEM_AUDIT.md — 블로그자동화 v12 시스템 감사

> **실제 코드 스캔 기준. 추측 없음.** 모든 항목은 grep/파일 카운트/코드 읽기로 검증했으며 근거를 `파일:라인`으로 명시합니다.
> 스캔일: **2026-06-21** / 대상: `C:\Users\연수\Desktop\블로그자동_v12` (`.venv`, `__pycache__` 제외)

---

## 1. 전체 파일 수

| 구분 | 수 |
|------|----|
| **전체 파일** (.venv/.git/__pycache__ 제외) | **78** |
| Python 파일 | **55** (총 **4,099** LOC) |
| 배치파일(.bat) | 6 |
| YAML(.yaml) | 3 (config / secrets / score_weights) |
| Markdown(.md) | 4 (README, INSTALL, README_CURRENT, SYSTEM_AUDIT) |
| JSON(.json) | 3 (credentials 등) |
| 이미지(.webp) | 4 (data/outputs 테스트 산출물) |
| 기타 | txt 1, log 1, .gitignore 1 |

> 참고: 현재 **git 저장소 아님**(`.git` 없음). `.gitignore`는 `config/secrets.yaml`만 등록.

---

## 2. Python 모듈 구조

```
(루트)
  main.py            12단계 파이프라인 오케스트레이터 (진입점)
  dashboard.py       Streamlit 대시보드 (8탭)
  health_check.py    ★실사용 헬스체크 (main/dashboard가 import)
  (test_img.py 는 2026-06-21 삭제됨)

modules/  (코어 32개)
  ├ collector/       base, factory, policy(✅), calculator(🟡), finance(❌stub), affiliate(❌stub)
  ├ ai_provider      OpenAI/Claude/Gemini 추상화 + 역할 라우팅
  ├ cleaner strategist planner writer editor   AI 단계
  ├ duplicate_checker history_loader
  ├ image_generator publisher
  ├ sheet_sync db_manager site_manager          DB 브릿지
  ├ logger backup_manager telegram_notifier config_loader
  ├ strategy_room                                전략회의실(분석)
  ├ setup_wizard google_provisioner              초기 설정/프로비저닝
  ├ rss_collector                                레거시 RSS(fallback)
  ├ checkpoint(❌거의 미사용) hub_manager(❌deadcode) health_check(❌미사용)

adapters/
  ├ db/      base, factory, sheets_adapter(✅), sqlite_adapter(✅), postgres_adapter(❌stub)
  └ storage/ base, factory, drive_adapter(✅), local_adapter(✅), s3_adapter(❌stub)

repositories/
  ├ article_repository(✅사용) site_repository(✅사용) calculator_repository(🟡1곳)
  └ queue_repository(❌deadcode) template_repository(❌deadcode)

scripts/   *.bat (6) + repair_google_setup.py
```

**아키텍처 패턴**: `sheet_sync`/`db_manager`/`site_manager`(브릿지) → `repositories/*`(도메인) → `adapters/db|storage/*`(저장소) → `factory`가 `cfg["DB_ADAPTER"]`(=sheets), `cfg["STORAGE_ADAPTER"]`(=drive)로 구현체 선택.

---

## 3. 사용 중인 라이브러리

### requirements.txt 선언 (12개)
`openai`, `anthropic`, `google-generativeai`, `google-auth`, `google-api-python-client`, `gspread`, `feedparser`, `pyyaml`, `numpy`, `requests`, `streamlit`, `pandas`

### 실제 import 검증 (third-party)
| 라이브러리 | import 횟수 | 사용처 |
|-----------|-----------|--------|
| google(.oauth2/.generativeai) | 9 | 인증·Gemini |
| googleapiclient | 7 | Drive/Sheets API |
| requests | 5 | WordPress/Pollinations/Telegram |
| openai | 4 | GPT·임베딩 |
| anthropic | 3 | Claude |
| streamlit | 2 | 대시보드/마법사 |
| feedparser | 2 | RSS |
| pyyaml(yaml) | 5 | 설정 |
| gspread | 1 | Sheets 어댑터 |
| numpy | 1 | 코사인 유사도 |
| pandas | 1 | 대시보드 표 |
| PIL(Pillow) | 1 | 이미지 저장(webp) |

> ⚠️ **불일치**: `PIL`(Pillow)을 `image_generator.py`에서 사용하나 **requirements.txt에 `Pillow` 미선언**. (현재 .venv엔 설치돼 있어 동작) `boto3`/`psycopg2`는 stub이라 미사용·미선언.

### 표준 라이브러리
`pathlib, datetime, json, uuid, io, abc, sys, shutil, zipfile, urllib, time, sqlite3, re, os, csv, logging`

---

## 4. 미사용 파일 (외부 참조 0건 — grep 검증)

| 파일 | 근거 |
|------|------|
| `modules/health_check.py` | 외부 import **0건**(`modules.health_check` 참조 0). 루트 `health_check.py`가 대신 사용됨 |
| `modules/hub_manager.py` | `generate_hub_queue`/`register_hub` 호출처 없음(자기 파일 내부 정의·자기호출만) |
| `repositories/queue_repository.py` | `QueueRepository` import/인스턴스화 0건 |
| `repositories/template_repository.py` | `TemplateRepository` import/인스턴스화 0건 |

> `modules/collector/__init__.py`는 0바이트(패키지 마커, 정상).

---

## 5. 죽은 코드 (Dead Code)

| 위치 | 상태 | 근거 |
|------|------|------|
| `modules/checkpoint.py` | `acquire_lock`/`release_lock`/`load`/`save` **전부 미호출** | `main.py:225`의 `cp.clear()` 단 1곳만 사용 → docstring의 "체크포인트 복구" 미작동 |
| `modules/hub_manager.py` | 전체 미사용 | §4 |
| `repositories/queue_repository.py` | 전체 미사용 | §4 |
| `repositories/template_repository.py` | 전체 미사용 | §4 |
| `modules/health_check.py` | 전체 미사용(중복 구현) | §4, §6 |
| `dashboard.py` `💰 비용 모니터` 탭 | 본문 `st.info(...)` 한 줄, 로직 없음 | dashboard.py:118-120 |
| `collector/finance.py` `collect()` | `print()+return []` | finance.py:8-11 |
| `collector/affiliate.py` `collect()` | `print()+return []` | affiliate.py:8-12 |
| `writer` 내부링크 | `related=[None,None,None]` 하드코딩 | main.py:162 → 링크 항상 미생성 |

> 참고: `config/score_weights.yaml`은 **dead 아님** — `strategist.py:59`가 실제 로드(실패 시 DEFAULT fallback). 단 대시보드 편집 UI는 없음.

---

## 6. 중복 코드

| 중복 | 위치 | 내용 |
|------|------|------|
| RSS 수집 로직 | `rss_collector.collect()` ↔ `collector/policy.PolicyCollector.collect()` | 둘 다 feedparser로 동일 수집. `rss_collector`는 `source_type`/`site_id` 키 없음. 사이트 미등록 시 레거시 경로(rss_collector)만 실행 |
| 헬스체크 구현 | `health_check.py`(루트) ↔ `modules/health_check.py` | 같은 목적, 다른 인터페이스(`run` vs `run_health_check`, 결과 구조 상이). 루트만 사용 |
| Drive 공개권한 코드 | `google_provisioner.py:160` ↔ `drive_adapter.py:37` | 동일 `permissions().create(anyone/reader)` 반복 |
| 동일 자격증명 중복 | `secrets.yaml` `claude_sonnet` == `claude_haiku` | `setup_wizard.py:298-299`가 같은 claude 키를 두 슬롯에 기록 |
| LLM JSON 파싱 패턴 | `cleaner:32`, `duplicate_checker:30`, `planner:73`, `strategist:106`, `strategy_room` | `json.loads(text.strip())` 반복. `strategy_room`만 견고화(`_parse_json_lenient`) — 나머지는 미적용(§8) |

---

## 7. Deprecated 라이브러리

| 라이브러리 | 상태 | 위치 |
|-----------|------|------|
| **google-generativeai** | **공식 지원 종료(deprecated)**. 실행 시 `FutureWarning` 발생, `google-genai`로 이전 권고 | `modules/ai_provider.py:59`, `modules/health_check.py:63`, `health_check.py:52` (3곳) |

> Gemini 호출 전부가 이 deprecated 패키지를 사용. 라이브러리 제거/업데이트 시 Planner(M1)·헬스체크 Gemini 점검이 깨질 수 있음.

---

## 8. API 오류 가능성 (코드 레벨, 검증됨)

1. **`KeyError: 'WORDPRESS_APP_PASSWORD'`** — `publisher.py:34`가 `cfg["WORDPRESS_APP_PASSWORD"]` 직접 첨자 접근하나 `config.yaml`엔 `WORDPRESS_PASSWORD`만 존재. (사이트별 등록 시 `site_repository`가 해당 키 생성해 회피)
2. **광범위 예외 삼킴** — `except Exception`/bare except **51곳**, 그중 **`except: pass`(완전 무음) 6곳**. API 오류가 조용히 묻혀 `(False,0.0)`/`{}`/`"실패"` 등으로 폴백 (예: `telegram_notifier`, `image_generator._upload`, `duplicate_checker`).
3. **deprecated Gemini SDK** — §7. 라이브러리 갱신 시 호출 실패 가능.
4. **Gemini max_tokens 무시** — `ai_provider.py:63-67` `GeminiProvider.chat`이 `generate_content(user)`만 호출, `max_tokens` 미전달 → 출력 길이 제어 불가.
5. **LLM JSON 파싱 취약** — `planner.py:73`, `strategist.py:106`은 `json.loads(text.strip())`를 직접 수행. 모델이 코드블록/잡텍스트 포함 시 `JSONDecodeError` 가능(상위 `retry_call`/except로 흡수되나 결과 손실). `cleaner`/`duplicate_checker`는 fallback 보유.
6. **`dashboard.py` 오류로그 탭 ImportError** — `from modules.sheet_sync import get_sheet` 호출하나 `get_sheet`는 `sheet_sync.py`에 **미정의**(grep 0건) → 탭 진입 시 항상 예외(try/except로 "로그 로드 오류" 표시).
7. **이미지 실패 시 깨진 `<img>`** — `image_generator.generate`는 실패해도 `thumbnail_url`/`body_image_url` 키를 `"실패"` 문자열로 반환. `publisher.py:21,23`가 그대로 `<img src='실패'>`로 삽입(KeyError는 아님, 깨진 이미지).
8. **예산 사후 기록 누락** — 예외 경로에서 `budget.record()` 미호출(main.py:213은 성공 경로만) → 실패 호출 토큰/비용 미집계.

---

## 9. 보안 위험 요소 (검증됨)

| 위험 | 위치 | 내용 |
|------|------|------|
| ✅ **(해결) 소스 하드코딩 키** | ~~`test_img.py:13`~~ | 파일 **2026-06-21 삭제됨**. 단 해당 Gemini 키는 `secrets.yaml`/`config.yaml`에 그대로 남아 있고 한때 소스에 노출됐으므로 **키 재발급 권장** |
| 🔴 **config.yaml 평문 키** | `config/config.yaml` | OpenAI/Claude/Gemini API 키 + `WORDPRESS_PASSWORD` 평문 저장 |
| 🟠 **secrets.yaml 평문 키** | `config/secrets.yaml` | `ai_keys`에 4개 키 평문. `.gitignore`엔 이 파일만 등록 |
| 🟠 **config.yaml/credentials.json 미보호** | `.gitignore` | `config.yaml`, `credentials.json`(서비스계정 개인키)이 .gitignore에 **없음** → 향후 git init 시 커밋 위험 (현재는 git 저장소 아님) |
| 🟠 **Drive 전체 공개 권한** | `google_provisioner.py:160`, `drive_adapter.py:37` | 업로드 파일/폴더에 `type:anyone, role:reader` → 링크만 알면 누구나 열람 (이미지 호스팅 목적이나 공개 노출) |
| 🟡 **credentials.json 루트 평문** | 루트 | 서비스계정 private_key가 프로젝트 루트에 평문 보관 |

---

## 10. 개선 우선순위 TOP 20

| # | 우선 | 항목 | 위치/근거 |
|---|------|------|-----------|
| 1 | 🔴 | (test_img.py는 삭제 완료) 노출됐던 Gemini 키 **재발급** | §9 |
| 2 | 🔴 | API 키를 config.yaml 평문에서 분리(env/secrets) | config.yaml §9 |
| 3 | 🔴 | `.gitignore`에 `config.yaml`, `credentials.json` 추가(git 도입 전) | .gitignore §9 |
| 4 | 🟠 | deprecated `google-generativeai` → `google-genai` 이전 | 3곳 §7 |
| 5 | 🟠 | `dashboard.py` 오류로그 탭 `get_sheet` 미정의 수정 | dashboard.py:106 |
| 6 | 🟠 | WordPress 키명 통일(`WORDPRESS_PASSWORD`↔`WORDPRESS_APP_PASSWORD`) — WP 구축 시 | publisher.py:34 |
| 7 | 🟠 | `except: pass`/광범위 except 정리(최소 로깅) | 51곳/무음 6곳 §8 |
| 8 | 🟠 | `planner`/`strategist` JSON 파싱에 `_parse_json_lenient` 적용 | planner:73, strategist:106 |
| 9 | 🟠 | requirements.txt에 `Pillow` 추가 | §3 불일치 |
| 10 | 🟡 | `💰 비용 모니터` 탭 실제 구현(budget.json 시각화) | dashboard.py:118 |
| 11 | 🟡 | `publisher` 이미지 URL `.get()` + "실패" 가드 | publisher.py:21,23 |
| 12 | 🟡 | 예외 경로 비용 기록(`budget.record`) 추가 | main.py:213 |
| 13 | 🟡 | DLQ를 상태전이(`ArticleRepository.increment_fail`)와 통합 | main.py:240 |
| 14 | 🟡 | dead code 제거/연결: `hub_manager`, `queue/template_repository` | §4,§5 |
| 15 | 🟡 | 중복 `health_check` 통합(루트로 일원화, modules판 삭제) | §6 |
| 16 | 🟡 | `rss_collector` ↔ `collector/policy` 중복 일원화 | §6 |
| 17 | 🟡 | `checkpoint` 실제 배선 또는 제거(복구 기능 정상화) | checkpoint.py |
| 18 | 🟡 | Gemini `max_tokens` 전달 | ai_provider.py:63 |
| 19 | ⚪ | `finance`/`affiliate` 수집기 구현 또는 factory에서 제외 | §5 |
| 20 | ⚪ | `score_weights.yaml` 대시보드 편집 UI 연결 | strategist.py:59 |

---

### 부록 — 수치 요약
- 파일 78 / Python 55(4,099 LOC)
- 광범위 except 51곳, 무음 `except:pass` 6곳
- stub 파일 4(finance, affiliate, postgres_adapter, s3_adapter)
- dead/미사용 모듈 5(checkpoint 부분, hub_manager, modules/health_check, queue_repository, template_repository)
- deprecated 라이브러리 1(google-generativeai, 3곳)
- 하드코딩 실키 0곳 (test_img.py 삭제 — 노출됐던 키 재발급 권장)
