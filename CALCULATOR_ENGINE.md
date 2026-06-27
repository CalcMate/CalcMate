# CALCULATOR_ENGINE.md — SalaryMate 계산기 엔진 (v12.0)

작업일: 2026-06-21 · 원칙: 기존 Policy(RSS) 시스템 **무삭제**, Calculator 엔진 **추가**. 모든 데이터 접근 Adapter→Repository 경유(gspread/Drive 직접 호출 0).

---

## 1. 전체 폴더 구조 (계산기 엔진 관련)

```
블로그자동_v12/
├─ main.py                         # ✏ --calculator / --seed-calculators 플래그 추가
├─ prompts/
│   └─ calculator_writer_prompt.txt   # 🆕 SEO 블로그 작성 프롬프트
├─ modules/
│   ├─ collector/
│   │   ├─ factory.py                 # (기존) calculator 라우팅 — 변경 없음
│   │   └─ calculator.py              # ✏ 키워드 확장 개선(base-name)
│   ├─ strategist_calculator.py       # 🆕 키워드 7항목 점수 평가
│   ├─ calculator_faq_generator.py    # 🆕 FAQ 5개 생성
│   ├─ calculator_seo_generator.py    # 🆕 seo_title/desc/keywords 생성
│   ├─ calculator_template_engine.py  # 🆕 스키마→HTML 계산기(결정적)
│   ├─ calculator_seed.py             # 🆕 템플릿5+계산기5 시드
│   ├─ calculator_pipeline.py         # 🆕 키워드→SEO글→CTA→발행
│   └─ ai_roles.py                    # (기존 v12) 역할별 모델
├─ repositories/
│   ├─ calculator_repository.py       # ✏ create()/delete() 추가
│   └─ template_repository.py         # (기존 v12) app_templates
└─ adapters/db/ (sheets|sqlite)       # (기존) 변경 없음
```

---

## 2. 신규 파일 목록

| 파일 | 역할 |
|------|------|
| `prompts/calculator_writer_prompt.txt` | SEO 블로그 글 작성 프롬프트(2500~3500자, CTA 필수) |
| `modules/strategist_calculator.py` | 키워드 점수(검색의도/CPC/검색량/SEO경쟁/계산기연결/전환/시즌) 0~100 |
| `modules/calculator_faq_generator.py` | 계산기명→FAQ 5개 |
| `modules/calculator_seo_generator.py` | 계산기/키워드→seo_title/description/keywords |
| `modules/calculator_template_engine.py` | input/output_schema→자가완결 HTML 계산기(AI 미사용) |
| `modules/calculator_seed.py` | app_templates 5종 + calculators 5종 시드(멱등) |
| `modules/calculator_pipeline.py` | 계산기 콘텐츠 파이프라인(수집→점수→SEO/FAQ→작성→위젯+CTA→저장→발행) |

## 3. 수정 파일 목록

| 파일 | 변경 |
|------|------|
| `repositories/calculator_repository.py` | `create()`(save 별칭, status=active), `delete()` 추가. id 충돌 방지(uuid 접미사) |
| `modules/collector/calculator.py` | 키워드 확장 개선: '계산기' 접미사 제거 후 `{base} 계산/계산법/조건/세금...` 생성, `keyword` 필드 추가, 중복 제거 |
| `main.py` | `--calculator`(파이프라인 1회), `--seed-calculators`(시드) 플래그 + 분기 추가. 기존 run_once/RSS 경로 무변경 |
| `dashboard.py` | 🧮 Calculator Builder 탭에 '초기 5종 시드' / '계산기 글 1건 생성' 버튼 추가 |

> Collector Factory(`factory.py`)는 이미 `calculator`/`finance`/`affiliate`/`policy`를 등록하고 있어 **변경 불필요**(작업3 충족 확인).

---

## 4. DB 컬럼 영향도

신규 컬럼 추가 없음. 기존 시트 탭 컬럼을 그대로 사용(어댑터가 없는 탭/컬럼은 자동 생성).

| 테이블 | 사용 컬럼 | 쓰기 주체 |
|--------|-----------|-----------|
| `calculators` | id, name, slug, category, calculator_type, template_id, version, published_url, site_id, formula, faq, input_schema, output_schema, seo_title, seo_desc, status, created_at, updated_at | CalculatorRepository(create/update/delete), seed |
| `app_templates` | template_id, template_name, template_type, html_template, seo_template, faq_template, status, created_at | TemplateRepository(save), seed |
| `articles`(마스터_DB) | 정책명, 최종추천제목, 메타설명, 태그, 발행 URL, 발행일시, 원본출처, 상태값, site_id | ArticleRepository(save) — 계산기 글 결과 |

영향: calculators/app_templates에 **데이터 행 추가**(시드 5+5), articles에 계산기 글 행 추가. 기존 정책(RSS) 데이터와 동일 테이블 공유(상태값/필드 호환).

---

## 5. 데이터 흐름 다이어그램

```
[기존 유지]  RSS Source ─▶ PolicyCollector ─▶ run_once(STEP1~12) ─▶ articles ─▶ WordPress

[신규 추가]  calculators(DB)
                │  CalculatorCollector.collect()         (Repository 경유)
                ▼
            키워드 목록 [{keyword, calculator_id, ...}]
                │  strategist_calculator.score_keywords() (7항목 점수, 정렬)
                ▼
            상위 N 키워드
                │  calculator_seo_generator.generate_seo()   (작성 AI=GPT)
                │  calculator_faq_generator.generate_faq()    (계산기 저장 FAQ 우선)
                │  calculator_pipeline._write_article()       (writer 프롬프트, GPT)
                │  calculator_template_engine.build_html()    (스키마→위젯, 결정적)
                ▼
            본문 HTML + "<h2>계산기 사용하기</h2> + CTA + 계산기 위젯"
                │  publisher.publish()  (WP 미구축 시 검수대기로 대기)
                ▼
            ArticleRepository.save() ─▶ articles 테이블
```

AI 역할(ai_roles): 총괄/검수=GPT(gpt-4o), 리서치=Gemini(2.5-flash), 코드=Claude(sonnet-4-6), 작성=GPT, 이미지=Gemini(프롬프트). 설정 탭에서 편집(`AI_ROLES`).

---

## 6. 구현 코드

위 신규/수정 파일에 실제 구현 완료(컴파일·실행 검증). 핵심 진입점:
- 시드: `python main.py --seed-calculators`  또는 대시보드 🧮 탭 버튼
- 실행: `python main.py --calculator`         또는 대시보드 🧮 탭 버튼
- 코드에서: `from modules.calculator_pipeline import run_calculator_once; run_calculator_once(cfg, max_count=N)`

---

## 7. 테스트 시나리오 (실행/검증 결과 포함)

| # | 시나리오 | 방법 | 결과 |
|---|----------|------|------|
| 1 | Repository create/delete | 단위 | ✅ create(active)/delete 동작, id 충돌 방지 |
| 2 | 키워드 확장 | 단위 | ✅ '주휴수당 계산기'→'주휴수당 계산/계산법/계산 방법/조건...' |
| 3 | 템플릿 엔진(결정적) | 단위 | ✅ 스키마→2KB HTML(입력2, 계산버튼, 결과영역) |
| 4 | 키워드 점수(휴리스틱) | 단위 | ✅ '계산법'(74) > '사용법'(60) 정렬 |
| 5 | 시드(템플릿5+계산기5) | SQLite 어댑터 | ✅ templates 5 / calculators 5 등록·조회 |
| 6 | **전체 파이프라인** | SQLite 어댑터(실 AI) | ✅ 1건 생산: SEO("2026 주휴수당 계산법 가이드")+본문+위젯, articles 저장(검수대기, WP 미구축이라 대기) |
| 7 | WP 미구축 graceful | 통합 | ✅ publisher가 skipped_no_wp → 검수대기 저장(오류 없음) |
| 8 | 시트 권한(403) 대비 | 코드 | ✅ 저장 실패 시 명확한 안내 메시지(시트 권한 확인) |

검증 환경: `DB_ADAPTER=sqlite`(임시 DB)로 Adapter→Repository 전 경로 실행. 실서비스(sheets)에서는 서비스 계정 시트 권한(현재 403) 복구 후 동일 동작.

---

## 8. 남은 의존/주의
- 실서비스 저장은 **Google Sheet 서비스계정 권한(현재 403)** 복구 필요. 그 전엔 생성은 되나 시트 저장 실패(안내 표시). SQLite로 전환 시 즉시 사용 가능.
- 점수화 기본은 휴리스틱(비용 0). `CALCULATOR_AI_SCORE: true` 설정 시 AI 평가.
- Gemini 무료 키 쿼터(429) 시 일부 생성 graceful 처리.
