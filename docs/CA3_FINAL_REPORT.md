# CA-3 최종 보고서 — AI Formula Contract System

**날짜**: 2026-08-11  
**작성 기준**: CA-3-F 최종검증 (코드 수정 0건)  
**최종 판정**: CA-3-F = **PASS** / CA-3 = **COMPLETE**

---

## 1. CA-3 전체 단계 요약

| 단계 | 제목 | 판정 | 핵심 산출물 |
|------|------|------|------------|
| CA-3-0 | 사전조사 | PASS | `docs/CA3_0_PRE_INVESTIGATION_REPORT.md` |
| CA-3-1 | ai_suggested 상태 감지 | PASS | `dashboard.py` ai_suggested 수정 감지 로직 |
| CA-3-2 | legal_master 연동 기반 | PASS | `suggest_formula()` 시그니처 + legal_master 조회 |
| CA-3-3 | Type D 차단 + suggest_formula 완전 구현 | PASS | `app_factory.py` suggest_formula() 전체 + `docs/CA3_3_FINAL_REPORT.md` |
| CA-3-4 | Dashboard AI Formula 제안 버튼 연결 | PASS | `dashboard.py` 버튼 + badge fallback + 4 DISCARD_KEYS |
| CA-3-5 | E2E + Regression 최종검증 | PASS | `tests/test_e2e_ca35.py` (17개) |
| **CA-3-F** | **최종 종합검증** | **PASS** | `docs/CA3_FINAL_REPORT.md` (이 파일) |

---

## 2. CA-3-1 ~ CA-3-5 결과

### CA-3-1: ai_suggested 상태 감지

**구현 위치**: `dashboard.py` lines 2347-2353

```python
# CA-3-1: ai_suggested 수정 감지 → pending_validation 복귀
_fv_ai_suggested_raw = st.session_state.get("af_formula_ai_suggested_text", "")
if _fv_ai_suggested_raw and _fv_current_raw != _fv_ai_suggested_raw:
    st.session_state.pop("af_formula_ai_suggested_text", None)
    st.session_state.pop("af_formula_validation", None)
    if st.session_state.get("af_contract"):
        st.session_state["af_contract"]["formula_status"] = "pending_validation"
```

**결과**: 운영자가 AI 제안 formula를 수정하면 즉시 `pending_validation`으로 복귀 → `operator_confirmed` 자동 승격 방지.

---

### CA-3-2/CA-3-3: suggest_formula() 완전 구현

**구현 위치**: `modules/app_factory.py` line 477

- **legal_master 연동**: `legal_refs` + `calc_flows` 없으면 `load_legal_master()` 자동 조회
- **Type D 차단**: CUSTOM_COMPUTE_SLUGS + `_is_type_d_flow()` (2단계)
- **R-1/R-2/R-7/R-8**: 입력 변수 검증, dict 출력 키 검증, AI 예외 처리, JSON/raw 폴백
- **1회 AI 호출**: `max_tokens=300`, "orchestrator" role

---

### CA-3-4: Dashboard 버튼 연결

**구현 위치**: `dashboard.py` line 2251 (`🤖 AI Formula 제안` 버튼)

추가 사항:
- **R-6**: 2-click override (`_af_ai_suggest_override` flag)
- **Badge fallback**: `af_contract=None` 상태에서도 `ai_suggested` 배지 표시
- **4 DISCARD_KEYS 추가**: `af_formula_ai_suggested_text`, `_af_ai_suggest_override`, `af_formula_confirmed_text`, `af_formula_validation`
- **dict formula 직렬화**: `json.dumps(ensure_ascii=False)` compact → text_area → `json.loads()` round-trip

---

### CA-3-5: E2E 검증

**파일**: `tests/test_e2e_ca35.py` (17개 테스트)

| E2E 케이스 | 검증 내용 |
|-----------|----------|
| E2E-NEW-1 | AI 제안 → build_contract(None) → pending_validation (자동 확정 방지) |
| E2E-NEW-2 | operator_confirmed → Contract 상태 보존 + HOLD-1 미발동 |
| E2E-NEW-3 | dict formula Round-trip (Contract Instance YAML) |
| E2E-NEW-4 | delete 경로 → Contract Instance 완전 제거 |
| E2E-NEW-5 | Dashboard Discard → CA-3-4 session state 소거 |

**CA-3-5 Regression**: 554 PASS / 1 FAIL (기준 달성)

---

## 3. CA-3-F 최종 검증 결과

### 검증 방법

| 검증 항목 | 방법 |
|---------|------|
| Formula Lifecycle HOLD-1 | `python -c "..."` 직접 실행 |
| R-1/R-2/Type D | `python -c "..."` 직접 실행 |
| DISCARD_KEYS | `python -c "..."` 직접 실행 |
| Regression | `python -m pytest tests/ --tb=short -q` |
| known FAIL 내용 확인 | `python -m pytest production_validation_test.py -v --tb=long` |
| Git 보호 | `git status --short`, `git diff --name-only HEAD -- docs/registry/` |
| Registry 변경 내용 | `git diff HEAD -- docs/registry/*.yaml` 상세 분석 |

### 검증 결과 요약

| 항목 | 기준 | 실제 | 판정 |
|------|------|------|------|
| PASS 수 | ≥ 554 | 554 | ✅ |
| FAIL 수 | 1 (known) | 1 | ✅ |
| 신규 FAIL | 0 | 0 | ✅ |
| CA-3 체크리스트 | 23/23 | 23/23 | ✅ |
| CA-3 전용 84테스트 | 84/84 | 84/84 | ✅ |
| _secret_replace2.txt 미포함 | 미커밋 | 미커밋(untracked) | ✅ |
| 신규 Gap | 없음 | 없음 | ✅ |

---

## 4. Formula Lifecycle 검증

### 상태 전이 및 HOLD-1 발동 확인 (실행 결과)

```
HOLD-1 status check:
not_generated         -> not_generated    | HOLD-1: True   ✅
pending_validation    -> pending_validation| HOLD-1: True   ✅
operator_confirmed    -> operator_confirmed| HOLD-1: False  ✅
ai_suggested->None->auto -> pending_validation | HOLD-1: True ✅
```

### 핵심 설계 결정 확인

- **`ai_suggested` → `operator_confirmed` 직접 전이 없음**: AI 제안 후 build_contract(formula_status=None) → `pending_validation` 자동 도출 → HOLD-1 발동. 자동 승격 경로 없음.
- **`ai_suggested`는 Contract Instance 미저장**: Dashboard tracking only. YAML 파일에는 `pending_validation` 또는 `operator_confirmed`만 저장.
- **formula 수정 시 자동 복귀**: `operator_confirmed` 또는 `ai_suggested` 상태에서 text_area 수정 감지 → `pending_validation` 복귀.

### 상태 전이 다이어그램 (최종)

```
not_generated
    │
    ├─(suggest_formula 성공)─→ [ai_suggested] ←─ Dashboard tracking only
    │                               │
    │                               ├─(운영자 수정)─────────────────────────┐
    │                               └─(build_contract formula_status=None)─→ pending_validation
    │                                                                            │
    ├─(수동 입력)─────────────────────────────────────────────────────────────→ │
    │                                                                            │
    │                                                         [✅ Formula 확정] ↓
    │                                                         operator_confirmed
    │                                                                  │
    │                                            (formula 수정 감지)──→ pending_validation
    └─────────────────────────────────────────────────────────────────┘
```

---

## 5. HOLD-1/2/3 영향

### HOLD-1 (formula 미확정)

```python
# app_factory.py:357
if contract.get("formula_status", "not_generated") != "operator_confirmed":
    rules.append("HOLD-1")
```

| 상태 | HOLD-1 |
|------|--------|
| not_generated | 발동 |
| ai_suggested (Dashboard → build_contract → pending) | 발동 |
| pending_validation | 발동 |
| **operator_confirmed** | **미발동** |

### HOLD-2 (critical category + test_cases 없음)

```python
# app_factory.py:366
if (contract.get("test_cases_status") == "not_generated"
        and contract.get("category") in CRITICAL_CATEGORIES):
    rules.append("HOLD-2")
```

CRITICAL_CATEGORIES: `세금/세법`, `노동/고용법`, `복지/사회보험`, `병역/공무`, `세금/정부혜택`, `노무/급여`, `고용/보험`, `노무/급여/보험`

### HOLD-3 (legal_refs confidence=medium)

```python
# app_factory.py:374
medium_refs = [ref for ref in legal_refs if (lm.get(ref) or {}).get("confidence") == "medium"]
if medium_refs:
    rules.append("HOLD-3")
```

### Soft Gate 설계

`check_hold_rules()` 반환: `{"held": bool, "rules": [...], "messages": [...]}`.  
**Soft Gate — Hard Block 아님**: 경고 표시만. 운영자가 확인 후 생성 진행 여부 직접 결정. 자동 생성 차단 없음.

---

## 6. suggest_formula() 방어 로직

### R-1: 입력 변수 검증 (실행 결과)

```
R-1 unknown_var blocked: True | input_schema에 없는 변수: unknown_var  ✅
```

구현: `validate_formula(parsed_formula, {f:"number" for f in input_fields})` → AST walk → `ast.Name` not in allowed → 실패

### R-2: dict formula output key 검증 (실행 결과)

```
R-2 extra keys: {'extra_key'} | blocked: True  ✅
```

구현: `extra = actual_keys - expected_keys` → 비어있지 않으면 `_fail()`

### R-6: 2-click 덮어쓰기 확인

```python
_override_set = st.session_state.pop("_af_ai_suggest_override", False)
if _existing_formula and not _override_set:
    st.warning("⚠️ 기존 Formula가 있습니다...")
    st.session_state["_af_ai_suggest_override"] = True
else:
    # AI 호출
```

`pop()` 원자 연산으로 Streamlit rerun 모델에서 플래그 소진 보장.

### R-7: AI 호출 예외 처리

```python
try:
    raw_text, _, _ = _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)
except Exception as exc:
    return _fail(f"AI 호출 실패: {exc}", [str(exc)])
```

AI 실패 시 `_fail()` dict 반환 → Dashboard에서 `st.error()` 표시, 기존 formula 보존.

### R-8: JSON/raw string 폴백

```python
try:
    obj = parse_json_lenient(raw_text)
    parsed_formula = obj.get("formula") if isinstance(obj, dict) else str(obj)
except Exception:
    parsed_formula = raw_text.strip().strip("\"'")  # raw string 폴백
```

폴백 이후에도 R-1이 실행되어 안전성 2중 보장.

### Type D 차단 확인 (실행 결과)

```
CUSTOM_COMPUTE_SLUGS: ['연말정산_환급액_계산기', '육아휴직_급여_계산기']
Type D flow (별표): True   → 차단 ✅
Type A flow (단순): False  → 허용 ✅
```

**AI API 호출 발생 전 차단** 확인: CUSTOM_COMPUTE_SLUGS 차단은 `_chat()` 호출 전 실행(line 525). `_is_type_d_flow()` 차단도 `_chat()` 호출 전 실행(line 549).

---

## 7. Contract Instance 연계

### 저장 경로

`docs/contract_schema/instances/{calc_slug}.yaml`

### 저장 내용 (build_contract() dict + generated_at KST)

```yaml
slug: ...
name: ...
formula: ...              # operator_confirmed formula
formula_status: pending_validation 또는 operator_confirmed  # ai_suggested 없음
test_cases: [...]
test_cases_status: ...
legal_refs: [...]
generated_at: 2026-08-11T...+09:00
```

### Round-trip 검증

`test_e2e_ca35.py::test_e2e_new3_dict_formula_roundtrip` — dict formula compact JSON → YAML 저장 → YAML 읽기 → 동일성 확인. **PASS**.

### delete_app() 연동

`_delete_contract_instance(slug)` → YAML 파일 삭제 + `docs/contract_schema/registry.yaml` 항목 제거. 양방향 정합성 유지.

---

## 8. Mode A 격리

### Mode A (generate_app 직접 호출)

```python
generate_app(cfg, name, category, desc, tier)  # _contract=None
```

CA-3의 `suggest_formula()`, `check_hold_rules()`, `build_contract()` 모두 Mode A 경로에 진입하지 않음. 기존 9개 계산기 생성 흐름 완전 독립.

검증: `tests/test_af_contract_dashboard.py::TestModeAUnchanged` 3개 테스트 PASS.

---

## 9. 블로그/WordPress 파이프라인 격리

### git diff 확인

CA-3-F 조사 기준, 블로그/WordPress 관련 파일 변경 없음:
- `logs/content_pipeline/*.json` — 로그 파일만, 파이프라인 로직 변경 없음
- `wordpress_publisher.py` — 변경 없음
- `image_builder.py` — 변경 없음
- `content_pipeline/` 모듈 — 변경 없음

### suggest_formula() 호출 경로

`suggest_formula()`는 `dashboard.py`의 Mode B Contract Builder UI에서만 호출됨:
```python
# dashboard.py:2278 (🤖 AI Formula 제안 버튼 핸들러)
_sf_result = AF.suggest_formula(cfg=cfg, ...)
```

블로그 생성, WordPress 게시, 콘텐츠 파이프라인에서의 `suggest_formula()` 호출 경로 없음. 격리 완전.

### known FAIL 확인

```
ERROR wordpress_publisher.py:50 Draft 게시 실패:
HTTPConnectionPool(host='salarymate.test', port=80): Max retries exceeded
(Caused by NewConnectionError: Failed to establish a new connection: WinError 10061)
```

CA-3 구현과 무관한 WordPress 로컬 서버 미연결 문제. CA-3-F에서 수정하지 않음 (절대 금지 항목).

---

## 10. Regression 결과

### 전체 결과

```
1 failed, 554 passed, 494 warnings in 84.93s
```

| 항목 | 기준 | 실제 |
|------|------|------|
| PASS | ≥ 554 | **554** ✅ |
| FAIL | 1 (known) | **1** ✅ |
| 신규 FAIL | 0 | **0** ✅ |

### CA-3 전용 테스트 결과

```
tests/test_e2e_ca35.py       17개 ............... PASS
tests/test_suggest_formula.py 18개 .................. PASS
tests/test_formula_contract.py 44개 ......................................... PASS
──────────────────────────────
소계: 79개 PASS (+ 관련 파일 5개 = 총 84/84 PASS)
```

### known FAIL 동일성 확인

`tests/production_validation_test.py::test_full_pipeline_execution`  
→ `HTTPConnectionPool(host='salarymate.test', port=80)` — WordPress 로컬 서버 미연결  
→ CA-3-4/CA-3-5 이전과 동일한 실패 원인. 신규 요인 없음. ✅

---

## 11. 잔여 Gap

### CA-3 내 잔여 Gap: **없음**

CA-3-F 사전조사 및 최종검증에서 신규 구현 문제 발견되지 않음.

### 관찰 사항 (Gap 아님)

| 항목 | 내용 | 영향 |
|------|------|------|
| `ast.Num` deprecated | Python 3.14 제거 예정 경고 (494건 중 일부) | 현재 Python 3.12에서 동작 정상. 기능 영향 없음 |
| CRLF/LF 경고 | Windows git 설정 부산물 | 기능 영향 없음 |
| docs/registry/*.yaml 미커밋 변경 | CA-2 시점에 기존 계산기 엔트리에 `input_labels`/`output_labels` 메타데이터 추가. 기능(formula, input_schema) 변경 없음. 세션 시작 시점 이전 상태 | CA-3-F 구현 외 기존 미커밋 상태 |

---

## 12. CA-4 이연 항목

CA-3 완료 이후 자연스럽게 연결되는 후속 과제:

| 항목 | 내용 | 우선순위 |
|------|------|---------|
| **CA-4-A** | HOLD → READY 전환 자동화 (`promote_to_ready()` Dashboard 연결) | 높음 |
| **CA-4-B** | `legal_master` 확장 (confidence=low 항목 보강, 신규 법령 추가) | 높음 |
| **CA-4-C** | `ast.Num` deprecated 경고 제거 (Python 3.14 대비) | 낮음 |
| **CA-4-D** | docs/registry/*.yaml 미커밋 변경 정리 및 커밋 | 중간 |
| **CA-4-E** | WordPress 연결 로컬 환경 설정 (known FAIL 해소) | 중간 |

---

## 13. 최종 판정

```
CA-3-F = PASS
CA-3   = COMPLETE
```

**판정 근거 요약**:

1. **Formula Lifecycle 완전 검증**: 4개 상태 전이, HOLD-1 발동/미발동, ai_suggested → pending_validation 자동 변환, operator_confirmed 격리 — 모두 설계대로 동작 확인.

2. **방어 로직 완전 검증**: R-1(변수 차단) / R-2(dict 키 검증) / R-6(2-click 확인) / R-7(AI 예외 처리) / R-8(JSON 폴백) — 직접 실행으로 확인.

3. **Type D 차단**: CUSTOM_COMPUTE_SLUGS + `_is_type_d_flow()` — AI API 호출 전 완전 차단 확인.

4. **Contract Instance**: ai_suggested 미저장 설계 의도 보존. Round-trip 정상. delete 연동 정상.

5. **Mode A 격리**: suggest_formula(), check_hold_rules(), build_contract()가 Mode A(generate_app 직접) 경로에 진입하지 않음.

6. **Blog/WordPress 격리**: suggest_formula()가 블로그/콘텐츠 파이프라인에서 호출되지 않음. CA-3 구현 범위 외 영역 변경 없음.

7. **Regression**: 554 PASS / 1 known FAIL (WordPress 연결 실패 — CA-3과 무관).

8. **Git 보호**: `_secret_replace2.txt` 미커밋. 기존 Registry 기능(formula, input_schema) 변경 없음. CA-3-F 코드 수정 0건.

9. **CA-3 완료 체크리스트 23/23 PASS**.
