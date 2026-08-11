# CA-4 사전조사 보고서 — HOLD/Legal Master/기술부채 정리

**날짜**: 2026-08-11  
**조사 단계**: 사전조사 전용 (코드 수정 0건)  
**조사 기준**: CA-3 COMPLETE 이후 상태

---

## 1. 조사 목적

CA-3 Formula Suggestion 시스템 완료 후 다음 4개 영역의 구현 범위와 순서를 확정한다.

- **CA-4-A**: HOLD → READY 전환 Dashboard 연결
- **CA-4-B**: legal_master 확장
- **CA-4-C**: Python 3.14 기술부채 (ast.Num)
- **CA-4-D**: Registry 미커밋 변경 정리

---

## 2. 현재 기준선

| 항목 | 값 |
|------|---|
| Regression | 554 PASS / 1 known FAIL |
| known FAIL | `test_full_pipeline_execution` (WordPress 연결 실패) |
| Python 버전 | 3.12.7 |
| CA-2 | COMPLETE |
| CA-3 | COMPLETE |
| 마지막 커밋 | `a4de724 feat(app-factory): complete Contract-based generation lifecycle` |

---

## 3. CA-4-A: 현재 HOLD 구조

### 두 종류의 HOLD 시스템이 병존한다

| 구분 | 이름 | 발동 시점 | 저장 위치 | 현재 상태 |
|------|------|----------|----------|---------|
| 1 | **Pre-generation Soft Gate** (HOLD-1/2/3) | `build_contract()` 직후, AI 호출 전 | 메모리 (session state) | ✅ 구현 완료 |
| 2 | **Post-save LEGAL HOLD** | `save_app()` 이후 | `docs/registry/*_af.yaml` (`status: HOLD`) | ✅ 구현 완료 |

### HOLD-1/2/3 (Pre-generation Soft Gate)

**구현 위치**: `check_hold_rules()` → `app_factory.py:340`  
**Dashboard 연결**: `dashboard.py:2488-2491` (Contract 기반 생성 버튼 핸들러)

```python
_hold = AF.check_hold_rules(_contract)
for _hm in _hold["messages"]:
    st.warning(f"⚠️ {_hm}")
```

**특성**: 경고만 표시. 생성 자체를 차단하지 않는다. 운영자가 결정.

### LEGAL HOLD (Post-save)

**저장**: `_write_registry_v3()` → `status: HOLD` (모든 App Factory 계산기는 초기 HOLD)

**Dashboard 연결** (`dashboard.py:1803-1887`):
- 🔴 LEGAL HOLD 배지 표시
- 체크리스트 UI (critical/advisory)
- `promote_to_ready()` 버튼 — **이미 완전 구현됨**

**`extract_checklist()` 자동 항목** (`review_center.py:49-`):
| ID | 조건 | Severity |
|----|------|---------|
| `formula_accuracy` | formula 있고 date_based 아님 | critical |
| `legal_basis` | 항상 (legal_refs 있/없에 따라 표시 변경) | critical/advisory |
| `formula_cap` | formula에 min()/max() 포함 시 | critical |
| `rate_constant` | formula에 소수점 상수 포함 시 | critical |
| `base_year` | critical category 시 | critical |
| `default_values` | input_schema에 default 있을 때 | critical |
| `edge_cases` | compute_rules 있을 때 | critical |
| `schema_match` | _schema_drift 있을 때 | critical |

---

## 4. HOLD → READY 현재 흐름

### 현재 완전 구현된 흐름

```
[계산기 저장(save_app)]
        │
        ↓
[Registry status: HOLD]
        │
        ↓  (Dashboard "계산기 목록" 페이지)
[🔴 LEGAL HOLD 배지 표시]
        │
        ↓
[체크리스트 자동 추출(extract_checklist)]
  ├── 🔴 필수: formula_accuracy, legal_basis, rate_constant, base_year ...
  └── 🟡 권장: 기타 advisory 항목
        │
        ↓  (운영자가 🔴 필수 항목 전체 체크)
[✅ READY 전환 버튼 활성화]
        │
        ↓
[promote_to_ready() → Registry status: READY]
```

**결론**: LEGAL HOLD → READY 전환 흐름은 Phase3-3에서 이미 완전 구현됨.  
`promote_to_ready()` (app_factory.py:237)는 Dashboard (dashboard.py:1884)에 이미 연결되어 있음.

### 발견된 Gap — CA-4-A 실제 구현 범위

#### Gap A-1: legal_refs UI 부재 (중요)

**현재 상태**: Dashboard Contract Builder에 `legal_refs` 입력 필드 없음.

```python
# dashboard.py:2483 — legal_refs가 하드코딩으로 빈 리스트
AF.build_contract(
    slug=_slug_clean,
    ...
    desc=af_desc or "",
    # legal_refs=[] 가 전달되지 않음 → 기본값 [] 사용
)
```

그리고 `suggest_formula()` 호출 시:
```python
# dashboard.py:2283 — legal_refs 하드코딩 빈 리스트
_sf_result = AF.suggest_formula(
    cfg=cfg, ...,
    legal_refs=[],  ← 항상 빈 리스트
)
```

**영향**:
1. HOLD-3 (confidence=medium legal_ref 경고)가 Dashboard에서 절대 발동할 수 없음
2. suggest_formula()가 legal_master의 `calculation_flow`를 참조할 수 없음
3. LEGAL HOLD 체크리스트의 `legal_basis` 항목이 "⚠️ legal_refs 미입력" 으로 항상 표시됨

#### Gap A-2: formula_status가 LEGAL HOLD 체크리스트에 미반영

**현재 상태**: `extract_checklist()`의 `formula_accuracy` 항목은 formula 존재 여부만 확인.  
`formula_status == operator_confirmed` 여부를 별도로 체크하지 않음.

**영향**: formula가 `pending_validation` 상태로 저장된 계산기도 `formula_accuracy` 체크 후 READY 가능.  
운영자가 수동으로 formula 상태를 확인해야 하지만 명시적 경고 없음.

#### Gap A-3: HOLD-1/2/3와 LEGAL HOLD 체크리스트 간 연결 없음

**현재 상태**: HOLD-1/2/3는 생성 전 경고이고, LEGAL HOLD 체크리스트는 생성 후 확인 항목.  
두 시스템이 서로 데이터를 공유하지 않음.

**영향**: 비교적 낮음. 운영자가 LEGAL HOLD 체크 시 formula_accuracy, legal_basis 항목을 직접 확인하도록 설계되어 있어 실질적 품질 보호는 유지됨.

---

## 5. Dashboard 연결점

### CA-4-A 구현 시 삽입 위치

**Gap A-1 해결**: Contract Builder expander (`dashboard.py:2225`) 내부에 `legal_refs` text_input 추가

삽입 위치 후보:
```python
# dashboard.py 약 2240-2244 (input_fields, output_fields 아래)
_af_legal_refs = st.text_input(
    "참조 법령 (entity_id, 쉼표 구분)", 
    placeholder="labor_standards_act_60, worker_retirement_benefit_act_8",
    key="af_contract_legal_refs",
    help="legal_master의 entity_id. HOLD-3 및 suggest_formula() 법령 참조에 사용됩니다."
)
```

그리고 suggest_formula() 호출 시(약 line 2278):
```python
legal_refs=[f.strip() for f in (_af_legal_refs or "").split(",") if f.strip()]
```

**Gap A-2 해결**: `extract_checklist()`에 `formula_status` 체크 항목 추가 (review_center.py)

**구현 범위 요약**:
- 수정 파일: `dashboard.py` (legal_refs UI), `modules/review_center.py` (checklist 항목)
- 신규 파일: 없음
- 예상 규모: `dashboard.py` +20줄, `review_center.py` +15줄

---

## 6. CA-4-B: legal_master 현황

### 전체 엔티티 목록

**파일**: `docs/legal_master/labor.yaml`, `employment.yaml`, `insurance.yaml`, `tax.yaml`  
**총 엔티티 수**: **8개**

| entity_id | 법령 | 조항 | confidence | calc_flow | 관련 계산기 |
|-----------|------|------|-----------|-----------|------------|
| `labor_standards_act_55` | 근로기준법 | 제55조 | **HIGH** | ✅ 4단계 | 주휴수당 |
| `worker_retirement_benefit_act_8` | 근로자퇴직급여 보장법 | 제8조 | **HIGH** | ✅ 5단계 | 퇴직금 |
| `labor_standards_act_60` | 근로기준법 | 제60조 | **HIGH** | ✅ 4단계 | 연차수당 |
| `employment_insurance_act_40` | 고용보험법 | 제40조 | **MEDIUM** | ✅ 7단계 | 실업급여 |
| `employment_insurance_act_70` | 고용보험법 | 제70조 | **HIGH** | ✅ 4단계 | 육아휴직급여 |
| `four_major_insurances` | 4대보험 복합 | 복합 | **HIGH** | ✅ 7단계 | 4대보험 |
| `income_tax_act_137` | 소득세법 | 제137조 | **MEDIUM** | ✅ 6단계 | 연말정산 |
| `income_tax_act_127` | 소득세법 | 제127조 | **HIGH** | ✅ 5단계 | 3.3% 원천징수 |

### confidence 분포

| confidence | 엔티티 수 | 해당 entity_id |
|-----------|---------|--------------|
| HIGH | 6개 | labor_55, retire_8, labor_60, insurance_70, four_major, tax_127 |
| MEDIUM | 2개 | employment_40, income_tax_137 |
| LOW | 0개 | — |

### calculation_flow 분포

**모든 8개 엔티티에 `calculation_flow` 존재** — 완성도 100%.

**Type D 트리거 항목**:
| entity_id | Type D 키워드 | AI Formula 영향 |
|-----------|-------------|--------------|
| `employment_insurance_act_40` | "매년 변경", "별표", "나이·피보험기간" | → AI BLOCKED (Type D) |
| `employment_insurance_act_70` | "매년 변경" | → AI BLOCKED (Type D) |
| `four_major_insurances` | "매년 변경" | → AI BLOCKED (Type D) |
| `income_tax_act_137` | 없음 | → AI 가능 (단, confidence=MEDIUM → HOLD-3) |

**Type A/B 가능한 엔티티** (AI Formula 제안 가능):
| entity_id | 계산기 | Type |
|-----------|-------|------|
| `labor_standards_act_55` | 주휴수당 | Type A (단순 곱셈) |
| `worker_retirement_benefit_act_8` | 퇴직금 | Type A (단순 곱셈) |
| `labor_standards_act_60` | 연차수당 | Type A (단순 곱셈) |
| `income_tax_act_137` | 연말정산 | Type A (HOLD-3 경고 발동) |
| `income_tax_act_127` | 3.3% 원천징수 | Type A (단순) |

---

## 7. legal_master Gap 분석

### Gap B-1: Dashboard legal_refs UI 부재 (확인된 주요 Gap)

**현재**: `suggest_formula()` 호출 시 `legal_refs=[]` 하드코딩.  
**영향**: legal_master의 calc_flow를 활용한 정교한 AI Formula 제안 불가.  
**해결**: Dashboard Contract Builder에 `legal_refs` 텍스트 입력 추가 (Gap A-1과 동일).

### Gap B-2: MEDIUM confidence 엔티티 데이터 갱신 필요성

**`employment_insurance_act_40`** (confidence=medium):
- 이유: 상한액(1일 66,000원, 2024년 기준), 소정급여일수(별표)가 **매년 변경**
- 갱신 방법: law.go.kr / 고용노동부 공식 자료 확인 후 confidence=high 전환 가능
- 단, 별표 데이터는 AI Formula에서 하드코딩 불가 → Type D 유지가 올바름

**`income_tax_act_137`** (confidence=medium):
- 이유: 세율 구간(6~45%), 공제 규정 등 복잡한 조건 존재
- 갱신 방법: 국세청 홈택스 / law.go.kr 교차 검증 후 단계별 공제 흐름 구체화
- 현재 deduction_rules 필드에 상세 데이터 이미 있음 (2025 귀속/2026 연말정산 기준)

### Gap B-3: 신규 엔티티 필요 가능성

현재 legal_master에 없는 계산기 범주:
- 병역/공무 카테고리: 없음 (현재 계산기도 없음 — 문제 아님)
- 연차 잔여일 계산기: `labor_standards_act_60` 참조 가능 — 추가 엔티티 불필요
- 3.3% 프리랜서 계산기: `income_tax_act_127` 이미 존재

**결론**: 신규 엔티티 추가는 현재 시점에서 긴급하지 않음. 우선 legal_refs UI 연결이 선행 과제.

### Gap B-4: Dashboard에서 legal_master 엔티티 목록 참조 불가

**현재**: 운영자가 entity_id를 직접 타이핑 (오타 가능성).  
**이상적**: legal_refs 입력 시 entity_id 자동완성 또는 드롭다운.  
**범위**: CA-4-B 구현 시 포함 여부 결정 필요.

---

## 8. CA-4-C: ast.Num 조사

### 사용 위치

**파일**: `modules/formula_engine.py` line 56-57 (단 1개소)

```python
if isinstance(node, ast.Constant):     # line 52 — Python 3.8+ 정상 처리
    if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    raise FormulaError(f"허용되지 않은 상수: {node.value!r}")
if isinstance(node, ast.Num):  # py<3.8 호환  ← line 56
    return node.n                               ← line 57
```

### Python 버전 영향

| 버전 | ast.Num 상태 | 리터럴(1.5) 노드 타입 | 영향 |
|------|------------|-------------------|------|
| < 3.8 | 정상 | `ast.Num` | lines 56-57이 실행됨 |
| 3.8 ~ 3.13 | deprecated | `ast.Constant` | lines 56-57은 도달 불가(dead code), 단 isinstance 호출 자체가 DeprecationWarning 발생 |
| **3.12.7 (현재)** | **deprecated** | **`ast.Constant`** | **494개 DeprecationWarning 발생** |
| 3.14 | 제거 | `ast.Constant` | `AttributeError: module 'ast' has no attribute 'Num'` → 코드 완전 파손 |

### 실행 경로 확인

```
python -c "import ast; tree = ast.parse('1.5', mode='eval'); print(type(tree.body).__name__)"
→ Constant
```

Python 3.12에서 `ast.parse('1.5')` → `ast.Constant` 노드 생성.  
**line 52-55가 먼저 매칭되므로 lines 56-57은 절대 실행되지 않는다 (dead code).**

### 수정 권장안

```python
# 삭제 대상 (lines 56-57 전체 제거)
if isinstance(node, ast.Num):  # py<3.8 호환
    return node.n
```

**수정 후 동작**:
- `ast.Constant` 처리 (line 52-55) → 기존과 동일
- DeprecationWarning 494개 → **0개**
- Python 3.14 호환성 확보

### 수정 파일 및 규모

| 파일 | 변경 | 규모 |
|------|------|------|
| `modules/formula_engine.py` | line 56-57 삭제 | **-2줄** |
| 테스트 파일 | 없음 | 변경 불필요 |

**Regression 위험**: 없음. Dead code 삭제이며, 55개 formula 테스트 모두 통과 예상.

---

## 9. CA-4-D: Git/Registry 변경 조사

### 현재 Git 상태 (2026-08-11 기준)

**마지막 커밋**: `a4de724 feat(app-factory): complete Contract-based generation lifecycle`

#### 추적 파일 수정 (tracked modified — 14개)

| 파일 | 변경 내용 | 분류 |
|------|----------|------|
| `dashboard.py` | CA-3-4 AI Formula 버튼 +188줄 | **A: 커밋 필수** |
| `modules/app_factory.py` | CA-3 완전 구현 +395줄 | **A: 커밋 필수** |
| `tests/test_formula_contract.py` | CA-3 테스트 44개 +426줄 | **A: 커밋 필수** |
| `tests/test_review_center.py` | review_center 테스트 +32줄 | **A: 커밋 필수** |
| `docs/registry/labor_af.yaml` | App Factory _af 엔트리 +6줄 | B: 의도된 변경 |
| `docs/registry/realty_af.yaml` | App Factory _af 엔트리 +9줄 | B: 의도된 변경 |
| `docs/registry/employment.yaml` | input_labels/output_labels 메타데이터 +14줄 | B: 의도된 변경 |
| `docs/registry/insurance.yaml` | input_labels/output_labels 메타데이터 +7줄 | B: 의도된 변경 |
| `docs/registry/labor.yaml` | input_labels/output_labels 메타데이터 +16줄 | B: 의도된 변경 |
| `docs/registry/tax.yaml` | input_labels/output_labels 메타데이터 +11줄 | B: 의도된 변경 |
| `logs/content_pipeline/pipeline_p_*.json` (11개) | 파이프라인 실행 로그 갱신 | B: 운영 데이터 |
| `tests/snapshots/competitive_analysis_snapshot.json` | 테스트 스냅샷 갱신 | B: 의도된 변경 |
| `modules/formula_engine.py` | (세션 시작 시점 미변경 — 조사 대상 아님) | — |
| `modules/review_center.py` | (세션 시작 시점 미변경 — 조사 대상 아님) | — |

**기존 Registry(non-_af) 변경 특성**:
- `employment.yaml`, `insurance.yaml`, `labor.yaml`, `tax.yaml`: CA-2 시점에 `_build_v3_entry()`가 `input_labels`/`output_labels` 필드를 추가한 부산물
- formula, input_schema, output_schema 등 기능 데이터는 변경 없음
- 기존 9개 계산기 슬러그 변경 없음 → 기능 영향 없음

#### 비추적 파일 (untracked — 22개)

| 파일/디렉토리 | 분류 | 처리 방향 |
|------------|------|---------|
| `tests/test_e2e_ca35.py` | **A: 커밋 필수** | git add |
| `tests/test_suggest_formula.py` | **A: 커밋 필수** | git add |
| `docs/CA1A_CONTRACT_SCHEMA_DESIGN.md` | A: 커밋 | git add |
| `docs/CA1B0_PREFLIGHT_REPORT.md` | A: 커밋 | git add |
| `docs/CA2_*.md` (8개 보고서) | A: 커밋 | git add |
| `docs/CA3_*.md` (7개 보고서) | A: 커밋 | git add |
| `docs/CA3_FINAL_REPORT.md` | **A: 커밋 필수** | git add |
| `docs/CA3_F_PRE_INVESTIGATION_REPORT.md` | **A: 커밋 필수** | git add |
| `docs/contract_schema/` (인스턴스 디렉토리 + registry.yaml) | B: 커밋 | git add |
| `docs/_backup_ca1b/` | **D: 보류** | 내용 확인 후 결정 |
| `_secret_replace2.txt` | **C: 절대 커밋 금지** | .gitignore 추가 검토 |
| `test_output.txt` | C: 임시 파일 | 삭제 가능 |
| `test_upload.txt` | C: 임시 파일 | 삭제 가능 |

#### 커밋 제안 단위

**커밋 1** (CA-3 구현 코어):
- `dashboard.py`, `modules/app_factory.py`, `tests/test_formula_contract.py`, `tests/test_review_center.py`, `tests/test_e2e_ca35.py`, `tests/test_suggest_formula.py`
- 메시지: `feat(ca3): implement AI Formula suggestion system with Dashboard integration`

**커밋 2** (문서 + Registry 메타데이터):
- `docs/CA*.md` (모든 보고서), `docs/registry/*.yaml` (6개), `docs/contract_schema/`
- 메시지: `docs(ca3): add investigation reports, update registry metadata`

**커밋 3** (운영 로그):
- `logs/content_pipeline/*.json`, `tests/snapshots/competitive_analysis_snapshot.json`
- 메시지: `chore: update pipeline logs and test snapshots`

---

## 10. CA-4-A~D 의존관계

### Q1: CA-4-A 전에 legal_master 확장이 필요한가?

**A: 아니다.** CA-4-A의 핵심 Gap(legal_refs UI 추가)은 legal_master 엔티티 추가 없이 구현 가능.  
단, legal_refs UI 추가(Gap A-1)는 CA-4-A와 CA-4-B의 공통 선행 작업이다.

### Q2: CA-4-B 전에 Dashboard legal_refs UI가 필요한가?

**A: 그렇다.** legal_master를 Dashboard에서 활용하려면 legal_refs UI가 선행되어야 한다.  
legal_master 데이터는 이미 충분하므로, UI 연결이 먼저다.

### Q3: CA-4-C는 독립 처리 가능한가?

**A: 그렇다.** `formula_engine.py` 2줄 삭제 — 완전 독립적. 가장 먼저 처리하는 것이 합리적.

### Q4: CA-4-D는 전에 해야 하는가, 마지막에 해야 하는가?

**A: 먼저다.** CA-3 구현을 커밋으로 정리한 뒤 CA-4 구현을 시작해야 커밋 히스토리가 명확해짐.  
특히 Category A 파일(dashboard.py, app_factory.py 등)을 커밋하지 않으면 CA-4 변경과 CA-3 변경이 섞인다.

### Q5: 단계적 분리가 안전한가?

**A: 그렇다.** 각 CA-4 서브 항목은 독립성이 높다.

| 항목 | 다른 항목 의존 | 독립 구현 가능 |
|------|-------------|-------------|
| CA-4-C (ast.Num 제거) | 없음 | ✅ 완전 독립 |
| CA-4-D (커밋 정리) | 없음 | ✅ 완전 독립 |
| CA-4-A (legal_refs UI) | CA-4-D 선행 권장 | ✅ 거의 독립 |
| CA-4-B (legal_master) | CA-4-A (legal_refs UI) 선행 필요 | ⚠️ CA-4-A 의존 |

---

## 11. 예상 수정 파일

| CA-4 항목 | 수정 파일 | 신규 파일 |
|----------|---------|---------|
| CA-4-A | `dashboard.py`, `modules/review_center.py` | 없음 |
| CA-4-B | `dashboard.py` (legal_refs UI) | 없음 (데이터 보강 시 `docs/legal_master/*.yaml`) |
| CA-4-C | `modules/formula_engine.py` | 없음 |
| CA-4-D | 없음 (커밋 작업) | 없음 |

---

## 12. 예상 변경 규모

| CA-4 항목 | 예상 추가 | 예상 삭제 | 총 규모 |
|----------|---------|---------|------|
| CA-4-A (legal_refs UI + checklist 항목) | ~35줄 | ~0줄 | **소규모** |
| CA-4-B (데이터 보강 - 선택) | ~20줄/엔티티 | 0줄 | **소규모** |
| CA-4-C (ast.Num 제거) | 0줄 | **2줄** | **최소** |
| CA-4-D (커밋) | 없음 | 없음 | **0줄** |

전체 CA-4 구현 규모: **~35줄 추가 / 2줄 삭제** (데이터 보강 미포함 시)

---

## 13. Regression 위험

| CA-4 항목 | Regression 위험 | 근거 |
|----------|---------------|------|
| CA-4-A (legal_refs UI 추가) | 낮음 | Dashboard UI 추가, 기존 로직 미변경 |
| CA-4-B (데이터 보강) | 매우 낮음 | YAML 데이터만 변경, 코드 없음 |
| CA-4-C (ast.Num 2줄 삭제) | **없음** | Dead code 삭제, 모든 테스트 동일 통과 예상 |
| CA-4-D (커밋) | 없음 | Git 작업만, 코드 변경 없음 |

---

## 14. Mode A 영향

| CA-4 항목 | Mode A 영향 |
|----------|-----------|
| CA-4-A (legal_refs UI) | 없음. Contract Builder(Mode B) expander에만 추가 |
| CA-4-B (legal_master) | 없음. legal_master는 suggest_formula()만 참조, Mode A는 미사용 |
| CA-4-C (ast.Num) | 없음. formula_engine은 Mode A/B 공통이지만 동작 변경 없음 |
| CA-4-D (커밋) | 없음 |

---

## 15. Blog/WordPress 영향

CA-4-A~D 어떤 항목도 Blog 생성, WordPress 게시, 콘텐츠 파이프라인에 영향을 주지 않는다.

- `suggest_formula()`는 Dashboard Mode B 전용 함수 → Blog 경로 없음
- `legal_refs` UI 추가 → Dashboard Contract Builder에만 영향
- `formula_engine.py` ast.Num 제거 → 계산기 실행 엔진, Blog/WordPress 미관여

---

## 16. 권장 구현 순서

```
CA-4-D  →  CA-4-C  →  CA-4-A  →  CA-4-B
```

| 순서 | 항목 | 이유 |
|------|------|------|
| 1 | **CA-4-D** | CA-3 작업 커밋 정리 → 깔끔한 베이스라인 확보 |
| 2 | **CA-4-C** | 2줄 삭제, 제로 리스크 → Regression 기준선 즉시 개선 (494 경고 제거) |
| 3 | **CA-4-A** | legal_refs UI 추가 → HOLD-3 기능 완성 + contract builder 완성도 향상 |
| 4 | **CA-4-B** | legal_master 데이터 보강 → 법적 검증 강화 (데이터 준비 필요 시 분리 진행) |

---

## 17. CA-4 세부 단계 제안

### CA-4-1: 커밋 정리 (CA-4-D)

- CA-3 전체 구현 3회 커밋 (코어, 문서, 로그)
- `.gitignore`에 `_secret_replace2.txt`, `test_output.txt`, `test_upload.txt` 추가 검토
- `docs/_backup_ca1b/` 내용 확인 후 처리

### CA-4-2: ast.Num 제거 (CA-4-C)

- `modules/formula_engine.py` 56-57줄 삭제
- Regression 실행 (554 PASS 확인)
- 커밋

### CA-4-3: legal_refs UI 연결 (CA-4-A + CA-4-B 공통)

- Dashboard Contract Builder expander에 `legal_refs` text_input 추가 (key="af_contract_legal_refs")
- `suggest_formula()` 호출 시 legal_refs 전달
- `build_contract()` 호출 시 legal_refs 전달
- `AF_SESSION_DISCARD_KEYS`에 `"af_contract_legal_refs"` 추가
- 테스트: HOLD-3 발동 확인
- 커밋

### CA-4-4: formula_status 체크리스트 반영 (CA-4-A)

- `extract_checklist()`에 `formula_status` 확인 항목 추가 (if formula_status != operator_confirmed → critical)
- `_save_contract_instance()`에서 formula_status를 app dict에 삽입하거나 Registry entry에 기록
- 테스트 추가
- 커밋

### CA-4-5: legal_master 데이터 보강 (CA-4-B, 선택)

- `employment_insurance_act_40` confidence 갱신 (고용노동부 최신 공식 자료 확인 후)
- `income_tax_act_137` confidence 갱신 (국세청 홈택스 확인 후)
- 공식 데이터 없이 수정 금지

---

## 18. 구현 전 승인 필요사항

| # | 승인 필요 사항 | 이유 |
|---|-------------|------|
| 1 | **CA-4-3 legal_refs UI 형태 확인** | text_input(직접 입력) vs dropdown(엔티티 목록) — UX 결정 필요 |
| 2 | **CA-4-4 formula_status 체크리스트 추가 범위** | `extract_checklist()` 수정 vs Dashboard만 수정 — 아키텍처 결정 |
| 3 | **CA-4-1 커밋 대상 파일 확인** | `docs/_backup_ca1b/` 처리 방향, `test_output.txt` 삭제 여부 |
| 4 | **CA-4-5 법령 데이터 보강 시점** | 공식 자료 준비 완료 시점 — 별도 진행 vs CA-4 통합 |

---

## 19. 최종 권고

### CA-4-A (HOLD → READY Dashboard 연결)

**CONDITIONAL PASS**

- LEGAL HOLD → READY 전환은 이미 구현 완료 (Dashboard lines 1803-1887)
- **실제 구현 과제**: Gap A-1 (legal_refs UI) + Gap A-2 (formula_status 체크리스트 반영)
- 규모: ~35줄 추가, 낮은 리스크
- legal_refs UI는 CA-4-A와 CA-4-B 공통 선행 작업으로 처리

### CA-4-B (legal_master 확장)

**CONDITIONAL PASS**

- legal_master 엔티티 8개, 모두 calc_flow 완비
- **실제 구현 과제**: Dashboard legal_refs UI 연결 (Gap B-1)
- MEDIUM confidence 2개 엔티티는 법적 공식 자료 확보 후 갱신 (급하지 않음)
- 법령 내용 임의 생성 금지 원칙 유지

### CA-4-C (ast.Num 제거)

**PASS**

- 2줄 삭제, dead code, zero risk
- Python 3.14 대비 필수 작업
- 즉시 진행 가능

### CA-4-D (Registry 미커밋 변경 정리)

**PASS**

- 변경 분류 완료 (A/B/C/D)
- Category C (_secret_replace2.txt) 절대 미포함 확인
- 커밋 순서: CA-3 코어 → 문서 → 로그

**전체 CA-4 권장 시작**: CA-4-D → CA-4-C (즉시, 코드 수정 최소) → CA-4-3 (legal_refs UI) → CA-4-4 → CA-4-5(선택)
