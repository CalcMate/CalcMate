# Phase3-0 신규 계산기 추가 구조조사 결과

작성일: 2026-08-08  
기준 태그: v2.0.0 (P2-3 완료)  
조사 방법: 코드 읽기 전용 (수정 없음)

---

## 1. 조사 대상별 발견사항

---

### 1-1. 현재 7개 계산기 구조 전수 확인

각 계산기가 걸쳐 있는 파일:

| 계산기 | registry v3 | legal_master | DB (calculators) | _compute_js 분기 |
|---|---|---|---|---|
| 주휴수당 | `labor.yaml` | `labor.yaml:labor_standards_act_55` | ✓ | formula 자동 (generic) |
| 퇴직금 | `labor.yaml` | `labor.yaml:worker_retirement_benefit_act_8` | ✓ | `date_based` 자동 |
| 연차수당 | `labor.yaml` | `labor.yaml:labor_standards_act_60` | ✓ | slug 분기 (`annual-leave-allowance`) |
| 실업급여 | `employment.yaml` | `employment.yaml:employment_insurance_act_40` | ✓ | slug 분기 (`unemployment-benefit`) |
| 육아휴직급여 | `employment.yaml` | `employment.yaml:employment_insurance_act_70` | ✓ | slug 분기 (`육아휴직_급여_계산기`) |
| 4대보험 | `insurance.yaml` | `insurance.yaml:four_major_insurances` | ✓ | slug 분기 (`four-insurances`) |
| 연말정산 | `tax.yaml` | *(tax.yaml에 엔티티 없음 — master에 직접)* | ✓ | slug 분기 (`연말정산_환급액_계산기`) |

**현재 정의 분포**:
- Registry v3 (`docs/registry/*.yaml`): 계산기 메타(display_order, card_desc, field_labels, writer_context, legal_refs)
- legal_master (`docs/legal_master/*.yaml`): 법령 조항 엔티티 (law/article/calculation_flow/forbidden_phrases 등)
- DB (`calculators` 테이블): input_schema, output_schema, formula, faq, seo_title, seo_desc
- `app_generator._compute_js()`: 계산 JS 로직 (복잡 계산기는 slug 분기 하드코딩)
- `legal_basis.master.yaml`: 구(舊) SSOT — `load_registry()`가 여전히 읽는 파일. `app_generator._registry()`가 이 경로 사용

**중요 발견**: `registry_loader.py`에 두 개의 로드 경로가 공존한다.
- **구 경로**: `load_registry()` → `legal_basis.master.yaml` + `registry_auto.yaml` → `app_generator._registry()`가 사용
- **신 경로**: `load_registry_v3()` → `docs/registry/*.yaml` → `generate_index()`, `generate_sitemap()`, `resolve()` 사용

신규 계산기는 두 경로에 모두 반영되어야 한다.

---

### 1-2. Registry v3 신규 계산기 추가 필드

기존 7개 YAML을 기준으로 스키마 분류:

**필수 필드**:
```yaml
<slug>:                          # URL path 겸 고유 키 (영소문자, 하이픈 또는 한글)
  name: "<계산기명>"              # 한글 표시명
  slug: "<slug>"                 # 위와 동일
  category: "<카테고리>"          # 예: 노무/급여, 세금/정부혜택
  emoji: "<이모지>"               # 카드 표시용
  card_label: "<카드 레이블>"     # 카드 상단 텍스트
  compute_type: <타입>            # single | date_based | dict (출력 구조)
  date_fields: []                # 날짜 입력 필드 목록 (없으면 [])
  validation_mode: <모드>         # formula | skip
  field_labels:                  # 입력/출력 필드 표시명 (input_schema 키와 1:1)
    <field_key>: "<표시명>"
  display_order: <정수>           # 홈 그리드 정렬 순서 (기존 1~7, 신규는 8+)
  card_desc: "<한 줄 설명>"       # 홈 카드 설명문
  difficulty: <난이도>            # simple | date_based | complex | multi_output
  difficulty_status: provisional  # 현재 전원 provisional
  content:
    evergreen: true|false
    update_cycle: null|yearly
    content_caveat: null|crude_estimate
  related_slugs:                 # 관련 계산기 slug 목록
  - <slug>
  legal_refs:                    # legal_master entity ID 목록
  - <entity_id>
  writer_context:
    emphasize:                   # Writer가 강조할 포인트
    - <항목>
    example_patterns:            # 글에 포함할 예시 케이스
    - <케이스>
    calculation_story:           # 계산기 설명 1줄 요약
    - <설명>
```

**선택 필드** (복잡 계산기에만):
- `benefit_amounts`: 실업급여의 daily_max, min_wage_hourly 등 수치
- `benefit_days_table`: 실업급여 수급일수 테이블
- `compute_rules`: 입력 검증 규칙 (양수/최솟값 등)

---

### 1-3. writer_context 필요 데이터

기존 6종 구조 분석:

| 항목 | 내용 | 예시 |
|---|---|---|
| `emphasize` | Writer가 반드시 언급할 법적 조건/예외 | "주 15시간 이상 조건", "IRP 의무이전" |
| `example_patterns` | 본문에 포함할 현실적 케이스 | "3년 근무 후 퇴직하는 직장인" |
| `calculation_story` | 계산기 목적 1줄 요약 | "퇴직금은 1년에 30일분 평균임금으로 계산됨" |

**신규 계산기 writer_context 작성 최소 요구사항**:
1. 해당 계산기의 핵심 법적 조건 2~3개 (Tier 1) 또는 핵심 산식 요약 (Tier 2)
2. 일반 직장인이 자주 오해하는 케이스 1~2개
3. 계산기 목적 1줄 설명

---

### 1-4. legal_master 필요 데이터

legal_master 엔티티 필드:

```yaml
<entity_id>:
  law: <법령명>
  article: <조항>
  related_articles: []
  authority: <소관기관>
  confidence: high|medium|low
  last_verified: <날짜>
  verification_source: [law.go.kr, easylaw.go.kr]
  writer_note: |
    Writer 지시문 (법적 표현 주의사항, 인용 금지 조항 등)
  reviewer_expectation:
    - <H-4 검수 기준>
  forbidden_articles: []
  forbidden_phrases: []
  needs_human_legal: true|false
  calculation_flow:
    - <계산 단계 설명>
```

**Tier별 요구사항**:

| 구분 | 설명 | legal_master 필요 여부 | 작성 난이도 |
|---|---|---|---|
| Tier 1 | 노동법/세법/고용보험법 근거 필요 | 필수 (법령 조항 + calculation_flow) | 높음 (법률 검토 필요) |
| Tier 2 | 순수 산술 공식 | 선택 (참고 법령이 있으면 추가, 없어도 무방) | 낮음 |

Tier 2 예시: 프리랜서 3.3% = `소득세법 제127조` (원천징수율) → 단순 참조, calculation_flow 불필요

---

### 1-5. 계산 로직/schema 필요 항목

**DB calculators 테이블 필수 컬럼**:
```
name, slug, category, calculator_type,
seo_title, seo_desc,
formula (수식 문자열 또는 ""),
input_schema (JSON: {field: type}),
output_schema (JSON: {field: type}),
faq (JSON array),
status = "active"
```

**계산 로직 위치**:
- **단순 공식** (Tier 2): `formula` 필드에 수식 문자열 → `_compute_js()` generic 분기에서 JS 자동 생성
- **복잡 로직** (Tier 1 일부): `modules/app_generator._compute_js()` 내 slug 분기 → 직접 JS 코드 작성 필요
- **날짜 기반**: `compute_type: date_based` + `validation_mode: skip` → `_compute_js()` date_based 분기 자동 처리

현재 slug 분기가 필요한 계산기 (app_generator.py:349,411,461,481,568):
- `unemployment-benefit` (수급일수 테이블, 상/하한)
- `four-insurances` (4종 요율 계산)
- `annual-leave-allowance` (별도 분기이나 단순)
- `육아휴직_급여_계산기` (6+6 특례)
- `연말정산_환급액_계산기` (11단계 세금 계산)

단순 formula 자동 처리 계산기: `weekly-holiday-allowance` (시급 × 시간 공식)

---

### 1-6. SEO/FAQ/H-4 자동 처리 가능 여부

| 컴포넌트 | 신규 계산기 자동 처리 | 비고 |
|---|---|---|
| `calculator_seo_generator` | **자동** | calc.name/category를 읽어 SEO 생성 |
| `calculator_faq_generator` | **자동** | calc.faq(DB) + registry writer_context 활용 |
| `calculator_writer_prompt.txt` | **자동** | 공통 프롬프트, legal_basis_block이 자동 주입 |
| H-4 Quality Gate | **자동** | QUALITY_GATE 설정 기준, slug 무관 |
| `_legal_basis_block()` | **자동** | registry + legal_master 읽어 자동 주입 |

추가 프롬프트 커스터마이징 없이 신규 계산기 추가 가능. 단, legal_master의 `writer_note`와 `forbidden_phrases`가 H-4 심사 기준에 영향을 주므로 작성 품질이 중요.

---

### 1-7. GitHub Pages 생성 과정 코드 수정 필요 여부

| 생성 대상 | 자동 여부 | 근거 |
|---|---|---|
| 홈 (`index.html`) 계산기 카드 | **자동** | `generate_index()`: `load_registry_v3()` 순회 → display_order 정렬 |
| `sitemap.xml` | **자동** | `generate_sitemap()`: `load_registry_v3()` 순회 |
| 계산기 페이지 (`/{slug}/`) | **자동** | `_rebuild_site.py`: DB `repo.get_all()` 순회 |
| 계산기 JS 로직 | **조건부 자동** | 단순 formula → 자동. 복잡 로직 → 코드 추가 필요 |
| `_RELATED_POSTS` 관련 글 | **무관** | 현재 비활성(`return ""`) — 신규 추가해도 영향 없음 |

**사이트 재생성 방법**: `scripts/_rebuild_site.py` 실행 → `data/workspace/_site/` 갱신 → GitHub commit → GitHub Actions 자동 배포.

P2-2-C에서 `_LABELS`/`_CALC_DESCS`/`_SLUG_ORDER` 제거 완료로, index/sitemap은 Registry v3에서 완전 자동화됨.

---

### 1-8. WordPress 콘텐츠 생성과의 관계

| 항목 | 관계 |
|---|---|
| V2 콘텐츠 생성 (`run_calculator_once`) | DB `calculators` 테이블 순회 → **신규 계산기 추가 즉시 자동 포함** |
| P2-3 RMS 리라이트 후보 | `IMPACT_MAP` (rms.py)에 등록된 entity만 탐지 → **신규 계산기는 수동 등록 필요** |
| P2-3 time-based 리라이트 후보 | articles 테이블 기준 → **자동 (365일 경과 후)** |
| `collect_rewrite_candidates()` | 계산기 신규 추가와 무관, 기존 published articles 대상 |

WordPress V2 콘텐츠는 DB에 계산기가 등록되면 다음 `run_calculator_once` 실행 시 자동으로 대상에 포함된다.

---

### 1-9. 계산기 1개 추가 시 실제 수정 파일 목록

#### Tier 2 (단순 공식) 기준:

**사람이 직접 작성해야 하는 작업**:

| 파일 | 작업 내용 | 난이도 |
|---|---|---|
| `docs/registry/<category>.yaml` | 새 계산기 YAML 항목 추가 | 중 (템플릿 복사 후 작성) |
| `docs/legal_master/<category>.yaml` | 법령 엔티티 추가 (Tier 1) / 선택 (Tier 2) | 높음 (Tier 1) / 낮음 (Tier 2) |
| `docs/legal_basis.master.yaml` | 구 SSOT에도 등록 필요 (app_generator._registry() 경로) | 중 |
| DB (`calculators` 테이블) | seed_calculators 실행 또는 직접 upsert | 낮음 |
| `modules/rms.py IMPACT_MAP` | 신규 계산기가 추적 중인 법령 엔티티에 의존하면 추가 | 낮음 |

**자동으로 처리되는 작업**:

| 파일/기능 | 자동화 조건 |
|---|---|
| `index.html` 카드 | registry v3 추가 → 즉시 |
| `sitemap.xml` | registry v3 추가 → 즉시 |
| `/{slug}/index.html` 생성 | DB 추가 + `_rebuild_site.py` 실행 |
| SEO 생성 | DB 추가 → 자동 |
| FAQ 생성 | DB + writer_context → 자동 |
| H-4 품질 검수 | 항상 자동 |
| P2-3 time-based 후보 | 발행 365일 후 자동 |

#### Tier 1 (복잡 로직) 추가 필요 작업:

| 파일 | 추가 작업 |
|---|---|
| `modules/app_generator._compute_js()` | 신규 slug 분기 + JS 계산 로직 작성 |
| `modules/calculator_seed.py SAMPLE_CALCULATORS` | 새 항목 추가 (시드 재실행 시 필요) |

---

### 1-10. 하드코딩 잔존 여부

#### 발견된 하드코딩 목록:

| 위치 | 내용 | 신규 추가 시 영향 | 위험도 |
|---|---|---|---|
| `app_generator.py:349` | `slug == "unemployment-benefit"` | 신규 계산기에 미적용 (정상 fallback) | **낮음** |
| `app_generator.py:411` | `slug == "four-insurances"` | 동상 | **낮음** |
| `app_generator.py:461` | `slug == "annual-leave-allowance"` | 동상 | **낮음** |
| `app_generator.py:481` | `slug == "육아휴직_급여_계산기"` | 동상 | **낮음** |
| `app_generator.py:568` | `slug == "연말정산_환급액_계산기"` | 동상 | **낮음** |
| `app_generator.py:45-102` `_RELATED_POSTS` | 7개 slug 명시 dict | **비활성** (`return ""`) — 신규 추가해도 표시 안 됨 | **없음** |
| `modules/rms.py:62-87` `IMPACT_MAP` | entity → slug 매핑 | 신규 계산기 누락 시 RMS 리라이트 미탐지 | **중간** |
| `modules/calculator_seed.py:33` | `SAMPLE_CALCULATORS` 7종 명시 | 시드 재실행 시 신규 계산기 미포함 | **낮음** (prod 영향 없음) |
| `site_generator.py:332` | 페이지 title: "퇴직금·주휴수당·실업급여·4대보험" | 신규 계산기 미반영 (텍스트 수동 갱신 필요) | **낮음** (SEO 문구, 기능 무관) |
| `site_generator.py:333,294,358` | description/hero 텍스트에 7개 명시 | 동상 | **낮음** |
| `scripts/_rebuild_site.py:2,38` | 주석 "7종 계산기" | 주석 오류(실제 동작 무관) | **없음** |

#### 핵심 판단:

`_compute_js()` 분기는 **if-elif 구조가 아닌 독립 if 블록**이므로, 신규 계산기가 기존 분기에 오진입하지 않는다. 신규 계산기 추가 시 기존 7개 계산기는 **깨지지 않는다**.

단, 복잡 로직이 필요한 신규 계산기(Tier 1)는 `_compute_js()` 분기를 추가하지 않으면 generic formula 분기로 fallback → **계산 결과가 0 또는 오류** 가능.

---

## 2. 계산기 1개 추가 시 필요 작업 전체 목록

| # | 작업 | 자동/수동 | Tier 2 | Tier 1 |
|---|---|---|---|---|
| 1 | `docs/registry/<category>.yaml` 항목 추가 | 수동 | ✓ 필수 | ✓ 필수 |
| 2 | `docs/legal_master/<category>.yaml` 엔티티 추가 | 수동 | 선택 | ✓ 필수 |
| 3 | `docs/legal_basis.master.yaml` 항목 추가 | 수동 | ✓ 필수 | ✓ 필수 |
| 4 | DB `calculators` 테이블 upsert | 수동 | ✓ 필수 | ✓ 필수 |
| 5 | `modules/rms.py IMPACT_MAP` 추가 | 수동 | 조건부 | ✓ 필수 |
| 6 | `app_generator._compute_js()` slug 분기 추가 | 수동 | X 불필요 | ✓ 필수 |
| 7 | `site_generator.py` title/desc 문구 갱신 | 수동 | 선택 | 선택 |
| 8 | `calculator_seed.py SAMPLE_CALCULATORS` 추가 | 수동 | 선택 | 선택 |
| — | `index.html` 카드 자동 생성 | **자동** | — | — |
| — | `sitemap.xml` 자동 생성 | **자동** | — | — |
| — | `/{slug}/` 페이지 자동 생성 | **자동** | — | — |
| — | SEO/FAQ 자동 생성 | **자동** | — | — |
| — | H-4 품질 검수 자동 | **자동** | — | — |
| — | V2 WordPress 콘텐츠 생성 자동 포함 | **자동** | — | — |
| — | P2-3 time-based 리라이트 자동 포함 | **자동** | — | — |

---

## 3. 결론 5가지

---

### ① Registry SSOT 검증

**부분적으로 SSOT. 여전히 두 곳을 수동으로 작성해야 한다.**

- Registry v3 (`docs/registry/*.yaml`) → `generate_index()`, `generate_sitemap()` 에 적용
- `legal_basis.master.yaml` (구 SSOT) → `app_generator._registry()` 경로에서 여전히 사용

따라서 신규 계산기 추가 시 `docs/registry/*.yaml` **와** `docs/legal_basis.master.yaml` **양쪽을 모두 갱신해야** 한다. 두 소스 중 하나만 쓰면 index 카드는 보이지만 JS 계산이 안 되거나, JS는 되지만 카드가 안 나오는 상황 발생 가능.

향후 Phase에서 `app_generator._registry()` 호출을 `load_registry_v3()` + `resolve()`로 전환하면 단일 SSOT 가능 (현재는 두 경로 병행 구조).

---

### ② 자동화 vs 수동 경계

**자동화 완료된 부분**:
- 홈 카드/sitemap/robots → Registry v3만 추가하면 자동
- 계산기 페이지 HTML 생성 → DB만 추가하면 `_rebuild_site.py` 자동
- SEO/FAQ/Writer/H-4 → 완전 자동

**여전히 수동인 부분**:
- Registry v3 YAML 작성 (계산기 정의)
- legal_master YAML 작성 (법령 근거, Tier 1)
- legal_basis.master.yaml 이중 등록 (구 경로 지원)
- DB 등록 (calculators 테이블)
- `_compute_js()` JS 로직 (복잡 계산기)
- `IMPACT_MAP` 업데이트 (RMS 연동)

---

### ③ 하드코딩 리스크

**즉시 위험한 하드코딩: 없음.**

`_compute_js()` slug 분기는 신규 계산기를 오탐하지 않는다. 신규 계산기 추가 시 기존 7개 계산기가 깨질 가능성은 없다.

**잠재적 위험 (기능 누락)**:
- 복잡 Tier 1 계산기를 `_compute_js()` 분기 없이 추가하면 계산 JS가 generic fallback으로 동작 → 틀린 결과 출력 가능
- `IMPACT_MAP` 미등록 시 해당 계산기는 법령 변경 감지(RMS) 후보에서 제외됨

**무기능 하드코딩 (수정 불필요)**:
- `_RELATED_POSTS`: 비활성화됨, 안전
- `_rebuild_site.py` 주석 "7종": 동작에 무관

---

### ④ 첫 계산기 후보 분류

**Tier 2 (순수 산술, 경량 검증) 후보**:

| 후보 | 공식 | legal_refs | _compute_js 분기 필요 | 추천도 |
|---|---|---|---|---|
| **프리랜서 3.3% (원천징수)** | `net = gross × (1 - 0.033)` | 소득세법 제127조 (참조용) | **불필요** | ★★★★★ |
| 전세 vs 월세 비교 | 전환이율 공식 | 없음 | 불필요 | ★★★★ |
| 군인 전역일 계산기 | 입대일 + 복무기간(date_based) | 없음 | 불필요 (date_based 분기 재사용) | ★★★★ |

**Tier 1 (법적 근거 필수) 후보**:

| 후보 | 복잡도 | _compute_js | 추천도 |
|---|---|---|---|
| 월급 실수령액 (근로소득세+4대보험) | 높음 | 신규 분기 필요 | ★★★ |
| 투잡 종합소득세 | 매우 높음 | 신규 분기 필요 | ★★ |
| 육아기 근로시간 단축 급여 | 높음 | 신규 분기 필요 | ★★ |

---

### ⑤ Phase3-0 → Phase3-1 전환 조건

다음 3가지가 확인되면 즉시 설계(Phase3-1)로 전환 가능:

1. **첫 계산기 slug/name/category 확정** — 이 감사 결과에서 후보 제안됨
2. **Tier 확인** — 단순 공식이면 `_compute_js` 신규 분기 불필요 확인
3. **legal_refs 엔티티 ID 확정** — 기존 legal_master에 없는 새 조항이면 작성 범위 포함

현재 상태: 조건 1 후보 확인됨(프리랜서 3.3%), 조건 2 충족(Tier 2, formula 자동), 조건 3 확인 필요(소득세법 제127조 엔티티 신규 작성 필요). **→ Phase3-1 진입 가능.**

---

## 4. 첫 계산기 후보 제안 및 근거

### 권장 후보: 프리랜서 3.3% 원천징수 계산기

**slug**: `freelancer-tax-3p3`  
**name**: 프리랜서 원천징수 계산기  
**category**: 세금/정부혜택  
**compute_type**: `single`  
**validation_mode**: `formula`

**공식**:
```
withholding_tax = gross_income * 0.033
net_income      = gross_income * 0.967
```

**근거**:

| 항목 | 내용 |
|---|---|
| 구조 검증 최적 | formula-based → `_compute_js` 신규 분기 불필요. 파이프라인 전체 자동 경로 검증 가능 |
| 법적 단순성 | 소득세법 제127조 3.3% (소득세 3% + 지방소득세 0.3%) — 법령 조항 단순 |
| 수요 검증 | "프리랜서 3.3%" 검색량 높음, 기존 7개 계산기와 중복 없음 |
| 이중 소스 작성 | registry v3 + legal_basis.master.yaml 양쪽 작성 패턴 검증 기회 |
| 위험 최소 | 기존 7개 계산기 코드 변경 없음. 실패해도 기존 서비스 무영향 |

**Phase3-1에서 설계할 파일 (예상)**:
1. `docs/registry/tax.yaml` — 새 항목 추가 (연말정산 아래)
2. `docs/legal_master/tax.yaml` — `income_tax_act_127` 엔티티 추가
3. `docs/legal_basis.master.yaml` — 동일 내용 병행 추가 (구 경로 지원)
4. DB seed — `calculators` 테이블 upsert (input: gross_income, output: withholding_tax/net_income)
5. `modules/rms.py IMPACT_MAP` — 조건부 (`min_wage_hourly` 관련 없음, 소득세율 고정)

**`app_generator._compute_js()` 수정: 불필요** (formula generic 분기 자동 처리)

---

## 부록: 조사 중 발견된 구조 메모

- `registry_loader.py:131` `add_auto_entry()` 함수 존재 — App Factory가 DB 외 등록 시 `registry_auto.yaml`에 자동 추가 가능
- `app_generator._RELATED_POSTS` — V2 WordPress 블로그 연동 시 활성화 예정. 신규 계산기 추가 시 빈 배열 반환되므로 관련 글 섹션 미표시 (정상)
- `site_generator.py:332` 페이지 title/description 문구 — 신규 계산기 추가 후 선택적으로 갱신 권장 (SEO 효과)
- `scripts/_rebuild_site.py` — 사이트 재생성 스크립트. 신규 계산기는 DB 추가 후 이 스크립트 1회 실행으로 반영됨

---

*이 문서는 Phase3-0 조사용 읽기 전용 산출물입니다. 코드 변경 없이 작성됨.*
