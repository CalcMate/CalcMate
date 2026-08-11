# CA-2-6-2 사전조사 보고서
# Formula Validation → Contract Builder 연결점 조사

작성일: 2026-08-10  
기준 HEAD: CA-2-6-1 완료 (501 PASS / 1 FAIL)  
조사 전용 단계 — 코드 수정 없음

---

## I. 조사 대상 파일 목록

| 파일 | 역할 | 조사 결과 |
|------|------|----------|
| `modules/formula_engine.py` | 핵심 검증 엔진 | 전체 정독 완료 |
| `modules/app_factory.py` | build_contract / check_hold_rules / generate_app_with_contract | 해당 함수 전부 확인 |
| `dashboard.py` | Mode A / Mode B UI | 관련 라인 전부 추적 (L2224–L2496) |
| `tests/test_app_factory_contract.py` | validate_formula_with_samples 기존 테스트 | 전체 확인 |
| `tests/test_af_contract_dashboard.py` | Contract Dashboard 테스트 | 전체 확인 |
| `tests/test_formula_contract.py` | CA-2-4/6-1 테스트 | 전체 확인 |
| `tests/test_review_center.py` | HOLD-1 테스트 | 전체 확인 |
| `docs/registry/labor.yaml` | 단순 산술 계산기 예시 | 확인 |
| `docs/registry/insurance.yaml` | 4대보험(dict formula) | 확인 |
| `docs/registry/labor_af.yaml` | App Factory 생성 계산기 | 확인 |
| `docs/registry/realty_af.yaml` | 전세 vs 월세(dict formula) | 확인 |

---

## II. 현재 Formula Validation 구조

### 함수 위치 및 시그니처

```python
# modules/formula_engine.py:205
def validate_formula_with_samples(
    formula, input_schema: dict, test_cases: list | None = None
) -> dict:
```

### 입력값

| 파라미터 | 타입 | 의미 |
|---------|------|------|
| `formula` | `str` 또는 `dict` | 단일 식(str) 또는 {출력키→식} dict |
| `input_schema` | `dict` | `{필드명: 타입문자열}` — 변수 허용 목록 결정 |
| `test_cases` | `list \| None` | `[{"input": {...}, "expected": {...}}]` |

### 반환값

```python
{
    "valid": bool,
    "message": str,                    # 오류 시 상세 메시지
    "sample_results": [                # test_cases 실행 결과
        {
            "input": dict,
            "output": dict,            # execute_formula() 결과
            "expected": dict | None,
            "match": bool | None,      # expected가 없으면 None
            # "error": str             # 실행 예외 발생 시만 포함
        }
    ]
}
```

### Level 1 / Level 2 / Level 3 의미

Level 1 — **구문 검증** (validate_formula() 내부, AST parse)  
: `ast.parse(expr, mode="eval")` 성공 여부. 허용 연산자/함수 화이트리스트 검사.  
허용 연산자: `+,-,*,/,//,%,**,unary`  
허용 함수: `min, max, round, abs, int, float`  
금지 구문: `Attribute, Subscript, Lambda, ListComp, comprehension`

Level 2 — **변수 검증** (validate_formula() 내부, input_schema 비교)  
: AST walk로 모든 `ast.Name` 노드 추출 → `input_schema.keys()` + `_FUNCS.keys()` 에 없으면 FAIL.  
`input_schema={}` 또는 `None`이면 변수 검증 건너뜀 (`allowed=set()` → 조건 `if allowed` False).

Level 3 — **실행 검증** (validate_formula_with_samples() 내부)  
: `execute_formula(formula, inp, None)` 실제 실행. test_cases 각 입력값으로 계산 → expected와 비교.  
Level 1/2 PASS 후에만 실행된다 (`if ok and test_cases`).

### 검증 실패 시 반환 구조

```python
# Level 1/2 실패 (validate_formula FAIL)
{"valid": False, "message": "input_schema에 없는 변수: ghost_var", "sample_results": []}

# Level 3 실패 (실행 예외)
{
    "valid": True,  # Level 1/2는 통과
    "message": "OK",
    "sample_results": [
        {"input": {...}, "output": None, "expected": {...}, "match": False, "error": "ZeroDivisionError: ..."}
    ]
}

# Level 3 실패 (expected 불일치)
{
    "valid": True,
    "message": "OK",
    "sample_results": [
        {"input": {...}, "output": {"result": 12.0}, "expected": {"result": 99.0}, "match": False}
    ]
}
```

### 예외 발생 가능성

- `ast.parse()` 실패 → `Exception` → `validate_formula()`에서 `try/except` 처리 후 `(False, str(e))` 반환
- `execute_formula()` 실패 → `sample_results` 항목에 `"error": str(e)` 포함, 상위 결과는 `valid=True` 유지
- `validate_formula_with_samples()` 자체가 예외를 던지는 경우는 없음 (모든 예외 포착됨)

### formula 타입별 처리 차이

| 타입 | Level 1/2 처리 | Level 3 처리 |
|------|---------------|-------------|
| `str` 단일 식 | 단일 expr 검증 | `execute_formula` → output_schema 미전달 → 출력키 `"result"` |
| `dict` (출력키→식) | 각 값(expr) 순차 검증 | `execute_formula` → 각 키별 결과 반환 |
| `str` JSON dict | `json.loads()` 후 dict 처리 | 위와 동일 |

**중요**: str formula의 출력키가 `"result"`로 고정된다. Contract의 `output_fields`와 불일치할 수 있음.  
→ str formula의 test_cases `expected` 는 반드시 `{"result": value}` 형식이어야 한다.

### CUSTOM_COMPUTE_SLUGS와의 관계

```python
CUSTOM_COMPUTE_SLUGS = frozenset({"연말정산_환급액_계산기", "육아휴직_급여_계산기"})
```

`validate_formula_with_samples()`는 slug를 파라미터로 받지 않는다.  
CUSTOM_COMPUTE_SLUGS 처리는 `validate_formula(formula, schema, slug=slug)` 에서만 발동한다.  
따라서 `validate_formula_with_samples()`에서는 CUSTOM 분기가 없다.  
CA-2-6-2에서 Contract formula 검증 버튼을 추가할 때, 해당 slug가 CUSTOM_COMPUTE_SLUGS인 경우 검증 버튼을 비활성화하거나 별도 메시지를 표시해야 한다.

---

## III. Contract ↔ Validation 입력 매핑

### 현재 임피던스 불일치 (Impedance Mismatch)

`validate_formula_with_samples()`가 요구하는 `input_schema: dict`는 `{필드명: 타입}` 형식이지만  
Contract의 `input_fields`는 `list[str]` (필드명만, 타입 없음)이다.

| Validation 입력 | Contract 필드 | 현재 존재 여부 | 변환 필요 여부 |
|----------------|--------------|-------------|-------------|
| `formula` | `contract["formula"]` | ✅ 존재 | 없음 (그대로 전달) |
| `input_schema` | `contract["input_fields"]` (list) | ⚠️ 부분 | **필요** — list → dict 변환 |
| `test_cases` (list) | `contract["test_cases"]` | ✅ 존재 | 없음 (그대로 전달) |
| `expected` (각 케이스) | `contract["test_cases"][i]["expected"]` | ✅ 존재 | 없음 |
| calculator slug | `contract["slug"]` | ✅ 존재 | CUSTOM 체크용 |
| `input_schema` 타입 | `contract["input_fields"]` | ❌ 타입 없음 | **단순 변환** 가능 |

### input_schema 변환 방법

```python
# 가장 단순한 변환 — 모든 필드를 "number"로 가정
input_schema = {field: "number" for field in contract["input_fields"]}
```

**이 변환이 유효한 이유**:  
`validate_formula()`의 Level 2는 `_FUNCS`에 없는 `ast.Name.id`가 `allowed` 집합에 있는지만 확인한다.  
타입 문자열("number", "date")의 실제 값은 검사에 사용되지 않는다.  
`execute_formula()`도 `_coerce_numbers(inputs)` → `float(v)`로 모든 값을 강제 변환하므로 타입 무관하다.

**주의**: date 필드는 `float()` 변환이 실패한다 → `0.0`으로 대체된다.  
퇴직금(severance-pay) 같은 date_fields 계산기는 test_cases 실행 시 부정확한 결과가 나올 수 있다.  
→ date_fields가 포함된 계산기는 Level 3 실행 결과를 신뢰하기 어렵다 (Level 1/2는 정상).

---

## IV. test_cases 구조 분석

### 공식 구조

```python
test_cases = [
    {
        "input": {필드명: 값, ...},
        "expected": {출력키: 값, ...}  # optional — 없으면 match=None
    },
    ...
]
```

### 실제 예시 3개

**예시 1: 연차 잔여일 계산기 (dict formula, 다중 출력)**
```python
test_cases = [
    {"input": {"years_of_service": 1, "used_days": 0},
     "expected": {"total_days": 15.0, "remaining_days": 15.0}},
    {"input": {"years_of_service": 3, "used_days": 5},
     "expected": {"total_days": 16.0, "remaining_days": 11.0}},
    {"input": {"years_of_service": 21, "used_days": 0},
     "expected": {"total_days": 25.0, "remaining_days": 25.0}},
]
# expected 키 = formula dict 키와 일치 → match 정상 동작
```

**예시 2: 주휴수당 계산기 (str formula, 단일 출력)**
```python
# formula = "hourly_wage * (weekly_hours / 40) * 8"
test_cases = [
    {"input": {"hourly_wage": 9860, "weekly_hours": 40},
     "expected": {"result": 9860.0}},  # str formula → 출력키 "result"
]
# ⚠️ str formula에서 출력키는 "result" 고정
# contract["output_fields"] = ["weekly_holiday_pay"] 와 다름
# test_cases에서는 "result"로 기대값 설정해야 함
```

**예시 3: 4대보험 계산기 (dict formula, 다중 출력)**
```python
# formula = {"national_pension": "monthly_salary*0.045", "health_insurance": "...", ...}
test_cases = [
    {"input": {"monthly_salary": 3000000},
     "expected": {
         "national_pension": 135000.0,
         "health_insurance": 106350.0,
         "employment_insurance": 27000.0,
         "total": 351456.0,
     }},
]
# expected 키 = formula dict 키와 일치해야 함
```

### str formula의 expected 키 문제 (중요)

```python
# formula = "a + b" (str)
# execute_formula() 결과: {"result": a+b}  ← 키가 "result"
# Contract output_fields = ["sum_value"]  ← 불일치

# test_cases에서 "sum_value" key로 expected 설정하면 match=False
# → str formula 사용 시 test_cases expected는 반드시 {"result": value}
# → dict formula 사용을 권장하는 이유
```

### 여러 output 지원 여부

- **dict formula**: ✅ 다중 출력 완전 지원 (`{"key1": expr1, "key2": expr2}`)
- **str formula**: ❌ 단일 출력만 (`"result"` 키 고정)

---

## V. Formula 유형별 검증 가능성

### 유형 A — 단순 산술 Formula (str)

예: `"hourly_wage * (weekly_hours / 40) * 8"` (주휴수당)  
예: `"daily_wage * unused_days"` (연차수당)  
예: `"avg_daily_wage * 0.6"` (실업급여 기본부분)

**판정: validate_formula_with_samples()로 검증 가능** ✅

근거:
- Level 1: AST parse + 허용 연산자 — 완전 지원
- Level 2: input_fields → `{"field": "number"}` 변환 후 완전 지원
- Level 3: `_coerce_numbers()` → float 변환 → 단순 산술이므로 정상 실행
- 단 `test_cases expected`는 `{"result": value}` 형식이어야 함

### 유형 B — Formula dict / 다중 출력

예: `{"national_pension": "monthly_salary*0.045", ...}` (4대보험)  
예: `{"total_days": "15+min(...)", "remaining_days": "15+min(...)-used_days"}` (연차 잔여일)  
예: `{"jeonse_opp_cost": "jeonse_deposit*(rate/12/100)", ...}` (전세 vs 월세)

**판정: validate_formula_with_samples()로 검증 가능** ✅

근거:
- Level 1/2: `exprs = list(formula.values())` → 각 expr 순차 검증 — 완전 지원
- Level 3: `execute_formula()` → dict formula 분기 → 각 키별 float 결과 반환
- `test_cases expected` 키 = formula dict 키와 일치해야 함 (자연스럽게 매핑)
- date 필드 없는 경우 완전 정확, date 필드 있는 경우 Level 3 부정확

### 유형 C — CUSTOM_COMPUTE_SLUGS

예: `연말정산_환급액_계산기`, `육아휴직_급여_계산기`

**판정: 현재 엔진으로 검증 불가 (partial)** ⚠️

근거:
- 이 계산기들은 `formula = ""` (빈 문자열) — formula가 없으므로 Level 1/2/3 모두 의미 없음
- `validate_compute_handler(slug)` → `_compute_js()` 핸들러 존재만 확인 가능
- `validate_formula_with_samples()`에는 slug 파라미터가 없어 CUSTOM 분기 없음
- CA-2-6-2에서 검증 버튼 표시 시 CUSTOM_COMPUTE_SLUGS는 "커스텀 핸들러 — formula 검증 불가" 메시지 표시

### 유형 D — date_fields 포함 계산기

예: `"avg_monthly_wage * (total_days / 365)"` (퇴직금 — `total_days`는 날짜 계산 결과)

**판정: Level 1/2 가능, Level 3 부정확** ⚠️

근거:
- `start_date`, `end_date`가 input_fields이면 `_coerce_numbers()`에서 `float("2024-01-01")` 실패 → `0.0`
- Level 3 실행은 되지만 결과가 0 기반 계산이므로 test_cases expected와 불일치 가능
- 퇴직금 계산기는 `total_days`를 직접 입력값으로 받는 구조이므로 이 경우는 괜찮음

---

## VI. Validation 결과 상태 설계

CA-2-6-1 확정 상태와 CA-2-6-2에서 추가되는 흐름:

```
formula 없음
    ↓
not_generated  →  HOLD-1 발동

formula 존재 (build_contract 자동 설정)
    ↓
pending_validation  →  HOLD-1 발동

[Formula 검증] 버튼 클릭
    ↓
validate_formula_with_samples() 실행

    ├── PASS (valid=True, 모든 sample match=True)
    │       ↓
    │   pending_validation 유지 (자동 승격 금지)
    │   UI: "✅ 검증 통과 — [Formula 확정] 버튼 활성화"
    │
    ├── FAIL (valid=False 또는 match=False 존재)
    │       ↓
    │   pending_validation 유지
    │   UI: "❌ 검증 실패: {message}" + 불일치 상세 표시
    │
    └── ERROR (실행 예외)
            ↓
        pending_validation 유지
        UI: "⚠️ 실행 오류: {error}"

[Formula 확정] 버튼 클릭 (운영자 명시적 승인)
    ↓
operator_confirmed  →  HOLD-1 해제

Formula 수정 (운영자가 텍스트 변경)
    ↓
pending_validation 복귀 (operator_confirmed 무효화)
    ↓
재검증 필요
```

**핵심 원칙 (지시서 §7 확인)**:  
`operator_confirmed`는 반드시 [Formula 확정] 버튼 클릭으로만 설정. 검증 PASS가 자동 승격하지 않음.

---

## VII. Validation 결과 저장 방식 권장안

### 후보 비교

**A. Contract Instance에 formula_validation 필드 저장**

```yaml
formula_validation:
  status: passed          # passed / failed / error
  level1: passed
  level2: passed
  level3: passed
  validated_at: "2026-08-10T..."
  sample_results: [...]
```

장점: 검증 이력 추적 가능. 다른 세션에서도 상태 복구 가능.  
단점: Dashboard 저장 버튼 없이 검증만 하면 영속화 안 됨. `save_app()` 경유 시 Contract Instance 갱신 필요.

**B. 세션/UI 상태로만 관리** ← **권장**

`st.session_state["af_formula_validation_result"]` 에 검증 결과 저장.  
[Formula 확정] 클릭 시 `st.session_state["af_contract"]["formula_status"] = "operator_confirmed"` 설정.  
`build_contract()` 재호출 없이 session state의 contract dict를 직접 수정.

장점: 구현 단순. 파일 I/O 없음. 세션 안에서 완결. Contract Instance 구조 변경 불필요.  
단점: 브라우저 새로고침 시 초기화. 검증 이력 없음.

**C. 별도 validation 결과 객체**

CA-2-6-1에서 `formula_validation` 필드를 Contract에 추가하는 방안.  
build_contract()에 `formula_validation: dict = None` 파라미터 추가.

장점: Contract 객체에 검증 결과 포함 → save_app() → Contract Instance에 영속화.  
단점: CA-2-6-1 범위 확장. build_contract() 시그니처 변경. CA-2-6-1 테스트 영향.

### 최종 권장: B (세션 관리) — CA-2-6-2 범위

이유:
1. CA-2-6-2 목표는 "Formula 검증 → 운영자 확인 → operator_confirmed 설정"이다.
2. 검증 결과를 영속화하려면 A 또는 C가 필요하지만 그것은 CA-2-6-3으로 이연 가능.
3. B로도 `formula_status = "operator_confirmed"` 설정은 완전히 가능하다.
4. session state에 `af_contract["formula_status"]`를 직접 수정하는 패턴은 이미 Dashboard가 사용 중이다.

---

## VIII. Validation 실행 시점 권장안

### 후보 비교

| 후보 | 설명 | 장점 | 단점 |
|------|------|------|------|
| A — formula 입력 직후 자동 실행 | text_area on_change 또는 매 렌더 | 즉각 피드백 | Streamlit 렌더 루프마다 실행 → 성능 낭비. 입력 중 오류 발생 |
| B — [Formula 검증] 버튼 클릭 | 명시적 버튼 | 운영자 제어. 정확한 시점 | 추가 버튼 클릭 단계 |
| C — [Contract 기반 생성] 버튼 전 자동 실행 | 생성 버튼 클릭 시 사전 검증 | 단계 절약 | Formula 수정 후 재검증 기회 없음. HOLD-1과 혼재 |
| D — Contract 생성 후 별도 검증 | 현재 구조(AI formula 검증) | 기존 구조 유지 | AI formula 기준 검증 — Contract formula 검증 아님 |

### 권장: B — [Formula 검증] 버튼 방식

이유:
- 운영자가 Formula를 여러 번 수정할 수 있다는 점에서 명시적 버튼이 가장 적합하다.
- 검증 결과를 보고 Formula를 다시 수정 → 재검증 → [Formula 확정] 흐름이 자연스럽다.
- Streamlit 구조상 버튼 클릭 → session_state 갱신 → 결과 표시가 가장 안정적이다.
- HOLD-1 경고는 [📋 Contract 기반 생성] 버튼 클릭 시 발동하므로 검증 버튼과 분리된다.

### 구체적 배치 위치 (dashboard.py)

```
현재 구조 (Mode B expander, L2224~L2317):
  [_af_formula text_area]    ← L2244
  [_af_test_cases text_area] ← L2250
  [📋 Contract 기반 생성 button] ← L2257

추가 후 구조:
  [_af_formula text_area]
  [🔍 Formula 검증 button]   ← 신규 추가
      → 결과 표시 (valid / message / sample_results)
      → [✅ Formula 확정 button] (검증 통과 시 활성화)
  [_af_test_cases text_area]
  [📋 Contract 기반 생성 button]
```

`_af_formula` text_area와 `_af_test_cases` text_area 사이에 삽입하는 것이 가장 자연스럽다.

---

## IX. Formula 수정 시 상태 전환

### 현재 코드 구조 분석

현재 Dashboard (L2293–L2304):
```python
_contract = AF.build_contract(
    slug=_slug_clean,
    ...
    formula=_formula_val,   # text_area 값
    test_cases=_test_cases_val,
)
st.session_state["af_contract"] = _contract
```

[📋 Contract 기반 생성] 버튼을 누를 때마다 `build_contract()`를 새로 호출하므로  
Formula 텍스트가 변경되면 자동으로 `formula_status = "pending_validation"`으로 재설정된다.

그러나 **[Formula 확정]** 버튼을 눌러 `operator_confirmed`로 설정한 후  
운영자가 formula text_area를 수정해도 session_state의 contract dict는 그대로다.  
→ formula 텍스트와 contract["formula_status"] 간 불일치 가능.

### 권장 상태 전환 흐름

```python
# [Formula 검증] 버튼 클릭 시
_formula_raw = st.session_state.get("af_contract_formula", "").strip()
_current_contract = st.session_state.get("af_contract") or {}
_current_formula = _current_contract.get("formula")

# formula 텍스트와 contract["formula"] 비교 → 다르면 pending_validation으로 복귀
# (이 체크는 [Formula 확정] 버튼 활성화 전에도 적용)
```

또는 더 단순한 방법:  
[Formula 검증] 버튼 클릭 시 항상 `contract["formula_status"] = "pending_validation"` 설정 후 검증 실행.  
[Formula 확정] 클릭 시에만 `"operator_confirmed"` 설정.  
→ 검증 버튼 자체가 상태를 리셋하므로 formula 수정 감지가 불필요해진다.

**이 패턴이 현재 코드 구조에서 가능한지**: ✅ 가능  
`st.session_state["af_contract"]["formula_status"] = "pending_validation"` 직접 수정 가능.  
단, session_state dict를 직접 mutate하는 방식 — Streamlit 공식 패턴과 일치.

---

## X. Mode A / Mode B 적용 범위

### 현재 코드 분리 상태

**Mode A** (`generate_app()` 직접 호출):
- dashboard.py L2207–L2220: `[AI 자동 생성]` 버튼
- formula 입력 UI 없음 (AI가 자유롭게 생성)
- `st.session_state.pop("af_contract", None)` → contract 없음
- formula_status 개념 없음

**Mode B** (`build_contract()` → `generate_app_with_contract()` 경로):
- dashboard.py L2224–L2317: `📋 Contract 확정 스펙 입력` expander
- `_af_formula` text_area → formula 입력 가능
- `af_contract` session_state → contract 저장
- formula_status: `pending_validation` (CA-2-6-1 이후)

### CA-2-6-2 적용 범위

**Formula Validation은 Mode B에만 적용** ✅

근거:
- 지시서 원칙: "Contract Builder 자동화 기능은 Mode B 중심, Mode A 기존 동작 불변"
- Mode A에는 formula 입력 UI가 없으므로 검증 버튼 삽입 위치 없음
- Mode B의 `_af_formula` text_area 아래에 버튼 삽입이 자연스럽고 코드 분리가 명확

**Mode A 영향 없음**: generate_app(), save_app(), delete_app() 모두 수정 불필요.

---

## XI. HOLD-1 연계

### CA-2-6-1 이후 현재 조건

```python
# modules/app_factory.py:353
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    rules.append("HOLD-1")
```

### 각 상태별 HOLD-1 발동 여부

| formula_status | HOLD-1 발동 | 의도 부합 여부 |
|---------------|------------|-------------|
| `not_generated` | ✅ 발동 | ✅ 올바름 — formula 없음 |
| `pending_validation` | ✅ 발동 | ✅ 올바름 — 미검증 상태 |
| `operator_confirmed` | ❌ 미발동 | ✅ 올바름 — 확정 완료 |

### CA-2-6-2에서 추가될 `validation_failed` 상태 검토

지시서 §7 권장안에 `validation_failed` 상태가 언급되었다.  
현재 조건 `!= "operator_confirmed"`은 `validation_failed`에도 자동으로 HOLD-1을 발동시킨다. ✅  
별도 분기 없이 자연스럽게 처리된다.

### CA-3에서 추가될 `ai_suggested` 상태 검토

`ai_suggested != "operator_confirmed"` → HOLD-1 발동 ✅  
현재 조건은 향후 `ai_suggested` 추가에도 추가 수정 없이 정확하게 동작한다.

**결론**: 현재 HOLD-1 조건 (`!= "operator_confirmed"`)은 CA-2-6-2, CA-3 모두에 대해 올바르다.

---

## XII. 기존 테스트 영향

### 현재 테스트 (CA-2-6-2 구현 후 무영향 확인)

| 테스트 파일 | 관련 테스트 | CA-2-6-2 영향 |
|------------|-----------|-------------|
| `test_app_factory_contract.py` `TestValidateFormulaWithSamples` (9개) | validate_formula_with_samples() 직접 테스트 | **없음** — 함수 수정 없음 |
| `test_af_contract_dashboard.py` `TestSaveBlockedTestCasesFail` (4개) | validate_formula_with_samples() 반환 형식 테스트 | **없음** |
| `test_formula_contract.py` CA-2-6-1 테스트 (5개) | build_contract() formula_status | **없음** |
| `test_review_center.py` HOLD-1 테스트 (2개) | check_hold_rules() | **없음** |
| `test_app_factory_contract.py` Mode A/B 테스트 | generate_app_with_contract() | **없음** |

### CA-2-6-2 구현 시 추가해야 할 테스트 목록

(실제 추가는 구현 단계에서)

| # | 테스트 케이스 | 파일 |
|---|------------|------|
| 1 | Contract formula (str) + input_fields → validate_formula_with_samples() PASS | test_formula_contract.py |
| 2 | Contract formula (dict) + input_fields → validate_formula_with_samples() PASS | test_formula_contract.py |
| 3 | input_fields list → `{field: "number"}` 변환 함수 정확성 | test_formula_contract.py |
| 4 | CUSTOM_COMPUTE_SLUGS slug → 검증 버튼 비활성화 판정 로직 | test_formula_contract.py |
| 5 | [Formula 확정] → formula_status = "operator_confirmed" 설정 | test_af_contract_dashboard.py |
| 6 | formula 수정 후 operator_confirmed → pending_validation 복귀 | test_af_contract_dashboard.py |
| 7 | validation PASS → HOLD-1 여전히 발동 (자동 승격 금지 확인) | test_review_center.py |

---

## XIII. 필수 / 권장 / 후속 변경 목록

### 필수 (CA-2-6-2 구현 필수 범위)

1. **[Formula 검증] 버튼 추가** (`dashboard.py` Mode B expander)
   - `_af_formula` text_area 아래 배치
   - formula + input_fields → `validate_formula_with_samples()` 실행
   - 결과 표시: valid/invalid + sample_results

2. **[Formula 확정] 버튼 추가** (`dashboard.py`)
   - 검증 통과 시 활성화 (비활성화 기본)
   - 클릭 시 `st.session_state["af_contract"]["formula_status"] = "operator_confirmed"`

3. **formula_status 현재 값 표시** (`dashboard.py`)
   - "📊 현재 상태: pending_validation / operator_confirmed" 배지 표시

4. **CUSTOM_COMPUTE_SLUGS 체크** (`dashboard.py`)
   - slug가 CUSTOM_COMPUTE_SLUGS에 있으면 검증 버튼 비활성화 + 안내 메시지

5. **테스트 추가** (7개, test_formula_contract.py + test_af_contract_dashboard.py + test_review_center.py)

### 권장 (CA-2-6-2에서 포함 가능)

6. **validation 결과를 session_state에 저장** (`st.session_state["af_formula_validation_result"]`)
   - 재렌더 시 결과 유지 (버튼 재클릭 없이 결과 표시 지속)

7. **formula 텍스트 변경 감지 → operator_confirmed 무효화**
   - 이전 formula 값을 session_state에 저장 → 다음 렌더에서 비교

### 후속 (CA-2-6-3 또는 CA-3으로 이연)

8. **formula_validation 필드를 Contract Instance에 영속화**
   - `build_contract()`에 `formula_validation: dict = None` 추가
   - `_save_contract_instance()`에서 검증 결과도 함께 저장

9. **validation_failed 상태 명시적 추가**
   - 현재는 pending_validation + session_state 결과로 구분
   - 추후 `formula_status = "validation_failed"` 상태 추가 가능

10. **ai_suggested 상태 (CA-3)**
    - AI가 formula를 자동 제안할 때 `ai_suggested` 설정
    - 현재 HOLD-1 조건 `!= "operator_confirmed"` 이 자동 처리

---

## XIV. CA-2-6-3으로 넘겨야 할 작업

CA-2-6-2 구현 후 남는 작업:

1. **formula_validation 영속화** — Contract Instance에 검증 결과 저장  
   (`docs/contract_schema/instances/{slug}.yaml` 에 `formula_validation` 필드 추가)

2. **validate_formula_with_samples() dashboard 연동 고도화**  
   - Level별 통과/실패 상세 표시 (Level 1/2/3 분리 표시)
   - sample_results 테이블 형식 표시

3. **formula_status transition 자동화 테스트**  
   - 모든 상태 전환 경로 단위 테스트

4. **date 필드 포함 계산기 Level 3 처리 개선**  
   - date 필드를 date 타입으로 파싱 후 실행하는 adapter 추가

---

## XV. 구현 예상 수정 파일 및 변경 범위

| 파일 | 수정 내용 | 예상 변경 범위 | 회귀 위험 |
|------|----------|--------------|----------|
| `dashboard.py` | Mode B expander에 [Formula 검증] + [Formula 확정] 버튼 추가, formula_status 표시 | +30~40줄 | **낮음** — Mode B 내부 추가, Mode A 무영향 |
| `tests/test_formula_contract.py` | 테스트 4개 추가 (input_fields 변환, CUSTOM 체크 등) | +30줄 | 없음 |
| `tests/test_af_contract_dashboard.py` | 테스트 2개 추가 (formula 확정 / 수정 시 복귀) | +20줄 | 없음 |
| `tests/test_review_center.py` | 테스트 1개 추가 (validation PASS 후 HOLD-1 유지 확인) | +10줄 | 없음 |
| `modules/app_factory.py` | 수정 없음 | 0줄 | 없음 |
| `modules/formula_engine.py` | 수정 없음 | 0줄 | 없음 |

**총 예상**: dashboard.py +35줄, 테스트 파일 3개 +60줄 합계  
**핵심**: `modules/` 파일은 수정 없음 — 기존 검증 엔진을 dashboard.py에서 호출만 추가

---

## XVI. 핵심 발견 요약

### 발견 1: validate_formula_with_samples()는 즉시 사용 가능

Contract 필드와의 매핑 변환은 단 한 줄이다:  
```python
input_schema = {field: "number" for field in contract["input_fields"]}
```
추가 adapter 없이 기존 함수를 그대로 호출할 수 있다.

### 발견 2: 현재 Dashboard의 test_cases 검증은 AI formula 기준

dashboard.py L2399–L2403의 기존 `validate_formula_with_samples()` 호출은  
**AI 생성 formula**와 **AI 생성 input_schema**를 사용한다.  
CA-2-6-2에서 추가할 검증은 **Contract formula** + **Contract input_fields** 기준이다.  
이 두 검증은 서로 다른 목적을 가지며, 둘 다 필요하다.

### 발견 3: formula_status가 현재 Dashboard에 전혀 표시되지 않음

grep 결과 dashboard.py에서 `formula_status` 문자열이 전혀 없다.  
CA-2-6-1에서 상태 필드를 추가했지만 운영자에게 보이지 않는 상태.  
CA-2-6-2에서 표시 추가가 필수 항목이다.

### 발견 4: str formula의 expected 키 불일치 주의

str formula → `execute_formula()` → 출력키 `"result"` 고정.  
Contract `output_fields: ["weekly_holiday_pay"]` 와 불일치 가능.  
Dashboard 운영자 안내 문구 또는 dict formula 사용 권장 메시지 필요.

### 발견 5: HOLD-1 조건 (`!= "operator_confirmed"`)은 미래에도 안전

`validation_failed`, `ai_suggested` 등 어떤 상태가 추가되어도  
`!= "operator_confirmed"` 조건이 자동으로 HOLD-1을 발동시킨다.  
app_factory.py 재수정 불필요.

---

*CA-2-6-2 사전조사 완료. 코드 수정 0건.*
