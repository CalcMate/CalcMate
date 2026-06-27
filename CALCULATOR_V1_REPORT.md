# CALCULATOR_V1_REPORT.md — 계산기 플랫폼 MVP(v1) 완성 보고서

작업일: 2026-06-23 · 모드: AUTO EXECUTION · 원칙: 보호 계층(main/RSS/Writer/Editor/Publisher/Repository/Adapter/Scheduler/Dashboard 로직) **무변경**, 신규 추가 방식.

---

## 구현 범위 (5개)
1. Calculator UI Template v1 확정
2. Calculator Template Library (골드 템플릿 5종)
3. Calculator Form Engine
4. AI Reviewer (자동 검수)
5. Site Mode System (승인전/승인후/확장)

---

## 신규 파일 목록
| 파일 | 역할 |
|------|------|
| `templates/calculators/calculator_v1.html` | 모든 계산기 공통 UI(Hero/입력폼/결과/해설/FAQ/관련/업데이트/모바일CTA). `{{TITLE}}`~`{{UPDATE_HTML}}` 변수 치환 |
| `templates/library/retirement.json` 외 4 (annual_leave/weekly_allowance/unemployment/insurance) | 골드 템플릿(calculator_type/fields/formula/output_schema/faq_template/article_template) |
| `modules/calculator_form_engine.py` | `generate_form_schema()`, `build_form_html()`, `get_library_template()` — 이름 분석→입력폼 자동 생성(라이브러리 우선, 없으면 AI) |
| `modules/calculator_reviewer.py` | `review_calculator()`, `approve()`, `reject()`, `review_and_save()` — 0~100 채점, ≥80 PASS / <80 REWRITE |
| `config/site_mode.yaml` | 운영 모드(pre_adsense/post_adsense/growth)별 노출 정책 |
| `modules/site_mode_manager.py` | `get_mode/set_mode/is_ads_enabled/is_cpa_enabled/is_share_enabled/is_report_enabled/all_flags` |

## 수정 파일 목록 (계산기 모듈만)
| 파일 | 변경 |
|------|------|
| `modules/app_generator.py` | `generate_calculator(calc, cfg=None)`이 **calculator_v1.html 템플릿 + Form Engine + Site Mode**로 생성하도록 재작성. 기존 호출(`generate_calculator(c)`) 호환, 출력(index/style/script 3파일) 유지. 공개 계산기용 라이트 테마 CSS |

> 보호 파일(main.py/RSS/writer/editor/publisher/repositories/adapters/scheduler/dashboard 로직)은 **한 줄도 수정하지 않음.** review_* 컬럼은 기존 `CalculatorRepository.update_generated`로 저장(Repository 구조 무변경).

---

## 동작 흐름 (MVP)
```
계산기 등록(시드/Builder)
  → Form Engine 입력폼 생성(라이브러리 우선)
  → Formula Engine 수식 검증
  → (AI 생성: SEO/FAQ/본문/이미지 — 기존 모듈)
  → AI Reviewer 검수(≥80 PASS / <80 REWRITE)
  → calculators 저장(review_status/score/reason/reviewed_at)
  → app_generator: calculator_v1.html + Site Mode 적용 → index/style/script
  → (배포: github_deployer)
```

## 검증 결과 (SQLite 어댑터 end-to-end)
| # | 항목 | 결과 |
|---|------|------|
| 1 | 기존 RSS run_once dry-run | ✅ `{'produced':0,'reason':'dry_run'}` (무변경) |
| 2 | 보호 파일 미수정 | ✅ main/writer/editor/publisher/repo/adapter/scheduler/dashboard 그대로 |
| 3 | 시드 5종 생성 | ✅ 5건 |
| 4 | Form Engine | ✅ 라이브러리 매칭(퇴직금→평균월임금/근속연수), build_form_html `<input>` 생성 |
| 5 | calculator_v1.html 렌더 | ✅ `{{}}` 잔여 0, Hero/FORM(in_avg_monthly_wage)/RESULT(out_severance_pay) 포함, 수식 valid |
| 6 | AI Reviewer | ✅ review_calculator 채점→DB(review_status/score/reviewed_at) 저장. 본문 미생성 시드는 정상적으로 REWRITE→NEEDS_REVIEW(25점) |
| 7 | Site Mode 전환 | ✅ pre_adsense=전부 숨김 / post_adsense=관련·광고 / growth=관련·광고·공유·리포트 |
| 8 | 전체 컴파일/임포트 | ✅ |

## calculators 테이블 추가 컬럼 (어댑터 자동 생성, 기존 컬럼 불변)
`review_status` · `review_score` · `review_reason` · `reviewed_at`
(상태값: AUTO_APPROVED / NEEDS_REVIEW. review_calculator는 PASS/REWRITE 산출)

## Site Mode 노출 정책
| mode | ads | cpa | share | report | related |
|------|-----|-----|-------|--------|---------|
| pre_adsense | ✕ | ✕ | ✕ | ✕ | ✕ |
| post_adsense | ✓ | ✕ | ✕ | ✕ | ✓ |
| growth | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## ✅ Reviewer ↔ auto_generate_all 자동 연결 완료 (2026-06-23)
- `calculator_reviewer.auto_review_and_fix()` 추가: 검수(PASS/REWRITE) → REWRITE 시 SEO/FAQ/본문 **자동 재생성 최대 2회** → 재채점 → 상태 확정(AUTO_APPROVED / AUTO_REWRITTEN / NEEDS_REVIEW).
- `calculator_content_generator.auto_generate_all(cfg, calc, auto_review=True)`가 생성(SEO→FAQ→본문→이미지) 직후 리뷰어 호출, 결과를 반영·저장(`review_status/score/reason/attempts/reviewed_at`).
- 검증: 퇴직금 계산기 1종 — 생성(본문 2,669자/FAQ 9) → 검수 REWRITE → 자동수정 2회 → NEEDS_REVIEW(47점)로 DB 저장. 전 컬럼 저장 확인. RSS dry-run 정상(무변경).
- 흐름: 계산기 등록 → 생성 → **AI 검수 → 자동수정 → 통과/검수대기** → DB 저장 (사용자 승인 단계 없음).

## 남은 TODO
- 골드 템플릿의 `article_template` 본문 자동 채움 연동.
- Form Engine select/radio options AI 추론 고도화.
- growth 모드 토스 결제/리포트 PDF 실제 연동.
- Reviewer REWRITE 시 자동 재생성 루프(현 버전은 채점+상태저장; 재생성은 별도 generator 호출 필요).
- 4대보험 등 기본 수식 법정 요율 최신화.

## 실행/사용
- 계산기 페이지 생성: `app_generator.generate_calculator(calc, cfg)` → 대시보드 🧮 계산기 관리 [배포]로 GitHub Pages 배포
- 검수: `calculator_reviewer.review_and_save(cfg, calc)`
- 모드 전환: `site_mode_manager.set_mode("post_adsense")` 또는 `config/site_mode.yaml`
