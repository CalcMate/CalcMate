# Phase 5-E 원인분석 + 수정설계 문서 (REV 2026-08-17)

> **작성일**: 2026-08-17 (REV — phase5e 구현 반영 재분류)
> **초판**: 2026-08-16
> **작성 목적**: DeepSeek 교차검수(2차 독립 QA)에서 발견된 문제들의 코드 레벨 원인 확정 + 다음 생성 단계를 위한 수정 설계안
> **이 문서의 범위**: 분석 + 설계만. 코드 수정/콘텐츠 수정/WordPress 게시물 변경 없음. Git commit 없음.
>
> **REV 반영 기준**: 2026-08-16 22:45~23:36에 커밋된 phase5e 1차 구현(cta_builder, content_integrity gates, LAW_SSOT, WP 게시/업데이트 스크립트, 04/05/07/10 재생성, 10개 WP 재업로드)이 이미 존재하므로, 아래 각 항목의 "기존시스템 존재여부"는 **현재 코드 상태** 기준으로 재분류했다.

---

## 요약: 발견된 문제 vs 근본 원인 vs 현재 상태

| # | 문제 현상 | 근본 원인 | 판정 | phase5e 현재 상태 |
|---|-----------|----------|------|------------------|
| 1 | 계산기 링크 0개, CTA 0개 | `_NO_LINK_RULE`이 AI 금지 + 자동삽입 약속 → **게시 시점(19:30) 스크립트에 자동삽입 코드 없음** + 생성 단계에서 G5/G6 명시적 제외 | **원인 확정** | 해결 수단 구현됨 (`modules/cta_builder.py` + 게시/업데이트 스크립트) — 다만 ContentRequest에 `calculator_url` 필드 없음(URL은 publish 시 slug로 합성) |
| 2 | FAQ-본문 숫자 충돌 (04번: 3.52% vs 3.545%) | FAQ와 본문이 **별도 AI 호출** — FAQ는 `_ctx(calc)`만 받고 example_context/legal_basis/SSOT 미전달, 본문은 검증 데이터 주입 | **원인 확정** | G-CONSISTENCY 구현됨(rate 한정) — 그러나 FAQ 생성 시 SSOT 미주입은 **그대로** |
| 3 | 과거 금액 혼입 (07번 150만원, 10번 7일) | example_context **하드코딩**(4.5%/3.545%/12.96%/0.9% = 2025 기준) + `content_ssot` 데이터가 2025 값이면서 `effective_year: 2026`으로 표기 | **원인 확정** | LAW_SSOT 주입 구현됨(2개 slug만) — **SSOT 데이터 자체 갱신은 아직** |
| 4 | 카테고리 전부 미분류 | 게시 시점 `_phase5c_wp_publish.py` 구버전이 `calculator_categories.yaml`을 사용하지 않음 | **원인 확정** | `_resolve_wp_category_ids()` 구현됨 (1242c65) — 8개 slug 매핑, 매핑 외 slug는 폴백 |
| 5 | 글 간 주제어 혼입 의심 | FAQ 생성이 `_ctx(calc)`만으로 독립 생성 + AI 파라메트릭 지식 의존 | **의심** (부분 방어됨) | `_VALID_CALCULATORS` SSOT 목록 + A-3 게이트 존재 — 잔여 위험은 FAQ |
| 6 | 법률 결론 문장 오류 (01번 징계해고 퇴직금, 07번 160만원 vs 150만원 서술) | 금지 표현 목록 커버리지 부족(severance-pay에 "징계해고" 패턴 부재) + example_context가 SSOT 정책("금액 미언급")과 독립적으로 하드코딩 | **원인 확정** | G-LEGAL-CURRENT/G8 존재 — 목록·데이터 보강 필요 |

**심각도**: 1·2·3·6 = Critical / 4 = Major / 5 = Minor

---

## 1. 원인분석 상세 (코드 근거)

### 1-1. 계산기 링크 0개 / CTA 0개 — **원인 확정**

**코드 근거**:
- `content/calculator/prompt.py` `_NO_LINK_RULE`(L70-77): "본문에 다른 계산기를 언급하거나 `<a href>` 링크를 생성하지 않는다. CTA 섹션은 작성하지 않는다. 시스템이 본문 뒤에 자동 삽입한다."
- `scripts/phase5_c_sample_gen.py` `run_gates()`: **"G5/G6은 phase5-c 로컬 생성 단계에서 제외 (pipeline 조립 후 검사)"** — 생성 단계에서 CTA/내부링크 부재가 검증되지 않음.
- 게시 시점(2026-08-16 19:30)의 `_phase5c_wp_publish.py` 구버전에는 CTA/카테고리 삽입 로직 없음. CTA/링크 자동삽입(`modules/cta_builder.py`)은 phase5e 커밋 `f771d2b`(22:45)에서 신설, `1242c65`에서 게시 스크립트에 연결.

**결론**: 프롬프트가 "시스템이 삽입"을 약속했지만, 그 시점에 시스템 삽입 코드가 존재하지 않아 10개 전부 링크/CTA 0개가 됨. 생성 단계 G5/G6 제외가 이를 사전 차단하지 못함.

**현재 상태**: `modules/cta_builder.py`(`inject_cta_and_links`, `validate_calc_url_structure`) + `_phase5c_wp_publish.py`/`_phase5e_wp_update.py`에서 CTA/내부링크/카테고리 삽입 구현됨. `_phase5e_wp_update.py`(STEP 3)가 기존 WP 게시물 10개를 PUT 갱신함. 다만 `validate_calc_url_structure`는 slug 기반 구조 검증(HTTP 404 확인 없음).

### 1-2. 본문 ↔ FAQ 숫자 충돌 — **원인 확정**

**코드 근거**:
- `scripts/phase5_c_sample_gen.py` `generate_faq_with_intent()`: `PM.get_faq_prompt(calc, n_min=5, n_max=7)` — **example_context, legal_basis, LAW_SSOT 전달 안 함**. FAQ는 AI 파라메트릭 지식으로 수치 생성(3.52%, 12.95% 등 구율).
- 본문은 `generate_article_body()`에서 example_context(narrative 강제 주입) + `_legal_basis_block()` + `law_ssot_block`을 받음.
- FAQ가 먼저 생성되고 본문이 나중에 생성되는 구조 → 본문의 검증 데이터가 FAQ에 반영될 경로 없음.
- `modules/content_integrity.py` `check_g_consistency()`: FAQ 섹션의 rate(0.5%~30% 범위 퍼센트)가 본문에 없는 경우만 검출 — **금액·기간은 미검사**, SSOT 대조 없음, phase5_c_sample_gen.run_gates에 연결 안 됨.

**결론**: FAQ와 본문이 서로 다른 데이터 소스로 독립 생성되고, FAQ 생성 단계에 검증 수치를 주입하는 경로가 없음. G-CONSISTENCY도 rate에 한정되고 생성 게이트에 미연결.

### 1-3. 2026년 콘텐츠에 과거 금액 혼입 — **원인 확정**

**코드 근거**:
- `scripts/phase5_c_sample_gen.py` `build_example_context()`: 4대보험 `4.5% / 3.545% / 12.96% / 0.9%`(L191 근처) **하드코딩** — `docs/legal_basis.master.yaml` `insurance_rates.reference_year: 2025`와 동일한 2025 수치. 육아휴직 `160만원`, 실업급여 상한 미반영.
- `docs/legal_basis.master.yaml` `four-insurances.content_ssot`: `effective_year: 2026`이지만 `value: "3.545%"`, `장기요양 12.96%` — **데이터가 2025 값 그대로인 채 연도만 2026으로 표기**.
- DeepSeek QA 교차검증: 2026년 실값은 국민연금 9.5%(근로자 4.75%), 건강보험 7.19%(근로자 3.595%), 장기요양 13.14%, 실업급여 상한 68,100원/일·하한 66,048원/일.

**결론**: ① example_context 스크립트 하드코딩(2025) ② SSOT 데이터 자체가 2025 값(갱신 안 됨) ③ G-LEGAL-CURRENT는 SSOT 신뢰를 전제하므로 SSOT가 틀리면 게이트도 통과시킴. **데이터 갱신 + 연도 불일치 감지**가 선행 필요.

### 1-4. 카테고리 전부 미분류 — **원인 확정**

**코드 근거**:
- `config/calculator_categories.yaml`: 8개 slug 카테고리/태그 매핑 존재(주휴/실업/육아/4대보험/퇴직금/연차/연말정산).
- 게시 시점 `_phase5c_wp_publish.py` 구버전 `publish_one()`의 `payload`에 `categories`/`tags` 키 없음 → WP REST가 미지정으로 처리(미분류).
- phase5e `1242c65`에서 `_resolve_wp_category_ids()`(GET→없으면 POST 생성) + `_resolve_wp_tag_ids()` 추가.

**결론**: 매핑 데이터는 있었으나 게시 경로가 사용하지 않음. 현재는 해결 수단 존재. 잔여: 매핑 외 slug(`freelancer-tax-3p3` 등)는 빈 카테고리 폴백 — 신규 계산기 추가 시 누락 위험.

### 1-5. 글 간 주제어 혼입 — **의심** (부분 방어됨)

**코드 근거**:
- `content/calculator/prompt.py` `_VALID_CALCULATORS` SSOT 목록 주입 + `_NO_LINK_RULE`: 존재하지 않는 계산기 언급/링크 원천 차단. `modules/publish_quality.py` A-3 게이트(`_count_hallucinated_calc_links`)도 SSOT 외 slug 차단.
- `_resolve_context_block()`: registry `resolve(slug)` 기반으로 계산기별 데이터 주입 — 교차 오염 없음(계산기 단위 격리).
- 잔여 위험: **FAQ 생성 시** intent hint만 있고 검증 컨텍스트가 없어 AI 파라메트릭 지식으로 타 주제어 혼입 가능성. 실제 QA에서 뚜렷한 혼입 사례는 미확인(주휴수당 글 "각주" 오타 등은 문체/오타 문제).

**결론**: 구조적 격리는 대체로 존재. FAQ 생성 컨텍스트 강화로 잔여 위험 제거 가능. 추가 조사 불필요(설계에 반영).

### 1-6. 법률 결론 문장 오류 — **원인 확정**

**코드 근거**:
- `docs/legal_basis.master.yaml` `severance-pay.forbidden_phrases`: "자발적 퇴사... 받을 수 없" 계열만 있고 **"징계해고" 패턴 없음** → QA 발견 "징계해고인 경우 퇴직금을 받을 수 없습니다"가 G8/G-LEGAL을 통과. (실제 법: 근로자퇴직급여보장법상 징계해고와 무관하게 1년 이상 근속 시 지급 의무)
- `scripts/phase5_c_sample_gen.py` 육아휴직 `example_context`: `200만원 × 0.8 = 160만원` 하드코딩 — `content_ssot` 정책("금액 미언급 — 고용노동부 최신 안내 참고", "상한 150만원 등 금지")과 **모순**. QA가 지적한 "160만원인데 150만원 미만 서술"은 example_context 주입값과 SSOT 금지값이 충돌한 결과.

**결론**: ① 금지 표현 목록 커버리지 부족(징계해고) ② example_context가 SSOT 정책과 독립적으로 하드코딩되어 SSOT 금지 수치를 직접 주입. **forbidden 목록 보강 + example_context를 SSOT 기반으로 생성** 필요.

---

## 2. 수정설계안

각 항목 형식: **문제 원인 → 설계 방향 → 구현 시 영향 범위 → 기존시스템 존재여부**

---

### A. 2026년 법정수치 SSOT (Single Source of Truth)

**문제 원인**: 법정수치가 ① `scripts/phase5_c_sample_gen.py` example_context 하드코딩 ② `legal_basis.master.yaml` insurance_rates(2025) ③ AI 파라메트릭 지식의 3중 구조로 분산. `content_ssot`는 2개 slug만 존재하고 데이터가 2025 값 + effective_year 2026으로 불일치.

**설계 방향**:
1. **SSOT 데이터 갱신(선행)**: `docs/legal_basis.master.yaml` content_ssot의 값·연도를 2026 실값으로 갱신(4대보험 요율, 장기요양, 실업급여 상/하한, 육아휴직 상/하한 등). 값은 law.go.kr/고용노동부 공식 자료로 검증 후 입력(임의 추정 금지).
2. **example_context를 SSOT 기반으로 전환**: `build_example_context()`의 하드코딩 수치를 제거하고, `modules/law_ssot.py`의 `get_slug_ssot()`/`get_ssot_prompt_block()`에서 값을 읽어 계산 예시를 구성. SSOT에 값이 없으면 해당 수치를 예시에 넣지 않음(육아휴직은 "금액 미언급" 정책 유지).
3. **FAQ에도 SSOT 주입**: `get_faq_prompt(calc, n_min, n_max, law_ssot_block)` 파라미터가 이미 존재하나, `generate_faq_with_intent()`가 전달하지 않음 → `law_ssot_block=get_ssot_prompt_block(slug)` 전달로 수정.
4. **연도 불일치 감지**: SSOT에 `effective_year`가 있고 현재 연도와 다르면 생성 전 경고/차단. `content_ssot.effective_year`가 `datetime.now().year`와 다를 때 Gate로 잡는 규칙 추가.

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `docs/legal_basis.master.yaml` | content_ssot 값·연도 갱신 (데이터 작업, 2개 slug → 필요 slug로 확장) |
| `scripts/phase5_c_sample_gen.py` | `build_example_context()` SSOT 연동, `generate_faq_with_intent()`에 `law_ssot_block` 전달 |
| `modules/law_ssot.py` | (필요 시) 연도 불일치 판정 헬퍼 추가 |
| `modules/content_integrity.py` | 연도 불일치 Gate 등록(선택) |

**기존시스템 존재여부**: **부분 존재** — `modules/law_ssot.py` + `get_ssot_prompt_block()`/`get_forbidden_in_content()` 구현됨(4e58a74). 부족: 데이터 갱신·slug 확장·FAQ 주입·example_context 연동.

---

### B. G-CONTENT (일관성 Gate: 제목↔intent↔본문↔FAQ↔example↔calculator)

**문제 원인**: 제목(SEO)은 `generate_seo()`에서, FAQ는 별도 호출, 본문은 intent 템플릿으로 각각 독립 생성 → 상호 일치 검증이 부분적(G-NEW1은 첫 H2만, G-H2는 필수 H2 존재만).

**설계 방향**:
- 제목 ↔ intent: `seo_title`에 intent 키워드(조건/방법/서류) 반영 여부 검사(WARN).
- intent ↔ 본문: `INTENT_H2_MAP`(phase5_c) / `_INTENT_REQUIRED_H2`(content_integrity) 필수 H2 전부 존재 검사(현재는 FAQ/첫 H2만).
- 본문 ↔ FAQ ↔ example: 아래 E(G-CONSISTENCY)와 통합.
- 본문 ↔ calculator: G-CALC(검증 예시 result 값이 본문에 등장) 이미 존재 — documents intent 면제 유지.

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `modules/content_integrity.py` | `check_g_h2_structure()` 강화(필수 H2 전부 + 금지 H2 패턴 확장), 제목-intent 검사 추가 |
| `scripts/phase5_c_sample_gen.py` | `run_gates()`에 `run_integrity_gates()` 연결(현재 미연결) |

**기존시스템 존재여부**: **부분 존재** — G-CALC/G-NUMCON/G-H2/G-STYLE+ 등 content_integrity에 구현됨(5aee3b1) but **생성 게이트에 미연결**이 핵심 결함.

---

### C. G-LEGAL-CURRENT (법령 최신성 Gate)

**문제 원인**: 초기 `_LEGAL_FORBIDDEN`은 특정 키워드만 차단, outdated 수치 탐지 메커니즘 부재. 이후 `check_g_legal_current()`가 `content_ssot.forbidden_in_content` 기반으로 구현됐으나, **SSOT 데이터 자체가 2025 값**이면 현행 판정이 틀림. 또한 "금지값"만 차단하고 "현행값"이 본문에 있는지는 긍정 검증하지 않음.

**설계 방향**:
1. SSOT 데이터 갱신(A) 선행.
2. `forbidden_in_content` 확장: QA에서 확인된 구 값 전부(3.52%, 12.95%, 12.81%, 12.27%, 7일 이내, 10일 이내, 육아휴직 상한 150만원/120만원 등) — `_phase5e_step2_validate.py`의 `FORBIDDEN_MAP`과 master YAML 동기화.
3. (선택) 현행값 긍정 검증: slug에 `required_in_content` 필드 추가 시 본문에 현행 수치 존재 여부를 검사.
4. 육아휴직 등 "금액 미언급" 정책 slug는 example_context가 금지 수치를 생성하지 않도록 A-2와 결합.

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `docs/legal_basis.master.yaml` | forbidden 목록 보강 + 데이터 갱신 |
| `modules/content_integrity.py` | (선택) 현행값 긍정 검사 |
| `scripts/_phase5e_step2_validate.py` | FORBIDDEN_MAP을 master YAML 단일 소스로 대체(중복 제거) |

**기존시스템 존재여부**: **이미 존재** — `check_g_legal_current()`(content_integrity) + `get_forbidden_in_content()`(law_ssot). 부족: 데이터 갱신, 금지 목록 보강, 긍정 검사.

---

### D. G-LINK (링크/CTA Gate)

**문제 원인**: 프롬프트가 AI 링크/CTA 금지 + 시스템 자동삽입을 약속했으나 게시 시점에 삽입 코드가 없었음. 현재는 `cta_builder.py`가 삽입하지만, **ContentRequest에 `calculator_url` 필드가 없어** 생성 단계에서 URL을 주입/검증할 수 없고, URL은 publish 시 `site_url + slug`로 합성됨.

**설계 방향**:
1. ContentRequest JSON에 `calculator_url` 필드 추가 — 생성 시점에 결정적(deterministic)으로 주입(`SITE_URL + "/" + slug + "/"`). AI가 생성하지 않음.
2. 게시 후처리(현재 `inject_cta_and_links`) 유지 — CTA 중복 방지 마커(`<h2>계산기 사용하기</h2>`) 및 내부링크(`internal-links`) 존재 검증은 publish_quality G5/G6(이미 존재) 사용.
3. **404 검증**: `validate_calc_url_structure()`는 slug 기반 구조 검증만 → publish 전 WP REST나 HTTP HEAD로 대상 계산기 페이지 200 확인(선택, 비용 허용 시).
4. 생성 게이트에서 G5/G6 제외 로직(`run_gates`의 "G5/G6 제외")을 **제거**하고, "생성 단계: CTA 미포함 검증 → 게시 단계: CTA 삽입 후 G6 통과"로 2단계를 명시화.

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `scripts/phase5_c_sample_gen.py` | ContentRequest에 `calculator_url` 추가, run_gates G5/G6 제외 로직 재설계 |
| `modules/cta_builder.py` | (선택) HTTP 404 검증 추가 |
| `modules/publish_quality.py` | G5/G6는 이미 존재 — 재사용 |

**기존시스템 존재여부**: **부분 존재** — `cta_builder.inject_cta_and_links`(f771d2b), G5/G6(publish_quality), `validate_calc_url_structure` 구현됨. 부족: ContentRequest URL 필드, 404 실검증, 생성 게이트 연결.

---

### E. G-CONSISTENCY (숫자 일관성 Gate)

**문제 원인**: FAQ와 본문이 독립 생성 + `check_g_consistency()`가 rate(0.5%~30%)만 비교하고 금액·기간·SSOT 대조 없음 + phase5_c 생성 게이트에 미연결.

**설계 방향**:
1. **FAQ 생성 시 SSOT/example_context 주입**(A-3) — 근본 해결.
2. `check_g_consistency()` 확장: rate 외에 금액(원/만원/억원), 기간(N일/N개월) 패턴을 FAQ↔본문 비교.
3. FAQ ↔ SSOT 대조: FAQ에 SSOT 금지값이 있으면 Critical(이미 G-LEGAL-CURRENT가 본문 기준 — FAQ까지 확장).
4. `run_gates()`(phase5_c)에 `run_integrity_gates()` 연결 — 현재 별도 스크립트(`_phase5e_step2_validate.py`, `_phase5e_golden_standard.py`)에서만 실행.

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `modules/content_integrity.py` | `check_g_consistency()` 확장(금액·기간·SSOT) |
| `scripts/phase5_c_sample_gen.py` | run_gates에 integrity gates 연결, FAQ 생성에 SSOT 전달 |

**기존시스템 존재여부**: **부분 존재** — `check_g_consistency()` 구현됨(5aee3b1). 부족: 검사 범위, 생성 게이트 연결, FAQ SSOT.

---

### F. G-STYLE (문체 Gate, 기존 검사 보강)

**문제 원인**: G7(publish_quality `DEFAULT_AI_STYLE_BLOCKLIST`) + G-STYLE+(content_integrity `_AI_STYLE_EXTRA`) 존재. QA가 지적한 "각주"(주휴수당, "각 주" 오타), "인터넷 연결 문제로...", 면피성 문장, 의미 없는 일반론은 **패턴 목록에 없어** 통과.

**설계 방향**:
1. 블록리스트 보강: QA에서 확인된 오타·패턴("각주에 맞는", "인터넷 연결 문제로", "~할 수 있을 수도 있습니다"류) 추가.
2. AI 문체는 패턴 기반 한계가 있으므로 S4(문체 자연스러움 AI Score)와 병행 — publish_quality의 Score 단계가 이미 존재(score >= 90 PASS).
3. **빈 문장·일반론 검사**: "~중요합니다", "~필요합니다", "~권장됩니다" 반복 빈도 임계 초과 시 minor fail(WARN).

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `modules/publish_quality.py` | `DEFAULT_AI_STYLE_BLOCKLIST` 보강, 일반론 빈도 검사 |
| `modules/content_integrity.py` | `_AI_STYLE_EXTRA` 보강 |
| `config/config.yaml` | `AI_STYLE_BLOCKLIST` 오버라이드 값 동기화(있는 경우) |

**기존시스템 존재여부**: **이미 존재** — G7/G-STYLE+/S4 Score. 부족: 목록·패턴 보강.

---

### G. G-IMAGE-SEMANTIC (이미지 의미 Gate)

**문제 원인**: `CALC_VISUAL_THEME`/`INTENT_IMAGE_PREFIX`로 프롬프트를 생성하지만, 결과 이미지가 주제와 일치하는지 검증하는 자동 단계가 없음(사람 육안 검수 의존). QA는 이미지 20장을 육안 확인해 의미·기술 모두 PASS로 판정했으나, 이는 사람 검수지 자동 Gate 아님.

**설계 방향** (현 단계):
1. **프롬프트 기록 + 수동 검수 체계** 유지: `requests/*.json`에 이미지 프롬프트 원문 + 생성 결과 파일명 기록(현재 `images.*.prompt` 필드 있음 — 활용).
2. **자동 검증은 보류**: Vision API 기반 의미 검증은 Phase 6 이후. 대신 텍스트 아티팩트(문자 포함)는 프롬프트에 "no text, no numbers, no letters"가 이미 포함 — 유지.
3. **alt 자동 삽입**: 게시물의 `<img alt>`가 `{keyword} {year} — {calc_name}` 등 의미 있는 값인지 게이트(WARN).

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `scripts/phase5_c_sample_gen.py` | 이미지 프롬프트·alt 기록(이미 대부분 존재) |
| `modules/content_integrity.py` | (선택) alt 존재/빈값 검사 |

**기존시스템 존재여부**: **부분 존재** — 프롬프트 생성·기록, alt 생성 존재. Vision 자동 검증은 **신규(보류)**.

---

### H. Category 자동지정

**문제 원인**: `config/calculator_categories.yaml` 매핑은 있었으나 게시 스크립트 구버전이 미사용. 현재 `_resolve_wp_category_ids()`로 해결됨.

**설계 방향**:
1. 현재 구현 유지 + **매핑 외 slug 폴백 명시**: `_CAT_MAP`에 없는 slug는 `categories: ["기타"]`(또는 intent 기반)로 fallback — 신규 계산기 자동 누락 방지.
2. 카테고리 매핑을 **intent 기반 2차 규칙**으로 확장: slug 매핑 우선, 없으면 intent(eligibility→[제도/지원], howto→[계산방법], documents→[신청서류], calculator→[계산기])로 자동 지정 — 데이터 입력 없이 신규 계산기 커버.
3. 게시 전 `publish_gate`에서 category_id 존재 검증(WARN).

**구현 시 영향 범위**:
| 파일 | 변경 내용 |
|------|----------|
| `config/calculator_categories.yaml` | (선택) 매핑 보강 |
| `scripts/_phase5c_wp_publish.py` / `_phase5e_wp_update.py` | 매핑 외 폴백 + intent 2차 규칙 |

**기존시스템 존재여부**: **이미 존재** — 매핑 YAML + `_resolve_wp_category_ids()`. 부족: 폴백 규칙.

---

### I. 기존 코드 재사용 vs 신규 구현 분류표 (현재 코드 기준)

| 항목 | 대상 파일 | 현재 상태 | 남은 작업 규모 |
|------|----------|----------|---------------|
| A. LAW_SSOT 데이터·주입 | `legal_basis.master.yaml`, `law_ssot.py`, `phase5_c_sample_gen.py` | **부분 존재** (로더+주입 함수, 2slug) | 데이터 갱신(2026) + slug 확장 + FAQ/example_context 연동 — **중** |
| B. G-CONTENT 일관성 | `content_integrity.py`, `phase5_c_sample_gen.py` | **부분 존재** (G-H2/G-CALC 등) | 생성 게이트 연결 + 제목-intent 검사 — **소~중** |
| C. G-LEGAL-CURRENT | `content_integrity.py`, `legal_basis.master.yaml` | **이미 존재** | 데이터 갱신 + forbidden 목록 보강 + (선택) 긍정 검사 — **소** |
| D. G-LINK/CTA | `cta_builder.py`, `publish_quality.py`, `phase5_c_sample_gen.py` | **부분 존재** (삽입 구현됨) | ContentRequest URL 필드 + 404 검증 + 게이트 제외 로직 정리 — **소~중** |
| E. G-CONSISTENCY | `content_integrity.py`, `phase5_c_sample_gen.py` | **부분 존재** (rate 한정) | 금액·기간 확장 + FAQ SSOT + 게이트 연결 — **소~중** |
| F. G-STYLE | `publish_quality.py`, `content_integrity.py` | **이미 존재** | 목록 보강 + 일반론 빈도 — **소** |
| G. G-IMAGE-SEMANTIC | `phase5_c_sample_gen.py` | **부분 존재** (프롬프트 기록) | alt 게이트(소), Vision 검증은 **보류(신규)** |
| H. Category | `_phase5c_wp_publish.py`, `calculator_categories.yaml` | **이미 존재** | 매핑 외 폴백 + intent 2차 규칙 — **소** |

---

## 3. 콘텐츠별 영향 분석

### 10개 Phase 5-C 콘텐츠

**이미 해결된 것(phase5e)**:
- CTA/내부링크 삽입: `_phase5e_wp_update.py` STEP 3가 10개 WP 게시물 갱신(커밋 c48ad20 "10개 WP 업로드 + 카테고리/CTA/게이트 통과")
- 카테고리/태그: 같은 STEP 3에서 지정
- 04/05/07/10 재생성: `_phase5e_regen_04_05_07_10.py` (31cbca6) — LAW_SSOT 주입 + 신규 Gate 통과

**남은 것(이 설계안 적용 시)**:
- **SSOT 데이터 갱신 후 재검증**: 04/10(4대보험 요율 2026 실값), 03/09(실업급여 상·하한 68,100/66,048원), 07(육아휴직 — example_context "160만원" 제거, "금액 미언급" 정책 준수) 재검수. 데이터가 바뀌면 4개 + 실업급여 2개 재생성 필요 가능.
- **01(퇴직금) 법적 오류**: "징계해고 퇴직금" 문장 — forbidden_phrases 보강 후 01 본문 재검수(현재 WP 본문에 해당 문장 잔존 여부 확인 필요).
- **FAQ SSOT 주입**: 10개 전체 FAQ 재생성(선택 — G-CONSISTENCY 확장 시 잔여 충돌만 재생성).

**예상 영향**: 코드/게이트는 재사용 가능, 콘텐츠 재생성은 SSOT 데이터 확정 후 최소 대상(4~6개)으로 제한.

### 37개 기존 콘텐츠

37개는 구 pipeline(`calculator_pipeline.py` + `prompts/calculator_writer_prompt.txt`)으로 생성된 별개 경로다. 이 설계 적용 시:

- **G-LEGAL-CURRENT/G-CONSISTENCY**: slug별 forbidden 목록으로 **식별만** 가능 — 37개 전수 수정은 이번 설계 범위 외(별도 Phase). 단, `check_publish_quality`에 G5/G6/CTA 관련 Gate가 이미 있어 향후 재발행 시 자동 적용됨.
- **CTA/내부링크/카테고리**: `calculator_pipeline.py` `_assemble()`이 이미 CTA/위젯 삽입 + `inject_internal_links` 사용(G5/G6 게이트 존재) — **37개 생성 경로에는 이미 해결 수단 존재**. 37개 WP 게시물의 현재 상태는 별도 점검 필요(이 문서 범위 외).
- **SSOT(A)**: `_write_article()`에 `_legal_basis_block()`은 주입되나 `content_ssot` 주입은 아직 없음 — 신규 계산기 생성 시 SSOT 주입을 기본으로 적용하면 37개 경로도 자동 혜택.

**예상 영향**: 37개 기존 게시물 수정은 하지 않음. 신규/재생성 경로부터 SSOT·Gate가 기본 적용되도록 설계.

---

## 4. 권장 적용 순서 (승인 후)

1. **P0 — SSOT 데이터 갱신(A)**: content_ssot 2026 실값 입력(4대보험/실업급여/육아휴직) + forbidden 목록 보강(C) + severance-pay "징계해고" 패턴 추가. → 데이터 작업 선행, 이후 모든 Gate가 정확해짐.
2. **P1 — 생성 게이트 연결(B/E)**: `run_gates()`에 `run_integrity_gates()` 연결 + FAQ 생성에 SSOT 주입(A-3) + G-CONSISTENCY 확장.
3. **P2 — 링크/카테고리 정리(D/H)**: ContentRequest `calculator_url` 필드 + 매핑 외 폴백 + (선택) 404 검증.
4. **P3 — 문체/이미지(F/G)**: 블록리스트 보강 + alt 게이트.
5. **재검수**: SSOT 데이터 확정 후 04/10/03/09/07/01 재검수 → 변경 필요한 것만 재생성 → `_phase5e_golden_standard.py`로 최종 판정.

---

## 5. 보호 범위 (이번 단계 확인)

- 코드 수정: **0건** (이 문서 갱신만)
- 콘텐츠(10개/37개) 수정: 없음
- WordPress 게시물 변경: 없음
- Git commit: 없음
- 37개 백업/제거: 미착수 (별도 지시 예정)
- phase5e 기존 커밋(cta_builder, content_integrity, LAW_SSOT, wp 스크립트, 재생성): 보호 — 이 설계는 그 위에 데이터·연결을 보강

---

## 6. 승인 후 진행 기준

이 문서는 **설계안**이며, 다음 단계(37개 백업/제거, 10개 재생성, 신규 5개 생성 등 실제 작업)는 사용자 검토·승인 후에만 착수한다. 이번 지시서 범위에서는 어떤 실행 작업도 수행하지 않았다.
