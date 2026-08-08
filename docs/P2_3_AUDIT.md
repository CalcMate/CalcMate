# P2-3 자동 리라이트 파이프라인 Audit 결과

조사 일자: 2026-08-08  
조사 방법: 코드 읽기 전용 (수정 없음)  
대상: modules/ · content/ · content_pipeline/ · repositories/ · prompts/ · docs/registry/ · docs/legal_master/

---

## 1. 기존 파이프라인 구조 (A항목 7개)

### A-1. Writer — 세 개의 분리된 경로

프로젝트에 writer 경로가 **3개** 존재하며 역할이 다르다.

**경로 ①: Production Calculator Pipeline** (`modules/calculator_pipeline._write_article()`, L217)
```
입력: cfg, calc(DB row), keyword, seo, faq, failed_rules, intent
출력: (body_html: str, tokens: int)
프롬프트: prompts/calculator_writer_prompt.txt  (6-H2 고정 템플릿)
호출 경로: run_calculator_once() → generate_seo() → generate_faq() → _write_article() → check_publish_quality() → publisher.publish()
```
실제 WordPress 발행은 이 경로만 사용한다. `failed_rules`가 있으면 재생성 지시 블록(`_rewrite_block`)이 추가 주입된다.

**경로 ②: Policy/Blog Pipeline** (`modules/writer.write_draft()`, L70)
```
입력: clean_data(정책 정보), seo_data, strategy, related_links, cfg
출력: (body_html: str, tokens: int)
프롬프트: SYSTEM_M3_POLICY 또는 SYSTEM_M3_CALCULATOR (소스 내 하드코딩)
호출 경로: V2 RSS/정책 파이프라인 (run_once) → writer.write_draft()
```
계산기 글이 아닌 정책/RSS 수집 기반 글 생성용. 현재 이 경로와 경로 ①은 완전히 분리.

**경로 ③: Calculator Content Generator** (`content/calculator/writer.generate_article()`, 실제 파일)
```
입력: cfg, calc, seo, faq, review, example_context, intent
출력: str (body_html)
프롬프트: content/calculator/prompt.py (별도 프롬프트 모듈)
호출 경로: content_pipeline/engine_adapter.run_content_generation() → modules/calculator_content_generator(shim) → content/calculator/writer
```
`content_pipeline/` 오케스트레이터에서만 사용. 프로토타입 상태(하단 A-7 참조).

---

### A-2. SEO Generator (`modules/calculator_seo_generator.py`)

```python
# 주요 공개 함수
generate_seo(cfg, name: str, keyword: str, intent: str) -> {seo_title, seo_description, seo_keywords}
generate_seo_title(cfg, calc: dict) -> str     # _seo_pair() 래퍼
generate_meta_description(cfg, calc: dict) -> str
```

입력: 계산기명(str) + 타겟 키워드(str) + intent 문자열  
출력: SEO 제목(28~40자, 연도 포함) · 메타설명 · 키워드 리스트  
intent="eligibility" 분기 존재 (지급조건형 제목 생성).  
모델: `writing` 역할(MODEL_WRITER). 비용 추적 BudgetTracker 포함.  
경로 ①에서 `generate_seo()`를, 경로 ③에서 `_seo_pair()`를 각각 호출.

---

### A-3. FAQ 생성 (`modules/calculator_faq_generator.py`)

```python
generate_faq(cfg, name_or_calc, n=6, n_max=8) -> list[dict]
# 반환: [{"question": ..., "answer": ...}, ...]
```

name(str) 또는 calc(dict) 양쪽 입력 허용. 6~8개 FAQ 생성.  
실패 시 5개 기본 FAQ 폴백(하드코딩).  
경로 ①에서는 DB에 저장된 FAQ 우선 → 없으면 `generate_faq()` 호출.  
경로 ③에서는 `generate_faq(cfg, calc)` 직접 호출.  
`calculator_pipeline.py` L407: `if calc.get("faq"): ... else: faq = generate_faq(cfg, calc.get("name", keyword))`

---

### A-4. H-4 Quality Gate (`modules/publish_quality.py`)

```
check_publish_quality(cfg, body_html, final_html, calc, link_pool_size) -> Rewrite Contract dict
반환: {result: PASS|WARN|REWRITE, score, severity, failed_rules, html, quality_review_model}
```

**자동 Gate(G1~G8 결정론, GPT 미호출):**

| 게이트 | 기준 | 등급 | 대상 HTML |
|---|---|---|---|
| G1 | 본문 가시텍스트 1800~2500자 | major | body_html |
| G2 | H2 5~7개 | major | body_html |
| G3 | FAQ ≥5문항 (`<dt>` 기준) | major | body_html |
| G4 | 계산 예시 ≥2개 | major | body_html |
| G5 | 내부링크 ≥2개 (Adaptive — pool 수 기준 완화) | **critical** | final_html |
| G6 | CTA "계산기 사용하기" 정확히 1회 (초과분 자동 삭제) | **critical** | final_html |
| G7 | AI 문체 금지표현 블록리스트 | minor | body_html |
| G8 | legal_basis 법령명·조항·소관기관 매칭 (결정론 문자열) | **critical** | body_html |

**AI Score(S1~S6):** Gate 전체 통과 후에만 GPT 채점. PASS ≥90 / WARN ≥80 / REWRITE <80.  
`_quality_signature(cfg, calc)` — 프롬프트+게이트+법적근거 SHA1[:8]. 이 서명이 바뀌면 HOLD 자동 재도전.  
`calculator_writer_prompt.txt`의 6-H2 구조와 G1~G4 게이트가 설계상 1:1 대응.

**H-4와는 별개인 두 번째 품질 시스템:**  
`content_pipeline/`의 `content_quality/quality_validator.QualityValidator` (A-7 참조). Production 미사용.

---

### A-5. Publisher (`modules/publisher.py`)

```python
# 신규 발행 — calculator_pipeline이 PASS/WARN 시 호출
publish(post_id, seo_data, html_body, image_urls, cfg) -> {wordpress, wp_post_id, wp_permalink, wp_status, published_at, status}

# 기존 글 수정 — 현재 dashboard 수동 편집에서만 호출, 파이프라인 미연결
update_post(cfg, wp_post_id, title=None, content=None, excerpt=None) -> {success, wp_post_id, link, modified, status}

# 보조
delete_post(cfg, wp_post_id, force=False) -> {success, ...}
restore_post(cfg, wp_post_id) -> {success, ...}
get_post(cfg, wp_post_id) -> {success, status, title, link, modified, ...}
```

WP 미구성(`is_wordpress_ready()` False) 시: `publish()`는 `"검수대기"` 로컬 미리보기만 저장하고 graceful 반환.  
`update_post()`는 `publisher.py:95~146`에 완전히 구현됨. None 필드는 미전송(수정 안 함)·빈 문자열은 삭제 구분.  
**핵심**: 리라이트를 위한 `update_post()`는 이미 존재. 파이프라인 연결만 없음.

---

### A-6. Duplicate 검사 (`modules/duplicate_checker.py`)

```python
check_duplicate(new_doc: str, existing_docs: list[str], cfg) -> (is_duplicate: bool, max_similarity: float)
```

임베딩(text-embedding-3-small) + 코사인 유사도 3단계:  
- ≥0.85 → 즉시 차단  
- ≤0.75 → 즉시 통과  
- 0.76~0.84 → AI Judge (GPT 판정)

**현재 production 미사용**: `calculator_pipeline.py`는 `check_duplicate()`를 호출하지 않는다.  
중복 방지는 `existing_by_calc[cid]`(제목 집합)과 `art_repo.count_active_articles()`로만 처리한다.  
`duplicate_checker.py`는 V2 정책/RSS 파이프라인(`modules/strategist.py` 계열)용.  
리라이트에서는 "동일 계산기 글 갱신"이므로 중복 개념 자체가 없음 — 재사용 불필요.

---

### A-7. Publish History 저장 구조 (`repositories/article_repository.py`)

DB 테이블: `articles` (AbstractDBAdapter → SQLite or Google Sheets 이중화)

```
주요 컬럼:
  ID, 정책명(keyword), 최종추천제목, 메타설명, 태그, 발행 URL,
  wp_post_id, wp_permalink, wp_status, published_at, 발행일시,
  원본출처, 상태값, site_id, calculator_id,
  quality_score, quality_status, quality_failed_rules,
  quality_review_model, quality_reviewed_at, quality_prompt_version
```

상태값 유효 목록:  
`대기·진행중·작성중·이미지오류·작성오류·발행완료·발행실패·복구대기·보류·만료·재처리대기·수정됨·휴지통·품질보류·재처리완료`

이력 추적: `append_history(article_id, event, extra)` → `history` 컬럼(JSON 배열) append.  
현재 기록 이벤트: `publish`, `quality_hold`, `quality_hold_released`.  
리라이트 추가 시 `rewrite` 이벤트를 추가하면 감사 추적 완성.

**Dual storage**: `adapters/db/` AbstractDBAdapter → SQLite(로컬) + Google Sheets(sheet_sync) 이중 저장.  
리라이트 이력도 동일 경로에 기록 가능.

---

## 2. 리라이트 개념 정의 (B항목 3개)

### B-1. 최초 생성 vs 리라이트 코드 분리 여부

**현재: 분리 안 됨.**  
`calculator_pipeline.run_calculator_once()`는 항상 신규 `publish()` 경로로만 발행한다.  
`publisher.update_post()`는 dashboard 수동 편집 외에 어떤 파이프라인에서도 호출되지 않는다.  
내부 "REWRITE" 개념은 품질 게이트 실패 시 동일 실행 내 재생성(retry)을 의미하며, 기존 WP 글 갱신이 아니다.

최초 생성과 갱신의 분기점이 될 코드:
```python
# 현재 없는 코드 — P2-3에서 추가할 부분
if existing_article.get("wp_post_id"):
    publisher.update_post(cfg, wp_post_id, content=new_html)  # 갱신
else:
    publisher.publish(post_id, seo_data, html_body, image_urls, cfg)  # 최초 발행
```

### B-2. 리라이트 트리거 후보

현재 자동 트리거 메커니즘은 없다. 후보:

| 트리거 | 코드 상태 | 연결 난이도 |
|---|---|---|
| RMS 법령 변경 감지 (`revision_detector.py`) | 감지까지 완성. IMPACT_MAP/legal_refs로 영향 계산기 특정 가능 | 중 — 감지→재생성 연결 코드 필요 |
| Registry v3 내용 변경 (writer_context, deduction_rules) | 변경 감지 미구현. `_quality_signature` 확장 필요 | 중 |
| `published_at` 경과 기간 (예: 6개월) | 단순 날짜 비교. `articles` 테이블에 `published_at` 존재 | 하 |
| 품질 게이트 재검사 결과 미달 | `check_publish_quality()` 재실행 가능. 기존 HTML 어디서 가져올지 문제 | 중 |

법령 변경(RMS) 연결 구조가 이미 `revision_detector.analyze_impact()` → slug 목록 반환까지 있으므로, 트리거로서 가장 의미 있는 후보.

### B-3. Slug/URL 유지 구조

**WordPress 블로그 글**: `wp_post_id`를 `articles` 테이블에 저장. `update_post(cfg, wp_post_id, content=...)` 호출 시 WP REST API가 해당 게시물만 수정하며 permalink/slug 불변. 안전.

**GitHub Pages 계산기 위젯**: `app_generator.py`가 DB `slug` 컬럼 기준으로 경로 생성. 리라이트와 무관하게 `_rebuild_site.py`로 언제든 재생성. 리라이트 영향 없음.

**calculator_id**: `articles` 테이블의 `calculator_id`는 갱신 행에서도 동일하게 유지. 삭제·재생성 없이 `update_post` + `append_history("rewrite", ...)` 패턴으로 기존 행 유지 가능.

---

## 3. Registry v3 연결 현황 (C항목 3개)

### C-1. writer_context 소비 여부

**연결됨.** `calculator_pipeline._resolve_context_block(calc)` (L188~L214):

```python
from .registry_loader import resolve
r = resolve(str(calc.get("slug", "")).strip()) or {}
dr = r.get("deduction_rules") or {}
cf = r.get("calculation_flow") or []
wc = r.get("writer_context") or {}
# → [계산 근거 데이터] 블록으로 writer 프롬프트에 주입
```

P2-1에서 `writer_context`가 보강된 registry YAML 현황:

| YAML | writer_context 보유 계산기 수 |
|---|---|
| labor.yaml | 3종 (주휴수당, 퇴직금, 연차수당) |
| employment.yaml | 2종 (구직급여, 육아휴직) |
| insurance.yaml | 1종 (4대보험) |
| tax.yaml | 1종 (연말정산) |

7종 전부 `writer_context`가 있으며, Production 파이프라인에서 즉시 소비 중.

### C-2. resolve() 확장 가능성

`resolve(slug)` = `load_registry_v3()[slug]` + `legal_refs` → `load_legal_master()` 병합.

P2-1 설계 단계에서 "연말정산 1종에만 실효성 있다"고 판단했으나, 현재 구조상으로는 **7종 전부 확장 가능**:
- `legal_master/` 디렉토리: `employment.yaml`, `insurance.yaml`, `labor.yaml`, `tax.yaml` 4개 존재.
- 각 YAML에 `legal_refs`가 있는 계산기는 `resolve()`가 `deduction_rules`/`calculation_flow`까지 병합.
- `연말정산_환급액_계산기`의 `deduction_rules`(소득공제 규칙)가 가장 풍부. 나머지 6종은 legal_master가 있어도 `deduction_rules`가 빈 경우 데이터 없이 no-op(빈 문자열 반환 — 정상 동작).
- P2-3에서 legal_master 데이터를 보강하면 바로 작동. 코드 변경 불필요.

### C-3. legal_master 실제 참조 여부

`_resolve_context_block()` → `resolve()` → `legal_master` 경로: **연결됨** (legal_master 데이터가 있는 slug에 한해).

`_legal_basis_block()` → `_load_legal_basis()` → `load_registry()` (OLD 경로, `legal_basis.master.yaml`): **별도 연결됨**.  
두 경로는 독립 동작. legal_master 수정 시 `_resolve_context_block`(writer 데이터), `_legal_basis_block`(법령 인용)이 모두 갱신됨.

---

## 4. V1/V2 대상 경계 확인 (D항목)

### 현재 엔진 분리 상태

| 엔진 | 대상 | 상태 | 파이프라인 |
|---|---|---|---|
| `modules/app_generator.py` | V1 GitHub Pages 계산기 위젯 페이지 | 운영 중 | `_rebuild_site.py` |
| `modules/calculator_pipeline.py` | V2 WordPress 블로그 글 (계산기 설명 SEO 글) | 운영 중 | 스케줄러 |
| `content/calculator/writer.py` | (동일) V2 WordPress 블로그 글 | 프로토타입 | `content_pipeline/` |
| `content/blog/writer.py` | V2 WordPress 일반 블로그 | **Stub (NotImplementedError)** | 없음 |
| `modules/writer.py` (write_draft) | 정책/RSS 수집 블로그 글 | 구 파이프라인 | run_once |

### P2-3 리라이트 대상

**P2-3 리라이트 = V2 WordPress 블로그 글** (`articles` 테이블, `wp_post_id` 보유 행).

V1 GitHub Pages 계산기 위젯 페이지는 P2-3 대상 아님:
- DB + Registry v3에서 결정론적으로 HTML 생성
- `_rebuild_site.py` 실행 시 즉시 전량 재생성
- 별도 리라이트 파이프라인 불필요

### content_pipeline/ 상태 — 프로토타입 확인

`content_pipeline/engine_adapter.py`에서 발견된 프로토타입 증거:
```python
from tests.test_weekly_holiday_compute import compute_weekly_allowance  # 테스트 코드 import
calc_id = "weekly-holiday-allowance"  # 하드코딩
calc_name = "주휴수당 계산기"          # 하드코딩
print(f"DEBUG PUBLISH: ...")           # debug print 잔존
print(f"DEBUG GATE: ...")              # debug print 잔존
```
`H3_FAQ`가 하드코딩 문자열 반환. `content/blog/writer.py`는 `NotImplementedError`.  
이 파이프라인은 P2-3 기반으로 사용 불가. 무시하고 `calculator_pipeline.py` 기반으로 구현.

---

## 5. 결론 5가지

### ① 재사용 가능 범위

| 컴포넌트 | 리라이트 재사용 | 판정 |
|---|---|---|
| `calculator_pipeline._write_article()` | 그대로 재사용 — `failed_rules`에 "갱신 이유"를 전달해 재생성 지시 추가 가능 | **그대로** |
| `calculator_seo_generator.generate_seo()` | 그대로 재사용 | **그대로** |
| `calculator_faq_generator.generate_faq()` | 그대로 재사용 (또는 DB FAQ 그대로 유지) | **그대로** |
| `publish_quality.check_publish_quality()` | 그대로 재사용 | **그대로** |
| `publisher.update_post()` | 이미 구현됨 — 파이프라인 연결만 없음 | **그대로** |
| `revision_detector.analyze_impact()` | 법령 변경→영향 계산기 목록까지 완성 | **연결만 필요** |
| `article_repository.append_history()` | `"rewrite"` 이벤트 추가하면 이력 추적 완성 | **그대로** |
| `duplicate_checker.check_duplicate()` | 리라이트에 중복 개념 없음 | **불필요** |
| `content_pipeline/` | 프로토타입 — 사용 불가 | **새로 설계** |
| `content/blog/writer.py` | NotImplementedError | **새로 설계** |

**신규 작성 필요한 것:**  
`run_calculator_rewrite(cfg, article_row, reason)` 함수 1개.  
기존 컴포넌트 조립 역할만 하면 됨. 새 AI 로직이나 새 모델 필요 없음.

---

### ② 리라이트 트리거 후보 (우선순위 순)

1. **법령 변경 (RMS 연동)**: `revision_detector.analyze_impact(entity_id)` → 영향 계산기 slug 목록 → 발행된 글 wp_post_id 조회 → 재생성 + `update_post`. 의미상 가장 타당한 트리거.

2. **`published_at` 경과**: `articles` 테이블 `published_at` 기준 6개월 이상 경과 + 최신 legal_basis와 불일치. 구현 가장 단순.

3. **Registry v3 writer_context 변경**: 현재 감지 미구현. `_quality_signature()` 방식을 registry hash 포함으로 확장해 갱신 판정 가능. 중간 난이도.

4. **품질 게이트 재검사**: 기존 발행 HTML을 DB에서 꺼내 `check_publish_quality()` 재실행. 현재 `articles` 테이블에 `html` 컬럼 없어 WP API `get_post()` 호출 필요 → 네트워크 의존성.

---

### ③ 안전성 리스크

| 리스크 | 상세 | 완화 방법 |
|---|---|---|
| WP API 실패 시 DB-WP 불일치 | `update_post()` 실패 시 DB `상태값`은 갱신됐지만 WP는 구 내용 | `update_post()` 성공 확인 후 DB 갱신. 실패 시 `"리라이트실패"` 상태 기록 |
| WP permalink 변경 | WP `update_post`는 title 변경 시 새 slug 생성 가능 | `title=None`(미전송) 또는 title 변경 금지 정책 |
| 발행이력 훼손 | 기존 행 삭제+재생성 패턴은 감사 이력 소실 | 기존 article 행 유지. `append_history("rewrite", ...)` 추가만 |
| 리라이트 중복 실행 | 동일 글 동시 재생성 | `articles` 테이블 `상태값`을 `"리라이트중"`으로 선점 후 진행 |
| calculator_id 소실 | - | `update_post`는 WP 포스트만 수정. DB `calculator_id` 불변 |

---

### ④ V1 계산기 위젯 vs V2 WordPress 블로그

| 구분 | V1 GitHub Pages (계산기 위젯) | V2 WordPress 블로그 (계산기 설명 SEO 글) |
|---|---|---|
| 생성 엔진 | `app_generator.py` | `calculator_pipeline.py` |
| 데이터 소스 | DB `calculators` + Registry v3 | DB `calculators` + `articles` + Registry v3 + legal_master |
| 리라이트 방식 | `_rebuild_site.py` (전량 재생성, 항상 결정론) | `publisher.update_post()` (개별 WP 포스트 갱신) |
| P2-3 대상 | **아님** — 재빌드 자동화로 충분 | **대상** |
| 발행이력 | 없음 (정적 파일) | `articles` 테이블 (`wp_post_id` 보유) |

**공통 엔진 가능성**: writer/SEO/FAQ는 공통 사용 가능. 발행 함수만 `publish()` vs `update_post()` 분기. 단, V1은 HTML 파일 출력이므로 공통화 실익 없음.

---

### ⑤ P2-3 구현 범위 제안

| 항목 | 판정 | 이유 |
|---|---|---|
| `run_calculator_rewrite(cfg, article_row, reason)` 함수 신규 | **구현 가능** | 기존 컴포넌트 조립만. `_write_article` + `update_post` 연결. 신규 AI 로직 없음 |
| 리라이트 트리거 — 수동 실행(API/CLI) | **구현 가능** | `only_cid` 패턴 이미 존재. 수동 재생성 최소 구현 |
| 리라이트 트리거 — RMS 법령 변경 자동 연동 | **추가 설계 필요** | `analyze_impact()` 결과→리라이트 스케줄링 연결 설계 필요. 현재 감지만 됨 |
| 리라이트 트리거 — published_at 경과 자동 | **구현 가능** | 단순 날짜 필터. 스케줄러에 추가 |
| 중복 방지 — 동일 계산기 동시 리라이트 방지 | **구현 가능** | `상태값` 선점 패턴 (`"리라이트중"`) 추가 |
| `articles` 테이블 `rewrite` 이벤트 이력 | **구현 가능** | `append_history("rewrite", ...)` 1줄 추가 |
| content_pipeline/ H4B_COMPETITIVE 활용 | **현재 보류** | 프로토타입 상태. 하드코딩·debug print 잔존. P2-3 범위 외 |
| `content/blog/writer.py` 구현 | **현재 보류** | NotImplementedError. P2-3 리라이트 대상 아님 |
| WP `get_post()` 재조회 후 리라이트 (freshness 확인) | **추가 설계 필요** | WP 네트워크 의존성 추가. 설계 결정 필요 |

---

## 6. P2-3 구현 범위 제안 표 (요약)

```
즉시 구현 가능 (기존 컴포넌트 조립만):
  [O] run_calculator_rewrite() 함수 — _write_article + check_publish_quality + update_post 연결
  [O] 수동 트리거 (CLI: python main.py rewrite --slug <slug>)
  [O] published_at 경과 자동 트리거 (스케줄러 추가)
  [O] rewrite 이벤트 이력 (append_history)
  [O] 동시 실행 방지 (상태값 선점)

추가 설계 필요:
  [△] RMS 법령 변경 → 자동 리라이트 연동 (analyze_impact + scheduler 연결)
  [△] Registry v3 writer_context 변경 감지 (hash 기반 비교 설계)
  [△] WP 현재 내용 재조회 후 freshness 판정

현재 보류:
  [X] content_pipeline/ H4B_COMPETITIVE 등 복잡 스테이지 (프로토타입 정리 후)
  [X] content/blog/writer.py V2 블로그 전용 엔진 (별도 PRD 필요)
```

---

*코드 수정 없음. 읽기 전용 조사. 조사 기준 커밋: a04d697*
