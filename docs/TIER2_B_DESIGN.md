# CalcMate — Tier2-B(날짜형) App Factory 지원 설계

**작성일**: 2026-08-09
**전제**: 코드 작성/실행/Registry 변경 없음. 설계 문서만.

---

## 0. 현재 상태: 사전 해소 필요 버그

이 설계를 구현하기 전에 해소해야 할 기존 버그가 조사 중 발견되었다.

### 버그: compute_rules + formula dict 계산기의 정적 사이트 다중 출력 누락

**증상**: `jeonse-vs-monthly`(formula dict 3개 출력, `compute_rules` 있음)의 정적 사이트 페이지에서
`computeResult`가 첫 번째 출력(`jeonse_opp_cost`)만 생성하고 나머지 2개 누락.

**원인 위치**: `modules/app_generator.py` — `_compute_js()` 내 `if validation:` 분기

```python
if validation:
    out_key = next(iter(fmap))           # 첫 번째 출력만 처리!
    out_expr = _to_js(next(iter(fmap.values())))
    body = (
        "  var out = {};\n"
        "  out.notices = [];\n"
        + validation
        + f'  out["{out_key}"] = ({out_expr});\n'   # 첫 번째만!
        + f'  out._formula = {formula_str};\n'
    )
```

**영향**: `_site/jeonse-vs-monthly/script.js`의 `computeResult`가 `jeonse_opp_cost`만 계산.
또한 `generate_html()`도 `sm-result-value`를 단일 출력만 표시 — formula dict의 다중 출력 렌더링 미지원.

**Tier2-B 설계와 관계**: Tier2-B는 self-contained HTML 방식을 채택하므로 이 버그를 직접 상속하지 않는다.
그러나 `jeonse-vs-monthly`(Tier2-A)가 정적 사이트에서 3개 출력 모두 정상 작동해야 Tier2-A 표준 경로가
완전히 확립된 것이므로, **Tier2-B 구현 전에 이 버그를 수정해야 한다**.

**수정 범위**: `_compute_js()` validation 분기를 formula dict 전체 출력을 순회하도록 수정.
기존 8개 계산기(단일 출력 + validation)와 호환성 유지 필요. (별도 작업지시서 발행 필요)

---

## 1. Tier2-A vs Tier2-B 구조 차이

### 1-1. 개요

| 항목 | Tier2-A (산술형) | Tier2-B (날짜형) |
|---|---|---|
| 대표 계산기 | jeonse-vs-monthly | 군인 전역일 (예정) |
| 계산 엔진 | formula dict (산술식 문자열) | JS Date 객체 연산 |
| `formula_engine` 지원 | ✅ (validate + execute) | ❌ (Date 연산 미지원) |
| `_compute_js()` 자동생성 | ✅ (dict 경로 — 단, 다중출력 버그 有) | ❌ (date_based 구조 불일치) |
| input_schema 타입 | `number` / `date` | `date` + `enum`(선택형) 혼합 |
| `_form_fields_v2()` 폼 생성 | ✅ (date/number 자동) | ❌ (`<select>` 미지원) |
| 정적 사이트 연계 | ✅ generate_calculator() | ❌ 별도 처리 필요 |
| App Factory HTML inline 저장 | ✅ (저장은 가능, 정적 사이트 연계가 문제) | ✅ (동일) |

### 1-2. 날짜 연산이 formula dict로 표현 불가능한 이유

`formula_engine`은 사칙연산 + `min/max/round/abs/int/float`만 허용:
```python
_FUNCS = {"min": min, "max": max, "round": round, "abs": abs, "int": int, "float": float}
```

날짜 덧셈(`입대일 + 18개월 → 전역일`)은 다음이 필요:
```js
// JS Date 객체 조작 — formula_engine 표현 불가
var d = new Date(enlistment_date);
d.setMonth(d.getMonth() + 18);
d.setDate(d.getDate() - 1);  // 전역일 = +18개월 후 전날
var discharge = d.toISOString().slice(0, 10);
```

Epoch ms 숫자로 우회(`enlistment_ms + 18 * 30.4375 * 86400000`)할 수 있지만:
- 사용자 입력이 timestamp ms여야 하므로 UX 파괴
- 달력월 기준 계산과 오차 발생 (30.4375일/월 가정 시 ~7일 오차)
- 윤년/월말 경계 정확 처리 불가

결론: **날짜 덧셈은 formula dict로 표현 불가 — JS Date 객체 필수**.

### 1-3. `date_based` compute_type 재활용 불가 이유

`app_generator._compute_js()` date_based 분기는 `start_date`/`end_date` 하드코딩:
```python
# app_generator.py:783
'  var s = new Date(inputs["start_date"]); var e = new Date(inputs["end_date"]);\n'
'  var total_days = Math.floor((e - s) / (1000*60*60*24));\n'
```
군인 계산기 구조:
- 입력: `enlistment_date`(입대일) + `branch`(병종 선택)
- `end_date`(전역일)는 **출력**, 입력이 아님
- 병종별 복무기간이 다르므로 단순 두 날짜 차이와 다른 구조

또한 `_form_fields_v2()`는 `<select>` 미지원:
```python
if "date" in str(spec).lower():
    # → <input type="date">
else:
    # → <input type="text" inputmode="numeric">   ← select 없음
```

---

## 2. 날짜 입력 + 조건 선택 Registry v3 스키마 설계

### 2-1. input_schema 확장 — `enum` 타입 도입

현행 input_schema 타입: `"number"` / `"date"` (두 가지만)

Tier2-B를 위한 신규 타입: `"enum:값1,값2,값3"` (콜론 뒤에 선택지 나열)

**예시 (군인 전역일 계산기):**
```json
{
  "enlistment_date": "date",
  "branch": "enum:army,navy,air_force,marine,social_service"
}
```

**`_form_fields_v2()` 수정 예상 범위**:
```python
# 추가될 분기 (현재 date/else 두 가지에 enum 추가)
elif str(spec).startswith("enum:"):
    options = str(spec).split(":", 1)[1].split(",")
    # <select> 태그 생성
```

이 변경은 기존 number/date 분기를 건드리지 않으므로 기존 9개 계산기에 영향 없음.

### 2-2. Registry v3 엔트리 추가 필드

Tier2-B 계산기의 v3 엔트리에 `html_source` 필드를 추가:

```yaml
# docs/registry/defense_af.yaml (예시)
military-discharge:
  name: 군인 전역일 계산기
  slug: military-discharge
  category: 국방/병역
  source: app_factory
  tier: 2
  tier_subtype: B          # ← 신규: A=산술형, B=날짜형 (빌드 경로 분기용)
  html_source: template_db  # ← 신규: DB의 html_template를 정적 페이지로 사용
  compute_type: date_based_custom  # ← 신규: 기존 date_based와 구분
  date_fields: [enlistment_date]
  status: HOLD
  display_order: 10
  ...
```

**`tier_subtype` 필드**: `_rebuild_site.py`의 빌드 분기 조건으로 사용.
**`html_source: template_db`**: 빌드 시 DB `app_templates.html_template` 직접 복사.
**`compute_type: date_based_custom`**: `_compute_js()`에 slug별 분기를 추가하지 않기 위한 명시적 구분.

### 2-3. 기존 v3 스키마 호환성

모든 신규 필드는 optional이며 기존 계산기에 없어도 동작:
- `tier_subtype` 없음 → Tier2-A 경로 (기존 동작 유지)
- `html_source` 없음 → `generate_calculator()` 경로 (기존 동작 유지)
- `compute_type: date_based_custom` 없음 → 기존 compute_type 처리 유지

---

## 3. 계산 로직 관리 방식 — 방안 A vs 방안 B

### 3-1. 방안 A: `date_formula` 전용 필드 도입

**개요**: App Factory에 `date_formula` 필드를 새로 정의하고, 제한된 날짜 연산 문법을 파싱:
```json
{
  "date_formula": {
    "discharge_date": "enlistment_date + branch_months(branch) - 1day",
    "remaining_days": "discharge_date - today()",
    "progress_pct": "(today() - enlistment_date) / total_days * 100"
  }
}
```

**`_compute_js()` 처리**: `date_formula` 파싱 → JS Date 코드 자동생성

**장점**:
- formula dict와 대칭 구조로 AI 생성 가능성 있음
- 메타데이터에 계산 로직 보존 (감사/수정 용이)
- 장기적으로 날짜 계산기 다수 추가 시 확장성

**단점**:
- `formula_engine`, `app_generator._compute_js()`, `_form_fields_v2()` 대규모 수정
- 날짜 문법 파서 신규 구현 (버그 위험, 테스트 부담)
- `branch_months(branch)` 같은 lookup 함수 설계 필요 (enum값 → 개월수 매핑)
- App Factory AI 프롬프트가 이 문법을 정확히 따르도록 유도 어려움
- 구현 공수: 추정 2~3 스프린트

**`_compute_js()` slug별 분기 원칙 준수 여부**: ✅ 준수 가능
(slug별 분기 없이 `date_formula` 필드 유무로 분기)

### 3-2. 방안 B: self-contained HTML + Registry 메타데이터 하이브리드 ← 추천

**개요**: 날짜 연산 로직은 처음부터 self-contained HTML(inline JS)로 작성.
계산 로직을 Registry에 formula로 보존하지 않는 대신, DB `html_template` 에 저장.
Registry v3에는 메타데이터(slug, category, 입력/출력 라벨, display_order 등)만 등록.
`_rebuild_site.py`는 `tier_subtype: B` 감지 시 `html_template`를 직접 `_site/<slug>/index.html`로 복사.

**방안 B의 세 단계:**
```
[1] App Factory HTML inline 저장
    _APP["html"] → save_app() → DB app_templates.html_template 저장

[2] Registry v3 HOLD 등록
    save_app() → _write_registry_v3() → defense_af.yaml
    (tier_subtype: B, html_source: template_db)

[3] 정적 사이트 빌드
    _rebuild_site.py → tier_subtype=B 감지
    → TemplateRepository로 html_template 조회
    → _site/<slug>/index.html 직접 저장 (script.js/style.css 불필요 — inline)
```

**장점**:
- 기존 `_compute_js()` 수정 불필요 → slug별 분기 원칙 유지
- `formula_engine` 수정 불필요
- `_form_fields_v2()` 수정 불필요 (self-contained HTML이 폼 직접 구현)
- 구현 공수: 최소 (빌드 분기 1개 + Registry 필드 2개 추가)
- jeonse-vs-monthly HTML inline 경험 재사용

**단점**:
- 계산 로직이 DB `html_template` 내 JS에만 존재 — 감사/수정 시 HTML 파일 직접 편집
- `formula_engine.execute_formula()`로 단위 테스트 불가 → JS 로직 단위 테스트는 별도
- 공용 `script.js` 업데이트 미반영 문제 (§7에서 위험도 분석)

**`_compute_js()` slug별 분기 원칙 준수 여부**: ✅ 완전 준수
(`_compute_js()` 자체를 호출하지 않음)

### 3-3. 추천 근거

**방안 B 채택 추천**. 이유:
1. 군인 전역일이 Tier2-B의 첫 계산기 — 날짜 문법 파서(방안 A)를 만들기 전에 요구사항이 더 넓어질 가능성
2. 방안 A는 구현 공수 대비 지금 당장의 효익이 제한적 (날짜형 계산기가 1~2개 수준인 동안)
3. 방안 B는 self-contained HTML을 이미 jeonse-vs-monthly에서 검증한 패턴
4. 방안 A는 날짜 문법 설계가 완성되지 않은 상태에서 구현 시 나중에 schema break 위험

**방안 A로 전환 기준**: 날짜형 계산기가 5개 이상 추가되고 self-contained HTML 관리 부담이
formula dict 대비 현저히 높아질 때.

---

## 4. self-contained HTML 운영 가능성 검토

### 4-1. 기존 사이트 구조와 호환성

현재 `_site/` 내 계산기 페이지 구조:
```
_site/<slug>/
  index.html   ← <script src="script.js"> 포함
  style.css    ← 공용 스타일
  script.js    ← 공용 모듈 + 계산기별 computeResult
```

self-contained HTML 방식:
```
_site/<slug>/
  index.html   ← 스타일/스크립트 모두 inline (script.js/style.css 불필요)
```

**파일 구조 충돌**: 없음. `_rebuild_site.py`가 `tier_subtype: B`를 감지하면
`index.html`만 쓰고 `script.js`/`style.css`는 생성하지 않으면 됨.

### 4-2. CSP(Content Security Policy) 호환성

현재 CalcMate 사이트: **CSP 메타태그/헤더 없음** (조사 확인):
```python
# 확인 결과: 기존 index.html, severance-pay/index.html 모두 CSP 없음
csp = re.findall(r'<meta[^>]*Content-Security-Policy[^>]*>', content, re.IGNORECASE)
# → []
```

self-contained HTML의 inline `<script>` / inline `<style>`은 CSP 제약 없음.
CSP가 없으므로 현재는 호환 문제 없음.

**미래 CSP 도입 시 리스크**: inline script는 `'unsafe-inline'` 또는 nonce가 필요.
현재 공용 `script.js`를 쓰는 계산기(기존 8+2개)도 동일 제약 발생 — 문제 범위 동일.

### 4-3. 공용 컴포넌트 접근 불가

self-contained HTML은 `assets.js`(공용 GA4, 카카오 공유 등)를 로드하지 않음.
jeonse-vs-monthly의 self-contained HTML도 동일 — 현재 이미 이 방식.

**실제 제약**: 카카오 공유, 결과 저장(PNG), PWA 설치 버튼 없음.
이는 UX 상 기능 제한이며, Tier2-B 계산기에는 이 기능 없이 운영하거나
self-contained HTML에 직접 구현 필요.

---

## 5. `_site/` 빌드 연결 방식

### 5-1. 현재 빌드 파이프라인 (Tier2-A)

```python
# scripts/_rebuild_site.py — 현재 흐름
for c in calcs:
    if (_v3.get(slug) or {}).get("status") == "HOLD":
        continue  # HOLD 제외
    files = AG.generate_calculator(c, cfg)   # ← HTML/JS/CSS 생성
    for fname, content in files.items():
        if fname in ("index.html", "style.css", "script.js"):
            (slug_dir / fname).write_text(content, encoding="utf-8")
```

### 5-2. Tier2-B 빌드 경로 설계 (방안 B)

`_rebuild_site.py`에 `tier_subtype: B` 분기 추가:

```python
# 설계 예시 (실제 구현 아님)
v3_entry = _v3.get(slug) or {}
if v3_entry.get("status") == "HOLD":
    continue

if v3_entry.get("tier_subtype") == "B":
    # Tier2-B: DB html_template를 직접 index.html로 저장
    template_id = c.get("template_id")
    if not template_id:
        print(f"  [SKIP] {slug} — Tier2-B지만 template_id 없음")
        continue
    tpl = tpl_repo.get_by_id(template_id)  # TemplateRepository
    html = (tpl or {}).get("html_template", "")
    if not html:
        print(f"  [SKIP] {slug} — html_template 비어있음")
        continue
    slug_dir.mkdir(parents=True, exist_ok=True)
    (slug_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  [OK] {slug} (Tier2-B, html_template 직접 사용)")
else:
    # Tier2-A 또는 기존: generate_calculator() 경로
    files = AG.generate_calculator(c, cfg)
    ...
```

### 5-3. 빌드 분기의 단순성

분기 조건: `v3_entry.get("tier_subtype") == "B"` — 단일 조건.
기존 9개 계산기에 `tier_subtype` 필드 없음 → 모두 else 경로 → 기존 동작 완전 유지.

---

## 6. Registry → index → sitemap 표준 경로 연결 확인

### 6-1. 확인 결과

| 단계 | Tier2-A | Tier2-B | 동일 여부 |
|---|---|---|---|
| save_app() → v3 HOLD 등록 | ✅ | ✅ (동일 함수) | 동일 |
| promote_to_ready() → READY | ✅ | ✅ (동일 함수) | 동일 |
| generate_index() HOLD 제외 | ✅ | ✅ (status 필드 기준) | 동일 |
| generate_sitemap() HOLD 제외 | ✅ | ✅ (status 필드 기준) | 동일 |
| _rebuild_site.py HOLD 제외 | ✅ | ✅ (status 필드 기준) | 동일 |
| _rebuild_site.py READY 빌드 | ✅ generate_calculator() | ⚠️ html_template 직접 사용 | **다름** |

**결론**: HOLD/READY 게이트, index 카드, sitemap은 `status` 필드 기준으로 동작하므로
Tier2-B도 동일하게 적용됨. 빌드 단계만 분기.

### 6-2. save_app() 즉시 v3 기록 원칙 유지

방안 B에서도 `save_app()` → `_write_registry_v3()` 호출 순서 동일.
`_build_v3_entry()`에 `tier_subtype: B`, `html_source: template_db` 필드만 추가.
기존 원칙 완전 유지.

---

## 7. 위험도 분석

### 7-1. self-contained HTML — 공용 script.js 업데이트 미반영 리스크

**위험**: 공용 `script.js`(GA4, 카카오 공유, PWA, renderResult 공통 UI 등)가 업데이트될 때,
Tier2-B self-contained 계산기에는 해당 업데이트가 반영되지 않음.

**현황 확인**: 이미 jeonse-vs-monthly self-contained HTML이 동일 문제를 가짐.
현재 공용 script.js 주요 기능: GA4 추적, 카카오 공유, PWA 설치, renderResult 공통 UI.

**실제 영향 범위**:
- GA4 추적: self-contained HTML에 없으면 해당 계산기 트래픽 미추적 (심각)
- 카카오 공유/PWA/결과저장: UX 기능 차이 (보통)
- 보안 패치(가능성): 공용 script.js에 보안 수정 시 self-contained에 누락 (심각)

**완화 방법 (설계 단계)**:
- Option 1: self-contained HTML도 GA4 snippet을 직접 포함 (최소한의 추적 보장)
- Option 2: `_rebuild_site.py` Tier2-B 빌드 시 GA4 snippet을 자동 삽입하는 래퍼 추가
- Option 3: Tier2-B 계산기 수가 많아지면 방안 A로 전환 (장기 완화)

**수용 가능 수준**: 현재(jeonse-vs-monthly 포함 1~2개) 수준에서는 수용 가능.
5개 이상이 되면 Option 2 구현 또는 방안 A 전환 재검토.

### 7-2. 기존 계산기 Registry 스키마 호환성 리스크

**위험**: `tier_subtype`, `html_source`, `compute_type: date_based_custom` 등 신규 필드를
Registry v3 스키마에 추가할 때, 기존 YAML 파서나 `load_registry_v3()`에서 예상치 못한 동작.

**현황 확인**:
- `load_registry_v3()`는 YAML dict를 그대로 Python dict로 반환 — 미지정 필드는 단순히 포함됨
- 기존 코드에서 알 수 없는 필드에 접근하는 경우: `.get("tier_subtype")` → `None` 반환 (안전)
- 신규 필드는 기존 코드가 참조하지 않으므로 영향 없음

**실제 위험도**: 낮음. YAML 스키마는 유연하며 추가 필드는 무시됨.

**완화 방법**: 신규 필드를 `_af.yaml` 파일(App Factory 전용)에만 추가 — 기존 `*.yaml` 파일 무수정.

### 7-3. 날짜 계산 타임존/윤년 버그 리스크

**위험**: JS Date 연산의 타임존 의존성으로 인해 계산 결과가 실행 환경(브라우저 타임존)에 따라
1일 차이 발생 가능.

**구체적 시나리오**:
```js
// 위험한 패턴 (타임존 의존)
var d = new Date("2025-06-01");          // UTC vs KST 차이로 2025-05-31 될 수 있음
d.setMonth(d.getMonth() + 18);
```

```js
// 안전한 패턴 (타임존 독립)
var parts = enlistmentDate.split("-");   // "2025-06-01" → ["2025", "06", "01"]
var d = new Date(+parts[0], +parts[1]-1, +parts[2]);  // 로컬 자정으로 생성
```

**완화 방법**: self-contained HTML 템플릿에 안전한 날짜 파싱 패턴 포함.
단위 테스트에서 타임존 경계 케이스(UTC±0, KST+9) 명시적 검증.

**윤년 처리**: `new Date(year, month, day)` 방식은 윤년을 자동 처리.
예: `new Date(2024, 1, 29)` → 2024-02-29 (윤년) 정상.

---

## 8. Tier2-B 표준 템플릿 체크리스트

Tier2-A의 표준 경로(formula dict → Registry → DB → 빌드 → QA)에 대응하는 Tier2-B 버전:

### 8-1. 생성 전 준비 체크리스트

```
[ ] 복무기간/날짜 규정의 법적 근거 확보 (HOLD-1 해소)
[ ] 계산 공식 사람이 검증 (병무청 실제 계산기와 대조)
[ ] 병종별 입력값 매핑 확정 (예: army → 18개월)
[ ] 전역일 계산 경계 케이스 정의 (미래 입대, 전역 완료, 윤년)
[ ] _CATEGORY_AF_YAML_MAP에 카테고리 추가 (있다면 재사용)
[ ] 테스트 케이스 최소 5개 수기 계산 완료
```

### 8-2. self-contained HTML 작성 체크리스트

```
[ ] 안전한 날짜 파싱 패턴 사용 (split+로컬 자정 방식)
[ ] rate <= 0 / 미입력 등 경계값 처리
[ ] 모바일 반응형 (viewport, font-size, touch 타겟)
[ ] GA4 기본 추적 snippet 포함 (이벤트: calculate 버튼 클릭)
[ ] 법적 근거 고지문 포함 (footer 또는 input hint)
[ ] 계산 결과 안내문구 (참고용, 실제와 다를 수 있음)
```

### 8-3. App Factory 저장 (_APP dict) 체크리스트

```python
_APP = {
    "name": "...",                           # 계산기 이름
    "category": "...",                       # _CATEGORY_AF_YAML_MAP에 있는 카테고리
    "calculator_type": "date_calculator",    # Tier2-B 식별자
    "formula": {},                           # 빈 dict (날짜 연산은 JS에 있음)
    "labels": { ... },                       # 입력/출력 한국어 라벨
    "input_schema": {
        "enlistment_date": "date",
        "branch": "enum:army,navy,...",      # enum 타입
    },
    "output_schema": {
        "discharge_date":  "string",
        "remaining_days":  "number",
        "progress_pct":    "number",
    },
    "compute_rules": {},                     # rate 제약 없음(날짜 계산기)
    "faq": [ ... ],
    "html": _HTML,                           # self-contained HTML (필수)
    "tier": 2,
    "_formula_valid": True,                  # 수동 세팅
    "_formula_msg": "날짜기반 계산(JS 내장) — 수식 검증 제외",
}
```

### 8-4. Registry v3 엔트리 필드 체크리스트

```yaml
slug:
  name: ...
  category: ...
  source: app_factory
  tier: 2
  tier_subtype: B          # ← Tier2-B 필수
  html_source: template_db  # ← Tier2-B 필수
  compute_type: date_based_custom   # ← Tier2-B 식별
  date_fields: [enlistment_date]
  status: HOLD              # 초기값 (save_app 자동)
  display_order: N          # 순서
```

### 8-5. 사이트 빌드 검증 체크리스트

```
[ ] HOLD 상태: index/sitemap 제외 확인
[ ] promote_to_ready() 후: READY 전환 확인
[ ] _rebuild_site.py: html_template → _site/<slug>/index.html 생성 확인
[ ] _site/<slug>/script.js, style.css: 생성 안 됨 확인 (inline이므로 불필요)
[ ] index.html에 계산기 카드 포함 확인
[ ] sitemap.xml에 slug 포함 확인
[ ] 브라우저에서 계산 결과 3개 출력 확인
[ ] 타임존 테스트 (UTC, KST 환경)
[ ] 윤년 경계 테스트 (예: 2028-02-29 입대)
```

### 8-6. 단위 테스트 체크리스트

```
[ ] 최소 5개 날짜 기반 테스트 케이스 (AUDIT TC-1 ~ TC-5)
[ ] 미래 입대 케이스 (진행률 0%)
[ ] 전역 완료 케이스 (남은일 음수)
[ ] rate/날짜 미입력 오류 처리
[ ] Python dateutil.relativedelta으로 예상값 계산 후 HTML JS와 비교
```

---

## 9. 결정 필요 항목

구현 시작 전에 사용자 판단이 필요한 항목:

| # | 항목 | 선택지 | 현재 추천 |
|---|---|---|---|
| D-1 | **전제 버그 수정 선행 여부** | (A) Tier2-B 전에 _compute_js validation 분기 버그 수정 (B) Tier2-B와 별개로 나중에 수정 | **A 추천** (Tier2-A 표준 경로 완성이 선행되어야) |
| D-2 | **방안 A vs 방안 B 최종 선택** | (A) date_formula 파서 구현 (B) self-contained HTML 하이브리드 | **B 추천** (§3-3 근거) |
| D-3 | **카테고리 결정** | (A) "국방/병역" 신규 카테고리 (B) 기존 카테고리에 편입 | **A 추천** (분류 명확성) |
| D-4 | **GA4 추적 처리** | (A) self-contained HTML에 GA4 snippet 직접 포함 (B) _rebuild_site.py가 자동 삽입 (C) 일단 GA4 없이 운영 | **A 추천** (가장 단순) |
| D-5 | **HOLD-1(전역일 공식 근거) 해소 시점** | (A) 이 설계 구현 전에 해소 (B) 구현 후 promote_to_ready 직전에 해소 | **B 가능** (설계/구현은 HOLD-1과 독립) |

---

## 부록: 구현 시 변경 파일 예상 범위 (방안 B 기준)

| 파일 | 변경 내용 | 기존 계산기 영향 |
|---|---|---|
| `modules/app_factory.py` | `_build_v3_entry()`에 `tier_subtype`, `html_source` 필드 추가; `_CATEGORY_AF_YAML_MAP`에 "국방/병역" 추가 | 없음 (선택적 필드) |
| `scripts/_rebuild_site.py` | `tier_subtype=B` 감지 후 `html_template` 직접 복사 분기 추가 | 없음 (else 경로 유지) |
| `modules/app_generator.py` | *(방안 B는 미수정)* `_form_fields_v2()`의 enum 지원은 self-contained HTML이 폼 직접 구현하므로 불필요 | 없음 |
| `docs/registry/defense_af.yaml` | 신규 생성 (저장 시 자동) | 없음 |
| `scripts/_save_military_discharge.py` | 1회 실행 스크립트 (실행 후 삭제) | 없음 |
| `tests/test_military_discharge.py` | 단위 테스트 신규 | 없음 |

**수정 파일: 2개** (`app_factory.py`, `_rebuild_site.py`)
**신규 파일: 3개** (`defense_af.yaml`, `_save_*.py`, `tests/test_*.py`)
**기존 계산기 영향: 0개**

---

*설계 기준: 2026-08-09 / 코드 작성/실행/Registry 변경 없음*
