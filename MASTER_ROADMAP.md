# MASTER ROADMAP — SalaryMate

> 프로젝트 전체 기준 문서. 개발·운영·유지보수의 공식 순서.
> 관련: [README](README.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [REGISTRY](docs/REGISTRY.md) ·
> [APP_FACTORY](docs/APP_FACTORY.md) · [OPERATIONS](docs/OPERATIONS.md) · [BACKLOG](BACKLOG.md) ·
> [KNOWN_ISSUES](KNOWN_ISSUES.md) · [CHANGELOG](CHANGELOG.md)
> [CALCULATOR_QUALITY_STANDARD](docs/CALCULATOR_QUALITY_STANDARD_V1.0.md)

---

## 시스템 현황 (2026-07-19)

| 영역 | 상태 |
|------|------|
| WordPress CRUD | ✅ 발행/수정/삭제/복원 |
| 품질 Gate (G1~G8) | ✅ 결정론 코드 검사 |
| 품질 Score (S1~S6) | ✅ GPT 채점, Gate와 책임 분리 |
| Retry / HOLD / 재평가 | ✅ 재생성·재시도·품질보류·재평가 게이트 |
| legal_basis | ✅ 7종 사람 검증 + G8 배선 |
| Calculator Registry 2.0 | ✅ 하드코딩 폐기, registry 유일 소스 |
| App Factory | ✅ 신규 계산기 생성 + registry 자동 등록 |
| 스케줄러 | ✅ 슬롯 기반 자동 발행 + 텔레그램 알림 |
| 계산기 품질 검증 | 🔄 6/7 Verified (연말정산 대기) |

---

## 운영 원칙

개발 순서는 항상 아래를 유지한다.

1. **정확성 (Quality)** — 계산이 틀리면 신뢰가 없다
2. **안정성 (Stability)** — 회귀가 없어야 확장할 수 있다
3. **사용성 (UX)** — 정확하고 안정적인 다음에 보기 좋게
4. **동적 기능 (Dynamic Engine)** — UX 기반 위에 동적 반영
5. **SEO** — 콘텐츠 완성 후 검색 최적화
6. **수익화 (Monetization)** — SEO 성과 확인 후 수익 구조
7. **신규 계산기 제작** — 표준 파이프라인으로 반복 적용

이 순서를 변경하지 않는다.

---

## Phase A. Calculator Quality Verification

**목표**: 모든 계산기의 계산 로직·법령·콘텐츠를 검증하여 전체 Verified 달성

### 계산기별 상태

| 계산기 | 상태 | 완료일 |
|---|---|---|
| 주휴수당 (weekly-holiday-allowance) | ✅ Verified | 2026-07-19 |
| 퇴직금 (severance-pay) | ✅ Verified | 2026-07-19 |
| 실업급여 (unemployment-benefit) | ✅ Verified | 2026-07-19 |
| 4대보험 (four-insurances) | ✅ Verified | 2026-07-19 |
| 연차수당 (annual-leave-allowance) | ✅ Verified | 2026-07-19 |
| 육아휴직 (육아휴직_급여_계산기) | ✅ Verified | 2026-07-19 |
| 연말정산 (연말정산_환급액_계산기) | ⏳ 검증 대기 | — |

### 산출물 (완료 기준)

- `docs/CALCULATOR_QUALITY_STANDARD_V1.0.md` — 체크리스트 + 계산기별 결과
- `KNOWN_ISSUES.md` — 발견·해결 이력 전체
- `tests/` — 각 계산기 전용 Fixtures + 회귀 테스트 (현재 141케이스)
- `docs/reference_cases/` — 정부 기준 케이스 파일
- `tests/golden/calculator_snapshots.json` — 계산 엔진 해시 고정

### 연말정산 검증 진입 조건

- 간이 근사 계산(#4, KNOWN_ISSUES.md) 설계 범위 문서화 완료
- writer 프롬프트 격리 실험 결과 반영 (docs/experiments/ 저장 예정)
- HOLD 해제 후 재평가 성공 확인

---

## Phase B. Stability & Regression

**목표**: 계산기 전체 안정화 + Calculator Quality Standard V1.x 확정

### 작업

- 전체 회귀 테스트 (Phase A 완료 후 전 계산기 동시 검증)
- 공통 Minor 일괄 정리
  - SP-5 날짜 레이블 영문 잔존 (퇴직금)
  - G8 DB 경로 사각지대 (#17 KNOWN_ISSUES.md)
  - needs_human_legal 플래그 의미 오류 (#7)
  - 관련카드 [:4] cap — 연말정산/육아휴직 미노출 (#8)
- Calculator Quality Standard V1.x 확정 → 신규 계산기 표준으로 고정
- 모든 계산기 Verified 선언

---

## Phase C. Calculator UX/UI V2 (정적 UI 개선)

**목표**: 계산 로직을 변경하지 않고 전 계산기 UI·공통 컴포넌트 통일

### C-1. 공통 UI

- 결과 카드 개선
- 입력폼 개선 (레이블·단위·힌트 통일)
- 버튼 디자인 통일
- 모바일 최적화
- 안내 박스 (주의사항·법령 출처)

### C-2. CTA 개선

- 결과 하단 CTA
- 본문 중간 CTA
- 하단 CTA

### C-3. FAQ

- Accordion(드롭다운) 적용
- FAQ Schema (구조화 데이터)
- 공통 FAQ 컴포넌트

### C-4. 관련 계산기

- 카드 UI
- 같은 카테고리 기반 추천 (룰 기반)
- 내부 링크 연결

### C-5. 관련 글

- 카드 UI
- 기본 내부 링크

---

## Phase D. Dynamic Content Engine (UX V3)

**목표**: 사용자 입력과 계산 결과를 본문에 실시간으로 반영하는 동적 콘텐츠 엔진

### D-1. 계산 결과 ↔ 본문 연동

```
"월급 300만원 기준"
      ↓  (사용자가 250만원 입력)
"입력하신 월급 250만원 기준"   ← 자동 반영
```

### D-2. article_content 개선

- Placeholder 시스템 설계
- Template Engine 구현
- `app_generator.py` 개선 (정적 HTML → 동적 렌더 지원)

### D-3. Dynamic FAQ

- 계산 결과 기반 FAQ 표시
- 계산 결과 기반 안내문
- 계산 결과 기반 예시 삽입

---

## Phase E. SEO & Monetization

**목표**: 계산기의 검색 성능과 수익성 최적화

### 작업

- Breadcrumb 구조화 데이터
- 내부 링크 자동화
- 관련 글 추천 로직
- 검색어 기반 CTA
- AdSense 배치 최적화
- 체류시간 증가 요소
- 성과 분석 (노출·클릭·CTR·수익)

---

## Phase F. New Calculator Pipeline

**목표**: 새 계산기 제작 표준화 — Phase A에서 확립한 Quality Standard 반복 적용

### 프로세스

```
기획 (슬러그·법령·공식 확정)
  ↓
Calculator Quality Standard 체크리스트 적용
  ↓
legal_basis.draft.yaml 항목 추가 (사람 검증)
  ↓
App Factory 생성 + Registry 등록
  ↓
계산 엔진 전용 테스트 작성
  ↓
Regression Test 전체 통과
  ↓
Verified 선언
  ↓
배포
```

---

## 운영 일정

| 주기 | 할 일 |
|------|-------|
| 매일 | 스케줄러 가동 확인 · 발행 목록/HOLD 확인 · 오류 로그 · 비용 모니터 |
| 주간 | 품질보류 원인 분석 · Score 점수 추이 관찰 · 연말정산 재평가 여부 확인 |
| 월간 | 법령/요율 변경 점검(특히 4대보험 요율) · legal_basis 재검증 · 백로그 재정렬 |

상세 운영 절차: [OPERATIONS.md](docs/OPERATIONS.md)

---

## 다음 Sprint 추천

**연말정산 검증 (Phase A 마지막)** — Calculator Quality Standard V1.0 전체 적용.
간이 근사 계산 설계 범위 문서화 + HOLD 해제 + Verified 선언 후 Phase B 진입.
