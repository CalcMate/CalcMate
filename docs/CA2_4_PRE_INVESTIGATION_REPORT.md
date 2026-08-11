# CA-2-4 사전조사 보고서: Contract Schema / Contract Instance 영속화 구조

**작성일**: 2026-08-10  
**조사 범위**: 코드/YAML 수정 없음. 읽기 전용 조사.  
**기준 베이스라인**: 485 PASS / 1 FAIL (WordPress 연결 — 기존 문제)  
**관련 선행 작업**: CA-2-1(formula_status), CA-2-2(legal_refs/contract_source), CA-2-3(check_hold_rules)

---

## I. 현재 Contract 생명주기 전체 추적

```
[1] 생성
    build_contract() → dict (메모리)
    파일: modules/app_factory.py:267
    키 수: 13개 (slug, name, category, tier, input_fields, output_fields,
                  formula, formula_status, scope_exclusions, test_cases,
                  test_cases_status, desc, legal_refs)

[2] 세션 저장
    st.session_state["af_contract"] = _contract
    파일: dashboard.py:2304
    수명: 세션 지속 중

[3] Pre-gen 체크 (CA-2-3)
    check_hold_rules(_contract) → read-only
    파일: dashboard.py:2307
    contract 변형: 없음

[4] 생성 및 embed
    generate_app_with_contract(cfg, contract)
      ├─ generate_app(..., _contract=contract)
      ├─ validate_against_contract(contract, result)
      ├─ result["_contract"] = contract          ← app dict에 참조 embed
      └─ result["_contract_validation"] = validation
    파일: modules/app_factory.py:~397
    contract 변형: 없음 (원본 read-only)

[5] 영속화 (현재)
    save_app(cfg, app, slug=slug_in)
      └─ _build_v3_entry(contract=app.get("_contract"))
           └─ contract_source (5개 필드 스냅샷)만 Registry에 기록
    파일: modules/app_factory.py:847
    ★ contract 전체(formula, test_cases 포함)는 영속 저장 없음

[6] 소멸
    st.session_state.pop("af_contract", None)
    파일: dashboard.py:2475 (추정 — 저장 성공 후 세션 초기화)
    결과: formula, test_cases, legal_refs 원본 완전 소멸 → 이후 추적 불가
```

**핵심 문제**: 현재 `contract_source` (CA-2-2)는 5개 필드 스냅샷 뿐이며 `formula` 자체가 없음.  
세션 소멸 후 "어떤 수식으로 이 계산기를 만들었는가"를 재현할 방법이 없음.

---

## II. `docs/contract_schema/` 도입 Glob 안전성 검증

### 현황
```
docs/contract_schema/ — 현재 미존재
docs/registry/         — load_registry_v3() glob 대상 (*.yaml)
docs/legal_master/     — load_legal_master() glob 대상 (*.yaml)
```

### 검증 결과

| Loader | glob 경로 | contract_schema/ 영향 |
|--------|-----------|----------------------|
| `load_registry_v3()` | `docs/registry/*.yaml` | **없음** (별도 디렉토리) |
| `load_legal_master()` | `docs/legal_master/*.yaml` | **없음** (별도 디렉토리) |

`docs/contract_schema/`는 양쪽 glob 범위 밖 → **도입 시 기존 로더에 오염 없음 (안전)**.

### 추가 확인: `_write_registry_v3()`
`_category_to_af_yaml(category)` → `docs/registry/{name}_af.yaml` 에만 저장.  
`docs/contract_schema/` 내 파일은 해당 함수가 절대 쓰지 않음 → **충돌 없음**.

---

## III. Contract Schema Registry 구조 설계 검증

### CA-1A 설계 필드 vs 현재 `build_contract()` 구현

| 필드 | CA-1A 설계 | 현재 구현 상태 |
|------|------------|---------------|
| `slug` | 필수 | ✓ 구현 |
| `name` | 필수 | ✓ 구현 |
| `category` | 필수 | ✓ 구현 |
| `tier` | 필수 | ✓ 구현 |
| `desc` | 선택 | ✓ 구현 |
| `input_fields` | 필수 | ✓ 구현 |
| `output_fields` | 필수 | ✓ 구현 |
| `legal_refs` | 선택 | ✓ 구현 (CA-2-2) |
| `formula` | 선택 | ✓ 구현 |
| `formula_status` | 자동 도출 | ✓ 구현 (CA-2-1) |
| `scope_exclusions` | 선택 | ✓ 구현 |
| `test_cases` | 선택 | ✓ 구현 |
| `test_cases_status` | 자동 도출 | ✓ 구현 (CA-2-1) |
| `schema_id` | 자동 | **✗ 미구현** |
| `schema_version` | 자동 | **✗ 미구현** |
| `generation_metadata` | 자동 | **✗ 미구현** |
| `review_metadata` | 자동 | **✗ 미구현** |

**CA-2-4 범위 결정**: `schema_id`/`schema_version`은 JSON Schema 검증과 연결될 때 의미 있음.  
현재 v12에는 JSON Schema validator가 없음 → CA-3+ 범위. CA-2-4에서는 불요.

---

## IV. Contract Instance SSOT 경계 — 3자 관계 명확화

### SSOT 경계 정의

| 계층 | 저장 위치 | 담당 데이터 | 가변성 |
|------|-----------|------------|--------|
| **운영 레이어** | `docs/registry/*_af.yaml` | status, tier, display_order, related_slugs | 운영자 수시 수정 |
| **생성 스냅샷** | Registry 내 `contract_source` | 5개 필드 (slug, input_fields, output_fields, formula_status, test_cases_status) | **불변** (CA-2-2 정의) |
| **생성 스펙** | `docs/contract_schema/{slug}.yaml` | Contract 전체 (formula, test_cases, legal_refs 포함) | 재생성 시 교체 |
| **임시 작업** | `st.session_state["af_contract"]` | 생성 작업 중 계약 객체 | 세션 소멸 시 사라짐 |

### 핵심 구분 원칙
- **`contract_source` (Registry 내부)** → "이 계산기가 어떤 Contract에서 왔는가"의 최소 증거 (CA-2-2 정의, 불변)
- **Contract Instance (`docs/contract_schema/`)** → "그 Contract의 전체 내용이 무엇이었는가"의 완전한 기록 (CA-2-4 신규)
- 두 레이어는 역할이 다르며, CA-2-2 `contract_source`는 CA-2-4 이후에도 **제거하지 않음** (사용자 정의 불변 원칙 유지)

---

## V. `save_app()` 내부 단계별 분석 및 Contract Instance 삽입 시점

### 현재 `save_app()` 실행 시퀀스 (modules/app_factory.py:780)

```
[사전] 중복 체크 (name + slug) — DB + Registry v3
  └─ 실패 시 즉시 return False (이후 없음)

[Step 1] DB 저장
  ├─ tpl_repo.save() → template_id 확보
  └─ calc_repo.save() → calculator row
    └─ 실패 시 즉시 return False (이후 없음)

[Step A] registry_auto.yaml 스테이징 (line 839)
  └─ add_auto_entry() — 실패 무시 (LOG.warning)

[Step B] v3 Registry 즉시 기록 (line 847-852)
  ├─ _v3_entry = _build_v3_entry(app, new_slug, tier=_tier, contract=app.get("_contract"))
  └─ _write_registry_v3(new_slug, _v3_entry, category)
    └─ 실패 시 _v3_warn 설정 (계산기 저장은 유효)

[Step B'] ← ★ Contract Instance 삽입 최적 지점
  └─ _save_contract_instance(new_slug, app.get("_contract"))
    └─ 실패 무시 (LOG.warning)

[Step C] calculator_index.json 갱신 (line 855)
  └─ 실패 무시

[Step D] 체크리스트 저장 (line 864-870)
  └─ extract_checklist() + save_af_checklist()
  └─ Step B 성공 시만 실행

return True, _msg
```

### Step B' 선택 이유
- Step 1 (DB) 실패 → `return False` → Contract 저장 자동 생략 (일관성 보장)
- Step B (Registry) 성공 → 계산기 배포 확정 → Contract 기록 시점으로 적절
- Step B 실패 (`_v3_warn` 있음) → Contract도 저장 보류 가능 (옵션)
- Step C/D 이후는 너무 늦고 정보가 없음

---

## VI. Slug/버전 전략

### 파일명 규칙
```
docs/contract_schema/{slug}.yaml
```
예시: `docs/contract_schema/severance-pay-custom.yaml`

### 덮어쓰기 vs 버전 관리

| 방식 | 장점 | 단점 |
|------|------|------|
| 단순 덮어쓰기 (`{slug}.yaml`) | 단순, 최신 스펙이 항상 1개 | 이전 스펙 소멸 |
| 타임스탬프 버전 (`{slug}_20260810.yaml`) | 히스토리 보존 | 파일 누적, 조회 복잡 |
| 숫자 버전 (`{slug}_v1.yaml`, `_v2.yaml`) | 명시적 버전 | 최신 추적 어려움 |

### 권장: 단순 덮어쓰기 + `generated_at` 필드

**근거**:
- `save_app()`은 slug 중복 시 `return False` → 같은 slug로 재저장 불가 (중복 체크)
- 따라서 실제로 같은 slug가 두 번 저장되는 정상 시나리오는 없음
- 재생성 필요 시 `delete_app()` 후 새 이름 → slug 변경이 표준 경로
- `generated_at` ISO 타임스탬프로 생성 시점 기록 충분
- 히스토리가 필요하면 git이 담당 (YAML은 git 추적 대상)

```yaml
# docs/contract_schema/sample-calc.yaml 예시
slug: sample-calc
name: 샘플 계산기
category: 노무/급여
tier: Tier2-A
generated_at: "2026-08-10T14:30:00+09:00"
formula_status: operator_confirmed
test_cases_status: operator_confirmed
input_fields:
  - base_pay
output_fields:
  - net_pay
legal_refs:
  - labor_standards_act_55
formula: "net_pay = base_pay * 0.9"
scope_exclusions: []
test_cases:
  - input: {base_pay: 1000}
    expected: {net_pay: 900}
desc: "기본급의 90%를 실수령액으로 계산"
```

---

## VII. 실패 시나리오 분석

### 시나리오 A: DB 저장 성공 → Contract Instance 저장 실패
```
[Step 1] DB 저장 성공
[Step B] Registry 기록 성공
[Step B'] Contract Instance 저장 실패 → LOG.warning (무시)
return True, _msg (성공 메시지)
```
**결과**: 계산기 배포 완료, Contract 이력만 없음.  
**조치**: 경고 로그만. 심각도 낮음 — 계산기 자체는 정상 작동.  
**장기 영향**: `docs/contract_schema/{slug}.yaml` 없음 → `load_contract_instance(slug)`가 None 반환.

### 시나리오 B: DB 저장 성공 → Registry 실패 → Contract Instance 삽입 위치 판단
```
[Step 1] DB 저장 성공
[Step B] Registry 기록 실패 → _v3_warn 설정
[Step B'] Contract Instance: 저장하지 않음 (if not _v3_warn 조건)
return True, _msg + _v3_warn
```
**결과**: 계산기는 DB에 있으나 Registry SSOT 없음.  
**현재 동작**: 이미 `_v3_warn` 분기로 Step D(checklist)도 생략함.  
**권장**: Contract Instance도 동일 조건으로 생략 → Registry 없는 계산기에 Contract만 고아 파일 방지.

### 시나리오 C: DB 저장 실패 (현재 동작 확인)
```
[Step 1] tpl_repo.save() 또는 calc_repo.save() 실패
return False, "저장 실패..." (line 833-834)
```
이후 Step A/B/B'/C/D 실행 안 됨 → Contract Instance 저장도 없음 → **자동 일관성 보장**.

### 시나리오 D: Contract Instance 파일 존재하지만 Registry 항목 없음 (고아 파일)
**발생 조건**: Registry 기록 실패 후 Contract Instance 저장 성공한 경우.  
**시나리오 B의 권장**대로 `not _v3_warn` 조건 사용 시 발생하지 않음.

---

## VIII. Mode A / Mode B 영향 분석

### Mode A: `generate_app()` 직접 → `save_app()`
```python
app.get("_contract")  # None
_build_v3_entry(contract=None)  # contract_source: None
_save_contract_instance(slug, None)  # None → 저장 생략
```
- Contract Instance 파일 생성 안 됨 → 정상 (Mode A는 Contract 없는 경로)
- 기존 9개 계산기(Mode A 저장)에는 영향 없음

### Mode B: App Factory 전체 경로 → `generate_app_with_contract()`
```python
app.get("_contract")  # build_contract() 결과 dict
_build_v3_entry(contract=app["_contract"])  # contract_source: 5필드 스냅샷
_save_contract_instance(slug, app["_contract"])  # 전체 YAML 저장
```
- Contract Instance 파일: `docs/contract_schema/{slug}.yaml` 생성
- Registry에는 `contract_source` 스냅샷 (기존 5필드) + 나머지 메타

### 기존 계산기 보호
`_write_registry_v3()`:
```python
if slug in existing_v3:
    raise ValueError(f"v3 Registry에 이미 존재하는 slug: '{slug}'")
```
기존 9개(+ annual-leave-remaining)는 이미 Registry에 있음 → save_app() 중복 체크에서 걸림 → **절대 덮어쓰기 불가**.

---

## IX. 테스트 영향 분석

### 현재 테스트 현황
```
tests/test_formula_contract.py   — 17 tests (PASS)
tests/test_review_center.py      — 27 tests (PASS)
전체: 44 PASS
```

### CA-2-4 구현 후 영향받는 테스트
| 테스트 파일 | 영향 | 이유 |
|------------|------|------|
| `test_formula_contract.py` | **있음** | `build_contract()` 시그니처 변경 없음, 단 `_save_contract_instance` 통합 테스트 추가 필요 |
| `test_review_center.py` | **없음** | review_center.py 무변경 |
| 기타 | 없음 | 새 순수 함수 추가만 |

### 추가 필요 테스트 목록
1. `_save_contract_instance(slug, contract)` — 정상 저장 확인
2. `_save_contract_instance(slug, None)` — None 전달 시 파일 생성 안 함
3. `load_contract_instance(slug)` — 저장된 파일 올바르게 로드
4. `load_contract_instance("nonexistent")` — 없는 slug → None 반환
5. `save_app()` 통합 흐름 — Contract Instance 파일 생성 확인 (mocking 사용)
6. `save_app()` Contract Instance 저장 실패 — 계산기 저장 성공 영향 없음 확인

---

## X. 최소 구현 범위 (A/B/C 분류)

### A: Must-have (CA-2-4 필수 구현)

| # | 항목 | 파일 | 설명 |
|---|------|------|------|
| A1 | `docs/contract_schema/` 디렉토리 | (mkdir) | `.gitkeep` 포함, git 추적 |
| A2 | `_save_contract_instance(slug, contract)` | `modules/app_factory.py` | 순수 함수. `contract`가 None이면 noop. `generated_at` 추가 후 YAML 저장 |
| A3 | `save_app()` Step B' 통합 | `modules/app_factory.py` | `if not _v3_warn and app.get("_contract"):` 조건으로 호출, 실패 무시 |
| A4 | 단위 테스트 추가 | `tests/test_formula_contract.py` | A2/A3 관련 최소 케이스 |

### B: Nice-to-have (CA-2-4 추가 가능, 시간 허용 시)

| # | 항목 | 파일 | 설명 |
|---|------|------|------|
| B1 | `load_contract_instance(slug)` | `modules/app_factory.py` 또는 `registry_loader.py` | slug → Contract dict 로드. 없으면 None |
| B2 | `delete_app()` 연동 | `modules/app_factory.py` | 계산기 삭제 시 `docs/contract_schema/{slug}.yaml` 도 삭제 |
| B3 | dashboard Mode B 표시 개선 | `dashboard.py` | 저장 완료 후 "Contract 영속화 완료" 메시지 |

### C: CA-3+ (이번 범위 아님)

| # | 항목 | 이유 |
|---|------|------|
| C1 | `schema_id` / `schema_version` | JSON Schema validator 없음. 도입 전 불필요 |
| C2 | `generation_metadata` / `review_metadata` | 연말정산 HOLD 해결 후 Writer 파이프라인에서 의미 있음 |
| C3 | Contract Instance 버전 히스토리 | slug 중복 불가 정책으로 실익 없음 |
| C4 | Contract Instance ↔ Registry 불일치 자동 감지 UI | review_center 고도화 시 |
| C5 | `check_schema_drift()` 고도화 | 현재 schema drift 체크는 Contract vs App result 비교. Contract Instance와는 별개 |

---

## XI. 권장 구현안 (CA-2-4)

### `_save_contract_instance()` 설계

```python
def _save_contract_instance(slug: str, contract: dict) -> None:
    """Contract 전체를 docs/contract_schema/{slug}.yaml에 저장.
    slug: 계산기 슬러그 (Registry의 key와 동일)
    contract: build_contract() 결과 dict. None이면 noop."""
    if not contract:
        return
    import yaml
    from datetime import datetime, timezone, timedelta
    KST = timezone(timedelta(hours=9))
    _path = Path(__file__).parent.parent / "docs" / "contract_schema" / f"{slug}.yaml"
    _path.parent.mkdir(parents=True, exist_ok=True)
    instance = dict(contract)
    instance["generated_at"] = datetime.now(KST).isoformat()
    with open(_path, "w", encoding="utf-8") as f:
        yaml.dump(instance, f, allow_unicode=True, sort_keys=False)
    LOG.info("Contract Instance 저장: %s → %s", slug, _path)
```

### `save_app()` 수정 최소 diff

```python
    # [Step B'] Contract Instance 영속화 (Mode B만 해당)
    if not _v3_warn and app.get("_contract"):
        try:
            _save_contract_instance(new_slug, app["_contract"])
        except Exception as _cie:
            LOG.warning("Contract Instance 저장 실패(무시): %s", _cie)
```
삽입 위치: line 851 (Step B `except` 블록) 직후, Step C (calculator_index) 직전.

---

## XII. 보고서 요약: 결정이 필요한 항목

| 번호 | 질문 | 권장 |
|------|------|------|
| Q1 | `docs/contract_schema/` glob 안전성 | **안전** (별도 디렉토리, 기존 로더 무관) |
| Q2 | Contract Instance 파일명 | `{slug}.yaml` 단순 덮어쓰기 + `generated_at` |
| Q3 | 삽입 시점 | Step B 성공 후 (Step B') |
| Q4 | Registry 실패 시 Contract Instance | **생략** (`not _v3_warn` 조건) |
| Q5 | Mode A 처리 | noop (contract=None 시 파일 미생성) |
| Q6 | `schema_id`/`schema_version` | CA-3+로 이연 |
| Q7 | `load_contract_instance()` | B항목 (구현 가능, 필수 아님) |
| Q8 | `delete_app()` 연동 | B항목 (구현 가능, 필수 아님) |

---

**CA-2-4 구현 승인을 요청합니다.**

구현 범위(안): A1~A4 (Must-have) + B2 (`delete_app()` 연동) 포함 권장.  
B1(`load_contract_instance`)과 B3(dashboard 표시)는 옵션으로 의견 주시면 반영합니다.
