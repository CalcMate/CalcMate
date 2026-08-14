# CA-2-0 사전조사 보고서 — Contract Builder 구조적 Gap 분석

작성일: 2026-08-10  
조사 범위: G-1 / G-2 / G-3 / G-4 / G-5 / G-8 / G-9  
제외 범위: G-6 / G-7 / G-10 (CA-1B-4에서 명시 제외)  
코드 수정: 0 (조사 전용)

---

## 1. 조사 대상 Gap 목록

| Gap | 제목 | 현재 상태 |
|-----|------|-----------|
| G-1 | Contract Schema 저장 경로 | `docs/contract_schema/` 미존재 |
| G-2 | formula_status / test_cases_status 4-상태 | build_contract() + dashboard UI 모두 미구현 |
| G-3 | legal_refs 소비 경로 | `_build_v3_entry()` hardcode `[]` |
| G-4 | calculation_flow → formula_hint 데이터 흐름 | formula_hint 필드 미존재 |
| G-5 | _build_v3_entry() input_labels/output_labels | contract param 없음 |
| G-8 | HOLD 규칙 적용 시점 | validate_against_contract()가 POST-생성만 처리 |
| G-9 | Contract-Registry 동기화 | Registry에 Contract 출처 미기록 |

---

## 2. G-1: Contract Schema 저장 경로

### 현재 상태
```
docs/contract_schema/  ← 미존재
docs/registry/         ← 6개 YAML, load_registry_v3()가 glob("*.yaml") 전체 머지
docs/legal_master/     ← 4개 YAML, load_legal_master() 전용
```

### 핵심 위험
`load_registry_v3()` 구현 (registry_loader.py:84-89):
```python
def load_registry_v3(force: bool = False) -> dict:
    global _reg_cache
    if _reg_cache is None or force:
        _reg_cache = _read_dir(_REG_DIR)   # _REG_DIR = docs/registry/
    return _reg_cache
```
`_read_dir()` → `sorted(d.glob("*.yaml"))` → 디렉터리 내 모든 YAML 머지.

**결론**: Contract Schema 파일을 `docs/registry/` 안에 두면 slug dict에 오염. 반드시 `docs/contract_schema/` 별도 경로 사용.

### 설계 결정 (CA-1A §5 Option A 재확인)
- `docs/contract_schema/registry.yaml` — 스키마 메타 정의
- `docs/contract_schema/instances/{slug}.yaml` — slug별 Contract 인스턴스
- 별도 로더 함수 필요 (`load_contract_schema()`) 또는 직접 yaml.safe_load

---

## 3. G-2: formula_status / test_cases_status

### 현재 build_contract() 반환 필드
```python
{slug, name, category, tier, input_fields, output_fields,
 formula, scope_exclusions, test_cases, desc}
```
→ `formula_status`, `test_cases_status` 둘 다 **없음**.

### 현재 Dashboard 입력 UI (lines 2250-2303)
수집 항목: slug, name, category, tier, input_fields, output_fields, formula, test_cases, desc  
→ formula_status / test_cases_status 입력 필드 **없음**.

### 현재 Dashboard 검증 패널 (lines 2338-2415)
표시 항목: slug 일치, formula 변경, schema drift, test case 실행 결과  
→ formula_status / test_cases_status 표시 **없음**.

### 설계 결정: 자동 도출 (Option B)

formula 값 존재 여부로 상태를 자동 파생 — 별도 UI 입력 불필요.

```
formula_status:
  formula is None or ""  → "not_generated"
  formula provided       → "operator_confirmed"

test_cases_status:
  test_cases is [] or None → "not_generated"
  test_cases provided      → "operator_confirmed"
```

CA-1A에서 정의한 상태 체계 중  
AF-Contract 경로에서 실제 발생 가능한 상태는 `not_generated` / `operator_confirmed` 두 개.  
(CA-1B-3-B P2 문서 정합성: CA-1A 최종 정의는 runtime 기준 `not_generated / ai_suggested /
 pending_validation / operator_confirmed` — CA-3-4에서 AI Formula 제안 도입으로 `ai_suggested` /
 `pending_validation`이 추가됨. `auto_disabled` / `error` 는 runtime 미사용 legacy 설계안)

---

## 4. G-3: legal_refs 소비 경로

### resolve() 브릿지 (registry_loader.py:92-103)
```python
def resolve(slug: str, ...) -> dict | None:
    reg = load_registry_v3()
    r = reg.get(slug)
    ...
    for ref in r.get("legal_refs", []) or []:
        merged.update(load_legal_master().get(ref, {}))   # entity_id → legal_master 조회
    merged.update(r)
    return merged
```

**브릿지 구조**:
```
Registry entry.legal_refs: ["labor_standards_act_55"]
                                     ↓
legal_master/labor.yaml["labor_standards_act_55"] → {law, article, calculation_flow, ...}
```

### 현재 _build_v3_entry() 문제
```python
"legal_refs": [],  # line 138 — hardcode 빈 배열
```
→ AF 생성 계산기는 `resolve(slug)` 호출 시 legal_master 데이터 **전혀 못 가져옴**.

### 설계 결정
`build_contract()` 에 `legal_refs: list = None` 파라미터 추가.  
`_build_v3_entry()` 에 `contract` 파라미터 추가 → `entry["legal_refs"] = contract.get("legal_refs") or []`

필수 여부: 선택(optional). 운영자가 entity_id 알고 있을 때만 입력. 모르면 `[]` 유지.

---

## 5. G-4: calculation_flow → formula_hint 데이터 흐름

### 현재 legal_master 구조 (4개 파일, 10개 엔티티 전수 조사 결과)

| entity_id | calculation_flow 항목수 | formula_hint 존재 |
|-----------|------------------------|-------------------|
| employment_insurance_act_40 | 7개 | **없음** |
| employment_insurance_act_70 | 4개 | **없음** |
| four_major_insurances | 7개 | **없음** |
| labor_standards_act_55 | 4개 | **없음** |
| worker_retirement_benefit_act_8 | 5개 | **없음** |
| labor_standards_act_60 | 4개 | **없음** |
| income_tax_act_137 | 7개 | **없음** |
| income_tax_act_127 | 5개 | **없음** |
| (realty 2개) | — | — |

`calculation_flow` 예시 (employment_insurance_act_40):
```yaml
calculation_flow:
  - "수급요건 확인: 비자발적 이직 + 피보험단위기간 180일 이상(고용보험법 제40조)"
  - "1일 구직급여 기본액 = 이직 전 평균임금 × 60%"
  - "상한: 1일 구직급여 ≤ 이직 전 최저임금 × 80%"
  ...
```

### 설계 결정: formula_hint = 별도 필드 (operator-authored)

**자동 도출 대신 명시 필드 채택** 이유:
- `calculation_flow`는 한국어 설명문이며 Python 수식으로 변환 불가
- 항목 중 `=` 포함 줄만 추출해도 부정확 (상한/하한 조건 등 누락)
- operator가 직접 확인한 정확한 수식 표현이 AI 프롬프트 품질 보장

```yaml
# legal_master/labor.yaml 추가 예시
labor_standards_act_55:
  formula_hint: "weekly_holiday_pay = hourly_wage × (weekly_hours / 5)"  # 운영자 작성
  calculation_flow: [...]  # 기존 유지
```

`generate_app()` 프롬프트 주입 경로:
```
contract["legal_refs"] → resolve(slug) → legal_master.formula_hint
                                             ↓
                                   generate_app() u1 프롬프트에 삽입
```

**이번 CA-2 범위에서는 설계만** — 실제 구현(legal_master YAML 편집 + 프롬프트 주입)은 CA-3 이후.

---

## 6. G-5: _build_v3_entry() input_labels/output_labels 수정 포인트

### 현재 시그니처 및 호출 경로
```python
# app_factory.py:109
def _build_v3_entry(app: dict, slug: str, tier: int = 2) -> dict:
    ...
    "field_labels": app.get("labels", {}) or {},  # AI 생성 labels만
    # input_labels, output_labels: 없음
    "legal_refs": [],
    ...

# app_factory.py:774-776 (save_app 내부)
_tier = app.get("tier", 2)
_v3_entry = _build_v3_entry(app, new_slug, tier=_tier)
_write_registry_v3(new_slug, _v3_entry, app.get("category", ""))
```

### 핵심 발견: app["_contract"] 이용 가능
`generate_app_with_contract()` → 반환 app dict에 `"_contract": contract` 포함.  
`save_app()` → `app` 파라미터로 전달받음 → `app.get("_contract", {})` 접근 가능.

### 정확한 수정 포인트

**수정 1: `_build_v3_entry()` 시그니처**
```python
# 변경 전
def _build_v3_entry(app: dict, slug: str, tier: int = 2) -> dict:

# 변경 후
def _build_v3_entry(app: dict, slug: str, tier: int = 2, contract: dict = None) -> dict:
    _c = contract or {}
    ...
    entry["input_labels"]  = _c.get("input_fields",  []) or []
    entry["output_labels"] = _c.get("output_fields", []) or []
    entry["legal_refs"]    = _c.get("legal_refs",    []) or []
```

**수정 2: `save_app()` 호출부 (line 775)**
```python
# 변경 전
_v3_entry = _build_v3_entry(app, new_slug, tier=_tier)

# 변경 후
_v3_entry = _build_v3_entry(app, new_slug, tier=_tier, contract=app.get("_contract"))
```

Mode A (generate_app, contract 없음) → `app.get("_contract")` → `None` → `_c = {}` → 기존 동작 완전 유지.  
Mode B (generate_app_with_contract) → `app["_contract"]` → input/output/legal_refs 자동 입력.

---

## 7. G-8: HOLD 규칙 적용 시점

### 현재 validate_against_contract() 위치 및 역할
```
generate_app_with_contract():
  1. generate_app() 호출 → AI 생성
  2. validate_against_contract(contract, ai_app) → 사후 비교
  3. _contract_validation 삽입 후 반환

→ HOLD 검사: 완전히 없음
```

### 설계 결정: PRE-생성 소프트 차단

HOLD는 **생성 전** 단계에서 Contract 자체를 검사. POST-생성 validate와 별개.

```
dashboard.py Mode B 버튼 클릭
    ↓
[NEW] check_hold_rules(contract)
    ├─ held=True  → st.warning() + 운영자 확인 체크박스 → 미체크 시 생성 차단
    └─ held=False → generate_app_with_contract() 진행
```

**HOLD 규칙 (CA-1A §4 기반, 코드 구현 단위)**

| Rule | 조건 | 발동 |
|------|------|------|
| HOLD-1 | `formula is None` AND `tier <= 2` AND `critical=True` | formula 없음 — AI 수식 검증 불가 |
| HOLD-2 | `test_cases == []` AND `critical=True` | 테스트 케이스 없음 — 검증 불가 |
| HOLD-3 | (미래) `confidence = "medium"` | 아직 Contract에 confidence 필드 없음 — 보류 |
| HOLD-4 | `input_fields == []` OR `output_fields == []` | 필수 스펙 누락 |
| HOLD-5 | slug가 Registry에 이미 존재 | slug 충돌 |

현재 dashboard.py가 이미 HOLD-4 일부(빈 입력/출력 에러)와 HOLD-5 일부(save_app slug 중복 체크)를 **분산** 처리 중.  
→ CA-2에서 `check_hold_rules()` 함수로 **통합 중앙화**하는 것이 목표.

### 구현 위치
```python
# app_factory.py에 신규 함수 추가
def check_hold_rules(contract: dict) -> dict:
    """PRE-생성 HOLD 검사. 반환: {held, rules, messages}"""
    ...
```

---

## 8. G-9: Contract-Registry 동기화

### 현재 흐름
```
generate_app_with_contract()
    → app["_contract"]  = contract      (ephemeral, 세션에만 존재)
    → app["_contract_validation"] = ... (ephemeral)
         ↓
save_app() → _build_v3_entry(app, slug, tier)
    → Registry entry: {name, slug, category, field_labels, ...}
    → _contract 정보: 전혀 기록 안 됨
```

Registry 저장 후 원본 Contract 추적 불가.

### 설계 결정: Registry에 contract_source 스냅샷 추가

`_build_v3_entry()` 출력에 `contract_source` 서브딕셔너리 추가 (G-5 수정과 동일 코드 변경 내):

```python
entry["contract_source"] = {
    "input_fields":     _c.get("input_fields",     []),
    "output_fields":    _c.get("output_fields",    []),
    "formula_status":   _c.get("formula_status",   "not_generated"),
    "test_cases_status":_c.get("test_cases_status","not_generated"),
    "generated_at":     None,  # 추후 timestamp 추가 가능
} if _c else None
```

Mode A → `_c = {}` → `contract_source = None` → YAML에 `contract_source: null` (기존 호환).  
Mode B → Contract 정보 영구 기록 → Registry에서 "이 계산기가 Contract 기반 생성" 추적 가능.

---

## 9. CA-2 구현 서브스텝 분할 제안

### 의존성 그래프
```
G-2 (formula_status auto-derive)
    ↓ (필드가 있어야 G-9 snapshot에 기록 가능)
G-5 + G-3 + G-9 (동일 파일 2줄 수정: _build_v3_entry + save_app 호출)
    ↓
G-8 (check_hold_rules — G-2 상태 필드 사용)
    ↓
G-1 + G-4 (별도 파일 — 후순위)
```

### 서브스텝

| 스텝 | 범위 | 변경 파일 | 라인 | 리스크 |
|------|------|-----------|------|--------|
| **CA-2-1** | G-2: formula_status/test_cases_status 자동 도출 | `app_factory.py` | `build_contract()` return dict 2개 키 추가 | 최저 |
| **CA-2-2** | G-5+G-3+G-9: _build_v3_entry contract 파람 + save_app 호출 수정 | `app_factory.py` | `_build_v3_entry()` 시그니처+본문, `save_app()` 호출 1줄 | 낮음 |
| **CA-2-3** | G-8: check_hold_rules() 신규 함수 + dashboard 통합 | `app_factory.py`, `dashboard.py` | 신규 함수 + Mode B 버튼 분기 | 중간 |
| **CA-2-4** | G-1: docs/contract_schema/ 디렉터리 + 스키마 파일 초안 | YAML 파일 생성 | 코드 없음 | 최저 |
| **CA-2-5** | G-4: legal_master formula_hint 필드 설계 확정 | docs/CA2_5_FORMULA_HINT_DESIGN.md | 문서만 | 최저 |

**권장 순서**: CA-2-1 → CA-2-2 → CA-2-3 → CA-2-4 → CA-2-5  
(CA-2-4/5는 코드 변경 없으므로 언제든 선행 가능)

---

## 10. 검증 계획 (CA-2-1~CA-2-3 공통)

- 기존 485 PASS / 1 FAIL 유지 확인
- `annual-leave-remaining` Registry 엔트리 불변 확인 (READY → READY)
- Mode A (`generate_app` 직접 호출) 기존 동작 불변 확인
- `_build_v3_entry()` Mode A 경로: `contract=None` → `input_labels=[]`, `output_labels=[]`, `legal_refs=[]`, `contract_source=None`
- `_build_v3_entry()` Mode B 경로: contract 있으면 → 필드 정상 입력 확인

---

## 11. 조사 결론

| Gap | 구현 난이도 | 권장 스텝 | 비고 |
|-----|------------|-----------|------|
| G-1 | 최저 | CA-2-4 | YAML 파일 생성만 |
| G-2 | 최저 | CA-2-1 | build_contract() 2줄 추가 |
| G-3 | 낮음 | CA-2-2 | G-5와 동일 수정 포인트 |
| G-4 | 최저 (설계만) | CA-2-5 | 구현은 CA-3 이후 |
| G-5 | 낮음 | CA-2-2 | 2개 위치 수정 |
| G-8 | 중간 | CA-2-3 | 신규 함수 + dashboard 분기 |
| G-9 | 낮음 | CA-2-2 | G-5와 동일 블록 |

**전체 예상 변경 규모**: `app_factory.py` ~40줄, `dashboard.py` ~15줄, YAML 파일 2~3개 생성.  
기존 코드 삭제 없음, Mode A 완전 하위 호환.
