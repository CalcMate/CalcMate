# CA-2-2 사전조사 보고서 — G-3 / G-5 / G-9

작성일: 2026-08-10  
조사 범위: G-3(legal_refs), G-5(Registry↔Contract 연결), G-9(contract_source 추적성)  
코드 수정: 0 (조사 전용)

---

## 1. G-3 현재 구조

### 1-1. legal_master entity_id 전수 목록

| entity_id | 파일 | law | article |
|-----------|------|-----|---------|
| `employment_insurance_act_40` | employment.yaml | 고용보험법 | 제40조 |
| `employment_insurance_act_70` | employment.yaml | 고용보험법 | 제70조 |
| `four_major_insurances` | insurance.yaml | 복합4법 | None |
| `labor_standards_act_55` | labor.yaml | 근로기준법 | 제55조 |
| `worker_retirement_benefit_act_8` | labor.yaml | 근로자퇴직급여 보장법 | 제8조 |
| `labor_standards_act_60` | labor.yaml | 근로기준법 | 제60조 |
| `income_tax_act_137` | tax.yaml | 소득세법 | 제137조 |
| `income_tax_act_127` | tax.yaml | 소득세법 | 제127조 |

**명명 규칙**: `{법령_영문명_snake_case}_{article_number}`  
**예외**: `four_major_insurances` — 4개 법령 복합을 단일 entity_id로 통합  
**entity_id ≠ slug** — 법령 식별자와 계산기 식별자는 완전히 별개 체계

**legal_master entity 키 구조 (공통 13개)**:  
`article, authority, calculation_flow, confidence, forbidden_articles, forbidden_phrases,`  
`last_verified, law, needs_human_legal, related_articles, reviewer_expectation,`  
`verification_source, writer_note`  
(일부 엔티티 추가: `deduction_rules`)

### 1-2. 현재 Registry legal_refs 현황 (10개 전체)

| Registry slug | legal_refs |
|---------------|-----------|
| weekly-holiday-allowance | `['labor_standards_act_55']` |
| severance-pay | `['worker_retirement_benefit_act_8']` |
| annual-leave-allowance | `['labor_standards_act_60']` |
| unemployment-benefit | `['employment_insurance_act_40']` |
| 육아휴직_급여_계산기 | `['employment_insurance_act_70']` |
| four-insurances | `['four_major_insurances']` |
| 연말정산_환급액_계산기 | `['income_tax_act_137']` |
| freelancer-tax-3p3 | `['income_tax_act_127']` |
| annual-leave-remaining | `[]` ← AF 생성, hardcode |
| jeonse-vs-monthly | `[]` ← AF 생성, hardcode |

**패턴**: 기존 8개 수동 큐레이션 계산기 = entity_id 1개씩 연결.  
AF 생성 2개 = `[]` hardcode.

### 1-3. resolve() 및 legal_master 조회 함수의 실제 동작

```python
# registry_loader.py:92-103
def resolve(slug, ...) -> dict | None:
    r = load_registry_v3().get(slug)
    if r is None:
        return None                          # 존재하지 않는 slug → None
    merged = {}
    for ref in r.get("legal_refs", []) or []:
        merged.update(load_legal_master().get(ref, {}))   # ← 핵심 병합
    merged.update(r)
    return merged
```

**실측 결과**:
- `resolve("weekly-holiday-allowance")` → 32개 키 (13 법령 + 19 계산기)
- `resolve("annual-leave-remaining")` → 23개 키 (법령 0 + 23 계산기, legal_refs=[])
- `resolve("nonexistent")` → `None`
- `load_legal_master().get("FAKE_ENTITY")` → `None`
- `merged.update(None or {})` → `{}` 로 처리 → **에러 없음, 무시됨**

**복수 legal_refs 동작 실측**:

| refs | 결과 |
|------|------|
| `['act_55']` | 유효, law=근로기준법 |
| `['act_55', 'act_60']` | 유효, act_60이 law/article 덮어씀 |
| `['act_55', 'NONEXISTENT']` | 유효, NONEXISTENT 무시 |
| `['NONEXISTENT_A', 'NONEXISTENT_B']` | 법령 필드 없음, 에러 없음 |
| `[]` | 법령 필드 없음, 에러 없음 |

**결론**: invalid entity_id는 `lm.get(ref)` → `None` → `{}.update()` → no-op.  
hard validation 불필요. 타입 정규화만으로 충분.

### 1-4. _build_v3_entry()의 현재 legal_refs 생성 경로

```python
# app_factory.py:138
entry = {
    ...
    "legal_refs": [],    # hardcode — Contract 정보 미전달
    ...
}
```

Contract에서 legal_refs를 전달하는 경로가 현재 없음.

### 1-5. Contract.legal_refs → Registry.legal_refs 공식 전달 규칙 (확정)

```
build_contract(legal_refs=['entity_id_1', ...])
  → contract["legal_refs"] = ['entity_id_1', ...]
  → _build_v3_entry(contract=contract)
  → entry["legal_refs"] = _c.get("legal_refs", []) or []
```

- **선택 필드** (optional): 운영자가 entity_id 알 때만 입력, 모르면 `[]` 유지
- **유효성 검사**: 없음 — resolve()가 graceful fallback 처리
- **타입 정규화**: `list(legal_refs or [])` — build_contract() 내부
- **복수 entity_id**: 허용, merge 순서 = 입력 순서

---

## 2. G-5 실제 데이터 흐름

### 2-1. Mode B 전체 흐름 (코드 경로)

```
dashboard.py:2293-2302
  contract = AF.build_contract(slug=_slug_clean, ..., desc=af_desc or "")
  st.session_state["af_contract"] = contract

dashboard.py:2308
  st.session_state["af_result"] = AF.generate_app_with_contract(cfg, contract)

app_factory.py:388-393
  result = generate_app(cfg, name, ...)
  result["_contract"] = contract           ← _contract 삽입 ✓
  result["_contract_validation"] = validation
  result["_schema_drift"] = validation["schema_drift"]
  return result

dashboard.py:2472
  app = st.session_state["af_result"]      ← _contract 포함
  AF.save_app(cfg, app, slug=slug_in)

app_factory.py:775-778
  _tier = app.get("tier", 2)
  _v3_entry = _build_v3_entry(app, new_slug, tier=_tier)  ← contract 미전달 현재
  _write_registry_v3(new_slug, _v3_entry, app.get("category", ""))
```

**핵심 확인**: `save_app()` 호출 시 `app.get("_contract")` **접근 가능** ✓  
이유: `generate_app_with_contract()`의 line 392 `result["_contract"] = contract`

### 2-2. Mode A 흐름 (변경 불필요)

```
dashboard → AF.generate_app(cfg, name, ...) → save_app(cfg, app, slug=slug_in)
app.get("_contract")  →  None  (generate_app은 _contract 미삽입)
→ _build_v3_entry(contract=None) → _c = {} → 기존 동작 완전 유지
```

### 2-3. 가장 작은 수정 위치

**위치 1**: `save_app()` line 775 — 1줄 수정

```python
# Before
_v3_entry = _build_v3_entry(app, new_slug, tier=_tier)

# After
_v3_entry = _build_v3_entry(app, new_slug, tier=_tier, contract=app.get("_contract"))
```

**위치 2**: `_build_v3_entry()` 시그니처 + 본문

```python
# Before
def _build_v3_entry(app: dict, slug: str, tier: int = 2) -> dict:

# After
def _build_v3_entry(app: dict, slug: str, tier: int = 2, contract: dict = None) -> dict:
    _c = contract or {}
    ...
```

**두 위치 합산**: ~15줄 변경, 삭제 0줄.

### 2-4. Contract slug vs Registry slug 일치 보장 여부

| | 출처 | 코드 위치 |
|---|------|---------|
| Contract.slug | `build_contract(slug=_slug_clean)` | dashboard.py:2294 |
| Registry slug | `save_app(slug=slug_in)` | dashboard.py:2472 |

**현재**: 동일 보장 없음. `slug_mismatch`를 `validate_against_contract()`가 감지하지만 저장 차단은 안함.  
**CA-2-2에서**: `contract_source.contract_slug` 기록 → 사후 비교 가능. 강제 일치 구현은 범위 밖.

### 2-5. 기존 테스트 호환성

`tests/test_af_contract_dashboard.py`와 `tests/test_app_factory_contract.py` 전수 조사 결과:
- `build_contract()` 반환 키를 exact set으로 assert하는 테스트 없음
- `_build_v3_entry()` 직접 테스트 없음 (save_app()의 통합 동작 테스트도 없음)
- `_make_app_with_drift()`의 `"legal_refs": []` → app dict에 있는 것, `build_contract()` 반환과 무관
- **Regression 위험: 없음**

---

## 3. G-9 후보 A/B/C/D 비교

### 3-1. 각 후보 실제 YAML 형태

**후보 A — 포인터**
```yaml
contract_source:
  slug: sample-calc
  path: docs/contract_schema/instances/sample-calc.yaml
```
크기: 93 bytes

**후보 B — 최소 스냅샷**
```yaml
contract_source:
  contract_slug: sample-calc
  input_fields: [base_pay, extra_pay]
  output_fields: [total_pay]
  formula_status: operator_confirmed
  test_cases_status: operator_confirmed
```
크기: 188 bytes

**후보 C — 해시**
```yaml
contract_source:
  hash: d847350e87c18254
```
크기: 42 bytes

**후보 D — 포인터 + 해시**
```yaml
contract_source:
  slug: sample-calc
  path: docs/contract_schema/instances/sample-calc.yaml
  hash: d847350e87c18254
```
크기: 118 bytes

### 3-2. 후보 비교 표

| 기준 | A (포인터) | B (스냅샷) | C (해시) | D (포인터+해시) |
|------|-----------|-----------|---------|--------------|
| YAML 크기 | 93 bytes | 188 bytes | 42 bytes | 118 bytes |
| 자기 완결성 | ✗ | **✓** | ✗ | ✗ |
| Instance 파일 삭제 내성 | ✗ (dead ref) | **✓** | ✗ (hash만 남음) | 부분 |
| CA-2-4 의존성 | **필요** | 불필요 | 불필요 | **필요** |
| 재생성 감지 | ✗ | 필드 비교 가능 | **hash 비교** | **hash 비교** |
| 배포 순서 유연성 | 낮음 | **높음** | **높음** | 낮음 |
| 단독 추적 가능 | ✗ | **✓** | ✗ | ✗ |

### 3-3. 세부 검토 항목

**Contract Instance 파일 수정/삭제 시 Registry 추적성**
- A: path 참조 파일이 없어지면 Registry가 유효성 잃음
- B: Registry 자체에 스냅샷 보유 → 파일 분실 무관
- C: hash만으로 복원 불가
- D: hash로 검증 가능, 복원은 불가

**Contract Instance의 버전 관리**
- Contract Instance(CA-2-4 대상) = YAML 파일 → Git으로 버전 관리 예정
- 하지만 CA-2-2 시점에서 CA-2-4는 미구현 → Instance 파일 없음
- A/D: CA-2-4 완료 전 생성된 Registry entry는 dead reference가 됨

**slug만으로 충분한지**
- slug는 Registry 내에서 이미 primary key → 중복 저장
- **단, Contract.slug ≠ Registry slug 가능** (현재 구조 기준)
- `contract_slug` 필드로 구분 명시 필요

**path를 저장할지 vs 규칙 기반 계산**
- 규칙: `f"docs/contract_schema/instances/{slug}.yaml"` → 항상 계산 가능
- 저장 시 유연성 없음 (경로 바뀌면 전체 갱신 필요)
- 규칙 기반이 더 안전

**hash 가치**
- 검증 로직 없으면 단순 메타데이터
- CA-2-2에서 hash 검증 구현 없음 → 추가하지 않음 (추후 확장 가능)

---

## 4. 권장 contract_source schema

**채택: 후보 B (최소 스냅샷)**

```yaml
# Mode B — Contract 기반 생성 시
contract_source:
  contract_slug: sample-calc        # build_contract()의 slug 파라미터 값
  input_fields: [base_pay, extra_pay]
  output_fields: [total_pay]
  formula_status: operator_confirmed
  test_cases_status: operator_confirmed

# Mode A — 직접 생성 시 (contract 없음)
contract_source: null
```

**채택 이유**:
1. CA-2-4(G-1) 의존 없음 → CA-2-2 단독 배포 가능
2. Contract Instance 파일 분실·미구현에도 Registry가 진실 보유
3. Git diff로 "어떤 스펙으로 생성됐는지" 즉시 파악 가능
4. `formula_status`/`test_cases_status` 포함 → CA-2-1 결과와 연동

**제외 결정**:
- `path`: 규칙 기반 계산 가능 + CA-2-4 미구현 → dead reference 위험
- `hash`: 검증 로직 없음 → 추후 확장
- `schema_id`: CA-1A 설계 있지만 미구현 → 추후 추가

---

## 5. legal_refs 최종 schema

```yaml
# Registry entry에서의 legal_refs (기존 형식 완전 호환)
legal_refs:
  - labor_standards_act_55          # legal_master entity_id 문자열 리스트
  # - 복수 지원 (merge 순서 = 리스트 순서)
  # - invalid entity_id → resolve()가 graceful fallback, 에러 없음

# build_contract() 파라미터 추가안
legal_refs: list = None
# 반환: "legal_refs": list(legal_refs or [])
```

**기존 Registry legal_refs 형식과 100% 호환** — 동일 문자열 리스트 형식.

---

## 6. Mode A / Mode B 각각의 동작

### Mode A (generate_app 직접)
```
generate_app() → save_app()
  app.get("_contract") = None
  ↓
_build_v3_entry(contract=None)
  _c = {}
  entry["input_labels"]    = []
  entry["output_labels"]   = []
  entry["legal_refs"]      = []
  entry["contract_source"] = None

Registry YAML:
  input_labels: []
  output_labels: []
  legal_refs: []
  contract_source: null
```

**기존 동작 완전 유지.** 기존 계산기(annual-leave-remaining 등) 재저장 없음.

### Mode B (generate_app_with_contract)
```
build_contract(slug='s', ..., legal_refs=['labor_standards_act_55'])
  → contract["legal_refs"] = ['labor_standards_act_55']
  → contract["formula_status"] = "operator_confirmed"  (CA-2-1)
  → contract["test_cases_status"] = "operator_confirmed"  (CA-2-1)

generate_app_with_contract() → result["_contract"] = contract

save_app(app) → _build_v3_entry(contract=app.get("_contract"))
  _c = contract
  entry["input_labels"]   = ['base_pay', 'extra_pay']
  entry["output_labels"]  = ['total_pay']
  entry["legal_refs"]     = ['labor_standards_act_55']
  entry["contract_source"] = {
      "contract_slug":    's',
      "input_fields":     ['base_pay', 'extra_pay'],
      "output_fields":    ['total_pay'],
      "formula_status":   'operator_confirmed',
      "test_cases_status":'operator_confirmed',
  }
```

---

## 7. 최소 수정 파일 목록

| 파일 | 변경 위치 | 변경 내용 | 줄 수 |
|------|----------|---------|------|
| `modules/app_factory.py` | `build_contract()` 시그니처 | `legal_refs: list = None` 파라미터 추가 | +2 |
| `modules/app_factory.py` | `build_contract()` return | `"legal_refs": list(legal_refs or [])` 추가 | +1 |
| `modules/app_factory.py` | `_build_v3_entry()` 시그니처 | `contract: dict = None` 파라미터 추가 | +1 |
| `modules/app_factory.py` | `_build_v3_entry()` 본문 | `_c`, `input_labels`, `output_labels`, `legal_refs`, `contract_source` 추가 | +10 |
| `modules/app_factory.py` | `save_app()` line 777 | `contract=app.get("_contract")` 전달 | +1 수정 |
| **합계** | | | **+14, 수정 1** |

Registry YAML 수정: 0 (신규 생성 계산기에만 자동 추가됨).

---

## 8. 기존 Registry 호환성

**기존 9개 수동 큐레이션 계산기** (`docs/registry/labor.yaml` 등):
- `_build_v3_entry()` 경로를 통해 생성되지 않음
- CA-2-2 변경 후에도 재저장 없음 → **무영향**

**annual-leave-remaining** (기존 AF 생성, READY):
- 이미 Registry에 저장됨, `save_app()` 재호출 없음 → **무영향**
- `input_labels`/`output_labels`는 CA-1B-1에서 이미 수동 추가됨

**신규 생성 계산기** (CA-2-2 이후):
- Mode B → `input_labels`, `output_labels`, `legal_refs`, `contract_source` 자동 추가
- Mode A → 기존과 동일

---

## 9. 예상 Regression 위험

| 항목 | 위험도 | 근거 |
|------|--------|------|
| `build_contract()` 신규 파라미터 `legal_refs=None` | **없음** | 기본값 None, 기존 호출부 변경 없음 |
| `_build_v3_entry()` 신규 파라미터 `contract=None` | **없음** | 기본값 None, 기존 save_app() 호출부 1줄만 수정 |
| 기존 테스트 assertion | **없음** | build_contract() 키 exact match 테스트 없음, _build_v3_entry() 직접 테스트 없음 |
| Mode A 경로 | **없음** | `contract=None → _c={}` → 기존 동작 |
| Registry YAML 직접 수정 | **없음** | 기존 YAML 미수정 |

---

## 10. CA-2-2 구현 단계 성공 기준

### build_contract() 검증

```python
c = build_contract("s", "N", legal_refs=["labor_standards_act_55"])
assert c["legal_refs"] == ["labor_standards_act_55"]

c2 = build_contract("s", "N")
assert c2["legal_refs"] == []

c3 = build_contract("s", "N", legal_refs=None)
assert c3["legal_refs"] == []
```

### _build_v3_entry() Mode B 검증 (단위)

```python
from modules.app_factory import build_contract, _build_v3_entry

contract = build_contract(
    slug="test-calc", name="테스트", 
    input_fields=["a"], output_fields=["b"],
    formula="b = a * 2",
    legal_refs=["labor_standards_act_55"],
    test_cases=[{"input": {"a": 1}, "expected": {"b": 2}}],
)
app = {"name": "테스트", "category": "노무/급여", "tier": 2,
       "description": "테스트 설명", "labels": {}, "formula": "b = a * 2",
       "input_schema": {"a": "number"}, "output_schema": {"b": "number"},
       "_contract": contract}
entry = _build_v3_entry(app, "test-calc", tier=2, contract=app.get("_contract"))

assert entry["input_labels"] == ["a"]
assert entry["output_labels"] == ["b"]
assert entry["legal_refs"] == ["labor_standards_act_55"]
assert entry["contract_source"] is not None
assert entry["contract_source"]["formula_status"] == "operator_confirmed"
assert entry["contract_source"]["test_cases_status"] == "operator_confirmed"
assert entry["contract_source"]["contract_slug"] == "test-calc"
```

### _build_v3_entry() Mode A 검증 (하위 호환)

```python
app_a = {"name": "테스트", "category": "노무/급여", "tier": 2, ...}
entry_a = _build_v3_entry(app_a, "test-calc", tier=2)  # contract 파라미터 없음

assert entry_a["input_labels"] == []
assert entry_a["output_labels"] == []
assert entry_a["legal_refs"] == []
assert entry_a["contract_source"] is None
```

### Regression
```
1 failed (WordPress known), 485 passed
```

### 보호 대상 불변 확인
- `annual-leave-remaining` → status: READY 유지
- 기존 9개 curated YAML 미변경 (git diff로 확인)
