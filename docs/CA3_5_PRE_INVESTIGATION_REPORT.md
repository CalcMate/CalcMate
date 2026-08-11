# CA-3-5 사전조사 보고서 — AI Formula E2E 최종검증 설계

> 조사 기준일: 2026-08-11  
> 원칙: 코드 수정 0건 / 조사 전용  
> 기준: CA-3-4 PASS (537 PASS / 1 known FAIL)

---

## 1. CA-3 전체 E2E 구조

### 1-1. 완전한 E2E 흐름 (코드 기준)

```
[Dashboard: Mode B expander — line 2225]
        │
        ▼
[입력 확보]
  af_name / af_cat / af_desc  (expander 이전, line 2156~2158)
  _af_slug_pre / _af_input_fields / _af_output_fields / _af_formula
        │
        ▼ (CA-3-4)
[🤖 AI Formula 제안] → AF.suggest_formula() → result
  성공: af_contract_formula = formula_str
        af_formula_ai_suggested_text = formula_str
        af_formula_confirmed_text → pop
        af_formula_validation → pop
        af_contract.formula_status = "ai_suggested" (if exists)
  실패: 기존 상태 유지, st.error()
        │
        ▼
[🔍 Formula 검증 — line 2300]
  _vfws(formula, schema, test_cases) → af_formula_validation
  af_contract.formula_status = "pending_validation"
        │
        ▼
[✅ Formula 확정 — line 2335, disabled=not _fv_passed]
  af_formula_confirmed_text = current formula raw
  af_contract.formula_status = "operator_confirmed"
        │
        ▼
[📋 Contract 기반 생성 — line 2368]
  _fv_prior_status = "operator_confirmed" if formula_raw==confirmed_raw else None
  _contract = AF.build_contract(formula_status=_fv_prior_status)
  af_contract = _contract
  check_hold_rules(_contract) → HOLD warnings
  AF.generate_app_with_contract(cfg, _contract) → af_result
    └─ generate_app(cfg, name, ..., _contract=_contract)
       [AI 4회 호출: 스펙→코드→SEO→이미지]
    └─ validate_against_contract(contract, result)
        │
        ▼
[💾 저장 — dashboard.py save_app() 호출]
  DB: calculators + app_templates
  registry_auto.yaml (스테이징)
  v3 Registry _af.yaml (HOLD)
  Contract Instance: docs/contract_schema/instances/{slug}.yaml
  review checklist
        │
        ▼
[삭제: delete_app()]
  DB: calculators + app_templates 삭제
  registry_auto.yaml 항목 제거
  _af.yaml 항목 제거
  Contract Instance 파일 삭제
  contract_schema/registry.yaml 항목 제거
```

---

## 2. 정상 Lifecycle

### 2-1. formula_status 전체 추적

| 단계 | formula_status 소재 | 값 |
|------|-------------------|-----|
| Mode B 진입 | `af_contract` 없음, 배지 = `not_generated` | N/A |
| AI 제안 성공 | `af_contract.formula_status` (if exists) | `ai_suggested` |
| | `af_formula_ai_suggested_text` | formula str |
| | 배지 fallback (af_contract 없을 때) | `ai_suggested` |
| [🔍 Formula 검증] | `af_contract.formula_status` | `pending_validation` |
| [✅ Formula 확정] | `af_contract.formula_status` | `operator_confirmed` |
| | `af_formula_confirmed_text` | formula raw text |
| [📋 Contract 기반 생성] | `build_contract(formula_status=_fv_prior_status)` | `operator_confirmed` 또는 auto-derived |
| `generate_app_with_contract()` 결과 | `app["_contract"]["formula_status"]` | 위와 동일 |
| Contract Instance YAML | `formula_status` 필드 | 위와 동일 |
| v3 Registry | `contract_source.formula_status` | 위와 동일 |

### 2-2. build_contract() 호출 시 formula_status 파생 로직 (핵심)

```python
# dashboard.py line 2404-2410
_fv_prior_raw = st.session_state.get("af_formula_confirmed_text", "")
_fv_prior_status = (
    "operator_confirmed"
    if _fv_prior_raw and _formula_raw == _fv_prior_raw
    else None
)
_contract = AF.build_contract(formula_status=_fv_prior_status, ...)
```

**결과 매핑**:

| 상황 | `_fv_prior_status` | `build_contract()` 결과 |
|------|-------------------|------------------------|
| Formula 없음 | None | `not_generated` |
| Formula 있음, 미확정 | None | `pending_validation` (auto-derived) |
| AI 제안만, 미확정 | None | `pending_validation` (auto-derived) |
| 운영자 확정 후 미변경 | `"operator_confirmed"` | `operator_confirmed` |
| 운영자 확정 후 수정 | None | `pending_validation` (auto-derived) |

**중요**: `ai_suggested` 상태는 Dashboard UI 추적용이다. build_contract() 호출 시 `ai_suggested`가 명시적으로 전달되지 않으므로 Contract Instance에는 `ai_suggested`가 저장되지 않는다. 이것은 **설계된 동작**이다 — 운영자가 확정([✅ Formula 확정])하지 않은 formula는 Contract로 생성 시 `pending_validation`으로 처리되어 HOLD-1이 발동한다.

---

## 3. 실패 Lifecycle

### 3-1. AI 제안 실패 시 흐름

```
suggest_formula() → {"success": False, "status": "not_generated"}
        │
        ▼
Dashboard (CA-3-4 구현)
  st.error(result["reason"])
  st.warning(w) for warnings
  session state 변경 없음
  st.rerun() 없음
        │
        ▼
기존 상태 완전 보존:
  af_contract_formula → 이전값 유지
  af_formula_ai_suggested_text → 이전값 유지
  af_contract.formula_status → 이전값 유지
```

### 3-2. Type D 차단 후 흐름

```
suggest_formula(slug="연말정산_환급액_계산기") 또는 calc_flows에 키워드
        │
        ▼
즉시 {"success": False, "reason": "...", "status": "not_generated"}
AI 호출 없음
        │
        ▼
Dashboard: st.error() + 기존 상태 보존
```

---

## 4. Formula Status Lifecycle

```
not_generated
    │ [AI Formula 제안 성공]
    ▼
ai_suggested          ← Dashboard 추적 전용 (session_state)
    │ [Formula 수정 감지]  → pending_validation  (CA-3-1 로직)
    │ [검증 클릭]          → pending_validation  (라인 2332)
    │ [미변경 + 검증]      → pending_validation  (동일)
    ▼
pending_validation
    │ [Formula 확정 — 검증 PASS 후]
    ▼
operator_confirmed
    │ [Formula 텍스트 수정]  → pending_validation  (CA-2-6-2 로직)
    │ [AI 재제안 + 다른 값]  → pending_validation  (CA-2-6-2 자동 발동)
    ▼
pending_validation
```

**Contract Instance에서의 formula_status**:

| 상황 | 저장되는 formula_status |
|------|------------------------|
| operator_confirmed 확정 후 생성 | `operator_confirmed` |
| AI 제안 후 바로 생성 (확정 생략) | `pending_validation` |
| Formula 없이 생성 | `not_generated` |
| `ai_suggested` | **저장 안 됨** (설계된 동작) |

---

## 5. AI 제안/검증/확정 연결

### 5-1. 연결 코드 경로

```
suggest_formula() [app_factory.py line 477]
    └─ _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)  # 1회
    └─ validate_formula(parsed_formula, schema)  # R-1
    └─ R-2 dict key check
    └─ returns {"success": True, "formula": ..., "status": "ai_suggested"}

Dashboard [dashboard.py line 2249+]
    └─ AF.suggest_formula(cfg, name, category, desc, input_fields, output_fields, legal_refs=[], slug)
    └─ 성공: st.session_state["af_contract_formula"] = formula_str
    └─ 성공: st.session_state["af_formula_ai_suggested_text"] = formula_str
    └─ 성공: st.session_state["af_contract"]["formula_status"] = "ai_suggested"

validate_formula_with_samples() [formula_engine.py]
    └─ Dashboard [🔍 검증] 버튼에서 직접 호출
    └─ suggest_formula() 내부에서도 validate_formula() 재사용 (R-1 검증)

build_contract() [app_factory.py line 286]
    └─ 생성 시점에 다시 formula_status 파생
```

### 5-2. Validation vs operator_confirmed 독립성

"Validation PASS ≠ operator_confirmed 자동 전환"

```python
# 검증 버튼 결과 (line 2331-2332)
st.session_state["af_formula_validation"] = _fv_result
if st.session_state.get("af_contract"):
    st.session_state["af_contract"]["formula_status"] = "pending_validation"

# 확정 버튼 (line 2335-2345)
if _fv_col2.button(
    "✅ Formula 확정",
    disabled=not _fv_passed,    # ← 검증 미통과 시 비활성
    ...
):
    st.session_state["af_formula_confirmed_text"] = (_af_formula or "").strip()
    if st.session_state.get("af_contract"):
        st.session_state["af_contract"]["formula_status"] = "operator_confirmed"
```

**우회 경로 없음 확인**:
- 검증 통과 → `_fv_passed = True` → [확정] 버튼 활성화 → 클릭 필요
- 검증 없이 [Contract 기반 생성] 클릭 → `_fv_prior_status = None` → `build_contract()` → HOLD-1 발동

---

## 6. R-6 덮어쓰기 방어

### 6-1. Scenario A: Formula 없음 → AI 제안

```
_existing_formula = "".strip() → falsy
→ _override_set = pop("_af_ai_suggest_override", False) → False
→ if 조건: _existing_formula(False) and not override → False
→ 즉시 AI 호출
```

### 6-2. Scenario B: Formula 있음 → 1차 클릭

```
_existing_formula = "a + b" → truthy
→ _override_set = pop("_af_ai_suggest_override", False) → False
→ if 조건: True and True → 경고 표시
→ st.session_state["_af_ai_suggest_override"] = True
→ rerun 없음 (버튼이 자동 rerun, 경고는 현재 렌더 사이클에서만 표시)
```

**Streamlit 동작 주의**: `st.button()` 클릭은 자동 rerun. 경고(`st.warning()`)는 current render에서 표시되고 다음 render에서 사라짐. `_af_ai_suggest_override=True`는 세션에 남음.

### 6-3. Scenario C: Formula 있음 → 2차 클릭

```
→ _override_set = pop("_af_ai_suggest_override", False) → True (제거됨)
→ if 조건: True and (not True = False) → False
→ AI 호출 진행
```

### 6-4. Scenario D: operator_confirmed 상태에서 AI 재제안

```
[AI 재제안 성공]
→ af_formula_confirmed_text → pop (삭제)
→ af_contract_formula = new_formula
→ 다음 렌더: _fv_confirmed_raw = "" (삭제됨)
→ _fv_current_raw != _fv_confirmed_raw? → False (confirmed_raw가 빈 문자열)
→ CA-2-6-2 발동 안 됨

[그러나 af_formula_ai_suggested_text = new_formula 설정]
→ 만약 기존 confirmed formula와 새 AI formula가 다르다면
   다음 렌더에서: _fv_current_raw == new_formula != 기존 confirmed_raw
   → 이미 af_formula_confirmed_text가 pop됐으므로 CA-2-6-2 발동 안 됨

결론: AI 재제안 성공 시 기존 af_formula_confirmed_text가 삭제되므로
      다음 [Contract 기반 생성] 클릭 시 _fv_prior_status = None → pending_validation
      → HOLD-1 발동 ✅
```

---

## 7. String/Dict Formula

### 7-1. 전체 경로에서의 formula 타입 추적

| 단계 | Type A | Type B |
|------|--------|--------|
| `suggest_formula()` 반환 | `str` | `dict` |
| Dashboard 직렬화 | `str(formula)` | `json.dumps(formula, ensure_ascii=False)` |
| `af_contract_formula` (widget) | `"a * b"` | `'{"k": "expr"}'` |
| `af_formula_ai_suggested_text` | `"a * b"` | `'{"k": "expr"}'` |
| `build_contract()` 블록 파싱 | try `json.loads()` fail → str | try `json.loads()` → dict |
| `build_contract()` contract.formula | `str` | `dict` |
| `generate_app_with_contract()` | str formula | dict formula |
| `_build_contract_enforcement_prompt()` | str 그대로 | `json.dumps(formula)` |
| `save_app()` DB 저장 | str | `json.dumps(formula)` |
| Contract Instance YAML | str | dict (yaml.dump가 그대로 직렬화) |
| v3 Registry `contract_source` | formula_status만 저장 | formula_status만 저장 |

**YAML 직렬화 주의**: `yaml.dump({"formula": {"k": "expr"}})` → YAML의 nested dict로 저장. 로드 시 `yaml.safe_load()` → dict 복원. 타입 손실 없음 ✅

**compact JSON vs indent JSON**: Dashboard에서 `json.dumps(ensure_ascii=False)` (indent 없음) 사용 → `af_formula_ai_suggested_text`와 `af_contract_formula` 비교 시 동일값 ✅

---

## 8. HOLD Lifecycle

### 8-1. check_hold_rules() 트리거 조건

```python
# HOLD-1: formula_status != "operator_confirmed"
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    rules.append("HOLD-1")

# HOLD-2: critical category + test_cases 미확정
if (contract.get("test_cases_status") == "not_generated"
        and contract.get("category") in CRITICAL_CATEGORIES):
    rules.append("HOLD-2")

# HOLD-3: legal_refs 중 confidence=medium 존재
```

### 8-2. formula_status별 HOLD-1 발동

| formula_status | HOLD-1 | 근거 |
|----------------|--------|------|
| `not_generated` | ✅ 발동 | != operator_confirmed |
| `ai_suggested` | ✅ 발동 | != operator_confirmed (CA-3-1 확인) |
| `pending_validation` | ✅ 발동 | != operator_confirmed |
| `operator_confirmed` | ❌ 미발동 | 조건 불충족 |

### 8-3. Hard Block vs Soft Gate 혼동 없음

| 구분 | 함수 | 동작 |
|------|------|------|
| Soft Gate | `check_hold_rules()` | 경고 표시, 진행 운영자 결정 |
| Hard Block | `validate_against_contract()` | _contract_validation["valid"]=False, 저장 차단 UI |

`validate_against_contract()`는 formula_status를 검사하지 않는다 — slug/schema/formula_value만 비교. 두 함수는 역할이 완전히 다름.

---

## 9. Contract Instance

### 9-1. 저장 경로 (`_save_contract_instance`)

```
save_app() [line 1152-1156]
  └─ if not _v3_warn and app.get("_contract"):
        _save_contract_instance(new_slug, app["_contract"])
```

**조건**: v3 Registry 기록 성공 + `_contract` 키 존재. Mode A(generate_app 직접)는 `_contract=None` → 저장 안 됨.

### 9-2. 저장 내용 (`_SCHEMA_DIR / "instances" / f"{slug}.yaml"`)

```yaml
slug: test-calc
name: 테스트 계산기
category: 노무/급여
tier: Tier2-A
input_fields: [base_pay]
output_fields: [net_pay]
formula: "net_pay = base_pay * 0.9"   # str 또는 dict 그대로
formula_status: operator_confirmed     # build_contract() 시점 값
test_cases: [...]
test_cases_status: operator_confirmed
desc: "..."
legal_refs: [...]
scope_exclusions: []
generated_at: "2026-08-11T..."
```

### 9-3. 로드 후 라운드트립

```python
loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
```

- str formula → str 복원 ✅
- dict formula → dict 복원 ✅ (YAML nested dict)
- formula_status → str 복원 ✅
- test_cases → list 복원 ✅

### 9-4. 삭제 경로

```
delete_app() [line 1178]
  └─ DB: calculators + app_templates 삭제
  └─ registry_auto.yaml 항목 제거
  └─ _af.yaml 항목 제거
  └─ _delete_contract_instance(slug)
       └─ instances/{slug}.yaml 삭제
       └─ contract_schema/registry.yaml 항목 제거
```

---

## 10. Registry

### 10-1. v3 Registry entry 구조 (Mode B)

```yaml
test-calc:
  name: 테스트 계산기
  slug: test-calc
  category: 노무/급여
  input_labels: [base_pay]         # ← contract.input_fields
  output_labels: [net_pay]         # ← contract.output_fields
  legal_refs: [labor_standards_act_55]  # ← contract.legal_refs
  status: HOLD
  source: app_factory
  contract_source:
    contract_slug: test-calc
    input_fields: [base_pay]
    output_fields: [net_pay]
    formula_status: operator_confirmed
    test_cases_status: operator_confirmed
```

**formula 자체는 Registry에 저장되지 않음** — Contract Instance YAML에만 저장.

### 10-2. 기존 Registry 보호

- `_write_registry_v3()`: slug 중복 시 ValueError → 기존 계산기 slug 보호
- 기존 `docs/registry/*.yaml` (비 `_af.yaml`) → 수정 없음
- `delete_app()`: `source != "app_factory"` 이면 삭제 거부

---

## 11. Mode A 완전 분리

### 11-1. 코드 경로 분리

| | Mode A | Mode B |
|-|--------|--------|
| 진입점 | `[🚀 생성]` 버튼 | `[📋 Contract 기반 생성]` 버튼 |
| AI 제안 버튼 | ❌ expander 외부 없음 | ✅ expander 내부 |
| `_contract` 전달 | `generate_app(cfg, name)` | `generate_app_with_contract(cfg, contract)` |
| Contract Instance | 저장 안 됨 | 저장됨 |
| formula_status | N/A | 추적됨 |
| HOLD-1 | 발동 안 됨 (formula 없음) | 발동 가능 |
| `suggest_formula()` | 호출 없음 | 버튼 클릭 시 호출 |

### 11-2. `generate_app()` 내 Mode A/B 분기

```python
def generate_app(cfg, name, ..., _contract=None):
    ...
    _contract_lock_section = (
        _build_contract_enforcement_prompt(_contract) + "\n\n"
    ) if _contract else ""   # ← _contract=None이면 빈 문자열
```

Mode A: `_contract=None` → Contract Lock 섹션 없음 → 기존 동작 그대로.

---

## 12. Session State Discard

### 12-1. AF_SESSION_DISCARD_KEYS 완전성 (CA-3-4 갱신 후)

현재 `AF_SESSION_DISCARD_KEYS` (15개):

```python
# 기본 키 (11개)
"af_result", "af_name", "af_cat", "af_desc", "af_tier",
"af_slug", "af_keyword", "af_tier_suggest", "_af_last_slug_for",
"af_seo", "af_discard_confirm",

# Contract 모드 키 (6개 → CA-3-4 기존 6 + 신규 4 → 총 10개)
"af_contract", "af_contract_slug_pre",
"af_contract_input_fields", "af_contract_output_fields",
"af_contract_formula", "af_contract_test_cases",

# CA-3-1/CA-3-4 추가 (4개)
"af_formula_confirmed_text", "af_formula_validation",
"af_formula_ai_suggested_text", "_af_ai_suggest_override",
```

합계: 21개

### 12-2. 기존 discard 테스트 호환성

`test_af_discard.py::TestAfDiscardKeysList::test_no_non_af_keys`:
```python
non_af = [k for k in AF_SESSION_DISCARD_KEYS
          if not k.startswith("af_") and not k.startswith("_af_")]
```

CA-3-4 추가 키 검증:
- `af_formula_confirmed_text` → `af_` 시작 ✅
- `af_formula_validation` → `af_` 시작 ✅
- `af_formula_ai_suggested_text` → `af_` 시작 ✅
- `_af_ai_suggest_override` → `_af_` 시작 ✅

**기존 discard 테스트 전원 통과** ✅

### 12-3. _full_session() 업데이트 필요 여부

`test_af_discard.py::_full_session()` — 현재 CA-3-1/CA-3-4 키 미포함. 그러나:
- `TestAfDiscardKeysList::REQUIRED_KEYS`는 기본 키 10개만 검증 → 이미 통과
- `TestAfDiscardConfirm::test_all_discard_keys_gone()`: `session`에 없는 키를 pop → `pop(k, None)` → 에러 없음

**CA-3-F에서 보완 권장**: `_full_session()`에 CA-3-4 키 추가 + discard 후 소거 확인 테스트.

---

## 13. Blog/WordPress Pipeline 분리

### 13-1. 코드 경로 완전 분리

| | App Factory (AI Formula) | Blog Pipeline |
|-|--------------------------|---------------|
| 위치 | `elif tab == "🏭 App Factory"` | 파이프라인 탭 |
| 핵심 함수 | `suggest_formula()`, `build_contract()`, `generate_app_with_contract()` | `PIPE.run_once(cfg)` |
| 데이터 소스 | Dashboard session_state | Registry v3 + DB |
| AI 호출 | `_chat(cfg, "orchestrator", ..., 300)` | Writer/Researcher role |

### 13-2. suggest_formula() 실패 전파 경로 없음

```
suggest_formula()
    └─ _fail() → dict 반환 (예외 전파 없음)
    └─ Dashboard: st.error() 표시
    └─ PIPE.run_once() → 완전히 다른 코드 경로
```

AI Formula 제안 실패가 블로그 생성에 영향을 줄 수 있는 코드 경로 **없음** ✅

### 13-3. 블로그 실패 알림 조사

`_run_blog` = `lambda: PIPE.run_once(cfg)` (dashboard.py line 398-399). `check_pipeline_health()` 등과 무관. Contract Builder 코드와 `PIPE` 코드는 동일 파일(dashboard.py)이지만 완전히 다른 `if/elif` 분기에서 실행됨.

---

## 14. Calculator Type별 지원범위

| 유형 | AI 제안 | Dashboard 검증 | 확정 | HOLD-1 | CA-3 지원 | CA-4 이연 |
|------|---------|---------------|------|--------|----------|----------|
| **Type A** (단순 산술) | ✅ AI 호출 | ✅ validate_formula | ✅ | ai_suggested/pending | ✅ 완전 지원 | — |
| **Type B** (dict 다중출력) | ✅ AI 호출 | ✅ dict 검증 | ✅ | ai_suggested/pending | ✅ 완전 지원 | — |
| **Type C** (해석 필요) | ⚠️ AI 가능하나 정확성 낮음 | ✅ 구문 검증 | ✅ | pending | ✅ (주의 필요) | legal_refs UI |
| **Type D** (CUSTOM_COMPUTE) | ❌ AI 차단 | ❌ (custom handler) | N/A | HOLD-1 항상 | ❌ 차단 | CA-4 |
| **Type D** (table-dependent) | ❌ 키워드 차단 | N/A | N/A | HOLD-1 항상 | ❌ 차단 | CA-4 |

**9개 기존 계산기 분류**:

| 계산기 | 유형 | AI 제안 가능 |
|--------|------|------------|
| 주휴수당 | A | ✅ |
| 연차수당 | A | ✅ |
| 퇴직금 간이 | A | ✅ |
| 3.3% 원천징수 | A | ✅ |
| 4대보험 | B | ✅ (조건부) |
| 연차잔여일 | B | ✅ (조건부) |
| 실업급여 | D | ❌ (테이블 의존) |
| 연말정산 | D | ❌ (CUSTOM_COMPUTE) |
| 육아휴직 | D | ❌ (CUSTOM_COMPUTE) |

---

## 15. 기존 테스트 재사용 가능성

| E2E 항목 | 기존 테스트 파일 | 커버리지 |
|---------|--------------|---------|
| E2E-1 정상 AI Formula 제안 | `test_suggest_formula.py` | ✅ 단위 완전 |
| E2E-2 덮어쓰기 방지 | `test_formula_contract.py` CA-3-4 TEST-2/3 | ✅ 로직 |
| E2E-3 AI 실패 | `test_suggest_formula.py` TEST-8/9 | ✅ 완전 |
| E2E-4 수정→pending_validation | `test_formula_contract.py` CA-3-1 TEST-7, CA-3-4 TEST-5 | ✅ |
| E2E-5 검증→operator_confirmed | `test_formula_contract.py` test_validation_pass_then_operator_confirmed | ✅ |
| E2E-6 dict Formula | `test_formula_contract.py` CA-3-4 TEST-6 | ✅ 직렬화 |
| E2E-7 HOLD lifecycle | `test_formula_contract.py` test_hold1_fires_for_ai_suggested | ✅ |
| E2E-8 Contract Instance round-trip | `test_formula_contract.py` test_contract_instance_* | ✅ 기본 |
| E2E-9 delete_app cleanup | `test_af_contract_dashboard.py` | ⚠️ 부분 |
| E2E-10 Mode A isolation | `test_af_contract_dashboard.py` I항목 | ✅ |
| E2E-11 session discard | `test_af_discard.py` + CA-3-4 TEST-7 | ✅ |
| E2E-12 blog isolation | 구조적 분리 확인됨 (테스트 불필요) | ✅ |

---

## 16. 필요한 신규 테스트

기존 테스트로 커버되지 않는 항목:

### 16-1. 필수 신규 테스트

| 테스트 ID | 내용 | 이유 |
|----------|------|------|
| E2E-NEW-1 | suggest_formula() 성공 → session state 설정 → build_contract() 호출 → formula_status = "pending_validation" | ai_suggested가 build_contract()에서 의도적으로 pending_validation으로 변환됨을 명시적으로 검증 |
| E2E-NEW-2 | operator_confirmed 후 build_contract() → formula_status = "operator_confirmed" 보존 | 확정 후 생성 경로 완전 검증 |
| E2E-NEW-3 | AI suggested formula → generate_app_with_contract() → Contract Instance formula 보존 | dict formula round-trip through full pipeline |
| E2E-NEW-4 | delete_app() → Contract Instance 파일 삭제 + registry.yaml 항목 제거 완전성 | 기존 테스트가 부분적으로만 검증 |
| E2E-NEW-5 | discard 후 CA-3-4 신규 키(4개) 소거 확인 | `_full_session()`에 CA-3-4 키 미포함 |

### 16-2. 선택 신규 테스트 (권장)

| 테스트 ID | 내용 |
|----------|------|
| E2E-OPT-1 | dict formula AI 제안 → text_area 직렬화 → json.loads() → build_contract() dict formula 복원 |
| E2E-OPT-2 | HOLD-1 발동 후 경고 메시지에 "formula가 운영자 확정 상태가 아닙니다" 포함 확인 |
| E2E-OPT-3 | validate_against_contract()가 formula_status를 체크하지 않음 확인 |

---

## 17. Regression 실행 계획

### 17-1. CA-3-F에서 실행할 명령

```bash
# 전체 Regression (기준: 537 PASS / 1 known FAIL)
python -m pytest tests/ -q --tb=short 2>&1 | tail -20

# 개별 파일 실행 (빠른 확인)
python -m pytest tests/test_formula_contract.py -v
python -m pytest tests/test_suggest_formula.py -v
python -m pytest tests/test_af_contract_dashboard.py -v
python -m pytest tests/test_af_discard.py -v
```

### 17-2. 성공 기준

| 항목 | 기준 |
|------|------|
| 총 PASS | ≥ 537 |
| 신규 FAIL | 0 |
| known FAIL | `test_full_pipeline_execution` 1건 (WordPress 연결 실패) |
| known FAIL 내용 | 변경 없음 |

---

## 18. 남은 Gap

| Gap | 내용 | 영향도 | CA-3-F 처리 |
|-----|------|--------|------------|
| G-1 | `ai_suggested` 상태가 Contract Instance에 저장되지 않음 | 낮음 | 설계된 동작, 문서화로 충분 |
| G-2 | `_full_session()`에 CA-3-4 키 4개 미포함 | 낮음 | CA-3-F 테스트 추가 권장 |
| G-3 | delete_app() 후 Contract Instance 삭제 통합 테스트 미흡 | 중간 | CA-3-F 신규 테스트 필요 |
| G-4 | `legal_refs` 입력 UI 없음 → suggest_formula()에 `legal_refs=[]` 전달 | 낮음 | CA-4 이연 (현재 동작에 문제 없음) |
| G-5 | suggest_formula() → build_contract() 상태 파생 명시적 테스트 없음 | 중간 | CA-3-F E2E-NEW-1/2 추가 |
| G-6 | 운영자가 [검증] 없이 [Contract 기반 생성] 직접 클릭 시 HOLD-1 발동 확인 | 낮음 | CA-3-F에서 확인 |

---

## 19. CA-3-F 최종검증 준비도

### 19-1. 현재 상태 체크리스트

- [x] CA-3-1: ai_suggested lifecycle 구현 (dashboard.py + app_factory.py)
- [x] CA-3-2: suggest_formula() 설계 조사 완료
- [x] CA-3-3: suggest_formula() 구현 (18개 테스트 PASS)
- [x] CA-3-4: Dashboard 연결 구현 (7개 테스트 PASS)
- [x] CA-3-5: 사전조사 완료 (이 보고서)
- [ ] CA-3-F: 신규 E2E 테스트 5개 추가 및 전체 Regression 최종 확인

### 19-2. CA-3-F 구현 범위

코드 수정: **없음** (테스트 파일만 추가)

추가 파일:
- `tests/test_formula_contract.py` 말미에 E2E-NEW-1~5 추가 (+약 80줄)

전체 Regression 실행 확인.

### 19-3. CA-3-F 완료 기준

- 신규 FAIL = 0
- PASS ≥ 542 (537 + 5 신규)
- known FAIL 내용 불변
- docs/CA3_F_FINAL_REPORT.md 작성

---

## 20. 최종 판정

**PASS — CA-3-F 진행 가능**

**근거**:
1. 전체 E2E 흐름이 코드 수준에서 정합하게 연결됨 ✅
2. formula_status lifecycle이 Dashboard→Contract→Registry→Instance 전 단계에서 일관됨 ✅
3. ai_suggested의 Contract Instance 미저장은 설계된 동작으로 확인됨 ✅
4. R-6 덮어쓰기 방어가 모든 시나리오에서 올바르게 작동함 ✅
5. Mode A/Blog/WordPress 완전 분리 확인됨 ✅
6. 기존 537개 테스트 대부분이 E2E 항목을 커버함 ✅
7. 신규 필요 테스트 5개로 남은 Gap 해소 가능 ✅

**주의 사항**:
- G-3 (delete_app Contract Instance 삭제): CA-3-F에서 반드시 테스트 추가
- G-5 (suggest_formula→build_contract 상태 파생): E2E-NEW-1이 필수
- G-2 (discard 키 소거): E2E-NEW-5로 완전 검증
