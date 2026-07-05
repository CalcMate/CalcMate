# SalaryMate 계산기 글 품질 기준서 v1.2

> 작성일 2026-07-04 · v1.1 대비 변경: Gate 설정값 분리, Gate별 수정범위 3단계
> (코드수정/부분재생성/전체재생성), failed_rules 우선순위, PASS/WARN/REWRITE 3단계,
> 품질 데이터 DB 저장 규칙 추가.
> 목적: Writer Prompt 개편 / 자동 품질검수 / 재생성 루프가 공유할
> **단일 기준(single source of truth)**.

---

## 0. 배경

- 시스템(엔진/CRUD/Repository/history)은 완성됐고 병목이 **콘텐츠 품질**로 이동함.
- v1.1까지 "Gate→Score→Rewrite 흐름"과 "실패 사유 구조화(Rewrite Contract)"를 정립.
- v1.2는 **운영 관점 보강**: 기준값을 코드에 박아넣지 않고 설정으로 분리, 재생성 비용을
  줄이는 수정범위 구분, 품질 데이터를 나중에 분석 가능한 형태로 축적하는 규칙.

---

## 1. 적용 범위

- 대상: `writer.py`가 생성하는 계산기 소개글 전체(신규 발행 + 재생성)
- 비대상: 계산기 앱 자체(UI/계산로직) 품질 — `app_generator`/formula 영역
- 검수 주체: `calculator_reviewer.review_calculator()` (GPT, `CALC_REVIEW_PROVIDER`)

---

## 2. 전체 흐름 — Gate → Score → Rewrite

```
생성 (writer)
   ↓
자동 Gate (코드, GPT 호출 없음)
   ↓ FAIL                          ↓ PASS
수정범위 판정(§6) → 처리          AI Score (GPT)
                                      ↓
                          90+   PASS   → 발행
                          80~89 WARN   → 발행 (개선 후보로 별도 기록, §8)
                          79↓   REWRITE → Rewrite Contract 생성(§9) → 재생성
```

**핵심 원칙**: 자동 Gate를 통과하지 못하면 GPT를 호출하지 않는다. Gate는 결정론적 판정만,
Score는 맥락 판단이 필요한 항목만 담당한다.

---

## 3. Gate 기준값 — 설정으로 분리 (하드코딩 금지)

이 문서는 **정책**을 정의하고, 실제 수치는 `config.yaml`에서 읽는다. 문서의 숫자는
"기본값" 의미이며 운영 중 조정 시 이 문서가 아니라 설정을 바꾼다.

```yaml
QUALITY_GATE:
  MIN_LENGTH: 1800
  MAX_LENGTH: 2500
  MIN_H2: 5
  MAX_H2: 7
  MIN_FAQ: 5
  MIN_EXAMPLES: 2
  CTA_COUNT: 1
  MIN_INTERNAL_LINKS: 2

QUALITY_SCORE:
  PASS_THRESHOLD: 90      # 이상 = PASS
  WARN_THRESHOLD: 80      # 80~89 = WARN (발행하되 개선후보)
  # 79 이하 = REWRITE

QUALITY_RETRY:
  CRITICAL_RETRY_LIMIT: 2   # Critical 사유로 연속 N회 실패 시 운영 알림
```

> 실제 config 키 이름/위치는 작업지시서 A에서 기존 `config.yaml` 구조 조사 후 확정.

---

## 4. Gate 목록 (코드 판정, GPT 호출 전 필수 통과)

| # | Gate 항목 | 기준(기본값) | 수정범위 |
|---|-----------|------|-----------|
| G1 | 본문 길이 | MIN_LENGTH~MAX_LENGTH | 부분재생성 |
| G2 | H2 개수 | MIN_H2~MAX_H2 | 부분재생성 |
| G3 | FAQ 개수 | MIN_FAQ 이상 | 부분재생성 |
| G4 | 계산 예시 최소 개수 | MIN_EXAMPLES 이상 (존재 여부만, 품질은 S1) | 부분재생성 |
| G5 | 내부링크 | `href="#"` 0개, MIN_INTERNAL_LINKS 이상 | 전체재생성 (§7 구조규칙 위반, Critical) |
| G6 | CTA | 정확히 CTA_COUNT회 | **코드수정** |
| G7 | AI 문체 금지표현 | §5 목록 매칭 0건 | 부분재생성 |

---

## 5. AI 문체 금지 표현 (패턴 수준 관리)

- 정형화된 오프닝("~에 대해 알아보겠습니다" 류)
- 근거 없는 확신형 결론("이제 완벽하게 이해하셨을 것입니다" 류)
- 챗봇 특유의 목록 나열식 결론 반복
- 수치 없이 얼버무리는 문장("다양한 조건에 따라 달라질 수 있습니다" 단독 사용)

> 목록은 계속 확장 — 별도 `AI_STYLE_BLOCKLIST` 설정으로 관리.

---

## 6. Gate 실패 시 수정범위 3단계

Gate 실패를 전부 "재생성"으로 뭉뚱그리지 않는다. GPT 호출 비용/속도에 직결됨:

| 단계 | 정의 | 해당 Gate | AI 호출 |
|------|------|-----------|---------|
| **코드수정** | AI 없이 코드만으로 해결 | G6(CTA 중복 — 하드코딩 CTA 블록 제거, Part 3 전례 그대로) | 없음 |
| **부분재생성** | 해당 섹션만 AI로 다시 생성 (전체 재작성 아님) | G1, G2, G3, G4, G7 | 있음(소규모) |
| **전체재생성** | writer 처음부터 재실행 | G5(구조적 결함, Critical) | 있음(전체) |

```
Gate Fail
   ↓
코드수정 가능? → 예: 코드에서 즉시 수정, 재검사
              → 아니오 ↓
부분재생성 대상? → 예: 해당 섹션만 AI 재호출, 재검사
                → 아니오 (G5) ↓
전체재생성 (writer 재실행)
```

> "부분재생성"의 실제 구현 방식(섹션 단위로 AI를 다시 부르는 인터페이스가 현재
> writer에 있는지)은 작업지시서 A/B에서 조사 후 확정 — 없으면 이번 범위에서는 전체재생성으로
> 통일하고 부분재생성은 v1.3 이후 최적화 과제로 미룰 수 있음.

---

## 7. AI Score — Gate 통과 후에만 채점

| # | 항목 | 판정 방식 |
|---|------|-----------|
| S1 | 계산 예시 품질 | 실제 formula/`_compute_js`와 일치하는지, 서로 다른 조건 2개인지 |
| S2 | 법적 근거 정확성 | §8 출처 표기 규칙 충족 여부 |
| S3 | 최신 기준 반영 | 금액·기간 기준에 적용 연도 명시 여부 |
| S4 | 문체 자연스러움 | Gate G7 이외의 부자연스러움 |
| S5 | 중복 콘텐츠 유사도 | 동일 계산기 기존 발행글 대비 (기준치는 후속 작업에서 확정) |
| S6 | 사용자 검색 의도 충족 | "바로 계산 → 예시 → 주의사항 → FAQ" 구조 대비 법설명 비중 과다 여부 |

---

## 8. 점수 3단계 — PASS / WARN / REWRITE

| 점수 | 상태 | 처리 |
|------|------|------|
| 90 이상 | **PASS** | 발행 |
| 80~89 | **WARN** | 발행하되 "개선 후보" 목록에 별도 기록 (§10 DB 저장) — 향후 일괄 개선 작업 대상 |
| 79 이하 | **REWRITE** | §9 Rewrite Contract 생성 → 재생성 |

> 기존 `PASS_THRESHOLD=80` 단일 기준에서 90/80 2단계로 세분화. WARN 상태는 즉시 조치
> 대상은 아니지만 데이터로 축적해 나중에 "어떤 계산기가 계속 WARN인지" 분석 가능하게 함.

---

## 9. Rewrite Contract — Reviewer ↔ Writer 계약 형식

```json
{
  "result": "REWRITE",
  "score": 71,
  "severity": "major",
  "failed_rules": [
    {"gate": "G5", "detail": "href=\"#\" 잔존", "priority": 1},
    {"gate": "S2", "detail": "법적 근거 없음 — 관련 법령 미언급", "priority": 2},
    {"gate": "G3", "detail": "FAQ 3개 → 최소 5개 필요", "priority": 3}
  ]
}
```

- `failed_rules`는 Gate/Score 실패를 동일 배열에 담되, **`priority` 필드로 처리 순서
  지정**(Critical 항목이 항상 1순위, 이후 severity·영향도 순).
- writer 재생성 프롬프트는 이 배열을 우선순위 순서 그대로 "다음 사항을 순서대로
  보완하라"는 지시로 주입.
- PASS/WARN 시: `result: "PASS"` 또는 `"WARN"`, `score`만 반환, `failed_rules` 생략
  (WARN인데 개선 여지가 있다면 `failed_rules`에 Minor 항목만 참고용으로 포함 가능 —
  단 이 경우 재생성 트리거로 사용하지 않음).

---

## 10. 품질 데이터 저장 규칙 (신규 — 향후 가장 큰 자산)

Reviewer 결과를 article 레코드에 저장(history와는 별도 목적 — history는 이벤트 로그,
이건 품질 분석용 데이터):

```
quality_score       (숫자, 최근 채점값)
quality_status       (PASS/WARN/REWRITE)
quality_failed_rules (JSON 문자열, 최근 failed_rules 배열)
quality_review_model (예: gpt-4o — 어떤 모델이 채점했는지)
quality_reviewed_at  (타임스탬프)
```

- 이 필드들이 쌓이면 "FAQ 부족으로 계속 떨어지는 계산기는?", "어떤 계산기가 항상
  WARN인가?" 같은 분석이 가능해짐 — Phase 3(품질 데이터 분석)의 기반.
- **알려진 제약 재확인**: `sheets_adapter.insert()`는 헤더 자동추가 미지원(`update()`는
  됨) → 신규 필드는 마스터_DB 시트 헤더 수동 추가 필요(3차/4차와 동일 패턴).

---

## 11. §7 내부링크 구조 규칙 (Critical, G5와 동일)

- 문제: writer가 "관련 계산기" 섹션을 직접 작성 + `internal_link_engine`이 별도 삽입 →
  중복 및 `href="#"` 잔존.
- **규칙**: writer 프롬프트에서 관련 계산기 섹션 작성 자체를 제거. 100%
  `internal_link_engine`(`is_active()` 기반)에 위임.
- G5 위반은 Critical — §12 우선순위의 최상위, 전체재생성 대상.

---

## 12. 실패 우선순위 — Critical / Major / Minor

| 등급 | 항목 예시 | 대응 |
|------|-----------|------|
| **Critical** | 계산 결과 오류, 법적 근거 오류, `href="#"` 잔존(G5), CTA 중복(G6) | 즉시 조치(수정범위는 §6 기준), 반복 실패 시 운영 알림 |
| **Major** | FAQ 부족, 글자수 부족, 계산 예시 개수 부족 | 부분재생성 |
| **Minor** | 문체 어색함, 표현 반복, SEO 세부사항 | WARN 상태에서 감점만, 즉시 재생성 강제 안 함 |

**운영 트리거**: Critical 사유로 `CRITICAL_RETRY_LIMIT`(기본 2)회 연속 REWRITE 후에도
해소 안 되면 자동 재생성 중단 + Telegram 알림. 정확한 N값과 알림 배선은 작업지시서 C에서
기존 Telegram 게이팅 구조(`TELEGRAM_EVENTS`) 조사 후 확정.

---

## 13. 자동검수 vs AI 판정 역할 분리 (요약)

| 구분 | 항목 | 이유 |
|------|------|------|
| **자동 Gate** | G1~G7 | 결정론적 판정, GPT 호출 전 필터 |
| **AI Score** | S1~S6 | 맥락 이해 필요, Gate 통과 후에만 호출 |

---

## 14. 기존 구조와의 정합

기존 `review_calculator`는 6개 항목 평균 + 0~100 클램프. 이 문서의 Gate(7) + Score(6)
체계를 기존 `DIMENSIONS`에 어떻게 매핑할지는 작업지시서 A에서 실제 코드 조사 후 확정.

---

## 15. 보류 항목 (v1.3 이후 — 지금 범위에 넣지 않음)

### (A) 계산기 난이도 분류 (simple/normal/complex)

분류 기준(입력 필드 수, 예외 조건 수, 연도별 변경 여부, 법령 의존도) 미정 상태로 3단계를
먼저 만들면 모호한 카테고리가 하나 더 생기므로 보류.

### (B) 계산 예시 자동 생성 (엔진 기반)

"계산 엔진이 숫자를 생성하고 AI는 설명만 작성"으로 파이프라인을 바꾸는 별도 Phase 2 작업.

### (C) S6(사용자 의도 충족)의 게이트 승격

계산 섹션 vs 법설명 섹션 글자수 비율 자동측정이 가능하면 AI Score에서 Gate로 이동 검토.

### (D) "부분재생성"의 실제 구현

writer에 섹션 단위 재생성 인터페이스가 없으면 v1.3까지는 부분재생성 대상 Gate도
전체재생성으로 통일 — 작업지시서 B에서 현재 writer 구조 조사 후 결정.

---

## 16. 버전 이력

| 버전 | 일자 | 변경 |
|------|------|------|
| v1.0 | 2026-07-04 | 최초 작성 |
| v1.1 | 2026-07-04 | Gate→Score→Rewrite 흐름, Rewrite Contract, Critical/Major/Minor, 출처표기 규칙 |
| v1.2 | 2026-07-04 | Gate 설정값 분리, 수정범위 3단계(코드수정/부분재생성/전체재생성), failed_rules priority, PASS/WARN/REWRITE 3단계, 품질데이터 DB 저장 규칙 |

---

## 17. 다음 단계 (이 문서 승인 후)

1. **작업지시서 A**: `calculator_reviewer.py`의 실제 `DIMENSIONS`/`PASS_THRESHOLD` 조사 →
   §14 매핑표 작성 → Gate(G1~G7)를 GPT 호출 전 사전필터로 코드 분리 → §3 config 키를
   실제 `config.yaml`에 맞게 확정 → Rewrite Contract(§9) JSON 스키마로 반환값 변경 →
   §10 품질데이터 필드 저장 배선(시트 헤더 수동추가 필요)
2. **작업지시서 B**: writer 프롬프트 개편 — §11 섹션 제거, §5 금지패턴 반영,
   `failed_rules`를 priority 순으로 재생성 프롬프트에 주입 → 부분재생성 가능 여부 조사(§15-D)
3. **작업지시서 C**: G6 코드수정 로직 + Critical 반복실패 Telegram 알림 배선
4. (Phase 2, 별도) 계산 예시 엔진 기반 자동생성
5. (Phase 3, 별도) 품질 데이터 분석 대시보드 — §10 데이터 축적 이후 가능
