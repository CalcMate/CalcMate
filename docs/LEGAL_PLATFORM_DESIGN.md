# Legal Platform 설계 (Sprint A — 스키마/구조/연동 설계)

> 상태: **설계만** (프로덕션 코드/데이터 무변경). 실제 마이그레이션·로더 연동은 Sprint B 이후.
> 목표: 계산기 50~100개 + 자동 법령 갱신을 지탱하는 **법령 = 단일 진실 소스(SSOT)** 구조.

---

## 0. 결정 요약 (2026-07-11 확정)

- **키 단위 = 법령 조항 엔티티** (계산기 slug 아님). `legal_master`가 SSOT.
- registry의 계산기는 법령을 **복사하지 않고 `legal_refs`로 참조**한다.
- 법령 엔티티 ID는 사람이 읽는 **불변 slug**(`employment_insurance_act_70`).
- 처음부터 `version` / `revision_date` / `source_tier` / `impact` 포함.
- 기존 `legal_basis.draft.yaml`(7종)은 **마이그레이션 후 대체**. 1회 전체 재평가는 재평가 시스템이 흡수([[../../docs/QUALITY_REEVALUATION.md]]).

---

## 1. 3계층 구조

```
legal_master/{category}.yaml   ← 법령 조항 = 진실. 여러 계산기가 공유·참조
        ▲ legal_refs
registry/{category}.yaml       ← 계산기 정의(compute/labels) + legal_refs
        ▲
source_tier.yaml               ← 기관별 신뢰도(law.go.kr=tier1 …)
```

**관심사 분리:**
- `legal_master` = "법이 무엇을 말하는가"(law/article/rate/effective_date …).
- `registry` = "이 계산기는 무엇이고 어떤 법을 참조하는가"(slug/compute/legal_refs).
- `source_tier` = "그 법을 어디서 검증하는가"(공식 소스 신뢰도).

카테고리 파일 분할: `employment / tax / insurance / pension / labor / childcare / veterans / housing / subsidy`.
(현재 registry의 `category` 필드 "노무/급여","세금/정부혜택" 등을 이 영문 도메인에 매핑.)

---

## 2. 법령 엔티티 ID 규칙 (불변)

형식: `{law_snake}_{article_num}` — 소문자 snake_case, 평생 불변(법 개정돼도 ID 유지, 내용만 version up).

| 엔티티 ID | 법령 | 조항 |
|---|---|---|
| `employment_insurance_act_40` | 고용보험법 | 제40조 (구직급여=실업급여) |
| `employment_insurance_act_70` | 고용보험법 | 제70조 (육아휴직 급여) |
| `income_tax_act_137` | 소득세법 | 제137조 (근로소득 연말정산) |
| `labor_standards_act_55` | 근로기준법 | 제55조 (주휴수당) |
| `labor_standards_act_60` | 근로기준법 | 제60조 (연차) |

> 규칙: ID는 조항 세부(제70조의2 등)까지 구분이 필요하면 `_70_2`로 확장. 접미(항/호)는 필요할 때만.

---

## 3. legal_master 스키마

```yaml
# legal_master/employment.yaml
employment_insurance_act_70:
  # ── 식별/법령 ──
  law: 고용보험법
  article: 제70조
  authority: 고용노동부
  # ── 버전/유효 ── (자동 갱신 시스템의 축)
  version: "2026.01"           # 사람이 읽는 스냅샷 버전(연.월)
  effective_date: 2026-01-01   # 시행일
  revision_date: null          # 마지막 개정일(감지되면 채움)
  source_tier: tier1           # source_tier.yaml 참조(신뢰도·검증방법은 거기)
  verification:                # 엔티티별 검증 스냅샷(변경 감지용, §5)
    source_url: https://law.go.kr/...
    last_verified: 2026-07-05T03:00:00
    source_hash: sha256:ab12…  # 원문 해시 — 동일하면 개정 없음
    etag: null
  confidence: high
  # ── 수치(요율/상하한) ── 요율 자동 감지의 대상
  rate:
    ordinary_wage_pct: 80       # 통상임금 80%
    monthly_cap: 1500000        # 상한(원)
    monthly_floor: 700000       # 하한(원)
  # ── 계산 로직 참조(진실은 formula_engine, 여기선 '어느 수식이 이 법을 쓰는지'만) ──
  formulas: [childcare_leave_formula]
  # ── Writer/Reviewer 힌트: '법률 관련'만 (콘텐츠 힌트는 registry) ──
  writer_hint: >
    고용보험법 제70조에 따라 30일 이상 육아휴직 + 피보험단위기간 180일 이상 시
    육아휴직 급여 지급. 상하한·요율은 시행령에서 정하며 연도별로 바뀔 수 있으므로
    구체 금액 단정 대신 "요율/상한 기준"으로 서술.   # ← 법적 서술 규칙만, 글 구성/예시는 registry
  reviewer_hint:
    - 법령명(고용보험법)·조항(제70조) 언급
    - 상하한 금액을 확정적으로 단정하지 않음
  # ── 금지(법적 정확성) ──
  forbidden:
    articles: []               # 혼동 조항(정확 표기 시 차단)
    phrases: []                # 확정형 표현 등(오탐 방지 위해 개인 단정형만)
  # ── 교차참조 ──
  cross_reference: [employment_insurance_act_41]   # 피보험단위기간 등
  # (impact 없음 — §6: 역인덱스 조회 View. examples/faq 없음 — §4: 콘텐츠는 registry)
```

**필드 경계 원칙 — legal_master는 "법령"만 소유:**
- `rate`가 legal_master에 있는 이유: **요율 자동 감지**의 대상이자, 여러 계산기가 같은 요율을 공유하기 위함. 단 **계산 로직 자체(formula)의 진실은 `formula_engine`/코드**에 두고, legal_master는 "어느 수식이 이 법을 근거로 하는지"(`formulas`)만 가리킨다(로직 이중화 방지).
- `writer_hint`/`reviewer_hint`는 **법률 관련 서술 규칙만**(조항 인용/확정표현 금지 등). 글 구성·톤 같은 콘텐츠 힌트는 registry.
- **`examples`(계산 예시)·`faq`는 legal_master에 두지 않는다** → 같은 법(제137조)이라도 연말정산과 다른 계산기의 예시·FAQ는 완전히 다르므로 **계산기별 콘텐츠 = registry 소유**(§4). legal_master의 예시가 필요하면 그건 "조항 적용례"일 뿐 계산기 예시가 아님.
- **`impact` 필드 없음** → §6대로 역인덱스 조회(View).

---

## 4. registry 스키마 (단순화)

```yaml
# registry/childcare.yaml
육아휴직_급여_계산기:
  name: 육아휴직 급여 계산기
  category: childcare
  legal_refs: [employment_insurance_act_70]   # ← 법령은 여기 참조만
  compute_type: single
  validation_mode: formula
  formula_id: childcare_leave_formula
  field_labels: {}
  difficulty: complex
  writer_hint: >                # 계산기 특화 힌트(선택). legal/global과 4단 합성
    육아휴직 사용 개월수·회사 지원 여부를 입력받아 예상 급여를 계산.
  # ── 콘텐츠(계산기별 — legal_master가 아니라 여기 소유) ──
  examples:                     # 이 계산기의 계산 예시(writer 주입 + reviewer 근거)
    - "예를 들어 통상임금 300만원, 6개월 육아휴직 → 상한 적용 = 1,500,000원 × 6"
  faq:                          # 이 계산기 고유 FAQ
    - {q: 회사 지원금이 있으면?, a: ...}
  related_slugs: [unemployment-benefit, ...]
```

- registry에서 **law/article/authority/forbidden 등 법령 필드 전부 제거** → `legal_refs`로 대체.
- **계산기별 콘텐츠(`examples`/`faq`)는 registry가 소유** — 같은 법이라도 계산기마다 예시·FAQ가 다르므로(§3 필드 경계 원칙).
- 기존 `legal_basis.draft.yaml`의 "registry v2 미러"(slug/compute/labels/content)가 이 registry로 승격.

---

## 5. source_tier.yaml + 엔티티별 검증 스냅샷

변경 감지 메타데이터는 **두 층**으로 나눈다(정규화):
- **tier 정의**(`source_tier.yaml`): host별 신뢰도·검증 방법 — 여러 엔티티가 공유하는 정적 메타.
- **엔티티별 스냅샷**(legal_master 엔티티): 그 조항을 마지막으로 조회했을 때의 hash/etag — 엔티티마다 다르므로 legal_master에 둔다.

```yaml
# source_tier.yaml — 기관별 신뢰도 + 검증 방법(환각 방지: 공식 데이터가 기준)
tier1:                          # 1차 공식 원문
  trust_score: 100
  verification_method: exact    # 원문 조항 정확 대조
  sources:
    - {host: law.go.kr,  name: 국가법령정보센터}
    - {host: nts.go.kr,  name: 국세청}
    - {host: moel.go.kr, name: 고용노동부}
tier2:                          # 공식 기관 해설/실무
  trust_score: 80
  verification_method: assisted # 해설 대조(보조)
  sources:
    - {host: kcomwel.or.kr, name: 근로복지공단}
    - {host: nhis.or.kr,    name: 국민건강보험공단}
    - {host: nps.or.kr,     name: 국민연금공단}
    - {host: easylaw.go.kr, name: 찾기쉬운 생활법령}
tier3:                          # 참고(검증 보조, 단독 근거 불가)
  trust_score: 50
  verification_method: reference
  sources:
    - {host: bokjiro.go.kr, name: 복지로}
```

**엔티티별 검증 스냅샷** — legal_master 엔티티에 추가되는 필드(§3 스키마에 포함):
```yaml
  source_tier: tier1
  verification:
    source_url: https://law.go.kr/...        # 실제 조회 URL
    last_verified: 2026-07-05T03:00:00
    source_hash: sha256:ab12…                # 조회 원문 해시(변경 감지 핵심)
    etag: "W/\"5f3-…\""                      # HTTP ETag(있으면 조회 절감)
    response_signature: null                  # 소스가 서명 제공 시
```

**검증 규칙(설계):**
- 엔티티 `source_tier`가 tier1이면 tier1 소스로만 verify. AI 생성값은 **항상 소스 대조 후에만** 채택.
- **매일 재조회 최소화**: 새벽 조회 시 ETag/Last-Modified로 먼저 확인 → 변화 없으면 원문 fetch·AI 판독 생략. 원문 fetch 시 `source_hash` 재계산 → 이전과 **동일하면 PASS(개정 없음)**, 다르면 `detect_revision` → `revision_date` 갱신 + `find_impacted` 트리거.

---

## 6. impact(영향도) — 저장값이 아니라 조회 결과(View)

> **impact는 저장 데이터가 아니라 조회 결과(View)이다.** legal_master에 `impact`를 **필드로 저장하지 않는다.**
> 관계(법령↔계산기)는 오직 registry의 `legal_refs` **한 곳에만** 존재한다. 이것이 진짜 SSOT다.

`impact`는 registry의 `legal_refs`를 **역인덱싱**한 런타임 조회로 만든다(캐시 파일도 두지 않는다 — 두면 동기화 붕괴 지점이 됨).

```
find_impacted(entity_id) = [slug for slug, r in registry if entity_id in r.legal_refs]
```
- **계산기 영향** = 위 역인덱스 결과(런타임 계산, 저장 안 함).
- **게시글 영향** = `find_impacted`로 얻은 slug들을 마스터_DB의 `wp_post_id`와 조인(발행 시 기록된 매핑에서 조회). 별도 저장 없음.
- 따라서 "법령 변경 → 영향 계산기/게시글 자동 탐색"은 **역인덱스 1함수(View)**로 성립하며, legal_master 엔티티에는 impact 관련 필드가 **아예 없다**(§3 스키마에서 제거됨).

---

## 7. Writer Layer 4단 합성

```
최종 writer 프롬프트 =
    global.writer            (공통 calculator_writer_prompt.txt — 문체/구조/포맷)
  + legal_master.writer_hint (참조된 각 legal_refs의 힌트, 법적 근거)
  + registry.writer_hint     (계산기 특화)
  + calculator.writer_hint   (개별 오버라이드, 있으면)
```
- 우선순위: 구체(individual) > registry > legal > global. 충돌 시 구체가 이김.
- 현재 `_legal_basis_block(calc)`가 하던 "법령 그대로 인용" 주입은 → `legal_refs → legal_master.writer_hint + forbidden` 합성으로 이관.
- reviewer도 동일하게 `legal_master.reviewer_hint + registry` 합성.

---

## 8. 로더 연동 (registry_loader 확장 방향 — Sprint B 구현)

현재: `load_registry() → slug→entry`(legal+registry 혼합).
변경: 2단 해석.
```
resolve(slug):
    r = registry[slug]                       # 계산기 정의
    laws = [legal_master[ref] for ref in r.legal_refs]
    return { **r, "_laws": laws }            # 계산기 + 참조 법령들
```
- 파이프라인(`_load_legal_basis`, `_check_g8`, `_quality_signature`, `_write_article`)은 이 `resolve(slug)` 하나만 알면 됨(단일 소스 유지).
- **G8**: 현재 slug→1개 legal. 변경 후 `_laws`(N개 조항) 각각을 검사(여러 조항 참조 대응).
- **품질 서명(`_LEGAL_SIG_FIELDS`)**: legal 필드가 `_laws`로 이동 → 서명은 `_laws`의 (law/article/rate/forbidden/writer_hint …) + registry(writer_hint) 조합으로 계산. **구조가 바뀌므로 마이그레이션 시 7종 서명 전부 변경 = 1회 전체 재도전**(재평가 시스템이 흡수, resolved 자동 정리).

---

## 9. 자동검증 인터페이스 (Sprint B 스텁 — 시그니처만)

```python
def fetch_official(entity: dict) -> str: ...
    # source_tier에 따른 공식 소스에서 조항 원문/요율 취득

def verify_entity(entity: dict) -> dict: ...
    # legal_master 값 vs 공식 소스 대조 → {ok: bool, mismatches: [...]}

def detect_revision(entity: dict) -> str | None: ...
    # 개정 감지 시 revision_date 반환(없으면 None)

def find_impacted(entity_id: str, registry: dict) -> list[str]: ...
    # legal_refs 역인덱스 → 영향 계산기 slug 목록

def propagate(entity_id: str) -> dict: ...
    # find_impacted → registry/본문/WP update 큐잉 + Telegram(무인 유지보수 훅)
```

---

## 10. 마이그레이션 전략 (Sprint B)

1. 기존 `legal_basis.draft.yaml` 7종 → (a) 법령 조항을 `legal_master/*.yaml` 엔티티로 추출, (b) 계산기 정의를 `registry/*.yaml`로, (c) `legal_refs` 연결.
2. `registry_loader.resolve()` 이중 조회로 교체(하위호환: 구 파일 없으면 legal_master 우선).
3. 품질 서명 1회 변경 → 6종 발행분 재도전. **재평가 시스템이 자동 재생성 + 옛 HOLD resolved 정리**. 대부분 재통과 예상.
4. 검증 완료 후 `legal_basis.draft.yaml` 폐지(단일 소스화).

> 마이그레이션은 되돌리기 쉬운 순서(파일 추가 → 로더 이중조회 → 구파일 제거)로. 각 단계 후 `--reevaluate-hold`(dry-run) 리포트로 영향 확인.

---

## 11. Sprint 경계

| Sprint | 산출물 |
|---|---|
| **A (현재)** | 본 설계 문서 — 스키마/3계층/ID규칙/registry연동/자동검증 인터페이스/마이그레이션 전략 |
| B | legal_master 데이터 채우기(7종 마이그레이션) + `resolve()` 로더 + 법령 수집기/변경 감지 |
| C | registry 자동생성 + writer_hint/reviewer_hint 자동 생성 |
| D | Writer Layer 2.0(4단 합성) + 연말정산 재도전 |

---

## 12. 이 설계로 풀리는 것

- 고용보험법 제70조 개정 → `find_impacted` → 육아휴직·(향후)출산급여 자동 탐색 → 본문/WP 갱신 → Telegram = **무인 유지보수**.
- 계산기 100개여도 법령은 조항 수만큼만 관리(중복 제거).
- 연말정산 병목(Writer 품질)은 Writer Layer 4단 + registry 콘텐츠 강화로 Sprint D에서 재도전.

---

## 13. Future Flow — 무인 유지보수 기준 설계도

이후 Sprint B~F가 채워 갈 전체 파이프라인. legal_master를 축으로 "법령 변경 → 발행 갱신"이 사람 개입 없이 흐른다.

```
[정부 공식 소스]  law.go.kr / nts.go.kr / moel.go.kr … (source_tier)
        │  새벽 배치: ETag/Last-Modified 선확인 → 변화 없으면 skip
        ▼
[Revision Detector]  원문 fetch → source_hash 비교
        │  hash 동일 → PASS(개정 없음, 종료)
        │  hash 변경 ▼
[legal_master 갱신]  verify_entity(tier 대조) → revision_date/rate/version up
        │
        ▼
[find_impacted()]  legal_refs 역인덱스(View) → 영향 계산기 slug + wp_post_id
        │
        ▼
[registry]  참조 계산기 확인(정의는 그대로, legal_refs만 매개)
        │
        ▼
[Writer Layer 2.0]  global + legal_master.writer_hint + registry(hint/examples/faq) + calculator
        │  본문 재생성(변경된 법령 반영)
        ▼
[Quality]  Gate(G1~G8) → Score → 품질 서명 변경 감지 → (재)통과
        │
        ▼
[WordPress Update]  publisher.update_post(wp_post_id, 새 본문)
        │
        ▼
[Telegram]  "고용보험법 제70조 개정 반영: 육아휴직 등 N건 갱신 발행" 알림
```

- **정지 조건(비용 0)**: source_hash 동일이면 AI·재생성 전부 skip. 매일 돌려도 대부분 여기서 끝난다.
- **사람 개입 지점**: `verify_entity`가 tier1 대조 실패/모호일 때만 승인 요청(그 외 무인).
- 이 플로우가 Sprint B(감지/수집), C(자동생성), D(Writer), 이후 E/F(무인 갱신·배포)의 기준 설계도다.
