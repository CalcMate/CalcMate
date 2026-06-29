# ROADMAP.md — 구현 현황 및 로드맵

> 실제 소스 코드 기준(2026-06-29, v12 Lite + SPRINT 2A/2B 반영). 구현됨/부분/미구현을 코드 근거로 구분.

---

## ✅ 구현 완료

### 코어 파이프라인 (12단계)
- 수집(policy/RSS) · 정제 · 중복검사(임베딩+코사인+AI judge) · 전략(M0+M2, final_score 키 정합) · SEO 기획(M1) · 작성 · 검수(+GPT fallback) · 파싱 · 이미지(Pollinations→Drive) · 기록
- 다건 처리(`run_once`가 DAILY_POST_COUNT만큼, 중복/실패 제외, 예산 초과 즉시 중단)

### 데이터/인프라
- DB 어댑터 sheets(기본)·sqlite · Storage drive(기본)·local — 실동작
- Repository: article/site/calculator/template
- BudgetTracker(모델별 입출력 비용, 실패호출 포함)
- 헬스체크 · 백업 · 설정 마법사(Sheets/Drive 자동생성)

### 운영/대시보드
- Streamlit **8그룹 2단 네비** + 다크 SaaS 홈(현재 Site 카드/5 KPI/Workflow 시각화/진행현황)
- 슬롯 스케줄러(평일/주말, 랜덤 예약, today_schedule.json 영속, 실패모드 3종, 즉시발행/재시도)
- 설정: AI 역할 편집, score_weights 슬라이더, 발행방식(**예약발행 단일화**, Legacy 제거)
- 성능: 2단 캐시(메모리 + SQLite 미러, 라이브 폴백) + 로그 tail + sync_cache 워밍

### 운영 자동화 (v12 Lite)
- **AI Assistant**(채팅+워크스페이스 파일도구+승인게이트+메모리+태스크+분석)
- **Cost Manager**(80%경고/100%정지/익일재개) · **Retry Queue**(WP 재발행) · **Image Fallback**(PIL 브랜드 이미지)
- **Telegram 고도화**: 표준화 헬퍼 + 이벤트 ON/OFF 게이팅(TELEGRAM_EVENTS)

### 보안/구조 (SPRINT 2A/2B)
- **Secrets 분리**: API키/앱비번/봇토큰 → `config/secrets.yaml`(gitignore), `config_loader.merge_secrets` 런타임 병합
- **Site Manager**: 현재 Site 셀렉터 · 안전삭제(보관30일/복구/DELETE확인) · 복제 · Export/Import
- **Site Wizard 5단계**(Profile→Platform 독립복수→Feature→Settings→Pipeline)
- **Site Settings Override**(Global→Site, 🔵뱃지/초기화) — *저장 완료, 런타임 소비는 후속*
- **통합 실행 버튼**(선택 Site의 platforms 기반 Pipeline 자동 라우팅, 기존 개별버튼은 고급실행 보존)

### 계산기 플랫폼 (SalaryMate)
- **Calculator UI v1**(calculator_v1.html, 변수 치환, 동일 UI)
- **Template Library** 5종(retirement/annual_leave/weekly_allowance/unemployment/insurance)
- **Form Engine**(이름→입력폼, 라이브러리 우선→AI, 7타입)
- **Formula Engine**(AST 안전 수식, eval 금지)
- **App Generator**(template+Form+SiteMode→index/style/script)
- **AI Reviewer**(검수 PASS/REWRITE + `auto_review_and_fix` 자동수정 루프, `auto_generate_all`에 **연결됨**, 상태 AUTO_APPROVED/AUTO_REWRITTEN/NEEDS_REVIEW)
- **Site Mode**(pre_adsense/post_adsense/growth) — 광고/관련/공유/리포트 노출 제어
- SEO/FAQ/본문/이미지프롬프트 생성기 + 시드 + App Factory + Internal Link

### 확장
- 사이트 생성 마법사(6유형) · AI Workspace · AI Pipeline Monitor

### 안정화 (완료)
- Gemini `google-genai` 마이그레이션 · WordPress 키 단일화 · JSON 파서 공통화 · 무음 except 제거 · dead code 4종 제거 · score_weights 키 정합

---

## 🟡 부분 구현 (코드 있으나 조건부/제약)

| 항목 | 제약 |
|------|------|
| WordPress 발행(`publisher`) | 실제 WP 미구축(example.com/temp). `WORDPRESS_APP_PASSWORD` 입력 시 동작. 글로벌 경로 키 직접참조 주의(사이트별 경로 권장) |
| 계산기 글 저장 | 시트 연결 정상(현재 0행). 대량 생성 시 시트 API rate 유의 |
| AI Reviewer 통과율 | 검수 모델 `claude-sonnet-4-6` 기준 엄격 → 생성물이 자주 NEEDS_REVIEW(임계값/프롬프트 튜닝 여지) |
| GitHub 배포(`github_deployer`) | `GITHUB_TOKEN` 필요. 미설정 시 graceful skip |
| App Factory 이미지 프롬프트 | Gemini 무료키 429 시 fallback |
| AI Workspace 파일수정 | 샌드박스 기본 + 프로젝트 파일은 백업+확인 게이트 |
| Multi-site 사이트별 설정 | 생성 후 편집 UI 추가됨(Site Settings Override, 작업7). 단 **저장만 되고 파이프라인 런타임 미소비**(AI 프로필 일부 제외) — 배선은 후속 |
| Site platforms/features | Wizard에서 sites 컬럼 저장(작업6). 실행 라우팅은 통합 버튼이 소비(작업8). 그 외 Feature 플래그는 런타임 미소비 |
| Telegram 이벤트 알림 | telegram_ops 경유 이벤트만 게이팅 적용. 발행성공/시작종료/승인요청/일일요약은 **미배선**(파이프라인 호출 추가 필요). 양방향은 설계만(`TELEGRAM_BIDIRECTIONAL_DESIGN.md`) |

---

## ❌ 미구현 (stub / 명시적 NotImplemented)

| 항목 | 근거 |
|------|------|
| 금융 수집기 `collector/finance.py` | `return []` |
| 제휴 수집기 `collector/affiliate.py` | `return []` |
| PostgreSQL 어댑터 | 전 메서드 `NotImplementedError` |
| S3 Storage 어댑터 | 전 메서드 `NotImplementedError` |
| 내부 링크(블로그 파이프라인) | `writer` related=[None,None,None] 고정 (계산기 경로엔 internal_link_engine 적용됨) |
| AUTO_TOPIC_EXPANSION 실행부 | config 플래그 + strategy_room 판정만, 자동 실행 로직 없음 |
| dashboard pages/ 멀티페이지 분리 | 미적용(단일 페이지 유지) |

---

## 🔭 향후 구현 (우선순위)

### P1 (운영 정상화) — ✅ 모두 해결됨
- ~~Google Sheet 403~~ → ✅ 해결(서비스 계정 공유 완료, read_test OK)
- ~~MODEL_EDITOR retired~~ → ✅ 해결(`claude-sonnet-4-6`로 교체, 실호출 확인)

### P2 (계산기/품질)
3. Reviewer 통과율 튜닝(임계값/프롬프트), 골드 템플릿 article_template 본문 자동 채움
4. App Factory 계산기 → WordPress 페이지 발행 연계
5. 사이트별 AI/WP/슬롯 설정 편집 UI(생성 후 수정)

### P3 (확장/품질)
6. PostgreSQL/S3 어댑터 실구현, 금융/제휴 수집기 실구현
7. AI 호출 비동기화(대시보드 블로킹 해소), 입출력 토큰 실분리
8. 테스트 스위트(pytest) 정식화

> 상세 과제: `TODO_NEXT.md` · 변경 이력: `CHANGELOG_AI.md` · 안정성: `STABILITY_REPORT.md` · 계산기: `CALCULATOR_V1_REPORT.md`
