# CA-2 FINAL — Contract System 최종 종합검증 보고서

> 검증 기준일: 2026-08-10  
> 검증자: Claude Sonnet 4.6 (자동 검증)  
> 원칙: 코드 수정 없음 / 테스트 수정 없음 / 결과 판정만 수행

---

## 1. 최종 판정

```
CA-2 FINAL = PASS
```

16개 체크리스트 전부 충족. 신규 FAIL 0건. 기준선 유지.

---

## 2. E2E 7개 시나리오 결과

| 시나리오 | 내용 | 판정 |
|----------|------|------|
| A | formula 없음 (not_generated) | ✅ PASS |
| B | formula 입력 / 미검증 (pending_validation) | ✅ PASS |
| C | formula 검증 실패 → 확정 불가 | ✅ PASS |
| D | formula 검증 성공 + 운영자 확정 (operator_confirmed) | ✅ PASS |
| E | operator_confirmed 후 formula 수정 → pending_validation | ✅ PASS |
| F | Contract 기반 계산기 생성 + 저장 전체 경로 | ✅ PASS |
| G | 계산기 삭제 → Contract Instance 정리 + registry 갱신 | ✅ PASS |

---

## 3. Contract Lifecycle 결과

### 3-1. build_contract() 필드 검증

| 필드 | 기본값 | 결과 |
|------|--------|------|
| `formula` | None | ✅ |
| `formula_status` (formula 없음) | `"not_generated"` | ✅ |
| `formula_status` (formula 있음, 미명시) | `"pending_validation"` | ✅ |
| `formula_status` (명시: operator_confirmed) | 그대로 보존 | ✅ |
| `test_cases` | `[]` | ✅ |
| `test_cases_status` (test_cases 없음) | `"not_generated"` | ✅ |
| `test_cases_status` (test_cases 있음) | `"operator_confirmed"` | ✅ |
| `desc` | `""` | ✅ |
| `legal_refs` | `[]` | ✅ |
| `scope_exclusions` | `[]` | ✅ |
| `input_fields` | `[]` | ✅ |
| `output_fields` | `[]` | ✅ |
| `slug` | lowercase normalized | ✅ |
| `tier` | `"Tier2-A"` | ✅ |

### 3-2. Contract → App Factory 정보 손실 없음

| 필드 | 경로 | 손실 여부 |
|------|------|----------|
| `formula` | Contract → `_contract` → sys1 CONTRACT LOCK → `app["_contract"]` | ✅ 없음 |
| `formula_status` | Contract → `_contract` → `save_app()` → Instance → registry | ✅ 없음 |
| `test_cases` | Contract → `_contract` → Instance YAML | ✅ 없음 |
| `test_cases_status` | Contract → registry.yaml 경량 인덱스 | ✅ 없음 |
| `desc` | Contract → generate_app(desc=) → AI prompt | ✅ 없음 |
| `legal_refs` | Contract → `_build_v3_entry()` → v3 Registry `legal_refs` | ✅ 없음 |
| `input_fields` | Contract → `_build_v3_entry()` → `input_labels` | ✅ 없음 |
| `output_fields` | Contract → `_build_v3_entry()` → `output_labels` | ✅ 없음 |

---

## 4. Formula Lifecycle 결과

전체 상태 전환 경로 검증:

```
formula 없음 → not_generated                              ✅ 정상
formula 입력 → pending_validation                         ✅ 정상
validate_formula_with_samples() 통과 → pending_validation  ✅ 정상 (자동 확정 없음)
[✅ Formula 확정] 버튼 클릭 → operator_confirmed           ✅ 정상
operator_confirmed 후 formula 수정 → pending_validation   ✅ 정상
```

**핵심 불변식**: "검증 성공 자체는 operator_confirmed를 자동 부여하지 않는다"
- `validate_formula_with_samples()` 통과 → `_fv_passed = True` → [✅ Formula 확정] 버튼 활성
- 운영자가 버튼을 직접 클릭해야만 `af_formula_confirmed_text` 저장 및 `formula_status = "operator_confirmed"` 설정
- **불변식 유지: ✅**

---

## 5. HOLD Rules 결과

| 조건 | 예상 | 실제 | 결과 |
|------|------|------|------|
| `not_generated` | HOLD-1 | HOLD-1 발동 | ✅ |
| `pending_validation` | HOLD-1 | HOLD-1 발동 | ✅ |
| `operator_confirmed` | HOLD-1 없음 | HOLD-1 없음 | ✅ |
| Critical + test_cases 없음 | HOLD-2 | HOLD-2 발동 | ✅ |
| Critical + test_cases 있음 | HOLD-2 없음 | HOLD-2 없음 | ✅ |
| medium confidence legal_ref | HOLD-3 | HOLD-3 발동 | ✅ |
| 모든 조건 충족 | HOLD 없음 | HOLD 없음 | ✅ |

CA-2-6-1에서 변경된 `formula_status != "operator_confirmed"` 조건 유지 확인: ✅

---

## 6. Formula Validation 결과

`validate_formula_with_samples()` 3단계 검증:

| Level | 내용 | 테스트 케이스 | 결과 |
|-------|------|------------|------|
| 1 | 구문 오류 감지 | `"a +"` → valid=False | ✅ |
| 2 | 변수 불일치 감지 | `"a + ghost"`, schema={"a"} → valid=False | ✅ |
| 3 | test_cases 실행 | `"a*2"`, 기대값 10.0 → match=True | ✅ |
| 3 | test_cases 실패 | `"a*2"`, 기대값 99.0 → match=False | ✅ |

**참고**: `"a + + b"`는 파이썬 유니어리 양수로 유효한 표현 (`a + (+b)`) → Level 1 통과가 정확한 동작.

---

## 7. Registry / Contract Instance 결과

### 7-1. v3 Registry (_build_v3_entry 구조)

| 필드 | 출처 | Mode B 한정 여부 |
|------|------|----------------|
| `input_labels` | Contract `input_fields` | Mode B에서만 비어있지 않음 |
| `output_labels` | Contract `output_fields` | Mode B에서만 비어있지 않음 |
| `legal_refs` | Contract `legal_refs` | Mode B에서만 비어있지 않음 |
| `contract_source` | Contract 경량 메타 | Mode B에서만 non-null |

**`contract_source`**: `{contract_slug, input_fields, output_fields, formula_status, test_cases_status}` — 경량 출처 인덱스이며, Contract Instance를 대체하지 않음. ✅

### 7-2. Contract Instance 영속화

| 검증 항목 | 결과 |
|-----------|------|
| `docs/contract_schema/instances/{slug}.yaml` 생성 | ✅ |
| `docs/contract_schema/registry.yaml` 갱신 | ✅ |
| Instance에 `formula` 원본 보존 | ✅ |
| Instance에 `test_cases` 원본 보존 | ✅ |
| Instance에 `formula_status` 보존 | ✅ |
| Instance에 `legal_refs` 보존 | ✅ |
| Instance에 `desc` 보존 | ✅ |
| Instance에 `scope_exclusions` 보존 | ✅ |
| Instance에 `generated_at` 자동 추가 | ✅ |
| Mode A (contract=None): Instance 생성 안 함 | ✅ |
| Mode A (contract={}): Instance 생성 안 함 | ✅ |
| registry.yaml `instances` 인덱스 갱신 | ✅ |
| `formula_status` registry에 기록 | ✅ |
| `test_cases_status` registry에 기록 | ✅ |

---

## 8. Mode A / Mode B 결과

| 항목 | Mode A | Mode B | 경계 명확? |
|------|--------|--------|-----------|
| `generate_app()` 호출 방식 | 직접 | `generate_app_with_contract()` 경유 | ✅ |
| sys1 CONTRACT LOCK | 없음 | `_build_contract_enforcement_prompt()` 삽입 | ✅ |
| `app["_contract"]` | None | contract dict | ✅ |
| `af_contract` 세션 처리 | 생성 후 `pop()` | `_contract` 저장 | ✅ |
| Contract 검증 패널 | 표시 안 함 | `_cv_for_save` 기반 표시 | ✅ |
| 저장 차단 | 없음 | `valid=False` → Save 비활성 | ✅ |
| Contract Instance 생성 | 절대 없음 | `_save_contract_instance()` 호출 | ✅ |
| HOLD-1/2/3 발동 | 없음 | `check_hold_rules()` 호출 | ✅ |

**Mode A 완전 분리 확인: ✅**

---

## 9. Delete Lifecycle 결과

```
계산기 생성
  ↓ save_app() → DB + v3 Registry HOLD + Contract Instance
계산기 삭제
  ↓ delete_app() →
    1. v3 Registry entry 제거                  ✅
    2. DB (calculators + app_templates) 삭제   ✅
    3. registry_auto.yaml 엔트리 제거          ✅
    4. _delete_contract_instance() 호출:
       - instances/{slug}.yaml 삭제            ✅
       - registry.yaml 항목 제거               ✅
고아 파일 없음                                 ✅
```

**Orphan 방지**: v3 Registry 저장 실패 시 `_v3_warn` 설정 → `if not _v3_warn and app.get("_contract")` 조건으로 Contract Instance 저장 건너뜀 → 고아 파일 불가능. ✅

---

## 10. Dashboard 결과

CA-2-6-2에서 추가된 UI 요소 최종 확인:

| UI 요소 | 구현 위치 | 동작 |
|---------|-----------|------|
| Formula 상태 배지 (⚪🟡🟢) | dashboard.py:2250-2266 | `af_contract.formula_status` 또는 fallback 비교 | ✅ |
| [🔍 Formula 검증] 버튼 | dashboard.py:2291 | `validate_formula_with_samples()` → `af_formula_validation` | ✅ |
| [✅ Formula 확정] 버튼 | dashboard.py:2326 | `disabled=not _fv_passed` → `af_formula_confirmed_text` 저장 | ✅ |
| Formula 수정 감지 | dashboard.py:2274-2281 | confirmed_raw != current_raw → `af_formula_confirmed_text` 삭제 | ✅ |
| Post-generation Formula 검증 | dashboard.py:2504-2520 | 변경 없음 (기존 동작 유지) | ✅ |

---

## 11. Regression 결과

| 구분 | 수치 |
|------|------|
| Before (기준선) | 505 PASS / 1 FAIL |
| After (현재) | 505 PASS / 1 FAIL |
| Delta | ±0 |
| Known FAIL | `test_full_pipeline_execution` (production_validation_test.py) |
| Known FAIL 내용 변화 | 없음 — 동일한 `salarymate.test` WP 연결 실패 |
| New FAIL | 0건 |

**Regression 기준선 유지: ✅**

---

## 12. Git Diff 분류 (CA-2 누적 변경)

### 12-1. CA-2 정식 변경 (committed in `a4de724`)

| 파일 | 내용 |
|------|------|
| `modules/app_factory.py` | `build_contract()`, `check_hold_rules()`, `validate_against_contract()`, `generate_app_with_contract()`, `_save_contract_instance()`, `_delete_contract_instance()`, `save_app()` Contract 지원, `delete_app()` Contract 정리 |
| `modules/formula_engine.py` | `validate_formula_with_samples()` 추가 |
| `dashboard.py` (Stage 1) | Contract Builder UI (Mode B 기본 구조, Contract 검증 패널) |

### 12-2. CA-2 정식 변경 (uncommitted — CA-2-6-2)

| 파일 | 상태 | 내용 |
|------|------|------|
| `dashboard.py` (Stage 2) | staged | Formula 상태 배지 + [검증][확정] 버튼 + formula_status 보존 로직 + HOLD 경고 표시 |
| `tests/test_formula_contract.py` | unstaged | CA-2-4 (17개) + CA-2-6-1 (5개) + CA-2-6-2 (4개) = 26개 신규 테스트 |
| `tests/test_review_center.py` | unstaged | CA-2-6-1 HOLD-1 2개 신규 테스트 |

### 12-3. CA-2 관련 테스트 (committed in `a4de724`)

| 파일 | 내용 |
|------|------|
| `tests/test_app_factory_contract.py` | Contract E2E 테스트 55개 |
| `tests/test_af_contract_dashboard.py` | Dashboard Contract UI 테스트 46개 |
| `tests/test_af_discard.py` | App Factory Discard 테스트 31개 |

### 12-4. CA-2 문서 (untracked)

- `docs/CA1A_CONTRACT_SCHEMA_DESIGN.md`
- `docs/CA1B0_PREFLIGHT_REPORT.md`
- `docs/CA2_0_*` ~ `docs/CA2_6_3_*` 사전조사/보고서
- `docs/contract_schema/registry.yaml`

### 12-5. Pre-existing 변경

| 파일 | 분류 |
|------|------|
| `logs/content_pipeline/*.json` | 자동 파이프라인 로그 |
| `tests/snapshots/competitive_analysis_snapshot.json` | 자동 스냅샷 갱신 |
| `docs/registry/employment.yaml` 외 | LF/CRLF 라인엔딩 변환만 (내용 변경 없음) |
| `modules/utils/data/logs/health_last.json` | 자동 헬스 로그 |

### 12-6. 계획 외 코드 변경

**없음** — CA-2 범위 내 모든 변경이 사전 확인된 구현 항목과 일치.

---

## 13. CA-2 잔여 Gap 분류

| Gap | 내용 | 분류 |
|-----|------|------|
| G-1 | Dashboard에 `legal_refs` 입력 UI 없음 | CA-3 이연 |
| G-2 | Dashboard에 `scope_exclusions` 입력 UI 없음 | CA-3 이연 |
| G-3 | Formula 배지 1사이클 지연 (Streamlit 특성) | Pre-existing (Streamlit 제약, 기능 영향 없음) |
| G-4 | HOLD 수락 단계 없음 (soft gate, 비차단) | 의도된 설계 |
| G-5 | v3 Registry 실패 시 Instance 저장 생략 | 의도된 설계 (Orphan 방지) |
| G-6 | `ai_suggested` 상태 미구현 | CA-3 이연 |
| G-7 | `test_full_pipeline_execution` FAIL | Pre-existing (DB/WP 연결 필요) |

---

## 14. CA-2 완료도 체크리스트

- [x] Contract lifecycle 정상
- [x] Formula status lifecycle 정상
- [x] Formula validation 정상
- [x] HOLD Rules 정상
- [x] Mode A 무영향
- [x] Mode B 정상
- [x] Registry 연결 정상
- [x] Contract Instance 생성 정상
- [x] Contract Instance 삭제 정상
- [x] Orphan 방지 정상
- [x] Dashboard 정상
- [x] E2E A~G PASS
- [x] Regression 기준선 유지 (505/1)
- [x] 신규 FAIL 0건

---

## 15. 최종 권고

**CA-2 종료 → CA-3 사전조사 진행**

CA-2 Contract System은 설계 목표를 모두 달성했다. 16개 체크리스트 전부 통과, 기준선 회귀 없음, 계획 외 변경 없음.

### CA-3 후보 (우선순위 순)

1. **AI Formula 자동제안 + `ai_suggested` 상태** (G-6)
   - `build_contract(formula=ai_formula, formula_status="ai_suggested")` — 1줄 확장 가능
   - Dashboard 배지 맵에 `"ai_suggested": "🤖 AI 제안"` 추가
   - HOLD-1 `!= "operator_confirmed"` 조건이 `ai_suggested`를 자동 차단 (변경 불필요)

2. **Dashboard `legal_refs` UI** (G-1)
   - Contract Builder에 `legal_refs` 텍스트 입력 필드 추가
   - `build_contract()` 호출 시 `legal_refs=_legal_refs_val` 전달

3. **AI test_cases 제안 / Contract Builder 자동 보강** (CA-3 선택)
   - 기존 test_cases 입력이 수동이므로 AI 제안으로 보강

> **CA-3 착수 전 별도 사전조사 필수** — 착수 지시서 전달 시 시작.
