# CA-2-3 사전조사 보고서 — HOLD Rules 구조 조사

작성일: 2026-08-10  
조사 범위: save_app() 흐름 / 현재 HOLD 위치 / CA-1A rules 비교 / Dashboard UI / 최소 구현 제안  
코드 수정: 0 (조사 전용)

---

## 1. 현재 HOLD 흐름

### 1-1. save_app() 전체 실행 순서

```
save_app(cfg, app, site_id="", slug=None)
  ┌─ 전제: app = generate_app_with_contract() 반환값 (Mode B)
  │         또는 generate_app() 반환값 (Mode A)
  │
  ① 중복 체크 (이름, slug — DB + v3 Registry)
  │   → slug 충돌 시 return False (HOLD-5 일부)
  │
  ② DB 저장 — 2단계
  │   ② -1. tpl_repo.save() → template_id 확보
  │   ② -2. calc_repo.save() → calculators 시트
  │
  ③ Step A: registry_auto.yaml (스테이징)
  │   → _build_registry_entry(app, new_slug) → add_auto_entry()
  │
  ④ Step B: v3 Registry 기록 — 프로덕션 SSOT
  │   → _build_v3_entry(app, new_slug, tier, contract=app.get("_contract"))
  │   → entry["status"] = "HOLD"  ← HOLD 결정 위치 (hardcode)
  │   → _write_registry_v3() → *_af.yaml
  │
  ⑤ calculator_index.json 갱신
  │
  ⑥ Step C: review_checklist 생성
  │   → extract_checklist(app, tier, category)
  │   → save_af_checklist(slug, checklist) → *_af.yaml에 추가
  │
  ⑦ return True, msg
```

**Contract 검증 위치**: save_app() 내부가 아님.  
`validate_against_contract()`는 `generate_app_with_contract()` 내부에서 이미 수행, 결과가 `app["_contract_validation"]`에 embed됨.

### 1-2. HOLD 의미 — 현재 코드에서 3개 개념이 공존

**현재 시스템의 3가지 HOLD 의미 (명확히 구분)**:

| # | HOLD 개념 | 위치 | 저장 차단? | 해소 방법 |
|---|-----------|------|-----------|---------|
| **A** | Registry `status: HOLD` | `_build_v3_entry()` line 137: `"status": "HOLD"` hardcode | **아니오** (저장 허용, 공개만 차단) | `promote_to_ready()` 호출 → checklist 완료 후 READY 전환 |
| **B** | `_contract_save_blocked` | dashboard.py line 2450: `validate_against_contract().valid = False` | **예** (저장 자체 차단 — Hard block) | Contract 수정 후 재생성 |
| **C** | `review_checklist` critical 미완료 | `promote_to_ready()` 내부 checklist 검사 | **아니오** (저장 허용, READY 전환만 차단) | 대시보드에서 checklist 항목 체크 후 promote_to_ready() |

**핵심**: 현재 `status: HOLD` = "legal 검증 대기, 공개 차단"으로 CA-1A의 HOLD rules (생성/저장 단계 품질 게이트)와 **다른 개념**.  
CA-2-3에서 구현할 `check_hold_rules()`는 **생성 전** 단계의 소프트 게이트 — `status: HOLD`와 독립적으로 동작.

---

## 2. CA-1A HOLD rules vs 현재 코드 차이

### 2-1. Rule별 현황 분석

| Rule | 조건 | 데이터 위치 | Pre/Post | 현재 구현 | 추가 파라미터 | 기존 로직 충돌 |
|------|------|-----------|---------|---------|------------|------------|
| **HOLD-1** | `formula_status != "operator_confirmed"` | `contract["formula_status"]` (CA-2-1 추가) | **Pre-gen** | **미구현** | 없음 | 없음 |
| **HOLD-2** | `test_cases_status != "operator_confirmed"` AND `category ∈ CRITICAL_CATEGORIES` | `contract["test_cases_status"]` (CA-2-1), `review_center.CRITICAL_CATEGORIES` | **Pre-gen** | **미구현** | 없음 | 없음 |
| **HOLD-3** | `legal_refs` entity 중 `confidence=medium` 존재 | `load_legal_master()[entity_id]["confidence"]` | **Pre-gen** | **미구현** | `load_legal_master()` 필요 | 없음 |
| **HOLD-4** | `input_fields == []` OR `output_fields == []` | `contract["input_fields"]`, `contract["output_fields"]` | **Pre-gen** | **부분 구현** (dashboard line 2262 에러 메시지만) | 없음 | 없음 |
| **HOLD-5** | slug 충돌 | `load_registry_v3()`, DB | **Post-gen** | **부분 구현** (save_app() line 724-732) | 없음 | 없음 |

**데이터 가용성**: HOLD-1~4 판단에 필요한 모든 데이터가 `check_hold_rules(contract)` 인자에서 또는 기존 로더를 통해 이미 접근 가능.

### 2-2. CRITICAL_CATEGORIES (실제 코드값)

`modules/review_center.py:17`:
```python
CRITICAL_CATEGORIES = frozenset({
    "세금/세법", "노동/고용법", "복지/사회보험", "병역/공무",
    "세금/정부혜택", "노무/급여", "고용/보험", "노무/급여/보험",
})
```

### 2-3. confidence 실측값 (legal_master 8개 entity 전수)

| entity_id | confidence |
|-----------|-----------|
| `employment_insurance_act_40` | **medium** (실업급여) |
| `employment_insurance_act_70` | high |
| `four_major_insurances` | high |
| `labor_standards_act_55` | high |
| `worker_retirement_benefit_act_8` | high |
| `labor_standards_act_60` | high |
| `income_tax_act_137` | **medium** (연말정산) |
| `income_tax_act_127` | high |

HOLD-3 발동 케이스: 실업급여 계산기(`legal_refs=['employment_insurance_act_40']`), 연말정산 계산기(`legal_refs=['income_tax_act_137']`).  
CA-1A §5 주석: *"완전 차단 시 실업급여·연말정산 계산기를 영구 생성 불가로 만들 위험"* → **HOLD-3는 저장 허용, 경고만**.

### 2-4. HOLD-4 현재 구현과 차이

현재 dashboard.py line 2262:
```python
elif not _af_input_fields.strip() or not _af_output_fields.strip():
    st.error("Contract 모드에서는 입력 필드와 출력 필드가 필수입니다.")
```
→ 이 체크는 **UI 텍스트 입력값**을 대상으로, `check_hold_rules(contract)`의 `contract["input_fields"]`와는 다른 위치.  
`check_hold_rules()` 내에서 동일 조건을 중복 체크해도 기존 로직과 충돌 없음.

---

## 3. Pre-generation / Post-generation 구분

### 현재 Mode B 생성 흐름과 HOLD 삽입 가능 위치

```
dashboard.py:2257
[📋 Contract 기반 생성] 버튼 클릭
    │
    ├─ 기존: 이름/slug/input/output 빈값 체크 (lines 2258-2263) ← HOLD-4 일부
    │
    ⬇  ← [CA-2-3 삽입 위치: check_hold_rules(contract)]
    │
    ├─ build_contract(slug, name, ...) → contract dict
    │
    ⬇  ← [또는 contract 완성 직후]
    │
    ├─ generate_app_with_contract(cfg, contract)  ← AI 호출 (수십 초)
    │
    └─ app["_contract_validation"] embed
```

**권장 삽입 위치**: `build_contract()` 호출 직후, `generate_app_with_contract()` 호출 이전.  
이유: contract 객체가 완성된 상태에서 체크 → formula_status, test_cases_status 등 정규화된 값 사용 가능.

---

## 4. Dashboard 승인 흐름

### 4-1. 현재 Mode B 저장 차단 구조

```
_contract_save_blocked = cv is not None and not cv.get("valid", True)
→ 저장 버튼 disabled=_contract_save_blocked
```
Hard block (validate_against_contract 불일치 시).

### 4-2. CA-2-3 proposed: 소프트 차단 (Soft gate)

```python
# check_hold_rules() 결과
# held=True  → st.warning() + st.checkbox("운영자 확인 후 진행") 
#              → 미체크 시 generate_app_with_contract() 차단
# held=False + warnings → st.info() 표시만 → 생성 진행

# HOLD-3 (confidence=medium) → held=False지만 warnings에 포함 → info 표시
```

**UI 적합성 평가**:

| 기능 | 가능 여부 | 방법 |
|------|---------|------|
| 경고만 표시 | ✓ | `st.warning()` |
| 운영자 확인 체크박스 | ✓ | `st.checkbox()` + `st.session_state` |
| 확인 후 생성 진행 | ✓ | 체크박스 상태를 조건으로 generate_app_with_contract() 호출 분기 |
| Mode A 영향 | **없음** | Mode A는 별도 버튼 경로 |

**주의사항**: Streamlit rerun 방식 → 체크박스 체크 후 "📋 Contract 기반 생성" 버튼을 다시 누르는 흐름이 자연스러움. 세션 상태로 "운영자가 HOLD를 인지하고 동의했음"을 추적 가능.  

**단순화 옵션**: 체크박스 없이 경고만 표시하고 버튼 클릭만으로 진행 허용하는 방식도 가능. CA-1A §5의 "소프트 차단" 수준에 맞음.

---

## 5. 예상 수정 파일

| 파일 | 변경 내용 | 예상 줄 수 | 위험도 |
|------|---------|-----------|-------|
| `modules/app_factory.py` | `check_hold_rules(contract)` 신규 함수 추가 | +25줄 | **최저** (신규, 기존 함수 미변경) |
| `dashboard.py` | Mode B 버튼 클릭 후 `check_hold_rules()` 호출 + 결과 표시 | +15줄 | **낮음** (기존 저장/생성 경로 변경 없음) |

Registry YAML 수정: 0.  
Contract Schema 파일 생성: 0.

---

## 6. 최소 구현안

### 6-A. 반드시 필요 (CA-2-3 본체)

**`check_hold_rules(contract)` 함수** (`modules/app_factory.py` 추가):

```python
def check_hold_rules(contract: dict) -> dict:
    """Contract에 대해 CA-1A §5 hold_rules를 Pre-generation 단계에서 평가.
    
    반환: {
        "held": bool,           # True이면 생성 차단 권고 (소프트)
        "blocking_rules": list, # HOLD-1/2 등 차단 규칙 id 목록
        "warning_rules": list,  # HOLD-3 등 경고만 표시 규칙 id 목록
        "messages": list[str],  # 운영자에게 표시할 메시지
    }
    """
    from modules.review_center import CRITICAL_CATEGORIES
    from modules.registry_loader import load_legal_master

    blocking, warnings, messages = [], [], []

    # HOLD-1: formula 미확정
    if contract.get("formula_status", "not_generated") != "operator_confirmed":
        blocking.append("HOLD-1")
        messages.append(
            "HOLD-1: formula가 미확정 상태입니다. "
            "수식을 입력하거나 formula_status=operator_confirmed 상태가 필요합니다."
        )

    # HOLD-2: test_cases 없음 + critical category
    category = contract.get("category", "")
    if (contract.get("test_cases_status", "not_generated") != "operator_confirmed"
            and category in CRITICAL_CATEGORIES):
        blocking.append("HOLD-2")
        messages.append(
            f"HOLD-2: '{category}'는 Critical 카테고리입니다. "
            "테스트 케이스를 입력해야 합니다."
        )

    # HOLD-3: confidence=medium (저장 허용, 경고만)
    legal_refs = contract.get("legal_refs") or []
    if legal_refs:
        lm = load_legal_master()
        medium_entities = [
            ref for ref in legal_refs
            if (lm.get(ref) or {}).get("confidence") == "medium"
        ]
        if medium_entities:
            warnings.append("HOLD-3")
            messages.append(
                f"HOLD-3: 참조 법령 {medium_entities}의 confidence=medium — "
                "법적 불확실성이 있습니다. 운영자 확인 후 진행하세요."
            )

    return {
        "held": bool(blocking),
        "blocking_rules": blocking,
        "warning_rules": warnings,
        "messages": messages,
    }
```

**dashboard.py Mode B 변경** (버튼 클릭 → build_contract 직후):

```python
# build_contract() 호출 후 (현재 line 2293-2303 이후)
_hold_result = AF.check_hold_rules(_contract)
if _hold_result["held"]:
    for _hm in _hold_result["messages"]:
        st.warning(_hm)
    st.info("⚠️ HOLD 조건이 있습니다. 위 항목을 확인하고 다시 시도하세요.")
    # 생성 진행하지 않음 (generate_app_with_contract 호출 건너뜀)
else:
    if _hold_result["warning_rules"]:
        for _wm in _hold_result["messages"]:
            st.info(_wm)
    # 기존 generate_app_with_contract() 호출 진행
    with st.spinner("..."):
        ...
```

### 6-B. 있으면 좋은 개선

- HOLD-5 pre-generation 통합: `check_hold_rules(contract)` 내에서 `load_registry_v3().get(contract["slug"])` 체크 → 현재 post-generation인 slug 충돌 감지를 pre-generation으로 앞당김
- 기존 dashboard.py line 2262 빈 필드 체크를 `check_hold_rules()` 위임으로 통합 (중복 제거)

### 6-C. CA-2 이후로 미뤄야 하는 항목

| 항목 | 이유 |
|------|------|
| HOLD-6 (date_based+formula 모순) | CA-1A "확장 가능 조건" — 운영 경험 후 결정 |
| HOLD-7 (다중 출력+test_cases 미검증) | 위 동일 |
| `review_metadata.hold_items` 기록 | Contract Instance 영속화(CA-2-4) 이후 |
| HOLD 이력을 Registry entry에 기록 | CA-2-4 이후 |
| check_hold_rules 결과를 generate_app_with_contract()에 전달 | 현재 불필요, 로그 추적만으로 충분 |

---

## 7. 회귀 위험

| 항목 | 위험도 | 근거 |
|------|--------|------|
| `check_hold_rules()` 신규 함수 | **없음** | 신규 추가, 기존 함수 미변경 |
| dashboard.py Mode B 분기 추가 | **낮음** | 기존 저장/생성 경로는 unchanged, 분기만 추가 |
| Mode A 경로 | **없음** | Mode A 버튼 경로와 완전히 별개 |
| 기존 Registry YAML | **없음** | 미수정 |
| `load_legal_master()` 호출 | **없음** | 기존 함수, 캐시됨, I/O 없음 |
| CRITICAL_CATEGORIES import | **없음** | `review_center.py`에서 이미 import되는 상수 |

---

## 8. CA-2-3 구현 성공 기준

### 단위 검증 (`check_hold_rules()`)

```python
from modules.app_factory import build_contract, check_hold_rules
from modules.review_center import CRITICAL_CATEGORIES

# HOLD-1: formula 미확정
c1 = build_contract("s", "N", category="노무/급여")
assert c1["formula_status"] == "not_generated"
r1 = check_hold_rules(c1)
assert r1["held"] is True
assert "HOLD-1" in r1["blocking_rules"]

# HOLD-2: critical category + test_cases 없음
c2 = build_contract("s", "N", formula="x=1", category="노무/급여")
r2 = check_hold_rules(c2)
assert r2["held"] is True
assert "HOLD-2" in r2["blocking_rules"]  # formula 있지만 test_cases 없음

# HOLD-3: confidence=medium (저장 허용, held=False)
c3 = build_contract("s", "N", formula="x=1",
    test_cases=[{"input": {}, "expected": {}}],
    category="노무/급여",
    legal_refs=["employment_insurance_act_40"])  # confidence=medium
r3 = check_hold_rules(c3)
assert r3["held"] is False           # 저장 차단 아님
assert "HOLD-3" in r3["warning_rules"]

# 전부 확정
c4 = build_contract("s", "N", formula="x=a+b",
    test_cases=[{"input": {"a": 1, "b": 2}, "expected": {"x": 3}}],
    category="노무/급여",
    legal_refs=["labor_standards_act_55"])  # confidence=high
r4 = check_hold_rules(c4)
assert r4["held"] is False
assert r4["blocking_rules"] == []
assert r4["warning_rules"] == []
```

### 회귀 검증

```
1 failed (WordPress known), 485 passed
신규 failure: 0
```

### 보호 대상

- 기존 Registry YAML 미수정
- `annual-leave-remaining` READY 상태 불변
- Mode A 동작 불변
- 기존 `_contract_save_blocked` 로직 불변

---

## 종합 판단

**CA-2-3 구현 가능성**: 높음.  
- 필요한 데이터(formula_status, test_cases_status, CRITICAL_CATEGORIES, legal_master.confidence) 모두 접근 가능
- `check_hold_rules()`는 순수 함수(네트워크·DB 없음) — `load_legal_master()`만 파일 I/O (캐시됨)
- 기존 코드 변경 최소: 신규 함수 1개 + dashboard 분기 추가
- CA-1A §5 설계의 HOLD-1/2/3 구현, HOLD-4(부분)/HOLD-5(부분)는 별도 판단

**HOLD-1 vs 현재 실무 주의사항**:  
현재 운영자가 formula 없이 Contract를 생성하는 케이스가 많을 수 있음 (formula는 MANUAL 필드).  
HOLD-1이 Hard block이면 formula 없는 Contract 기반 생성이 전면 차단됨.  
→ CA-1A 원칙 유지 (Hard block) vs. 운영 유연성 중 선택은 CA-2-3 구현 승인 시 확정 필요.  
현재 조사 기준으로는 **CA-1A 원칙 유지 (HOLD-1 = Soft block, 경고+진행 여부 운영자 선택)** 를 권장함.  
이유: 현재 `_contract_save_blocked`(Hard block)가 이미 존재하므로, pre-generation에 또 하나의 Hard block을 쌓으면 formula 없는 케이스에서 생성 자체가 불가능해짐.
