# MASTER ROADMAP — SalaryMate 프로젝트 기준 문서

> 프로젝트 전체를 한눈에. 향후 개발·운영·유지보수의 기준 문서.
> 관련: [README](README.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [REGISTRY](docs/REGISTRY.md) ·
> [APP_FACTORY](docs/APP_FACTORY.md) · [OPERATIONS](docs/OPERATIONS.md) · [BACKLOG](BACKLOG.md) ·
> [KNOWN_ISSUES](KNOWN_ISSUES.md) · [CHANGELOG](CHANGELOG.md)

---

## 1. 프로젝트 목표

- **계산기 자동 생성** — 메타데이터 입력 → App Factory가 스펙/코드/SEO 자동 생성
- **블로그 자동 생성** — 계산기/정책 키워드 → SEO 글 자동 작성
- **WordPress 자동 발행** — 생성물 REST 발행/수정/삭제/복원
- **품질 자동 검증** — 결정론 Gate(G1~G8) + GPT Score(S1~S6) + 재시도/HOLD
- **Registry 기반 자동 운영** — 계산기 메타데이터 단일 소스, legal 검증 게이트

핵심 철학: **식별자(slug, 영문)와 표시(name, 한글)를 분리**, **Registry가 단일 소스**,
**Gate(결정론) vs Score(GPT) 책임 분리**, **legal은 사람 검증**(AI 환각 방지).

---

## 2. 현재 완료 ✅

| 영역 | 상태 |
|------|------|
| WordPress CRUD | ✅ 발행/수정/삭제(휴지통)/복원 (publisher.py 단일) |
| 품질 Gate (G1~G8) | ✅ 결정론 코드 검사, G8=legal_basis 대조 |
| 품질 Score (S1~S6) | ✅ GPT 채점, Gate와 책임 분리(F에서 정리) |
| Retry / HOLD | ✅ 재생성 재시도 + 품질보류 + 재평가 게이트 |
| legal_basis | ✅ 7종 사람 검증 데이터 + G8 배선 |
| Calculator Registry 2.0 | ✅ Phase A~D — 하드코딩 폐기, registry 유일 소스 |
| registry_auto | ✅ App Factory 자동 기록 + merge 로더(큐레이션 우선) |
| App Factory | ✅ 신규 계산기 생성 + 영문 slug 직접 입력 + registry 등록 |
| legal 미검증 차단 | ✅ BLOCK_UNVERIFIED_LEGAL — 데이터-존재 게이트 + 자동 해제 |
| 실환경 E2E 검증 | ✅ 작업지시서 F — Case 1~4 통과(S1/S2/S3 구조적 버그 발견·수정) |

상세 흐름: [ARCHITECTURE.md](docs/ARCHITECTURE.md), Registry: [REGISTRY.md](docs/REGISTRY.md).

---

## 3. 현재 운영 흐름

```
Dashboard(App Factory)
   → 신규 계산기 생성(영문 slug + 한글 name)
   → Registry 등록(registry_auto, legal 미검증 → HOLD)
   → 사람이 legal_basis 입력(승격)
   → Writer 본문 생성(legal_basis 주입)
   → Gate(G1~G8)  →  Score(S1~S6)  →  Retry/HOLD
   → PASS/WARN → WordPress 발행
   → 마스터_DB(Google Sheet) 기록(quality_* + history)
```

---

## 4. 로드맵

### ✅ 완료
CRUD · Registry 2.0 · Quality Gate · Score · Retry · HOLD · legal_basis · registry_auto · App Factory · slug/name 분리

### 🔵 운영 중 (관찰)
- 실환경 관찰(계산기 발행 품질)
- 로그 수집(quality_*, history)
- **Score 안정화** — S5/normalized 변동성(59~85) 데이터 축적 후 판단

### 🟡 다음 개발 (권장 순서)
1. **법령·요율 자동 감지** — 운영 시작 후 최우선 유지보수 이슈(법령/요율 변경). 계산기·글이 쌓이기 전 구축 권장
2. **요율 자동 업데이트** — 4대보험 등 formula 요율 연 1회 갱신 자동화
3. **계산 예시 엔진** — Score S1 품질 향상(다양한 조건 예시 자동 생성)
4. **통계/그래프 대시보드** — 발행량·품질·비용 시각화

### 🌙 장기 목표
- 계산기 100+ · 블로그 대량 발행
- Registry 자동 운영(신규 계산기 무인 등록·검증 흐름 성숙)
- 법령 자동 감지 · 요율 자동 업데이트
- AI 운영 자동화(관찰→진단→수정 루프)

---

## 5. 운영 일정

| 주기 | 할 일 |
|------|-------|
| 매일 | 스케줄러 가동 확인 · 발행 목록/HOLD 확인 · 오류 로그 · 비용 모니터 |
| 주간 | 품질보류 원인 분석(legal 미입력 vs Score 실패) · Score 점수 추이 관찰 |
| 월간 | 법령/요율 변경 점검(특히 4대보험 요율) · legal_basis 재검증 · 백로그 재정렬 |

상세 운영 절차: [OPERATIONS.md](docs/OPERATIONS.md).

---

## 6. 다음 Sprint 추천

**Sprint: 법령·요율 자동 감지 (권장 최우선)**
운영 시작 시 가장 먼저·자주 발생하는 유지보수는 법령/요율 변경이다. 계산기와 글이 많이 쌓이기 전에
구축하면 업데이트가 훨씬 수월하다. 착수 전 조사(어떤 소스에서 감지할지, registry `content.update_cycle`/
`last_verified`와 어떻게 연동할지)를 먼저 한다.
