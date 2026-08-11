# CA-2-6-1 사전조사 보고서: Formula Status State Machine

**작성일**: 2026-08-10  
**조사 범위**: 코드/YAML 수정 없음. 읽기 전용 조사.  
**선행 작업**: CA-2-1(formula_status 2-상태), CA-2-3(HOLD-1/2/3), CA-2-4(Contract Instance), CA-2-5(validate_formula_with_samples 확인)

---

## I. 현재 formula_status 사용처 전수조사

### 코드 기준 사용처

| 파일 | 위치 | 읽기/쓰기 | 현재 의미 | 변경 필요 |
|------|------|---------|----------|----------|
| `modules/app_factory.py:316` | `build_contract()` 반환 | **쓰기** | `formula != None → "operator_confirmed"`, 없으면 `"not_generated"` | **필요** (ai_suggested 분기 추가) |
| `modules/app_factory.py:319` | `build_contract()` 반환 | **쓰기** | `test_cases → "operator_confirmed"`, 없으면 `"not_generated"` | **필요** (동일 패턴) |
| `modules/app_factory.py:343` | `check_hold_rules()` | **읽기 (분기 조건)** | `== "not_generated"` → HOLD-1 경고 발동 | **필요** (`!= "operator_confirmed"`으로 확장) |
| `modules/app_factory.py:351` | `check_hold_rules()` | **읽기 (분기 조건)** | `test_cases_status == "not_generated"` AND critical → HOLD-2 | 필요 없음 |
| `modules/app_factory.py:155` | `_build_v3_entry()` | **읽기 (전달)** | `contract_source.formula_status`에 그대로 저장 | 필요 없음 |
| `modules/app_factory.py:796` | `_update_contract_registry()` | **읽기/쓰기** | `registry.yaml` 인덱스에 formula_status 값 저장 | 필요 없음 |
| `dashboard.py:2248` | Contract 입력 UI | 참조 안 함 | formula 텍스트 입력 위젯(`af_contract_formula` key) | 향후 CA-2-6-2에서 상태 표시 |
| `dashboard.py:2371` | Contract 검증 결과 표시 | 참조 안 함 | `_cv.get("formula_changed")` 만 참조 | 향후 CA-2-6-2에서 status 표시 |
| `tests/test_formula_contract.py:187` | Contract Instance 테스트 | **읽기** | `assert entry["formula_status"] == "operator_confirmed"` | 필요 없음 (하위 호환 유지 전제) |

### 핵심 발견: formula_status 사용 패턴

**분기 조건으로 사용**: `check_hold_rules()` 단 1곳
```python
# app_factory.py:343
if contract.get("formula_status", "not_generated") == "not_generated":
    rules.append("HOLD-1")
```
→ 현재 HOLD-1은 `== "not_generated"` 에만 발동. `ai_suggested` 추가 시 이 조건이 누락됨.

**단순 전달값**: `_build_v3_entry()`, `_update_contract_registry()`, `_save_contract_instance()`  
→ 값을 읽어서 그대로 저장. 상태 추가해도 코드 변경 불필요.

---

## II. Formula 전체 데이터 흐름 추적

```
[1] 운영자 입력
    dashboard.py:2248  af_contract_formula (text_area)
    dashboard.py:2293  build_contract(formula=af_formula_str, ...)
                                         ↑
                           formula 있음 → formula_status = "operator_confirmed"
                           formula 없음 → formula_status = "not_generated"
    ★ 현재: build_contract()는 validation 미수행. 값 유무만으로 상태 결정.

[2] Pre-gen 체크
    dashboard.py:2307  check_hold_rules(_contract)
    app_factory.py:343  formula_status == "not_generated" → HOLD-1 경고
    ★ formula 있으면 HOLD-1 없음 (설령 validation을 아직 안 했어도)

[3] AI 생성
    generate_app_with_contract(cfg, contract)
    → generate_app(..., _contract=contract)
    → validate_against_contract(contract, ai_result)
       └─ formula 변경 여부 비교 (contract.formula vs ai_result.formula)
    → result["_contract"] = contract   ← formula_status 원본 그대로 embed
    → result["_contract_validation"] = {valid, formula_changed, ...}
    ★ formula_status는 변경 없음. contract 원본 그대로 전달.

[4] 저장
    save_app(cfg, app, slug=slug_in)
    → _build_v3_entry(app, slug, contract=app.get("_contract"))
       └─ contract_source.formula_status = contract["formula_status"]   ← 그대로
    → _write_registry_v3(slug, entry, category)
    → _save_contract_instance(slug, app["_contract"])
       └─ contract dict 전체 YAML 저장 → formula_status 포함
    → _update_contract_registry(slug, contract, generated_at)
       └─ registry.yaml에 formula_status 저장

[5] 영속화된 formula_status 위치
    ① Registry v3 (docs/registry/*_af.yaml): contract_source.formula_status
    ② Contract Instance (docs/contract_schema/instances/{slug}.yaml): formula_status (전체)
    ③ Contract Schema registry (docs/contract_schema/registry.yaml): instances.{slug}.formula_status

★ 모든 저장 경로에서 formula_status는 build_contract()가 최초 설정한 값 그대로 전달됨.
   저장 경로 어디에서도 formula_status를 변경하거나 재계산하지 않음.
```

---

## III. validate_formula_with_samples() 구조 분석

### 반환 구조 (formula_engine.py:205~240)

```python
# 반환 dict
{
    "valid": bool,          # Level 1+2 결과 (validate_formula 결과)
    "message": str,         # Level 1+2 메시지 ("OK" 또는 오류 설명)
    "sample_results": [     # Level 3 결과 (test_cases 있을 때만 비어있지 않음)
        {
            "input": dict,       # test_cases의 input
            "output": dict,      # execute_formula(formula, input) 실행 결과
            "expected": dict,    # test_cases의 expected
            "match": bool|None,  # expected == output (expected=None이면 None)
            "error": str,        # 실행 오류 시 (선택적)
        }
    ]
}
```

### 3개 레벨 상세

| Level | 검증 대상 | 성공 결과 | 실패 결과 | 반환 구조 |
|-------|---------|---------|---------|--------|
| **1** | formula 문법 (ast 파싱, 화이트리스트) | `valid=True, message="OK"` | `valid=False, message="허용되지 않은 구문: ..."` | `validate_formula_with_samples().valid` |
| **2** | input_schema에 없는 변수명 | `valid=True` | `valid=False, message="input_schema에 없는 변수: X"` | `validate_formula_with_samples().valid` |
| **3** | test_cases 실행 결과 vs expected | `sr.match=True` (모두) | `sr.match=False` (하나라도) | `validate_formula_with_samples().sample_results` |

### 성공/실패 정의

**전체 검증 성공 조건**:
```
validate_formula_with_samples(formula, input_schema, test_cases) 결과에서:
  result["valid"] == True                           # Level 1+2 통과
  AND
  all(sr["match"] == True for sr in result["sample_results"] if sr.get("expected"))
                                                    # Level 3 전체 통과 (test_cases 있을 때)
```

**검증 실패 조건**:
```
result["valid"] == False                                      # Level 1 또는 2 실패
OR
any(sr["match"] == False for sr in result["sample_results"]) # Level 3 하나라도 불일치
OR
any("error" in sr for sr in result["sample_results"])         # 실행 오류
```

### 현재 미검증 영역

| 검증 항목 | 현재 구현 | 비고 |
|---------|---------|------|
| dict formula의 출력 키 ↔ output_fields 대조 | **미구현** | output_schema 파라미터 미사용 |
| test_cases의 경계값 충분성 | **불가** | 자동 판단 로직 없음 |
| 법적 의미 정확성 | **불가** | 코드로 검증 불가 (CA-3) |

---

## IV. ai_suggested 필요성 검증

### 현재 문제: "formula 있음" = "operator_confirmed" 는 거짓

```python
# 현재 build_contract()
"formula_status": "operator_confirmed" if (formula is not None and formula != "") else "not_generated"
```

이 규칙의 전제: "formula를 build_contract()에 전달하는 주체 = 운영자 = 이미 확인함"  
→ CA-2 이전의 Mode B 경로에서는 이 전제가 성립 (운영자가 직접 dashboard에서 formula 입력)

**ai_suggested가 필요한 시점**: AI가 calculation_flow에서 formula를 자동 제안하는 CA-3 기능 구현 시

**현재(CA-2-6) 기준 판단**:
- AI formula 자동 제안: CA-3으로 이연됨
- 운영자가 dashboard에서 직접 formula를 입력하는 현재 Mode B 경로: `operator_confirmed` 적합

**결론**: `ai_suggested` 상태는 CA-2-6에서 코드에 구현할 필요 없음.  
CA-3에서 AI 제안 기능 구현 시 추가 예정.

단, `build_contract()`에 `formula_status` 파라미터를 외부에서 명시 가능하도록 개방하면,  
CA-3 구현 시 코드 변경 없이 `formula_status="ai_suggested"` 전달 가능.

---

## V. validation_failed 필요성 검증

### 현재 문제: 검증 실패 상태 표현 불가

현재 흐름:
```
운영자가 formula 입력 → build_contract() → formula_status="operator_confirmed"
                                          ↑
                         validate_formula() 미실행
```

dashboard에서 formula를 입력해도 **validate_formula()가 자동 호출되지 않음**.  
check_hold_rules()도 formula_status가 `"not_generated"`인지만 확인.

결과: "formula를 입력했지만 validate_formula() 실패" 상태를 코드에서 표현 불가.

**validation_failed 적용 시나리오**:
```
운영자 formula 입력
    ↓
validate_formula_with_samples() 실행 (CA-2-6-2 dashboard 연결)
    ↓ FAIL
formula_status = "validation_failed"
    ↓ (운영자가 formula 수정 후 재시도)
formula_status = "ai_suggested" → validate → "operator_confirmed"
```

**CA-1A 원본 설계에서의 대응**: `error` 상태 (입력했지만 검증 실패)

**결론**: `validation_failed` (CA-1A의 `error`)는 **CA-2-6-2 dashboard 연결과 함께 구현**해야 의미 있음.  
dashboard에서 validate_formula_with_samples()를 호출하고 결과를 formula_status에 반영해야 함.  
CA-2-6-1 (State Machine 설계)에서는 상태 정의만 확정, 코드 구현은 CA-2-6-2에서.

---

## VI. 상태 머신 후보 비교

### CA-1A 원본 설계 (참조)

CA-1A에서 이미 4개 상태를 정의했음:
```
not_generated / auto_disabled / operator_confirmed / error
```
CA-2-1에서 "현재 AF-Contract 경로에서 발생 가능한 상태는 2개"로 단순화.  
CA-2-6에서는 이 2개를 CA-3 준비를 위해 확장하는 것이 목적.

---

### 후보 A: 현재 구조 유지
```
not_generated ──→ operator_confirmed
```
- **장점**: 변경 없음, 테스트 안정
- **단점**: "formula 있지만 검증 실패" 표현 불가, AI 제안 구분 불가
- **적합 조건**: CA-3 AI 기능 구현 계획 없을 때
- **현재 CalcMate**: ✗ (CA-3 준비 필요)

---

### 후보 B: ai_suggested 추가, validation_result 별도 필드
```
not_generated ──→ ai_suggested ──→ operator_confirmed
                         ↑ (formula 수정)
```
- validation 결과: `formula_validation: {valid, level, errors, sample_results}` 별도 필드
- `validation_failed` 상태 없음 → `ai_suggested` + `formula_validation.valid=False`로 표현

**장점**:
- 상태 3개로 단순
- "검증 통과했지만 운영자 미확인" 표현 가능
- "검증 실패 후 수정 중"도 `ai_suggested`로 유지 가능

**단점**:
- 운영자 직접 입력도 `ai_suggested`를 거쳐야 함 — 명칭이 혼란스러울 수 있음
- HOLD-1: `!= "operator_confirmed"` (ai_suggested도 HOLD-1 대상)

**적합 조건**: CA-3 AI 제안 기능 구현이 확정된 경우

---

### 후보 C: ai_suggested + validation_failed 분리
```
not_generated ──→ ai_suggested ──→ operator_confirmed
                      ↑↓
                validation_failed
```
- CA-1A 원본 설계(`error`)와 동일 구조

**장점**:
- "검증 실패" 명시적 표현
- CA-1A와 최대 호환

**단점**:
- 상태 4개 → 관리 복잡
- `ai_suggested` ↔ `validation_failed` 순환 전이 관리 필요
- HOLD-1 조건: `not_generated OR ai_suggested OR validation_failed` (= `!= "operator_confirmed"`)
- 운영자 직접 입력도 `ai_suggested` → 명칭 혼란

---

### 후보 D: validation_passed 상태 추가
```
not_generated ──→ ai_suggested ──→ validation_passed ──→ operator_confirmed
                      ↑ (실패 시 재입력)
```
- `validation_passed`: 기술적 검증만 통과, 운영자 미확인
- `operator_confirmed`: 운영자가 `validation_passed` 상태에서 명시적 확인

**장점**:
- "자동 승인" 방지가 가장 명확
- 기술 검증과 운영자 확인을 완전 분리

**단점**:
- 상태 4개 → 가장 복잡
- validation_failed는 `ai_suggested` 복귀로 처리해야 함 → 별도 상태 필요
- 실질적으로 더 복잡해지나 benefit은 후보 C와 유사

---

### 후보 비교 요약

| 기준 | A (현재) | B (3상태) | C (4상태) | D (4상태+) |
|------|---------|---------|---------|---------|
| 상태 수 | 2 | 3 | 4 | 4~5 |
| AI 제안 구분 | ✗ | ✓ | ✓ | ✓ |
| 검증 실패 명시 | ✗ | 별도 필드 | ✓ 명시 | ✓ |
| 구현 복잡도 | 최소 | 낮음 | 중간 | 높음 |
| CA-1A 호환 | 부분 | 부분 | **최대** | 낮음 |
| HOLD-1 수정 필요 | ✗ | ✓ | ✓ | ✓ |
| 현재 테스트 영향 | **없음** | 낮음 | 중간 | 높음 |

---

## VII. 권장 상태 머신

### 권장: 후보 B 변형 (3상태 + formula_validation 분리, 단계적 적용)

```
not_generated
    ↓ (formula 입력 — AI 제안 또는 운영자 직접 입력)
pending_validation                     ← 신규 (ai_suggested 대신)
    ↓↑ (validate_formula_with_samples() 실행)
    │   → formula_validation.valid=False: pending_validation 유지 + 경고 표시
    ↓ (validate 통과 + 운영자 명시적 확인 버튼)
operator_confirmed
```

**`ai_suggested` 대신 `pending_validation`을 권장하는 이유**:
- `ai_suggested` = 출처(source) 정보 → formula의 출처가 AI인지 운영자인지와 무관한 현재 CalcMate 경로
- `pending_validation` = 상태(state) 정보 → "formula는 있으나 아직 운영자 최종 확인 전"
- 운영자가 직접 입력한 formula도 validate를 거치기 전에는 `pending_validation`
- CA-3에서 AI 제안 기능 구현 시 formula에 `formula_source: "ai_suggested"` 별도 필드 추가 가능

**단, CA-1A와의 호환 및 CA-2-5에서 이미 ai_suggested로 제안된 사항 고려 시:**  
`pending_validation` 대신 `ai_suggested`를 유지하되, 명세 주석으로 "출처와 무관한 미확정 상태"임을 명시하는 방안도 수용 가능. **사용자 최종 판단 필요**.

### formula_status vs formula_validation 분리

```python
# Contract 권장 구조 (구현은 CA-2-6-2)
{
    "formula": "avg_monthly_wage * (total_days / 365)",
    "formula_status": "pending_validation",   # 상태: 누가 확인했는가
    "formula_validation": {                   # 기술적 검증 결과 (선택적)
        "valid": True,
        "level": 3,                           # 어느 레벨까지 통과했는가
        "errors": [],
        "sample_results": [
            {"input": {...}, "output": {...}, "expected": {...}, "match": True}
        ]
    }
}
```

**분리 이유**:
1. `formula_status` = 운영자 확인 단계 (비즈니스 상태)
2. `formula_validation` = 기술적 검증 결과 (코드 실행 결과)
3. 두 개념이 독립 → "검증 통과 but 운영자 미확인" 표현 가능
4. `formula_validation`은 dashboard에서 validate 버튼 클릭 시 갱신
5. `formula_status`는 운영자의 명시적 "확정" 버튼 클릭 시만 `operator_confirmed`로 변경

**통합하지 않는 이유**:
- `validation_failed` 상태를 단일 값으로 표현하면 실패 이유와 결과를 함께 담을 수 없음
- `formula_status`는 간단한 string 값으로 HOLD rule, Registry, Contract Instance에 모두 저장되는 인덱스 역할

---

## VIII. 상태 전이 규칙 (권장)

```
전이 1: not_generated → pending_validation
  조건 : formula 값이 입력됨 (None → str/dict)
  트리거: build_contract(formula="...", formula_status=None)
  결과 : formula_status = "pending_validation"

전이 2: pending_validation → pending_validation (formula 수정)
  조건 : formula 값 변경
  트리거: build_contract(formula="다른_수식")
  결과 : formula_status = "pending_validation" 유지 (재검증 필요)
          formula_validation = None (초기화)

전이 3: pending_validation → operator_confirmed
  조건 : (1) validate_formula_with_samples() 전체 통과
          (2) 운영자 명시적 확인 ("Formula 확정" 버튼)
  트리거: dashboard의 확인 버튼 → build_contract(formula=..., formula_status="operator_confirmed")
  결과 : formula_status = "operator_confirmed"
          formula_validation = {valid: True, level: 3, ...}

전이 4: operator_confirmed → pending_validation (formula 재수정)
  조건 : formula 값 변경 (이미 확정된 후 재편집)
  트리거: build_contract(formula="수정된_수식")
  결과 : formula_status = "pending_validation" (재확인 필요)

전이 5: not_generated → operator_confirmed (직접 확정, 기존 Mode B 경로)
  조건 : formula_status="operator_confirmed" 명시적 전달
  트리거: build_contract(formula="...", formula_status="operator_confirmed")
  결과 : formula_status = "operator_confirmed"
  주의 : 하위 호환을 위해 유지. 현재 Mode B 경로 (validate 미수행)
```

### HOLD-1 수정 필요 사항
```python
# 현재 (app_factory.py:343)
if contract.get("formula_status", "not_generated") == "not_generated":
    → HOLD-1

# 변경 후 (pending_validation 추가 시)
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    → HOLD-1
# 의미: not_generated, pending_validation 모두 HOLD-1 대상
```

---

## IX. 운영자 확인과 validation 성공의 관계

### 핵심 질문: Level 3 validation 성공 = 법적 계산식 정확성 보증인가?

**답: 아니다.**

```
Level 3 validation 성공의 의미:
  "test_cases의 input값으로 formula를 실행했을 때 expected와 일치한다"

Level 3 validation이 보증하지 않는 것:
  - test_cases 자체가 법적으로 정확한지
  - formula가 법률 조항을 완전히 반영하는지
  - 경계값이 충분히 검증됐는지
  - 상한/하한 조건이 포함됐는지
```

따라서:

**정책 A (validation 성공 → 자동 operator_confirmed): 위험하고 불가**
- Level 3 성공 ≠ 법적 정확성
- test_cases를 잘못 설정하면 잘못된 formula가 `operator_confirmed`됨
- CalcMate 운영 원칙 위반: "AI가 법적 계산식을 자동 확정하지 않는다"

**정책 B (validation 성공 → 운영자 확인 → operator_confirmed): 권장**
- validation 결과를 운영자에게 표시
- 운영자가 결과를 검토하고 명시적으로 확인
- `operator_confirmed` = "운영자가 검증 결과를 보고 최종 승인"

**요약**: validation 성공은 필요조건이지 충분조건이 아님.  
`operator_confirmed`에는 반드시 **운영자의 명시적 확인 행위**가 필요.

---

## X. test_cases_status와의 관계

### 현재 독립 관계

```
formula_status    | test_cases_status | 허용 여부 | 비고
-----------------+-----------------+----------+------
not_generated    | not_generated   | 허용 (초기상태) | HOLD-1 + HOLD-2(critical)
pending_validation| not_generated  | 허용       | HOLD-1(formula 미확정) + HOLD-2(critical)
operator_confirmed| not_generated  | 허용(비critical) / HOLD-2(critical) | 현재 동작 유지
operator_confirmed| operator_confirmed | 허용   | 이상적 상태
pending_validation| operator_confirmed | 허용   | test_cases는 있으나 formula 미확정
```

### CA-1A HOLD-7 (미구현) 관련

CA-1A 설계에 `HOLD-7: formula_status == "operator_confirmed" AND test_cases_status != "operator_confirmed"` 정의됨.  
현재 미구현 — CA-2-6에서 구현 여부 검토 필요. 단, 이미 HOLD-2로 `critical category` 기준 유사 역할.

### HOLD-2와 test_cases_status 현재 연동

```python
# check_hold_rules() 현재 (app_factory.py:351)
if (contract.get("test_cases_status", "not_generated") == "not_generated"
        and contract.get("category", "") in CRITICAL_CATEGORIES):
    → HOLD-2
```

`pending_validation` 상태 추가 시 test_cases_status에는 영향 없음.

---

## XI. HOLD Rules와의 관계

### 현재 HOLD-1 조건과 신규 상태의 충돌

```
현재: formula_status == "not_generated" → HOLD-1
     formula_status == "operator_confirmed" → HOLD-1 없음

문제: pending_validation 추가 시
     formula_status == "pending_validation" → 현재 코드에서 HOLD-1 미발동
     → formula를 입력했지만 확인 안 됐어도 HOLD-1 경고 없이 진행 가능
```

**HOLD-1 수정 필수**: `== "not_generated"` → `!= "operator_confirmed"`

### validation_failed (formula_validation.valid=False) 시 Hard Block 여부

```
현재 Hard Block: _contract_save_blocked = contract_validation이 INVALID일 때 (AI 결과 불일치)
                → 이것은 AI vs Contract 불일치 (다른 개념)

formula_validation 실패 시:
  → formula_status = "pending_validation" 유지
  → HOLD-1 발동 (formula_status != "operator_confirmed")
  → Soft Gate (경고만, 진행 가능)
  → 단, 운영자가 직접 operator_confirmed로 설정하려면 validation 통과 필요
```

**결론**: `formula_validation` 실패는 기존 HOLD-1 Soft Gate로 충분.  
별도 Hard Block 불필요. 새로운 HOLD rule 추가 불필요.

---

## XII. Mode A / Mode B 영향 분석

### Mode A: 영향 없음

```
generate_app() 직접 호출
→ app["_contract"] = None
→ _build_v3_entry(contract=None)
→ contract_source = None
→ formula_status 없음
→ 신규 상태와 무관
```

### Mode B: build_contract() 파라미터 수정 필요

```python
# 현재 build_contract()
"formula_status": "operator_confirmed" if (formula is not None and formula != "") else "not_generated"

# CA-2-6-1 이후
"formula_status": formula_status or (
    "operator_confirmed" if (formula is not None and formula != "") else "not_generated"
)
# formula_status 파라미터가 명시된 경우 그대로 사용 (하위 호환 유지)
```

**기존 Mode B 테스트 영향**:
- `build_contract(formula="...")` → `formula_status="operator_confirmed"` 유지 (파라미터 None일 때 기존 규칙)
- 기존 테스트 (`test_formula_contract.py:187`) 변경 불필요

---

## XIII. Contract Instance 영향

### 현재 저장 경로별 formula_status 흐름

| 저장 위치 | formula_status 저장 방식 | 새 상태 추가 시 |
|---------|----------------------|--------------|
| Contract Instance (`instances/{slug}.yaml`) | contract dict 전체 저장 (dict() 복사) | 자동 반영됨 |
| Contract Schema Registry (`registry.yaml`) | `_update_contract_registry()` 에서 formula_status 읽어 저장 | 자동 반영됨 |
| Registry v3 contract_source | `_build_v3_entry()` 에서 formula_status 읽어 저장 | 자동 반영됨 |

**결론**: formula_status 값 자체만 바뀌므로 저장 코드 변경 불필요.

### contract_source와 중복 여부

`contract_source.formula_status` = 생성 시점 스냅샷 (불변).  
`formula_validation` 신규 필드: Contract Instance에만 저장, contract_source에는 저장 안 함.  
→ 중복 없음. 역할 명확히 분리됨.

---

## XIV. 기존 데이터 호환성

### 현재 존재하는 formula_status 값

전수 조사 결과:
- Registry v3 `contract_source`: 10개 엔트리 모두 `contract_source: null` (Mode A 저장, formula_status 없음)
- Contract Instance: `docs/contract_schema/instances/` 아무 파일 없음
- 기존 YAML에 `formula_status` 필드 없음

**결론**:
- 기존 데이터에 `formula_status` 값 없음 → 새 상태 추가해도 기존 YAML 깨지지 않음
- `contract.get("formula_status", "not_generated")` 패턴이 이미 사용 중 → None 처리 완비
- **Migration 불필요**

---

## XV. 테스트 추가 범위

### 현재 관련 테스트 파일

| 파일 | 테스트 수 | formula_status 관련 |
|------|---------|-------------------|
| `tests/test_formula_contract.py` | 26개 (CA-2-4 이후 기준) | 4개 (`operator_confirmed` 검증) |
| `tests/test_review_center.py` | 27개 | HOLD-1/2/3 간접 |

### CA-2-6-1 구현 후 추가 필요 테스트

| # | 테스트 케이스 | 파일 |
|---|------------|------|
| 1 | `formula=None` → `formula_status="not_generated"` (기존 유지) | test_formula_contract.py |
| 2 | `formula="..."` + `formula_status=None` → `"operator_confirmed"` (하위 호환) | test_formula_contract.py |
| 3 | `formula="..."` + `formula_status="pending_validation"` 명시 → `"pending_validation"` | test_formula_contract.py |
| 4 | `formula="..."` + `formula_status="operator_confirmed"` 명시 → `"operator_confirmed"` | test_formula_contract.py |
| 5 | `formula="..."` + `formula_status="ai_suggested"` 명시 → `"ai_suggested"` | test_formula_contract.py |
| 6 | `check_hold_rules(formula_status="pending_validation")` → HOLD-1 발동 | test_review_center.py |
| 7 | `check_hold_rules(formula_status="operator_confirmed")` → HOLD-1 없음 | test_review_center.py |
| 8 | Contract Instance에 `pending_validation` 저장 + 복구 확인 | test_formula_contract.py |
| 9 | Mode A: formula_status 영향 없음 | 기존 테스트 유지 |

---

## XVI. 구현 범위 분리

### CA-2-6-1 구현 대상 (상태 머신 코드화)

| # | 항목 | 파일 | 내용 |
|---|------|------|------|
| 1 | `build_contract()` 파라미터 확장 | `modules/app_factory.py` | `formula_status: str = None` 파라미터 추가. 명시 시 그대로 사용. None이면 기존 자동 도출 |
| 2 | `check_hold_rules()` HOLD-1 조건 수정 | `modules/app_factory.py` | `== "not_generated"` → `!= "operator_confirmed"` |
| 3 | `formula_validation` 필드 추가 (`build_contract()` 반환) | `modules/app_factory.py` | `formula_validation: dict = None` 파라미터 + 반환에 포함 |
| 4 | 단위 테스트 추가 | `tests/test_formula_contract.py` | 위 표 9개 케이스 |

### CA-2-6-2 구현 대상 (Dashboard 연결)

| # | 항목 | 파일 |
|---|------|------|
| 1 | formula 입력 후 `validate_formula_with_samples()` 버튼 | `dashboard.py` |
| 2 | 검증 결과 표시 (Level 1/2/3, sample_results) | `dashboard.py` |
| 3 | "Formula 확정" 버튼 → `formula_status="operator_confirmed"` 설정 | `dashboard.py` |
| 4 | `formula_status` 현재 값 표시 | `dashboard.py` |
| 5 | validation 성공 전 `operator_confirmed` 클릭 시 경고 | `dashboard.py` |

### CA-3 이연 대상

| # | 항목 | 이유 |
|---|------|------|
| 1 | AI formula 자동 제안 (`ai_suggested` 자동 설정) | AI 호출 로직 미구현 |
| 2 | formula_source 필드 (`ai_generated` vs `operator_manual`) | 출처 추적은 AI 기능 구현 후 의미 있음 |
| 3 | test_cases 자동 생성 | CA-2-5 이연 결정 유지 |
| 4 | 법적 의미 검증 (Level 4+) | 외부 법률 DB 필요 |

---

## XVII. 예상 수정 파일

| 파일 | 수정 내용 | 회귀 위험 |
|------|----------|----------|
| `modules/app_factory.py:281~322` | `build_contract()` `formula_status` 파라미터 추가 | **낮음** — 기존 None 경로 동작 유지 |
| `modules/app_factory.py:343` | HOLD-1 조건 `== "not_generated"` → `!= "operator_confirmed"` | **중간** — check_hold_rules() 테스트 확인 필요 |
| `tests/test_formula_contract.py` | 신규 상태 케이스 추가 | 낮음 |
| `tests/test_review_center.py` | HOLD-1 `pending_validation` 케이스 추가 | 낮음 |

---

## XVIII. 예상 회귀 위험

### 위험 1: HOLD-1 조건 변경
현재: `== "not_generated"` → 변경 후: `!= "operator_confirmed"`  
`pending_validation`, `ai_suggested` formula도 HOLD-1 경고 발동  
기존 테스트 중 `formula_status="operator_confirmed"` 아닌 케이스: HOLD-1 발동 여부 확인 필요

→ 현재 `test_review_center.py`의 HOLD-1 관련 테스트 재확인 요구

### 위험 2: build_contract() 파라미터 추가
`formula_status=None` (기본값) → 기존 동작 완전 유지  
기존 모든 `build_contract(...)` 호출: 명시적 `formula_status` 없음 → 기존 로직 동일  
**회귀 위험 없음**

---

## XIX. CA-2-6-1 판정 (최종 결론)

### 권장 formula_status 상태

```
not_generated       — formula 없음 (초기 상태, 기존 유지)
pending_validation  — formula 있음, 운영자 미확인 (신규)
operator_confirmed  — validate 통과 + 운영자 명시적 확인 (기존 유지)
```

(선택적 검토) `ai_suggested`: CA-3 AI 기능 구현 시 추가. 현재는 `pending_validation` 범위에 포함.

### 권장 상태 전이

```
not_generated
    ↓ formula 입력
pending_validation  ← formula 있음 + validate 미실행 or 실패
    ↓ validate_formula_with_samples() 통과
    + 운영자 명시적 "Formula 확정" 클릭
operator_confirmed
    ↓ formula 재수정
pending_validation  (재확인 필요)
```

### validation_result

**분리 권장**: `formula_status` (운영자 확인 상태) + `formula_validation` (기술적 검증 결과) 별도 필드  
**이유**: validation 성공 ≠ 법적 정확성. 운영자 확인이 반드시 필요하므로 두 개념 분리가 안전.

### HOLD Rules

HOLD-1 조건 수정 필요: `== "not_generated"` → `!= "operator_confirmed"`  
신규 HOLD rule 불필요. `formula_validation` 실패는 기존 HOLD-1 Soft Gate로 처리 충분.

### Mode A

**영향 없음** (contract 없는 경로, formula_status 없음)

### Mode B

`build_contract()` 파라미터 확장. 기존 호출 경로 하위 호환 유지.

### CA-2-6-1 구현 대상

- `build_contract()` `formula_status` / `formula_validation` 파라미터 추가
- `check_hold_rules()` HOLD-1 조건 수정 (`!= "operator_confirmed"`)
- 단위 테스트 추가 (9개 케이스)

### CA-2-6-2 구현 대상

- Dashboard formula 입력 후 즉시 `validate_formula_with_samples()` 버튼
- 검증 결과 표시 + "Formula 확정" 버튼 → `operator_confirmed` 설정

### CA-3 이연

- AI formula 자동 제안 + `ai_suggested` 자동 설정
- test_cases 자동 생성, 법적 의미 검증

### 코드 수정

**없음** (이번 단계 조사 전용)
