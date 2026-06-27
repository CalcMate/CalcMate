# SalaryMate 계산기 플랫폼 확장 — 개발 완료 보고서

작업일: 2026-06-22 · 원칙: 기존 RSS/발행 파이프라인 **무삭제·무변경**, 신규 모듈로만 확장. 모든 데이터 접근 Repository/Adapter 경유(직접 Sheets 접근 금지).

---

## 1. 신규 파일 (5종 + 보고서)

| 파일 | 역할 | 핵심 함수 |
|------|------|-----------|
| `modules/formula_engine.py` | 계산기 수식 **안전 실행**(AST 화이트리스트, eval 미사용) | `execute_formula` `validate_formula` `load_formula` `save_formula` |
| `modules/app_generator.py` | 메타데이터→정적앱(HTML/CSS/JS) 생성, 수식→JS 변환 | `generate_calculator` `generate_html` `generate_js` `generate_css` |
| `modules/github_deployer.py` | GitHub Pages 자동 배포(토큰 없으면 graceful) | `create_repo` `deploy_app` `get_deploy_url` `is_configured` |
| `modules/internal_link_engine.py` | 계산기↔블로그 내부링크/CTA | `generate_related_calculators` `generate_related_articles` `inject_internal_links` `generate_cta` |
| `modules/calculator_seeder.py` | 초기 5종 등록(수식 포함, 멱등) | `seed_default_calculators` |

## 2. 수정 파일 (확장만, 기존 로직 보존)

| 파일 | 변경 |
|------|------|
| `dashboard.py` | **🧮 계산기 관리** 탭 신규(시드/수식편집·검증/미리보기/배포·재배포/상태토글/파일저장/삭제·URL표시) |
| `modules/calculator_pipeline.py` | 발행 본문에 `internal_link_engine`로 관련 계산기/관련 글 **내부링크 자동 주입**(try/except 가드, 실패 무시) |
| `modules/site_wizard.py` | `create_site`가 `content_mode` 오버라이드 허용(예: SalaryMate = `hybrid`). 기본값 유지 |

## 3. 기존 자산 재사용(이미 존재, 변경 없음)
- `modules/collector/factory.py` — `source_type=calculator` 라우팅 이미 등록(policy/calculator/finance/affiliate/custom)
- `modules/collector/calculator.py` — calculators→키워드 수집
- `main.py --calculator` — 계산기 콘텐츠 파이프라인 진입점
- `repositories/{calculator,site,template}_repository.py`, `adapters/db|storage/*`
- `modules/calculator_seed.py`(SAMPLE 데이터, seeder가 재사용)

---

## 4. 완료 기준 흐름 검증 (SQLite 어댑터로 end-to-end)

| 단계 | 모듈 | 검증 결과 |
|------|------|-----------|
| 계산기 등록 | `calculator_seeder.seed_default_calculators` | ✅ 5종 생성(주휴/퇴직/연차/실업/4대보험, 수식 포함) |
| 수식 실행 | `formula_engine` | ✅ 퇴직금 (월300만/3년) = 9,000,000 / 4대보험 다중출력 / 보안 악성코드 4종 전부 차단 |
| HTML 생성 | `app_generator.generate_calculator` | ✅ index.html/style.css/script.js, 수식→JS 변환 정상 |
| GitHub 배포 | `github_deployer.deploy_app` | 🟡 코드 완성. **토큰 미설정 → graceful (False, 안내)**. `GITHUB_TOKEN` 설정 시 동작 |
| 블로그 생성+발행 | `calculator_pipeline.run_calculator_once` | ✅ 키워드→SEO/FAQ→본문+위젯+CTA→ArticleRepository 저장(WP 미구축 시 검수대기) |
| 내부링크 | `internal_link_engine` | ✅ 관련 계산기(같은 카테고리 우선)/관련 글/CTA 주입 |
| 관련 계산기 연결 | `internal_link_engine.generate_related_calculators` | ✅ |

> 기존 정책 RSS 자동화(`run_once` 12단계)는 **무변경** — 컴파일/임포트 정상 확인.

---

## 5. 사용법

### 콘텐츠 생성(새 사이트 불필요)
1. `python main.py --seed-calculators` 또는 대시보드 🧮 계산기 관리 → **기본 5종 시드**
2. 🧮 계산기 관리: 수식 편집·검증 → 미리보기 → (토큰 설정 시) 🚀 배포 → URL 확인
3. `python main.py --calculator` 또는 🧮 Calculator Builder의 "계산기 글 생성" → 블로그 글(+계산기 위젯/CTA/내부링크) 발행

### GitHub Pages 배포 활성화
`config.yaml`에 추가:
```yaml
GITHUB_TOKEN: ghp_xxx       # repo 권한 PAT
GITHUB_REPO: salarymate-calculators
```
→ 계산기별 `slug` 하위 경로로 배포: `https://{owner}.github.io/salarymate-calculators/{slug}/`

### 멀티사이트(SalaryMate)
🌐 사이트 관리 → 유형 **계산기**로 등록(`site_type=calculator`, `content_mode=hybrid` 지정 가능) → 메인 파이프라인/스케줄러가 해당 사이트엔 계산기 콘텐츠 생성.

---

## 6. 보안/안정성
- **수식 실행 보안**: `eval()` 미사용. AST 화이트리스트(숫자·사칙연산·min/max/round/abs/int/float만). `__import__`/`open`/속성접근/거듭제곱 폭주 전부 차단(검증됨).
- **Graceful Degradation**: GitHub 토큰 미설정/시트 권한 오류/AI 쿼터 시 크래시 없이 안내·스킵 + 로그.
- **Backward Compatibility**: 기존 함수명/모듈/RSS·WP 파이프라인 무변경. 신규 기능은 별도 모듈/탭.

## 7. 잔존/주의
- GitHub 배포는 `GITHUB_TOKEN` 필요(미설정 시 로컬 미리보기·파일저장만).
- Sheets 저장은 서비스계정 시트 권한 필요(현재 OK). 권한 문제 시 `DB_ADAPTER: sqlite`로 즉시 동작.
- 4대보험 등 기본 수식은 예시 요율 — 실제 법정 요율로 조정 권장(`formula_engine.save_formula` 또는 🧮 계산기 관리에서 편집).
