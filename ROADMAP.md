# ROADMAP.md — 구현 현황 및 로드맵

> 실제 소스 코드 기준(2026-07-04, Sprint 2A/2B + Calculator Reviewer + 계산기 v2/App
> Factory/WordPress 발행·수정 반영). Completed / In Progress / Planned 3그룹으로만 구분.

---

## ✅ Completed

### 코어
- 12단계 파이프라인(`run_once`/`_process_one`): 수집 · 정제 · 중복검사 · 전략(M0+M2) · SEO(M1) · 작성(M3) · 검수(M4+GPT fallback) · 파싱 · 이미지(Pollinations→Drive) · 발행 · 기록
- AI 추상화 `ai_provider`(OpenAI/Claude/Gemini) + BudgetTracker(모델별 비용)
- DB 어댑터 sheets/sqlite · Storage drive/local · Repository(article/site/calculator/template)
- 헬스체크 · 백업 · 설정 마법사(Sheets/Drive 자동생성)

### Dashboard Lite
- Streamlit **8그룹 2단 네비**(NAV_GROUPS)
- 운영센터 홈: 현재 Site 카드 + 5 KPI(시스템/Workflow/AI작업/오늘/비용) + Workflow 시각화 + 진행현황
- 2단 캐시(메모리 + SQLite 미러) + 로그 tail + sync_cache 워밍

### Secrets 분리
- API키/앱비번/봇토큰 → `config/secrets.yaml`(gitignore) + `secrets.example.yaml`(추적)
- `config_loader.merge_secrets` 런타임 병합(secrets 우선), 저장 경로도 secrets로 리다이렉트

### 계산기 플랫폼 (SalaryMate)
- Calculator UI v1 · Template Library 5종 · Form Engine · Formula Engine(AST) · App Generator · Site Mode
- **AI Reviewer GPT 분리**(`CALC_REVIEW_PROVIDER/MODEL`, 블로그 editor=Claude 유지, 자기검수 해소)
- **total 정규화**(항목 평균 + 0~100 클램프, 범위초과 버그 수정)
- **시드 본문 보호**(`upsert_by_slug`: 재시드 시 기존 본문 미덮어쓰기)
- SEO/FAQ/본문/이미지프롬프트 생성기 + 시드 + App Factory + Internal Link

### 운영 자동화
- **Cost Manager**(80%경고/100%정지/익일재개) · **Retry Queue**(WP 재발행) · **Image Fallback**
- **Telegram**(표준화 헬퍼 + 이벤트 ON/OFF 게이팅 `TELEGRAM_EVENTS`)
- **AI Assistant**(채팅+워크스페이스 파일도구+승인게이트+메모리+태스크+분석)
- 슬롯 스케줄러(평일/주말, 랜덤예약, today_schedule.json, 실패모드 3종) — 예약발행 단일화

### Site 관리 (Sprint 2B)
- Site Manager(현재 Site 셀렉터 · 안전삭제 보관30일/복구/DELETE · 복제 · Export/Import)
- 5단계 Site Wizard(Profile→Platform 독립복수→Feature→Settings→Pipeline)
- Site Settings Override(Global→Site, 🔵뱃지/초기화) — 저장
- 통합 실행 버튼(platforms 기반 Pipeline 자동 라우팅)

### 계산기 v2 · App Factory · WordPress (2026-07-04)
- **Design System v2 확정** + 버그 4건 수정(파일저장 경로 · 관련링크 · 퇴직금 수식경고 · 노출설정 cfg)
- **App Factory**: 중복방지(프롬프트+slug/name) · AI/키워드 아이디어 제안 · formula 검증(1회 재시도) · 계산기별 한국어 labels · 저장→관리 자동이동
- **위젯 엔진 통일**: WP 삽입 위젯을 v2(`generate_html`)로 — 구 naive 합산 제거. `render_inline_calculator()`를 대시보드 미리보기와 WP가 공유
- **파이프라인 콘텐츠 버그 4건**: CTA중복 · 숨김섹션 소스잔존(→`render_*`+`show_*` 서버단 생략) · 죽은링크(→`is_active`) · 계산기당 중복발행(→`count_active_articles`)
- **WordPress 발행 메타데이터**: post_id/permalink/status/published_at/history/calculator_id 저장
- **WordPress 글 수정(Update)**: `publisher.update_post` + 대시보드 ✏️수정 UI (성공 시에만 로컬 갱신)
- 아키텍처 원칙 확립: 상태판단=Repository 계층 / WP REST=`publisher.py`만 / 섹션노출=`render_*`+`show_*`

### 문서/안정화
- Sprint 2A 감사 보고 · Sprint 2B 보고 · AI Assistant 분석 · Calculator Reviewer Fix 결과
- `docs/BUGFIX_CALC_DESIGN_V2.md` · `docs/CALC_QUALITY_IMPROVEMENT_RESULT.md`
- Gemini google-genai 마이그레이션 · WordPress 키 단일화 · JSON 파서 공통화

---

## 🟡 In Progress / 부분 구현

- **WordPress**: 로컬(Laragon `salarymate.test`) 발행·수정 실환경 검증 완료(post_id/history 저장). **실서버(공개 도메인) 배포는 미완**. 글 삭제/복원은 3·4차 예정
- **Site Settings Override 런타임 소비**: 저장은 되나 파이프라인이 site 값을 아직 읽지 않음(AI 프로필 일부 제외) — 배선 필요
- **Site Manager 고도화**: 안전삭제/복제/Export·Import UI 완료, 자동 만료삭제·일괄작업은 미구현
- **Dashboard 운영센터**: 카드/시각화 완료, 실시간성·일부 KPI(Revenue=AdSense 미연동)는 보강 여지
- **계산기 품질**: GPT 검수+정규화 적용. 일부 항목(예: 실업급여) 콘텐츠 품질 낮음 → 프롬프트 보강 여지
- **GitHub 배포**(`github_deployer`): `GITHUB_TOKEN` 필요, 미설정 시 skip

---

## 🔭 Planned

### WordPress 글 관리 (계산기 파이프라인 후속)
- **3차: WordPress 글 삭제**(휴지통 이동, 영구삭제 아님) — `publisher.delete_post` + 대시보드 삭제버튼 + article "삭제됨" 전환(실제 WP 반영)
- **4차: 휴지통 복원**
- **계산기 글 품질 시스템**: 품질 기준서 → writer 프롬프트 개선(§7 관련계산기 중복 등) → 자동 검수
- 정책 RSS 소스 갱신(`korea.kr` 404 → 유효 피드로 교체 또는 복수화)

### 플랫폼/인프라
- **RSS Platform** 확장(수집원/카테고리 다변화)
- **Affiliate Platform**(`collector/affiliate.py` stub 실구현)
- **Shorts Platform**(영상/숏폼 콘텐츠)
- **SaaS Platform**(외부 제공형)
- **Multi-Site 운영**(사이트별 독립 파이프라인·스케줄·예산)
- 금융 수집기(`collector/finance.py`) · PostgreSQL/S3 어댑터 실구현
- `provision()` 재호출 가드(시트 재생성으로 인한 데이터 유실 차단)
- Telegram 미배선 이벤트(발행성공/시작종료/승인요청/일일요약) + 양방향 명령
- AI Assistant 툴콜 에이전트화 · 대화 영속화
- 테스트 스위트(pytest) 정식화 · 노출 키 재발급

> 상세 이력: `SPRINT_2A_REPORT.md` · `SPRINT_2B_REPORT.md` · `docs/CALCULATOR_REVIEWER_FIX_RESULT.md` · `docs/BUGFIX_CALC_DESIGN_V2.md` · `docs/CALC_QUALITY_IMPROVEMENT_RESULT.md`
