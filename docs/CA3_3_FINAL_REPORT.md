# CA-3-3 최종 보고서 — suggest_formula() AI Formula 제안 엔진

> 완료일: 2026-08-10  
> 기준: CA-3-2 사전조사 PASS 기반

---

## 1. 수정 파일

| 파일 | 변경 내용 | 줄 수 |
|------|-----------|-------|
| `modules/app_factory.py` | `_TYPE_D_FLOW_KEYWORDS`, `_is_type_d_flow()`, `suggest_formula()` 추가 | +155줄 |
| `tests/test_suggest_formula.py` | 신규 생성 — 18개 테스트 | +226줄 |

**변경 금지 파일 준수 확인**:
- `dashboard.py` — 변경 없음 ✅
- `docs/registry/*.yaml` — 변경 없음 ✅
- `docs/legal_master/*.yaml` — 변경 없음 ✅
- `docs/contract_schema/instances/*.yaml` — 변경 없음 ✅
- Blog/WordPress 관련 파일 — 변경 없음 ✅

---

## 2. suggest_formula() 최종 Signature

```python
def suggest_formula(
    cfg: dict,
    name: str,
    category: str = "",
    desc: str = "",
    input_fields: list = None,
    output_fields: list = None,
    legal_refs: list = None,
    calculation_flow: list = None,
    scope_exclusions: list = None,
    slug: str = None,
) -> dict:
```

**반환 형식**:
```python
# 성공
{
    "success": True,
    "formula": str | dict,
    "reason":  str,
    "assumptions": list,
    "warnings":    list[str],
    "status":  "ai_suggested",   # 항상 ai_suggested
}

# 실패
{
    "success": False,
    "formula": None,
    "reason":  str,
    "assumptions": [],
    "warnings":    list[str],
    "status":  "not_generated",
}
```

---

## 3. Prompt 구조

**sys_suggest** (orchestrator role, max_tokens=300):

```
너는 계산기 Formula 제안 도우미다.
제공된 Contract와 법적 근거 정보만 사용한다.
존재하지 않는 입력 변수나 출력 변수를 만들지 않는다.
제공되지 않은 법률 규칙, 요율, 기준값을 임의로 생성하지 않는다.
계산 규칙이 충분하지 않으면 Formula를 추측하지 않는다.
AI의 제안은 운영자의 최종 확정이 아니며, 검증되지 않은 Formula임을 전제로 한다.

입력 변수(이것만 사용 가능): {input_fields}
출력 변수: {output_fields}
[카테고리, 설명, 법령 계산 흐름 — 있을 때만]

규칙:
1. 입력 변수 목록 외 변수 절대 금지
2. 대입문(=), 세미콜론(;), 함수 정의, 외부 함수 호출 금지
3. 허용 함수: min, max, round, abs, int, float 만
4. calculation_flow에 없는 상수·요율 추가 금지
5. [단일/복수 출력 형식 지정]

반드시 아래 JSON 형식으로만 응답하라:
{"formula": "...", "reason": "...", "assumptions": [], "warnings": []}
계산 근거가 불충분하면:
{"formula": null, "reason": "근거 부족 이유", "assumptions": [], "warnings": ["..."]}
```

**u_suggest**: `f"계산기명: {name}"`

---

## 4. Type A/B/D 처리 결과

| 유형 | 처리 | 검증 |
|------|------|------|
| Type A (단순 산술) | AI 호출 → formula 반환 → R-1/R-2 검증 | ✅ PASS |
| Type B (다중 출력) | AI 호출 → dict formula → R-2 키 검증 → R-1 검증 | ✅ PASS |
| Type D (CUSTOM_COMPUTE_SLUGS) | AI 호출 없이 즉시 차단 (`slug` 파라미터) | ✅ PASS |
| Type D (calculation_flow 키워드) | AI 호출 없이 즉시 차단 (`_is_type_d_flow()`) | ✅ PASS |

**Type D 차단 키워드** (`_TYPE_D_FLOW_KEYWORDS`):
- `"매년 변경"`, `"별표"`, `"테이블"`, `"나이·피보험기간"`

---

## 5. JSON/Raw 파싱 결과

| 응답 유형 | 처리 경로 | 결과 |
|----------|----------|------|
| JSON `{"formula": "...", "reason": "...", ...}` | `parse_json_lenient()` → dict → formula 추출 | ✅ PASS |
| Raw string `"a * b"` | `parse_json_lenient()` 실패 → raw strip | ✅ PASS |
| JSON `{"formula": null, ...}` | formula=None 감지 → 실패 반환 | ✅ PASS |
| JSON dict formula `{"formula": {"k": "expr"}}` | dict formula 추출 후 R-2 검증 | ✅ PASS |
| 빈 문자열 | 빈 응답 감지 → 실패 반환 | ✅ PASS |

---

## 6. Input/Output Variable 방어 결과

| 위험 | 방어 수단 | 결과 |
|------|----------|------|
| R-1: AI가 없는 input 변수 사용 | `validate_formula(formula, schema)` — Level 2 | ✅ PASS (test 4) |
| R-2: AI가 없는 output 키 사용 (dict) | `actual_keys - expected_keys` → 차단 | ✅ PASS (test 5) |
| dict 키 ⊆ output_fields 부분집합 | 허용 (issubset 체크) | ✅ PASS |

---

## 7. AI 실패 처리 결과

| 실패 유형 | 처리 | 결과 |
|----------|------|------|
| 예외 (ConnectionError, timeout 등) | try/except → `_fail()` 반환 | ✅ PASS (test 8) |
| 빈 응답 (`""`, `"   "`) | 빈 응답 감지 → `_fail()` 반환 | ✅ PASS (test 9) |
| formula=null | `_fail()` 반환 | ✅ PASS |
| input_fields 없음 | AI 호출 없이 `_fail()` 반환 | ✅ PASS |
| output_fields 없음 | AI 호출 없이 `_fail()` 반환 | ✅ PASS |

**모든 예외가 외부로 전파되지 않음 확인** ✅

---

## 8. Formula Status 결과

| 조건 | status | 확인 |
|------|--------|------|
| AI 제안 성공 | `"ai_suggested"` | ✅ |
| `"operator_confirmed"` 자동 전환 | ❌ 발생하지 않음 | ✅ |
| `"pending_validation"` 자동 전환 | ❌ 발생하지 않음 | ✅ |
| 실패 시 | `"not_generated"` | ✅ |

---

## 9. 테스트 결과

| 테스트 | 내용 | 결과 |
|--------|------|------|
| TEST-1 `test_type_a_success_json` | Type A JSON 응답 | ✅ PASS |
| TEST-2 `test_type_b_dict_formula` | Type B dict formula | ✅ PASS |
| TEST-3a `test_type_d_blocked_by_custom_slug` | CUSTOM_COMPUTE_SLUGS 차단 | ✅ PASS |
| TEST-3b `test_type_d_blocked_by_keyword_in_flow` | 매년 변경 키워드 차단 | ✅ PASS |
| TEST-3c `test_type_d_blocked_by_table_keyword` | 별표 키워드 차단 | ✅ PASS |
| TEST-4 `test_invalid_input_variable` | R-1 입력 변수 검증 실패 | ✅ PASS |
| TEST-5 `test_invalid_output_variable` | R-2 출력 변수 검증 실패 | ✅ PASS |
| TEST-6 `test_json_response_parsing` | JSON 응답 파싱 | ✅ PASS |
| TEST-7 `test_raw_string_response_parsing` | Raw string 파싱 | ✅ PASS |
| TEST-8 `test_ai_call_failure_handled` | AI 호출 예외 처리 | ✅ PASS |
| TEST-9 `test_empty_ai_response_handled` | 빈 응답 처리 | ✅ PASS |
| TEST-10 `test_success_status_is_ai_suggested_not_operator_confirmed` | status 확인 | ✅ PASS |
| TEST-11 `test_suggest_formula_does_not_modify_external_state` | 외부 상태 미변경 | ✅ PASS |
| 추가 `test_missing_input_fields_returns_failure` | 필수 입력 체크 | ✅ PASS |
| 추가 `test_missing_output_fields_returns_failure` | 필수 입력 체크 | ✅ PASS |
| 추가 `test_ai_returns_null_formula` | null formula 처리 | ✅ PASS |
| 추가 `test_dict_formula_subset_of_output_fields_allowed` | 부분집합 허용 | ✅ PASS |
| 추가 `test_type_a_flow_no_type_d_keywords_passes` | Type A flow 정상 진행 | ✅ PASS |

**18/18 PASS** ✅

---

## 10. Regression 결과

| | PASS | FAIL |
|--|------|------|
| Before (CA-3-2 이후) | 512 | 1 (known) |
| After (CA-3-3) | 530 | 1 (known) |
| Delta PASS | **+18** | |
| Delta FAIL | 0 | |
| 신규 FAIL | **0** | |
| Known FAIL | `test_full_pipeline_execution` (WordPress) | |

---

## 11. Git Diff 범위

**수정된 파일**:
- `modules/app_factory.py` — `suggest_formula()` 함수 추가 (기존 함수 변경 없음)
- `tests/test_suggest_formula.py` — 신규 생성

**변경되지 않은 파일** (변경 금지 준수):
- `dashboard.py` ✅
- `docs/registry/*.yaml` ✅
- `docs/legal_master/*.yaml` ✅
- `docs/contract_schema/instances/*.yaml` ✅
- Blog/WordPress pipeline 관련 파일 ✅
- `build_contract()` ✅
- `check_hold_rules()` ✅
- `validate_formula_with_samples()` ✅
- `generate_app()` ✅
- `save_app()` / `delete_app()` ✅

---

## 12. 기존 기능 영향 여부

| 기능 | 영향 | 확인 |
|------|------|------|
| Mode A (`generate_app()`) | 없음 | ✅ |
| Mode B (`generate_app_with_contract()`) | 없음 | ✅ |
| `check_hold_rules()` HOLD-1/2/3 | 없음 | ✅ |
| Contract Instance 저장/로드 | 없음 | ✅ |
| Registry v3 | 없음 | ✅ |
| 블로그 생성 Pipeline | 없음 | ✅ |
| WordPress Publishing Pipeline | 없음 | ✅ |
| `CUSTOM_COMPUTE_SLUGS` | 읽기만 (import) | ✅ |
| `validate_formula()` | 재사용 (내부 호출) | ✅ |
| `_chat()` | 재사용 (내부 호출) | ✅ |

---

## 13. CA-3-4 Dashboard 연결 준비 상태

`suggest_formula()` 독립 함수가 완성되었으므로 CA-3-4에서 Dashboard 연결 시 필요한 것:

**Dashboard에서 호출하는 방법**:
```python
from modules.app_factory import suggest_formula

result = suggest_formula(
    cfg=cfg,
    name=af_name,
    category=af_cat,
    desc=af_desc,
    input_fields=[f.strip() for f in (af_input_fields or "").split(",") if f.strip()],
    output_fields=[f.strip() for f in (af_output_fields or "").split(",") if f.strip()],
    legal_refs=[],          # Dashboard에서 legal_refs 입력 UI 추가 시 연결
    calculation_flow=None,  # legal_refs로 자동 조회됨
    slug=af_slug,           # Type D 차단에 사용
)

if result["success"]:
    st.session_state["af_contract_formula"] = str(result["formula"])
    st.session_state["af_formula_ai_suggested_text"] = str(result["formula"])
    if st.session_state.get("af_contract"):
        st.session_state["af_contract"]["formula_status"] = "ai_suggested"
    if result["warnings"]:
        for w in result["warnings"]:
            st.warning(w)
    st.rerun()
else:
    st.error(result["reason"])
```

**CA-3-1에서 이미 준비된 것**:
- `af_formula_ai_suggested_text` 세션 키 수정 감지 로직 ✅
- Dashboard 배지 `"ai_suggested": "🔵 AI 제안"` ✅

**CA-3-4에서 추가할 것**:
- `[🤖 AI Formula 제안]` 버튼
- 2-click override 패턴 (기존 formula 덮어쓰기 확인)
- spinner 중 실행
- warnings → `st.warning()` 표시

---

## CA-3-3 완료 조건 체크리스트

- [x] `suggest_formula()` 독립 구현
- [x] 기존 `_chat()` 재사용
- [x] AI 호출 최대 1회
- [x] `max_tokens=300` 이하
- [x] Type A 지원
- [x] Type B 지원
- [x] Type D 차단 (CUSTOM_COMPUTE_SLUGS + 키워드)
- [x] JSON 응답 처리
- [x] Raw string 응답 처리
- [x] Input variable 검증 (R-1)
- [x] Output variable 검증 (R-2)
- [x] AI 호출 실패 안전 처리 (R-7)
- [x] 빈 응답 안전 처리 (R-8)
- [x] `status="ai_suggested"`
- [x] `operator_confirmed` 자동 전환 없음
- [x] 기존 Formula 자동 overwrite 없음
- [x] Dashboard 수정 없음
- [x] Blog Pipeline 수정 없음
- [x] WordPress Pipeline 수정 없음
- [x] 신규 테스트 18개 PASS
- [x] Regression 신규 FAIL 0

## **CA-3-3 PASS** ✅
