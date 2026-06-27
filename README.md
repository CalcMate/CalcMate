# 블로그자동화 v12 / SalaryMate 플랫폼

> 정부정책(RSS) 블로그 자동화 + **계산기 콘텐츠 플랫폼** + AI 운영센터(Streamlit).
> 본 문서는 **실제 소스 코드 기준**(추측 없음). 작성: 2026-06-23. (Python 81개 파일)

---

## 프로젝트 개요

- **목적**: RSS/계산기 키워드를 수집 → AI로 SEO 글·계산기 페이지 생성·검수 → 이미지 → WordPress/GitHub Pages 발행까지 무인 자동화. 운영은 Streamlit 대시보드.
- **현재 버전**: v12 (`main.py` 시작 로그 `블로그자동화 v12`). 코어는 v11.6의 12단계 파이프라인 계승.
- **두 갈래 콘텐츠**: ① 정책/RSS 블로그(`run_once` 12단계) ② 계산기 플랫폼(생성→AI검수→정적앱→배포).

### 핵심 기능 (실제 구현)
| 영역 | 기능 | 상태 |
|------|------|------|
| 수집 | RSS(정책), 계산기 키워드 | ✅ |
| 생성 | 정제→전략(M0/M2)→SEO(M1)→작성(M3)→검수(M4)→이미지→발행 (12단계) | ✅ (발행은 WP 구축 시) |
| 계산기 | Formula/Form Engine, v1 UI 템플릿, 템플릿 라이브러리 5종, App Generator, AI Reviewer(자동검수·수정), Site Mode | ✅ |
| 운영 | Streamlit 대시보드 8그룹(Dashboard/Content/Calculator/Scheduler/Revenue/Logs/Settings/**AI Assistant**), 2단 네비 | ✅ |
| 운영비서 | **AI Assistant**(GPT/Claude/Gemini 채팅 + 워크스페이스 파일도구 + 승인 게이트 + 메모리/태스크/분석) | ✅ |
| 운영 자동화 | Cost Manager(80%경고/100%정지/익일재개) · Retry Queue(WP 재발행) · Image Fallback · Telegram 고도화 | ✅ |
| 스케줄 | 평일·주말 슬롯 + 랜덤 예약 + 실패모드 3종 (예약발행 단일화, Legacy 제거) | ✅ |
| 데이터 | Sheets/SQLite(DB), Drive/Local(Storage) 어댑터 | ✅ (Postgres/S3 stub) |
| 성능 | 2단 캐시(메모리+SQLite 미러) + 로그 tail | ✅ |

---

## 현재 동작 흐름 (실제 구현)

```
[운영자] 대시보드 버튼 / .bat / 스케줄러 예약시각
   ↓
수집  STEP1  SiteManager.get_active_sites() → site_type별 Collector
              (사이트 미등록 시 rss_collector 레거시 fallback)
   ↓
정제  STEP2  cleaner.clean_rss_item()                  [OpenAI gpt-4o]
   ↓
1차중복 STEP3 duplicate_checker (임베딩+코사인+AI judge) [OpenAI]
   ↓
전략  STEP5  strategist.design_strategy() M0 + M2 점수  [OpenAI gpt-4o]
   ↓
SEO기획 STEP6 planner.plan_seo() + 2차 제목 중복검사     [Gemini 2.5-flash]
   ↓
작성  STEP7  writer.write_draft()                       [OpenAI gpt-4o-mini]
   ↓
검수  STEP8  editor.edit() (+실패 시 GPT fallback)       [Claude → GPT]
   ↓
파싱  STEP9  cleaner.parse_html_body()
   ↓
이미지 STEP10 image_generator.generate()                 [Pollinations → Drive]
   ↓
발행  STEP11 publisher.publish() (WP 미구축 시 검수대기 대기) [WordPress REST]
   ↓
기록  STEP12 sheet_sync.append_row()/append_log(), 단계별 비용 기록
```

> 계산기 경로(별도): `calculator_pipeline.run_calculator_once()` (키워드→점수→SEO/FAQ→본문+위젯+CTA→발행) / `calculator_content_generator.auto_generate_all()` (SEO→FAQ→본문→이미지→**AI Reviewer 검수·자동수정**→저장).

---

## 설치 방법

1. **Python**: 3.11+ (`scripts/install.bat`이 확인). 개발/검증은 3.12 venv.
2. **의존성**: `python -m venv .venv` → `.venv\Scripts\python.exe -m pip install -r requirements.txt`
   (openai, anthropic, **google-genai**, gspread, google-api-python-client, feedparser, streamlit, pandas, numpy, Pillow, pyyaml, requests)
3. **config**: `config/config.yaml`(모델/예산/Google/WP), `config/secrets.yaml`(WP 프로필·AI키), `config/score_weights.yaml`, `config/site_mode.yaml`. 최초 미설정 시 대시보드가 설정 마법사 자동 표시.
4. **Google Sheets**: `credentials.json`(서비스계정) + `GOOGLE_SHEET_ID`. **시트를 서비스 계정 이메일에 편집자 공유 필수**. 마법사 2단계가 7탭 자동 생성.
5. **Google Drive**: 같은 서비스 계정 `GOOGLE_DRIVE_ROOT_ID`(이미지 업로드), 폴더도 공유.
6. **WordPress**: `WORDPRESS_URL`/`WORDPRESS_USERNAME`/`WORDPRESS_APP_PASSWORD`(Application Password). 미설정 시 발행 자동 대기(크래시 없음).
7. **실행**: 아래 '운영 방법'.

> ✅ Google Sheets 연결 정상(서비스 계정 공유 완료, `read_test: True`). 권한 이슈 발생 시 `DB_ADAPTER: sqlite`로 폴백 가능.

---

## 운영 방법

| 진입점 | 명령/파일 | 역할 |
|--------|-----------|------|
| 단발 실행 | `scripts/run_pipeline.bat` (`main.py --once`) | 12단계 1회(`DAILY_POST_COUNT`만큼) |
| 예약 발행 | `scripts/run_scheduler.bat` (`main.py --scheduler`) | 슬롯 일정대로 시각별 1건(**유일한 상시 운영 방식**) |
| 검증 | `scripts/run_dryrun.bat` (`main.py --dry-run`) | 헬스체크+설정 검증 |
| 전략회의실 | `scripts/run_strategy_room.bat` (`--strategy-room`) | 운영 분석 JSON |
| 계산기 | `main.py --calculator` / `--seed-calculators` | 계산기 글 생성 / 초기 5종 시드 |
| 캐시 워밍 | `scripts/sync_cache.bat` | 대시보드 SQLite 미러 갱신(첫 진입 가속) |
| 대시보드 | `scripts/run_dashboard.bat` (`dashboard.py`, 다크 SaaS, 8그룹) | 운영센터 + AI Assistant |

> 운영 방식 기본값 `config.OPERATION_MODE`(scheduled). 플래그 없이 `main.py` 실행 시 이 값 따름.

---

## AI 역할 (현재 코드 기준)

파이프라인 단계 모델은 `config.yaml`의 `*_PROVIDER`/`MODEL_*`, `sites` 탭 있으면 사이트별 프로필 우선(`ai_provider.build_provider_for_role`).

| 역할 | 모듈 | 현재 모델 | 설명 |
|------|------|-----------|------|
| **Orchestrator (M0)** | `strategist.py` | OpenAI `gpt-4o` | 전략/각도/회피패턴/톤 + M2 Python 7점수 `final_score` |
| **Planner (M1)** | `planner.py` | Gemini `gemini-2.5-flash` | SEO 제목/메타/키워드/FAQ/구조/이미지 프롬프트 |
| **Writer (M3)** | `writer.py` | OpenAI `gpt-4o-mini` | source_type별 본문 HTML |
| **Editor (M4)** | `editor.py` | Claude `claude-sonnet-4-6` → 실패 시 OpenAI `gpt-4o` | 검수/교정 (유효 모델, 실호출 확인) |
| **Cleaner** | `cleaner.py` | OpenAI `gpt-4o` | 행정용어 정제 + STEP9 파싱 |
| **Image Generator** | `image_generator.py` | Pollinations 무료 | 썸네일/본문 webp → Drive |

> 계산기 확장 기능(App Factory/AI Workspace/Form/SEO/FAQ/Reviewer)은 `ai_roles.py` 역할표 사용(총괄=GPT, 코드=Claude `claude-sonnet-4-6`, 리서치/이미지=Gemini).

---

## 더 읽기
`ARCHITECTURE.md`(계층/흐름) · `FILE_STRUCTURE.md`(파일별 역할·의존성) · `ROADMAP.md`(완료/부분/미구현) · `CALCULATOR_V1_REPORT.md` · `CHANGELOG_AI.md` · `STABILITY_REPORT.md` · `TODO_NEXT.md`
