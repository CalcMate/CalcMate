# APP_FACTORY_DESIGN.md — App Factory Production 연결 보강 설계

**작성일**: 2026-08-08  
**근거**: APP_FACTORY_AUDIT.md 결과  
**단계**: 설계 only (코드 작성 없음)

---

## 설계 요약

App Factory가 현재 기록하는 두 개의 registry(registry_auto.yaml과 legal_basis.master.yaml)
외에, 프로덕션 SSOT인 `docs/registry/*.yaml`(v3)에도 동기화 기록을 추가하는 것이 이번 보강의
핵심이다. 이 변경 하나로 홈페이지 카드·사이트맵 반영이 활성화되고, Phase3-1 방식(6~7개 파일
수동 수정)을 Tier2 한정으로 대체할 수 있게 된다.

---

## 1. registry_auto.yaml → v3 연결 방안

### 1-1. 두 스키마 차이 정리

| 필드 | registry_auto.yaml | v3 (registry/*.yaml) | 비고 |
|------|--------------------|----------------------|------|
| slug | ✅ | ✅ | 동일 |
| name | ✅ | ✅ | 동일 |
| category | ✅ | ✅ | 동일 |
| emoji | ✅ (고정 🧮) | ✅ | v3는 계산기별 커스텀 |
| card_label | ✅ (= name) | ✅ | v3는 짧은 표시용 |
| compute_type | ✅ (자동추론) | ✅ (수동) | 추론 방식 동일 |
| date_fields | ✅ | ✅ | 동일 |
| validation_mode | ✅ | ✅ | 동일 |
| field_labels | ✅ (app가 labels 출력) | ✅ | 동일 |
| difficulty | ✅ | ✅ | 동일 |
| difficulty_status | ✅ (provisional) | ✅ (provisional) | 동일 |
| display_order | **없음** | ✅ (정렬·카드 위치) | **v3에만 있음 — 추가 필요** |
| card_desc | **없음** | ✅ (카드 서브타이틀) | **v3에만 있음 — 추가 필요** |
| content.evergreen | ✅ (null) | ✅ (true/false) | v3는 콘텐츠 업데이트 정책 |
| content.update_cycle | ✅ (null) | ✅ | 동일 |
| content.content_caveat | **없음** | ✅ (null/"crude_estimate") | v3에만 있음 |
| related_slugs | ✅ (빈 리스트) | ✅ | v3는 사람이 채움 |
| legal_refs | **없음** | ✅ (legal_master 참조 키) | **v3 핵심 필드 — legal 승격 시 추가** |
| writer_context | **없음** | ✅ (emphasize/example_patterns/story) | **v3에만 있음 — 기본값 자동 생성** |
| law/article/authority 등 | ✅ (전부 null) | v3엔 없음(legal_master 분리) | legal은 legal_master에만 |
| needs_human_legal | ✅ | v3엔 없음 | registry_auto.yaml 전용 플래그 |

**공백 필드 요약**: v3에만 있는 필드 중 자동 생성 가능한 것(display_order, card_desc,
writer_context 기본값)과 legal 승격 시 채워야 할 것(legal_refs)을 분리.

### 1-2. 두 방안 비교

**방안 A: save_app() 내에서 v3 직접 쓰기 (즉시 동기화)**

```
save_app() 호출 시:
  1. DB 저장 (기존)
  2. registry_auto.yaml 기록 (기존)
  3. [추가] v3 yaml 기록: _append_registry_v3(slug, v3_entry, category)
     - v3_entry = registry_auto 엔트리 + display_order + card_desc + writer_context 기본값
     - category → yaml 파일 매핑: "세금/정부혜택"→tax.yaml, "노무/급여"→labor.yaml,
       "고용/보험"→employment.yaml, "노무/급여/보험"→insurance.yaml, 기타→labor.yaml(폴백)
```

장점:
- save_app() 한 번 호출로 모든 경로 동기화, 창(window) 없음
- 관리 포인트 1개

단점:
- legal HOLD 상태 계산기가 v3에 등록되어 홈페이지 카드에 노출될 수 있음  
  (generate_index는 v3 ∩ old-path 교집합 slug만 카드로 생성 — legal 미승격 시 old-path에 없으므로 실제로는 미노출. 단, legal 승격 후 자동 노출)
- category-to-file 매핑을 새 카테고리 추가 시 관리해야 함

**방안 B: legal 승격 시 v3 동기화 (rms.promote()에 연결)**

```
rms.promote(slug) 실행 시:
  1. legal_basis.master.yaml 승격 (기존)
  2. [추가] v3 yaml 기록: _append_registry_v3(slug, v3_entry, category)
     - registry_auto.yaml 항목을 읽어 v3 형식으로 변환
     - legal_refs 추가 (승격된 법령 엔티티 ID)
```

장점:
- legal 검증 완료된 계산기만 v3에 등록 → 홈페이지 카드 품질 보장
- 미검증 계산기 홈페이지 노출 위험 없음

단점:
- registry_auto.yaml → v3 변환 시점이 나뉘어 두 파일의 불일치 기간이 길어짐
- rms.promote()는 사람이 수동 실행하는 CLI — 이 코드도 App Factory 경로를 알아야 함

### 1-3. 추천안: 방안 A (즉시 동기화), 단 카드 표시 정책 명시

**근거**:
- generate_index()가 `v3 ∩ old-path` 교집합만 카드로 생성하므로, legal HOLD 상태(old-path
  미등록)에서는 v3에 있어도 카드 미표시. 방안 A의 "노출 위험"은 사실상 legal 승격 이후에만
  발생하며, 이는 의도된 동작이다.
- 방안 B는 save_app() → promote()의 2-step gap에서 registry_auto.yaml과 v3가 장기
  불일치하는 구조를 만든다. 이 패턴이 "App Factory 잔재" 재발의 직접 원인이 된다.
- 방안 A에서 v3 write가 실패하면 예외를 경고로만 처리하고 save_app() 자체는 성공 처리
  (기존 registry_auto.yaml 기록과 동일 패턴). 실패 로그를 대시보드에 표시.

**v3 자동 생성 필드 값 전략**:

```
display_order = max(기존 v3 전체 display_order) + 1  (없으면 10)
card_desc     = app.get("desc") 또는 seo_desc 앞 40자 + "…"
card_label    = name (App Factory는 name이 곧 card_label)
writer_context = {
    emphasize: [],
    example_patterns: [seo_desc에서 추출한 1개],
    calculation_story: []
}
content = {evergreen: true, update_cycle: null, content_caveat: null}
legal_refs = []   # 빈 리스트 — legal 승격 시 사람이 추가
related_slugs = []  # 빈 리스트 — 사람이 채움
```

### 1-4. registry_auto.yaml의 역할 재정의

v3가 최종 SSOT라는 원칙을 코드에 명시:
- **registry_auto.yaml**: 스테이징 레이어. App Factory 생성 직후 상태 보존. 재생성/롤백 기준점.
- **docs/registry/*.yaml(v3)**: 프로덕션 SSOT. generate_index / generate_sitemap / resolve()의 단일 소스.
- **legal_basis.master.yaml**: 콘텐츠 파이프라인(writer→gate) 전용. RMS 워크플로 산출물.

registry_auto.yaml에 기록하고 v3에 미기록하는 상태는 "스테이징 상태"로 정의.
스테이징 상태의 계산기는 홈페이지 카드 미표시, 사이트맵 미등록.

---

## 2. legal_master 반자동 등록 구조

### 2-1. Tier 분류 기준

| Tier | 예시 | legal_master 필요 수준 |
|------|------|-----------------------|
| Tier2 — 순수산술 | 프리랜서 3.3% (고정세율), 대출이자 계산기 | 수식만 명시. 세율 변경 가능성 있으면 법령 조항 1개 |
| Tier2 — 공시율 | 최저임금 적용 계산기 | 법령 + 연도별 공시값 필요 |
| Tier1 — 노동법 | 퇴직금, 연차수당, 실업급여 | calculation_flow 전체 + deduction_rules |
| Tier1 — 세법 | 연말정산, 종합소득세 | 복수 조항 + 공제표 + 면책 문구 |

### 2-2. App Factory가 자동 생성하는 placeholder 구조

legal 검증은 사람이 해야 하지만, App Factory가 GPT를 통해 `docs/legal_master/<category>.yaml`에
placeholder 엔트리를 생성하면 법령 조사 시작점을 제공할 수 있다.

```yaml
# App Factory가 생성하는 placeholder 형태 (save_app 시 자동 추가)
<slug>_auto:                      # entity_id에 _auto 접미사로 구분
  law: null                       # 사람이 채움 (law.go.kr 검증 필수)
  article: null
  authority: null
  confidence: low                 # 자동생성은 항상 low
  needs_human_legal: true
  writer_note: |
    [자동 생성 placeholder — 사람이 법령 원문 검증 후 수정]
    GPT 초안: <app_factory가 생성한 법령 설명 초안>
  calculation_flow:               # GPT 생성 초안 (검증 필요)
    - <step 1>
    - <step 2>
  forbidden_phrases:
    - 참고용임을 명시하지 않은 확정 수치
```

이 placeholder는 `legal_refs`에 등록되지 않음 (`legal_refs: []` 유지). 사람이 법령 조항을
검증하고 엔티티 ID를 확정한 뒤:
1. legal_master yaml에 정식 엔티티(placeholder 없는 버전) 작성
2. v3 registry의 `legal_refs`에 엔티티 ID 추가
3. rms 워크플로로 legal_basis.master.yaml 승격

### 2-3. App Factory 폼 Tier 선택 추가 (결정 필요 항목 #1)

→ §8 참조

---

## 3. 정적 사이트 빌드 자동 연결

### 3-1. 두 배포 경로 이해

현재 CalcMate에는 사실상 두 개의 계산기 배포 경로가 존재한다:

```
경로 A (현재 8개 계산기):
  DB → _rebuild_site.py → _site/<slug>/index.html + script.js + style.css
  → AG.generate_calculator()가 _compute_js()로 계산 로직 생성
  → generate_index()가 v3 기반으로 홈페이지 카드 생성

경로 B (App Factory 생성):
  DB → app_templates.html_template (self-contained HTML)
  → 이 HTML을 WordPress에 직접 삽입
  → _rebuild_site.py를 타지 않음(현재)
```

이 두 경로는 의도적으로 분리할 수도 있고, 통합할 수도 있다.

### 3-2. 방안 비교

**방안 X: 경로 분리 유지 + 사이트 빌드 수동 트리거**

- App Factory는 WordPress 배포 경로(경로 B)를 유지
- 홈페이지 카드·사이트맵을 원한다면 v3 등록 후 대시보드에서 "사이트 재빌드" 버튼을 수동으로 누름
- _rebuild_site.py는 DB에서 slugs를 읽으므로 App Factory 저장 후 실행하면 App Factory 계산기도 정적 빌드됨  
  단, `_compute_js()`에 분기가 없는 경우 script.js의 computeResult가 null 반환 → 기능 불완전

**방안 Y: 경로 통합 + 자동 트리거**

- save_app() 성공 후 자동으로 _rebuild_site.py 실행
- 성공 여부와 건수를 대시보드에 표시
- App Factory HTML은 _compute_js()로 변환하는 "로직 추출" 단계 필요

### 3-3. 추천안: 방안 X (경로 분리 유지), 단 빌드 버튼 추가

**근거**:
- App Factory HTML은 self-contained이므로 WordPress 삽입에는 추가 빌드 없이 동작
- _compute_js() 통합을 자동화하려면 GPT 생성 JS 코드를 파싱해야 하는 복잡도 발생
- 홈페이지 카드 반영은 대시보드 "🔧 사이트 관리 → 전체 재빌드" 버튼이 이미 있음

**추가할 것**: save_app() 성공 직후 대시보드에 안내 메시지 추가:
```
✅ 저장 완료. 홈페이지 카드·사이트맵 반영 원하면 [사이트 관리 → 전체 재빌드]를 실행하세요.
```

**빌드 실패 피드백**: _rebuild_site.py는 stderr/stdout을 반환하므로 에러 로그를 대시보드에
접을 수 있는 expander로 표시. 빌드 실패가 App Factory 저장 자체를 실패 처리하지는 않음.

---

## 4. index 카드 / sitemap 자동 반영 설계

### 4-1. display_order 결정 방식

**추천: 자동 증가 (Auto-increment)**

```python
def _next_display_order() -> int:
    v3 = load_registry_v3()
    orders = [e.get("display_order", 0) for e in v3.values() if isinstance(e.get("display_order"), int)]
    return max(orders, default=0) + 1
```

이유:
- 사용자가 display_order를 모르는 상태에서 App Factory 폼에 숫자를 입력하게 하면 실수 발생
- 자동 증가하면 새 계산기는 항상 홈페이지 카드 맨 끝에 추가됨 (자연스러운 동작)
- 순서 조정이 필요한 경우에는 v3 yaml을 직접 편집 (드문 케이스, 수동 작업이 맞음)

### 4-2. generate_sitemap() 재사용 가능 여부

`generate_sitemap()`은 `load_registry_v3()`에서 display_order 기준 정렬 후 slug별 URL을 생성.
App Factory 계산기가 v3에 등록되면 **추가 코드 없이 자동으로 sitemap.xml에 포함**.

조건: 1-3의 방안 A 실행(v3에 즉시 기록) + 빌드 트리거(수동 또는 자동).

### 4-3. generate_index() 카드 표시 조건

현재 코드:
```python
_slugs = [s for s, _ in sorted(
    [(s, e.get("display_order", 999)) for s, e in _v3.items() if reg.get(s)],
    ...
)]
```

`reg.get(s)` = `load_registry()`(old path = legal_basis.master.yaml + registry_auto.yaml).  
App Factory 생성 계산기는 registry_auto.yaml에 있으므로 `reg.get(s)` 통과.  
→ **v3에 등록하면 legal HOLD 상태에서도 홈페이지 카드 표시됨**.

이것이 의도된 동작인지 결정 필요 (→ §8 결정 필요 #2).

---

## 5. DB-Registry 정합성 보장 메커니즘

### 5-1. 현재 save_app()의 중복 방지

```python
# 이름 중복 체크
if any(c.get("name") == name for c in _all): return False, "중복"
# slug 중복 체크
if any(c.get("slug") == new_slug for c in _all): return False, "중복"
```

이 체크는 DB에만 적용. v3 slug 중복은 미체크.

### 5-2. 추가할 정합성 검증

**생성 시점 검증** (save_app() 내부에 추가):

```python
# v3 slug 중복 체크 (기존 8개 계산기 덮어쓰기 방지)
v3 = load_registry_v3()
if new_slug in v3:
    return False, f"v3 Registry에 이미 존재하는 slug: '{new_slug}'"
```

**별도 정합성 체크 스크립트**: 선택적. DB slugs와 v3 slugs를 비교해 불일치 리스트 출력.
긴급 점검용으로 `scripts/_check_registry_db_sync.py`를 준비하되 자동 실행은 하지 않음.

### 5-3. "Registry 유일 소스" 원칙 충족 여부

Phase D에서 확립된 원칙: "_compute_js() 분기와 관련 카드는 registry가 유일 소스, 하드코딩 없음."

App Factory 경유 계산기도 이 원칙을 만족:
- compute_type/date_fields/validation_mode → registry_auto.yaml에서 자동 추론해 기록
- v3에 동기화 후 generate_index(), generate_sitemap(), resolve()가 registry만 읽음
- _compute_js()에 분기 추가 없이 self-contained HTML 사용 → app_generator._compute_js()는 App Factory 계산기를 모름 (경로 B)

단, **경로 A(정적 사이트)**로 App Factory 계산기를 빌드하면 script.js에 `return null`이 나온다.
경로 A 완전 지원이 필요하면 §6에서 별도 설계 필요.

---

## 6. Tier2 계산 로직 자동 생성 가능 범위 및 한계

### 6-1. 현재 App Factory HTML로 가능한 것

App Factory의 Claude 단계는 self-contained HTML을 생성한다. 이 HTML에는:
- `<input>` → 값 읽기
- JS 계산 함수 (formula를 JS로 변환)
- `<output>` → 결과 표시
- CSS 스타일 (인라인)

**WordPress 삽입 목적**: ✅ 완전 동작. 페이지에 iframe 없이 직접 삽입 가능.  
**CalcMate 정적 사이트(_site/) 목적**: ❌ script.js 분리 구조와 맞지 않음.

### 6-2. Tier별 자동화 가능 범위

| Tier | 수식 복잡도 | App Factory HTML | script.js 자동 변환 | 사람 개입 |
|------|------------|-----------------|---------------------|-----------|
| Tier2-Simple | 단일 수식, 단일 출력 | ✅ 완전 | 가능 (수식 문자열 → JS 함수 파싱) | 로직 검토만 |
| Tier2-Multi | 단일 수식, 복수 출력 | ✅ 가능 | 가능 (freelancer-tax-3p3 패턴) | 로직 검토만 |
| Tier2-Rate | 공시율 적용 (최저임금 등) | ⚠️ 연도별 값 하드코딩 위험 | 어려움 (연도값 주입 로직 필요) | 연도값 검증 필수 |
| Tier1-Date | 날짜 기반 (퇴직금, 연차) | ⚠️ JS 복잡도 높음 | 어려움 | 로직 전체 사람 검토 |
| Tier1-Complex | 복수 공제 구간 (연말정산) | ❌ GPT 오류 가능성 높음 | 불가 | 전체 사람 개발 |

### 6-3. script.js 자동 변환 방안 (Tier2-Simple/Multi 한정)

GPT가 생성한 formula 문자열 (`"gross_income * 0.033"` 같은 형태)을 이용해
_compute_js() 분기를 자동 생성하는 것은 Tier2 단순 수식에 한해 **기술적으로 가능**.

```python
def _build_compute_js_snippet(slug: str, input_schema: dict,
                               output_schema: dict, formula: str) -> str:
    """Tier2 단일/복수 출력 수식을 _compute_js() 분기 코드로 변환."""
    # formula = "gross_income * 0.033"
    # → JS: var result = Math.round(gross_income * 0.033); out["result"] = result;
```

**주의**: GPT가 생성한 formula가 단순 수식이 아닌 경우(복수 라인, 조건문 포함) 변환 실패 가능.
변환 실패 시 "App Factory 계산기는 WordPress 전용(경로 B만 지원)"으로 처리하면 됨.

### 6-4. 추천 접근법

**이번 보강 범위에서는 script.js 자동 변환을 제외**. 이유:
- App Factory 계산기의 1차 배포 목적이 WordPress이므로 self-contained HTML로 충분
- script.js 변환은 formula 파싱 → 오류 가능성 → 추가 QA 필요
- 향후 "CalcMate 정적 사이트에도 App Factory 계산기 표시" 요구 발생 시 별도 구현

**_compute_js() 분기 추가 방식(Phase3-1)은 Tier1 복잡 계산기 전용으로 유지**.

---

## 7. 위험도 분석

### 위험 1: 기존 8개 계산기 데이터 덮어쓰기

**발생 경로**:  
App Factory의 v3 write가 기존 8개 계산기와 동일한 slug로 실행될 경우
(`_append_registry_v3(slug, entry)` 내부에서 yaml.safe_dump로 덮어쓰기).

**발생 확률**: 낮음. save_app()의 slug 중복 체크(DB 기준)가 1차 방어.
단, DB에는 없지만 v3에는 있는 경우(v3 수동 추가 후 DB 미등록) 미방어.

**방지 방법**:
- v3 yaml 기록 함수 내부에서 `if slug in load_registry_v3(): raise ValueError` 추가
- save_app()에서 v3 slug 중복도 사전 체크 (§5-2)
- v3 write는 기존 slug를 건드리지 않고 새 slug를 append하는 방식으로 구현

**발동 시 피해**: v3 yaml 파일 손상 → git으로 즉시 복구 가능. 정적 빌드 전에는 _site/에 영향 없음.  
**심각도**: 중간 (복구 가능, 서비스 영향 전 git 복구 가능)

---

### 위험 2: registry_auto.yaml과 v3 일시적 불일치

**발생 경로**:  
방안 A(즉시 동기화)에서도 두 파일 write 사이에 예외가 발생하면 불일치 발생:
- DB 저장 성공 + registry_auto.yaml 기록 성공 + v3 write 실패 → 스테이징만 존재

**발생 확률**: 낮음 (파일 쓰기 실패는 디스크 오류 수준). 네트워크 없고 로컬 파일.

**방지 방법**:
- v3 write 실패는 경고 처리 (save_app() 실패 아님 — 기존 registry_auto.yaml 패턴과 동일)
- 대시보드에 "v3 동기화 실패 — 사이트 관리 탭에서 수동 동기화 필요" 경고 표시
- 대시보드에 "v3 미동기화 계산기" 조회 기능 추가 (registry_auto.yaml slugs - v3 slugs)

**발동 시 피해**: 홈페이지 카드·사이트맵 미반영 (콘텐츠 발행에는 영향 없음).  
**심각도**: 낮음 (홈페이지 카드 누락, 서비스 중단 없음, 수동 복구 가능)

---

### 위험 3: App Factory HTML vs 정적 사이트 아키텍처 불일치

**발생 경로**:  
_rebuild_site.py가 App Factory로 생성된 계산기도 DB에서 읽어 처리 시도.
이 경우 `AG.generate_calculator(c, cfg)` → `_compute_js(c)` → App Factory 계산기에 분기 없음
→ script.js에 `return null;` 생성 → 정적 사이트 계산 기능 불완전.

**발생 확률**: 높음. 대시보드에서 "전체 재빌드" 누르면 반드시 발생.

**방지 방법**:
- 두 경로를 명시적으로 분리: v3 entry에 `deployment_mode: "wordpress_only"` 플래그 추가
- _rebuild_site.py와 AG.generate_calculator()는 이 플래그가 있으면 해당 slug를 스킵
- 또는: _compute_js()에 "App Factory 계산기 → self-contained HTML 임베드" fallback 추가

**발동 시 피해**: App Factory 계산기의 정적 사이트 버전이 계산 불가. WordPress 버전은 정상.  
**심각도**: 중간 (WordPress는 정상, CalcMate 정적 사이트만 영향)

---

## 8. "결정 필요" 항목

다음 항목들은 근거 데이터 없이 추측으로 채울 수 없다. 구현 전 판단 필요.

### 결정 #1: App Factory 폼에 Tier 선택 UI 추가 여부

**선택지**:
- A. 추가한다 — "Tier2 (단순수식) / Tier1 (법령 필요)" 라디오 버튼. Tier1 선택 시 legal_master 조사 체크리스트 표시.
- B. 추가하지 않는다 — 모든 계산기를 App Factory로 동일하게 처리. Tier는 나중에 수동으로 v3 yaml에 표시.

**영향**: Tier UI 없으면 사용자가 Tier1 복잡 계산기를 App Factory로 무조건 시도할 수 있음.

---

### 결정 #2: App Factory 생성 계산기의 홈페이지 카드 표시 정책

generate_index()는 현재 `v3 ∩ old-path` 교집합을 카드로 표시.
App Factory 계산기는 registry_auto.yaml(old-path 소속)에 있으므로, v3에 등록하면 legal HOLD 상태에서도 카드 표시됨.

**선택지**:
- A. 허용한다 — HOLD 상태 카드도 홈페이지에 표시. 카드에 "준비중" 배지 추가.
- B. 허용하지 않는다 — generate_index() 조건에 `needs_human_legal=False` 체크 추가. legal 승격 후에만 표시.
- C. 현재 그대로 — legal HOLD 상태는 old-path에 있어도 사이트 빌드 전까지 카드 미표시 (빌드를 수동으로만 트리거하면 사실상 B와 동일).

---

### 결정 #3: legal_master placeholder 자동 생성 여부

**선택지**:
- A. 생성한다 — GPT가 법령 초안을 생성해 `docs/legal_master/<category>.yaml`에 _auto 접미사 엔트리로 추가. 사람이 검증해 정식 엔트리로 수정.
- B. 생성하지 않는다 — legal_master는 완전 수동. App Factory는 legal_refs=[] 상태로만 저장. 사람이 법령 조사 완료 후 별도 추가.

**영향**: A는 GPT 환각으로 잘못된 법령 초안이 파일에 들어갈 위험. B는 법령 조사 시작점이 없어 사람 부담 증가.

---

### 결정 #4: App Factory 계산기의 배포 경로

**선택지**:
- A. WordPress 전용 (경로 B) — self-contained HTML만 사용. 정적 사이트 빌드 대상 제외.
- B. 정적 사이트 포함 (경로 A+B) — script.js 자동 변환 구현. 빌드 시 App Factory 계산기도 포함.
- C. 선택적 — v3 yaml에 `deployment_mode` 플래그로 계산기별 결정.

**영향**: B는 §6에서 설명한 script.js 자동 변환 구현이 추가로 필요.
