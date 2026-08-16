# Phase 5-E 원인분석 + 수정설계 문서

> **작성일**: 2026-08-16  
> **작성 목적**: DeepSeek 교차검수에서 발견된 문제들의 코드 레벨 원인 확정 + 다음 생성 단계를 위한 수정 설계안  
> **이 문서의 범위**: 분석 + 설계만. 코드 수정/콘텐츠 수정/WordPress 게시물 변경 없음.

---

## 요약: 발견된 문제 vs 근본 원인

| # | 문제 현상 | 근본 원인 | 심각도 |
|---|-----------|----------|-------|
| 1 | 계산기 링크 0개, CTA 0개 | `_NO_LINK_RULE`이 AI 금지 + 자동삽입 약속 → 자동삽입 코드 미구현 | Critical |
| 2 | FAQ-본문 숫자 충돌 (04번: 3.52% vs 3.545%) | FAQ와 본문이 별도 AI 호출, G-CALC가 FAQ를 검사하지 않음 | Critical |
| 3 | 과거 금액 혼입 (07번: 150만원, 현행 250만원) | `LAW_VERSION`/법정수치 SSOT가 프롬프트에 주입되지 않음 | Critical |
| 4 | 카테고리 미분류 | `calculator_categories.yaml` 존재하나 publish 스크립트가 무시 | Major |
| 5 | 10번 신고기한 오류 (7일 → 법적 14일) | 위 3번과 동일 원인 (AI training data 의존) | Critical |
| 6 | 05번 H2 구조 오류 (`계산기 이용 방법` ← howto 미적합) | LEGACY_H2_PATTERN이 이 패턴을 포함하지 않음 | Major |
| 7 | 글 간 주제어 혼입 의심 | FAQ 생성이 `_ctx(calc)` 만으로 이루어지고 본문과 독립 생성 | Minor |

---

## A. 2026년 법정수치 SSOT 설계

### 문제 원인

`config/config.yaml`에 `LAW_VERSION: 2026-07`이 정의되어 있으나, 이 값은 `modules/config_loader.py`를 통해 로드되고 내부 버전 태깅에만 사용된다. `content/calculator/prompt.py`의 `get_article_prompt()`, `get_faq_prompt()` 어디에도 법정수치 SSOT 블록이 주입되지 않는다.

`QUALITY` 상수(prompt.py line 21)는 "법령·요율은 입력/시스템 제공 값만 사용"이라고 지시하지만, 시스템이 실제로 어떤 값도 제공하지 않으므로 AI는 training data에서 법정수치를 가져온다. 육아휴직 150만원(pre-2024), 4대보험 FAQ의 3.52%/12.95%(구율)가 이로 인해 발생했다.

**확정된 오류 값**:
- 07번 육아휴직: 본문·FAQ 모두 "첫 3개월 상한 150만원" → 현행(2026): 첫 6개월 250만원(6+6 부모육아휴직제)
- 04번 4대보험 FAQ: "건강보험료 3.52%, 장기요양 12.95%" → 현행: 건보 3.545%, 장기요양 12.96%
- 10번 4대보험 서류: "보통 7일 이내" → 법적 기한 14일 이내

### 설계 방향

`config/config.yaml`에 `LAW_SSOT` 섹션을 추가하고, `get_article_prompt()` 및 `get_faq_prompt()` 모두에 SSOT 블록을 주입하는 헬퍼 함수 `_law_ssot_block(slug: str) -> str`을 신설한다.

```yaml
# config/config.yaml 추가 설계 (현행 아님 — 설계안)
LAW_SSOT:
  four-insurances:
    health_insurance_rate: "3.545%"
    ltc_rate: "12.96% (건보료의)"
    pension_rate: "4.5%"
    employment_insurance_rate: "0.9%"
    report_deadline: "취득일로부터 14일 이내"
  육아휴직_급여_계산기:
    first_6months_cap: "250만원 (6+6 부모육아휴직제, 2024년 이후)"
    after_6months_cap: "160만원"
    minimum: "70만원"
    law_basis: "고용보험법 제70조~제73조, 2024년 개정"
  severance-pay:
    minimum_tenure_days: 365
    law_basis: "근로자퇴직급여 보장법 제8조"
  unemployment-benefit:
    min_employment_days: 180
    law_basis: "고용보험법 제40조"
  weekly-holiday-allowance:
    min_weekly_hours: 15
    law_basis: "근로기준법 제55조"
  annual-leave-allowance:
    law_basis: "근로기준법 제60조"
```

`get_faq_prompt(calc, legal_ssot=None)`로 시그니처 변경. `legal_ssot`가 있으면 시스템 프롬프트 맨 앞에:

```
[2026년 현행 법정수치 — 이 값만 사용, AI 추측 절대 금지]
{slug별 ssot 내용}
```

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `config/config.yaml` | `LAW_SSOT` 섹션 추가 |
| `content/calculator/prompt.py` | `_law_ssot_block(slug)` 추가, `get_faq_prompt()` / `get_article_prompt()` 시그니처 변경 |
| `scripts/phase5_c_sample_gen.py` | `get_faq_prompt(calc, legal_ssot=ssot)` 호출부 수정 |

### 기존시스템 존재여부

- `LAW_VERSION` 태그: **이미존재** (config.yaml) — 확장 가능
- SSOT 주입 로직: **신규** 필요
- slug별 SSOT 데이터: **신규** 필요 (수동 입력 불가피)

---

## B. G-CONSISTENCY: FAQ-본문 숫자 일관성 Gate

### 문제 원인

`content/calculator/prompt.py`에서 `get_faq_prompt(calc)`는 `_ctx(calc)`만 입력받아 독립 AI 호출로 생성된다. `get_article_prompt(calc, faq=faq_list)`는 FAQ를 JSON으로 받아 본문에 삽입하지만, FAQ가 먼저 생성되고 본문이 나중에 생성되는 구조다.

기존 G-CALC 게이트(`modules/content_integrity.py`)는 `example_context.examples[].result` 값이 **본문**에 등장하는지만 검사한다. **FAQ가 같은 숫자를 올바르게 사용하는지 교차검증하는 Gate가 없다**.

04번 아티클에서:
- 본문: "건강보험 106,350원(3.545%)" ← `example_context`에서 옴, G-CALC 통과
- FAQ: "건강보험료는 월 급여의 3.52%" ← AI training data, Gate 없음

### 설계 방향

G-CONSISTENCY Gate를 신설한다. 검사 대상: `<dt>...<dd>` 블록에서 퍼센트/원화 숫자를 추출하고, 본문 body에서 같은 맥락의 숫자와 비교.

구체적 알고리즘:
1. FAQ의 `<dd>` 텍스트에서 `\d+\.?\d*%` 패턴으로 rate 값 추출
2. 본문 전체에서 동일 rate 패턴 추출
3. FAQ rate가 본문에 없거나 다른 값이면 WARN (Critical 아님 — 본문이 정답, FAQ가 outdated일 가능성)
4. `LAW_SSOT`에 해당 slug의 값이 있으면 FAQ/본문 모두 SSOT와 대조

```python
# modules/content_integrity.py에 추가할 Gate 설계
def run_g_consistency(body_html: str, slug: str, ssot: dict) -> GateResult:
    """FAQ rate vs 본문 rate vs SSOT rate 3방향 비교"""
    faq_rates = _extract_rates_from_faq(body_html)
    body_rates = _extract_rates_from_body(body_html)
    ssot_rates = ssot.get(slug, {})
    
    issues = []
    for rate in faq_rates:
        if rate not in body_rates:
            issues.append(f"FAQ rate {rate} not found in body")
    if ssot_rates:
        for k, v in ssot_rates.items():
            if isinstance(v, str) and "%" in v:
                if not _rate_appears(body_html, v):
                    issues.append(f"SSOT {k}={v} missing from article")
    return GateResult(passed=len(issues) == 0, issues=issues, grade="major")
```

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `modules/content_integrity.py` | `run_g_consistency()` 추가, `run_integrity_gates()`에 등록 |
| `scripts/_phase5e_integrity_check.py` | 새 gate 포함하도록 runner 업데이트 |

### 기존시스템 존재여부

- G-CALC (본문 vs example_context): **이미존재** — FAQ 대상 확장 필요
- G-CONSISTENCY (FAQ vs 본문): **신규**

---

## C. G-LEGAL-CURRENT: 법령 최신성 Gate

### 문제 원인

`_LEGAL_FORBIDDEN` (`modules/content_integrity.py`)은 특정 키워드(예: "사직서" in 퇴직금 글)가 출현하면 차단하는 방식이다. **"3.52%"처럼 outdated 법정수치가 등장했을 때 이를 탐지하는 Gate가 없다**.

10번 글의 "7일 이내" 역시 어떤 Gate도 탐지하지 못했다. 법적 기한/요율이 outdated인지 검사하는 메커니즘 자체가 Phase 5-C 파이프라인에 없다.

### 설계 방향

G-LEGAL-CURRENT Gate를 신설한다. `LAW_SSOT` 데이터에서 "금지해야 할 outdated 표현"과 "허용된 현행 표현"을 함께 정의한다.

```yaml
# config/config.yaml LAW_SSOT 확장 설계
LAW_SSOT:
  four-insurances:
    forbidden_rates:  # 이 값이 본문/FAQ에 나오면 FAIL
      - "3.52%"
      - "12.95%"
      - "3.535%"
    current_rates:
      - "3.545%"
      - "12.96%"
    forbidden_deadlines:
      - "7일 이내"   # 4대보험 취득신고 컨텍스트
    current_deadlines:
      - "14일 이내"
  육아휴직_급여_계산기:
    forbidden_caps:
      - "150만원"     # pre-2024
      - "120만원"     # pre-2024 이후 상한
    current_caps:
      - "250만원"     # 첫 6개월
      - "160만원"     # 이후
```

Gate 로직:
```python
def run_g_legal_current(body_html: str, slug: str, ssot: dict) -> GateResult:
    slug_ssot = ssot.get(slug, {})
    plain = _strip_html(body_html)
    issues = []
    for forbidden in slug_ssot.get("forbidden_rates", []) + slug_ssot.get("forbidden_caps", []) + slug_ssot.get("forbidden_deadlines", []):
        if forbidden in plain:
            issues.append(f"Outdated value '{forbidden}' found in article")
    return GateResult(passed=len(issues) == 0, issues=issues, grade="critical")
```

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `config/config.yaml` | `LAW_SSOT.*.forbidden_*` / `current_*` 추가 |
| `modules/content_integrity.py` | `run_g_legal_current()` 추가 |
| `scripts/_phase5e_integrity_check.py` | 새 gate 포함 |

### 기존시스템 존재여부

- G-LEGAL (특정 키워드 금지): **이미존재** — outdated 수치로 확장 필요
- slug별 forbidden 수치 목록: **신규**

---

## D. G-LINK: 계산기 링크/CTA Gate

### 문제 원인 (확정)

`content/calculator/prompt.py` line 70-77의 `_NO_LINK_RULE`:
```python
"- 관련 계산기 섹션을 본문에 작성하지 않는다. 관련 계산기/관련 글 링크는 시스템이 자동 삽입한다.\n"
"- CTA(계산기 사용하기) 섹션은 작성하지 않는다. 시스템이 본문 뒤에 자동 삽입한다.\n"
```

AI가 이 지시를 따라 링크/CTA를 생성하지 않았다. 그런데 `scripts/phase5_c_sample_gen.py`와 `scripts/_phase5c_wp_publish.py` 어디에도 "자동 삽입" 로직이 없다.

- `get_cta_prompt()` (prompt.py line 160): 존재하지만 Phase 5-C 생성 흐름에서 한 번도 호출되지 않음
- `publish_quality.py`의 `_count_cta()`: 검사만 하고, 삽입 기능은 없음
- `_phase5c_wp_publish.py`의 `payload` 딕셔너리: `categories`, CTA 관련 필드 없음

결과적으로 10개 아티클 전부 `<h2>계산기 사용하기</h2>` = 0개, 계산기 링크 = 0개.

### 설계 방향

게시 직전 `build_gutenberg()` 호출 전에 CTA 블록과 계산기 링크를 후처리로 삽입한다. AI 생성 단계에서 삽입하지 않는다(현재 `_NO_LINK_RULE` 유지).

**CTA 블록 템플릿**:
```python
# 신설: modules/cta_builder.py
SITE_URL = cfg["SITE_URL"]  # "https://calcmate.kr"

def build_cta_block(slug: str, calc_name: str) -> str:
    url = f"{SITE_URL}/{slug}/"
    return (
        f'<h2>계산기 사용하기</h2>\n'
        f'<p>{calc_name}를 직접 사용해 정확한 금액을 확인하세요.</p>\n'
        f'<p><a href="{url}" target="_blank" rel="noopener">'
        f'{calc_name} 바로가기</a></p>\n'
    )
```

**내부링크 블록 템플릿**:
```python
def build_internal_links_block(slug: str, related_slugs: list) -> str:
    """config/calculator_categories.yaml의 same-category slug들을 링크로 생성"""
    links = []
    for rel_slug in related_slugs[:3]:  # 최대 3개
        ...
    return f'<div class="internal-links">{...}</div>'
```

**삽입 위치**: `build_gutenberg()` 내부에서 `body_html` 끝에 CTA 블록을 append한 뒤 Gutenberg 블록으로 조립.

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `modules/cta_builder.py` | **신규** — CTA 블록 + 내부링크 블록 생성 |
| `scripts/_phase5c_wp_publish.py` | `build_gutenberg()` 내에서 `cta_builder` 호출 |
| `config/config.yaml` | `SITE_URL` 이미 존재 — 활용만 |
| `config/calculator_categories.yaml` | 이미 존재 — related slug 조회에 사용 |

### 기존시스템 존재여부

- `get_cta_prompt()`: **이미존재** (prompt.py) — 사용 안 됨
- CTA 삽입 로직: **신규**
- 내부링크 블록 (`_count_internal_links`): **이미존재** (publish_quality.py) — 생성 로직은 신규
- `_dedupe_cta()`: **이미존재** (publish_quality.py) — 중복 제거용, 활용 가능

---

## E. H2 구조 검증 강화 (G-STRUCTURE)

### 문제 원인

`scripts/phase5_c_sample_gen.py` line 61-63의 `LEGACY_H2_PATTERN`:
```python
LEGACY_H2_PATTERN = re.compile(
    r'<h2[^>]*>\s*(?:계산기\s*소개|입력\s*방법|결과\s*확인)\s*</h2>', re.I
)
```

05번 아티클(howto intent)에서 `<h2>계산기 이용 방법</h2>`가 출현했으나 이 패턴에 포함되지 않아 통과됐다. `INTENT_H2_MAP["howto"]`에 `"이용 절차"`가 정의되어 있는데 `"계산기 이용 방법"`이 생성됐다는 것은 H2 구조 검증이 통과 기준이 아닌 참고 기준으로만 작동했음을 의미한다.

실제로 `phase5_c_sample_gen.py`의 H2 검증은:
```python
# G-NEW1: intent별 H2 패턴 검증 — 현재 WARN만 출력, FAIL 처리 없음
```
형태로 소프트 경고만 발생시키고 재생성을 트리거하지 않는 것으로 파악된다.

### 설계 방향

`LEGACY_H2_PATTERN`을 확장하거나, `INTENT_H2_MAP`과 실제 H2를 대조하는 강도를 높인다.

```python
# LEGACY_H2_PATTERN 확장안
LEGACY_H2_PATTERN = re.compile(
    r'<h2[^>]*>\s*(?:계산기\s*소개|입력\s*방법|결과\s*확인|계산기\s*이용\s*방법|'
    r'이용\s*방법|사용\s*방법|사용\s*안내)\s*</h2>',
    re.I
)
```

그리고 G-STRUCTURE gate를 추가: `INTENT_H2_MAP[intent]`에 정의된 H2가 모두 존재하는지 검사하고, 하나라도 없으면 Major fail.

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `scripts/phase5_c_sample_gen.py` | `LEGACY_H2_PATTERN` 확장, G-STRUCTURE 강화 |
| `modules/content_integrity.py` | `run_g_structure(html, intent)` 추가 (선택적) |

### 기존시스템 존재여부

- `LEGACY_H2_PATTERN`: **이미존재** — 확장 필요
- `INTENT_H2_MAP`: **이미존재** — 검증 강도 강화 필요

---

## F. H. 카테고리 자동지정

### 문제 원인

`config/calculator_categories.yaml`에 전체 11개 계산기의 카테고리·태그가 정의되어 있다:
```yaml
four-insurances:
  categories: ["노동", "보험"]
  tags: ["4대보험", "급여계산"]
```

`scripts/_phase5c_wp_publish.py`의 `publish_one()` → `payload` 딕셔너리(line 203-212)에 `categories`, `tags` 키가 없다. WordPress REST API는 `categories: [id1, id2]` 형식으로 받기 때문에, slug → category_name → WordPress category_id 변환 단계가 필요하다.

### 설계 방향

`publish_one()` 내에 3단계 처리를 추가:
1. `calculator_categories.yaml`에서 slug의 `categories` 리스트 조회
2. WordPress REST API `GET /wp-json/wp/v2/categories?slug=노동`으로 category_id 조회
3. 없으면 `POST /wp-json/wp/v2/categories`로 신규 생성
4. `payload["categories"] = [id1, id2]` 삽입

```python
# 설계: _phase5c_wp_publish.py에 추가할 함수
def _resolve_wp_category_ids(session, category_names: list) -> list[int]:
    ids = []
    for name in category_names:
        r = session.get(f"{WP_BASE}/wp-json/wp/v2/categories", params={"search": name})
        results = r.json()
        if results:
            ids.append(results[0]["id"])
        else:
            r2 = session.post(f"{WP_BASE}/wp-json/wp/v2/categories", json={"name": name})
            ids.append(r2.json()["id"])
    return ids
```

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `scripts/_phase5c_wp_publish.py` | `_resolve_wp_category_ids()` 신설, `load_article()` + `publish_one()` 수정 |
| `config/calculator_categories.yaml` | 변경 없음 — 읽기만 |

### 기존시스템 존재여부

- `calculator_categories.yaml`: **이미존재**
- category_id 조회/생성 로직: **신규**

---

## G. G-IMAGE-SEMANTIC: 이미지-글 주제 정합성 Gate

### 문제 원인

생성된 이미지가 글 주제와 불일치하는 경우(예: 퇴직금 글에 육아 이미지)를 탐지할 게이트가 없다. `phase5_c_sample_gen.py`의 `CALC_VISUAL_THEME`과 `INTENT_IMAGE_PREFIX`는 이미지 프롬프트 생성에 사용되지만, 실제 생성된 이미지가 프롬프트에 맞게 생성됐는지 검증하는 단계가 없다.

이미지 내용을 자동으로 검증하려면 Vision API 호출이 필요하므로 비용/복잡도 대비 효과가 낮다.

### 설계 방향

현 단계에서 자동화 Gate보다는 **이미지 생성 프롬프트 기록 + 체계적 수동 검수**가 현실적이다.

- `requests/` JSON의 `images.thumbnail.prompt`, `images.body.prompt` 필드에 사용된 실제 프롬프트를 저장
- 검수 시 프롬프트와 결과 이미지를 나란히 확인
- 완전 자동화는 Phase 6 이후 Vision-based gate로 대체

### 구현 시 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `scripts/phase5_c_sample_gen.py` | 이미지 생성 결과에 사용된 프롬프트를 request JSON에 기록 |

### 기존시스템 존재여부

- 이미지 프롬프트 저장: **부분존재** (request JSON에 alt는 있으나 prompt 원문 없음)
- Vision-based semantic check: **신규** (현 단계 보류)

---

## I. 기존 코드 재사용 vs 신규 구현 분류표

| 항목 | 대상 파일 | 상태 | 작업 규모 |
|------|----------|------|----------|
| A. LAW_SSOT 주입 | `config/config.yaml`, `content/calculator/prompt.py` | 신규 | 중 (데이터 입력 + 함수 추가) |
| B. G-CONSISTENCY | `modules/content_integrity.py` | 신규 | 소 (rate 추출 함수 + gate) |
| C. G-LEGAL-CURRENT | `config/config.yaml`, `modules/content_integrity.py` | 신규 | 소 (forbidden 목록 + gate) |
| D. CTA 자동삽입 | `modules/cta_builder.py` (신규), `scripts/_phase5c_wp_publish.py` | 신규 | 중 |
| E. 내부링크 자동삽입 | `modules/cta_builder.py`, `config/calculator_categories.yaml` 활용 | 신규 | 중 |
| F. H2 구조 강화 | `scripts/phase5_c_sample_gen.py` | 이미존재 확장 | 소 |
| G. 이미지 Gate | 보류 | — | — |
| H. 카테고리 자동지정 | `scripts/_phase5c_wp_publish.py` | 신규 | 소 |

---

## 콘텐츠별 영향 분석

### 10개 Phase 5-C 콘텐츠에 이 설계 적용 시

모든 문제는 생성 단계 결함이므로, **재생성 없이 후처리로 해결 가능한 항목**과 **재생성 필수 항목**을 분리한다.

**후처리로 수정 가능** (재생성 불필요):
- H. 카테고리 → WordPress API 업데이트
- D. CTA + 내부링크 → 기존 게시물 content에 append 후 `PUT /posts/{id}`

**재생성 필수** (법정수치/구조 오류):
- 07번 육아휴직: 본문+FAQ 전체 재생성 (150만원 → 250만원)
- 04번 4대보험 FAQ: FAQ 재생성 또는 본문+FAQ 재생성 (3.52% → 3.545%)
- 10번 4대보험 서류: 본문+FAQ 재생성 (7일 → 14일)
- 05번 연차수당: 본문 재생성 (H2 구조 오류 + 계산기 이용 방법)

**현행 유지 가능** (검수 통과 수준):
- 01번, 02번, 03번, 06번, 09번 — 사실 오류 없음, 후처리(CTA+카테고리)만

### 37개 기존 콘텐츠에 이 설계 적용 시

37개 콘텐츠는 구 pipeline(`calculator_pipeline.py`)으로 생성된 것으로, 구조 자체가 다르다(구 H2 패턴 사용). 이 설계의 새 Gate들을 37개에 직접 적용하면:

- G-LEGAL-CURRENT: slug별 forbidden 수치 탐지로 법정수치 오류 있는 게시물 식별 가능
- G-CONSISTENCY: 구 pipeline 글도 FAQ-본문 rate 비교 가능
- CTA/내부링크: 37개 모두 `<h2>계산기 사용하기</h2>` 없을 가능성 높음 — 일괄 후처리 가능
- 카테고리: 37개 모두 미분류 상태일 가능성 — 일괄 category 할당 가능

**단, 37개에 대한 실제 수정 작업은 이 문서의 범위 외 (별도 Phase에서 결정).**

---

## 다음 단계 (이 문서 승인 후)

1. 설계 승인 → 구현 순서 확정
2. 구현 우선순위 (제안):
   - 1순위: A (SSOT) + C (G-LEGAL-CURRENT) — 신뢰성 핵심
   - 2순위: D (CTA 삽입) + H (카테고리) — 게시 품질
   - 3순위: B (G-CONSISTENCY) + F (H2 강화) — Gate 강화
3. 07, 04, 10, 05번 4개 아티클 재생성
4. 10개 전체 후처리 (CTA + 카테고리) → WordPress 업데이트
5. 재검수 (Phase 5-F)
