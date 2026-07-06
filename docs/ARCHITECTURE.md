# ARCHITECTURE — 계산기 콘텐츠 파이프라인

> SalaryMate 계산기 플랫폼의 전체 흐름. (정책/RSS 블로그 12단계 파이프라인은 `main.py`/루트 README 참조 —
> 이 문서는 **계산기 생성→발행** 경로에 집중한다.)

## 전체 흐름

```
App Factory ──(신규 계산기 생성)──▶ Registry ──▶ Generator ──▶ Writer ──▶ Gate(G1~G8)
                                                                              │
                                                                              ▼
                                                          Score(S1~S6, GPT) ──▶ Retry/HOLD
                                                                              │
                                                                       PASS/WARN
                                                                              ▼
                                                                        WordPress 발행
```

각 단계 담당 모듈:

| 단계 | 모듈 | 역할 |
|------|------|------|
| App Factory | `modules/app_factory.py` | AI로 신규 계산기(스펙/코드/SEO) 생성 → calculators 시트 + `registry_auto.yaml` 기록 |
| Registry | `docs/legal_basis.draft.yaml` + `docs/registry_auto.yaml`, `modules/registry_loader.py` | 계산기 메타데이터의 **단일 소스**(slug/compute/legal/관련계산기). 상세: [REGISTRY.md](REGISTRY.md) |
| Generator | `modules/app_generator.py` | 계산기 정적앱(index.html/style.css/script.js) 생성. compute 분기·관련카드를 **registry에서만** 읽음 |
| Writer | `modules/calculator_pipeline.py::_write_article` | 본문 생성. 프롬프트 = 정적 프롬프트 + 문체 블록 + **legal_basis 블록** + 재생성 보완지시 |
| Gate | `modules/publish_quality.py::check_gates` + `_check_g8` | 결정론 코드 검사(GPT 미사용). G1~G8 |
| Score | `modules/publish_quality.py::_score_with_gpt` | GPT 채점 S1~S6. PASS≥90 / WARN≥80 / REWRITE<80 |
| Retry/HOLD | `modules/calculator_pipeline.py::run_calculator_once` | REWRITE면 전체재생성 재시도(MAX_TOTAL_RETRY). 한도 초과 시 "품질보류" HOLD |
| 발행 | `modules/publisher.py` | WordPress REST 발행/수정/삭제/복원(이 파일에서만) |

## Gate (G1~G8) — 결정론, GPT 미사용

`check_gates`(body/final_html) + `_check_g8`(legal_basis 대조). 모두 코드가 직접 판정한다.

| Gate | 검사 | 등급 |
|------|------|------|
| G1 | 본문 길이(MIN~MAX_LENGTH) | major |
| G2 | H2 개수(MIN~MAX_H2) | major |
| G3 | FAQ 개수(≥MIN_FAQ) | major |
| G4 | 계산 예시 개수(≥MIN_EXAMPLES) | major |
| G5 | 내부링크(≥MIN_INTERNAL_LINKS) + `href="#"` 0개 | critical |
| G6 | CTA 개수(=CTA_COUNT, 초과분 자동제거) | critical |
| G7 | AI 문체 금지표현(AI_STYLE_BLOCKLIST) | minor |
| **G8** | **legal_basis 대조**: law/article/authority 언급(채워진 필드만) + forbidden_articles/phrases | critical |

G8은 legal_basis의 검증된 값이 본문에 실재하는지 **문자열 매칭**으로 판정한다(GPT 환각 방지의 최종 방어선).

## Score (S1~S6) — GPT 채점, Gate와 책임 분리

`CALC_REVIEW_PROVIDER`/`CALC_REVIEW_MODEL`(기본 openai/gpt-4o)로 채점. **Gate가 결정론적으로 확정한
"존재/형식"은 Score가 재판정하지 않는다**(작업지시서 F 정리):

| Score | 판정 | Gate와의 경계 |
|-------|------|---------------|
| S1 | 계산 예시 **품질**(formula 일치·조건 다양성) | 예시 '개수'는 G4 소관 |
| S2 | 법적 근거 설명의 **맥락 적합성** | 존재/정확성은 G8 소관 |
| S3 | 적용 연도 명시 | **evergreen 계산기는 면제**(registry `content.evergreen`) |
| S4 | 문체 자연스러움 | 특정 금지표현은 G7 소관 |
| S5 | 고유 정보(중복 회피) | Gate 미커버 순수 질적 |
| S6 | 검색 의도 충족(비중·균형) | 섹션 '존재'는 Gate 소관 |

## Retry / HOLD

- REWRITE 결과면 직전 `failed_rules`를 writer에 주입해 **전체 재생성**, `MAX_TOTAL_RETRY`까지.
- Critical 연속 실패가 `CRITICAL_RETRY_LIMIT` 도달 시 Telegram 알림.
- 한도 초과에도 REWRITE면 발행하지 않고 **"품질보류"**(자동 재도전 대상) 저장.
- 재평가 게이트: 같은 writer 프롬프트 버전(`_prompt_version`=writer 프롬프트 sha1)으로 HOLD된 계산기는 재도전 스킵.
  프롬프트가 바뀌면 재도전.

## legal 미검증 차단 (BLOCK_UNVERIFIED_LEGAL)

App Factory 신규 계산기는 legal이 비어 있다(`needs_human_legal: true`). `QUALITY_GATE.BLOCK_UNVERIFIED_LEGAL: true`(기본)
이면 **GPT 호출 전에 즉시 품질보류**로 차단해 검증 안 된 법적 주장이 발행되는 것을 막는다. 사람이 legal을 채우면 자동 해제.
상세: [REGISTRY.md](REGISTRY.md), [APP_FACTORY.md](APP_FACTORY.md).
