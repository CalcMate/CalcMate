# CA-3-0 사전조사 보고서 — AI Formula 자동제안 + Contract Builder 고도화

> 조사 기준일: 2026-08-10  
> 원칙: 코드 수정 0건 / 구현 없음 / 조사 전용  
> 기준 시스템: CA-2 FINAL PASS 상태 (505 PASS / 1 FAIL)

---

## 1. 현재 AI Formula 생성 구조

### 1-1. Formula가 생성되는 위치

`generate_app()` 함수 (`modules/app_factory.py:545`) 내 **Step 1 (orchestrator)**:

```python
# generate_app() Step 1 — 이곳에서 AI가 formula를 생성한다
sys1 = "너는 웹 계산기 기획자다. ... formula 규칙 ..."
u1   = f"계산기명: {name}\n카테고리: {category}\n설명: {desc}"
t1, m1, k1 = _chat(cfg, "orchestrator", sys1, u1, 800)
spec = parse_json_lenient(t1)
formula = spec.get("formula", "")   # AI가 반환한 formula
```

Step 1의 sys1 프롬프트가 요구하는 응답 형식:
```json
{"calculator_type":"", "input_schema":{}, "output_schema":{}, "formula":"또는{}", "labels":{}}
```

즉 **formula는 input_schema + output_schema + formula 묶음의 일부**로 생성된다.

### 1-2. Formula 생성 후 처리

```python
# Step 1 완료 후 validate_formula() 즉시 실행 (1회 재시도 포함)
ok, msg = validate_formula(spec.get("formula", ""), spec.get("input_schema", {}))
if not ok:
    # retry once — 동일 sys1에 실패 사유 추가 후 재시도
    ...
spec["_formula_valid"] = ok
spec["_formula_msg"]   = msg
```

**핵심 관찰**: 현재 formula 전용 단독 함수가 없다. formula는 항상 4-Step 파이프라인(스펙 → HTML → SEO → 이미지) 내 Step 1의 부산물로 생성된다.

### 1-3. CA-3에서 재사용 가능한 부분

| 구성 요소 | 재사용 가능 여부 |
|-----------|----------------|
| `_chat(cfg, "orchestrator", ...)` | ✅ 그대로 재사용 |
| `validate_formula()` | ✅ 그대로 재사용 |
| `validate_formula_with_samples()` | ✅ 그대로 재사용 |
| `parse_json_lenient()` | ✅ 그대로 재사용 |
| Step 1 전체 (스펙 생성) | ⚠️ 부분 — formula만 추출하는 경량 버전 필요 |
| Step 2/3/4 (HTML/SEO/이미지) | ❌ CA-3 불필요 |

**결론**: `suggest_formula(cfg, contract)` 전용 함수가 필요하다. 기존 Step 1 로직을 단순화한 버전으로, AI 호출 1회 + formula만 반환한다.

---

## 2. ai_suggested 상태 도입 가능 위치

### 2-1. 상태 머신 제안

```
not_generated
    ↓ [🤖 AI Formula 제안] 클릭
ai_suggested          ← NEW
    ↓ (수동 수정 시 → pending_validation)
    ↓ [🔍 Formula 검증] 클릭 (통과 시)
pending_validation
    ↓ [✅ Formula 확정] 클릭
operator_confirmed
```

**수정 감지 확장 (CA-2-6-2 기존 로직 병렬)**:
```python
# 기존 (CA-2-6-2)
if af_formula_confirmed_text and current != confirmed:
    → pending_validation

# CA-3 추가
if af_formula_ai_suggested_text and current != ai_suggested:
    → pending_validation   # (ai_suggested에서 수정됨)
```

### 2-2. ai_suggested 진입 조건

```python
# suggest_formula() 반환 후 dashboard에서
st.session_state["af_formula_ai_suggested_text"] = ai_formula_raw
# build_contract()에 formula_status="ai_suggested" 전달
```

### 2-3. AI 제안 직후 operator_confirmed 방지

- `check_hold_rules()` 현재 조건: `formula_status != "operator_confirmed"` → HOLD-1
- `ai_suggested != "operator_confirmed"` → HOLD-1 자동 발동 ✅
- **별도 코드 변경 없이 기존 HOLD-1 로직이 ai_suggested를 차단한다**

### 2-4. 하위 호환성

| 기존 요소 | ai_suggested 추가 시 영향 |
|-----------|--------------------------|
| `build_contract()` | None — `formula_status` passthrough 그대로 |
| `check_hold_rules()` HOLD-1 | None — `!= "operator_confirmed"` 이미 차단 |
| `_save_contract_instance()` | None — YAML에 `ai_suggested` 문자열 그대로 저장 |
| `_update_contract_registry()` | None — `formula_status` 값 그대로 기록 |
| `delete_app()` | None — 파일 삭제만, formula_status 무관 |
| 기존 Contract Instance YAML | None — 기존 파일 수정 불필요 |
| HOLD-1/2/3 | None — HOLD-1은 ai_suggested를 올바르게 차단 |
| `validate_against_contract()` | None — formula 비교 로직 무관 |

---

## 3. Formula Lifecycle 제안

### 3-1. 전체 lifecycle (CA-3 이후)

```
┌──────────────────────────────────────────┐
│  not_generated                           │
│     ↓ [🤖 AI Formula 제안]              │
│  ai_suggested    ┐                       │
│     ↓ 수동 수정  │→ pending_validation  │
│     ↓ [🔍 검증] (통과)                  │
│  pending_validation                      │
│     ↓ [✅ Formula 확정]                  │
│  operator_confirmed                      │
│     ↓ formula 수정                       │
│  pending_validation (반복)              │
└──────────────────────────────────────────┘
```

### 3-2. validate_formula_with_samples() 재사용 확인

AI 제안된 formula에 그대로 적용 가능:

```python
# suggest_formula() 반환값:
ai_result = {"formula": "a * hourly_wage", "formula_status": "ai_suggested"}

# 기존 검증 로직 그대로 재사용:
schema = {f: "number" for f in contract["input_fields"]}
result = validate_formula_with_samples(
    ai_result["formula"],
    schema,
    contract.get("test_cases") or None
)
# Level 1: 구문 ✅
# Level 2: input_fields에 없는 변수 → False ✅ (위험 1 자동 방어)
# Level 3: test_cases 있으면 실행 ✅
```

**재사용 가능: ✅ 변경 없이 그대로**

### 3-3. ai_suggested와 pending_validation 분리 기준

| 상태 | 의미 | 진입 경로 |
|------|------|----------|
| `ai_suggested` | AI가 제안, 운영자가 아직 검토 안 함 | [🤖 AI 제안] 클릭 |
| `pending_validation` | 운영자가 직접 입력/수정 or AI 제안 후 수동 수정 | formula 입력/수정 |
| `operator_confirmed` | 운영자가 검증 통과 후 직접 확정 | [✅ Formula 확정] 클릭 |

---

## 4. Dashboard 연결점

### 4-1. 현재 Contract Builder UI 구조 (CA-2-6-2 기준)

```
Contract Builder (expander)
  ├─ slug, input_fields, output_fields 입력
  ├─ _af_formula (text_area, key="af_contract_formula") ← 삽입 위치
  ├─ formula_status 배지 (🔍)
  ├─ test_cases (text_area)
  ├─ 수정 감지 로직 (af_formula_confirmed_text)
  ├─ [🔍 Formula 검증] 버튼
  ├─ [✅ Formula 확정] 버튼
  └─ [📋 Contract 기반 생성] 버튼
```

### 4-2. CA-3 최소 삽입 위치

**위치**: `_af_formula = st.text_area(...)` 이후, 배지 이전
```
formula text_area          ← 기존
    ↓
[🤖 AI Formula 제안] 버튼  ← NEW (CA-3)
    ↓ 클릭 시 suggest_formula() 호출
formula_status 배지         ← 기존 (ai_suggested 배지 추가)
```

### 4-3. UI 흐름 (최소 변경)

```python
# (1) [🤖 AI Formula 제안] 버튼 클릭
if st.button("🤖 AI Formula 제안", key="af_formula_ai_suggest"):
    if not _af_input_fields.strip() or not _af_output_fields.strip():
        st.error("입력/출력 필드를 먼저 입력해야 AI Formula를 제안받을 수 있습니다.")
    else:
        # suggest_formula(cfg, partial_contract) 호출
        # → result = {"formula": "...", "formula_status": "ai_suggested", ...}
        st.session_state["af_ai_suggested_formula"] = result["formula"]
        st.session_state["af_formula_ai_suggested_text"] = str(result["formula"])
        st.session_state["af_contract_formula"] = str(result["formula"])  # text_area 반영
        st.rerun()

# (2) 배지에 "ai_suggested" 추가
_fv_badge_map = {
    "not_generated":     "⚪ Formula 미생성",
    "pending_validation": "🟡 검증 대기",
    "ai_suggested":       "🤖 AI 제안",   # NEW
    "operator_confirmed": "🟢 운영자 확정",
}

# (3) 수정 감지 확장
if af_formula_ai_suggested_text and current != af_formula_ai_suggested_text:
    st.session_state.pop("af_formula_ai_suggested_text", None)
    if st.session_state.get("af_contract"):
        st.session_state["af_contract"]["formula_status"] = "pending_validation"
```

### 4-4. text_area 값 주입 방법

Streamlit에서 `st.text_area(key="af_contract_formula")` 값을 코드로 갱신하려면:
```python
st.session_state["af_contract_formula"] = new_formula   # 다음 렌더에 반영
st.rerun()
```
이 방법은 `st.session_state["af_formula_confirmed_text"]` 처리와 동일 패턴 → **기존 구조에서 작동 확인됨** ✅

---

## 5. validate_formula_with_samples() 재사용 가능성

| 기능 | 재사용 여부 | 비고 |
|------|------------|------|
| Level 1 구문 검사 | ✅ 그대로 | 한국어/설명문 차단 |
| Level 2 변수 검사 | ✅ 그대로 | AI 미지정 변수 자동 차단 |
| Level 3 test_cases 실행 | ✅ 그대로 | test_cases가 있을 때만 |
| dict formula 지원 | ✅ 그대로 | 다중 출력 자동 처리 |
| input_fields → schema 변환 | ✅ 기존 코드 재사용 | `{f: "number" for f in ...}` |

**추가 필요 사항**: 없음 — `validate_formula_with_samples()`는 변경 없이 AI 제안 formula에도 완전 적용 가능.

---

## 6. 계산기 유형별 AI Formula 자동제안 가능성

| 유형 | 대표 계산기 | AI Formula 제안 | 자동 검증 | 운영자 확인 |
|------|------------|----------------|----------|------------|
| A — 단순 산술 | 주휴수당, 연차수당, 3.3%세금 | ✅ 높음 | ✅ 가능 | 필수 |
| B — 다중 출력 | 4대보험 | ⚠️ 중간 (dict formula) | ✅ 가능 | 필수 |
| C — 조건부 capping | 연차 잔여일, 퇴직금 간이 | ⚠️ 중간 (min/max 포함) | ⚠️ 부분 | 필수 |
| D — 구간/테이블 | 실업급여, 연말정산 | ❌ 제한적 | ❌ 테이블 없음 | 필수 |

### 유형별 상세

**Type A (단순 산술)** — `legal_master.calculation_flow` 활용 최적:
- 주휴수당: `"주휴수당 = 1일 소정근로시간 × 시급"` → `weekly_hours / 5 * hourly_wage` 유추 가능
- AI → `validate_formula_with_samples()` → 운영자 확정 전 경로가 가장 안전하고 유용

**Type B (다중 출력)** — dict formula 생성:
- 4대보험: `{"national_pension": "salary * 0.045", "health_insurance": "salary * 0.03545"}`
- formula_engine dict 지원으로 Level 1/2 검증 가능
- 요율이 매년 변경되므로 운영자 확인 반드시 필요

**Type C (조건부 capping)**:
- formula_engine은 `min()`, `max()` 허용 → `15 + min(max(0, ...), 10)` 표현 가능
- AI가 cap 조건을 정확히 생성하기 어려움 → Level 3 test_cases 없으면 논리 오류 무감지
- 운영자 법령 원문 대조 필수

**Type D (구간/테이블)**:
- 실업급여: `소정급여일수 = 나이·피보험기간 테이블` → Python formula로 표현 불가
- 연말정산: CUSTOM_COMPUTE_SLUGS에 이미 포함 (`연말정산_환급액_계산기`) — formula 방식 미적용
- **CA-3에서 Type D는 AI Formula 제안 UI를 활성화하지 않는 것을 권장**

---

## 7. 위험요소 및 방어책

| 위험 | 설명 | 현재 방어 | CA-3 대응 |
|------|------|----------|----------|
| W-1 | AI가 없는 변수 사용 | ✅ Level 2 자동 차단 | 추가 불필요 |
| W-2 | AI가 한국어/설명문 반환 | ✅ Level 1 구문 오류 | prompt에 "Python 산술식만" 명시 |
| W-3 | AI가 예상치 못한 형식 반환 | ⚠️ `parse_json_lenient()` | suggest_formula prompt에 예시 포함 |
| W-4 | AI가 법적 조건 임의 추가 | ❌ 감지 불가 | 운영자 확인 필수 (HOLD-1) |
| W-5 | 검증 통과 but 법적 부정확 | ❌ Level 3만으로 한계 | test_cases 추가 권장 |
| W-6 | AI 제안이 기존 formula 덮어씀 | ❌ 현재 없음 | 확인 경고 또는 별도 표시 영역 |
| W-7 | Type D 계산기에 formula 제안 | ❌ 현재 없음 | category/slug 기반 제안 버튼 비활성 |

### 방어책 분류

| 방어책 | CA-3 필수 | CA-4 이연 |
|--------|----------|----------|
| W-1 Level 2 변수 검사 | 기존 완료 | — |
| W-2 prompt "Python 산술식만" | ✅ CA-3-2 | — |
| W-3 반환 형식 예시 포함 | ✅ CA-3-2 | — |
| W-4 운영자 확인 (HOLD-1 유지) | 기존 완료 | — |
| W-5 test_cases 추가 권장 UI | ⚠️ CA-3-3 (선택) | CA-4 |
| W-6 기존 formula 덮어씀 경고 | ✅ CA-3-3 | — |
| W-7 Type D 제안 버튼 비활성 | ✅ CA-3-3 | — |

---

## 8. Contract Instance 영향

### 8-1. 기존 YAML 호환성

```yaml
# 기존 docs/contract_schema/instances/*.yaml
formula_status: operator_confirmed   # 기존 값 — 변경 없음
```

`ai_suggested` 추가 시:
```yaml
formula_status: ai_suggested    # 신규 — 기존 YAML 미변경, 신규 Instance만 사용
```

**영향**: 없음. 기존 파일 수정 불필요. ✅

### 8-2. HOLD-1 영향

```python
# 현재 (CA-2-6-1)
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    # → HOLD-1 발동
```

`ai_suggested` → `"ai_suggested" != "operator_confirmed"` → HOLD-1 자동 발동 ✅

### 8-3. registry.yaml contract_source

```yaml
contract_source:
  formula_status: ai_suggested   # 새 값, 기존 파싱 로직 영향 없음
```

영향: 없음. `contract_source.formula_status` 는 값을 그대로 기록하는 구조. ✅

### 8-4. 기존 계산기 재저장 시 AI 상태 오염 위험

- 기존 계산기는 Mode B 경로 통하지 않는 한 Contract Instance가 없음
- `save_app()`: `app.get("_contract")` 가 None이면 Contract Instance 저장 안 함
- 재저장 시에도 ai_suggested 상태가 자동 삽입되는 경로 없음 ✅

---

## 9. CA-3 세부 단계 제안

### CA-3-1: ai_suggested 상태 인프라 (최소 변경)

**목표**: Dashboard에 `ai_suggested` 배지 표시만 추가

**수정 파일**:
- `dashboard.py`: `_fv_badge_map`에 `"ai_suggested": "🤖 AI 제안"` 1줄 추가

**테스트 추가**:
```python
def test_formula_status_ai_suggested_preserved():
    c = build_contract("x", "X", formula="a*2", formula_status="ai_suggested")
    assert c["formula_status"] == "ai_suggested"

def test_hold1_fires_for_ai_suggested():
    contract = build_contract("x", "X", formula="a*2", formula_status="ai_suggested")
    result = check_hold_rules(contract)
    assert "HOLD-1" in result["rules"]
```

**예상 수정 규모**: `dashboard.py` 1줄 + 테스트 2개

---

### CA-3-2: suggest_formula() 함수

**목표**: `modules/app_factory.py`에 formula 전용 AI 제안 함수 추가

**함수 시그니처**:
```python
def suggest_formula(cfg: dict, contract: dict) -> dict:
    """Contract 정보를 기반으로 AI가 formula를 제안한다.
    
    생성 규칙:
    - input_fields의 변수만 사용
    - Python 산술식 (str 또는 {출력키: 식} dict)
    - legal_master calculation_flow가 있으면 참조
    
    반환: {
        "formula": str | dict,
        "formula_status": "ai_suggested",
        "valid": bool,            # Level 1/2 검증 결과
        "message": str,           # 검증 메시지
        "sample_results": list,   # Level 3 (test_cases 있을 때)
    }
    """
```

**내부 구조**:
```python
def suggest_formula(cfg, contract):
    input_fields  = contract.get("input_fields") or []
    output_fields = contract.get("output_fields") or []
    desc          = contract.get("desc", "")
    legal_refs    = contract.get("legal_refs") or []
    
    # legal_master calculation_flow 조회
    lm = load_legal_master()
    calc_flows = []
    for ref in legal_refs:
        flow = (lm.get(ref) or {}).get("calculation_flow") or []
        calc_flows.extend(flow)
    
    # AI 제안 프롬프트 (경량 — Step 1 단순화)
    sys_suggest = (
        "너는 계산기 수식 설계자다. 아래 정보로 Python 산술 수식만 제안하라.\n"
        f"입력 변수: {input_fields}\n"
        f"출력 변수: {output_fields}\n"
        + (f"설명: {desc}\n" if desc else "")
        + (f"법령 계산 흐름(참고):\n" + "\n".join(f"  - {f}" for f in calc_flows) + "\n" if calc_flows else "")
        + "규칙:\n"
        "1. 입력 변수만 사용 (다른 변수 절대 금지)\n"
        "2. 단일 출력: 산술 표현식 문자열\n"
        "   복수 출력: {출력키: 산술식} JSON\n"
        "3. 대입문(=), 함수 정의, 미정의 함수 금지\n"
        "4. 허용 함수: min, max, round, abs, int, float\n"
        "5. 수식만 반환 — 설명문 없음\n"
        "   단일: \"hourly_wage * weekly_hours / 5\"\n"
        "   복수: {\"output1\": \"a + b\", \"output2\": \"a - b\"}"
    )
    u_suggest = f"계산기명: {contract.get('name', '')}"
    
    raw, _, _ = _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)
    # parse: JSON dict 또는 str
    try:
        formula = json.loads(raw.strip())
    except Exception:
        formula = raw.strip().strip('"\'')
    
    # validate
    schema = {f: "number" for f in input_fields}
    result = validate_formula_with_samples(formula, schema, contract.get("test_cases") or None)
    return {
        "formula": formula,
        "formula_status": "ai_suggested",
        "valid": result["valid"],
        "message": result["message"],
        "sample_results": result.get("sample_results", []),
    }
```

**예상 수정 규모**: `modules/app_factory.py` +35-40줄

---

### CA-3-3: Dashboard 연결

**목표**: `[🤖 AI Formula 제안]` 버튼 + 세션 스테이트 + 수정 감지

**추가 세션 키**:
- `af_formula_ai_suggested_text` — AI 제안 시점의 formula raw 텍스트 (수정 감지용)

**삽입 위치**: `_af_formula = st.text_area(...)` 이후 (배지 이전)

**수정 감지 추가 (기존 로직 직후)**:
```python
# AI 제안 수정 감지 (기존 confirmed 감지 직후 추가)
_fv_ai_raw = st.session_state.get("af_formula_ai_suggested_text", "")
if _fv_ai_raw and _fv_current_raw != _fv_ai_raw:
    st.session_state.pop("af_formula_ai_suggested_text", None)
    if st.session_state.get("af_contract"):
        st.session_state["af_contract"]["formula_status"] = "pending_validation"
```

**버튼 로직**:
```python
if st.button("🤖 AI Formula 제안", key="af_formula_ai_suggest"):
    if not _af_input_fields.strip() or not _af_output_fields.strip():
        st.error("입력/출력 필드를 먼저 입력해야 AI Formula를 제안받을 수 있습니다.")
    elif _af_formula.strip():
        if not st.session_state.get("_af_ai_suggest_override"):
            st.warning("기존 Formula가 있습니다. AI 제안으로 덮어씁니다. 다시 클릭하면 진행합니다.")
            st.session_state["_af_ai_suggest_override"] = True
        else:
            # 진행
            _do_suggest(...)
    else:
        _do_suggest(...)
```

**예상 수정 규모**: `dashboard.py` +60-80줄

---

## 10. 최소 수정 파일 / 예상 변경 범위

| 단계 | 수정 파일 | 예상 변경 줄수 | 위험도 |
|------|-----------|--------------|--------|
| CA-3-1 | `dashboard.py` | 1줄 | 거의 없음 |
| CA-3-1 | `tests/test_formula_contract.py` | +15줄 | 없음 |
| CA-3-2 | `modules/app_factory.py` | +35-40줄 (신규 함수) | 낮음 |
| CA-3-2 | `tests/test_app_factory_contract.py` | +30-40줄 | 낮음 |
| CA-3-3 | `dashboard.py` | +60-80줄 | 중간 |
| CA-3-3 | `tests/test_af_contract_dashboard.py` | +20-30줄 | 낮음 |

**총 예상 규모**: `modules/app_factory.py` 1함수 + `dashboard.py` +65~85줄 + 테스트 60-85줄

---

## 11. 기존 기능 영향도

| 기능 | 영향 | 이유 |
|------|------|------|
| Mode A (generate_app) | ✅ 없음 | CA-3는 Mode B 전용 |
| Mode B 기존 흐름 | ✅ 없음 | 새 버튼 추가, 기존 로직 비변경 |
| Contract Instance 저장 | ✅ 없음 | `formula_status` 값 추가만 |
| HOLD-1/2/3 | ✅ 없음 | `!= "operator_confirmed"` 유지 |
| [🔍 Formula 검증] / [✅ Formula 확정] | ✅ 없음 | 독립 버튼, 기존 동작 유지 |
| 기존 9개 계산기 | ✅ 없음 | Mode B 비사용 |
| 기존 Contract Instance YAML | ✅ 없음 | 파일 수정 불필요 |
| validate_formula_with_samples() | ✅ 없음 | 코드 변경 없이 재사용 |

---

## 12. Regression 위험

| 위험 항목 | 위험도 | 비고 |
|-----------|--------|------|
| HOLD-1 로직 변경 | ✅ 없음 | `!= "operator_confirmed"` 유지 |
| build_contract() 변경 | ✅ 없음 | 변경 없음 |
| validate_formula_with_samples() 변경 | ✅ 없음 | 변경 없음 |
| Dashboard 기존 버튼 동작 | ✅ 낮음 | 새 버튼 추가만, 기존 키 미변경 |
| text_area 값 주입 (st.session_state) | ⚠️ 중간 | Streamlit rerun 순서 주의 필요 |
| suggest_formula() 오류 | ⚠️ 중간 | AI 호출 실패 시 try/except 필수 |
| Type D 계산기에 버튼 표시 | ⚠️ 중간 | category 기반 비활성 로직 필요 |

---

## 13. CA-4 이후 이연 항목

| 항목 | 이유 |
|------|------|
| AI test_cases 자동 제안 | 별도 복잡도, CA-3 범위 초과 |
| AI formula 법적 정확성 자동 검증 | legal_master 연동 복잡, 법령 해석 필요 |
| ai_suggested 기반 자동 test_cases 생성 | CA-3에서는 기존 test_cases 입력 유지 |
| formula 버전 관리 (히스토리) | Contract Instance 구조 확장 필요 |
| Type D 계산기 AI 지원 | 별도 테이블/구간 데이터 구조 설계 필요 |
| multi-formula 제안 (복수 후보 제시) | UI 복잡도 증가, CA-3 스코프 초과 |

---

## 14. legal_master.calculation_flow 활용 가능성

| 법령 | calculation_flow 수준 | AI Formula 힌트 활용 |
|------|----------------------|-------------------|
| 주휴수당 (labor_standards_act_55) | ✅ 명확 (`주휴수당 = 1일 소정근로시간 × 시급`) | ✅ 높음 |
| 퇴직금 (worker_retirement_benefit_act_8) | ✅ 명확 (`퇴직금 = 평균임금 × 30 × 근속일수/365`) | ✅ 높음 |
| 연차수당 (labor_standards_act_60) | ✅ 명확 (`연차수당 = 일급 × 미사용일수`) | ✅ 높음 |
| 4대보험 (four_major_insurances) | ✅ 명확 (각 요율 명시) | ✅ 높음 (dict formula) |
| 실업급여 (employment_insurance_act_40) | ⚠️ 구간 의존 (`상한 매년 변경`) | ⚠️ 제한적 |
| 육아휴직 (employment_insurance_act_70) | ⚠️ 구간 의존 (`상·하한 매년 변경`) | ⚠️ 제한적 |
| 연말정산 (income_tax_act_137) | ❌ 복잡한 공제 테이블 | ❌ 불가 |

**결론**: `legal_master.calculation_flow`는 Type A/B 계산기에서 AI 힌트로 활용하면 formula 제안 품질이 크게 향상된다. Type D는 calculation_flow가 있어도 단순 formula 변환 불가.

---

## 15. 최종 권고

**CA-3 구현 착수 가능**

### 권장 Formula Lifecycle

```
not_generated
    ↓ [🤖 AI Formula 제안] 클릭
ai_suggested
    ↓ 수동 수정 시 → pending_validation
    ↓ [🔍 Formula 검증] 통과 시 → pending_validation
pending_validation
    ↓ [✅ Formula 확정] 클릭
operator_confirmed
    ↓ formula 수정 시
pending_validation (반복)
```

### CA-3 구현 권장 순서

| 단계 | 내용 | 수정 파일 |
|------|------|----------|
| CA-3-1 | `ai_suggested` 상태 인프라 (배지 1줄 + 테스트 2개) | `dashboard.py`, test |
| CA-3-2 | `suggest_formula()` 함수 구현 | `modules/app_factory.py` |
| CA-3-3 | Dashboard [🤖 AI Formula 제안] 버튼 연결 | `dashboard.py` |

### 예상 수정 파일

- `modules/app_factory.py` — `suggest_formula()` 신규 함수 (+40줄)
- `dashboard.py` — 버튼 + 배지 + 세션 스테이트 (+70줄)
- `tests/test_formula_contract.py` — `ai_suggested` lifecycle 테스트 (+15줄)
- `tests/test_app_factory_contract.py` — `suggest_formula()` 단위 테스트 (+35줄)

### Regression 위험

**낮음** — 기존 build_contract / check_hold_rules / validate_formula_with_samples / 기존 UI 버튼 모두 미변경. 신규 함수 추가 + 기존 배지 맵 1줄 + 새 버튼 독립 추가가 전부.

---

**핵심 원칙 재확인**:

> AI 제안 ≠ Formula 검증 ≠ 운영자 확정 ≠ 법적 정확성 보증

`ai_suggested` 상태는 HOLD-1이 자동 차단하며, 검증([🔍]) + 확정([✅]) 2단계를 통과해야만 `operator_confirmed`에 도달한다. AI는 초안 생성 보조 역할로만 제한된다.
