# CalcMate Phase2 — P2-1 Registry 설계 조사 결과

기준일: 2026-08-08  
조사 범위: 코드 수정 없음. 읽기·분석·문서화만.

---

## 1. Registry v3 실제 구조

### 1-1. 파일 배치

```
docs/registry/
  labor.yaml        → weekly-holiday-allowance, severance-pay, annual-leave-allowance
  employment.yaml   → unemployment-benefit, four-insurances
  insurance.yaml    → (고용보험/4대보험 세부, 아직 비어있거나 보조)
  tax.yaml          → 연말정산_환급액_계산기

docs/legal_master/
  labor.yaml        → labor_standards_act_55, labor_standards_act_60, worker_retirement_benefit_act_8
  employment.yaml   → employment_insurance_act_40 등
  insurance.yaml    → (보험료 관련)
  tax.yaml          → income_tax_act_137
```

### 1-2. Registry 엔트리 스키마 (7종 공통)

| 필드 | 타입 | 상태 |
|------|------|------|
| name | str | 채워짐 |
| slug | str | 채워짐 |
| category | str | 채워짐 |
| emoji | str | 채워짐 |
| card_label | str | 채워짐 |
| compute_type | str | 채워짐 (single / date_based) |
| date_fields | list | 채워짐 |
| validation_mode | str | 채워짐 (formula / skip) |
| **field_labels** | dict | **전부 {} — 7종 모두 비어있음 (핵심 GAP)** |
| difficulty | str | provisional |
| content.evergreen | bool | 채워짐 |
| related_slugs | list | 채워짐 |
| legal_refs | list | 채워짐 |
| writer_context | dict | 연말정산만 있음 (선택 필드) |

### 1-3. Legal Master 엔트리 스키마

| 필드 | 타입 | 역할 |
|------|------|------|
| law | str | 법령명 |
| article | str | 조항 |
| related_articles | list | 관련 조항 |
| authority | str | 소관기관 |
| confidence | str | 검증 신뢰도 |
| last_verified | date | 검증일 |
| writer_note | str | 작성 지침 |
| forbidden_articles | list | 인용 금지 조항 |
| forbidden_phrases | str | 확정형 금지 표현 |
| needs_human_legal | bool | 추가 검증 필요 여부 |
| deduction_rules | dict | (세금 계산기만) 공제 규칙 수치 |
| calculation_flow | list | (세금 계산기만) 계산 흐름 |

---

## 2. Production 소비 지점 분석

### 2-1. 현재 production 경로 (legacy)

```
app_generator._registry()
  └─ registry_loader.load_registry()  ← legal_basis.master.yaml + registry_auto.yaml merge
      [소비처]
      - _compute_type(calc)         → HTML/JS 분기 (date_based 여부)
      - _validation_mode(calc)      → JS 검증 로직 분기
      - _related_triples(cur_slug)  → 관련 계산기 카드 (related_slugs, emoji, card_label)
```

```
calculator_pipeline._load_legal_basis()
  └─ registry_loader.load_registry()
      [소비처]
      - _legal_basis_block(calc)    → writer 프롬프트 (법적 근거 주입)
      - _legal_unverified(lb)       → HOLD 판단
      - _quality_signature(cfg, calc) → 재평가 서명
```

### 2-2. v3 구조 사용 지점 (이미 production에 연결됨)

```
calculator_pipeline._resolve_context_block(calc)
  └─ registry_loader.resolve(slug)
      └─ load_registry_v3() + load_legal_master()
      [소비처]
      - deduction_rules → writer 프롬프트에 계산 근거 데이터 주입
      - calculation_flow → 계산 흐름 주입
      - writer_context.emphasize / example_patterns / calculation_story
```

**현재 v3가 production에 실제로 기여하는 계산기: 연말정산_환급액_계산기 1종**  
(writer_context + deduction_rules가 채워진 유일한 엔트리)

나머지 6종은 `resolve()`가 빈 dict를 반환 → `_resolve_context_block()` 결과 = "" (no-op)

### 2-3. site_generator.py의 소비 지점

```
site_generator.generate_index(cfg)
  ├─ app_generator._registry()        ← legacy 경로 (slug→name, emoji)
  └─ app_generator._SLUG_ORDER        ← 하드코딩 순서 (7종 고정)
      └─ _CALC_DESCS[slug]            ← 하드코딩 카드 설명 문구

generate_sitemap(cfg)
  └─ app_generator._SLUG_ORDER        ← 하드코딩 순서
```

---

## 3. _CALC_DESCS / _SLUG_ORDER 마이그레이션 타당성

### 3-1. 현재 상태

| 데이터 | 위치 | 방식 |
|--------|------|------|
| 계산기 표시 순서 | `app_generator._INTERNAL_LINK_MAP` dict 키 순서 → `_SLUG_ORDER` | 하드코딩 |
| 홈 카드 설명 문구 | `site_generator._CALC_DESCS` | 하드코딩 |
| 앵커 텍스트 변형 | `app_generator._INTERNAL_LINK_MAP[slug][1]` | 하드코딩 |
| 키워드-slug 매핑 | `app_generator._KW_SLUG` | 하드코딩 |

### 3-2. Registry v3로 이관 가능 여부

| 데이터 | 이관 위치 후보 | 판단 |
|--------|--------------|------|
| 카드 설명 (`_CALC_DESCS`) | `registry.card_desc` 신규 필드 | 이관 가능 — 단순 문자열 |
| 표시 순서 (`_SLUG_ORDER`) | `registry.display_order` int 필드 | 이관 가능 — int 정렬 |
| 앵커 텍스트 변형 | `registry.anchor_variants` list 필드 | 이관 가능 — list[str] |
| 키워드-slug 매핑 | `registry.search_keywords` list 필드 | 이관 가능 — list[str] |

### 3-3. 이관의 선행 조건

Registry v3 엔트리의 `field_labels: {}` 문제를 해결하지 않으면 v3 전환 자체가 불완전.  
`field_labels`는 계산기 입력폼 레이블 소스로, 현재 `_LABELS` 전역 dict(app_generator)가 fallback 역할 중.  
v3로 전환 시 `_LABELS`를 registry로 옮기거나, `_LABELS` fallback 구조를 유지하면서 v3를 추가 소스로 사용해야 함.

---

## 4. calculator_seed.py 역할과 방향

### 4-1. 현재 역할

`calculator_seed.py`는 DB 초기 시드 전용 파일:
- `APP_TEMPLATES` 5종: DB `app_templates` 테이블 시드
- `SAMPLE_CALCULATORS` 7종: DB `calculators` 테이블 시드 (slug, name, formula, faq 등)
- Repository/Adapter 경유. gspread 직접 호출 없음.
- 멱등 설계 (중복 slug 건너뜀).

### 4-2. Registry v3와의 관계

`calculator_seed.py`의 `SAMPLE_CALCULATORS`는 DB의 계산기 정의 소스.  
Registry v3 (`docs/registry/*.yaml`)는 별도 파일 소스.  
**두 소스가 동일 7종을 중복 정의하는 3-way 정의 문제 (P2-0 감사 결론과 동일).**

| 소스 | 담당 필드 | 현재 status |
|------|----------|------------|
| `SAMPLE_CALCULATORS` (seed) | name, slug, formula, input_schema, output_schema, faq, seo | DB 시드용 |
| `legal_basis.master.yaml` (legacy) | law, article, authority, forbidden_articles 등 | production 중 |
| `docs/registry/*.yaml` (v3) | compute_type, validation_mode, related_slugs, legal_refs | 부분 production |

### 4-3. 방향 권장

`calculator_seed.py`는 DB 마이그레이션/초기화 도구로만 유지.  
계산기 메타데이터(SEO, 설명, 순서 등)의 SSOT를 registry v3로 점진적으로 이동.  
DB는 동적 데이터(published_at, article 본문 등)만 담당하는 분리 구조.

---

## 5. 어댑터/호환성 전략

### 5-1. 현재 구조 (생산 안정)

```
production: load_registry() → legal_basis.master.yaml + registry_auto.yaml
v3 부분 사용: resolve() → registry/*.yaml + legal_master/*.yaml (연말정산만 실효)
```

### 5-2. 권장 전략: Dual-Path + Gradual Migration

1. **v3 채우기 단계** (P2-1):  
   registry v3 `field_labels` 채우기 → v3 신규 필드(card_desc, display_order 등) 추가  
   코드 변경 없이 데이터만 채움.

2. **Soft Switchover 단계** (P2-2):  
   `_registry()`가 v3를 primary로, legacy를 fallback으로 사용하도록 전환.  
   `load_registry_v3()` 결과가 없는 slug만 legacy fallback.

3. **Legacy Deprecation 단계** (P2-3+):  
   `legal_basis.master.yaml` → v3 완전 이관 후 legacy 로더 제거.

### 5-3. 즉각 적용 가능 (코드 변경 없이)

- `docs/registry/*.yaml`에 `writer_context` 필드 채우기 → `_resolve_context_block()` 실효
- `legal_master/*.yaml`에 `deduction_rules` / `calculation_flow` 채우기 → writer 품질 개선
- 모든 변경이 v3 데이터 파일에만 영향 → production 코드 무변경

---

## 6. 리스크 분석

| 리스크 | 수준 | 설명 |
|--------|------|------|
| `field_labels: {}` 전환 시 레이블 누락 | 중 | `_LABELS` fallback이 있어 화면 깨짐은 없으나 의도한 계산기별 레이블 미적용 |
| legacy↔v3 slug 불일치 | 중 | 일부 슬러그가 한글(연말정산_환급액_계산기) — 양쪽 동일 확인 필요 |
| `_SLUG_ORDER` 하드코딩 제거 후 순서 변동 | 낮 | 홈 카드 노출 순서가 예상과 달라질 수 있음 (SEO 영향 없음) |
| `calculator_seed.py` 재시드 충돌 | 낮 | 멱등 설계이므로 재시드 시 기존 DB 데이터 덮어쓰지 않음 |
| v3 데이터 오입력 | 중 | YAML 파싱 실패 시 `_read_yaml()` 가 `{}` 반환 → silent fail |

---

## 7. P2-1 구현 스코프 권장

### 권장 P2-1 스코프: "Registry v3 데이터 보강 (코드 변경 없음)"

**목표**: registry v3를 production에서 의미 있게 활용할 수 있는 데이터 상태로 만들기.  
**코드 변경**: 0 (YAML 파일만 수정).  
**V1 영향**: 없음 (v3는 additive — legacy 경로 미변경).

#### 구체적 작업 목록

| 작업 | 대상 파일 | 내용 |
|------|----------|------|
| T1 | `docs/registry/*.yaml` 7종 | `field_labels` 채우기 (input_schema 필드 → 한글 레이블 매핑) |
| T2 | `docs/registry/*.yaml` 7종 | `card_desc` 신규 필드 추가 (site_generator._CALC_DESCS 값 이관) |
| T3 | `docs/registry/*.yaml` 7종 | `display_order` int 필드 추가 (_SLUG_ORDER 순서 반영) |
| T4 | `docs/legal_master/*.yaml` | 나머지 6종 `deduction_rules` / `calculation_flow` 채우기 (writer 품질 향상) |
| T5 | `docs/registry/*.yaml` 5종 | `writer_context` 채우기 (연말정산 외 6종) |

#### 비고 (P2-2 이후 범위)

- `_SLUG_ORDER` / `_CALC_DESCS` 코드 제거 → P2-2 (코드 전환)
- `_registry()` v3 Soft Switchover → P2-2
- `calculator_seed.py` SSOT 통합 → P2-3+

---

## 요약

**핵심 발견 3가지**

1. `field_labels: {}`이 7종 전부 비어있어 v3로 전환 시 레이블이 `_LABELS` 전역 fallback에만 의존.
2. `resolve()`는 이미 production 경로에 연결되어 있으나 실효는 연말정산 1종만.
3. `_SLUG_ORDER` / `_CALC_DESCS`는 하드코딩 — registry에 `display_order` / `card_desc` 추가하면 이관 가능.

**P2-1 권장 결론**: YAML 데이터 보강(코드 0줄 변경)으로 v3 활용 범위를 7종 전체로 확장.  
코드 전환(Soft Switchover)은 데이터 검증 완료 후 P2-2에서 진행.
