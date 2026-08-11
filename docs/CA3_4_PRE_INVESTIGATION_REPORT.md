# CA-3-4 사전조사 보고서 — Dashboard suggest_formula() 연결점

> 조사 기준일: 2026-08-10  
> 원칙: 코드 수정 0건 / 조사 전용  
> 기준: CA-3-3 PASS (530 PASS / 1 known FAIL)

---

## 1. 현재 Dashboard Formula Lifecycle

### 1-1. Mode B 전체 구조 (실제 코드 기준)

```
dashboard.py line 2224:
  with st.expander("📋 Contract 확정 스펙 입력 ...")

  line 2232: _af_slug_pre    (key="af_contract_slug_pre")
  line 2236: _af_input_fields (key="af_contract_input_fields")
  line 2240: _af_output_fields (key="af_contract_output_fields")
  line 2244: _af_formula text_area (key="af_contract_formula")
             ↑ [🤖 AI Formula 제안] 버튼 삽입 위치 (line 2249 직후)
  line 2250: formula_status 배지 (CA-2-6-2 + CA-3-1)
  line 2268: _af_test_cases  (key="af_contract_test_cases")
  line 2275: Formula 수정 감지 — operator_confirmed 무효화 (CA-2-6-2)
  line 2284: ai_suggested 수정 감지 (CA-3-1)
  line 2300: [🔍 Formula 검증] 버튼
  line 2335: [✅ Formula 확정] 버튼
  line 2368: [📋 Contract 기반 생성] 버튼 → build_contract() → generate_app_with_contract()
```

### 1-2. Formula lifecycle 상태 전이 (현재 코드)

```
not_generated
    ↓ formula text_area에 입력
pending_validation (배지 상태 갱신)
    ↓ [🔍 Formula 검증] 클릭 (line 2300)
pending_validation (af_contract.formula_status = "pending_validation")
    ↓ [✅ Formula 확정] 클릭 (line 2335, disabled=not _fv_passed)
operator_confirmed
    ↓ formula 수정
pending_validation (line 2278-2282)
```

### 1-3. Session state 전체 목록

| 키 | 역할 | 생성 위치 |
|----|------|----------|
| `af_contract` | build_contract() 결과 dict | line 2423 |
| `af_formula_confirmed_text` | [✅ 확정] 시 formula raw text 저장 | line 2341 |
| `af_formula_validation` | [🔍 검증] 결과 dict | line 2324 |
| `af_formula_ai_suggested_text` | CA-3-1 — AI 제안 추적 | CA-3-1 수정 감지 (line 2285) |
| `af_contract_formula` | formula text_area widget value | Streamlit widget key |
| `af_contract_input_fields` | input_fields text_input value | Streamlit widget key |
| `af_contract_output_fields` | output_fields text_input value | Streamlit widget key |
| `af_contract_slug_pre` | slug text_input value | Streamlit widget key |
| `af_contract_test_cases` | test_cases text_area value | Streamlit widget key |
| `_af_ai_suggest_override` | CA-3-4 신규 — 2-click 확인 플래그 | CA-3-4에서 추가 예정 |

---

## 2. suggest_formula() 연결 후보 위치

### 2-1. 최적 삽입 위치: line 2249 직후, 배지(line 2250) 이전

**이유**:
1. `_af_input_fields` (line 2236), `_af_output_fields` (line 2240) 가 이미 렌더됨 → 필수 입력 확보 ✅
2. `_af_formula` text_area (line 2244) 직후 → 클릭 시 결과가 같은 위치에 주입 → 자연스러운 UX ✅
3. 배지 이전 → AI 제안 후 즉시 "🔵 AI 제안" 배지 표시 ✅
4. 검증/확정 버튼(line 2300, 2335) 이전 → AI 제안 → 검증 → 확정 흐름이 위에서 아래로 ✅

### 2-2. 삽입 후 UI 구조

```
_af_formula text_area (line 2244~2249)
    ↓
[🤖 AI Formula 제안] 버튼  ← NEW (CA-3-4)
    ↓
formula_status 배지 (line 2250~2267)
    ↓
_af_test_cases text_area (line 2268~2273)
    ↓
수정 감지 블록 (line 2275~2290)
    ↓
[🔍 Formula 검증] / [✅ Formula 확정] (line 2292~2366)
    ↓
[📋 Contract 기반 생성] (line 2368)
```

---

## 3. 필요한 입력 데이터 확보 시점

| suggest_formula() 인자 | 소스 | 확보 시점 | 가용 여부 |
|----------------------|------|----------|----------|
| `cfg` | `cfg` 변수 | App Factory section 진입 시 | ✅ 항상 |
| `name` | `af_name` (line 2156) | Mode B expander 이전 | ✅ 항상 |
| `category` | `af_cat` (line 2157) | Mode B expander 이전 | ✅ 항상 |
| `desc` | `af_desc` (line 2158) | Mode B expander 이전 | ✅ 항상 |
| `input_fields` | `_af_input_fields` (line 2236) | line 2249 시점에 ✅ | ✅ 확보됨 |
| `output_fields` | `_af_output_fields` (line 2240) | line 2249 시점에 ✅ | ✅ 확보됨 |
| `slug` | `_af_slug_pre` (line 2232) | line 2249 시점에 ✅ | ✅ Type D 차단용 |
| `legal_refs` | **Dashboard에 입력 UI 없음** | — | ⚠️ 미구현 (Gap) |
| `calculation_flow` | legal_refs에서 자동 조회 | — | ⚠️ legal_refs 없으면 None |

### legal_refs 미구현 Gap 처리 방안

`legal_refs=[]`로 전달 → `suggest_formula()` 내부에서 calculation_flow 자동 조회 생략 → AI가 `name`/`input_fields`/`output_fields`/`desc`만으로 formula 제안.

**영향**: Type A/B 계산기에서 calculation_flow 힌트 없이도 AI가 formula를 추정할 수 있음. 단, 법령 정확성 보증 없음 → 운영자 확인이 더욱 중요.

**CA-3-4 결정**: legal_refs UI 없이 구현 → `legal_refs=None` 전달. 향후 CA-3-5 또는 CA-4에서 legal_refs 입력 UI 추가 가능.

---

## 4. AI 제안 UI 흐름

### 4-1. 정상 흐름 (기존 formula 없음)

```
[🤖 AI Formula 제안] 클릭 (1차)
    ↓ _af_input_fields 없음? → st.error() 중단
    ↓ _af_output_fields 없음? → st.error() 중단
    ↓
suggest_formula(cfg, name, input_fields, output_fields, slug=slug)
    ↓ spinner 표시
    ↓ 성공 (result["success"] is True)
        → st.session_state["af_contract_formula"] = formula_str
        → st.session_state["af_formula_ai_suggested_text"] = formula_str
        → af_contract["formula_status"] = "ai_suggested" (if af_contract exists)
        → warnings 있으면 st.warning()
        → st.info("반드시 검토 후 [🔍 Formula 검증]을 실행하세요.")
        → st.rerun()
    ↓ 실패 (result["success"] is False)
        → 기존 session state 유지
        → st.error(result["reason"])
        → warnings 있으면 st.warning()
        → rerun 없음
```

### 4-2. 2-click 패턴 (기존 formula 있음)

```
[🤖 AI Formula 제안] 클릭 (1차)
    ↓ _af_formula.strip() 존재 AND _af_ai_suggest_override 없음
    → st.warning("⚠️ 기존 Formula가 있습니다. 다시 클릭하면 AI 제안으로 교체됩니다.")
    → st.session_state["_af_ai_suggest_override"] = True
    → (rerun 없음 — 경고만 표시)

[🤖 AI Formula 제안] 클릭 (2차)
    ↓ _af_ai_suggest_override == True → 진행
    → st.session_state.pop("_af_ai_suggest_override", None)
    → suggest_formula() 호출 → 정상 흐름
```

**Streamlit 작동 원리**: `st.button()` 클릭은 자동으로 rerun을 유발. 1차 클릭 시 `_af_ai_suggest_override=True` 설정 후 페이지 재렌더됨. 2차 클릭 시 override flag가 True → 진행. 이 패턴은 Streamlit의 session_state 기반 다단계 확인에서 표준적으로 동작한다.

### 4-3. AI 제안 완료 후 전체 lifecycle

```
AI 제안 성공
    ↓
formula text_area = AI 제안값
formula_status 배지 = "🔵 AI 제안"
af_formula_ai_suggested_text = AI 제안값
    ↓
운영자 검토 (수정 가능)
    ↓ (수정 시)
CA-3-1 수정 감지 → pending_validation 복귀
    ↓ (또는 수정 없이)
[🔍 Formula 검증] 클릭
    → af_contract.formula_status = "pending_validation"
    ↓ 통과 시 _fv_passed=True
[✅ Formula 확정] 활성화
    → af_contract.formula_status = "operator_confirmed"
```

---

## 5. 기존 Formula 덮어쓰기 방어안 (R-6)

### 5-1. 방어 구현 설계

```python
# 삽입 위치: line 2249 직후
_af_suggest_disabled = (
    not (_af_input_fields or "").strip()
    or not (_af_output_fields or "").strip()
)
if st.button(
    "🤖 AI Formula 제안",
    key="af_formula_ai_suggest",
    disabled=_af_suggest_disabled,
    help="..." if _af_suggest_disabled else "...",
):
    _existing_formula = (_af_formula or "").strip()
    if _existing_formula and not st.session_state.get("_af_ai_suggest_override"):
        # 1차 클릭 — 경고
        st.warning("⚠️ 기존 Formula가 있습니다. 다시 클릭하면 AI 제안으로 교체됩니다.")
        st.session_state["_af_ai_suggest_override"] = True
    else:
        # 2차 클릭 또는 기존 formula 없음 — 실행
        st.session_state.pop("_af_ai_suggest_override", None)
        # suggest_formula() 실제 호출 로직
```

### 5-2. Override 플래그 자동 해제 조건

- 2차 클릭에서 진행 시 → `pop("_af_ai_suggest_override")`
- 기존 formula가 삭제됨 → 1차 클릭에서 `_existing_formula.strip()` = False → 직접 실행
- 폐기 버튼 클릭 → `AF_SESSION_DISCARD_KEYS` (CA-3-4에서 추가 예정)

---

## 6. string/dict formula 처리안

### 6-1. suggest_formula() 반환값

```python
# Type A
result["formula"] = "hourly_wage * weekly_hours / 5"   # str

# Type B
result["formula"] = {"national_pension": "monthly_salary * 0.045", ...}  # dict
```

### 6-2. text_area 주입 방법

```python
_sf_formula = result["formula"]
_sf_formula_str = (
    json.dumps(_sf_formula, ensure_ascii=False, indent=2)
    if isinstance(_sf_formula, dict)
    else str(_sf_formula)
)
st.session_state["af_contract_formula"] = _sf_formula_str
```

### 6-3. build_contract() 전달 (기존 코드 line 2384-2390)

```python
_formula_raw = (_af_formula or "").strip()
if _formula_raw:
    try:
        _formula_val = json.loads(_formula_raw)  # dict → 복원
    except Exception:
        _formula_val = _formula_raw              # str → 그대로
```

**dict formula 처리 흐름**:
```
suggest_formula() → {"k": "expr"}
    ↓ json.dumps(indent=2) → text_area에 표시
    ↓ 운영자 검토
    ↓ json.loads() in build_contract() 블록
    → formula={"k": "expr"} dict로 복원
    → build_contract(formula={"k": "expr"})
```

**기존 코드가 이미 이 패턴을 지원함** ✅ — 별도 처리 불필요.

**주의**: `json.dumps(ensure_ascii=False, indent=2)` 사용 시 multi-line JSON이 text_area에 표시됨. 이는 가독성 측면에서 좋으나, `_fv_current_raw`와 `_fv_ai_suggested_text` 비교 시 whitespace 차이 가능.

→ **방어책**: `json.dumps(..., indent=None)` 또는 compact JSON으로 저장하여 비교 일관성 확보. 또는 비교 시 `json.loads()` 후 비교.

---

## 7. 실패 처리안

`suggest_formula()` 실패 조건:
- `result["success"] is False`
- `result["status"] == "not_generated"`

실패 시 Dashboard 처리:
```python
if _suggest_result["success"]:
    # ... session state 변경 + rerun
else:
    st.error(f"❌ AI Formula 제안 실패: {_suggest_result['reason']}")
    for _w in (_suggest_result.get("warnings") or []):
        st.warning(f"⚠️ {_w}")
    # 아무 session state도 변경하지 않음
    # st.rerun() 없음 → 현재 상태 유지
```

**검증**:
- `af_contract_formula` 변경 없음 → 기존 formula 유지 ✅
- `af_formula_ai_suggested_text` 변경 없음 ✅
- `af_contract.formula_status` 변경 없음 ✅
- Contract 생성 흐름 중단 없음 → [📋 Contract 기반 생성] 버튼 계속 사용 가능 ✅

---

## 8. Session State 영향

### 8-1. CA-3-4에서 신규 추가되는 session key

| 키 | 역할 | 생명주기 |
|----|------|----------|
| `_af_ai_suggest_override` | 2-click 확인 플래그 | 2차 클릭 후 또는 폐기 시 해제 |

`af_formula_ai_suggested_text`는 CA-3-1에서 이미 구현됨 — CA-3-4에서 추가 없음.

### 8-2. AF_SESSION_DISCARD_KEYS 갱신 필요

현재 `AF_SESSION_DISCARD_KEYS` (app_factory.py line 42-61)에 누락된 키:

| 키 | 현재 상태 | CA-3-4 필요 조치 |
|----|----------|----------------|
| `af_formula_confirmed_text` | 미포함 (기존 gap) | CA-3-4에서 추가 권장 |
| `af_formula_validation` | 미포함 (기존 gap) | CA-3-4에서 추가 권장 |
| `af_formula_ai_suggested_text` | 미포함 (CA-3-1 gap) | CA-3-4에서 추가 |
| `_af_ai_suggest_override` | 신규 | CA-3-4에서 추가 |

→ `AF_SESSION_DISCARD_KEYS` 확장이 필요하다. 그러나 이 변경은 `modules/app_factory.py` 수정을 수반한다. 폐기 시 해당 키들이 남아있어도 다음 렌더 사이클에서 자연스럽게 처리되므로 **CA-3-4 필수가 아닌 권장** 수준.

---

## 9. 기존 Validation/Confirm Lifecycle 영향

### 9-1. AI 제안 후 수정 감지 충돌 분석

**시나리오**: 운영자가 `operator_confirmed` 상태에서 AI 제안 클릭

```python
# AI 제안 클릭 → st.session_state["af_contract_formula"] = new_formula + st.rerun()
# 재렌더 시:

_fv_confirmed_raw = "기존_확정_formula"   # af_formula_confirmed_text 값
_fv_current_raw   = "ai_제안_formula"    # text_area 새 값

if _fv_confirmed_raw and _fv_current_raw != _fv_confirmed_raw:
    # → operator_confirmed 무효화 → pending_validation
```

**결론**: AI가 다른 formula를 제안하면 기존 `operator_confirmed` 상태가 자동 무효화된다. **이것이 올바른 동작이다** ✅

**시나리오**: AI 제안 formula가 기존 확정 formula와 동일한 경우

→ `_fv_current_raw == _fv_confirmed_raw` → 수정 감지 미발동 → `operator_confirmed` 유지.

→ 이 경우도 올바른 동작이다. AI가 같은 formula를 제안하면 기존 확정 상태를 해제할 이유가 없음.

### 9-2. ai_suggested 배지 표시 충돌 분석

배지 로직 (line 2250-2267):
```python
_fv_badge_status = (st.session_state.get("af_contract") or {}).get("formula_status")
if _fv_badge_status is None:
    # af_contract가 없을 때 text_area 내용으로 추정
    ...
```

AI 제안 후:
- `af_contract.formula_status = "ai_suggested"` → 배지 = "🔵 AI 제안" ✅
- `af_contract`가 없는 경우 (아직 build_contract() 미호출): `_fv_badge_status = None` → 배지 로직이 text_area 내용으로 추정 → `pending_validation` (내용 있으므로)

**Gap**: `af_contract`가 없는 상태에서 AI 제안 성공 시 배지가 "🟡 검증 대기"로 표시될 수 있음.

→ **방어책**: AI 제안 성공 직후 `af_contract`가 없어도 배지용 별도 session key (`af_formula_ai_badge_text`) 관리 또는 `af_contract`가 없을 때 `af_formula_ai_suggested_text` 기반으로 배지 판단 추가.

→ **CA-3-4 결정**: 복잡도 최소화를 위해 `af_formula_ai_suggested_text`가 있을 때 배지를 "🔵 AI 제안"으로 표시하는 fallback 로직 1줄 추가.

### 9-3. [🔍 Formula 검증] 버튼 (line 2300) 영향

AI 제안 후 `_af_formula` text_area에 AI formula가 표시됨 → [🔍 Formula 검증] 클릭 시 해당 formula 검증 → **기존 로직 그대로 작동** ✅

`af_contract.formula_status = "pending_validation"` 설정 (line 2332) → 배지 변경 → ✅

### 9-4. [✅ Formula 확정] 버튼 (line 2335) 영향

`disabled=not _fv_passed` 기존 로직 → AI 제안 후 검증 없이는 비활성 ✅

검증 통과 후 클릭 → `af_formula_confirmed_text = current_raw`, `formula_status = "operator_confirmed"` → ✅

---

## 10. Mode A 완전 분리 확인

`[🤖 AI Formula 제안]` 버튼은 `with st.expander("📋 Contract 확정 스펙 입력...")` 블록 **내부**에만 존재.

Mode A 생성 경로:
- Dashboard의 별도 버튼 → `AF.generate_app(cfg, ...)` 직접 호출
- Contract Builder expander와 완전히 다른 코드 블록

**Mode A 경로에 suggest_formula() 코드 없음** ✅

---

## 11. Blog/WordPress Pipeline 분리 확인

| 시스템 | 데이터 소스 | suggest_formula() 접촉 여부 |
|--------|-----------|--------------------------|
| Blog pipeline (`PIPE.run_once(cfg)`) | Registry v3 → DB | ❌ 없음 |
| WordPress publisher | Registry v3 → DB | ❌ 없음 |
| Content pipeline | `modules/content_pipeline/` | ❌ 없음 |
| SEO pipeline | Registry v3 | ❌ 없음 |

Dashboard session_state는 블로그/WordPress 파이프라인이 접근하지 않는다. suggest_formula() Dashboard 연결은 **Contract Builder expander 내 session_state 변경만** 발생시킨다.

**Blog/WordPress pipeline 오염 없음** ✅

---

## 12. 예상 수정 파일 및 줄 수

### 12-1. 주 수정 파일

**`dashboard.py` 단일 파일** — CA-3-4 가능.

| 변경 위치 | 내용 | 예상 줄 수 |
|----------|------|-----------|
| line 2249 직후 | [🤖 AI Formula 제안] 버튼 + 처리 로직 | +45~55줄 |
| line 2250~2267 배지 로직 | `af_formula_ai_suggested_text` fallback 1줄 추가 | +3줄 |

**총 예상**: `dashboard.py` +50~60줄

### 12-2. 선택적 수정 파일

**`modules/app_factory.py`** — AF_SESSION_DISCARD_KEYS 확장 (권장, 필수 아님):

```python
AF_SESSION_DISCARD_KEYS: tuple[str, ...] = (
    ...기존 키들...,
    # CA-3-1/CA-3-4 추가
    "af_formula_confirmed_text",
    "af_formula_validation",
    "af_formula_ai_suggested_text",
    "_af_ai_suggest_override",
)
```

예상 줄 수: +4줄

### 12-3. 테스트 파일

`tests/test_af_contract_dashboard.py` 또는 `tests/test_suggest_formula.py` +3~5개 테스트

---

## 13. 테스트 계획

### 13-1. 추가할 테스트

| 테스트 | 내용 |
|--------|------|
| `test_suggest_formula_button_disabled_without_fields` | input/output fields 없으면 비활성 판정 |
| `test_suggest_formula_success_updates_session_state` | 성공 시 af_contract_formula / af_formula_ai_suggested_text 업데이트 |
| `test_suggest_formula_failure_keeps_existing_formula` | 실패 시 기존 formula 유지 |
| `test_suggest_formula_overrides_operator_confirmed` | 기존 확정 formula와 다른 AI 제안 → 수정 감지 → pending_validation |
| `test_two_click_override_pattern` | 2-click 패턴 동작 확인 |

### 13-2. 테스트 파일 위치

기존 `tests/test_af_contract_dashboard.py`에 추가 (Dashboard 통합 테스트 패턴 일치).

mock 방식: `monkeypatch.setattr("modules.app_factory.suggest_formula", ...)`

---

## 14. 위험요소 및 방어책

| 위험 | 설명 | 방어 | 구현 위치 |
|------|------|------|----------|
| R-6 기존 Formula 덮어쓰기 | AI 제안이 운영자 입력 formula를 즉시 교체 | 2-click override 패턴 | CA-3-4 구현 |
| R-7 AI 호출 실패 | suggest_formula() 예외 전파 | 이미 CA-3-3에서 처리 (try/except → _fail) | CA-3-3 완료 ✅ |
| R-8 string/dict formula 혼용 | dict formula를 str로 변환 시 build_contract() 문제 | json.dumps() → json.loads() 기존 패턴 적용 | CA-3-4 구현 |
| Session state stale value | 폐기 후 `af_formula_ai_suggested_text` 잔존 | AF_SESSION_DISCARD_KEYS 확장 | CA-3-4 (권장) |
| operator_confirmed 덮어쓰기 | AI가 다른 formula 제안 시 기존 확정 무효화 | 기존 수정 감지 로직이 자동 처리 | 기존 로직 ✅ |
| Mode A 오염 | suggest_formula 버튼이 Mode A에 노출 | expander 내부에만 위치 | 구조적 방어 ✅ |
| blog/WordPress 오염 | suggest_formula가 pipeline에 연결 | 완전히 다른 코드 경로 | 구조적 방어 ✅ |
| 배지 표시 누락 | af_contract 없을 때 ai_suggested 배지 미표시 | af_formula_ai_suggested_text fallback | CA-3-4 구현 (+3줄) |
| JSON indent whitespace 비교 불일치 | json.dumps(indent=2)로 저장 시 비교 오차 | compact JSON 또는 파싱 후 비교 | CA-3-4 구현 주의 |

---

## 15. 구현 권장 순서

```
CA-3-4-A: dashboard.py에 [🤖 AI Formula 제안] 버튼 추가
    - line 2249 직후
    - 비활성 조건: input_fields or output_fields 없음
    - suggest_formula() 호출 (spinner)
    - 성공: session state 업데이트 + rerun
    - 실패: error 표시만

CA-3-4-B: 배지 fallback 로직 추가 (+3줄)
    - af_formula_ai_suggested_text 있으면 "ai_suggested" 배지 강제

CA-3-4-C: AF_SESSION_DISCARD_KEYS 확장 (권장)
    - modules/app_factory.py +4줄
    - af_formula_confirmed_text, af_formula_validation,
      af_formula_ai_suggested_text, _af_ai_suggest_override

CA-3-4-D: 테스트 추가
    - test_af_contract_dashboard.py 또는 신규 파일
    - 5개 테스트 (monkeypatch suggest_formula)
```

---

## 16. 최종 판정

**PASS — 구현 가능. dashboard.py 단일 파일로 완성 가능.**

**근거**:
- suggest_formula()가 CA-3-3에서 독립 함수로 완성됨 ✅
- Dashboard 삽입 위치 명확 (line 2249 직후) ✅
- 기존 session state 구조와 충돌 없음 (CA-3-1에서 ai_suggested 감지 로직 기준비) ✅
- string/dict formula 처리: 기존 json.loads() 패턴으로 해결 ✅
- 2-click override 패턴: Streamlit session_state 기반으로 안정적 구현 가능 ✅
- Mode A / blog / WordPress 완전 분리 ✅

**주의 사항**:
1. JSON compact 직렬화 사용 (indent=None) — whitespace 비교 오차 방지
2. 배지 fallback 3줄 필요 — af_contract 없을 때 ai_suggested 표시
3. AF_SESSION_DISCARD_KEYS 확장 권장 (ca-3-4에서 함께 처리)

**예상 수정 파일**:
- `dashboard.py` — +50~60줄
- `modules/app_factory.py` — +4줄 (AF_SESSION_DISCARD_KEYS, 선택)
- `tests/test_af_contract_dashboard.py` — +5개 테스트
