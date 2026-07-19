# 육아휴직급여 계산기 — Phase 0 Gap Analysis

> 작성일: 2026-07-19 | 수정 금지 단계 (분석 전용)
> 목적: 재설계 규모 확정, Phase 1 범위 정확히 설계하기 위한 선행 진단

---

## 1. 현재 계산 로직 전체 분석

### 1-1. 코드 생성 경로 (app_generator.py)

현재 계산기는 `_compute_js()` 함수의 **제네릭 경로**를 통해 생성됨.

```
slug = "육아휴직_급여_계산기"
  → four-insurances 분기 미해당
  → annual-leave-allowance 분기 미해당
  → date_based 분기 미해당 (compute_type=None)
  → compute_rules 없음 (legal_basis에 validation 없음)
  → 순수 제네릭: input_schema 읽기 → formula 파싱 → 단순 대입식 생성
```

생성된 JS (script.js 실제):
```js
window.computeResult = function(inputs){
  var avg_monthly_wage = inputs["avg_monthly_wage"] || 0;
  var leave_months = inputs["leave_months"] || 0;
  var government_support_percentage = inputs["government_support_percentage"] || 0;
  var company_policy_support_percentage = inputs["company_policy_support_percentage"] || 0;
  var out = {};
  out["total_leave_allowance"] = (
    (avg_monthly_wage * leave_months)
    * ((government_support_percentage + company_policy_support_percentage) / 100)
  );
  return out;
};
```

### 1-2. 현재 입력/출력/공식

| 요소 | 현재 값 |
|------|---------|
| 입력 1 | `avg_monthly_wage` — 월 평균 임금 |
| 입력 2 | `leave_months` — 휴직 기간(개월) |
| 입력 3 | `government_support_percentage` — 정부 지원 비율(%) |
| 입력 4 | `company_policy_support_percentage` — 회사 지원 비율(%) |
| 출력 | `total_leave_allowance` — 예상 육아휴직 급여 총액 |
| 공식 | `avg_monthly_wage × leave_months × (gov_pct + company_pct) / 100` |
| 상한 | **없음** |
| 하한 | **없음** |
| 월별 분기 | **없음** (leave_months를 단순 배수로만 사용) |
| 특례 | **없음** |
| 입력 검증 | **없음** |
| notices | **없음** |
| _formula | **없음** (computeResult에서 미반환) |

### 1-3. 현재 코드가 법령을 반영하지 못하는 구조적 이유

법령에서 지급률(80%/100%)은 **조건에 따라 코드가 결정**해야 하는 값임.  
그런데 현재는 사용자가 `government_support_percentage`에 80을 입력해야만 "80%" 계산이 됨.

→ 사용자가 0 입력 → 급여 0원  
→ 사용자가 120 입력 → 120% 계산 (법령 초과)  
→ 상한/하한 없음 → 과대 계산 무한정 허용

이 구조는 "계산기가 법령을 모른다"는 상태. formula 문자열로는 조건 분기가 불가능함.

---

## 2. 법령 기준 모델

### 2-1. 근거 조문

| 조문 | 내용 |
|------|------|
| 고용보험법 제70조 ① | 30일 이상 육아휴직 + 피보험단위기간 180일 이상 → 급여 지급 |
| 고용보험법 시행령 제95조 | 지급액 = 통상임금 × 지급률, 단 상한/하한 적용 (매년 고시) |
| 고용보험법 시행령 제95조의3 | 6+6 부모 육아휴직 특례: 2024년 1월 1일 시행 |
| 남녀고용평등법 제19조 | 육아휴직 12개월 — 법적 권리 (사업주 재량 아님) |

### 2-2. 일반 육아휴직급여 (2024년 기준)

```
monthly_allowance = clamp(
    monthly_wage × 0.80,
    min=700,000원,
    max=1,500,000원
)
```

| 항목 | 값 |
|------|-----|
| 지급률 | 통상임금 × 80% |
| 상한 | 월 150만원 |
| 하한 | 월 70만원 |
| 하한 분기 통상임금 | 875,000원 (× 80% = 700,000원) |
| 상한 분기 통상임금 | 1,875,000원 (× 80% = 1,500,000원) |

### 2-3. 6+6 부모 육아휴직 특례 (2024년 1월 1일 시행)

조건: 부모 모두 육아휴직 사용 + 생후 18개월 이내 자녀

```
if use_66 and 1 <= special_month <= 6:
    monthly_allowance = min(monthly_wage × 1.00, CAP[special_month])
else:
    monthly_allowance = 일반 육아휴직급여 공식
```

| 특례 월 | 지급률 | 월 상한 |
|---------|--------|---------|
| 1개월 | 100% | 2,000,000원 |
| 2개월 | 100% | 2,500,000원 |
| 3개월 | 100% | 3,000,000원 |
| 4개월 | 100% | 3,500,000원 |
| 5개월 | 100% | 4,000,000원 |
| 6개월 | 100% | 4,500,000원 |
| 7~12개월 | → 일반 전환 | 1,500,000원 |

### 2-4. 특례 우선순위

- 일반 vs 6+6: **배타적** (동시 적용 불가)
- 6+6 조건(부모 모두 육아휴직 + 생후 18개월 이내) 충족 시 → 6+6 우선
- 조건 불충족 → 일반 자동 적용
- 1~6개월 이후 → 일반으로 자동 전환

---

## 3. Gap Analysis 표

| 항목 | 현재 상태 | 법령 기준 | Gap | 조치 |
|------|-----------|-----------|-----|------|
| 입력: 지급률 | 사용자 직접 입력 (gov_pct, company_pct) | 법령 고정 (80%/100%) — 사용자 입력 아님 | **설계 오류** | 입력 교체 |
| 입력: 특례 여부 | 없음 | use_66 (일반/6+6 선택) | 누락 | 신규 |
| 입력: 특례 월 | 없음 | special_month (1~6) | 누락 | 신규 |
| 입력: 기간 | leave_months (단순 배수) | 월 1개씩 계산 (일반은 배수 가능) | 불필요 설계 | 교체 |
| 출력: 총액 | total_leave_allowance (총액) | monthly_allowance (월 급여) | 설계 변경 | 교체 |
| 지급률 계산 | (gov_pct + company_pct) / 100 | 80% (일반) / 100% (6+6) | **근본 오류** | 교체 |
| 상한 | 없음 | 150만원 (일반), 200~450만원 (6+6 월별) | 누락 | 신규 |
| 하한 | 없음 | 70만원 | 누락 | 신규 |
| 특례 분기 | 없음 | use_66 조건 → 별도 계산 | 누락 | 신규 |
| 월별 계단 cap | 없음 | 6+6 1~6월 각 다른 상한 | 누락 | 신규 |
| 입력 검증 | 없음 | 음수/0 → null | 누락 | 신규 |
| notices | 없음 | 상한 초과 경고 등 | 누락 | 신규 |
| _formula | 없음 | "통상임금 N원 × 80% = M원" 등 | 누락 | 신규 |
| formula 필드 | 단순 수식 문자열 | 분기 로직 → 문자열 표현 불가 | **구조 한계** | 커스텀 분기로 대체 |
| legal_basis 시행령 | 미등재 | 시행령 제95조, 제95조의3 필요 | 누락 | 추가 |

**불필요한 기능** (제거 대상):
- `government_support_percentage` 입력 — 법령 고정값이므로 사용자 입력 불필요
- `company_policy_support_percentage` 입력 — 육아휴직급여는 고용보험 지급, 회사 지원 별도

---

## 4. 재설계 규모 결론

### 제네릭 코드 생성 경로의 능력 한계

현재 `_compute_js()`의 제네릭 경로는:
- 단일 수식 문자열 → JS 대입식으로 1:1 변환
- if/else 분기 불가
- min/max 클램프 불가
- notices 배열 불가
- 딕셔너리(월별 cap) 불가

6+6 특례 + 상한/하한 클램프를 formula 문자열로 표현하는 것은 **구조적으로 불가능**.

### 3단계 판정

> **계산 엔진 신규 작성 필요 (3단계)**

- 기존 함수 부분 수정: ❌ — 공식 자체가 잘못됨, 상한/하한/특례 구조 없음
- 일부 함수 교체: ❌ — formula 필드 기반 제네릭 경로 자체가 이 요구사항을 처리 못함
- **계산 엔진 신규 작성**: ✅ — `app_generator.py`에 `"육아휴직_급여_계산기"` 전용 slug 분기 추가 (four-insurances, annual-leave-allowance와 동일 방식)

### 신규 작성 범위 (명확한 경계)

**app_generator.py에 추가할 분기 (40~50줄 수준):**
```python
if str(calc.get("slug", "")) == "육아휴직_급여_계산기":
    return (
        'window.computeResult = function(inputs){\n'
        '  var monthly_wage = inputs["monthly_wage"] || 0;\n'
        '  var use_66 = inputs["use_66"] || 0;\n'
        '  var special_month = inputs["special_month"] || 0;\n'
        '  if (monthly_wage <= 0) { return null; }\n'
        '  var CAP_66 = {1:2000000,2:2500000,3:3000000,4:3500000,5:4000000,6:4500000};\n'
        '  var out = {};\n'
        '  var notices = [];\n'
        '  var allowance;\n'
        '  if (use_66 && special_month >= 1 && special_month <= 6) {\n'
        '    var raw66 = monthly_wage;\n'           # 100%
        '    allowance = Math.min(raw66, CAP_66[special_month]);\n'
        '    out._formula = ...;\n'
        '  } else {\n'
        '    var raw = monthly_wage * 0.80;\n'
        '    allowance = Math.min(Math.max(raw, 700000), 1500000);\n'
        '    out._formula = ...;\n'
        '  }\n'
        '  out["monthly_allowance"] = allowance;\n'
        '  out.notices = notices;\n'
        '  return out;\n};\n'
    )
```

**DB 필드 교체 (fix_pl_phase2.py 수준):**
- `input_schema`: `{"monthly_wage":"number","use_66":"number","special_month":"number"}`
- `output_schema`: `{"monthly_allowance":"number"}`
- `formula`: 비우거나 None (커스텀 분기가 처리)
- `labels`: 새 라벨

---

## 5. 영향 범위 체크리스트

| 파일/컴포넌트 | 영향 | 작업 유형 | 순서 |
|---|---|---|---|
| `modules/app_generator.py` | ✅ **높음** | 신규 slug 분기 약 50줄 추가 | Phase 2 |
| `data/workspace/.../script.js` | ✅ **높음** | 재생성 | Phase 2 (regen) |
| `data/workspace/.../index.html` | ✅ **높음** | 입력 필드 재생성 | Phase 2 (regen) |
| DB `formula` 필드 | ✅ **높음** | None으로 교체 (커스텀 분기 사용) | Phase 2 |
| DB `input_schema` 필드 | ✅ **높음** | 3개 입력으로 교체 | Phase 2 |
| DB `output_schema` 필드 | ✅ **높음** | monthly_allowance로 교체 | Phase 2 |
| DB `labels` 필드 | ✅ **높음** | 새 라벨로 교체 | Phase 2 |
| DB `faq` 필드 | ✅ **높음** | PL-3~6 교정 + FAQ[2] 재작성 | Phase 1 (일부 먼저) |
| DB `article_content` 필드 | ✅ **높음** | PL-3~5 교정 (재생성 시 덮어씌워짐 주의) | Phase 2 재생성 후 |
| `docs/legal_basis.draft.yaml` | 🟡 **중간** | 시행령 제95조, 제95조의3 추가, compute_rules 갱신 | Phase 2 전 |
| `tests/golden/calculator_snapshots.json` | ✅ **높음** | SHA256 갱신 | Phase 2 후 |
| `tests/test_parental_leave_compute.py` | ✅ **높음** | 신규 작성 (20~30케이스) | Phase 2 후 |
| `docs/reference_cases/parental_leave_diagnosis.md` | 🟡 **중간** | 기존 파일 있음, 업데이트 | Phase 2 후 |
| `KNOWN_ISSUES.md` | 🟡 **중간** | Phase별 해결 이력 업데이트 | 각 Phase 후 |

**영향 없는 파일:**
- `style.css` — 계산기 공통 CSS, 변경 없음
- `components.js` — 공통 UI, 변경 없음
- 다른 계산기 파일 — 독립적

---

## 6. PL-3~6 처리 시점 제안

### PL-3~5 — 재설계와 독립, Phase 1으로 먼저

| 코드 | 내용 | 처리 방식 |
|------|------|----------|
| PL-3 | FAQ[0] 자녀 연령 "출산 후 1년" → 만 8세 이하 | DB faq만 수정, index.html 무관 |
| PL-4 | FAQ[1] 피보험단위기간 180일 + 원칙-예외 구조 | DB faq만 수정 |
| PL-5 | FAQ[6] 육아휴직 권리 "회사 정책" 오류 | DB faq만 수정 |

이 3건은 **faq JSON 필드만 건드리므로 재설계와 완전히 독립**. 즉시 진행 가능.

### PL-6 — 재설계 완료 후 자동 해결 또는 Phase 1에서 내용만 교체

| 코드 | 내용 | 처리 방식 |
|------|------|----------|
| PL-6 | FAQ[2] 코드 변수명 노출 + 계산 구조 오류 서술 | faq[2] 내용을 올바른 계산 방식으로 교체 |

FAQ[2]는 계산 방식을 설명하는 문항이므로, 올바른 내용(80%/6+6 특례 구조)으로 교체해야 함.  
재설계 후 새 계산 구조가 확정되면 정확하게 쓸 수 있으므로, **Phase 1에서 임시 교체 또는 Phase 2 완료 후 교체** — 어느 쪽도 가능.

**권고 순서:**
```
Phase 1 (즉시): PL-3, PL-4, PL-5, PL-13 — faq 내용 교정
Phase 2 (재설계): app_generator.py + DB 스키마 교체 + 재생성
Phase 2 후:     PL-6 FAQ[2] 교체, article_content 교정, notices, _formula, 테스트
```

---

## 최종 요약

| | |
|---|---|
| **재설계 규모** | **계산 엔진 신규 작성 (3단계)** |
| **핵심 이유** | formula 문자열 기반 제네릭 경로는 if/else·min/max·딕셔너리 처리 불가 |
| **구현 방법** | `app_generator.py`에 `"육아휴직_급여_계산기"` 전용 slug 분기 추가 |
| **코드 규모** | app_generator.py +50줄, DB 스키마 교체, 재생성 스크립트 |
| **콘텐츠 오류 처리** | PL-3/4/5 먼저 (재설계와 독립) / PL-6 재설계 후 |
| **테스트** | 신규 20~30케이스 작성 필요 |
| **기존 5개 계산기 영향** | 없음 (slug 분기 독립, 공통 경로 무변경) |
