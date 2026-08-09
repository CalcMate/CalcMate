# Phase3-3-0 대시보드/App Factory 운영화 현황조사 결과

**조사일**: 2026-08-09  
**기준 커밋**: `b54c684` (v2.2.0)  
**조사 방법**: 코드 읽기 전용 (코드/Registry/DB 수정 없음, 실행 없음)  
**조사 파일**: `dashboard.py` (2858줄), `modules/app_factory.py` (509줄), `modules/github_deployer.py` (122줄), `modules/ai_roles.py` (59줄)

---

## 1. 조사 대상별 발견사항 (10개 항목)

---

### 1-1. 현재 대시보드 "계산기 생성" 관련 화면 구조

**탭 경로**: 사이드바 `🧮 Calculator` → `🏭 App Factory` (dashboard.py line 1979)

**화면 흐름 (실제 코드 기준)**:

```
[🔍 키워드 입력] → "키워드로 제안" 버튼 → AF.suggest_idea(keyword) 호출
                                               ↓ name/category/desc 자동채움
[💡 AI 아이디어 제안] 버튼 ─────────────────→ AF.suggest_idea() 호출 (키워드 없음)
                                               ↓
[Tier 선택 라디오] ← 사람이 직접 선택 (Tier1 or Tier2)
[계산기명 * 필수] ← 사람 입력 (또는 suggest 결과 자동채움)
[카테고리] ← 사람 입력 또는 suggest 결과
[설명] ← 사람 입력 또는 suggest 결과
                                               ↓
[🏭 자동 생성] 버튼 → AF.generate_app() 호출 → AI 4단계(스펙/코드/SEO/이미지)
                                               ↓
생성 결과 표시: steps / HTML미리보기 / FAQ / 스키마 / formula 타입 / SEO 제목
[slug 수동 확정 입력]
                                               ↓
[💾 저장] 버튼 → AF.save_app() → DB + Registry v3 HOLD 등록
```

**연결된 두 번째 탭**: `🧮 계산기 관리` (dashboard.py line 1756)

```
계산기별 expander 내부:
  - HOLD 상태면 "✅ READY 전환" 버튼 (AF_CM.promote_to_ready() 호출)
  - 수식 편집 + 저장 (FE.validate_formula → FE.save_formula)
  - AI 자동 생성: SEO / FAQ / 본문 / 이미지 프롬프트 / 전체 자동생성
  - 앱 미리보기 (iframe)
  - [🚀 배포] / [파일 저장] / [상태토글] / [삭제] 버튼
```

---

### 1-2. 현재 입력 범위

**사람이 반드시 입력해야 하는 항목**:

| 항목 | 현재 상태 | 설명 |
|---|---|---|
| Tier 선택 | **필수 수동 선택** | Tier1/Tier2 라디오 버튼 (AI 자동 판정 없음) |
| 계산기명 | **필수 수동 입력** | (AI 제안으로 자동채움 가능하나, 최종 확인은 사람) |
| slug | **필수 수동 확정** | 생성 후 영문 slug를 사람이 입력/확인 후 저장 |

**AI가 자동 생성하는 항목**:

| 항목 | 생성 주체 | 사람 개입 |
|---|---|---|
| 카테고리 / 설명 | AI suggest_idea() (GPT-4o) | suggest 결과를 사람이 확인 가능 |
| input_schema | AI generate_app() (GPT-4o) | 저장 전 expander에서 확인 가능 |
| output_schema | AI generate_app() (GPT-4o) | 저장 전 확인 가능 |
| formula / formula dict | AI generate_app() (GPT-4o) | 수식 검증 통과 여부 표시 |
| HTML (인라인 자가완결형) | AI generate_app() (Claude) | 미리보기 가능 |
| SEO 제목 / 메타설명 | AI generate_app() (GPT-4o) | 표시됨 |
| FAQ 목록 | AI generate_app() (GPT-4o) | expander에서 확인 가능 |
| 이미지 프롬프트 | AI generate_app() (Gemini) | 표시됨 |

**Phase3-2 실제 생성 경로와의 대조**:

Phase3-2(전세 vs 월세)는 **대시보드 경유하지 않음**. Claude Code가 직접 `app_factory.save_app()` 호출. 입력 항목도 Claude Code가 연구·조사 후 직접 지정:
- 계산기명: 사람(Claude Code)이 지정
- formula dict: 사람(Claude Code)이 법령 조사 후 직접 설계 (AI 생성 아님)
- input/output schema: 사람(Claude Code)이 직접 설계
- compute_rules: 사람(Claude Code)이 직접 지정
- 카테고리/설명: 사람(Claude Code)이 직접 지정

> **결론**: Phase3-2의 실제 경로는 대시보드 App Factory UI가 아닌 Claude Code 직접 호출이었으며, 법령 조사·공식 설계·QA 전부 사람(Claude Code) 단계에서 이루어졌다. 대시보드의 "자동 생성" 버튼과는 전혀 다른 경로였다.

---

### 1-3. "AI 자동분석" 파트 현재 존재 여부

**① Tier 판정 AI 자동제안**:
- **없음**. 사람이 라디오 버튼으로 직접 선택 (Tier1 or Tier2).
- `generate_app()`은 사람이 선택한 `tier` 파라미터를 받아서 프롬프트에 삽입할 뿐, AI가 Tier를 먼저 판단하는 기능은 없음.

**② 입력값/출력값/계산식 AI 초안 생성**:
- **있음**. `generate_app()` Step 1 (GPT-4o, orchestrator role)에서 자동 생성.
- formula 검증 실패 시 1회 재시도 로직 포함.
- 그러나 법령 근거·세율 정확성은 AI가 보장하지 않음 (프롬프트에 정확성 요구 없음).

**③ SEO/FAQ 콘텐츠 자동 생성 연결**:
- **App Factory 내부에 포함됨**. `generate_app()` Step 3 (GPT-4o, writer role)에서 동시 생성.
- **별도 연결 없음**: 기존 WordPress 파이프라인의 calculator_content_generator / calculator_faq_generator와는 독립적으로 구현됨. 재사용 구조가 아니라 별도 코드.
- `🧮 계산기 관리` 탭에서 "SEO 생성/FAQ 생성" 버튼 별도 제공 (calculator_seo_generator, calculator_faq_generator 모듈 경유).

---

### 1-4. "검토 필요 항목" 표시 기능 현재 존재 여부

**있는 것**:
- HOLD 상태 계산기에 `🔴 LEGAL HOLD` 배지 표시 (dashboard.py line 1798)
- 경고 메시지: "legal 검증(법령 근거/계산 공식) 완료 후 READY 전환하세요" (line 1805-1809)

**없는 것**:
- 구체적으로 "어떤 항목이 검토가 필요한지" 자동 추출 로직 없음
  - `_build_registry_entry()`에서 `reviewer_expectation: []` 빈 배열로 등록 (line 397)
  - Registry entry의 `legal_refs`, `law`, `article` 필드도 모두 null/빈값 (line 394-396)
- "이 계산기는 세율이 법령에 명시되어 있으므로 확인 필요" 같은 맥락 인식 없음

**Phase3-2의 HOLD-1 해결 과정 대조**:
- HOLD-1(전월세전환율 법령 확인) 해결은 Claude Code가 대화를 통해 직접 조사
- 대시보드가 "이걸 확인하세요"라고 유도한 것이 아님
- 검토 과정이 대시보드에 기록되지 않음

> **결론**: HOLD 상태 표시는 있으나, "무엇을 검토해야 하는지" 안내 기능은 전무. LEGAL HOLD 배지는 있지만 빈 warning 메시지만 있고 구체적인 체크리스트나 법령 근거 추출 기능은 없다.

---

### 1-5. [검토]/[PASS] 승인 게이트 현재 상태

**대시보드 버튼 존재**: `✅ READY 전환 (legal 검증 완료)` (dashboard.py line 1810)

**동작 방식**:
```python
if st.button(f"✅ READY 전환 (legal 검증 완료)", key=f"cm_ready_{cid}", type="primary"):
    _ok_r, _msg_r = AF_CM.promote_to_ready(c.get("slug", ""))
```

**AI 자동 PASS 경로 존재 여부**:
- **없음**. `promote_to_ready()`는 항상 수동 호출만 가능.
- `promote_to_ready()` 내부에서 `source != app_factory` 계산기는 거부 (line 174-175).
- 자동 PASS 우회 경로: 없음. "AI 자동PASS 금지" 원칙이 코드 레벨에서 지켜짐.

**Phase3-2 실제 상황**:
- 대시보드 버튼이 아닌 Claude Code가 직접 `promote_to_ready()` 호출함.
- 즉, "사람이 버튼을 눌러야 한다"는 UI 게이트는 있지만, CLI에서 우회 가능한 상태.
- 단, CLI 우회도 `promote_to_ready()` 함수를 통하므로 `source != app_factory` 보호는 유지됨.

---

### 1-6. Build 트리거

**`_rebuild_site.py` 대시보드 트리거**: **없음**

현재 대시보드에서 제공하는 빌드 관련 버튼:

| 버튼 | 동작 | 한계 |
|---|---|---|
| `📥 파일 저장` | 개별 계산기 3파일을 `data/workspace/<slug>/`에 저장 | _site 전체 재빌드 아님 |
| `💾 로컬 저장` (사이트 페이지) | `data/workspace/_site/`에 site_generator 결과 저장 | 계산기 파일 미포함 |
| 없음 | `_rebuild_site.py` 전체 실행 | — |

> `_rebuild_site.py`는 9개 계산기 전체 + 사이트 페이지를 빌드하는 스크립트이며, 현재 터미널에서 수동 실행만 가능. 대시보드에 Build 버튼 없음.

---

### 1-7. Deploy 트리거 및 안전장치

**대시보드의 `🚀 배포` 버튼**:
- `GH.deploy_app()` 호출 → **GitHub API PUT** 방식 (git push 아님)
- `GITHUB_TOKEN` 미설정 시 비활성화 (현재 Production 환경에서 설정 여부 미확인)
- 동작: 개별 계산기 파일 3개를 GitHub API로 특정 저장소에 직접 업로드

**이것은 현재 Production 배포 경로와 다름**:

| 구분 | 대시보드 배포 버튼 | 현재 Production 경로 |
|---|---|---|
| 방식 | GitHub API PUT (파일별) | git push → GitHub Actions |
| 대상 저장소 | `cfg.GITHUB_REPO` (별도 저장소) | `calcmate/calcmate` (현재 저장소) |
| 빌드 | 없음 (파일 직접 업로드) | `deploy.yml` Actions |
| 검증 4단계 | 없음 | commit → push → Actions 성공 → 실사이트 확인 |

**안전장치 현황**:
- 대시보드 배포 버튼: `GITHUB_TOKEN` 없으면 비활성화 (한 단계 보호)
- 배포 전 "이 배포가 실제 Production에 영향을 주는지" 확인 단계: **없음**
- 배포 성공/실패 여부만 표시, 실제 사이트 URL 응답 확인: **없음**

---

### 1-8. 기존 App Factory 4개 결정사항과의 정합성

| 결정사항 | 코드 현황 | Phase3-3 재검토 필요 여부 |
|---|---|---|
| **① Tier 선택 UI**: 사람이 선택 | ✅ 라디오 버튼 구현됨 (line 2011) | 불필요 (정합) |
| **② READY 전환 후 index/sitemap 카드 표시** | ✅ promote_to_ready → 재빌드 후 반영 | 불필요 (정합) |
| **③ legal_master 완전 수동** | ✅ `reviewer_expectation: []` 빈 배열 유지 | 불필요 (정합) |
| **④ CalcMate 정적사이트 포함** | ✅ READY 전환 후 `_rebuild_site.py`로 반영 | 불필요 (정합) |

4개 결정사항 모두 현재 코드와 정합. Phase3-3 설계에서 재검토 불필요.

---

### 1-9. Tier1(법령형) 계산기와의 경계

**현재 상태**:
- App Factory UI에서 Tier1 선택 가능 (라디오 버튼)
- Tier1 선택 시 info 메시지: "계산 로직 + legal 근거 모두 사람이 검증해야 합니다"
- generate_app() 프롬프트에 Tier1 힌트 포함: "법령/조건분기/복잡 계산"

**실제 한계**:
- `generate_app()`이 생성하는 formula는 산술 표현식만 가능 (단순 사칙연산)
- 기존 Tier1 계산기(퇴직금/실업급여/연말정산 등)는 슬러그별 하드코딩 로직 (`_compute_js()`의 date_based 분기 등)
- Tier1을 App Factory로 생성하면 formula가 법령 로직을 정확히 표현하지 못함

**Phase3-3 설계 방향**:
- 대시보드 제작센터는 **Tier2-A 전용**으로 설계하는 것이 현실적
- Tier1은 "생성 불가" 또는 "운영자가 코드에서 직접 구현"으로 분리 유지
- 같은 UI 흐름을 공유하는 것은 위험 (Tier1 AI 생성 결과를 그대로 PASS하면 법령 오류 발생 가능)

---

### 1-10. 기술적 제약/리스크

**AI 실시간 호출 가능 여부**:
- ✅ 이미 구현됨: `_chat()` → `make_provider()` → `build_provider()`
- 모델 체계: GPT-4o (orchestrator/writer/review), Claude Sonnet 4.6 (code), Gemini 2.5 Flash (research/image)
- 동기 호출 + `st.spinner()` 블로킹 방식 (수십 초 대기 중 UI 멈춤)
- 비동기 처리 없음 → generate_app() 전체(4단계) 완료까지 사용자 대기

**API 비용**:
- BudgetTracker 연동됨 (`record(model, tokens)`)
- generate_app() 1회: orchestrator(800) + code(4000) + writer(1500) + image(400) ≈ 6700 토큰 상한
- suggest_idea() 1회: orchestrator(400) 토큰

**Registry v3 오염 리스크**:
- `promote_to_ready()`: `source != app_factory` 검사로 기존 8개 계산기 보호 ✅
- `_write_registry_v3()`: `_CATEGORY_AF_YAML_MAP`에 없는 카테고리는 `etc_af.yaml` 폴백
- 오염 가능 지점: slug 중복 저장 (현재 방어 로직 확인 필요)

```python
# app_factory.py save_app() line 428~509
# slug 중복 방어: DB에서 중복 체크 → CalculatorRepository.create()가 처리
# v3 Registry: _write_registry_v3()가 기존 entry를 slug로 덮어씀 (중복 slug면 기존 데이터 손실)
```

> **리스크**: 동일 slug로 두 번 save_app() 호출 시 v3 Registry entry가 덮어써짐. 현재 대시보드에서 명시적 중복 확인 UI 없음.

---

## 2. 결론 5가지 (①~⑤)

---

### ① 현재 vs 목표 격차표 (8단계)

| 목표 단계 | 목표 내용 | 현재 상태 | 격차 |
|---|---|---|---|
| **① 계산기 이름/기본정보 입력** | 이름만 입력하면 나머지 자동 | 이름+Tier+slug 수동 필수 | **부분 자동** |
| **② AI 자동분석** | Tier판정/입출력/공식/SEO/FAQ 자동 제안 | 공식/SEO/FAQ 자동 ✅, Tier 판정 ❌ | **부분 자동** |
| **③ 자동 QA** | formula 검증 + HTML 요소 검증 자동 | formula 검증 ✅, HTML 요소 검증 ❌ | **부분 자동** |
| **④ 검토 필요 항목 표시** | 법령/세율/계산기준 자동 추출 표시 | HOLD 배지만 있음, 항목 추출 없음 | **없음** |
| **⑤ PASS 게이트** | 사람이 명시적으로 버튼 클릭 | 대시보드 버튼 있음 ✅ | **완료** |
| **⑥ READY** | HOLD → READY 전환 | promote_to_ready() 구현 ✅ | **완료** |
| **⑦ Build** | _rebuild_site.py 자동 트리거 | 수동 터미널 실행만 가능 | **수동** |
| **⑧ Deploy** | git push → Actions → calcmate.kr | 수동 터미널 실행만 가능 | **수동** |

---

### ② 가장 시급한 보강 지점

**순위 1 — ④ 검토 필요 항목 표시**: 현재 완전히 없음

현재는 HOLD 상태 계산기에 "검증하세요"는 있지만 **무엇을**이 없다. 
운영자가 검토해야 할 사항을 스스로 알아내야 하며, Phase3-2에서도 HOLD-1(전월세전환율) 문제를 Claude Code가 별도 연구로 발견했다. 
이 기능이 없으면 "사람이 PASS 버튼을 눌렀다"가 "진짜 검토했다"를 보장하지 않는다.

**순위 2 — ⑦ Build 트리거 부재**: `_rebuild_site.py`를 대시보드에서 실행 불가

READY 전환 후 실제 사이트에 반영하려면 터미널을 열어야 한다. PASS 버튼을 누른 운영자가 다음에 뭘 해야 하는지 대시보드에서 안내받지 못한다.

**순위 3 — ③ HTML 출력 요소 자동 QA**: Phase3-2에서 발견된 버그 유형

formula dict 모든 출력이 HTML에 정상 생성되는지 검증하는 자동화 QA가 없다. 현재 `generate_app()`은 formula 수식 검증만 하고 HTML 요소 검증은 하지 않는다.

---

### ③ AI 자동분석 파트의 현실성

**Tier 판정 AI 자동화 — 안전하지 않음**

AI(GPT-4o)가 "이 계산기는 Tier2입니다"라고 판단하는 기능을 추가할 수 있지만:
- 날짜 계산이 필요한지 여부를 AI가 정확히 판단하기 어려움 (예: "복무기간 계산" → Tier2-B인지 AI가 모를 수 있음)
- 법령 구간별 요율 계산(Tier1)을 Tier2로 잘못 분류할 위험

> **권고**: Tier 판정은 **사람 선택 유지** (AI가 참고 제안은 가능하나 최종 확정은 사람)

**계산식 AI 자동 제안 — 조건부 안전**

현재 generate_app()이 이미 공식을 자동 생성함. 단, 다음 조건에서만 신뢰 가능:
- 법령 근거가 명확히 알려진 간단한 공식 (3.3% 원천징수 등)
- 사람이 생성된 공식을 반드시 검토하는 경우

> **권고**: AI 공식 초안 제안 → 사람 검토/수정 → PASS 게이트 통과. 현재 구조 유지.

**SEO/FAQ AI 자동 생성 — 안전**

현재 generate_app() 내에서 이미 자동 생성됨. SEO/FAQ는 계산 정확성과 무관하므로 AI 자동화 안전.

---

### ④ Phase3-3 설계 범위 제안

**이번 설계에서 다룰 항목** (현실적, 구현 가능):

| 항목 | 이유 |
|---|---|
| ④ 검토 필요 항목 자동 추출 표시 | 가장 시급. 계산기 유형 분석으로 추출 가능 |
| ⑦ Build 버튼 (`_rebuild_site.py` 트리거) | 간단한 subprocess 호출로 구현 가능 |
| ① Tier 자동 제안 (비강제) | AI 제안 + 사람 최종 선택 방식으로 개선 |
| ③ HTML 출력 요소 QA | generate_calculator() 호출 후 `id="out_*"` 검증 추가 |

**다음 Phase로 미뤄야 할 항목**:

| 항목 | 이유 |
|---|---|
| ⑧ Deploy 완전 자동화 (git push 포함) | 배포 4단계 검증 없이 자동화하면 위험. 반드시 사람이 최종 확인해야 함 |
| Tier1 계산기 App Factory 지원 | formula dict로 표현 불가한 복잡한 로직. 별도 설계 필요 |
| Tier2-B (날짜형) App Factory 지원 | `docs/TIER2_B_DESIGN.md` 설계 완료 후 별도 구현 |
| 비동기 AI 호출 (실시간 스트리밍) | Streamlit 아키텍처 변경 필요 |

---

### ⑤ HOLD 항목 (근거 없이 넘어가면 안 되는 판단 지점)

**HOLD-A: 검토 체크리스트 생성 기준**

"검토 필요 항목 자동 추출" 기능을 만들 때, 체크리스트 생성 기준을 어떻게 정의할 것인가? AI가 생성한 체크리스트 자체가 누락될 수 있으므로, 최소 기준(법령 근거 확인, 세율 변경 여부, 계산 공식 검증)은 템플릿으로 고정하고 AI는 추가 항목만 제안해야 한다.

**HOLD-B: Build 버튼 권한 설계**

대시보드에서 `_rebuild_site.py`를 트리거하면 9개 계산기 전체가 재빌드된다. HOLD 상태 계산기가 섞여 있을 때 의도치 않게 빌드되는 일이 없는지 확인 필요 (`_rebuild_site.py` 이미 HOLD 필터링 내장 → 문제없음 확인됨).

**HOLD-C: Deploy 대시보드 자동화 범위**

대시보드에서 git push까지 포함한다면, "배포 완료 4단계"(commit → push → Actions 성공 → 실사이트 HTTP 200) 중 몇 단계까지 자동 검증할 것인가? 이를 건너뛰면 "배포했다고 표시됐지만 실제로 안 됐다"는 상황이 발생한다. Phase3-3 설계에서 명시적으로 결정해야 한다.

**HOLD-D: slug 중복 방어**

동일 slug로 save_app()을 두 번 호출하면 v3 Registry entry가 덮어써짐. 현재 DB는 CalculatorRepository가 보호하지만 v3 YAML은 무조건 덮어씀. Phase3-3 설계에서 slug 중복 시 경고/거부 로직 명시 필요.

---

## 3. 현재 vs 목표 격차표 (요약)

```
최종 목표 흐름                    현재 구현 상태
─────────────────────────────────────────────────────────────────
[계산기 이름/기본정보 입력]    →  이름+Tier+slug 3개 수동 필수
                                  카테고리/설명은 AI 제안 가능
                                  상태: 부분 자동

[AI 자동분석]                 →  공식/SEO/FAQ 자동 생성 ✅
                                  Tier 판정: 사람 선택 (AI 없음)
                                  HTML 요소 QA: 없음
                                  상태: 부분 자동

[자동 QA]                     →  formula 수식 검증 ✅
                                  HTML 출력 요소 검증: 없음
                                  실제 URL 200 확인: 없음
                                  상태: 부분 자동 (불완전)

[⚠️ 검토 필요 항목 표시]       →  HOLD 배지만 있음
                                  "무엇을 확인해야 하는지": 없음
                                  법령/세율/계산기준 자동 추출: 없음
                                  상태: 없음 ← 가장 큰 격차

[검토] / [PASS 버튼]           →  대시보드 버튼 존재 ✅
                                  AI 자동 PASS 경로: 없음 ✅
                                  상태: 완료

[READY]                        →  promote_to_ready() 구현 ✅
                                  source != app_factory 보호 ✅
                                  상태: 완료

[Build]                        →  대시보드 트리거: 없음
                                  수동 터미널 실행만 가능
                                  상태: 수동

[Deploy]                       →  대시보드 git push: 없음
                                  GitHub API PUT (별도 저장소): 있지만
                                  현재 Production 경로(git→Actions)와 다름
                                  상태: 수동
─────────────────────────────────────────────────────────────────
```

---

*조사 기준: 2026-08-09 / 기준 커밋 b54c684 / 코드 읽기 전용 / 실행 없음*
