# CA-1B-0: Registry 실수정 전 안전장치 및 대상 확정 보고서

**작성일**: 2026-08-10  
**단계**: Phase2-CA-1B-0 (조사·백업·확정 전용 — 코드/YAML 수정 없음)  
**전제**: 이 보고서의 모든 산출물은 CA-1B-1 / CA-1B-2 착수 전 승인 베이스라인.

---

## 목차

1. [백업 완료 확인](#1-백업-완료-확인)
2. [Git 상태 보고](#2-git-상태-보고)
3. [Registry yaml 파일 목록 (filesystem 기준)](#3-registry-yaml-파일-목록-filesystem-기준)
4. [필드 현황 inventory](#4-필드-현황-inventory)
5. [input/output labels 매핑표 (수정 대상 확정)](#5-inputoutput-labels-매핑표-수정-대상-확정)
6. [af_desc 누락 위치 특정](#6-af_desc-누락-위치-특정)
7. [Mode A 수정 금지 재확인](#7-mode-a-수정-금지-재확인)
8. [Baseline 회귀검증 결과](#8-baseline-회귀검증-결과)

---

## 1. 백업 완료 확인

**백업 위치**: `docs/_backup_ca1b/`  
**백업 시각**: 2026-08-10

| 원본 경로 | 백업 경로 | 크기(bytes) |
|----------|----------|------------|
| `docs/registry/employment.yaml` | `docs/_backup_ca1b/registry/employment.yaml` | 2,874 |
| `docs/registry/insurance.yaml` | `docs/_backup_ca1b/registry/insurance.yaml` | 1,545 |
| `docs/registry/labor.yaml` | `docs/_backup_ca1b/registry/labor.yaml` | 3,878 |
| `docs/registry/labor_af.yaml` | `docs/_backup_ca1b/registry/labor_af.yaml` | 4,163 |
| `docs/registry/realty_af.yaml` | `docs/_backup_ca1b/registry/realty_af.yaml` | 1,570 |
| `docs/registry/tax.yaml` | `docs/_backup_ca1b/registry/tax.yaml` | 2,949 |
| `docs/legal_master/employment.yaml` | `docs/_backup_ca1b/legal_master/employment.yaml` | 3,389 |
| `docs/legal_master/insurance.yaml` | `docs/_backup_ca1b/legal_master/insurance.yaml` | 2,729 |
| `docs/legal_master/labor.yaml` | `docs/_backup_ca1b/legal_master/labor.yaml` | 3,574 |
| `docs/legal_master/tax.yaml` | `docs/_backup_ca1b/legal_master/tax.yaml` | 5,343 |
| `docs/legal_basis.master.yaml` | `docs/_backup_ca1b/legal_basis.master.yaml` | 24,339 |
| `docs/registry_auto.yaml` | `docs/_backup_ca1b/registry_auto.yaml` | 2,421 |
| `docs/legal_basis.draft.yaml` | `docs/_backup_ca1b/legal_basis.draft.yaml` | 71 |

**총 13개 파일 백업 완료.**

복원 방법: 각 백업 파일을 원본 경로로 복사하면 된다.

---

## 2. Git 상태 보고

**결론: Working tree에 미커밋 변경 존재 — 임의 커밋/stash 금지**

### 수정된 파일 (12개)
모두 `logs/content_pipeline/pipeline_p_*.json` — 파이프라인 실행 로그 파일.
코드/Registry/계산기 로직과 무관한 로그 파일이며, CA-1B 작업과 충돌하지 않는다.

```
M  logs/content_pipeline/pipeline_p_annual-leave-allowance.json
M  logs/content_pipeline/pipeline_p_calc1.json
M  logs/content_pipeline/pipeline_p_calc2.json
M  logs/content_pipeline/pipeline_p_calc_fail.json
M  logs/content_pipeline/pipeline_p_calc_hold.json
M  logs/content_pipeline/pipeline_p_calc_rewrite.json
M  logs/content_pipeline/pipeline_p_four-insurances.json
M  logs/content_pipeline/pipeline_p_parental-leave-benefit.json
M  logs/content_pipeline/pipeline_p_severance-pay.json
M  logs/content_pipeline/pipeline_p_unemployment-benefit.json
M  logs/content_pipeline/pipeline_p_weekly-holiday-allowance.json
M  logs/content_pipeline/pipeline_p_연말정산_환급액_계산기.json
```

### Untracked 파일 (2개)
```
??  _secret_replace2.txt         ← 절대 커밋 금지
??  docs/CA1A_CONTRACT_SCHEMA_DESIGN.md
```

**운영자 결정 필요**: `docs/CA1A_CONTRACT_SCHEMA_DESIGN.md`는 CA-1B-0 완료 후 커밋할 수 있으나, 지시 없이 임의 커밋하지 않는다. 로그 파일 12개도 별도 지시 없이 임의 처리하지 않는다.

---

## 3. Registry yaml 파일 목록 (filesystem 기준)

CA-0 조사 보고서의 "6개 yaml merge" 기록과 **실제 filesystem이 일치**. 추가·삭제된 파일 없음.

| 파일명 | 유형 | 계산기 엔트리 수 | 파일 크기 |
|--------|------|--------------|---------|
| `employment.yaml` | 기존(수동관리) | 2 | 2,874 bytes |
| `insurance.yaml` | 기존(수동관리) | 1 | 1,545 bytes |
| `labor.yaml` | 기존(수동관리) | 3 | 3,878 bytes |
| `tax.yaml` | 기존(수동관리) | 2 | 2,949 bytes |
| `labor_af.yaml` | AF 자동생성 | 1 | 4,163 bytes |
| `realty_af.yaml` | AF 자동생성 | 1 | 1,570 bytes |
| **합계** | | **10** | |

### 계산기 엔트리 전체 목록 (파일별)

**employment.yaml** (2개):
- `unemployment-benefit` (실업급여)
- `육아휴직_급여_계산기` (육아휴직 급여)

**insurance.yaml** (1개):
- `four-insurances` (4대보험)

**labor.yaml** (3개):
- `weekly-holiday-allowance` (주휴수당)
- `severance-pay` (퇴직금)
- `annual-leave-allowance` (연차수당)

**tax.yaml** (2개):
- `연말정산_환급액_계산기` (연말정산 환급액)
- `freelancer-tax-3p3` (프리랜서 3.3%)

**labor_af.yaml** (1개):
- `annual-leave-remaining` (연차 잔여일) — status: READY, source: app_factory

**realty_af.yaml** (1개):
- `jeonse-vs-monthly` (전세 vs 월세) — status: READY, source: app_factory

---

## 4. 필드 현황 inventory

### 4-1. 기존 수동관리 파일 (employment / insurance / labor / tax) 공통 구조

| 최상위 필드 | 모든 파일 공통 | 비고 |
|-----------|------------|------|
| `name` | ✅ | |
| `slug` | ✅ | |
| `category` | ✅ | |
| `emoji` | ✅ | |
| `card_label` | ✅ | |
| `compute_type` | ✅ | single / dict / date_based |
| `date_fields` | ✅ | 보통 [] |
| `validation_mode` | ✅ | formula / skip |
| `field_labels` | ✅ | input/output **구분 없음** |
| `display_order` | ✅ | |
| `card_desc` | ✅ | |
| `difficulty` | ✅ | simple / complex / multi_output / date_based |
| `difficulty_status` | ✅ | provisional |
| `content` | ✅ | evergreen / update_cycle / content_caveat |
| `related_slugs` | ✅ | |
| `legal_refs` | ✅ | |
| `writer_context` | ✅ | emphasize / example_patterns / calculation_story |

**CA-0 시점과 동일 구조 확인. 변경 없음.**

### 4-2. AF 자동생성 파일 (_af.yaml) 추가 필드

기존 파일 대비 추가되는 필드:

| 필드 | 용도 |
|------|------|
| `status` | READY / HOLD |
| `tier` | 2 (Tier2) |
| `source` | app_factory |
| `review_checklist` | 운영자 검토 항목 목록 |
| `compute_rules` | 양수 입력 강제 등 |

**field_labels**: `_af.yaml`도 input/output 구분 없이 동일 구조.

### 4-3. CA-0 시점 대비 변경 사항

**없음**. `labor_af.yaml`은 이번 세션에서 `annual-leave-remaining` 저장 E2E 테스트로 생성됐지만, CA-0 조사 당시에도 존재했던 파일이다 (status: READY). 구조 변경 없음.

---

## 5. input/output labels 매핑표 (수정 대상 확정)

DB `input_schema` / `output_schema`를 기준으로, 각 계산기의 `field_labels` 키를 input/output으로 분류한 확정 매핑표. **이번 단계에서는 표만 작성. yaml 수정은 CA-1B-1에서 진행.**

### 5-1. 완전 매핑표

| slug | 소속 파일 | 필드명 | DB 타입 | input/output |
|------|---------|--------|---------|-------------|
| **weekly-holiday-allowance** | labor.yaml | `hourly_wage` | number | **input** |
| | | `weekly_hours` | number | **input** |
| | | `weekly_holiday_pay` | number | **output** |
| **severance-pay** | labor.yaml | `avg_monthly_wage` | number | **input** |
| | | `start_date` | date | **input** |
| | | `end_date` | date | **input** |
| | | `severance_pay` | number | **output** |
| **annual-leave-allowance** | labor.yaml | `daily_wage` | number | **input** |
| | | `unused_days` | number | **input** |
| | | `annual_leave_allowance` | number | **output** |
| **unemployment-benefit** | employment.yaml | `avg_daily_wage` | number | **input** |
| | | `age` | number | **input** |
| | | `employment_months` | number | **input** |
| | | `daily_benefit` | number | **output** |
| | | `total_benefit` | number | **output** |
| **육아휴직_급여_계산기** | employment.yaml | `monthly_wage` | number | **input** |
| | | `insured_days` | number | **input** |
| | | `use_6plus6` | boolean | **input** |
| | | `leave_month` | number | **input** |
| | | `monthly_allowance` | number | **output** |
| **four-insurances** | insurance.yaml | `monthly_salary` | number | **input** |
| | | `national_pension` | number | **output** |
| | | `health_insurance` | number | **output** |
| | | `employment_insurance` | number | **output** |
| | | `total` | number | **output** |
| **연말정산_환급액_계산기** | tax.yaml | `total_salary` | number | **input** |
| | | `family_count` | number | **input** |
| | | `paid_tax` | number | **input** |
| | | `estimated_refund` | number | **output** |
| **freelancer-tax-3p3** | tax.yaml | `gross_income` | number | **input** |
| | | `withholding_tax` | number | **output** |
| | | `net_income` | number | **output** |
| **jeonse-vs-monthly** | realty_af.yaml | `jeonse_deposit` | number | **input** |
| | | `wolse_deposit` | number | **input** |
| | | `wolse_amount` | number | **input** |
| | | `rate` | number | **input** |
| | | `jeonse_opp_cost` | number | **output** |
| | | `wolse_to_jeonse_equiv` | number | **output** |
| | | `monthly_savings` | number | **output** |
| **annual-leave-remaining** | labor_af.yaml | `years_of_service` | integer | **input** |
| | | `used_days` | integer | **input** |
| | | `total_days` | integer | **output** |
| | | `remaining_days` | integer | **output** |

### 5-2. CA-1B-1 수정 대상 파일별 요약

| 파일 | 계산기 수 | input 필드 합계 | output 필드 합계 |
|------|---------|--------------|---------------|
| `labor.yaml` | 3 | 7 | 3 |
| `employment.yaml` | 2 | 7 | 3 |
| `insurance.yaml` | 1 | 1 | 4 |
| `tax.yaml` | 2 | 4 | 3 |
| `labor_af.yaml` | 1 | 2 | 2 |
| `realty_af.yaml` | 1 | 4 | 3 |
| **합계** | **10** | **25** | **18** |

### 5-3. 수정 방식 확정 (CA-1B-1 설계)

**현재 구조**:
```yaml
field_labels:
  hourly_wage: "시급(원)"     # input인지 output인지 불명
  weekly_hours: "주당 근로시간" # input인지 output인지 불명
  weekly_holiday_pay: "주휴수당(원)"  # input인지 output인지 불명
```

**CA-1B-1 이후 목표 구조**:
```yaml
field_labels:
  hourly_wage: "시급(원)"
  weekly_hours: "주당 근로시간"
  weekly_holiday_pay: "주휴수당(원)"
input_labels:
  - hourly_wage
  - weekly_hours
output_labels:
  - weekly_holiday_pay
```

**선택 이유**: `field_labels`를 유지하면서 `input_labels` / `output_labels` 키를 별도로 추가. 기존 `field_labels` 소비 코드(`registry_loader.py`, `app_factory.py` 등) 변경 없이 CA-1B-1만으로 분리 가능. 하위 호환 유지.

**예외**: `_af.yaml` 파일(labor_af, realty_af)은 App Factory가 자동 기록하는 파일이므로, `save_app()` 코드에서 `input_labels` / `output_labels`도 함께 기록하도록 CA-1B-1에서 `_write_registry_v3()` 수정 필요.

---

## 6. af_desc 누락 위치 특정

> **CA-1B-2 수정 경계**: Mode B의 Contract 생성 경로만 수정. Mode A 경로, `generate_app()` 일반 경로, 기존 9개 계산기 재생성 동작은 수정 대상에서 제외.

### 6-1. af_desc 데이터 흐름

```
dashboard.py
  └── af_desc = st.text_area("설명", key="af_desc")           ← line 2158: 운영자 입력
          │
          ├── [Mode A, line 2215-2216]
          │     AF.generate_app(cfg, af_name, af_cat, af_desc, tier=af_tier)
          │     → af_desc 정상 전달 ✅
          │
          └── [Mode B, line 2293-2302]
                AF.build_contract(
                    slug=..., name=..., category=..., tier=...,
                    input_fields=..., output_fields=...,
                    formula=..., test_cases=...,
                )                          ← af_desc 전달 누락 ❌
                → contract에 desc 없음
                → generate_app_with_contract(cfg, contract)
                     → contract.get("description", "") or contract.get("desc", "")
                     → "" 반환
                     → AI 생성 시 설명 컨텍스트 없음
```

### 6-2. 누락 지점 정확 특정 (4곳)

| # | 파일 | 함수 / 위치 | 라인 | 문제 |
|---|------|-----------|------|------|
| **A** | `dashboard.py` | Mode B `build_contract()` 호출 블록 | **2293–2302** | `desc=af_desc` 파라미터가 없음. `af_desc`는 동일 스코프에 존재하나 전달 안 됨 |
| **B** | `modules/app_factory.py` | `build_contract()` 함수 시그니처 | **267** (approx) | `desc` 파라미터 자체가 없음 — 받을 수가 없는 상태 |
| **C** | `modules/app_factory.py` | `generate_app_with_contract()` | **381** (approx) | `contract.get("description", "") or contract.get("desc", "")` — 이중 키 폴백. B가 수정되면 단일 키(`desc`)로 통일 필요 |
| **D** | `run_phase2_repro_test.py` | `contract["desc"] = DESC` | **55** | `build_contract()` 호출 후 수동 키 추가 (임시 우회). B 수정 후 `build_contract(desc=DESC)` 로 대체 필요 |

**E2E 스크립트 3개도 D와 동일 패턴**: `run_save_e2e_test.py` line 100, `run_annual_leave_e2e.py` (유사 위치).

### 6-3. CA-1B-2 수정 범위 (확정)

```
수정 대상:
  - modules/app_factory.py: build_contract() 시그니처에 desc: str = "" 추가
  - modules/app_factory.py: generate_app_with_contract()에서 단일 키 contract.get("desc", "") 사용
  - dashboard.py: line 2302 다음에 desc=af_desc or "" 파라미터 추가

수정 제외:
  - Mode A 경로 (dashboard.py line 2215-2216) — af_desc 이미 정상 전달 중
  - generate_app() 함수 자체 — 변경 없음
  - 기존 9개 계산기 재생성 경로 — 변경 없음
  - run_phase2_repro_test.py, run_save_e2e_test.py 등 E2E 스크립트
    → CA-1B-2 이후 별도 지시 시 정식화
```

---

## 7. Mode A 수정 금지 재확인

**CA-1B 전체 기간 동안 Mode A 관련 코드/설정은 수정 대상에서 명시적으로 제외된다.**

| 대상 | 파일/경로 | 제외 근거 |
|------|---------|---------|
| Mode A 생성 경로 | `dashboard.py:2208–2220` | `generate_app()` 직접 호출. af_desc 정상 전달 중. 수정 불필요 |
| `generate_app()` 함수 | `modules/app_factory.py` | Contract 미사용 경로. CA-1B 범위 외 |
| Mode A 저장 경로 | `dashboard.py` | CA-1B와 무관 |
| 기존 9개 계산기 Registry | `docs/registry/*.yaml` | input_labels/output_labels **추가**는 수행. 기존 field_labels/legal_refs 등 기존 필드 변경은 금지 |
| 기존 9개 계산기 DB 데이터 | DB `calculators` / `app_templates` | 수정 금지 |

---

## 8. Baseline 회귀검증 결과

**실행 일시**: 2026-08-10  
**실행 명령**: `python -m pytest tests/ -v --tb=short`

### 결과 요약

| 구분 | 수치 |
|------|------|
| **PASS** | **485** |
| **FAIL** | **1** |
| WARN | 457 |
| 실행 시간 | 88.72초 |

### 실패 테스트: `tests/production_validation_test.py::test_full_pipeline_execution`

**실패 원인**: WordPress 서버(`salarymate.test:80`) 연결 불가 + `OPENAI_API_KEY` 미설정.

```
각 계산기: PASS | PASS | PASS | PASS | PUBLISHED | FAILED
assert all(res["STATUS"] == "SUCCESS" for res in results_table.values())
```

파이프라인의 1~5단계(생성·가공·SEO·FAQ·발행)는 전부 PASS. 마지막 6단계(WordPress HTTP publish)에서 연결 거부로 FAIL. 이는 CA-0 이전부터 존재하는 **테스트 환경 제약 known issue**이며, 코드 결함이 아니다.

### Registry v3 상태 (전 10개 계산기)

| slug | status | source |
|------|--------|--------|
| unemployment-benefit | (없음 = READY 취급) | (수동) |
| 육아휴직_급여_계산기 | (없음) | (수동) |
| four-insurances | (없음) | (수동) |
| weekly-holiday-allowance | (없음) | (수동) |
| severance-pay | (없음) | (수동) |
| annual-leave-allowance | (없음) | (수동) |
| annual-leave-remaining | **READY** | app_factory |
| jeonse-vs-monthly | **READY** | app_factory |
| 연말정산_환급액_계산기 | (없음) | (수동) |
| freelancer-tax-3p3 | (없음) | (수동) |

**10개 전부 Registry v3 + DB에 정상 등록. 무결성 이상 없음.**

### CA-1B 회귀 기준

CA-1B-1 / CA-1B-2 완료 후 재실행 시:
- PASS ≥ 485 (현재와 동일 이상)
- FAIL = 1 (동일한 `production_validation_test.py` known issue만 허용)
- 새로운 FAIL 발생 시 해당 변경사항 즉시 롤백

---

## 요약 — CA-1B-1 / CA-1B-2 착수 전제 체크리스트

| 항목 | 상태 |
|------|------|
| 백업 완료 (`docs/_backup_ca1b/` 13개 파일) | ✅ |
| Git 상태 — 로그 파일 미커밋 변경 12개 존재 (운영자 결정 대기) | ⚠️ |
| Registry yaml 파일 수 재확인 (6개, CA-0과 일치) | ✅ |
| 계산기 전체 10개 엔트리 확인 | ✅ |
| 필드 현황 inventory (CA-0과 일치, 변경 없음) | ✅ |
| input/output 매핑표 완성 (25 input, 18 output, 10 계산기) | ✅ |
| af_desc 누락 위치 특정 (4곳: A-D) | ✅ |
| Mode A 수정 금지 재확인 | ✅ |
| Baseline: 485 PASS / 1 FAIL (known issue) | ✅ |
