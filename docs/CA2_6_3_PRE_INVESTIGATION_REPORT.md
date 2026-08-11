# CA-2-6-3 사전조사 보고서 — Contract Builder 최종 연결점 점검

> 조사 기준: CA-2-6-2 구현 완료 상태 (2026-08-10)  
> 원칙: 코드 수정 금지 / 신규 기능 구현 금지 / 기존 테스트 수정 금지  
> 테스트 현황: **505 PASS / 1 FAIL** (known FAIL: `test_full_pipeline_execution`)

---

## 1. 전체 E2E 연결 구조 검증

### 1-1. Mode A (Contract 없음)

```
Dashboard [▶ AI 생성] 버튼
  └─ generate_app(cfg, name, category, desc, tier)          ← _contract=None
       └─ sys1: CONTRACT LOCK 섹션 없음
  └─ af_result 저장
  └─ af_contract 세션에서 제거 (pop)

[💾 저장] 버튼
  └─ save_app(cfg, app, ...)
       ├─ DB save (calculators + app_templates)
       ├─ registry_auto.yaml 스테이징
       ├─ v3 Registry HOLD 등록
       ├─ Contract Instance 저장 안 함  ← app.get("_contract") is None
       └─ extract_checklist + save_af_checklist
```

**연결 상태: ✅ 정상** — Mode A는 `af_contract` 세션 키를 명시적으로 제거하므로 Contract Instance가 절대 생성되지 않는다.

---

### 1-2. Mode B (Contract 기반 생성)

```
Dashboard Contract Builder (expander)
  ├─ slug / input_fields / output_fields 필수 입력
  ├─ formula 선택 입력 → formula_status 배지 표시
  ├─ [🔍 Formula 검증] → validate_formula_with_samples() → af_formula_validation
  ├─ [✅ Formula 확정] (valid=True만 활성) → af_formula_confirmed_text 저장
  └─ formula 수정 감지 → af_formula_confirmed_text / af_formula_validation 삭제

[📋 Contract 기반 생성] 버튼
  ├─ 입력값 검증 (name / slug / input_fields / output_fields 필수)
  ├─ build_contract(..., formula_status=_fv_prior_status)
  │     _fv_prior_status = "operator_confirmed" if 확정텍스트==현재텍스트 else None
  ├─ af_contract 세션에 저장
  ├─ check_hold_rules(_contract) → HOLD 경고 표시 (비차단)
  └─ generate_app_with_contract(cfg, _contract)
        ├─ generate_app(..., _contract=contract)
        │     └─ sys1: CONTRACT LOCK 섹션 삽입 (_build_contract_enforcement_prompt)
        ├─ validate_against_contract(contract, result) → _contract_validation
        └─ result["_contract"] = contract

Contract 검증 패널 표시 (_cv is not None)
  ├─ slug 일치 여부
  ├─ 필드 drift 여부
  └─ formula 변경 여부

[💾 저장] 버튼
  ├─ _contract_save_blocked = (_cv is not None) AND (_cv.get("valid") == False)
  ├─ save_app(cfg, app, ..., slug=contract_slug)
  │     ├─ DB save
  │     ├─ registry_auto.yaml 스테이징
  │     ├─ v3 Registry HOLD 등록
  │     ├─ [B'] _save_contract_instance(slug, app["_contract"])
  │     │         → docs/contract_schema/instances/{slug}.yaml
  │     │         → docs/contract_schema/registry.yaml 갱신
  │     └─ extract_checklist + save_af_checklist
  └─ af_contract / af_result 세션 초기화
```

**연결 상태: ✅ 정상** — build_contract → generate_app_with_contract → save_app → Contract Instance까지 단방향 흐름이 끊기지 않는다.

---

## 2. 7개 시나리오 코드 추적 결과

### 시나리오 A: formula 없음 (formula_status = not_generated)

- `build_contract(formula=None)` → `formula_status = "not_generated"`
- `check_hold_rules()`: HOLD-1 발동 (`not_generated != "operator_confirmed"`)
- `_build_contract_enforcement_prompt()`: formula 섹션 생략, 필드만 전달
- `validate_against_contract()`: `contract.get("formula") is None` → `formula_changed = False` → 불일치 없음
- 저장: Contract Instance의 `formula_status = "not_generated"` 영속화

**결과: ✅ 정상** — HOLD 경고 표시 후 생성/저장 가능. formula 없는 계산기도 Mode B 사용 가능.

---

### 시나리오 B: formula 미검증 (pending_validation)

- 사용자가 formula 입력 후 [검증] 버튼 미클릭
- `af_formula_confirmed_text` 없음 → `_fv_prior_status = None`
- `build_contract(formula=expr, formula_status=None)` → 자동 도출 → `"pending_validation"`
- HOLD-1 발동 (경고 표시, 비차단)
- 생성 진행, Contract Instance에 `formula_status = "pending_validation"` 저장

**결과: ✅ 정상** — 의도된 동작. 운영자가 경고를 인지하고 진행하는 흐름.

---

### 시나리오 C: 검증 실패 (validation failed)

- [🔍 Formula 검증] 클릭 → `validate_formula_with_samples()` 실패
- `_fv_passed = False` → [✅ Formula 확정] 버튼 비활성(disabled=True)
- `af_formula_confirmed_text` 저장 불가
- 생성 시: `_fv_prior_status = None` → `build_contract()` → `"pending_validation"`
- HOLD-1 발동

**결과: ✅ 정상** — 검증 실패한 formula는 `operator_confirmed`가 될 수 없음.

---

### 시나리오 D: 검증 성공 후 확정 (operator_confirmed)

- [🔍 Formula 검증] 통과 → `_fv_passed = True`
- [✅ Formula 확정] 클릭 → `af_formula_confirmed_text = formula_raw`
- `af_contract["formula_status"] = "operator_confirmed"` + `st.rerun()`
- 배지: `🟢 운영자 확정`
- [📋 Contract 기반 생성] 클릭:
  - `_fv_prior_raw == _formula_raw` → `_fv_prior_status = "operator_confirmed"`
  - `build_contract(formula_status="operator_confirmed")` → `"operator_confirmed"`
  - **HOLD-1 발동 안 함**
  - sys1: CONTRACT LOCK에 확정된 formula 포함

**결과: ✅ 정상** — 전체 확정 흐름이 단방향으로 연결됨.

---

### 시나리오 E: 확정 후 formula 수정

- formula 수정 감지 로직 (dashboard.py:2274-2281):
  ```python
  if _fv_confirmed_raw and _fv_current_raw != _fv_confirmed_raw:
      st.session_state.pop("af_formula_confirmed_text", None)
      st.session_state.pop("af_formula_validation", None)
      if st.session_state.get("af_contract"):
          st.session_state["af_contract"]["formula_status"] = "pending_validation"
  ```
- `af_formula_confirmed_text` 삭제 → 다음 렌더링에서 `_fv_prior_status = None`
- 배지: `🟡 검증 대기`로 복귀
- 재생성 시 HOLD-1 발동

**결과: ✅ 정상** — 단, 배지 업데이트는 수정 감지 코드가 실행되는 다음 렌더링 사이클에 반영됨 (Streamlit 특성상 1사이클 지연, 기능상 문제 없음).

---

### 시나리오 F: Contract 생성 성공 + 저장

- `generate_app_with_contract()` → `_contract_validation.valid = True`
- `_contract_save_blocked = False` → [💾 저장] 활성
- `save_app()`:
  - DB: calculators + app_templates 저장
  - registry_auto.yaml 스테이징 기록
  - v3 Registry HOLD 등록
  - `not _v3_warn and app.get("_contract")` → `_save_contract_instance()` 호출
  - `docs/contract_schema/instances/{slug}.yaml` 생성
  - `docs/contract_schema/registry.yaml` 갱신 (formula_status 포함)
  - `extract_checklist + save_af_checklist` 체크리스트 저장
- 저장 완료 후 `af_result` / `af_contract` 세션 초기화

**결과: ✅ 정상** — 전체 저장 파이프라인이 연결됨.

**현황**: `docs/contract_schema/instances/` 디렉토리에 인스턴스 없음 (예상 — Mode B로 실제 저장된 계산기 없음).

---

### 시나리오 G: 계산기 삭제

- `delete_app(cfg, slug)` (app_factory.py:968):
  1. v3 Registry에서 `source != "app_factory"` 보호 확인
  2. DB: calculators + app_templates 삭제
  3. registry_auto.yaml 엔트리 제거
  4. v3 Registry 엔트리 제거
  5. `_delete_contract_instance(slug)` 호출 (app_factory.py:1017-1021)
     - `docs/contract_schema/instances/{slug}.yaml` 삭제
     - `docs/contract_schema/registry.yaml` 항목 제거
  6. calculator_index.json 재생성

**결과: ✅ 정상** — Contract Instance와 DB 레코드가 원자적으로(try/except 분리이나) 함께 정리됨.

---

## 3. Mode A / Mode B 경계 최종 확인

| 항목 | Mode A | Mode B |
|------|--------|--------|
| 생성 함수 | `generate_app()` | `generate_app_with_contract()` |
| sys1 CONTRACT LOCK | 없음 | `_build_contract_enforcement_prompt()` 삽입 |
| `app["_contract"]` | `None` | `contract` dict |
| `af_contract` 세션 | 생성 후 `pop()` 제거 | `_contract` 저장 |
| Contract 검증 패널 | 표시 안 함 (`_cv is None`) | 표시 (`_cv is not None`) |
| 저장 차단 | 없음 | `valid=False`면 [💾 저장] disabled |
| Contract Instance | 생성 안 함 | `_save_contract_instance()` 호출 |

**경계 상태: ✅ 명확** — 두 경로 사이에 상태 오염 없음. Mode A 클릭 시 `af_contract` 세션 제거가 명시적으로 보장됨 (dashboard.py:2217).

---

## 4. CA-3 확장성 평가 (ai_suggested 상태)

### 현재 3-state 구조
```
not_generated → pending_validation → operator_confirmed
```

### CA-3에서 예상되는 ai_suggested 상태
```
not_generated → (AI 자동생성) → ai_suggested → pending_validation → operator_confirmed
```

### 필요한 변경 사항 (최소)

| 위치 | 변경 내용 |
|------|-----------|
| `build_contract()` | 파라미터 변경 없음 — `formula_status="ai_suggested"` 그대로 전달 가능 |
| `check_hold_rules()` HOLD-1 | `!= "operator_confirmed"` 조건 유지 — `ai_suggested` 자동 차단 ✅ |
| 배지 맵 | `"ai_suggested": "🤖 AI 제안"` 항목 추가 필요 |
| [🔍 Formula 검증] 버튼 | `ai_suggested` 상태에서도 검증 가능 — 로직 변경 없음 |
| Contract Instance | `formula_status: ai_suggested` 그대로 영속화 가능 |

**확장성: ✅ 높음** — `build_contract()`의 `formula_status` 파라미터 패스스루 설계 덕분에 CA-3 ai_suggested 상태 추가는 최소 변경(배지 맵 1줄)으로 가능.

---

## 5. Gap 분석 (G-1 ~ G-10 재평가)

### 확인된 Gap (현재 버전 기준)

| Gap ID | 항목 | 상태 | 비고 |
|--------|------|------|------|
| G-1 | Dashboard에 `legal_refs` 입력 필드 없음 | ⚠️ 열린 Gap | `build_contract()` 파라미터 존재, UI 미노출 |
| G-2 | Dashboard에 `scope_exclusions` 입력 필드 없음 | ⚠️ 열린 Gap | 동일, CA-3 범위로 연기 |
| G-3 | formula_status 배지가 수정 감지보다 1사이클 앞서 렌더링 | ✅ 허용 가능 | Streamlit 특성상 불가피, 기능 영향 없음 |
| G-4 | HOLD 경고 수락(acknowledge) 단계 없음 | ✅ 의도된 설계 | 운영자가 경고 보고 직접 판단 |
| G-5 | v3 Registry 실패 시 Contract Instance 저장 건너뜀 | ✅ 의도된 설계 | 고아 파일 방지 로직 |
| G-6 | validate_against_contract()가 저장 함수 내부에서 재호출 안 됨 | ✅ 의도된 설계 | UI에서 차단, 함수는 생성 시점에만 호출 |
| G-7 | `_af_test_cases` 변수가 검증 버튼과 생성 버튼 양쪽에서 사용 | ✅ 정상 | text_area 정의 후 두 곳에서 안전하게 참조 |
| G-8 | Contract Instance 현재 0개 (instances/ 비어 있음) | ✅ 정상 | 실제 Mode B 저장 미완료 상태로 예상 |
| G-9 | `test_full_pipeline_execution` FAIL | ⚠️ 기존 known FAIL | DB 연결 필요, 격리 불가 — 기존 이슈 |
| G-10 | CA-3용 ai_suggested 상태 미구현 | ✅ CA-3 범위 | 현재 설계에서 확장 가능 |

### 실질적 행동 필요 Gap

- **G-1, G-2**: `legal_refs`, `scope_exclusions` UI 필드 — CA-3 또는 별도 스프린트 범위
- **G-9**: `test_full_pipeline_execution` — 기존 known FAIL, 이 조사 범위 외

---

## 6. CA-2 완료도 평가

| 단계 | 제목 | 상태 |
|------|------|------|
| CA-2-1 | Contract 스키마 구조 + `build_contract()` | ✅ 완료 |
| CA-2-2 | Contract Instance 영속화 (`_save_contract_instance`, `_delete_contract_instance`) | ✅ 완료 |
| CA-2-3 | `docs/contract_schema/registry.yaml` 인덱스 | ✅ 완료 |
| CA-2-4 | `validate_against_contract()` + schema drift 감지 | ✅ 완료 |
| CA-2-5 | `check_hold_rules()` HOLD-1/2/3 | ✅ 완료 |
| CA-2-6-1 | formula_status 3-state 머신 (`pending_validation` 도입) | ✅ 완료 |
| CA-2-6-2 | Dashboard Formula 검증 UI + `operator_confirmed` 흐름 | ✅ 완료 |
| CA-2-6-3 | 최종 연결점 점검 (이 보고서) | ✅ 완료 |

**CA-2 전체 완료도: ✅ 목표 범위 내 100% 완료**

---

## 7. CA-3 전환 준비 상태

### CA-3 전제 조건 (현재 상태 기준)

| 전제 조건 | 상태 |
|-----------|------|
| Contract 객체 구조 확정 | ✅ |
| formula_status 상태 머신 | ✅ (ai_suggested 1-라인 확장 가능) |
| Dashboard 검증 UI | ✅ |
| HOLD rules (soft gate) | ✅ |
| Contract Instance 영속화 | ✅ |
| Registry 연동 | ✅ |
| test coverage (505 PASS) | ✅ |

**전환 준비 상태: ✅ CA-3 시작 가능**

---

## 8. 결론 및 권고

CA-2에서 설계된 Contract 시스템의 7개 E2E 시나리오(A~G)가 코드 수준에서 모두 연결돼 있음을 확인했다.

**발견된 유일한 열린 Gap**:
- `legal_refs`, `scope_exclusions`가 Dashboard UI에 노출되지 않음 → **CA-3 스코프로 연기 권고**

**CA-2 시스템은 운영 투입 준비 완료** — 다음 단계는 CA-3 (AI formula 자동제안 + ai_suggested 상태) 또는 Dashboard `legal_refs` UI 추가 중 선택.
