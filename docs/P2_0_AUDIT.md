# CalcMate P2-0 Architecture Audit

기준일: 2026-08-08  
범위: V1.0.0 코드베이스 (Feature Freeze 완료)  
목적: Phase 2 설계를 위한 현재 구조 파악  
조사 방법: 코드 읽기 전용 (수정 없음)

---

## 1. 계산기 정의 위치 (3중 정의 문제)

계산기 1개를 추가하려면 현재 **최소 3곳**을 수정해야 한다.

| 위치 | 파일 | 역할 | 수동 여부 |
|------|------|------|----------|
| DB seed | `modules/calculator_seed.py` SAMPLE_CALCULATORS | DB 초기 적재 (formula, input/output schema, FAQ, seo_title, seo_desc) | 수동 |
| Registry SSOT | `docs/legal_basis.master.yaml` | 법령 + 계산기 메타 (law, article, compute_type, related_slugs, emoji 등) | 수동 |
| Hardcode | `modules/app_generator.py` | `_LABELS`, `_PLACEHOLDERS`, `_INTERNAL_LINK_MAP`, `_KW_SLUG` | 수동 |
| Hardcode | `modules/site_generator.py` | `_CALC_DESCS` (홈페이지 카드 설명) | 수동 |

추가로 **Sprint B-1** 신구조(아직 프로덕션 미연결)에도 작성 필요:

| 위치 | 파일 |
|------|------|
| Registry v3 | `docs/registry/{category}.yaml` |
| Legal master | `docs/legal_master/{category}.yaml` |

계산기 1개 추가 시 실제 건드려야 하는 파일: **최소 6개**.

---

## 2. Registry 시스템 현황

### 2-1. 현재 프로덕션이 사용하는 경로 (구조)

```
load_registry()  ←  modules/registry_loader.py
  ├── docs/registry_auto.yaml     (현재 비어있음 — header 주석만)
  └── docs/legal_basis.master.yaml  ← 프로덕션 SSOT (동일 slug 우선)
```

`load_registry()` 는 `app_generator._registry()` → `calculator_pipeline._load_legal_basis()` → `publish_quality` 등 모든 핵심 모듈이 위임. **단일 진입점 구조는 올바르다.**

`legal_basis.master.yaml`에는 7개 계산기가 schema_version 2로 정의됨:
- 법령 필드: law, article, related_articles, authority, confidence, writer_note, forbidden_articles/phrases
- Registry 필드: slug, category, emoji, card_label, compute_type, date_fields, validation_mode, related_slugs, compute_rules

### 2-2. Sprint B-1 신구조 (존재하지만 프로덕션 미연결)

```
load_registry_v3()  ←  registry_loader.py
  └── docs/registry/*.yaml    (labor, employment, insurance, tax — 7개 계산기 정의됨)

load_legal_master()  ←  registry_loader.py
  └── docs/legal_master/*.yaml  (labor, employment, insurance, tax — 법령 엔티티 분리)

resolve(slug)  ←  위 둘을 합성
```

`docs/registry/*.yaml` 4개 파일에 7개 계산기가 **이미 작성**되어 있고,  
`docs/legal_master/*.yaml` 4개 파일에 법령 엔티티가 **이미 분리**되어 있다.  
그러나 **`load_registry_v3()` / `resolve()` 를 실제로 호출하는 프로덕션 코드는 없다.**

→ P2-1에서 이 두 경로를 연결하면 신구조로 전환 완료.

### 2-3. 두 구조의 데이터 불일치 가능성

`legal_basis.master.yaml`과 `docs/registry/*.yaml`은 현재 별도로 존재한다. 동기화 도구 없음. 수동으로 유지 중.

---

## 3. Site 생성 파이프라인

### 3-1. 사이트 정적 페이지 (`site_generator.generate_all`)

`scripts/_rebuild_site.py` 호출 → `modules/site_generator.generate_all(cfg)` 반환값:

```
index.html           홈페이지 (계산기 카드 그리드)
site.css             공용 CSS
about/index.html     소개
privacy/index.html   개인정보처리방침
terms/index.html     이용약관
contact/index.html   문의하기
404.html             에러 페이지
sitemap.xml          12 URL (5 static + 7 calculator)
robots.txt           User-agent * / Allow / Sitemap
```

홈 계산기 카드는 `_registry()` + `_SLUG_ORDER`에서 동적 조회 (새 계산기 추가 시 자동 반영 — 단, `_SLUG_ORDER` 갱신 필요).

### 3-2. 계산기 개별 페이지 (`app_generator.generate_calculator`)

`_rebuild_site.py` → 각 계산기별 `app_generator.generate_calculator(calc, cfg)` 호출.

```
{slug}/index.html    계산기 HTML (template: calculator_v2.html)
{slug}/style.css     계산기 CSS (design_system.css + 컴포넌트 CSS)
{slug}/script.js     계산기 JS (analytics.js + formula + components.js 등 번들)
```

`calculator_v2.html`은 Jinja-스타일이 아닌 `{{PLACEHOLDER}}` 치환 방식.  
GA4 스크립트, naver 메타태그, JSON-LD, 입력폼, FAQ, 관련계산기 등 모두 Python에서 생성해 치환.

**주의**: `_TPL` 변수(line 27)는 `calculator_v1.html`을 참조하지만,  
실제 생성에는 `_TPL_V2`(`calculator_v2.html`)가 사용됨 → v1 참조는 사실상 dead code.

---

## 4. 콘텐츠(WordPress) 파이프라인

`modules/calculator_pipeline.py` → WordPress 블로그 포스트 생성.

```
Calculator(DB) → KeywordGenerator → SEOGenerator → WriterAgent
  → QualityGate → Publisher(WordPress)
```

`_load_legal_basis()` 내부에서 `load_registry()` 호출 → legal 필드를 writer 프롬프트에 주입  
(forbidden_articles, forbidden_phrases, writer_note 등).

현재 `PUBLISH_SCHEDULE.enabled: false` — 자동 스케줄 비활성. 수동 실행만 가능.  
`RUN_MODE: wordpress` 이지만 CalcMate V1 정적 사이트와 독립적으로 동작.

---

## 5. 데이터 저장 (DB + Sheets)

### 5-1. DB 어댑터

`DB_ADAPTER: dual` → SQLite(기본) + Google Sheets(동기화)  
`SQLITE_PATH: data/blog_auto.db`

### 5-2. `calculators` 테이블 주요 필드

| 필드 | 설명 |
|------|------|
| id | `calc_` + timestamp + uuid4[:4] (예: calc_20260805121653_0065) |
| slug | URL slug |
| name / category | 계산기명/분류 |
| formula | Python-스타일 수식 문자열 (JS 변환용) |
| input_schema | JSON {"field": "number"/"date"} |
| output_schema | JSON {"field": "number"} |
| faq | JSON 배열 |
| seo_title / seo_desc | SEO 메타 |
| labels | JSON {field: label} — 계산기별 라벨 오버라이드 (대부분 비어있음) |
| related_slugs | **DB에서는 비어있음** — 실제 related_slugs는 registry(legal_basis.master.yaml)에만 있음 |
| article_content | AI 생성 WordPress 콘텐츠 |
| status | active / draft / hold |

### 5-3. 현재 7개 계산기 DB ID

```
calc_20260805121653_0065 | severance-pay
calc_20260805121654_01c3 | annual-leave-allowance
calc_20260805121656_f443 | unemployment-benefit
calc_20260805121657_98d3 | four-insurances
calc_20260806100007_18a9 | weekly-holiday-allowance
calc_20260806223827_a5d9 | 연말정산_환급액_계산기
calc_20260806223828_6152 | 육아휴직_급여_계산기
```

---

## 6. 하드코딩된 데이터 목록 (P2에서 Registry로 흡수 대상)

### `modules/app_generator.py`

| 변수 | 위치 | 내용 | Registry 흡수 가능? |
|------|------|------|---------------------|
| `_LABELS` | line 29–50 | 입력/출력 필드의 한글 레이블 (~25개) | ✅ `field_labels` 필드로 |
| `_PLACEHOLDERS` | line 55–63 | 입력 필드 예시값 | ✅ registry 신필드로 |
| `_RELATED_POSTS` | line 66–123 | 관련 블로그 포스트 링크 (현재 비활성) | N/A (V2에서 재설계) |
| `_INTERNAL_LINK_MAP` | line 1158–1187 | 계산기 키워드 → 상대 href + 앵커 텍스트 변형 | ✅ registry + 키워드 필드로 |
| `_KW_SLUG` | line 1190–1198 | 키워드 → slug 매핑 | ✅ registry name/keyword 필드로 |
| `_SLUG_ORDER` | line 1202 | `_INTERNAL_LINK_MAP` 키 순서 파생 | ✅ registry 순서 필드로 |

### `modules/site_generator.py`

| 변수 | 위치 | 내용 | Registry 흡수 가능? |
|------|------|------|---------------------|
| `_CALC_DESCS` | line 21–29 | 홈페이지 계산기 카드 한줄 설명 | ✅ registry `card_desc` 신필드로 |

**소결**: 새 계산기 추가 시 Python 코드 6곳을 수동으로 수정해야 한다. P2-1에서 이것들을 YAML registry로 이동하면 "YAML 1파일 추가 → 사이트 자동 반영" 구조가 된다.

---

## 7. P2-1 Registry 자동화를 위한 작업 목록

"계산기 추가 시 N곳 수동 수정" → "1곳만 수정(registry YAML)" 달성을 위한 변경:

### Step 1: 신구조(`registry_v3` + `legal_master`) 프로덕션 연결

- `app_generator._registry()`: `load_registry()` → `load_registry_v3()` (또는 `resolve()`) 로 교체
- `calculator_pipeline._load_legal_basis()`: 동일하게 신구조로 교체
- 기존 `legal_basis.master.yaml` 역할을 `docs/legal_master/*.yaml` + `docs/registry/*.yaml` 이 대체

### Step 2: 하드코딩 데이터를 Registry YAML로 이동

| 항목 | 이동 대상 |
|------|----------|
| `_LABELS` (field_labels) | `docs/registry/*.yaml` 의 `field_labels` 필드 |
| `_PLACEHOLDERS` | `docs/registry/*.yaml` 에 `field_placeholders` 신필드 추가 |
| `_CALC_DESCS` | `docs/registry/*.yaml` 에 `card_desc` 신필드 추가 |
| `_INTERNAL_LINK_MAP` | `docs/registry/*.yaml` 에 `link_keywords` 신필드 추가 |
| `_KW_SLUG` | 위와 동일 (`link_keywords` 에서 파생) |
| `_SLUG_ORDER` | `docs/registry/*.yaml` 에 `display_order: int` 신필드 추가 |

### Step 3: 코드에서 하드코딩 제거

- `app_generator.py`에서 `_LABELS`, `_PLACEHOLDERS`, `_INTERNAL_LINK_MAP`, `_KW_SLUG`, `_SLUG_ORDER` 제거
- `site_generator.py`에서 `_CALC_DESCS` 제거
- 각 함수가 registry에서 동적으로 읽도록 변경

### Step 4: `calculator_seed.py`의 formula/schema를 Registry로 흡수 (선택)

현재 formula, input_schema, output_schema는 DB(seed에서 적재)에만 있다.  
이것도 registry YAML에 옮기면 "YAML만 있으면 계산기 완성" 구조가 가능.  
단, 기존 DB 데이터와의 정합성 관리 필요 → P2-2(계산기 추가 자동화) 에서 진행 권고.

---

## 8. 기술 부채 / 위험 요소

### 8-1. 두 Registry 시스템의 병행 (가장 큰 위험)

`docs/legal_basis.master.yaml`(구) 과 `docs/registry/*.yaml` + `docs/legal_master/*.yaml`(신) 이 동시에 존재.  
현재 동기화 자동화 없음 → 한쪽만 수정하면 불일치 발생.  
**P2-1 전환 완료 전까지 legacy SSOT는 `legal_basis.master.yaml` 단일**로 유지해야 안전.

### 8-2. `related_slugs` 의 이중 위치

- Registry: `legal_basis.master.yaml` / `docs/registry/*.yaml` 에 있음 (실제 사용 중)
- DB `calculators.related_slugs`: **모두 비어있음**

Registry 없이 DB만으로 관련 계산기 링크를 렌더링할 수 없다. Registry 의존성이 강함.

### 8-3. `calculator_v1.html` 참조 Dead Code

`app_generator.py` line 27: `_TPL = ... / "calculator_v1.html"` 참조.  
실제 생성에는 `_TPL_V2`(`calculator_v2.html`)만 사용됨.  
`_TPL` 은 더 이상 사용되지 않지만 import되어 있음 → 혼란 유발.

### 8-4. `_RELATED_POSTS` Dead Code

`app_generator.py` line 66–123의 `_RELATED_POSTS` dict:  
`render_related_posts()`가 `return ""` 로 단락 처리되어 있어 데이터가 전혀 사용되지 않음.  
V2 블로그 연결 전까지 그대로 보존 (V1 Freeze 원칙).

### 8-5. `_SLUG_ORDER` 의 파생 방식

```python
_SLUG_ORDER = [k for k in _INTERNAL_LINK_MAP]
```

Python 3.7+ dict 삽입 순서를 이용한 순서 파생.  
`_INTERNAL_LINK_MAP`에 새 계산기를 추가할 때 순서 관리가 암묵적 → 실수 시 홈페이지 카드 순서, sitemap 순서 변동.

### 8-6. `registry_auto.yaml` 비어있음

App Factory (`save_app`)가 자동생성하는 구조이지만 현재 V1에서 App Factory는 미사용.  
파일 자체는 존재(header 주석만). `load_registry()`는 이를 먼저 읽고 master가 덮어쓰므로 빈 파일은 무해.

### 8-7. 두 slug 인코딩 혼재

영문 slug: `severance-pay`, `weekly-holiday-allowance` 등  
한글 slug: `연말정산_환급액_계산기`, `육아휴직_급여_계산기`  
URL에서 퍼센트 인코딩이 자동 적용되어 현재 작동하지만, 향후 계산기 추가 시 일관성 정책 결정 필요.

---

## 9. 결론 및 P2-1 권고사항

### P2-1에서 가장 먼저 해야 할 것 3가지

**① `load_registry_v3()` / `resolve()` 프로덕션 연결**

이미 `docs/registry/*.yaml` + `docs/legal_master/*.yaml` 에 7개 계산기가 정의되어 있다.  
`app_generator._registry()` 와 `calculator_pipeline._load_legal_basis()` 에서 `load_registry_v3()` + `resolve()` 를 호출하도록 교체하면 신구조 전환이 완료된다.  
기존 `legal_basis.master.yaml`은 rollback 대비로 보존.

**② `_CALC_DESCS` + `_SLUG_ORDER` 를 Registry YAML로 이동**

이 두 항목이 가장 빈번하게 새 계산기 추가 시 누락되는 부분이다.  
`docs/registry/*.yaml`에 `card_desc: str`과 `display_order: int` 필드를 추가하고,  
`site_generator.py`와 `app_generator.py`에서 registry를 읽도록 변경.

**③ 계산기 추가 절차 문서화 + 검증 스크립트**

현재 새 계산기 추가에 관한 단일 절차 문서가 없다.  
`docs/HOW_TO_ADD_CALCULATOR.md`(또는 동등한 문서)와  
"registry 필수 필드 누락 여부 체크" 스크립트를 작성하면  
P2-2(자동화) 전까지 수동 실수를 방지할 수 있다.

---

*이 문서는 read-only 조사 결과이며, 코드 수정은 포함하지 않는다.*  
*다음 단계: P2-1 Registry 자동화 설계 → 승인 → 구현.*
