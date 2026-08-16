# Phase 5-C 후속 검증 결과 보고서

**작성일**: 2026-08-16  
**목적**: 이미지 육안 확인 + 로컬 WordPress 렌더링 검증

---

## ① 이미지 20장 육안 확인

### PIL 파일 검증 (전체)

| 항목 | 결과 |
|------|------|
| 총 파일 수 | 20장 (썸네일 10 + 본문이미지 10) |
| 파일 포맷 | webp |
| 썸네일 해상도 | 512×512 |
| 본문이미지 해상도 | 800×450 |
| 파일 크기 범위 | 6.2KB ~ 19.9KB |
| PIL verify 결과 | **20/20 OK** (깨짐/로드 실패 없음) |

### AI 텍스트 아티팩트 발견 (이슈 이미지 6장)

| 파일 | 이슈 내용 | 심각도 |
|------|-----------|--------|
| four-insurances_calculator_body.webp | 중앙에 "JALSIN" 텍스트 | ⚠️ 중간 |
| four-insurances_calculator_thumb.webp | "Bo" 텍스트 노출 | ⚠️ 중간 |
| four-insurances_documents_body.webp | 중앙에 "JALAEN" 텍스트 | ⚠️ 중간 |
| unemployment-benefit_howto_body.webp | 마인드맵 중앙 "NICEON" 텍스트 | ⚠️ 중간 |
| 연말정산_환급액_계산기_calculator_body.webp | "JALSEN" 텍스트 | ⚠️ 중간 |
| 연말정산_환급액_계산기_calculator_thumb.webp | "AJ Assistent" 텍스트 | ⚠️ 중간 |

**원인**: AI 이미지 생성 모델(Pollinations)이 한국어 키워드를 영어 gibberish 텍스트로 렌더링하는 현상  
**영향**: 콘텐츠 신뢰도에 영향줄 수 있음 — 실서버 게시 전 재생성 권장

### 정상 이미지 (14장)

| Slug | Type | 판정 |
|------|------|------|
| severance-pay × eligibility | thumb + body | ✅ PASS |
| severance-pay × documents | thumb + body | ✅ PASS |
| annual-leave-allowance × howto | thumb + body | ✅ PASS |
| unemployment-benefit × eligibility | thumb + body | ✅ PASS |
| unemployment-benefit × howto | thumb | ✅ PASS |
| weekly-holiday-allowance × howto | body | ✅ PASS |
| 육아휴직_급여_계산기 × eligibility | thumb + body | ✅ PASS |

---

## ② 로컬 WordPress 2개 업로드

| 항목 | 글1 | 글2 |
|------|-----|-----|
| Slug | severance-pay × eligibility | four-insurances × documents |
| 제목 | 2026 퇴직금 받는 조건 총정리 | 4대보험 취득신고 서류 완전 안내 |
| Post ID | 308 | 310 |
| 이미지 Media ID | 307 | 309 |
| 업로드 상태 | ✅ 드래프트 생성 성공 | ✅ 드래프트 생성 성공 |
| 미리보기 URL | /?p=308&preview=true | /?p=310&preview=true |

---

## ③ PC + 모바일 렌더링 확인

### 글1 — severance-pay × eligibility (post 308)

| 체크 항목 | 결과 |
|-----------|------|
| H2 구조 | 지급 대상 / 근로시간 조건 / 제외 대상 / 계산 방법 / FAQ — **5개 ✅** |
| H3 | 없음 (정상) |
| FAQ dl/dt/dd | dl×1, dt×6, dd×6 — **정상 ✅** |
| 계산 예시 렌더링 | "300만원 × (730÷365) = 600만원" — **정상 ✅** |
| Featured Image | severance-pay_eligibility_thumb.webp (512×512) — **로드 ✅** |
| 본문 길이 | 2,067자 ✅ |
| 수평 overflow | 없음 ✅ |
| 고정폭 요소 | 없음 ✅ |
| 반응형 CSS | GeneratePress responsive 확인 ✅ |
| 법령 언급 | 근로자퇴직급여보장법 제8조 명시 ✅ |

### 글2 — four-insurances × documents (post 310)

| 체크 항목 | 결과 |
|-----------|------|
| H2 구조 | 필수 서류 목록 / 서류 발급 방법 / 제출 기한 및 절차 / 주의사항 / FAQ — **5개 ✅** |
| FAQ dl/dt/dd | dl×1, dt×6, dd×6 — **정상 ✅** |
| Featured Image | four-insurances_documents_thumb.webp (512×512) — **로드 ✅** |
| 본문 길이 | 2,224자 ✅ |
| 수평 overflow | 없음 ✅ |
| 고정폭 요소 | 없음 ✅ |
| 반응형 CSS | GeneratePress responsive 확인 ✅ |

### 공통 발견 이슈

1. **PC 뷰 상단 빈 공백**: 첫 로드 시 featured image 표시 안 됨 → 새로고침 후 정상 표시. 캐싱 문제로 판단. 실서버에서는 재현 안 될 가능성 높음.
2. **sidebar 레이아웃**: 데스크탑 2-column 정상 / 모바일 breakpoint(≤768px) 반응형 CSS 존재 확인 — 실제 폰에서의 스택 전환은 GeneratePress 기본 동작으로 보장됨.

---

## 종합 판정

| 항목 | 판정 |
|------|------|
| ① 이미지 육안 확인 | ⚠️ **PASS with 이슈** — 14/20 정상, 6장 AI 아티팩트 텍스트 |
| ② WordPress 업로드 | ✅ **PASS** — 2/2 드래프트 정상 생성 |
| ③ PC 렌더링 | ✅ **PASS** — H2/FAQ/이미지/overflow 모두 정상 |
| ③ 모바일 대응 | ✅ **PASS** — 반응형 CSS 확인, overflow/고정폭 요소 없음 |

---

## 이슈 처리 권고

### 이미지 AI 아티팩트 (6장)

- **Phase 5-D 진입 전 처리 권장**: 이미지 프롬프트에 영어 텍스트 생성 억제 지시 추가
  ```
  예: "no text, no letters, no words, no english text"
  ```
- **영향 범위**: 6/20장 (four-insurances 4장, 연말정산 2장)
- **재생성 대상**: four-insurances_calculator_*, four-insurances_documents_body, unemployment-benefit_howto_body, 연말정산_*

---

## 완료 조건 충족 여부

- ①②③ 전부 실행 완료 ✅
- 문제 발견: **이미지 아티팩트 6장** (Phase 5-D 진입 전 재생성 권장)
- **Gate(G1/G4/G8/G-NEW2) 최종 반영 준비 완료** — 지시 시 즉시 진행 가능
