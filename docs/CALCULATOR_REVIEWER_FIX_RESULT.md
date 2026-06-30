# CALCULATOR_REVIEWER_FIX_RESULT.md

> 계산기 AI 검수(Calculator Reviewer) 수정 작업 결과 정리 · 2026-06-30
> 원칙: 작업별 현황보고 → 승인 → 변경 게이트. 코어(파이프라인/Adapter) 무변경.

---

## 1. 문제 원인

### ① 자기검수 구조 (모델 배정)
- `calculator_reviewer.review_calculator()`가 `build_provider_for_role("review", cfg)`를 호출.
- `ai_provider.py`에서 `"review"` 역할은 **flat 키 `EDITOR_PROVIDER`/`MODEL_EDITOR`** 를 읽음(= `claude-sonnet-4-6`).
- 계산기 생성도 Claude(`AI_ROLES.code`) → **"Claude 생성 → Claude 검수"(자기검수)** 구조.
- ⚠️ 지시서 초기 전제(`AI_ROLES.review` 수정)는 **무효**였음: reviewer는 `AI_ROLES.review`를 참조하지 않음(주석에 `# MODEL_EDITOR` 명시). 또한 `MODEL_EDITOR`는 블로그 `editor.py`와 **공유** → 그대로 바꾸면 블로그 검수까지 변경됨.

### ② total 정규화 버그
- `review_calculator()`가 GPT가 반환한 `total`을 **범위 검증 없이 그대로 사용**.
- GPT가 0~100 대신 합산형 `total`(예: 220, 120)을 반환 → **본문 0자 계산기가 부당하게 PASS**.
- 결과적으로 PASS 비율이 거품(실측 80%가 무의미).

### ③ 시드 멱등성 실패 → 본문 유실
- 본문 0자(연차수당/실업급여/4대보험)의 진짜 원인.
- **시드가 본문을 덮어쓴 게 아님**: `CalculatorRepository.create()`는 새 id로 **insert**(미덮어쓰기).
- 실제 메커니즘: **calculators 시트 탭이 비워지거나 새로 생성된 뒤**(`sheets_adapter`가 없는 탭을 빈 탭으로 자동 생성 + `provision()`이 새 스프레드시트 생성), `get_all()`이 빈 결과 → 시더가 **본문 없는 5행을 새로 채움** → 이후 주휴수당/퇴직금만 재생성되어 본문 회복, 나머지 3개는 0자로 잔존.
- ⚠️ 반증된 가설: **sqlite/sheets 백엔드 불일치 아님** — `DB_ADAPTER`는 일관되게 `sheets`(env 미설정·코드가 env 안 읽음·sqlite 파일 없음).

---

## 2. 수정 내역 (커밋별)

| 커밋 | 제목 | 무엇을 고쳤나 |
|------|------|----------------|
| `02ade00` | 계산기 검수를 전용 키로 GPT 분리 | 계산기 검수만 GPT로 분리(블로그 editor·code 생성=Claude 유지). `MODEL_EDITOR` 공유 문제 회피 위해 **전용 키** 신설 |
| `bdac756` | total을 항목 평균으로 정규화 + 0~100 클램프 | GPT raw total(범위초과) 신뢰 제거 → 항상 6개 항목 평균으로 산출 후 0~100 클램프 |
| `07eae80` | 시더를 slug 기준 upsert로 변경(콘텐츠 보존) | `upsert_by_slug` 추가(기존 비어있지 않은 필드 보존) + 시더 2곳 `create→upsert_by_slug`. 재시드 시 본문 유실 방지 |

> 보조: 작업 전 체크포인트 커밋 `0625b84`.

---

## 3. 변경된 파일 목록과 위치

| 파일 | 변경 | 커밋 |
|------|------|------|
| `config/config.yaml` | `CALC_REVIEW_PROVIDER: openai`, `CALC_REVIEW_MODEL: gpt-4o` 신규(MODEL_EDITOR_FALLBACK 아래) | `02ade00` |
| `modules/calculator_reviewer.py` | import에 `build_provider` 추가(line 15) · provider 선택 2줄 교체(line 55~56, 전용 키 직접 읽기) | `02ade00` |
| `modules/calculator_reviewer.py` | `total` 정규화(line 61~64: GPT raw total 무시, 항목 평균 + `max(0,min(100,…))`) | `bdac756` |
| `repositories/calculator_repository.py` | `get_by_slug()` + `upsert_by_slug()` 신규(create 아래) | `07eae80` |
| `modules/calculator_seeder.py` | `repo.create(` → `repo.upsert_by_slug(`(line 48) | `07eae80` |
| `modules/calculator_seed.py` | `repo.create(` → `repo.upsert_by_slug(`(line 120) | `07eae80` |

**무변경(의도적 유지):** `review_calculator` 채점 구조/`DIMENSIONS`/`PASS_THRESHOLD`(80) · `auto_review_and_fix`/`_rewrite` 루프 · `create/save/update` · `editor.py`(블로그 검수) · `AI_ROLES.code`(Claude 생성) · 12단계 파이프라인 · Adapter.

---

## 4. 검증 결과

### 모델 전환 검증
- BudgetTracker `by_model`: `gpt-4o` 오늘 신규 비용 발생, `claude-sonnet-4-6` 미증가 → **계산기 검수=GPT 확정**, 블로그 editor=Claude 유지 확인.

### total 정규화 검증
- 재검수 시 **범위초과(>100) 0건**, 빈 본문 계산기가 정상적으로 낮은 점수→REWRITE.

### 시드 upsert 검증
- 재시드 실행 → **행수 5 불변(중복 0)**, 주휴수당 1998→1998 · 퇴직금 2921→2921 **본문 보존**.
- `upsert_by_slug` 직접 테스트: 본문 있는 slug에 `article_content:''` 전달해도 **1998자 유지**.

### 5종 계산기 최종 점수표
| 계산기 | 본문 | review_status | score | 비고 |
|--------|------|---------------|-------|------|
| 주휴수당 | 1998자 | NEEDS_REVIEW | (기존) | 기존 본문 유지(재생성 안 함) |
| 퇴직금 | 2921자 | NEEDS_REVIEW | (기존) | 기존 본문 유지 |
| 연차수당 | 2701자 | **AUTO_APPROVED** | 80 | 0자→복구 |
| 실업급여 | 2571자 | NEEDS_REVIEW | **53** | 0자→복구 후 재생성(2회)에도 미달 |
| 4대보험 | 2692자 | **AUTO_REWRITTEN** | 80 | 0자→복구(재생성 2회 후 통과) |

→ **본문 0자 3종 모두 복구**, 기존 2종 영향 없음.

---

## 5. 남은 이슈

- **실업급여 53점(NEEDS_REVIEW)** — 시스템 문제 아님, **콘텐츠 품질** 문제.
  - 상·하한/수급요건/피보험단위기간 등 기준이 복잡해 현재 생성 프롬프트로는 GPT 검수가 반복적으로 낮게(53~60) 평가. 일회성 재생성으로 개선 안 됨.
  - 추후 **프롬프트/기준 보강**으로 별도 처리 필요.
- (비치명적) 복구 중 **이미지 프롬프트 생성 간헐 실패**(Gemini 503 / JSON 파싱) — 본문/검수와 무관, `image_fallback` 처리.

---

## 6. 보류된 항목

- **제안 B: `provision()` 재호출 가드** — 본문 유실의 근본 원인(시트 탭/스프레드시트가 비워지거나 새로 생성되는 것)을 차단하는 작업.
  - 이번 범위에서 **제외**. 시트 비워짐 **재발 시 별도 작업지시**로 처리 예정.
  - 방향(참고): `provision()`이 `GOOGLE_SHEET_ID` 존재 시 새 시트 생성을 막거나, 시더/어댑터가 빈 탭 자동 생성과 데이터 유실을 구분하도록 가드.

---

> 작성: 2026-06-30 · 관련 커밋 `02ade00` / `bdac756` / `07eae80` (+ 체크포인트 `0625b84`)
