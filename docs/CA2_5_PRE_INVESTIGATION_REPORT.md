# CA-2-5 사전조사 보고서: Formula 제안·검증·확정 구조

**작성일**: 2026-08-10  
**조사 범위**: 코드/YAML 수정 없음. 읽기 전용 조사.  
**핵심 원칙**: AI가 법적 계산식을 자동 확정하지 않는다. AI는 formula를 "제안"할 수 있지만, Contract에 확정되는 값은 운영자 확인을 거쳐야 한다.

---

## I. calculation_flow 전수조사 결과 (8개 엔티티)

| entity_id | confidence | formula 변환 가능성 | 필요 변수 | 위험 요소 |
|-----------|------------|-------------------|-----------|----------|
| `labor_standards_act_55` | high | **높음** | hourly_wage, weekly_hours | 조건(주 15시간 미만)은 formula 밖 처리 필요. ÷5×8 vs ÷40×8 표기 차이 |
| `income_tax_act_127` | high | **높음** | total_income | 가장 단순. 3.3% 고정 — 요율 변경 시 formula 하드코딩 문제 |
| `worker_retirement_benefit_act_8` | high | **중간** | avg_monthly_wage, total_days | 법정 방식(일액×30×일수÷365)과 간이 방식(월평균×일수÷365) 중 선택 불확실. legal_master 자체에 "※ 간이 방식 사용" 주석 있음 |
| `four_major_insurances` | high | **중간** | monthly_salary | 요율 5개가 명시적. 매년 변경 — formula 하드코딩 시 유지보수 문제. dict formula 필요 |
| `labor_standards_act_60` | high | **중간** | daily_wage, unused_days | 연차 발생일수 계산(조건·min·max)과 연차수당 계산을 분리해야 함. 미사용 일수를 직접 입력받는 방식으로 단순화 가능 |
| `employment_insurance_act_40` | **medium** | **낮음** | avg_daily_wage, age, employment_months | 소정급여일수 테이블(120~270일) 참조 필요 — formula_engine으로 처리 불가. 상한(66,000원)·하한(최저임금×80%) 매년 변경 |
| `employment_insurance_act_70` | high | **낮음** | monthly_wage, is_6plus6 | 6+6 특례 조건 분기. 상·하한 매년 변경. 이미 CUSTOM_COMPUTE_SLUGS 분류 |
| `income_tax_act_137` | **medium** | **불가** | 총급여, 각종 공제 다수 | 세율 구간별 테이블, 다단계 공제. formula_engine 단일 식 처리 불가. 이미 CUSTOM_COMPUTE_SLUGS 분류 |

---

## II. formula 패턴 분류

### 패턴 A: 단순 산술식 (formula_engine으로 직접 처리 가능)
- `income_tax_act_127`: `total_income * 0.033`
- `labor_standards_act_55`: `hourly_wage * (weekly_hours / 40) * 8`

**특징**: 단일 곱셈/나눗셈. 조건 없음. AI 제안 위험도 **낮음**.  
**주의**: 법정 조건(주 15시간 미만 제외)은 `scope_exclusions`로 명시. formula에 if-else 없어야 함.

### 패턴 B: 다중 출력 곱셈 (dict formula)
- `four_major_insurances`: 4개 출력 키 (국민연금, 건강보험, 장기요양, 고용보험)

**특징**: 요율 값이 legal_master에 명시. AI 제안 위험도 **중간** (요율 연도 혼동 가능).  
**주의**: 장기요양보험 = 건강보험료 × 12.95% — 중간 계산 값 재사용으로 dict formula 필요.

### 패턴 C: 날짜/기간 기반 (calc_slug 단위 간이화 필요)
- `worker_retirement_benefit_act_8`: 법정 방식 vs 간이 방식 선택 문제

**특징**: legal_master 자체가 두 방식을 병기. AI가 선택 기준 없이 하나를 선택할 위험.  
**주의**: 운영자가 어느 방식인지 명시해야 한다. AI에게만 맡기면 안 됨.

### 패턴 D: 조건·min/max 포함 (부분 단순화 필요)
- `labor_standards_act_60`: 연차 발생일수 + 연차수당 2단계

**특징**: 연차 발생일수 계산(`15 + min(max(0, (근속연수-1)//2), 10)`)과 수당 계산 분리.  
기존: `annual-leave-remaining`(발생일수)과 `annual-leave-allowance`(수당)으로 이미 분리.  
**주의**: formula에 min/max 포함 가능 (formula_engine 지원). 그러나 AI가 누락할 위험.

### 패턴 E: 구간별 테이블 참조 (formula_engine 처리 불가)
- `employment_insurance_act_40`: 소정급여일수 테이블 (나이·피보험기간 matrix)

**특징**: 이중 조건 테이블. formula_engine으로 표현 불가. CUSTOM_COMPUTE_SLUGS 처리 필요.  
**위험**: AI가 테이블 없이 단순 곱셈식만 제안할 경우 불완전 계산기가 됨. confidence=medium 추가 주의.

### 패턴 F: 다단계 공제 + 세율 구간 (formula_engine 처리 불가)
- `income_tax_act_137`: 연말정산 6~45% 누진세율 + 다단계 공제

**특징**: 이미 CUSTOM_COMPUTE_SLUGS 분류됨. formula 단일 식으로 표현 자체가 불가능.  
confidence=medium — 세부 공제 항목 법률 불확실성 있음.

---

## III. validate_formula() 현재 한계 (3단계 검증 구분)

### 현재 구현 (modules/formula_engine.py)

```
허용 연산자: +, -, *, /, //, %, ** (지수 최대 8)
허용 함수  : min, max, round, abs, int, float
금지 구문  : Attribute, Subscript, Lambda, ListComp, comprehension
변수 검증  : input_schema.keys()에 없는 이름 → FAIL
             단, _FUNCS 이름(min/max 등)은 변수 검증 제외 (HOLD-3 수정 완료)
```

### 3단계 검증 현황

#### Level 1: 문법적으로 유효한 formula
- **현재 상태**: `validate_formula(formula, {})` — 완전 구현. ast 파싱 + 화이트리스트 검증.
- **감지 가능**: 한글 포함, 금지 구문, 미지원 연산자
- **감지 불가**: 논리 오류

#### Level 2: Contract 변수와 정합한 formula
- **현재 상태**: `validate_formula(formula, input_schema)` — 완전 구현.
- **감지 가능**: `input_schema`에 없는 변수 (`some_unknown_variable` → FAIL 실증)
- **감지 불가**: output_fields와 dict formula 출력 키 일치 여부 (output_schema 검증 없음)

#### Level 3: 실제 계산 결과가 맞는 formula
- **현재 상태**: `validate_formula_with_samples(formula, input_schema, test_cases)` — **이미 구현됨**
- **실증 결과**:
  ```
  잘못된 주휴수당 formula: hourly_wage * weekly_hours
  → test_case: 10000 × 40 = 400,000원 (실제: 80,000원)
  → match=False 감지 성공
  ```
- **감지 가능**: test_cases와 실제 계산 결과 불일치
- **감지 불가**: 법률 의미 오류 (법적으로 잘못된 근거를 test_cases 자체가 잘못 설정한 경우)

### output field 연결 검증 현황
- `dict formula`의 출력 키 (`net_pay`, `tax` 등)가 Contract `output_fields`와 일치하는지 **검증 없음**
- 현재 `validate_formula()`는 `input_schema`만 받음
- `output_schema`는 `execute_formula(formula, inputs, output_schema)`에서 단일 식의 출력 키 매핑에만 사용

---

## IV. formula 상태 전이 후보

### 현재 상태 (CA-2-1 구현)
```
not_generated   ← formula=None 또는 ""
operator_confirmed  ← formula가 운영자 입력으로 존재
```

### 추가 필요 상태 분석

#### `ai_suggested` (신규 필요)
```
not_generated → ai_suggested → operator_confirmed
```
**필요 이유**: AI가 calculation_flow에서 formula를 제안했지만 운영자가 아직 확인하지 않은 중간 상태.  
현재 2개 상태로는 이 구분 불가 → 운영자가 확인 전 `operator_confirmed`를 사용하면 의미 훼손.

#### `validation_failed` (신규 필요)
```
ai_suggested → validation_failed (validate_formula_with_samples 실패 시)
```
**필요 이유**: `validate_formula_with_samples()` 실행 후 test_cases 불일치 발견 시.  
현재는 실패해도 상태 반영 방법이 없음.

### 권장 4개 상태
```
not_generated      → formula 없음 (기본값)
ai_suggested       → AI 제안, 운영자 미확인
validation_failed  → validate_formula_with_samples() FAIL
operator_confirmed → 운영자 확인 완료
```

**중요**: 이번 CA-2-5에서 코드 구현 않음. 상태 도출 규칙은 CA-2-6에서 설계.

---

## V. AI Formula 제안 방식 설계 후보

### 입력 구조 (AI에게 전달해야 할 정보)

```python
{
    "calc_name":        "퇴직금 계산기",
    "category":         "노무/급여",
    "input_fields":     ["avg_monthly_wage", "total_days"],
    "output_fields":    ["severance_pay"],
    "calculation_flow": [
        "계속근로 1년 미만이면 지급 대상 아님",
        "퇴직금 = 평균임금 일액 × 30 × (계속근로일수 ÷ 365)",
        "※ 이 계산기는 avg_monthly_wage × (총근속일수 ÷ 365) 간이 방식 사용"
    ],
    "legal_refs":       ["worker_retirement_benefit_act_8"],
    "scope_exclusions": ["계속근로 1년 미만 제외"],
}
```

### 출력 구조 (AI 반환 구조화 결과)

```python
{
    "formula":          "avg_monthly_wage * (total_days / 365)",
    "reasoning_summary": "법정 일액 방식 대신 법령 주석에 명시된 간이 방식 채택. ...",
    "required_variables": ["avg_monthly_wage", "total_days"],
    "warnings": [
        "법정 방식과 간이 방식의 결과가 다를 수 있음",
        "1년 미만 조건은 scope_exclusions에서만 처리"
    ],
    "formula_status": "ai_suggested"
}
```

**핵심**: AI 반환값의 `formula_status`는 항상 `ai_suggested`. 운영자 확인 전 `operator_confirmed` 절대 불가.

---

## VI. 주요 위험과 차단 위치

### 위험 1: AI가 자연어 법률을 잘못 해석하여 formula 생성
**예시**: `employment_insurance_act_40`에서 상한/하한을 포함한 완전한 formula를 만들려 시도 → 테이블 참조 누락  
**차단 위치**: validate_formula_with_samples() + test_cases 불일치 → `validation_failed`  
**근본 방어**: confidence=medium 엔티티는 HOLD-3 경고로 주의 환기 (CA-2-3 구현됨)

### 위험 2: formula 문법 정상 but 계산 논리 오류
**예시**: `hourly_wage * weekly_hours` (주휴수당 조건 미적용)  
**차단 위치**: validate_formula_with_samples() → test_cases match=False 감지 **가능** (실증 완료)  
**전제 조건**: test_cases가 정확해야 함. 없으면 HOLD-2 경고 (CA-2-3 구현됨)

### 위험 3: input_fields에 없는 변수를 formula에 사용
**예시**: `base_pay * some_unknown_variable`  
**차단 위치**: validate_formula(formula, input_schema) Level 2 → FAIL 즉시 반환 **가능** (실증 완료)  
**참고**: `min`, `max` 등 허용 함수명은 이미 예외 처리 (HOLD-3 수정됨)

### 위험 4: formula에 존재하지만 test_cases에서 검증 안 된 분기
**예시**: min/max 포함 formula에서 경계값 test_case 없음  
**차단 위치**: 현재 시스템으로 자동 차단 불가. 운영자가 경계값 test_case를 직접 추가해야 함  
**보완책**: HOLD-2 — test_cases 없으면 생성 전 경고 (CA-2-3 구현됨). 단, test_cases 충분성은 검증 안 함

### 위험 5: 법정 상한/하한 또는 조건문을 AI가 누락
**예시**: 실업급여에서 상한(66,000원/일) 하한(최저임금×80%) 누락  
**차단 위치**: test_cases에 상한 경계값 케이스 포함 시 match=False로 감지 가능  
**한계**: test_cases 자체에 경계값 케이스가 없으면 통과. 자동 생성 불가 → CA-3 범위

---

## VII. test_cases와 Formula 연계 가능성 분석

### 현재 `validate_formula_with_samples()` 구현 확인 (formula_engine.py:205~240)

```python
def validate_formula_with_samples(formula, input_schema, test_cases):
    # Level 1/2: validate_formula() 호출
    ok, msg = validate_formula(formula, input_schema)
    # Level 3: test_cases 순서대로 execute_formula() 실행 후 expected 비교
    for tc in test_cases:
        output = execute_formula(formula, tc["input"])
        match = (output == tc["expected"]) if expected else None
        result["sample_results"].append({...})
```

### 실측 결과

| 검증 항목 | 현재 가능 여부 | 실증 |
|----------|-------------|------|
| formula 문법 검증 | ✓ 가능 | Level 1 |
| input_fields 정합 검증 | ✓ 가능 | `some_unknown_variable` → FAIL |
| test_cases 실행 검증 | ✓ 가능 | 잘못된 formula → match=False |
| dict formula 다중 출력 | ✓ 가능 | `net_pay`, `tax` 두 키 정상 반환 |
| output_fields ↔ dict formula 키 대조 | ✗ 미구현 | output_schema 파라미터 미사용 |
| 경계값 자동 생성 | ✗ 불가 | CA-3 범위 |
| 법적 의미 검증 | ✗ 불가 | AI도 보증 불가 |

### test_cases 구조와 formula 실행의 호환성
현재 Contract `test_cases` 구조: `[{"input": {...}, "expected": {...}}]`

- `execute_formula(formula, inp)` 반환: `{"result": 값}` (단일 식) 또는 `{출력키: 값}` (dict)
- **불일치 주의**: 단일 식 formula의 경우 출력 키가 `"result"`이지만, test_cases의 expected가 `{"severance_pay": 3000000}` 형식이면 `match=False`
- **권장 수정 (CA-2-6)**: `validate_formula_with_samples()` 호출 시 output_schema 전달하여 output key 매핑 통일 필요

---

## VIII. 후보 A/B/C 비교

### 후보 A: calculation_flow → AI formula 생성 → validate_formula() → operator_confirmed

```
calculation_flow
     ↓
AI formula 제안 (ai_suggested)
     ↓
validate_formula(formula, input_schema)   ← Level 1/2 검증만
     ↓
operator_confirmed                         ← 운영자 클릭만
```

**장점**: 구현 단순. 현재 코드 변경 최소.  
**단점**:
- test_cases 실행 검증 없음 → 논리 오류 감지 불가
- validate_formula_with_samples()가 이미 있는데 활용하지 않음
- "운영자 확인"이 클릭 한 번으로 완료 → 실질 검증 없는 확정 위험

### 후보 B: calculation_flow → AI formula 제안 → validate_formula() → test_cases 실행 → 운영자 확인 → operator_confirmed

```
calculation_flow
     ↓
AI formula 제안 (ai_suggested)
     ↓
validate_formula(formula, input_schema)   ← Level 1/2
     ↓ FAIL → validation_failed, 재제안 요청
validate_formula_with_samples(formula, input_schema, test_cases)  ← Level 3
     ↓ match=False → validation_failed
운영자 확인 (결과 화면 표시)
     ↓ 확인
operator_confirmed → Contract Instance 저장
```

**장점**:
- `validate_formula_with_samples()` 이미 구현됨 → 추가 구현 최소
- 논리 오류(위험 2)를 test_cases로 감지
- 운영자가 실제 계산 결과를 보고 확인하는 구조
- `validation_failed` 상태 구분 가능

**단점**:
- test_cases가 없으면 Level 3 실행 불가 → HOLD-2 경고와 연동 필요
- AI가 아직 미구현 → 현재는 운영자가 formula를 직접 입력하는 경우에만 적용

### 후보 C: calculation_flow → AI formula 제안 → 자동 검증 → 운영자 확인 → Contract 저장

B와 구조적으로 동일. 차이: "자동 검증"의 범위를 Level 1/2/3 이상으로 확장하는 의도.  
**B와 실질 차이**: 현재 코드로는 Level 4(법적 의미)가 불가 → B와 동일한 범위.  
C의 추가 검증(Level 4)은 외부 법률 DB 또는 LLM 재검증 필요 → CA-3+ 범위.

**결론: 후보 B 권장**

| 기준 | A | B | C |
|------|---|---|---|
| 현재 구현 활용도 | 낮음 | **높음** | 낮음 |
| 논리 오류 감지 | ✗ | **✓** | ✓ |
| 구현 추가량 | 최소 | 소량 | 불명확 |
| 운영자 확인 실질성 | 낮음 | **높음** | 높음 |
| Level 4 지원 | ✗ | ✗ | ✗ (CA-3) |

---

## IX. 기존 계산기 영향 분석

### Registry v3 formula 현황 (전수 확인)

| slug | status | source | formula in Registry | contract_source |
|------|--------|--------|---------------------|-----------------|
| weekly-holiday-allowance | ? | manual | **없음** | 없음 |
| severance-pay | ? | manual | **없음** | 없음 |
| annual-leave-allowance | ? | manual | **없음** | 없음 |
| unemployment-benefit | ? | manual | **없음** | 없음 |
| four-insurances | ? | manual | **없음** | 없음 |
| freelancer-tax-3p3 | ? | manual | **없음** | 없음 |
| 연말정산_환급액_계산기 | ? | manual | **없음** | 없음 |
| 육아휴직_급여_계산기 | ? | manual | **없음** | 없음 |
| annual-leave-remaining | READY | app_factory | **없음** | 없음 |
| jeonse-vs-monthly | READY | app_factory | **없음** | 없음 |

**결론**: Registry v3에는 formula 필드 자체가 없음. formula는 DB(`calculators.formula`)에만 존재.  
DB의 formula 값은 `test_formula_contract.py`의 `FORMULA_CONTRACTS`에 기대값으로 고정 관리.

### Contract Instance가 없는 기존 계산기
- 10개 중 0개가 Contract Instance 보유 (CA-2-4 이전 저장된 계산기 전체)
- `docs/contract_schema/instances/`에 아무 파일도 없음 (정상)
- 이번 단계에서 소급 생성 **하지 않음**

### V1 Feature Freeze 침범 여부
- 기존 계산기 formula 변경: **없음**
- Registry YAML 수정: **없음**
- CUSTOM_COMPUTE_SLUGS 변경: **없음**
- 결론: **침범 없음**

---

## X. CA-2 구현 범위 vs CA-3 이연 범위

### CA-2에서 구현해야 할 것

| 항목 | 필요 이유 | 예상 대상 파일 |
|------|----------|--------------|
| `formula_status`에 `ai_suggested` 추가 | AI 제안과 운영자 확인을 구분하기 위한 상태 | `modules/app_factory.py:build_contract()` |
| `validation_failed` 상태 추가 | `validate_formula_with_samples()` FAIL 결과 반영 | `modules/app_factory.py:build_contract()` |
| `validate_formula_with_samples()` 대시보드 연결 | Mode B Contract Builder에서 formula 입력 후 즉시 Level 1/2/3 검증 표시 | `dashboard.py` |
| output_fields ↔ dict formula 키 대조 | Level 2 강화: `validate_formula(formula, input_schema, output_fields=None)` | `modules/formula_engine.py:validate_formula()` |
| formula 입력/표시 UI (Contract Builder Mode B) | 운영자가 formula를 입력하고 검증 결과를 확인하는 화면 | `dashboard.py` |

### CA-3으로 이연할 것

| 항목 | 이연 이유 |
|------|----------|
| AI formula 자동 제안 (calculation_flow → formula) | AI 호출 로직 미구현. 구조 설계만 CA-2-5에서 완료 |
| legal_master 자연어 → formula 자동 변환 | 패턴 E/F 계산기(테이블 참조, 다단계)는 formula_engine 자체 한계 |
| 자동 test_cases 생성 | 법적 경계값을 AI가 자동으로 생성하는 것은 별도 설계 필요 |
| 법률 의미 검증 (Level 4+) | 외부 법률 DB 또는 LLM 재검증 필요. 현재 infrastructure 없음 |
| 대규모 formula 자동 보강 (기존 계산기 소급) | V1 Feature Freeze. 별도 마이그레이션 계획 필요 |
| CUSTOM_COMPUTE_SLUGS 자동 감지 | 테이블 참조 필요 여부를 자동 판별하는 분류 모델 필요 |

---

## XI. CA-2-5 구현 시 예상 수정 파일

| 파일 | 수정 내용 | 회귀 위험 |
|------|----------|----------|
| `modules/app_factory.py` | `build_contract()` formula_status 상태 추가 (`ai_suggested`, `validation_failed`) | 낮음 — 현재 `operator_confirmed` / `not_generated` 상태는 유지 |
| `modules/formula_engine.py` | `validate_formula()` output_fields 파라미터 추가 (선택적) | 낮음 — 기존 호출 시그니처 유지 가능 |
| `dashboard.py` | Mode B Contract Builder formula 입력 UI + validate_formula_with_samples() 결과 표시 | 중간 — 기존 Mode B 흐름 변경 주의 |
| `tests/test_formula_contract.py` | formula 상태 전이 테스트 + output_fields 대조 테스트 | 낮음 |

---

## XII. 예상 회귀 위험

### 위험 1: `ai_suggested` 상태 추가 시 기존 테스트 영향
`build_contract(formula=...)` 반환의 `formula_status`가 현재 `operator_confirmed`인 테스트들.  
`ai_suggested` 상태는 **새 파라미터 경유**로만 설정 → 기존 `formula != None` 경로는 `operator_confirmed` 유지.  
**회귀 위험**: 낮음.

### 위험 2: `validate_formula()` output_fields 파라미터 추가
기존 호출: `validate_formula(formula, input_schema)` — 변경 없이 유지.  
신규 호출: `validate_formula(formula, input_schema, output_fields=["net_pay"])` — 선택적.  
**회귀 위험**: 낮음 (기본값 None으로 하위 호환).

### 위험 3: dashboard.py Mode B formula 입력 UI 추가
기존 Mode B 흐름 (`generate_app_with_contract()` → `save_app()`)은 변경 없음.  
formula 입력 UI는 `build_contract()` 호출 전 단계에 추가.  
**회귀 위험**: 중간 — dashboard.py는 대형 파일. 기존 Mode B 테스트(`test_af_contract_dashboard.py`) 회귀 확인 필수.

---

## XIII. CA-2-5 판정 (최종 결론)

**Formula 자동생성 구현**:
→ 미실시 (CA-3 이연)

**권장 Formula 흐름**:
```
legal_master.calculation_flow
        ↓ [운영자가 참조하거나, CA-3 AI가 제안]
formula 입력 (dashboard Mode B Contract Builder)
        ↓ 상태: ai_suggested 또는 operator_confirmed
validate_formula(formula, input_schema)           [문법 + 변수 정합]
        ↓ FAIL → validation_failed, 재입력
validate_formula_with_samples(formula, input_schema, test_cases)  [계산 결과]
        ↓ match=False → validation_failed
운영자 검토 (검증 결과 화면 표시)
        ↓ 확인
operator_confirmed
        ↓
Contract Instance 저장 (docs/contract_schema/instances/{slug}.yaml)
```

**CA-2 구현 대상**:
- `formula_status` 상태 추가: `ai_suggested`, `validation_failed` (build_contract 파라미터 확장)
- `validate_formula()` output_fields 대조 강화 (선택적 파라미터)
- dashboard Mode B formula 입력 UI + 검증 결과 표시 (`validate_formula_with_samples()` 연결)
- 관련 단위 테스트 추가

**CA-3 이연**:
- AI formula 자동 제안 (calculation_flow → formula LLM 변환)
- 자동 test_cases 생성
- 법률 의미 검증 (Level 4+)
- 기존 계산기 formula 소급 적용
- 패턴 E/F (테이블 참조) 계산기 formula 자동화
- CUSTOM_COMPUTE_SLUGS 분류 자동화

**기존 계산기 영향**:
- 없음 (Registry YAML 무변경, formula DB 무변경, CUSTOM_COMPUTE_SLUGS 무변경)

**핵심 발견 — 이미 구현된 것**:
`validate_formula_with_samples()` (formula_engine.py:205)이 이미 Level 1+2+3 검증을 지원함.  
CA-2 구현의 핵심 작업은 이 함수를 dashboard Mode B에 **연결하는 것** — 새 검증 로직 구현이 아님.

**CalcMate가 AI 계산식을 신뢰하는 경계**:
```
AI 제안 → 신뢰하지 않음 (ai_suggested)
문법 검증 통과 → 신뢰 시작 가능
test_cases 통과 → 신뢰 조건 충족
운영자 확인 → operator_confirmed (최종 확정)
```
AI가 결정하는 것은 없다. AI는 후보를 만들고, 시스템이 검증하고, 운영자가 확정한다.
