# REGISTRY 2.0 — 계산기 메타데이터 단일 소스

> 계산기의 식별자·계산방식·법적근거·관련계산기를 **한 곳**에서 관리한다. Phase A→D를 거쳐
> 하드코딩 폴백을 모두 제거하고 registry가 유일 소스(Single Source of Truth)가 되었다.

## 두 파일 + 로더

| 파일 | 역할 | 편집 주체 |
|------|------|-----------|
| `docs/legal_basis.draft.yaml` | 사람이 검증한 큐레이션 데이터(legal 포함) | **사람만** (코드는 읽기만) |
| `docs/registry_auto.yaml` | App Factory가 자동 생성한 신규 계산기 엔트리 | **App Factory만** (사람 편집 금지) |
| `modules/registry_loader.py` | 두 파일을 merge → `slug→entry` dict | — |

`load_registry()`가 둘을 merge하며 **동일 slug는 큐레이션(legal_basis.draft.yaml)이 항상 우선**한다.
→ 자동 엔트리를 사람이 검증해 legal_basis.draft.yaml로 "승격"하면 그게 최종본이 되고, registry_auto의
임시 엔트리는 자동으로 무시된다.

세 소비자(`app_generator._registry`, `calculator_pipeline._load_legal_basis`, `publish_quality._load_legal_basis`)가
모두 `load_registry()`에 위임한다 → 단일 소스.

## 엔트리 스키마 (schema_version: 2)

```yaml
<slug>:
  # identity
  slug: <영문 식별자 — 폴더/URL/내부참조>
  name: <한글 정식 명칭 — 대시보드/legal 인용>
  category: <카테고리>
  emoji: "🧮"
  card_label: <관련카드 표시명(짧은 UI 문구). 기본=name, 다르면 override>
  # compute (app_generator가 소비)
  compute_type: single | dict | date_based
  date_fields: [<날짜 입력 필드>]
  validation_mode: formula | skip   # date_based는 skip
  # labels / meta
  field_labels: {<필드>: <라벨>}
  difficulty: simple | date_based | multi_output | complex
  difficulty_status: provisional
  needs_human_legal: true|false
  # legal (G8 + writer가 소비) — 사람이 검증해 채움
  law: <법령명>
  article: <조항> | null
  authority: <소관기관>
  related_articles: [...]
  writer_note: <작성 지침>
  forbidden_articles: [<혼동 조항 — 등장 시 G8 critical>]
  forbidden_phrases: [<확정형 금지 표현>]
  confidence / last_verified / verification_source
  # content / relations
  content: {evergreen: true|false|null, update_cycle: null|yearly, content_caveat: ...}
  related_slugs: [<관련 계산기 slug>]
```

## needs_human_legal + 데이터-존재 게이트

`needs_human_legal: true`는 "legal 검증 필요" 선언이지만, **실제 차단 판정은 플래그가 아니라 데이터 존재**로 한다:

```python
# calculator_pipeline._legal_unverified(lb)
needs_human_legal == True  AND  (law/article/authority가 전부 비어있음)  → 미검증(차단 대상)
```

**왜 플래그 단독이 아닌가**: 사람이 legal을 채우고 `needs_human_legal: false`로 바꾸는 걸 깜빡해도,
실제 데이터(law/article/authority)가 있으면 자동으로 "검증됨"으로 취급된다. 플래그는 거짓말할 수 있어도
데이터 존재 여부는 거짓말하지 못한다.

## HOLD → 자동 해제 흐름

```
App Factory 생성 → registry_auto(legal 전부 null, needs_human_legal:true)
   → 발행 시도 → _legal_unverified=True → 품질보류(GPT 호출 0)
사람이 legal_basis.draft.yaml에 legal 입력(승격)
   → 큐레이션이 auto를 덮음 → _legal_unverified=False
   → 다음 실행에서 게이트 통과 → 정상 파이프라인(G8 포함) → 발행
```

legal-HOLD는 sentinel 버전(`legal_unverified`)으로 기록되어, writer 프롬프트 버전 기반 재평가 게이트와
충돌하지 않는다(legal 채우면 게이트 자체를 통과하므로 이전 HOLD가 막지 않음).

## Phase A~D 요약

| Phase | 내용 |
|-------|------|
| A | schema_version 2 데이터 구조 신설(로직 무변경) |
| B | 하드코딩(`_RELATED`/compute 분기)이 registry 읽기 + 폴백. 스냅샷 하니스 도입 |
| C | App Factory 자동기록(`registry_auto.yaml`) + legal 미검증 HOLD 정책 |
| D | 하드코딩 폴백 **완전 제거** → registry 유일 소스 |

회귀 검증: `tests/snapshot_calculators.py`(7종×5산출물=35 sha256). registry 변경 후에도 35/35 동일해야 한다.
