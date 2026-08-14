# Tier2-B 표준경로 구현 전 사전검증 — 최종 보고서

**작성일**: 2026-08-15
**검증 대상**: 군인전역일 계산기 (10번째 배포 대상, Tier2-B)
**구현 방식**: Method B (자체포함 HTML + Registry 메타데이터 하이브리드)

---

## Section 1 — Git 상태

| 항목 | 결과 |
|------|------|
| HEAD | `9b4dbb4 fix(contract): preserve legal refs in review checklist` |
| 보호파일 변경 | 없음 (로그/스냅샷만 modified) |
| 예상 외 커밋 | 없음 |

**→ PASS**

---

## Section 2 — 배포 기준선 확인

**배포된 계산기: 9개** (±annual-leave-remaining)

| 배포된 계산기 (9) | 미배포 (Registry만) |
|---|---|
| weekly-holiday-allowance | annual-leave-remaining (HOLD, _site 없음) |
| severance-pay | |
| annual-leave-allowance | |
| unemployment-benefit | |
| four-insurances | |
| 연말정산_환급액_계산기 | |
| 육아휴직_급여_계산기 | |
| freelancer-tax-3p3 | |
| jeonse-vs-monthly | |

- sitemap.xml 9개 URL 확인
- Registry 10개 엔트리 vs 배포 9개 = 차이 1 = annual-leave-remaining
- 회귀 기준선: **9개**, Registry 수(10) 기준 사용 금지

**→ PASS**

---

## Section 3 — 기존 설계 문서 요약

### 계산 로직 (PHASE3_3_0_AUDIT.md)

| 병종 | 복무기간 | 법령 근거 |
|------|----------|-----------|
| 육군 | 18개월 | 병역법 제18조 |
| 해병대 | 18개월 | 병역법 제18조 |
| 해군 | 20개월 | 병역법 제18조 |
| 공군 | 21개월 | 병역법 제18조 |
| 사회복무요원 | 21개월 | 병역법 제26조 |

**전역일 공식 (설계 문서 주장)**: 입대일 + N개월 - 1일
**입력**: `enlistment_date` (date), `branch` (select: army/navy/air_force/marine/social_service)
**출력**: `discharge_date` (string), `remaining_days` (number), `progress_pct` (number)

### 7개 테스트 케이스 (설계 문서 정의)

TC-1 육군 월중 입대 / TC-2 해군 / TC-3 공군 / TC-4 해병대 / TC-5 사회복무요원 / TC-6 월말 입대(말일 처리) / TC-7 미래 입대(복무 중)

**→ 테스트 파일 미존재** (PHASE3_3_0_AUDIT.md에만 기술, test 파일 없음)

### Method B 정의 (TIER2_B_DESIGN.md)

- formula dict 없음, `_compute_js()` 수정 없음
- `html_template` → DB `app_templates` 테이블 저장
- `_rebuild_site.py`: `tier_subtype=B` 감지 → `html_template`을 `_site/<slug>/index.html`로 직접 복사
- 새 Registry 필드: `tier_subtype: B`, `html_source: template_db`, `compute_type: date_based_custom`

---

## Section 4 — 공식 전역일 계산식 확인 (D-5 핵심)

### 4-1: 설계 문서 기준

> "입대일 + N개월 - 1일"

### 4-2: 웹 검색 재확인 (2026-08-15 기준)

**복무기간** — 병무청 공식 / 생활법령정보 기준:

| 병종 | 복무기간 | 설계 문서와 일치 |
|------|----------|---------|
| 육군 | 18개월 | ✅ 일치 |
| 해병대 | 18개월 | ✅ 일치 |
| 해군 | 20개월 | ✅ 일치 |
| 공군 | 21개월 | ✅ 일치 |
| 사회복무요원 | 21개월 | ✅ 일치 |

**법령**: 병역법 제18조제2항·제19조제1항제3호 (현역병), 병역법 제26조 (사회복무요원)

**전역일 공식** — 더캠프, 핀즈, K-Calculator 등 복수 서비스 확인:

> "복무 시작일 + N개월 - 1일"

예: 2026-01-15 입대(육군, 18개월) → 2027-07-15 − 1일 = **2027-07-14** 전역

**말일 처리**: 결과 날짜가 해당 월에 존재하지 않으면 민법 기준 해당 월 마지막 날 적용

### 4-3: 불일치 여부

**불일치 없음.** 설계 문서 = 웹 검색 결과 = 완전 일치

### 4-4: 날짜 산술 규칙

| 규칙 | 처리 방식 |
|------|----------|
| 전역일 = 입대일 + N개월 - 1일 | Python: `(enlistment_date + relativedelta(months=N)) - timedelta(days=1)` |
| 말일 처리 | `dateutil.relativedelta` 자동 처리 (2월, 30일 월) |
| 윤년 | relativedelta가 자동 처리 |
| 포함/미포함 | 입대일 포함, 전역일 포함 (= N개월 - 1일 이유) |

**→ HOLD-1 (공식 미확인) → CLEARED**

---

## Section 5 — legal_master 상태

| 파일 | 엔티티 수 | 군사/병역 관련 |
|------|-----------|--------------|
| labor.yaml | 3 | 없음 |
| employment.yaml | 2 | 없음 |
| insurance.yaml | 1 | 없음 |
| tax.yaml | 2 | 없음 |
| **합계** | **8** | **없음** |

**판정: B — 신규 법령 엔티티 필요**

- 군인전역일 계산기는 병역법 제18조/제26조 근거 필요
- 기존 8개 엔티티 중 해당 없음
- CA-4-B (legal_master UI) 범위와 별개의 데이터 신규 추가 필요
- 구현 선행조건: `docs/legal_master/defense.yaml` 신규 생성 필요

---

## Section 6 — 실제 변경 범위 확인

### `scripts/_rebuild_site.py` (현재 71줄)

**현재 구조** (line 42-58):

```python
for c in calcs:
    slug = c.get("slug", "")
    if (_v3.get(slug) or {}).get("status") == "HOLD":
        print(f"  [SKIP] {slug}")
        continue
    files = AG.generate_calculator(c, cfg)      # ← 단일 경로만 존재
    ...
```

**필요한 추가**:

```python
    v3_entry = _v3.get(slug) or {}
    if v3_entry.get("tier_subtype") == "B":     # ← 신규 Tier2-B 분기
        # DB에서 html_template 가져와 _site/<slug>/index.html로 직접 복사
        ...
        continue
    files = AG.generate_calculator(c, cfg)      # 기존 Tier2-A/Tier1
```

**기존 계산기 영향**: 없음 (tier_subtype 필드가 없으면 기존 경로 유지)

### `modules/app_factory.py`

**변경 위치 3곳**:

1. `_CATEGORY_AF_YAML_MAP` (line 24-30): `"국방/병역"` 키 없음 → 추가 필요

   ```python
   "국방/병역": "defense_af",  # 신규 추가 필요
   ```

2. `_build_v3_entry()` (line 117-166): `tier_subtype`, `html_source`, `compute_type` 저장 로직 없음 → 조건부 추가 필요

3. `build_contract()` (line 286-337): `tier_subtype` 파라미터 없음 → 추가 필요

**기존 계산기 영향**: 없음 (optional 파라미터, 기존 경로 변경 없음)

### `dashboard.py`

**현재 Tier 선택 (line 2192-2207)**:

```python
af_tier = st.radio(
    options=[2, 1],
    format_func=lambda t: "Tier2 — 단순 산술/일반 공식" if t == 2 else "Tier1 — ..."
)
```

**문제**: Tier2-B 선택 불가. `_tier_map_str_to_int` (line 2165)에 `"Tier2-B": 2` 매핑은 존재하지만 UI에 노출 안 됨.

**필요한 추가**: Tier2 선택 시 하위 subtype 체크박스 또는 Tier 옵션 확장 필요

**→ HOLD-2 (빌드 경로 미확인) → 설계 명확, 구현만 남음. CLEARED.**

---

## Section 7 — 기존 Tier2-A 계산기 영향 분석

| 계산기 | 유형 | 영향 |
|------|------|------|
| jeonse-vs-monthly | Tier2-A, 배포중 | 없음 (tier_subtype=B 없음, 기존 경로 유지) |
| annual-leave-remaining | Tier2-A, HOLD | 없음 (HOLD → 빌드 제외) |
| 기존 8개 계산기 | source≠app_factory | 없음 (promote_to_ready 진입 불가) |

**jeonse-vs-monthly 회귀 리스크**: 없음. `_rebuild_site.py` 변경은 `tier_subtype` 필드 존재 여부에 의존 → jeonse-vs-monthly의 Registry 엔트리에 해당 필드 없음 → 기존 경로 그대로 실행.

---

## Section 8 — 기존 테스트 현황

### tier2-b 관련 테스트 (`tests/test_review_center.py`)

| 테스트 | 검증 내용 | 상태 |
|--------|----------|------|
| `test_formula_accuracy_not_extracted_for_tier2b` | Tier2-B에서 formula_accuracy 미추출 | ✅ 존재 |
| `test_formula_cap_not_extracted_for_date_based` | date_based에서 formula_cap 미추출 | ✅ 존재 |
| `test_detect_tier2b_keywords_positive` | "전역일", "복무", "D-Day" 감지 | ✅ 존재 |
| `test_detect_tier2b_keywords_negative` | 일반 계산기 오탐 없음 | ✅ 존재 |
| `test_legal_basis_critical_for_critical_category` | "병역/공무" 카테고리 처리 | ✅ 존재 |

### 7 TC (TC-1~TC-7) 테스트 파일 존재 여부

**없음.** `PHASE3_3_0_AUDIT.md`에만 기술. 테스트 구현은 구현 단계에서 필요.

### `_rebuild_site.py` Tier2-B 분기 테스트

**없음.** 구현 후 신규 작성 필요.

---

## Section 9 — 최종 판정

### HOLD 항목 재평가

| HOLD | 내용 | 판정 |
|------|------|------|
| HOLD-1 | 전역일 공식 미확인 | **CLEARED** — 웹 검색으로 "입대일+N개월-1일" 확인, 설계 문서와 100% 일치 |
| HOLD-2 | 정적 사이트 빌드 경로 미확인 | **CLEARED** — `_rebuild_site.py` 구조 확인, Tier2-B 분기 추가 위치 특정 완료 |

### 구현 전 필수 선행조건

| # | 항목 | 파일 | 비고 |
|---|------|------|------|
| P-1 | legal_master 신규 엔티티 생성 | `docs/legal_master/defense.yaml` | 병역법 제18조/제26조 |
| P-2 | App Factory 카테고리 추가 | `modules/app_factory.py` line 24-30 | `"국방/병역": "defense_af"` |
| P-3 | `_build_v3_entry()` 확장 | `modules/app_factory.py` line 117-166 | tier_subtype/html_source 저장 |
| P-4 | `build_contract()` 확장 | `modules/app_factory.py` line 286-337 | tier_subtype 파라미터 추가 |
| P-5 | Dashboard Tier2-B UI | `dashboard.py` line 2192-2207 | Tier2 선택 시 subtype 체크박스 |
| P-6 | `_rebuild_site.py` Tier2-B 분기 | `scripts/_rebuild_site.py` line 48 | html_template 직접 복사 경로 |
| P-7 | 군인전역일 HTML 템플릿 제작 | DB app_templates 테이블 | GA4 추적 포함 (Method B 위험 완화) |

**변경 파일 수: 4개** (app_factory.py, _rebuild_site.py, dashboard.py, defense.yaml 신규)

### 구현 권장 순서

```
P-1 (legal_master defense.yaml)
  → P-2 ~ P-6 (코드 4파일, 동시 진행 가능)
    → P-7 (군인전역일 HTML 템플릿)
      → 7 TC 테스트 코드 작성
        → 빌드 검증 (_rebuild_site.py 실행 + _site/군인전역일 확인)
```

---

## 최종 판정

```
┌─────────────────────────────────────────────────────────────────┐
│                  ✅ READY FOR IMPLEMENTATION                     │
│                                                                  │
│  HOLD-1 (공식): CLEARED — 웹 검색으로 확인, 설계와 100% 일치   │
│  HOLD-2 (빌드): CLEARED — _rebuild_site.py 구조 확인 완료      │
│  회귀 리스크:   LOW — 기존 9개 계산기 코드 경로 영향 없음      │
│  변경 범위:     4개 파일, 구체 위치 특정 완료                  │
│  선행조건:      P-1(legal_master) 먼저, P-2~P-6 동시 진행 가능 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 참고 — 웹 검색 출처

- [병역의무자(현역) 복무기간 및 보수 — 찾기쉬운 생활법령정보](https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=1461&ccfNo=2&cciNo=2&cnpClsNo=1)
- [병무청 — 입영신청 절차 및 복무기간](https://www.mma.go.kr/contents.do?mc=mma0000728)
- [사회복무요원 소집해제일 계산 및 복무기간 21개월](https://military-calculator.a4calendar.com/social)
- [병무청_군별 복무유형별 복무기간 — 공공데이터포털](https://www.data.go.kr/data/15004572/fileData.do)
