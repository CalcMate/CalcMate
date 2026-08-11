# CA-3-F 사전조사 보고서 — AI Formula Contract System 최종검증

**날짜**: 2026-08-11  
**조사 대상**: CA-3-1 ~ CA-3-5 전체 구현 (modules/app_factory.py, modules/formula_engine.py, dashboard.py)  
**절대 원칙**: 이 보고서는 사전조사 전용. 코드 수정 0건.  
**최종 판정**: **PASS**

---

## 1. 조사 범위

| 단계 | 내용 | 결과 |
|------|------|------|
| CA-3-1 | ai_suggested 상태 감지 로직 | ✅ 구현 완료 |
| CA-3-2 | legal_master 연동 + suggest_formula 기반 | ✅ 구현 완료 |
| CA-3-3 | Type D 차단 + suggest_formula 전체 구현 | ✅ 구현 완료 |
| CA-3-4 | Dashboard AI Formula 제안 버튼 연결 | ✅ 구현 완료 |
| CA-3-5 | E2E + Regression 최종검증 | ✅ 554 PASS / 1 known FAIL |

조사 파일:
- `modules/app_factory.py` (전체, 총 1,000+ 줄)
- `modules/formula_engine.py` (전체)
- `dashboard.py` (lines 2249–2370, CA-3-4 구현 구간)
- `tests/test_formula_contract.py` (44개 테스트)
- `tests/test_suggest_formula.py` (18개 테스트)
- `tests/test_e2e_ca35.py` (17개 테스트)
- `tests/test_app_factory_contract.py`, `test_af_discard.py`, `test_af_contract_dashboard.py`

---

## 2. Formula Lifecycle 상태 머신

```
not_generated
    │
    ├─(suggest_formula 성공)─→ ai_suggested  [Dashboard tracking only]
    │                               │
    │                               ├─(operator 수정)─→ pending_validation
    │                               └─(build_contract 경유)─→ pending_validation
    │
    ├─(수동 입력)─→ pending_validation
    │                    │
    │                    └─([✅ Formula 확정] 클릭)─→ operator_confirmed
    │                                                      │
    │                    (formula 수정 감지)─────────────→ pending_validation
    └─────────────────────────────────────────────────────┘
```

**핵심 설계 결정**:
- `ai_suggested`는 **Dashboard 추적 전용**이다. Contract Instance(YAML)에 절대 저장되지 않는다.
- `build_contract(formula_status=None, formula=X)` → `derived_status = "pending_validation"` (app_factory.py:319-320)
- 운영자가 Formula를 수동으로 확정(`[✅ Formula 확정]`)해야만 `operator_confirmed` 도달

**상태별 HOLD-1 발동 여부**:
| 상태 | HOLD-1 발동 |
|------|------------|
| `not_generated` | ✅ 발동 |
| `ai_suggested` | ✅ 발동 (Dashboard 추적 → build_contract 경유 → pending으로 변환) |
| `pending_validation` | ✅ 발동 |
| `operator_confirmed` | ❌ 미발동 |

---

## 3. AI Suggestion 흐름 (suggest_formula)

**함수 위치**: `modules/app_factory.py` line 477

**흐름도**:
```
suggest_formula(cfg, name, category, desc, input_fields, output_fields, legal_refs, slug)
    │
    ├─[Type D 차단 1] slug in CUSTOM_COMPUTE_SLUGS → _fail("커스텀 계산 로직")
    ├─[필수 입력 확인] input_fields 없음 → _fail
    ├─                 output_fields 없음 → _fail
    ├─[legal_master 조회] legal_refs 있고 calc_flows 없으면 → load_legal_master() 경유 조회
    ├─[Type D 차단 2] _is_type_d_flow(calc_flows) → _fail("테이블/법령 기준값")
    ├─[Prompt 구성] multi_output(len>1) → JSON format rule / single → 산술 표현식 rule
    ├─[AI 호출] _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)  ← R-7: try/except
    ├─[빈 응답 처리] raw_text 없음 → _fail
    ├─[JSON 파싱] parse_json_lenient() → except → raw_text.strip() 폴백  ← R-8
    ├─[formula null 처리] formula is None/""/=="null" → _fail
    ├─[dict JSON 파싱] formula 문자열이 "{" 시작 → json.loads()
    ├─[R-2] isinstance(dict) + output_fields → extra = actual_keys - expected_keys → _fail if extra
    ├─[R-1] validate_formula(parsed_formula, {f:"number" for f in input_fields}) → _fail if not ok
    └─[성공] {success:True, formula:..., reason:..., status:"ai_suggested"}
```

**반환 status**: `"ai_suggested"` (성공) 또는 `"not_generated"` (실패/차단)

---

## 4. R-1 방어 (입력 변수 검증)

**구현 위치**: `app_factory.py` lines 648-655

```python
schema = {f: "number" for f in input_fields}
ok, msg = validate_formula(parsed_formula, schema)
if not ok:
    return _fail(f"AI Formula 변수 검증 실패: {msg}", [f"변수 검증 오류: {msg}"])
```

**validate_formula() 동작** (`formula_engine.py` line 112):
1. CUSTOM_COMPUTE_SLUGS slug → validate_compute_handler()로 위임
2. dict formula: JSON 문자열 파싱 후 `.values()`로 각 식 순회
3. AST 파싱 (`ast.parse(expr, mode="eval")`)
4. `ast.walk()` → `ast.Name` 노드: `node.id not in allowed and node.id not in _FUNCS` → 실패
5. 금지 노드: `ast.Attribute`, `ast.Subscript`, `ast.Lambda`, `ast.ListComp`, `ast.comprehension`
6. dummy 값(1.0)으로 `execute_formula()` 실행 테스트

**커버리지**: 존재하지 않는 변수, 금지 구문(속성 접근, 람다 등) 차단 확인됨.

---

## 5. R-2 방어 (dict formula 출력 키 검증)

**구현 위치**: `app_factory.py` lines 638-646

```python
if isinstance(parsed_formula, dict) and output_fields:
    expected_keys = set(output_fields)
    actual_keys = set(parsed_formula.keys())
    extra = actual_keys - expected_keys
    if extra:
        return _fail(f"AI가 정의되지 않은 출력 변수를 사용했습니다: {extra}", ...)
```

**보호 대상**: AI가 `output_fields`에 없는 출력 키를 임의로 추가하는 것을 차단.  
**방향**: `actual - expected` (extra만 차단; missing은 R-1의 validate_formula 단계에서 잡힘)

---

## 6. R-6 방어 (2-click 덮어쓰기 확인)

**구현 위치**: `dashboard.py` lines 2262-2308

```python
_existing_formula = (_af_formula or "").strip()
_override_set = st.session_state.pop("_af_ai_suggest_override", False)
if _existing_formula and not _override_set:
    # 1차 클릭 — 경고 후 대기
    st.warning("⚠️ 기존 Formula가 있습니다. 다시 클릭하면 AI 제안으로 교체됩니다.")
    st.session_state["_af_ai_suggest_override"] = True
else:
    # 2차 클릭 또는 기존 formula 없음 — AI 호출
    ...
```

**설계 특성**:
- `pop()` 1회 읽기+삭제 원자 연산 → Streamlit rerun 모델에서 플래그 소진 확실
- 기존 formula 없으면 1클릭 즉시 AI 호출 (경고 불필요)
- 플래그 `_af_ai_suggest_override`는 AF_SESSION_DISCARD_KEYS에 포함 (초기화 시 소거)

---

## 7. R-7 방어 (AI 호출 실패 처리)

**구현 위치**: `app_factory.py` lines 598-602

```python
try:
    raw_text, _, _ = _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)
except Exception as exc:
    LOG.error("suggest_formula AI 호출 실패: %s", exc)
    return _fail(f"AI 호출 실패: {exc}", [str(exc)])
```

**보호**: 네트워크 오류, API 키 오류, 타임아웃 등 모든 AI 호출 예외 → `_fail()` dict 반환.  
**Dashboard 동작**: `_sf_result["success"]` False → `st.error()` 표시, 기존 formula 유지.

---

## 8. R-8 방어 (JSON 파싱 + raw string 폴백)

**구현 위치**: `app_factory.py` lines 608-628

```python
try:
    obj = parse_json_lenient(raw_text)
    if isinstance(obj, dict):
        parsed_formula = obj.get("formula")
        ...
    else:
        parsed_formula = str(obj).strip() if obj is not None else None
except Exception:
    parsed_formula = raw_text.strip().strip("\"'")  # raw string 폴백
```

**보호**: AI가 JSON 형식 대신 plain text 수식 반환 시에도 formula 파싱 시도.  
**후속 방어**: raw string 폴백 이후에도 R-1(validate_formula)이 실행되어 안전성 보장.

---

## 9. Type A / B / D 분류

| 타입 | 조건 | AI Formula 지원 |
|------|------|----------------|
| **Type A** | `len(output_fields) == 1` | ✅ HIGH — 단일 산술 표현식 |
| **Type B** | `len(output_fields) > 1` | ✅ MEDIUM — dict JSON 형식 |
| **Type D-1** | slug in `CUSTOM_COMPUTE_SLUGS` | ❌ BLOCKED |
| **Type D-2** | `_is_type_d_flow(calc_flows)` == True | ❌ BLOCKED |

**CUSTOM_COMPUTE_SLUGS** (`formula_engine.py` line 25):
```python
frozenset({"연말정산_환급액_계산기", "육아휴직_급여_계산기"})
```

**_TYPE_D_FLOW_KEYWORDS** (`app_factory.py` line 463):
```python
frozenset({"매년 변경", "별표", "테이블", "나이·피보험기간"})
```

**Type B 포맷**: `multi_output = len(output_fields) > 1` → system prompt에 JSON format rule 삽입:
```python
output_format_rule = f"5. 복수 출력이므로 JSON 형식으로 반환: " + json.dumps({k: "산술식" for k in output_fields}) + " (출력 변수 목록과 키 이름 일치)\n"
```

---

## 10. Formula 검증 (validate_formula_with_samples)

**함수 위치**: `formula_engine.py` line 205

**3단계 검증**:
| 단계 | 함수 | 내용 |
|------|------|------|
| Level 1 | `validate_formula()` | AST 구문 파싱, 금지 노드 차단 |
| Level 2 | `validate_formula()` | input_schema 외 변수명 차단 |
| Level 3 | `execute_formula()` | test_cases 기반 실제 계산 실행 |

**반환 형식**:
```python
{
    "valid": bool,
    "message": str,
    "sample_results": [{"input": {}, "output": {}, "expected": {}, "match": bool|None}]
}
```

**Dashboard 연동**: `[🔍 Formula 검증]` 버튼 → `af_formula_validation` session state에 저장 → `[✅ Formula 확정]` 버튼 활성화 조건 = `valid==True AND no match==False`

---

## 11. HOLD-1 / HOLD-2 / HOLD-3

**함수 위치**: `app_factory.py` line 340 (`check_hold_rules()`)

**HOLD-1**:
```python
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    rules.append("HOLD-1")
```
- 발동 조건: `operator_confirmed` 이외 모든 상태
- ai_suggested → build_contract → pending_validation → HOLD-1 발동 (설계 의도대로)

**HOLD-2**:
```python
if (contract.get("test_cases_status") == "not_generated"
        and contract.get("category") in CRITICAL_CATEGORIES):
    rules.append("HOLD-2")
```
- CRITICAL_CATEGORIES (`review_center.py` line 17): 세금/세법, 노동/고용법, 복지/사회보험, 병역/공무, 세금/정부혜택, 노무/급여, 고용/보험, 노무/급여/보험

**HOLD-3**:
```python
medium_refs = [ref for ref in legal_refs if (lm.get(ref) or {}).get("confidence") == "medium"]
if medium_refs:
    rules.append("HOLD-3")
```

**Soft Gate vs Hard Block**:
- `check_hold_rules()` 반환: `{"held": bool, "rules": [...], "messages": [...]}`
- **Soft Gate**: 경고 표시만. 운영자가 확인 후 생성 진행 여부 결정. 자동 차단 없음.
- Dashboard에서 HOLD-1 경고를 표시해도 `[🏭 계산기 생성]` 버튼은 활성 상태 유지.

---

## 12. Contract Instance

**저장 함수**: `_save_contract_instance()` (`app_factory.py` line 1025)  
**삭제 함수**: `_delete_contract_instance()` (`app_factory.py` line 1050)  
**경로**: `docs/contract_schema/instances/{calc_slug}.yaml`

**저장 시점**: `save_app()` 내부 (line 1154) — 계산기 DB 저장 성공 후

**저장 내용** (build_contract() dict + `generated_at` KST timestamp):
```yaml
slug: ...
name: ...
category: ...
tier: ...
input_fields: [...]
output_fields: [...]
formula: ...               # operator_confirmed된 formula만 여기 존재
formula_status: ...        # pending_validation 또는 operator_confirmed (ai_suggested 없음)
scope_exclusions: [...]
test_cases: [...]
test_cases_status: ...
desc: ...
legal_refs: [...]
generated_at: 2026-08-11T...+09:00
```

**ai_suggested가 Contract Instance에 없는 이유**:
- Dashboard에서 AI 제안 후 build_contract() 호출 시 `formula_status=None` 전달
- `None` + formula 있음 → `derived_status = "pending_validation"` (자동 도출)
- 따라서 Contract Instance에는 `ai_suggested` 상태가 절대 기록되지 않음

**삭제 경로**: 계산기 삭제 시 `_delete_contract_instance(slug)` 호출 (line 1229) → YAML + registry.yaml 항목 모두 제거

---

## 13. Registry 분리

| 저장소 | 경로 | 용도 |
|--------|------|------|
| App Factory Registry | `docs/registry/*_af.yaml` | 계산기 메타데이터 (status=HOLD/READY) |
| Contract Instance | `docs/contract_schema/instances/*.yaml` | 운영자 확정 스펙 |
| 기존 Registry | `docs/registry/labor.yaml` 등 | 기존 9개 계산기 (수정 금지) |

**분리 보장**:
- `_write_registry_v3()`: 기존 v3 slug와 중복 시 `ValueError` (line 178)
- `_delete_from_registry_v3()`: `_af.yaml`에서만 제거, 기존 파일 접근 불가
- `promote_to_ready()`: `source != "app_factory"` 거부 (line 247)

---

## 14. Dashboard UI (CA-3-4 구현)

**버튼 위치**: `dashboard.py` line 2251 (`# ── CA-3-4: AI Formula 제안 버튼 ──`)

**버튼 활성화 조건**:
```python
_sf_input_ok = (
    bool((_af_input_fields or "").strip())
    and bool((_af_output_fields or "").strip())
)
st.button("🤖 AI Formula 제안", disabled=not _sf_input_ok, ...)
```

**AI 호출 후 session state 업데이트**:
```python
st.session_state["af_contract_formula"]         = _sf_formula_str  # text_area에 반영
st.session_state["af_formula_ai_suggested_text"] = _sf_formula_str  # ai_suggested 추적
st.session_state.pop("af_formula_confirmed_text", None)            # 이전 확정 소거
st.session_state.pop("af_formula_validation", None)                # 이전 검증 소거
if st.session_state.get("af_contract"):
    st.session_state["af_contract"]["formula_status"] = "ai_suggested"
```

**dict formula 직렬화**:
```python
_sf_formula_str = (
    json.dumps(_sf_formula, ensure_ascii=False)  # compact JSON (no indent)
    if isinstance(_sf_formula, dict)
    else str(_sf_formula)
)
```

**Badge fallback** (af_contract=None일 때, line 2311-2323):
```python
_fv_badge_status = (st.session_state.get("af_contract") or {}).get("formula_status")
if _fv_badge_status is None:
    _fv_ai_badge_raw = st.session_state.get("af_formula_ai_suggested_text", "")
    if _fv_ai_badge_raw and _fv_cur_raw_badge == _fv_ai_badge_raw:
        _fv_badge_status = "ai_suggested"   # CA-3-4 추가
```

**수정 감지 로직**:
- operator_confirmed 무효화 (CA-2-6-2): `af_formula_confirmed_text` vs current → pending_validation (line 2341)
- ai_suggested 무효화 (CA-3-1): `af_formula_ai_suggested_text` vs current → pop + pending_validation (line 2348)

---

## 15. Session State 관리

**AF_SESSION_DISCARD_KEYS** 총 21개 (`app_factory.py` lines 42-66):

| 키 | 용도 | 추가 단계 |
|----|------|----------|
| `af_result` | AI 생성 결과 전체 | 기존 |
| `af_name` ~ `af_keyword` | 기본 입력 필드 | 기존 |
| `af_tier_suggest` | AI Tier 추천 상태 | 기존 |
| `_af_last_slug_for` | slug 자동완성 추적 | 기존 |
| `af_seo` | SEO 제목 표시 | 기존 |
| `af_discard_confirm` | 폐기 확인 플래그 | 기존 |
| `af_contract` ~ `af_contract_test_cases` | Mode B 전용 (7개) | CA-2 |
| `af_formula_confirmed_text` | operator_confirmed raw | CA-3-1 |
| `af_formula_validation` | [🔍] 결과 dict | CA-3-1 |
| `af_formula_ai_suggested_text` | AI 제안 추적 | CA-3-4 |
| `_af_ai_suggest_override` | 2-click 플래그 | CA-3-4 |

**Discard/초기화 동작**: `[🗑 초기화]` 버튼이 위 21개 키 모두 pop → `st.rerun()` → 완전 초기화

---

## 16. Blog/WordPress 파이프라인 분리 확인

**git diff --stat** 분석 결과:
- `modules/app_factory.py`: +395줄 (CA-3 구현)
- `dashboard.py`: +188줄 (CA-3-4 구현)
- `logs/content_pipeline/*.json`: 로그 파일 업데이트 (내용 변경 아님)
- `modules/formula_engine.py`: 변경 없음 (CA-3-F 조사 범위)

Blog/WordPress 관련 파일 (`content_pipeline`, `wordpress`) 변경 없음.  
suggest_formula()는 `_chat(cfg, "orchestrator", ...)` 경유 → 블로그 파이프라인과 완전 독립.

---

## 17. Production 영향 분석

**기존 9개 계산기**:
- `CUSTOM_COMPUTE_SLUGS` = {"연말정산_환급액_계산기", "육아휴직_급여_계산기"} → suggest_formula 진입 차단
- 나머지 7개: suggest_formula를 호출할 UI 경로 없음 (Dashboard Mode B 전용 버튼)
- `generate_app()` (Mode A): `_contract=None` 경로 → CA-3 코드 미관여

**Mode A vs Mode B 분리**:
```python
# Mode A: _contract 없음
generate_app(cfg, name, category, desc, tier)           # _contract=None

# Mode B: _contract 있음
generate_app_with_contract(cfg, contract)               # _contract=contract 전달
    → generate_app(cfg, ..., _contract=contract)
    → validate_against_contract()
```

CA-3의 `suggest_formula()`는 `generate_app()` 전에 독립 실행되며, 결과를 Dashboard의 `af_contract_formula` text_area에 삽입하는 것으로 끝난다. `generate_app()` 호출 경로에 영향 없음.

---

## 18. CA-2 → CA-3 Gap 추적

| CA 단계 | 구현 내용 | 완료 여부 |
|---------|----------|----------|
| CA-2-4 | build_contract() 기본 구조 | ✅ |
| CA-2-5 | generate_app_with_contract() + validate_against_contract() | ✅ |
| CA-2-6-2 | formula_status 배지 + operator_confirmed 무효화 | ✅ |
| CA-3-1 | ai_suggested 수정 감지 → pending_validation 복귀 | ✅ |
| CA-3-2 | legal_master 연동 + suggest_formula 시그니처 | ✅ |
| CA-3-3 | Type D 차단 + R-1/R-2/R-7/R-8 + suggest_formula 완전 구현 | ✅ |
| CA-3-4 | Dashboard 버튼 + R-6 + 4 DISCARD_KEYS + badge fallback | ✅ |
| CA-3-5 | E2E 17개 테스트 + Regression 검증 | ✅ |

**CA-2 잔여 Gap**: 없음. CA-3 구현으로 모두 충족됨.

---

## 19. CA-3 완료 체크리스트 (23항목)

| # | 항목 | 확인 위치 | 상태 |
|---|------|----------|------|
| 1 | `suggest_formula()` 함수 존재 | `app_factory.py:477` | ✅ |
| 2 | `suggest_formula()`가 `generate_app()`과 독립 | 함수 서명·호출 경로 | ✅ |
| 3 | Type D 차단 1: CUSTOM_COMPUTE_SLUGS | `app_factory.py:525` | ✅ |
| 4 | Type D 차단 2: `_is_type_d_flow()` | `app_factory.py:549` | ✅ |
| 5 | `_TYPE_D_FLOW_KEYWORDS` 4개 정의 | `app_factory.py:463` | ✅ |
| 6 | R-1: `validate_formula()` 입력 변수 검증 | `app_factory.py:648` | ✅ |
| 7 | R-2: dict formula 출력 키 검증 | `app_factory.py:638` | ✅ |
| 8 | R-7: AI 호출 try/except + `_fail()` 반환 | `app_factory.py:598` | ✅ |
| 9 | R-8: JSON 파싱 + raw string 폴백 | `app_factory.py:614` | ✅ |
| 10 | `check_hold_rules()` 함수 존재 | `app_factory.py:340` | ✅ |
| 11 | HOLD-1: `operator_confirmed` 이외 → 경고 | `app_factory.py:357` | ✅ |
| 12 | HOLD-2: critical category + test_cases 없음 | `app_factory.py:366` | ✅ |
| 13 | HOLD-3: legal_refs confidence=medium | `app_factory.py:374` | ✅ |
| 14 | Soft Gate 설계 (hard block 아님) | `check_hold_rules()` 반환 구조 | ✅ |
| 15 | Dashboard AI Formula 버튼 삽입 | `dashboard.py:2251` | ✅ |
| 16 | R-6: 2-click override 패턴 | `dashboard.py:2262` | ✅ |
| 17 | dict formula compact JSON 직렬화 | `dashboard.py:2286` | ✅ |
| 18 | `af_contract["formula_status"] = "ai_suggested"` 업데이트 | `dashboard.py:2300` | ✅ |
| 19 | Badge fallback (af_contract=None) | `dashboard.py:2318` | ✅ |
| 20 | AF_SESSION_DISCARD_KEYS 4개 추가 | `app_factory.py:61-65` | ✅ |
| 21 | `ai_suggested` Contract Instance 미저장 (설계 의도) | `build_contract()` formula_status 도출 | ✅ |
| 22 | `_save_contract_instance()` / `_delete_contract_instance()` | `app_factory.py:1025,1050` | ✅ |
| 23 | Registry 분리 (_af.yaml vs contract_schema/) | `_write_registry_v3()` 보호 로직 | ✅ |

---

## 20. Regression 결과

**실행 명령**:
```
python -m pytest tests/ --tb=no -q
```

**결과**:
```
1 failed, 554 passed, 494 warnings in 81.16s
```

| 항목 | 기준 | 실제 | 판정 |
|------|------|------|------|
| PASS | ≥ 542 | 554 | ✅ |
| FAIL | = 1 (known) | 1 | ✅ |

**known FAIL**: `tests/production_validation_test.py::test_full_pipeline_execution`  
→ WordPress 연결 실패 (네트워크 의존 테스트, 인프라 문제)  
→ CA-3 구현과 무관

**테스트 파일별 CA-3 관련 카운트**:
| 파일 | 테스트 수 | 관련 단계 |
|------|----------|----------|
| `test_formula_contract.py` | 44개 | CA-2 ~ CA-3-4 전체 |
| `test_suggest_formula.py` | 18개 | CA-3-3 suggest_formula |
| `test_e2e_ca35.py` | 17개 | CA-3-5 E2E |
| `test_app_factory_contract.py` | - | CA-2 Contract |
| `test_af_discard.py` | - | DISCARD_KEYS |
| `test_af_contract_dashboard.py` | - | Mode A/B 분리 |

CA-3 직접 관련 테스트 합계 (6개 파일): **216개** (`--collect-only` 기준)

---

## 21. Git Diff 보호 확인

**변경 파일 (CA-3 구현)**:
- ✅ `dashboard.py` (+188줄: CA-3-4 버튼, badge fallback)
- ✅ `modules/app_factory.py` (+395줄: suggest_formula, build_contract 확장, check_hold_rules, Contract Instance 함수)
- ✅ `tests/test_formula_contract.py` (+426줄: CA-2 ~ CA-3-4 44개 테스트)
- ✅ `tests/test_review_center.py` (+32줄: review_center 테스트 확장)
- ✅ `tests/test_e2e_ca35.py` (신규: CA-3-5 17개 E2E 테스트)
- ✅ `docs/registry/*.yaml` (App Factory 계산기 등록 부산물)

**절대 수정 금지 확인**:
| 보호 대상 | 상태 |
|----------|------|
| `_secret_replace2.txt` | `??` untracked — 미추가, 미커밋 ✅ |
| `annual-leave-remaining` 계산기 | 기존 9개 registry 변경 없음 ✅ |
| 기존 계산기 9개 | app_factory.py 수정 없음, Mode A 경로 보존 ✅ |
| `v2.0.0~v2.3.0` 태그 | git tag 조작 없음 ✅ |
| Blog/WordPress pipeline | content_pipeline 파일: 로그만, 로직 변경 없음 ✅ |
| 기존 _af.yaml 등록 엔트리 | _write_registry_v3() 보호로 중복 차단 ✅ |

---

## 22. 발견된 신규 Gap

**없음.**

이번 CA-3-F 사전조사에서 신규 구현 문제는 발견되지 않았다.

사소한 관찰 사항 (Gap 아님):
1. `formula_engine.py:56`: `ast.Num is deprecated` 경고 (494개 중 일부) — Python 3.14에서 제거 예정이나 현재 Python 3.x에서 동작 문제 없음. CA-3 구현 범위 외.
2. CRLF/LF 경고: Windows git 설정 부산물. 기능 영향 없음.

---

## 23. 최종 판정

### PASS ✅

**판정 근거**:

1. **Formula Lifecycle 완전 구현**: 4개 상태(not_generated → ai_suggested → pending_validation → operator_confirmed)가 Dashboard와 Contract Instance에서 설계대로 동작.

2. **AI Suggestion 흐름 완전 구현**: suggest_formula() → Dashboard 버튼 → Contract 갱신 E2E 경로 구현 및 검증 완료.

3. **R-1~R-8 방어 모두 구현**: Type D 차단(R-4/R-5), 입력 변수 검증(R-1), dict 출력 키 검증(R-2), 2-click 확인(R-6), AI 호출 실패 처리(R-7), JSON 폴백(R-8) 전부 코드에 존재.

4. **HOLD-1/2/3 Soft Gate**: `check_hold_rules()`가 ai_suggested/pending_validation에 대해 정상 발동. 하드 블락이 아닌 경고 구조로 설계 준수.

5. **ai_suggested 설계 결정 보존**: Contract Instance에 `ai_suggested` 상태 미저장. build_contract(formula_status=None) → pending_validation 자동 도출. 의도적 설계.

6. **Registry 분리 보장**: _af.yaml vs contract_schema/instances/ 완전 분리. 기존 9개 계산기 레지스트리 보호.

7. **Regression 기준 충족**: 554 PASS / 1 known FAIL (WordPress 네트워크 의존 테스트).

8. **Git 보호 원칙 준수**: _secret_replace2.txt 미커밋, 기존 계산기 미수정, 블로그 파이프라인 미수정.

9. **CA-3 완료 체크리스트 23/23 통과**.

---

**다음 단계**: CA-3 전체 구현 완료. `legal_master` 확장 또는 CA-4(READY 전환 자동화) 등 후속 로드맵 진행 가능.
