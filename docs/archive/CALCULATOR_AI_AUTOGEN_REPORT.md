# 계산기 AI 자동생성 엔진 — 개발 완료 보고서

작업일: 2026-06-22 · 원칙: 기존 RSS/발행 파이프라인·보호 파일(main/strategist/repositories·adapters의 기존 동작) 무변경, 신규 모듈 추가 방식. 데이터 접근 Repository 경유.

---

## 1. 파일별 역할 + 함수

### 신규 파일
| 파일 | 역할 | 함수 |
|------|------|------|
| `modules/calculator_prompt_manager.py` | 모든 계산기 프롬프트 중앙 관리 + 품질규칙 주입 | `get_seo_prompt` `get_faq_prompt` `get_article_prompt` `get_cta_prompt` `get_image_prompt` |
| `modules/calculator_content_generator.py` | 블로그 본문 생성 + 전체 자동생성 오케스트레이션 | `generate_article` `auto_generate_all` |
| `modules/calculator_image_prompt_generator.py` | 이미지 프롬프트 생성 | `generate_thumbnail_prompt` `generate_body_prompt` |

### 수정(확장) 파일 — 기존 함수 보존
| 파일 | 추가/변경 |
|------|-----------|
| `modules/calculator_seo_generator.py` | `generate_seo_title()`, `generate_meta_description()` 추가 (기존 `generate_seo` 유지) |
| `modules/calculator_faq_generator.py` | `generate_faq()` → `{question,answer}` 5~10개 (q/a 하위호환) |
| `modules/app_generator.py` | FAQ 렌더가 q/a·question/answer 양쪽 허용 |
| `repositories/calculator_repository.py` | `update_generated()` — 생성 결과 + `generated_at` 저장 |
| `dashboard.py` | 🧮 계산기 관리 탭에 자동생성 버튼 6종 + 결과 미리보기 |
| `adapters/db/sqlite_adapter.py`, `sheets_adapter.py` | `update`가 **신규 컬럼 자동 추가**(기존 컬럼 불변) |

---

## 2. 연동 구조 (데이터 흐름)

```
[대시보드 🧮 계산기 관리 / 버튼]  또는  calculator_content_generator.auto_generate_all()
   │
   ▼
calculator_prompt_manager (프롬프트+품질규칙)
   │
   ├─ SEO   : calculator_seo_generator.generate_seo_title / generate_meta_description   [MODEL_WRITER]
   ├─ FAQ   : calculator_faq_generator.generate_faq (5~10, {question,answer})           [MODEL_WRITER]
   ├─ 본문  : calculator_content_generator.generate_article (2000자+, HTML, CTA 포함)    [MODEL_WRITER, 선택 검수 MODEL_EDITOR]
   └─ 이미지: calculator_image_prompt_generator (thumbnail/body)                         [Gemini Flash→Writer fallback]
   │
   ▼
CalculatorRepository.update_generated()  ──▶ adapters/db (sheets|sqlite)
   (seo_title, seo_description, faq, article_content,
    image_prompt_thumbnail, image_prompt_body, generated_at)
   │
   ▼
대시보드 "생성 결과 미리보기" 표시  +  app_generator/calculator_pipeline에서 활용
```

### calculators 테이블 확장 컬럼 (신규, 기존 컬럼 변경 없음)
`seo_title`, `seo_description`, `article_content`, `image_prompt_thumbnail`, `image_prompt_body`, `generated_at`
(어댑터 `update`가 누락 컬럼 자동 추가 → sheets/sqlite 모두 저장 가능)

### AI 모델 사용 규칙 (지시서 준수)
| 작업 | 역할(config 키) | 비고 |
|------|----------------|------|
| 총괄 | `MODEL_ORCHESTRATOR` | (필요 시) |
| SEO/FAQ/본문 | `MODEL_WRITER` | `build_provider_for_role("writing")` |
| 검수 | `MODEL_EDITOR` | `generate_article(review=True)` 시 |
| 이미지 프롬프트 | Gemini Flash(research) → 실패 시 Writer | |

### 품질 규칙
'AI가 작성/ChatGPT/Claude/Gemini' 표현 금지, 키워드 스팸 금지 — 모든 시스템 프롬프트에 `QUALITY` 주입.

---

## 3. 검증 결과 (5종, SQLite 어댑터 end-to-end 실 AI)

### 생성 단계
| 계산기 | SEO | FAQ | 본문 | 이미지 |
|--------|-----|-----|------|--------|
| 주휴수당 | ✅ | ✅ 8 | ✅ 1,712자 | ✅ |
| 퇴직금 | ✅ | ✅ 9 | ✅ 2,501자 | ✅ |
| 연차수당 | ✅ | ✅ 9 | ✅ 2,734자 | ✅ |
| 실업급여 | ✅ | ✅ 8 | ✅ 2,038자 | ✅ |
| 4대보험 | ✅ | ✅ 9 | ✅ 2,338자 | ✅ |

- 금지표현(AI/ChatGPT/Claude/Gemini) 검출: **없음 ✅**
- FAQ 개수 5~10 범위 충족 ✅

### DB 저장 단계
- 1차: 신규 컬럼이 헤더에 없어 저장 실패 발견 → 어댑터 `update` 보강(누락 컬럼 자동 추가)
- 2차(보강 후): **전체 자동생성 저장 5/5 성공**. DB 재조회 결과 5종 모두 `seo_title`/`seo_description`/`article_content`/`image_prompt_thumbnail`/`image_prompt_body`/`generated_at` 전 컬럼 저장 완료 ✅

### 종합 판정 (지시서 검증 항목)
| 항목 | 주휴수당 | 퇴직금 | 실업급여 | 연차수당 | 4대보험 |
|------|---------|--------|----------|----------|---------|
| SEO 생성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| FAQ 생성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 본문 생성 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 이미지 프롬프트 | ✅ | ✅ | ✅ | ✅ | ✅ |
| DB 저장 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 대시보드 표시 | ✅(생성결과 미리보기 + 버튼) |

**5종 전부 통과.**

---

## 4. 사용법
- 대시보드 🧮 계산기 관리 → 계산기 펼치기 → [SEO/FAQ/본문/이미지프롬프트] 개별 생성 또는 [⚡ 전체 자동생성]
- 코드: `from modules.calculator_content_generator import auto_generate_all; auto_generate_all(cfg, calc)`
- 결과는 calculators 행에 저장되고 "생성 결과 미리보기"로 확인.

## 5. 안정성/주의
- 기존 RSS 12단계(`run_once`)·`strategist`·보호 파일 기존 동작 무변경(컴파일/임포트/ dry-run 정상).
- 어댑터 `update` 변경은 **추가 컬럼 자동 생성**만(기존 컬럼/행 동작 불변).
- 실서비스(sheets)는 서비스계정 시트 권한 필요. 4대보험 등 기본 수식은 예시 요율(편집 가능).
- Gemini 무료키 429 시 이미지 프롬프트는 Writer로 fallback.
