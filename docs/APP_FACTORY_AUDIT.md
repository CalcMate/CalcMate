# APP_FACTORY_AUDIT.md — App Factory 신규 계산기 생성 기능 점검

**작성일**: 2026-08-08  
**조사 방식**: Read-only 코드 점검 (코드 수정 없음)  
**조사 범위**: `modules/app_factory.py`, `dashboard.py:1959-2056`, `modules/registry_loader.py:131-139`, `docs/registry_auto.yaml`, git log

---

## 1. 자동화 범위표

App Factory가 "💾 저장" 버튼 클릭 시 자동 수행하는 작업과 미수행 작업 목록.

### ✅ 자동 처리 (save_app() 호출 시)

| # | 항목 | 세부 |
|---|------|------|
| A1 | **AI 스펙 생성** | GPT: 입력/출력 스키마 + 수식 설계, 수식 검증 실패 시 1회 재시도 |
| A2 | **AI HTML 생성** | Claude: 인라인 CSS/JS 포함 self-contained 계산기 HTML |
| A3 | **AI SEO/FAQ** | GPT: seo_title, seo_desc, FAQ(Q/A), 블로그 초안, 이미지 프롬프트(Gemini) |
| A4 | **DB 저장** | `calculators` 시트 + `app_templates` 시트 (CalculatorRepository, TemplateRepository) |
| A5 | **registry_auto.yaml 기록** | `add_auto_entry(slug, entry)` — old path(`load_registry()`)로 읽힘 |
| A6 | **calculator_index.json 갱신** | slug ↔ 한글 name 매핑 (개발 편의용, 어떤 로직도 읽지 않음) |
| A7 | **캐시 무효화** | `registry_loader.invalidate()` — 저장 직후 반영 |

**registry_auto.yaml 자동 엔트리 구조** (`_build_registry_entry()` 결과):
```
slug, name, category, emoji, card_label, card_desc, compute_type(자동추론),
date_fields(자동추론), validation_mode(formula/date_based), difficulty(자동추론),
display_order(0), field_labels(자동추론), related_slugs([]),
law/article/authority/writer_note → 전부 null
needs_human_legal: true   ← BLOCK_UNVERIFIED_LEGAL 게이트가 이 플래그를 읽어 HOLD
```

### ❌ 자동 미처리 (수동 보완 필요)

| # | 항목 | 이유 |
|---|------|------|
| B1 | **docs/registry/*.yaml 기록** | save_app()이 v3 경로를 모름 — generate_index()/generate_sitemap() 홈페이지 카드·사이트맵 미반영 |
| B2 | **docs/legal_master/*.yaml 기록** | legal 엔티티는 사람이 법령 원문 교차검증 후 수동 작성 |
| B3 | **정적 사이트 빌드** | _rebuild_site.py는 v3(docs/registry/*.yaml) 경유 → B1 해결 전까지 불가 |
| B4 | **_compute_js() 분기** | app_factory HTML은 self-contained(인라인 JS). _rebuild_site.py 기반 정적 빌드(script.js 분리)와 아키텍처가 다름 |
| B5 | **rms.py IMPACT_MAP 등록** | 법령 변경 감지 연동 없음 — 수동 추가 필요 |
| B6 | **콘텐츠 발행(WordPress)** | legal null → BLOCK_UNVERIFIED_LEGAL → 자동 HOLD. 사람이 legal 승격 후 다음 파이프라인에서 발행 |

---

## 2. freelancer-tax-3p3 방식과의 격차 분석

freelancer-tax-3p3는 App Factory 미사용, 수동 직접 구현 방식이다.

### 두 방식 비교

| 항목 | freelancer-tax-3p3 (수동) | App Factory |
|------|--------------------------|-------------|
| 스키마/수식 설계 | 사람이 직접 설계 | GPT가 자동 설계 |
| HTML/JS | _rebuild_site.py → script.js 분리 정적 파일 3종 | Claude가 인라인 self-contained HTML 1종 |
| v3 Registry 등록 | docs/registry/tax.yaml 직접 수정 | **미등록** (registry_auto.yaml만) |
| legal_master 등록 | docs/legal_master/tax.yaml 직접 작성 | **미등록** |
| old-path Registry | legal_basis.master.yaml 직접 수정 | registry_auto.yaml 자동 기록 |
| DB seed | calculator_seed.py 추가 | calculators + app_templates 시트 직접 저장 |
| _compute_js() 분기 | app_generator.py에 slug-specific 분기 추가 | **없음** (HTML 인라인 JS 자체 해결) |
| IMPACT_MAP | rms.py 수동 추가 | **없음** |
| 홈페이지 카드 반영 | ✅ (v3 경유 generate_index) | ❌ (v3 미등록) |
| 사이트맵 반영 | ✅ (v3 경유 generate_sitemap) | ❌ (v3 미등록) |
| legal 상태 | needs_human_legal: false (검증 완료) | needs_human_legal: true (HOLD) |
| WordPress 발행 가능 여부 | ✅ (legal 검증 완료) | ❌ (legal 승격 전까지 HOLD) |

**핵심 격차 요약**:  
- App Factory가 기록하는 `registry_auto.yaml`은 `load_registry()`(old path) 소비자인 `app_generator._registry()`가 읽는다.  
  → 콘텐츠 파이프라인(writer→gate→score) 진입 자체는 legal 승격 후 가능.  
- 그러나 `generate_index()`, `generate_sitemap()`은 `load_registry_v3()`(docs/registry/*.yaml)만 읽는다.  
  → **홈페이지 카드 미노출, 사이트맵 미등록** 상태로 발행 가능. SEO 노출 불완전.

---

## 3. 바로 사용 가능 여부 판정

### 콘텐츠 파이프라인 (writer → gate → score → WordPress)

**조건부 사용 가능** — 다음 수동 작업 완료 후:

1. legal 검증 완료 (`docs/legal_basis.master.yaml` 또는 `legal_basis.draft.yaml` 승격)  
   → needs_human_legal = False → BLOCK_UNVERIFIED_LEGAL 게이트 해제  
2. 다음 파이프라인 실행 → 정상 글 발행 가능

### 홈페이지 카드 / 사이트맵 반영

**사용 불가** — docs/registry/*.yaml(v3)에 미등록 상태에서는 generate_index(), generate_sitemap() 이 계산기를 알 수 없음.  
카드 노출 및 사이트맵 반영을 원한다면 아래 §4의 보강 필요.

### 정적 사이트 빌드 (_site/ 폴더)

**사용 불가** — B1 미해결 시 _rebuild_site.py가 이 계산기를 인식하지 못함.  
단, App Factory HTML 자체(인라인 self-contained)는 WordPress HTML 삽입에는 그대로 사용 가능.

---

## 4. 보강이 필요하다면 최소 범위

현재 App Factory를 그대로 사용해 계산기를 추가하고 **홈페이지 카드 + 사이트맵 반영**까지 자동화하려면 최소 2가지 보강이 필요하다.

### 보강 Option A — save_app()에 v3 동기화 추가 (권장)

**변경 파일**: `modules/app_factory.py:save_app()` 내부

```
현재: add_auto_entry(slug, entry) → registry_auto.yaml(old path) 기록
추가: _append_registry_v3(slug, entry_v3) → docs/registry/<category>.yaml 기록
     (category → tax/labor/employment/insurance 매핑 필요)
```

**효과**: save_app() 한 번으로 old path + v3 양쪽에 기록 → legal 승격 후 홈페이지 카드/사이트맵 즉시 반영 가능.  
**주의**: legal null 상태의 카드가 홈페이지에 노출될 수 있으므로, v3 기록 시점을 "legal 승격 후"로 늦추는 것이 더 안전 (Option B).

### 보강 Option B — rms.promote()에 v3 동기화 추가 (더 안전)

**변경 파일**: `modules/rms.py:promote()` 내부

```
현재: master.yaml에만 승격
추가: docs/registry/<category>.yaml에도 동시 기록
```

**효과**: legal 검증이 완료된 항목만 v3에 등록 → 미검증 카드 홈페이지 노출 없음.  
**제약**: promote() 이전까지 홈페이지 카드 미노출 (의도적 제한으로 볼 수도 있음).

### 공통 미니멀 체크리스트 (어느 Option이든)

| 보강 항목 | 대상 파일 | 우선순위 |
|-----------|-----------|----------|
| v3 registry 동기화 | app_factory.py 또는 rms.py | 필수 (홈페이지 카드/사이트맵) |
| category → yaml 파일 매핑 | app_factory.py | 필수 (v3 동기화 전제) |
| IMPACT_MAP 자동 등록 | rms.py 또는 app_factory.py | 권장 (법령 변경 감지) |
| _compute_js() 분기 자동화 | 해당 없음 | 불필요 (App Factory는 인라인 HTML 방식) |

---

## 5. 현재 상태 요약

- **registry_auto.yaml**: 헤더 주석만 존재 (실제 사용 이력 없음 — App Factory가 실운영에서 save_app()을 호출한 이력 없음)
- **git log**: `4d72d61(feat: save_app이 registry_auto.yaml 자동 기록)`, `db8bac0(feat: 영문 slug 직접 입력)` 등 App Factory 자체는 2026-07 이전에 구현 완료. 그러나 실제 계산기 생성 이력은 없음.
- **App Factory UI**: 대시보드 `🧮 Calculator → 🏭 App Factory` 탭에서 완전히 접근 가능. 키워드 아이디어 제안 + 수동 입력 + 자동 생성 + 미리보기 + 저장 플로우가 구현되어 있음.
- **핵심 판단**: App Factory는 "AI 초안 생성 + DB 등록"까지는 완성도 높게 동작. 단, v3 Registry 비동기화로 인해 홈페이지 카드/사이트맵 반영이 누락되는 구조적 갭이 있음. 이 갭은 코드 10~20줄 수준의 보강으로 해결 가능.
