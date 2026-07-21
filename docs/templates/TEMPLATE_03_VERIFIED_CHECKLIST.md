# [계산기명] 계산기 — Verified 승인 체크리스트 템플릿
> Phase F에서 Verified 등록 전 최종 감사용. 모든 항목 ✅ 확인 후 승인.
> 이 파일을 복사해 `docs/reference_cases/[slug]_verified.md`로 저장.

---

## 기본 정보

| 항목 | 내용 |
|---|---|
| 계산기 | [계산기명] ([slug]) |
| 감사 날짜 | YYYY-MM-DD |
| 법령 귀속 연도 / 기준일 | YYYY년 귀속 / 시행일 |
| 감사자 | SalaryMate Dev |

---

## Phase 1 게이트 — 법령 확정

- [ ] **법령 원문 확인**: [법령명] 제XX조 law.go.kr에서 직접 확인
- [ ] **관련 조항 확인**: 시행령 / 시행규칙 / 별표 포함
- [ ] **폐지 조항 없음**: `forbidden_articles` 목록에서 0건 확인
- [ ] **confidence = high**: `legal_basis.draft.yaml` 기록
- [ ] **설계 범위 확정**: v1 포함/제외 합의 완료

---

## Phase 2 게이트 — 계산 구현

### 2-1. 계산식 정확성
- [ ] Python mirror 함수 구현 완료 (`modules/xxx_calculator.py`)
- [ ] `app_generator.py` JS 분기 추가 + Python mirror와 동일 로직 확인

### 2-2. 정부 공식 계산기 비교 (최소 3케이스, 오차 0원)

| 케이스 | 입력 | 정부 결과 | 프로그램 결과 | 오차 |
|---|---|---|---|---|
| A | | | | |
| B | | | | |
| C | | | | |

출처: [정부 계산기 URL / 법령 직접 계산]

### 2-3. 경계값 3점 세트 테스트
| 경계 | 직전 | 기준점 | 직후 |
|---|---|---|---|
| [법적 경계] | ✅/❌ | ✅/❌ | ✅/❌ |

### 2-4. 불변식 (Invariant) 테스트
- [ ] **INV-[N]** [불변식 설명]: [파라미터화 케이스] 수 PASS
- [ ] **INV-[N]** [불변식 설명]: [파라미터화 케이스] 수 PASS

### 2-5. 단위 테스트
- [ ] 총 테스트 케이스: **N개** ALL PASS
- [ ] `tests/test_[slug_snake]_compute.py` 영구 등록

### 2-6. 전체 회귀
- [ ] `py -m pytest tests/ -q` → **NNN passed** ALL PASS

---

## Phase 3 게이트 — 콘텐츠 품질

### 3-1. SP-8 감사 (코드 변수명·구 HTML 노출 금지)
```
검사 대상 변수명: [변수명 목록]
article_content: 0건 ✅
faq: 0건 ✅
```
확인 명령: `py scripts/_sp8_grep_[slug].py`

### 3-2. FAQ 품질
- [ ] 최소 5문항 이상
- [ ] 법령 조항 최소 1회 언급
- [ ] 구체적 수치/조건 포함
- [ ] 원칙→예외 구조 (C-13): FAQ / article HTML FAQ / article 본문 3곳 일관성
- [ ] 지급 제외 케이스 포함

### 3-3. article_content 품질
- [ ] 계산 예시 최소 2개 (compute_xxx() 결과 직접 인용 — 수기 계산 금지)
- [ ] 서로 다른 조건으로 구성
- [ ] v1 설계 범위 외 항목은 "이 계산기에서 다루지 않습니다" 명시
- [ ] 구 HTML form 잔재 0건

### 3-4. _detail / _formula / notices 구조
- [ ] `_detail`: 계산 과정 N단계 표시
- [ ] `_formula`: 1줄 요약 표시
- [ ] `notices`: 경계 조건 / disclaimer 포함

### 3-5. legal_basis 외부화
- [ ] 하드코딩 상수 없음: 요율/금액 모두 `legal_basis.draft.yaml` 경유
- [ ] `content_caveat: null` (완전 구현 확인)

### 3-6. 권리 안내 (C-13)
- [ ] 법적 의무를 임의사항처럼 표현하지 않음
- [ ] 권리를 제한사항처럼 표현하지 않음
- [ ] 원칙 → 예외 순서 서술

---

## 최종 판정

| 항목 | 결과 | 미해결 이슈 |
|---|---|---|
| 법령 정확성 | ✅/❌ | |
| 계산 정확성 | ✅/❌ | |
| 경계값 테스트 | ✅/❌ | |
| 불변식 테스트 | ✅/❌ | |
| SP-8 감사 | ✅/❌ | |
| FAQ 품질 | ✅/❌ | |
| 콘텐츠 정합성 | ✅/❌ | |

**Critical 이슈**: N건  
**Major 이슈**: N건  
**Minor 이슈**: N건 (기능 영향 없음)

### 판정: ✅ Verified / ❌ 미통과 (재작업 필요)

> Critical 0, Major 0 달성 시 Verified 승인 가능.

---

## Verified 등록 후 처리

- [ ] `docs/CALCULATOR_QUALITY_STANDARD_V1.0.md` 트래커 갱신
- [ ] `docs/CALCULATOR_CHANGELOG.md` 버전 이력 추가
- [ ] `tests/golden/calculator_snapshots.json` 해시 갱신
- [ ] 커밋: `docs(verified): [계산기명] 계산기 Verified 등록`
