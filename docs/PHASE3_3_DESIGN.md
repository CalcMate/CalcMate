# Phase3-3 대시보드 검토센터 설계

**기반 조사**: `docs/PHASE3_3_0_DASHBOARD_AUDIT.md`  
**기준 커밋**: `b54c684` (v2.2.0)  
**작성일**: 2026-08-09  
**상태**: 결정사항 확정 — 구현은 별도 승인 후

---

## 핵심 목표

> "AI가 계산기를 만들고, 무엇을 사람이 확인해야 하는지도 스스로 찾아서 대시보드에 보여주는 것"

완성 범위:

```
[이름 입력] → [AI 추천: Tier/공식/출력/slug] → [운영자 수정] → [생성]
     → [검토 체크리스트 표시] → [체크 완료 + PASS] → [Build QA] → [Build]
     → [수동 배포 안내 화면]
```

**운영 원칙**: AI 추천은 자동화하되, 법률·세액·급여·복지 등 정확성이 중요한 항목의 최종 승인은 자동화하지 않는다. 이 원칙은 계산기가 20~30개로 늘어도 유지된다.

Deploy(commit/push/Actions) 자동화는 이번 Phase 범위 밖 — 수동 유지.

---

## 확정된 결정사항 요약

| ID | 항목 | 결정 |
|---|---|---|
| D-1 | Tier 기본값 | AI 추천값으로 자동 선택 + 운영자 최종 확인/변경 |
| D-2 | legal_basis 조건 | 카테고리 기반: 세금/법령/복지 → 🔴, 순수 산술 → 🟡 |
| D-3 | 체크 취소 | 취소 가능, 취소 시 재확인 필요 |
| D-4 | Tier2-B QA skip | date_based 계산기는 formula dict QA 자동 skip |
| D-5 | Build 단위 | 전체 `_rebuild_site.py` 실행 (index/sitemap 포함) |

---

## 1. 검토 체크리스트 데이터 구조

### 1-1. 체크리스트 항목 스키마

```yaml
ChecklistItem:
  id: str                         # "formula_accuracy", "legal_basis" 등
  severity: "critical" | "advisory"  # critical=🔴 필수, advisory=🟡 권장
  label: str                      # 화면 표시 텍스트
  display_value: str | null       # 실제 값 (읽지 않고 클릭 방지)
  auto_source: str                # 이 항목이 어떤 규칙에서 추출됐는지
  checked: bool
  checked_by: str | null          # 현재: "operator" 고정
  checked_at: str | null          # ISO 8601
```

**`display_value`의 역할**: 항목 옆에 실제 값을 노출해 "읽지 않고 클릭" 방지.
- 계산공식 항목 → formula 전문 표시
- 법적 근거 항목 → legal_refs 현재 값 (없으면 "⚠️ 미입력" 표시)
- 세율/계수 항목 → 공식에서 추출한 상수 목록 표시
- 기준 연도 항목 → "직접 확인 필요" + legal_refs 값

### 1-2. 저장 위치

**Registry v3 `_af.yaml`에 `review_checklist` 필드 추가.**

```yaml
# docs/registry/realty_af.yaml 예시
jeonse-vs-monthly:
  status: HOLD
  tier: 2
  source: app_factory
  # ... 기존 필드 ...
  review_checklist:
    - id: formula_accuracy
      severity: critical
      label: "계산 공식 정확성"
      display_value: "(jeonse_deposit - wolse_deposit) * rate / 100 / 12"
      auto_source: "formula_field"
      checked: false
      checked_by: null
      checked_at: null
```

**이유**:
- 계산기 상태(HOLD/READY)와 같은 파일 — 단일 진실 소스
- `promote_to_ready()`가 같은 파일에서 체크리스트 완료 여부 검증 가능
- HOLD → READY 전환 시 체크리스트 이력 보존 (감사 추적)

**기각된 대안**:
- 별도 DB 테이블: Registry v3 SSOT 구조와 분리 → 기각
- calculators DB 컬럼 추가: App Factory 전용 필드를 공통 테이블에 추가, 구조 오염 → 기각

### 1-3. 감사 추적

현재: `checked_by: "operator"` 고정 (단일 운영자 가정).
`checked_at`은 체크 시각(ISO 8601) 기록. **D-3 결정**에 따라 체크 취소 허용 — 취소 시 `checked: false`, `checked_by: null`, `checked_at: null`로 초기화.

---

## 2. 🔴 필수 vs 🟡 권장 분류 기준

### 2-1. 카테고리 기반 legal_basis 분류 (D-2 확정)

legal_basis의 🔴/🟡 여부는 **계산기 카테고리**로 결정한다.

| 카테고리 | legal_basis 등급 | 예시 |
|---|---|---|
| 세금/세법 | 🔴 필수 | 프리랜서3.3%, 원천징수, 부가세 |
| 노동/고용법 | 🔴 필수 | 실업급여, 퇴직금, 주휴수당, 연차수당 |
| 복지/사회보험 | 🔴 필수 | 4대보험, 육아휴직급여 |
| 병역/공무 | 🔴 필수 | 군인전역일 계산기 |
| 부동산/임대 | 🟡 권장 | 전세vs월세 (법정이율 있으나 고정 비교값이 아님) |
| 단순 산술/비율 | 🟡 권장 | 단순 퍼센트 계산, 이자 계산 |
| 날짜/기간 계산 | 🟡 권장 (Tier2-B) | 복무 만료일, D-Day 계산 |
| 미분류 (null) | 🔴 필수 (보수적) | — |

카테고리는 계산기 생성 시 `category` 필드에서 읽는다.

### 2-2. 항목 분류표 (Tier2-A 기준)

| ID | 레이블 | 🔴/🟡 | 추출 조건 | `display_value` |
|---|---|---|---|---|
| `formula_accuracy` | 계산 공식 정확성 | 🔴 | formula 있는 경우 (Tier2-A) | formula 전문 |
| `legal_basis` | 법적 근거 (법령/조항) | D-2 카테고리 기준 | 항상 | legal_refs 값 또는 "⚠️ 미입력" |
| `rate_constant` | 적용 세율/계수 확인 | 🔴 | formula에 소수점 상수 포함 시 | 공식 내 추출 상수 목록 |
| `base_year` | 기준 연도/시행일 | 🔴 | 🔴 카테고리 계산기에 항상 | "직접 확인 필요" + legal_refs |
| `default_values` | 기본 입력값 타당성 | 🔴 | input_schema에 default 있는 경우 | default 값 목록 |
| `edge_cases` | 예외조건 처리 | 🔴 | compute_rules 있는 경우 | compute_rules 내용 |
| `seo_title` | SEO 제목 검토 | 🟡 | seo_title 있는 경우 | seo_title 값 |
| `faq_content` | FAQ 내용 검토 | 🟡 | faq 있는 경우 | FAQ Q 목록 |
| `description_text` | 설명 문구 검토 | 🟡 | desc 있는 경우 | desc 값 |

### 2-3. Tier별 항목 차이

| 항목 | Tier2-A (산술형) | Tier2-B (날짜형) | Tier1 (법령복잡형) |
|---|---|---|---|
| `formula_accuracy` | 🔴 | ❌ (날짜 로직, formula 없음) | 🔴 |
| `legal_basis` | D-2 카테고리 기준 | D-2 카테고리 기준 | 🔴 |
| `rate_constant` | 🔴 (상수 포함 시) | ❌ | 🔴 |
| `base_year` | 🔴 카테고리만 | 🔴 카테고리만 | 🔴 |
| `default_values` | 🔴 (해당 시) | 🟡 | 🔴 |
| `edge_cases` | 🔴 (해당 시) | 🔴 | 🔴 |

### 2-4. 항목 자동 추출 로직 — 규칙 기반 채택

AI 분석 대신 규칙 기반을 선택한 이유: 예측 가능성이 높고, 매번 같은 결과를 보장하며, AI 오판으로 필수 항목이 누락되는 위험이 없다.

**추출 의사코드**:

```python
CRITICAL_CATEGORIES = {"세금/세법", "노동/고용법", "복지/사회보험", "병역/공무"}

def extract_checklist(app: dict, tier: str, category: str) -> list[ChecklistItem]:
    items = []
    formula = app.get("formula")
    legal_refs = app.get("legal_refs") or []
    compute_rules = app.get("compute_rules") or {}
    defaults = {k: v.get("default") for k, v in (app.get("input_schema") or {}).items()
                if isinstance(v, dict) and "default" in v}

    # D-2: legal_basis 등급 결정
    legal_severity = "critical" if (not category or category in CRITICAL_CATEGORIES) else "advisory"

    # formula_accuracy: Tier2-A + formula 있는 경우
    if formula and tier == "Tier2-A":
        formula_str = json.dumps(formula) if isinstance(formula, dict) else str(formula)
        items.append(ChecklistItem(
            id="formula_accuracy", severity="critical",
            label="계산 공식 정확성",
            display_value=formula_str[:400],
            auto_source="formula_field"
        ))

    # legal_basis: 항상 (등급은 카테고리로 결정)
    disp = "⚠️ legal_refs 미입력" if not legal_refs else str(legal_refs)
    items.append(ChecklistItem(
        id="legal_basis", severity=legal_severity,
        label="법적 근거 (법령/조항)",
        display_value=disp,
        auto_source="legal_refs_empty" if not legal_refs else "legal_refs_present"
    ))

    # rate_constant: formula에 소수점 상수 포함 시
    if formula:
        constants = re.findall(r'\b\d+\.\d+\b', str(formula))
        if constants:
            items.append(ChecklistItem(
                id="rate_constant", severity="critical",
                label="적용 세율/계수 확인",
                display_value=f"공식 내 상수: {constants}",
                auto_source="formula_constants"
            ))

    # base_year: 🔴 카테고리만
    if legal_severity == "critical":
        items.append(ChecklistItem(
            id="base_year", severity="critical",
            label="기준 연도/시행일 확인",
            display_value="직접 확인 필요 — 법령 시행일 또는 세율 적용 연도",
            auto_source="critical_category"
        ))

    # default_values
    if defaults:
        items.append(ChecklistItem(
            id="default_values", severity="critical",
            label="기본 입력값 타당성",
            display_value=str(defaults),
            auto_source="input_defaults"
        ))

    # edge_cases
    if compute_rules:
        items.append(ChecklistItem(
            id="edge_cases", severity="critical",
            label="예외조건 처리 확인",
            display_value=str(compute_rules)[:300],
            auto_source="compute_rules"
        ))

    # 🟡 권장: SEO / FAQ
    if app.get("seo_title"):
        items.append(ChecklistItem(id="seo_title", severity="advisory",
            label="SEO 제목 검토", display_value=app["seo_title"],
            auto_source="seo_title_field"))
    if app.get("faq"):
        faq_qs = [f.get("q", "") for f in app["faq"][:3]]
        items.append(ChecklistItem(id="faq_content", severity="advisory",
            label="FAQ 내용 검토", display_value=str(faq_qs),
            auto_source="faq_field"))

    return items
```

---

## 3. HOLD → READY 게이트 설계

### 3-1. 전환 조건 (AND 조건)

```
READY 전환 가능 조건:
  [1] 🔴 필수 체크리스트 항목 전체 checked == True
  AND
  [2] 운영자가 [✅ READY 전환] 버튼을 명시적으로 클릭

체크리스트만으로 자동 READY 전환: 불가
AI가 checked = True로 자동 설정하는 경로: 없음
```

### 3-2. UI 흐름

```
계산기 관리 탭 → HOLD 계산기 expander 내부

─────────────────────────────────────────────────────────────
⚠️ LEGAL HOLD — 아래 항목을 직접 확인한 후 READY 전환

🔴 필수 검토 (전체 완료해야 READY 버튼 활성화)
┌───────────────────────────────────────────────────────────────┐
│ ☐  계산 공식 정확성                                            │
│    (jeonse_deposit - wolse_deposit) * rate / 100 / 12         │
├───────────────────────────────────────────────────────────────┤
│ ☐  법적 근거 (법령/조항)                                       │
│    ⚠️ legal_refs 미입력 — 주택임대차보호법 제7조의2 등 입력 필요│
├───────────────────────────────────────────────────────────────┤
│ ☐  적용 세율/계수 확인                                         │
│    공식 내 상수: ['4.75', '100', '12', '1200']                 │
├───────────────────────────────────────────────────────────────┤
│ ☐  기준 연도/시행일 확인                                       │
│    직접 확인 필요 — 법령 시행일 또는 세율 적용 연도            │
└───────────────────────────────────────────────────────────────┘

🟡 권장 검토 (선택사항)
┌───────────────────────────────────────────────────────────────┐
│ ☐  SEO 제목 검토: "전세 vs 월세 비교 계산기 | CalcMate"       │
│ ☐  FAQ 내용 검토: ['전세가 유리한 경우는?', '월세전환율이란?'] │
└───────────────────────────────────────────────────────────────┘

[진행 현황] 🔴 필수 0/4 완료
[✅ READY 전환]  ← 🔴 필수 전체 완료 시에만 활성화
─────────────────────────────────────────────────────────────
```

### 3-3. D-3: 체크 취소 허용 설계

```
체크된 항목 재클릭 →
  st.warning("이 항목의 확인을 취소하시겠습니까?") 표시
  [확인] 클릭: checked=False, checked_by=null, checked_at=null
  [취소] 클릭: 기존 checked=True 유지
```

취소를 허용하는 이유: 잘못 클릭한 경우 수정 불가 상태가 되면 오히려 형식적 체크를 조장할 수 있음.

### 3-4. 기존 원칙과의 정합성

- "AI 자동 PASS 금지" ✅ 유지
- READY 버튼 클릭은 사람의 명시적 행위이며 `promote_to_ready()` 함수를 통해서만 전환
- `promote_to_ready()` 내부에서 `review_checklist` 미완료 시 예외 발생 (서버측 이중 차단)

---

## 4. Build 버튼 및 사전 HTML 출력 QA

### 4-1. Build 버튼 활성화 조건

```
Registry v3 status == "READY"인 경우에만 Build 버튼 렌더링
HOLD 상태에서는 버튼 자체를 표시하지 않음
```

### 4-2. 6단계 사전 검사 설계

Build 클릭 → QA 실행 → 전부 통과 시에만 `_rebuild_site.py` 실행.
QA는 `generate_calculator(calc, cfg)` 반환 파일로 검사 (실제 계산기 실행 없음).

**D-4**: `compute_type == "date_based"` 이면 Step 3~5 자동 skip.

```
Step 1: input_schema 존재 확인
  PASS: input_schema가 비어있지 않음
  FAIL: "입력 스키마 없음 — generate_app() 재실행 필요"

Step 2: output_schema 존재 확인
  PASS: output_schema가 비어있지 않음
  FAIL: "출력 스키마 없음"

Step 3: output_schema key ↔ HTML id="out_*" 1:1 대응  [jeonse Bug2 재발 방지]
  [Tier2-B: AUTO-SKIP → "날짜형 계산기 — HTML ID 직접 확인 필요"]
  PASS: output_schema의 모든 key가 id="out_{key}"로 HTML에 존재
  FAIL: "HTML에 없는 출력 ID: {누락 목록}"

Step 4: formula dict 모든 key가 JS computeResult에서 처리되는지  [jeonse Bug1 재발 방지]
  [Tier2-B: AUTO-SKIP]
  [단일 formula: "단일 출력 — 해당 없음 (PASS)"]
  PASS: formula.keys() ⊆ JS에서 추출한 out["key"] 집합
  FAIL: "JS에서 누락된 출력 키: {목록}"

Step 5: 복수 출력 완전성
  [Tier2-B: AUTO-SKIP]
  PASS: len(output_schema.keys()) == len(HTML id="out_*" 요소)
  FAIL: "출력 {N}개 중 HTML ID {M}개만 존재"

Step 6: 기본 입력값으로 계산 실행 가능 여부
  input_schema default 값 또는 더미 최솟값(1.0)으로 formula_engine 실행
  PASS: 에러 없이 숫자/dict 반환
  FAIL: "계산 오류: {에러 메시지}"
```

### 4-3. QA 결과 화면

```
Build QA 실행 중... (spinner)

결과:
✅ Step 1: 입력 스키마 존재 — 4개 항목
✅ Step 2: 출력 스키마 존재 — 3개 항목
✅ Step 3: HTML 출력 요소 1:1 대응 — 3/3
✅ Step 4: JS 다중 출력 처리 — 3/3 키
✅ Step 5: 복수 출력 완전성 — 3/3
✅ Step 6: 기본값 계산 실행 — 성공

→ 전체 통과 → _rebuild_site.py 실행 중...

또는:

❌ Step 3: HTML 출력 요소 1:1 대응
   HTML에 없는 출력 ID: {'monthly_savings', 'wolse_to_jeonse_equiv'}
   → Build 차단. 위 문제를 해결 후 재시도하세요.
```

### 4-4. D-5: Build 실행 단위

전체 `_rebuild_site.py` 실행. index 카드, sitemap.xml까지 항상 Production 상태에 맞춤.
전체 빌드 시간은 수 초 이내이므로 부분 빌드의 이점이 없음.

---

## 5. slug 중복 차단 (D 확정)

### 5-1. 차단 시점

**이름 입력 단계** — 생성 버튼 클릭 전에 실시간 대조.

### 5-2. 차단 로직

```python
def check_slug_conflict(name: str) -> tuple[str, bool, str]:
    auto_slug = _slug(name)  # app_factory._slug() 재사용
    v3_slugs = set(load_registry_v3().keys())
    try:
        db_slugs = {c.get("slug") for c in CalculatorRepository(...).get_all()}
    except Exception:
        db_slugs = set()
    all_slugs = v3_slugs | db_slugs

    if auto_slug in all_slugs:
        return auto_slug, True, f"'{auto_slug}' 슬러그가 이미 존재합니다."
    return auto_slug, False, ""
```

### 5-3. UI 흐름

```
이름 입력: "퇴직금 계산기"
→ slug 자동 생성: "toejigeum-gyesanggi"
→ 실시간 확인: ❌ 중복! 이미 존재합니다 (severance-pay 참조)
→ 생성 버튼 비활성화

이름 입력: "월세 전환 이자 계산기"
→ slug: "wolse-jeonhwan-ija-gyesanggi"
→ 실시간 확인: ✅ 중복 없음
→ 생성 버튼 활성화
```

**이중 차단**: `save_app()` 저장 단계에서도 같은 중복 검사 재실행 (UI~저장 경쟁 조건 방지).

---

## 6. Tier 추천 UI (D-1 확정)

### 6-1. 추천 흐름

AI(GPT-4o)가 이름/설명으로 Tier 추천 → 추천값이 라디오 기본 선택으로 자동 세팅 → 운영자 확인/변경.

### 6-2. 추천 프롬프트

```
system:
  너는 한국 웹 계산기 분류 전문가다.

  Tier2-A: 단순 산술/비율 공식으로 표현 가능. 날짜 계산 없음. 구간 요율 없음.
           예: 원천징수(총액×3.3%), 전세 기회비용(금액×이율÷12)
  Tier2-B: 핵심 로직이 날짜 덧셈/기간 계산. 단순 산술로 표현 불가.
           예: 복무 만료일, 육아휴직 종료일
  Tier1:   날짜 계산, 구간별 누진 요율, 다단계 법령 분기 등.
           예: 퇴직금, 실업급여

  JSON만 반환: {"tier": "Tier2-A", "reason": "이유 1~2문장", "confidence": "high|medium|low"}

user:
  계산기명: {name}
  설명: {desc}
```

### 6-3. UI 흐름 (D-1 반영)

```
[AI 분석 중...]

Tier 선택 (최종은 운영자가 확인/변경):
● Tier2-A — 단순 산술/일반 공식   ← AI 추천 (신뢰도: 높음)
            "단순 사칙연산으로 표현 가능. 날짜 계산 없음."
○ Tier2-B — 날짜/기간 계산형
○ Tier1   — 법령/조건분기/복잡 계산

⚠️ Tier가 틀리면 Build 단계에서 오류가 날 수 있습니다. 확인 후 진행하세요.
```

**신뢰도 표시**:
- `high`: 추천 표시만
- `medium`: "⚠️ 확신도 보통 — 직접 확인 권장"
- `low`: "🚨 분류 불확실 — 반드시 직접 판단하세요" (강조)

**Tier2-B 키워드 사전 감지** (rule-based, AI 이전): 이름/설명에 "날짜", "기간", "전역일", "만료일", "종료일", "D-Day" 포함 시 배너 경고 표시 (라디오 선택값과 무관).

**Tier2-B 추천 시**: "Tier2-B는 현재 App Factory 미지원. `docs/TIER2_B_DESIGN.md` 확인 필요" 안내.

---

## 7. Deploy 준비 화면 설계

Build 완료 직후 표시. 수동 배포 4단계를 안내하여 누락 방지.

### 7-1. 화면 구성

```
✅ Build 완료 (2026-08-09 09:58 KST)
   _site/ 갱신됨 — 9개 계산기, sitemap.xml 포함

─────────────────────────────────────────────────────────────
📋 배포 전 확인 체크리스트 (수동 진행)
─────────────────────────────────────────────────────────────

Step 1  git commit
        ┌──────────────────────────────────────────────────────┐
        │ git add data/workspace/_site/ docs/registry/         │
        │ git commit -m "feat(phase3-N): add {slug} calculator"│
        └──────────────────────────────────────────────────────┘

Step 2  git push
        ┌──────────────────────────────────────────────────────┐
        │ git push origin master                               │
        └──────────────────────────────────────────────────────┘

Step 3  GitHub Actions 확인
        → 최신 워크플로 ✅ 완료 상태 확인

Step 4  실제 사이트 확인
        - https://calcmate.kr/             (메인 카드 노출)
        - https://calcmate.kr/{slug}/      (HTTP 200 + 출력 요소)
        - https://calcmate.kr/sitemap.xml  (URL 포함)
─────────────────────────────────────────────────────────────
⚠️ Step 3·4가 확인될 때까지 "배포 완료"로 간주하지 마세요.
─────────────────────────────────────────────────────────────
```

### 7-2. 수동 유지 이유

- git push 자동화 → Build QA 통과해도 사고 발생 가능 (과거 재발 방지)
- Actions 실패 실시간 감지에는 GitHub API 폴링 필요 — Phase3 범위 초과
- 단계적 확장: 이번 Phase는 "생성→검토→Build" 완성, Deploy는 다음 Phase

---

## 8. 위험도 분석

### 8-1. 체크박스 형식적 체크 위험

**위험**: 운영자가 내용을 읽지 않고 클릭만.

**완화 방안**:
- `display_value`에 실제 값 노출 (공식 전문, legal_refs 값, 상수 목록)
- 🔴 항목에 "⚠️ 미입력" 상태 붉게 강조
- D-3 취소 허용: "어차피 못 돌리니까 대충 찍자" 심리 감소
- PASS 버튼 위에 "위 🔴 필수 항목 전체를 직접 확인하였습니다" 문구 명시

**한계**: 의도적 우회는 방지 불가. 실수 방지 도구이지, 책임 강제 도구가 아님.

### 8-2. Tier 추천 오분류 위험

**위험**: AI 추천이 틀렸는데 운영자가 기본 선택값을 변경하지 않고 수용.

**시나리오**:
- "육아휴직 만료일 계산기" → AI가 Tier2-A 추천, 실제는 Tier2-B
- "최저임금 위반 판단 계산기" → Tier2-A 추천, 실제는 조건분기 필요

**완화 방안**:
- 신뢰도 `low`/`medium` 시 강조 경고 (섹션 6-3)
- Tier2-B 키워드 rule-based 사전 감지 배너 (AI 이전 단계)
- 추천 근거("이유 1~2문장") 항상 표시 — 운영자가 판단 가능하게
- D-4: date_based QA 자동 skip으로 false positive 방지

**잔존 위험**: 운영자가 근거를 읽지 않고 AI 추천 수용 — 절차적 설계로 100% 방지 불가.

### 8-3. HTML 출력 QA false negative 위험

**위험**: QA "통과"를 줬지만 실제로는 문제가 있는 경우.

| 유형 | 원인 | D-4 대응 |
|---|---|---|
| Tier2-B (날짜형) | output_schema 없이 JS Date 로직으로만 처리 | Step 3~5 자동 skip + "직접 확인 필요" 표시 |
| 미래 신규 유형 | QA 규칙이 새 유형을 알지 못함 | "알 수 없는 유형 — 수동 확인 권장" 경고 |
| 복잡한 조건분기 | formula dict 외 별도 JS 로직 | Step 4 정규식이 모든 패턴을 잡지 못할 수 있음 |

**완화 방안**:
- Step 4 정규식 확장 가능하도록 설계 (`out["key"]` 외 패턴도 감지)
- QA skip 시 "⚠️ 이 단계는 건너뜀 — 수동 확인 필요" 명시
- "전체 통과 = 배포 안전" 보장이 아님을 결과 화면에 명시

---

## 9. 전체 흐름 다이어그램 (Phase3-3 완성 후)

```
🏭 App Factory 탭
│
├─ [이름 + 설명 입력]
│   → slug 자동 생성 → 실시간 중복 확인
│   → Tier2-B 키워드 감지 배너 (rule-based)
│   → AI Tier 추천 → 라디오 기본값 자동 세팅 (D-1)
│   → 운영자 Tier 확인/변경
│   → 중복 없음 + Tier 선택 완료 → [🏭 자동 생성] 활성화
│
├─ [🏭 자동 생성]
│   → generate_app(): 스펙/HTML/SEO/FAQ/formula 생성
│   → 검토 체크리스트 자동 추출 (규칙 기반, D-2 카테고리)
│
├─ [💾 저장]
│   → save_app(): DB + Registry v3 HOLD
│   → review_checklist 첨부 (전부 unchecked)
│
🧮 계산기 관리 탭
│
├─ HOLD 계산기
│   └─ [검토 체크리스트]
│       ├─ 🔴 필수 (display_value 함께 표시)
│       │   └─ 체크 클릭 → checked=True + timestamp
│       │   └─ 재클릭 → 재확인 후 취소 가능 (D-3)
│       └─ 전체 🔴 완료 → [✅ READY 전환] 활성화
│           └─ 클릭 → promote_to_ready() → status=READY
│
└─ READY 계산기
    └─ [⚙️ Build]
        → QA Step 1~6
          (D-4: date_based이면 Step 3~5 자동 skip)
        ├─ 실패 → 차단 + 구체적 이유
        └─ 통과 → _rebuild_site.py 전체 실행 (D-5)
                  → ✅ Build 완료
                  → 수동 배포 4단계 안내 화면
```

---

*설계 기준: 2026-08-09 / D-1~D-5 확정 반영 / 구현은 별도 승인 후*
