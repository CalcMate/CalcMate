# APP FACTORY — 신규 계산기 생성

> 메타데이터만 입력하면 계산기(스펙/코드/SEO)를 AI로 자동 생성하고 registry에 등록한다.
> 단, **발행은 legal 검증 완료까지 HOLD**된다(검증 안 된 법적 주장 방지).

## 식별자 원칙 — slug(영문) vs name(한글)

| 항목 | 값 | 용도 |
|------|-----|------|
| `slug` | 영문 (예: `annual-tax-settlement`) | 폴더명 · URL · WordPress · registry 키 · 내부참조 |
| `name` | 한글 (예: `연말정산`) | 대시보드 · App Factory UI · Telegram · 사용자 표시 |

**신규 계산기는 App Factory UI에서 영문 slug를 직접 입력**한다(GPT 번역/로마자 변환 없음). 검증 정규식
`^[a-z0-9][a-z0-9-]*$` — 한글/공백/대문자 거부. 기존 계산기(연말정산_환급액_계산기 등 한글 slug 포함)의
slug는 **절대 변경하지 않는다**(registry 키·폴더·WP 보호).

## 생성 절차

```
1. 대시보드 🧮 Calculator ▸ App Factory
2. 계산기명(한글 name) + 카테고리 + 설명 입력  (AI 아이디어 제안 버튼도 있음)
3. "🏭 자동 생성" → generate_app() 4단계:
     sys1(orchestrator) 스펙(input/output/formula/labels) + formula 검증(1회 재시도)
     sys2(code)        단일 HTML(인라인 CSS/JS)
     sys3(writer)      SEO 제목/설명 + FAQ + 블로그 초안
     sys4(image)       이미지 프롬프트
4. 미리보기 확인 → 영문 slug 입력 → "💾 저장"
     save_app(): calculators 시트 + app_templates 시트 + registry_auto.yaml 자동 기록
                 + docs/calculator_index.json(slug↔name 매핑) 갱신
```

`save_app`이 `registry_auto.yaml`에 쓰는 자동 엔트리:
- identity/compute/labels/meta 자동 추론 (compute_type: date 필드→date_based, 출력 2+/formula dict→dict, 그 외 single)
- **legal 전부 null + `needs_human_legal: true`** (사람이 나중에 채움)

## 발행 — HOLD → legal 입력 → 자동 해제

신규 계산기는 legal이 비어 있어 `_legal_unverified=True` → `BLOCK_UNVERIFIED_LEGAL: true`(기본)에서
**GPT 호출 전에 즉시 품질보류**된다.

```
발행하려면:
1. docs/legal_basis.draft.yaml 에 이 계산기 slug의 legal 입력(law/article/authority 등) — 사람이 검증
   (registry_auto.yaml이 아니라 legal_basis.draft.yaml에 = "승격")
2. 다음 실행에서 _legal_unverified=False → 게이트 통과 → 정상 파이프라인(G8 포함) → 발행
```

`needs_human_legal`를 `false`로 바꾸지 않아도 legal 데이터만 있으면 통과한다(데이터가 게이트 — [REGISTRY.md](REGISTRY.md)).

## opt-out (완전 자동화)

`BLOCK_UNVERIFIED_LEGAL: false`로 두면 legal 미검증 계산기도 발행되지만, writer가 **"legal 미확정 모드"**로
동작한다: 특정 법령/조항 인용을 원천 금지(환각 차단) + 강한 미확정 면책 문구 강제.

## 절대 변경 금지 (App Factory 관련)

- 기존 계산기 slug (registry 키)
- generate_app의 생성 로직(4단계) · save_app의 시트 저장
- calculator_index.json은 **순수 참조 문서** — 어떤 로직도 이 파일을 읽지 않는다(개발 편의용).
