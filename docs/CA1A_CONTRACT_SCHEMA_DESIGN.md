# CA-1A: Contract Schema Registry 설계 문서

**버전**: 1.0.0  
**작성일**: 2026-08-10  
**단계**: Phase2-CA-1A (설계 문서 전용 — 코드 수정 없음)  
**전제 입력**: CA-0 보고서 (Contract 구조·Registry v3·legal_master 분석 결과)

---

## 목차

1. [배경 및 목적](#1-배경-및-목적)
2. [Contract Schema Registry 구조](#2-contract-schema-registry-구조)
3. [개별 Contract 구조 확정](#3-개별-contract-구조-확정)
4. [AUTO / TRANSFORM / MANUAL / HOLD 경계 최종 확정](#4-auto--transform--manual--hold-경계-최종-확정)
5. [hold_rules 목록](#5-hold_rules-목록)
6. [저장 위치·포맷 및 SSOT 관계](#6-저장-위치포맷-및-ssot-관계)
7. [desc 필드 공식화 — 기존 코드 불일치 지점](#7-desc-필드-공식화--기존-코드-불일치-지점)
8. [향후 검토 과제 (CA-1A 범위 외)](#8-향후-검토-과제-ca-1a-범위-외)

---

## 1. 배경 및 목적

v2.4.0에서 Contract 기반 App Factory 생성 파이프라인의 전체 라이프사이클이 검증됐다.
그러나 현재 Contract는 운영자가 대시보드에서 전 필드를 직접 입력하며, 아래 문제가 존재한다.

| 문제 | 현황 |
|------|------|
| `desc` 필드 비공식 | `build_contract()` 시그니처에 없음. 호출자가 수동으로 `contract["desc"]` 추가 |
| `formula_status` / `test_cases_status` 없음 | 미입력 / 검증실패 / 확정 상태를 `None` 하나로 뭉침 |
| 개별 Contract 비영속 | 세션 초기화 시 소멸 — 생성 이력·법적 근거 감사 추적 불가 |
| AUTO/TRANSFORM 경계 미정의 | Registry v3에서 어디까지 자동 제안 가능한지 기준 없음 |

CA-1A의 목적: 위 문제의 해결 구조를 설계 문서로 확정한다.
실제 코드 변경은 CA-1B / CA-2에서 수행한다.

---

## 2. Contract Schema Registry 구조

Contract Schema Registry는 "Contract 인스턴스가 따라야 하는 구조 정의"다.
개별 계산기 Contract 인스턴스와 다르다.

```
Contract Schema Registry (= 스키마 템플릿 정의)
├── schema_id           : str        — "calcmate_contract_v1"
├── schema_version      : str        — "1.0.0"  (SemVer)
├── required_fields     : list[str]  — Contract에서 반드시 있어야 하는 키
├── optional_fields     : list[str]  — 있어도 없어도 되는 키
├── auto_fields         : dict       — AUTO 분류 필드와 소스 정보
├── transform_fields    : dict       — TRANSFORM 분류 필드 (권장확인 / 필수확인 구분)
├── manual_fields       : list[str]  — MANUAL 필드 목록
├── hold_rules          : list[Rule] — HOLD 트리거 조건 목록
└── validation_rules    : dict       — 각 필드의 형식/값 검증 규칙
```

### 2-1. schema_version 버전 정책

SemVer (Major.Minor.Patch) 적용:

| 구분 | 변경 조건 | 예시 |
|------|----------|------|
| **Major** | 기존 Contract 인스턴스와 하위 호환이 깨지는 변경 (필드 삭제, 타입 변경, 필수 필드 추가) | `1.x.x → 2.0.0` |
| **Minor** | 하위 호환을 유지하면서 필드 추가, hold_rule 추가 | `1.0.x → 1.1.0` |
| **Patch** | 설명/예시 수정, 검증 규칙 문구 수정 | `1.0.0 → 1.0.1` |

> **주의**: schema_version 변경 시, 기존 Contract 인스턴스 파일의 `schema_version` 필드를 Migration 스크립트로 일괄 갱신해야 한다. CA-1A 설계 시점 버전은 `1.0.0`.

### 2-2. Contract Schema Registry 전체 필드 명세

```yaml
# docs/contract_schema/registry.yaml (예정)
schema_id: calcmate_contract_v1
schema_version: "1.0.0"

required_fields:
  - slug          # 확정 URL 식별자
  - name          # 계산기명
  - formula_status    # 상태 추적 필수
  - test_cases_status # 상태 추적 필수

optional_fields:
  - category
  - tier
  - input_fields
  - output_fields
  - formula
  - legal_refs
  - test_cases
  - scope_exclusions
  - desc
  - generation_metadata
  - review_metadata

auto_fields:
  slug:
    source: "Registry v3 slug"
    condition: "기존 계산기 재생성 시. 신규는 운영자 입력."
  name:
    source: "Registry v3 name"
    condition: "기존 계산기 재생성 시."
  category:
    source: "Registry v3 category"
    condition: "기존 계산기 재생성 시."
  desc:
    source: "Registry v3 card_desc + writer_context.calculation_story 조합"
    condition: "항상 초안 자동 생성. 운영자 권장 확인."

transform_fields:
  tier:
    source: "Registry v3 compute_type / difficulty"
    level: required_confirm   # 필수확인
    rule: "date_based → Tier1, dict/multi_output → Tier2-A, single/simple → Tier2-A"
    risk: "오분류 시 법적 검증 경로 자체가 잘못 태워짐"
  input_fields:
    source: "Registry v3 field_labels (input) + DB input_schema"
    level: required_confirm   # 필수확인
    rule: "field_labels keys ∩ DB input_schema keys. input/output 분리 선행 필요."
    risk: "오매핑 시 Contract Lock이 잘못된 필드를 AI에 강제"
  output_fields:
    source: "Registry v3 field_labels (output) + DB output_schema"
    level: required_confirm   # 필수확인
    rule: "input_fields와 동일 방식. 분리 필요."
    risk: "위와 동일"
  scope_exclusions:
    source: "legal_master forbidden_articles + forbidden_phrases"
    level: recommended_confirm  # 권장확인
    rule: "forbidden_articles 목록을 제외 조건 텍스트로 변환"
    risk: "틀려도 법적/금전적 오류로 직결되지 않음 (표시 텍스트)"

manual_fields:
  - formula        # 항상 MANUAL. formula_status로 상태 추적.
  - test_cases     # 항상 MANUAL. test_cases_status로 상태 추적.
  - legal_refs     # 운영자가 legal_master entity_id 선택

hold_rules:
  # → Section 5 참조

validation_rules:
  slug:
    type: str
    pattern: "^[a-z0-9][a-z0-9-]*$"
    max_length: 80
  name:
    type: str
    min_length: 1
    max_length: 200
  category:
    type: str
  tier:
    type: str
    allowed: ["Tier1", "Tier2-A", "Tier2-B"]
  input_fields:
    type: list[str]
    item_pattern: "^[a-z][a-z0-9_]*$"
  output_fields:
    type: list[str]
    item_pattern: "^[a-z][a-z0-9_]*$"
  formula:
    type: "str | dict | null"
    note: "validate_formula() 통과 시에만 formula_status=operator_confirmed 가능"
  formula_status:
    type: str
    allowed: ["not_generated", "ai_suggested", "pending_validation", "operator_confirmed"]
    note: "runtime 구현 기준 4개 상태 (CA-1B-3-B P2 문서 정합성 갱신)"
  test_cases:
    type: list[dict]
    item_keys_required: ["input", "expected"]
    note: "input/expected 모두 dict[str, number]"
  test_cases_status:
    type: str
    allowed: ["not_generated", "operator_confirmed"]
    note: "runtime 구현 기준 2개 상태 (CA-3-4 이후 formula_status와 분리 운영)"
  legal_refs:
    type: list[str]
    note: "legal_master entity_id 목록"
  desc:
    type: str
    max_length: 2000
  scope_exclusions:
    type: list[str]
  generation_metadata:
    type: dict
    required_keys: ["generated_at", "generator_version", "ai_model"]
  review_metadata:
    type: dict
    required_keys: ["reviewed_by", "reviewed_at", "hold_items"]
```

---

## 3. 개별 Contract 구조 확정

### 3-1. 전체 필드 명세

```python
{
    # ── 스키마 식별 ────────────────────────────────────────────
    "schema_id":      str,    # "calcmate_contract_v1"
    "schema_version": str,    # "1.0.0"

    # ── 기본 정보 (AUTO / TRANSFORM) ──────────────────────────
    "slug":           str,    # 확정 URL 식별자 (소문자·숫자·하이픈)
    "name":           str,    # 계산기명
    "category":       str,    # 카테고리 (예: "노동/고용법")
    "tier":           str,    # "Tier2-A" | "Tier2-B" | "Tier1"
    "desc":           str,    # 설명 (공식 필드, 이번 설계에서 확정)

    # ── 필드 명세 (TRANSFORM, 필수확인) ──────────────────────
    "input_fields":   list[str],   # 확정 입력 필드명 리스트
    "output_fields":  list[str],   # 확정 출력 필드명 리스트

    # ── 법령 참조 (MANUAL) ────────────────────────────────────
    "legal_refs":     list[str],   # legal_master entity_id 목록
                                   # (예: ["labor_standards_act_60"])

    # ── 수식 (MANUAL + 미확정 시 HOLD) ───────────────────────
    "formula":        "str | dict | None",
    "formula_status": str,    # 4개 상태값 (runtime 구현 기준):
                              # "not_generated"      — formula 미입력 (초기 상태)
                              # "ai_suggested"       — AI가 formula 제안 (운영자 확정 전)
                              # "pending_validation" — formula 존재하나 최종 검증/확정 전
                              # "operator_confirmed" — 운영자 확정 (validate_formula() 통과)

    # ── 적용 제외 (TRANSFORM, 권장확인) ──────────────────────
    "scope_exclusions": list[str],  # 명시적 제외 조건

    # ── 테스트 케이스 (MANUAL + 미확정 시 HOLD) ──────────────
    "test_cases":        list[dict],  # [{"input": {...}, "expected": {...}}]
    "test_cases_status": str,   # runtime 구현 기준 2개 상태값:
                                 #   "not_generated" / "operator_confirmed"

    # ── 생성 메타데이터 ───────────────────────────────────────
    "generation_metadata": {
        "generated_at":       str,   # ISO-8601 (UTC)
        "generator_version":  str,   # app_factory.py 기준 커밋 해시 또는 "manual"
        "ai_model":           str,   # 실제 사용된 AI 모델명 (없으면 "none")
        "source_registry_slugs": list[str],  # 참조한 Registry v3 slug 목록
    },

    # ── 검토 메타데이터 ───────────────────────────────────────
    "review_metadata": {
        "reviewed_by":   str | None,    # 검토자 (없으면 null)
        "reviewed_at":   str | None,    # ISO-8601 (UTC)
        "hold_items":    list[str],     # 현재 HOLD 상태인 hold_rule id 목록
        "locked_at":     str | None,    # CONTRACT LOCK 확정 시각 (저장 직전)
        "locked_by":     str | None,    # 확정자
    },
}
```

### 3-2. formula_status / test_cases_status 상태 전이

> **CA-1B-3-B P2 문서 정합성**: 아래는 **runtime 구현 기준** 상태값이다.
> `auto_disabled` / `error` 는 **현재 runtime 공식 상태값이 아니다** (프로덕션 코드 미사용 —
> CA-1A 초기 설계안으로, CA-3-4에서 AI Formula 제안 도입과 함께 `ai_suggested` /
> `pending_validation` 체계로 대체됨. 임의로 코드에 상태값을 추가하거나 rename하지 않는다).

**formula_status (runtime 4-state)**:

```
not_generated ──────────────────────────────────────────────────────────────┐
(formula 미입력 — build_contract 자동 도출: formula 없음 → not_generated) │
    │                                                                       │
    ├──(🤖 AI Formula 제안 → af_contract.formula_status = ai_suggested)──► ai_suggested
    │                                                                       │
    └──(운영자 formula 직접 입력 → build_contract 자동 도출)              │
                                        │                                   │
                                        ▼                                   ▼
                              pending_validation ──────────────► operator_confirmed
                              (formula 존재하나 최종          (✅ 운영자 확정 —
                               검증/확정 전)                   validate_formula() 통과)
    ▲                        ▲                                │
    │                        │                                │
    └──(운영자가 제안 내용을   └──(operator_confirmed /         │
       그대로 확정)              ai_suggested 상태에서           │
                                 formula 수정 감지 →            │
                                 pending_validation 복귀)       │
                                                                ▼
                                              CONTRACT LOCK 가능
                                              (formula: operator_confirmed
                                               test_cases: operator_confirmed 일 때)
```

**test_cases_status (runtime 2-state)**:

```
not_generated ──(테스트 케이스 입력)──► operator_confirmed
(build_contract 자동 도출:            (validate_formula_with_samples() 모두 match)
 test_cases 없음 → not_generated)
```

**상태 규칙**:
- `not_generated`: Contract 생성 직후, formula/test_cases를 아직 한 번도 입력하지 않은 상태 (`build_contract()` 자동 도출)
- `ai_suggested`: AI가 formula를 제안했지만 운영자가 아직 확정하지 않은 상태 (CA-3-4 신규)
- `pending_validation`: formula가 존재하지만 아직 최종 검증/확정되지 않은 상태 — `operator_confirmed`/
  `ai_suggested` 상태에서 formula가 수정되면 복귀 (CA-3-4 신규)
- `operator_confirmed`: 운영자가 입력/확정하고 `validate_formula()` 통과 (또는 test_cases의 경우
  `validate_formula_with_samples()` 모두 match)
- ~~`auto_disabled`~~: 자동 생성 불가 상태 — **runtime 미사용 (legacy 설계안)**
- ~~`error`~~: 검증 실패 상태 — **runtime 미사용**. 검증 실패 결과는 별도 `af_formula_validation`
  session_state로 보관하고 `pending_validation` 상태를 유지한다 (legacy 설계안)

**CONTRACT LOCK 전제 조건** (변경 금지 → 저장 허용):
- `formula_status == "operator_confirmed"` 또는 formula가 None이고 HOLD 아닌 경우
- `test_cases_status == "operator_confirmed"` 또는 test_cases가 빈 배열이고 법령 계산기 아닌 경우
- 모든 hold_rules가 해소된 경우

### 3-3. desc 필드 공식화

`desc`를 Contract의 공식 필드로 확정한다.

**역할 정의**:
- AI 생성 시 `sys1`의 계산기 설명 컨텍스트 (`generate_app()` u1 파라미터)
- Registry v3 `card_desc` / `writer_context` 초안 생성 소스
- 운영자가 법령 계산기의 적용 범위, 제외 조건, 특이사항을 기술하는 자유 텍스트

**공식화에 따른 코드 변경 위치** (실제 수정은 CA-1B에서):
→ Section 7 참조

---

## 4. AUTO / TRANSFORM / MANUAL / HOLD 경계 최종 확정

### 4-1. 최종 경계표

| Contract 필드 | 분류 | 확인 수준 | 소스 | 근거 |
|-------------|------|---------|------|------|
| `slug` | **AUTO** | 충돌 확인만 | Registry v3 slug | 1:1 직접 사용. 단 `_write_registry_v3()` 충돌 차단 전 slug 검증 필요 |
| `name` | **AUTO** | 불필요 | Registry v3 name | 1:1 직접 사용 |
| `category` | **AUTO** | 불필요 | Registry v3 category | 직접 사용. 미매핑 카테고리는 `labor_af` 폴백 (HOLD 아님) |
| `desc` | **TRANSFORM** | 권장확인 | Registry v3 `card_desc` + `writer_context.calculation_story` 조합 | 초안 자동 생성 가능. 틀려도 법적 오류 아님 |
| `tier` | **TRANSFORM** | **필수확인** | Registry v3 `compute_type` / `difficulty` | `date_based`→Tier1, 나머지→Tier2-A 추론. 오분류 시 법적 검증 경로 자체가 잘못 선택됨 |
| `input_fields` | **TRANSFORM** | **필수확인** | Registry v3 `field_labels`(input) + DB `input_schema` | field_labels에 input/output 구분 없음 — 분리 선행 필요. 오매핑 시 Contract Lock이 잘못된 필드 강제 |
| `output_fields` | **TRANSFORM** | **필수확인** | Registry v3 `field_labels`(output) + DB `output_schema` | 위와 동일 |
| `legal_refs` | **MANUAL** | 선택 확인 | 운영자가 legal_master entity_id 직접 선택 | Registry v3 `legal_refs` 필드로 후보 제안 가능하지만 최종 선택은 운영자 |
| `formula` | **MANUAL** | **직접 입력 + 검증** | — | calculation_flow가 자연어라 Python 식 자동 변환 불가. `formula_status` 추적 |
| `scope_exclusions` | **TRANSFORM** | 권장확인 | legal_master `forbidden_articles` 변환 | 틀려도 표시 텍스트 오류 수준 |
| `test_cases` | **MANUAL** | **직접 입력 + 검증** | — | formula 미확정 시 expected 자동 계산이 circular validation. `test_cases_status` 추적 |
| `schema_id` | **AUTO** | 불필요 | 고정값 `"calcmate_contract_v1"` | |
| `schema_version` | **AUTO** | 불필요 | 고정값 현재 버전 | |
| `generation_metadata` | **AUTO** | 불필요 | 생성 시점 자동 기록 | |
| `review_metadata` | **AUTO** (부분) | 운영자 확인 후 갱신 | 초기값 자동, 검토 후 운영자 갱신 | |

### 4-2. MANUAL 필드와 HOLD의 관계

MANUAL 필드는 **입력 주체가 운영자**라는 의미다.
HOLD는 **해당 값이 미확정 상태에서 다음 단계 진행이 차단**된다는 의미다.

```
formula:     MANUAL
  → 미입력 = formula_status: "not_generated" → HOLD-1 트리거
  → AI 제안 = formula_status: "ai_suggested" → HOLD-1 유지
  → 검증/확정 대기 = formula_status: "pending_validation" → HOLD-1 유지
  → 입력+검증통과 = formula_status: "operator_confirmed" → HOLD-1 해소

test_cases:  MANUAL
  → 비어있음 + 법령 계산기 = test_cases_status: "not_generated" → HOLD-2 트리거
  → 입력+일부 match 실패 = test_cases_status: "pending_validation"(실패 결과는
    별도 validation 저장) → HOLD-2 유지
  → 입력+전체 match = test_cases_status: "operator_confirmed" → HOLD-2 해소
```

---

## 5. hold_rules 목록

### 기본 5개 (CA-0 확정, 변경 금지)

| ID | 트리거 조건 | 차단 대상 | 해소 방법 |
|----|-----------|---------|---------|
| **HOLD-1** | `formula`가 `None` 또는 `formula_status != "operator_confirmed"` | CONTRACT LOCK + save_app() | 운영자가 formula 직접 입력 후 validate_formula() 통과 |
| **HOLD-2** | `test_cases`가 비어있음 AND 카테고리가 `CRITICAL_CATEGORIES`에 해당 | CONTRACT LOCK + save_app() | 운영자가 test_cases 입력 후 validate_formula_with_samples() 전체 match |
| **HOLD-3** | 참조 법령(`legal_refs` 경유)의 `confidence: medium` | 저장 허용, 경고 표시 (차단은 않음) | 운영자 명시적 확인 (`review_metadata.hold_items`에서 제거) |
| **HOLD-4** | `input_fields`/`output_fields` 자동 제안이 ambiguous — Registry `field_labels` 없거나 DB schema 조회 불가 | 자동 제안 생략, 운영자 직접 입력 요구 | 운영자 직접 입력 후 필드 비어있지 않으면 해소 |
| **HOLD-5** | `slug` 충돌 — `load_registry_v3()` 또는 DB에 동일 slug 존재 | Contract 생성 자체 차단 | 다른 slug로 변경 |

### 확장 가능 조건 (CA-1A 추가 발견)

| ID | 트리거 조건 | 비고 |
|----|-----------|------|
| **HOLD-6** | `tier == "Tier1"` AND `validation_mode == "skip"` (date_based 계산기) AND `formula`가 None이 아닌 경우 | date_based는 formula 검증을 건너뜀(`validation_mode: skip`). formula가 입력됐는데 검증이 안 되는 모순 상태. CA-2 설계 시 결정. |
| **HOLD-7** | `formula_status == "operator_confirmed"` AND `test_cases_status != "operator_confirmed"` AND `formula`가 dict (다중 출력) | 다중 출력 formula는 출력 간 의존성 오류 위험이 높음. test_cases로 전체 출력값 검증이 더 중요. CA-2 설계 시 결정. |

### HOLD-3 별도 처리 근거

HOLD-3는 **저장을 차단하지 않는다**. 이유:
- confidence=medium은 법적 불확실성이지 계산 오류가 아님
- 경고를 표시하고 `review_metadata.hold_items`에 기록해 추적 가능
- 완전 차단 시 실업급여·연말정산 계산기를 영구 생성 불가로 만들 위험

---

## 6. 저장 위치·포맷 및 SSOT 관계

### 6-1. 저장 경로 옵션 비교

#### 옵션 A: `docs/contract_schema/` 신규 디렉토리

```
docs/
├── contract_schema/
│   ├── registry.yaml        # Contract Schema Registry (스키마 정의)
│   └── instances/           # 개별 Contract 인스턴스
│       ├── annual-leave-remaining.yaml
│       ├── jeonse-vs-monthly.yaml
│       └── ...
├── registry/                # Registry v3 (Production Metadata SSOT)
│   ├── labor.yaml
│   └── ...
└── legal_master/            # 법령 엔티티 (법적 근거 SSOT)
    ├── labor.yaml
    └── ...
```

**장점**:
- 역할 분리 명확: Contract = 생성 의도 기록, Registry v3 = Production 메타데이터
- 기존 `docs/registry/*.yaml` 구조 변경 없음
- Contract 인스턴스가 Registry v3와 완전히 독립 — Production 영향 없음
- 감사 추적용 파일이 별도 디렉토리에 집중

**단점**:
- 새 디렉토리 관리 추가
- Contract 인스턴스와 Registry v3 엔트리 간 slug 동기화를 코드로 관리해야 함

#### 옵션 B: 기존 `docs/registry/*_af.yaml`에 `contract_snapshot` 서브키 추가

```yaml
# docs/registry/labor_af.yaml
annual-leave-remaining:
  # ... 기존 Registry v3 필드 ...
  contract_snapshot:
    schema_id: calcmate_contract_v1
    formula: {...}
    formula_status: operator_confirmed
    test_cases: [...]
```

**장점**: 파일 수 최소화, slug 동기화 자동

**단점**:
- Registry v3(Production Metadata SSOT)와 Contract(생성 의도 SSOT)가 섞임
- `_af.yaml`이 App Factory 자동 관리 파일인데 Contract 내용을 추가하면 충돌 가능
- `validate_against_contract()` 등 Contract 소비 경로에서 Registry를 읽어야 하는 의존성 생김
- 기존 `labor_af.yaml` 스키마 변경 → CA-1B 이후 작업 복잡도 증가

### 6-2. 권고안: **옵션 A 채택**

역할 분리 원칙이 더 중요하다.

```
Registry v3 (docs/registry/*.yaml)    = Production Metadata SSOT
                                         slug/status/tier/field_labels/review_checklist

Contract Schema Registry              = Contract 구조 정의 SSOT
(docs/contract_schema/registry.yaml)    schema_id/version/rules/hold_rules

Contract 인스턴스                      = 생성 당시 Contract SSOT
(docs/contract_schema/instances/)       formula/test_cases/legal_refs/review_metadata
                                         + 감사 추적 (generated_at/locked_at)

DB (calculators + app_templates)      = 실행/운영 데이터 SSOT
                                         input_schema/output_schema/html/formula(실행용)
```

### 6-3. 개별 Contract 인스턴스 — 영속 저장 판단

**판정: 영속 저장 필요**

근거:
1. **법적 감사 추적**: 법령 기반 계산기를 어떤 formula로, 어떤 legal_refs를 근거로 생성했는지 기록이 없으면 나중에 법령 변경 시 어떤 계산기를 업데이트해야 하는지 파악 불가
2. **Contract Lock 증거**: `CONTRACT LOCK`으로 AI를 강제한 원본 Contract가 없으면 AI 결과와 비교 재현이 불가
3. **세션 한계**: 현재 `st.session_state["af_contract"]`는 브라우저 탭 닫으면 소멸 — 저장 완료 이후에도 Contract 원본 접근 불가

**저장 포맷**: YAML (Registry v3와 동일 포맷, 인간 가독)

**파일명 규칙**: `{slug}.yaml`

**저장 시점**: `save_app()` 성공 직후 (DB + Registry v3 기록과 동시)

**수정 정책**: 불변(Immutable). 저장 후 수정 금지. 재생성 시 기존 파일을 `{slug}.v{timestamp}.yaml`로 아카이브하고 새 파일 생성.

### 6-4. SSOT 관계 다이어그램

```
운영자 입력
    │
    ▼
build_contract() ──→ Contract 인스턴스 (메모리)
    │                        │
    │                        │ validate_against_contract()
    │                        ▼
    │               generate_app_with_contract()
    │                        │ (AI 생성 + Contract Lock)
    │                        ▼
    │               save_app() ─────────────┬──────────────────────┐
    │                                       │                      │
    ▼                                       ▼                      ▼
docs/contract_schema/                docs/registry/          DB (calculators
instances/{slug}.yaml                *_af.yaml               + app_templates)
[Contract SSOT]                      [Production             [실행 데이터
 formula/test_cases                   Metadata SSOT]          SSOT]
 legal_refs/review_metadata           status/tier/            input_schema
 generated_at/locked_at               review_checklist        html/formula
```

**읽기 방향**:
- `validate_against_contract()`: Contract 인스턴스 읽음
- `load_registry_v3()`: Registry v3 읽음
- `execute_formula()`: DB formula 읽음
- 세 소스가 서로 읽지 않음 (단방향, 의존성 없음)

---

## 7. desc 필드 공식화 — 기존 코드 불일치 지점

`desc`를 Contract의 공식 필드로 확정하면 아래 위치를 CA-1B에서 수정해야 한다.
**이번 단계에서 수정하지 않는다.**

### 7-1. 불일치 지점 목록

| 파일 | 위치 | 현황 | 필요한 변경 |
|------|------|------|-----------|
| `modules/app_factory.py` | `build_contract()` 파라미터 (line 267) | `desc` 파라미터 없음 | `desc: str = ""` 파라미터 추가 + 반환 dict에 포함 |
| `modules/app_factory.py` | `generate_app_with_contract()` (line 381) | `contract.get("description", "") or contract.get("desc", "")` — 두 키 혼용 | `build_contract()`에 `desc` 추가 후 `contract.get("desc", "")` 단일 키로 통일 |
| `dashboard.py` | Mode B `build_contract()` 호출 (line 2293) | `desc=af_desc` 전달 없음 → AI가 Mode B에서 계산기 설명 컨텍스트를 받지 못함 | `build_contract(... desc=af_desc or "")` 추가 |
| `run_phase2_repro_test.py` | line 55 | `contract["desc"] = DESC` (수동 키 추가) | `build_contract(... desc=DESC)` 로 정식화 |
| `run_phase2_e2e_test.py` | 동일 패턴 | 동일 | 동일 |
| `run_save_e2e_test.py` | 동일 패턴 | 동일 | 동일 |
| `run_annual_leave_e2e.py` | 동일 패턴 | 동일 | 동일 |

### 7-2. dashboard Mode B 누락이 미치는 현재 영향

`dashboard.py` line 2293-2302에서 `build_contract()` 호출 시 `af_desc` (공통 설명 입력값)가 contract에 포함되지 않는다.

결과: `generate_app_with_contract()` → `generate_app()` → `u1 = f"설명: {desc}"` 에서 `desc = ""`이 됨.

AI는 Mode B에서 계산기 설명 없이 이름+카테고리만으로 스펙을 설계한다.
현재 Contract Lock의 `input_fields`/`output_fields`/`formula`가 강제하기 때문에 스키마 오류는 발생하지 않지만, **AI가 한국어 라벨(`labels` 필드)이나 HTML 설명 문구를 정확히 생성하지 못할 위험**이 있다.

### 7-3. 수정 순서 권장 (CA-1B)

```
1. build_contract(desc: str = "") 파라미터 추가
2. generate_app_with_contract()에서 단일 키 contract.get("desc", "") 사용
3. dashboard.py Mode B에서 build_contract(... desc=af_desc or "") 전달
4. 4개 E2E/repro 스크립트 build_contract() 호출 정식화
```

---

## 8. 향후 검토 과제 (CA-1A 범위 외)

다음은 이번 설계에 포함하지 않는다. CA-2 이후 별도 판단 필요.

### 8-1. formula_hint 필드 (legal_master 보강)

`legal_master/*.yaml`에 `formula_hint: str` 필드를 추가하면 Contract Builder가 Python 수식 초안을 제안할 수 있다. 예:
```yaml
labor_standards_act_60:
  formula_hint: |
    total_days: "15 + min(max(0, (years_of_service - 1) // 2), 10)"
    remaining_days: "total_days - used_days"
```

현재 `calculation_flow`가 한국어 자연어라 직접 사용 불가. `formula_hint` 추가 시 legal_master 편집 공수 발생.

결정 기준: formula_hint를 누가 입력하는가 (법령 전문가 vs 운영자) — CA-2 설계 시 결정.

### 8-2. calculation_flow → Python 식 변환기

`calculation_flow` 텍스트에서 한국어 변수명을 Registry `field_labels` 키로 매핑하는 변환기. 구현 복잡도가 높고 오변환 위험이 있어 CA-1A에서 제외.

### 8-3. test_cases 경계값 자동 추출 (구조화 테이블 한정)

`legal_master`의 `benefit_days_table` (실업급여) 같은 구조화 테이블에서 경계값 test_case 자동 추출이 이론적으로 가능하다. 대상이 제한적이고 검증 방법 설계가 필요해 CA-2 이후 판단.

### 8-4. HOLD-6 / HOLD-7 확정

Section 5에서 "확장 가능 조건"으로 기재한 HOLD-6(date_based+formula 모순), HOLD-7(다중 출력+test_cases 미검증). CA-2 Contract Builder 설계 시 운영 경험을 보고 확정.

---

## 요약 — CA-1B / CA-2 착수 전제 확정 사항

| 항목 | 확정 내용 |
|------|---------|
| Contract Schema 버전 | `1.0.0` (SemVer 정책 정의됨) |
| `desc` | 공식 필드 확정. CA-1B에서 `build_contract()` 파라미터 추가 |
| `formula_status` / `test_cases_status` | runtime 구현 기준 확정 — formula_status 4개 (`not_generated / ai_suggested / pending_validation / operator_confirmed`), test_cases_status 2개 (`not_generated / operator_confirmed`) |
| formula / test_cases | 항상 MANUAL. CA-1A 이후 자동화 불가 상태로 고정 |
| HOLD 기준 | 5개 기본 + 2개 확장 후보 확정 |
| Contract 인스턴스 영속 저장 | **필요**. `docs/contract_schema/instances/{slug}.yaml` |
| Schema Registry 위치 | `docs/contract_schema/registry.yaml` (신규 디렉토리, 옵션 A) |
| SSOT 역할 분리 | Registry v3 = Production Metadata / Contract 인스턴스 = 생성 의도 / DB = 실행 데이터 |
| input_fields/output_fields 분리 | CA-1B에서 Registry `field_labels`에 `input_labels`/`output_labels` 분리 선행 필요 |
