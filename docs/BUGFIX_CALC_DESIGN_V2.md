# BUGFIX — 계산기 Design System v2 (2026-07-04)

> 계산기 정적 앱(`app_generator` + design v2) 관련 버그 4건 수정 기록 + PWA 보류 메모.
> 공통 원칙: **UI/디자인/레이아웃/계산식(formula·computeResult) 무변경**, 최소 범위 수정.
> ※ 이 문서는 이전 `BUGFIX_CALC_FILE_SAVE.md`(3건)를 **통합·대체**한다.

| # | 버그 | 커밋 |
|---|------|------|
| 1 | 파일 저장 CSS/JS 미적용(경로 불일치) | `3ca475a` (+이력 `a4224f6`) |
| 2 | 관련계산기 링크 `href="#"` | `8827a88` |
| 3 | 퇴직금 수식 경고 오탐 | `da49650` |
| 4 | 노출설정 미반영(cfg 미전달) | `8e91990` |
| ⏸ | PWA 홈화면추가 — 배포 후 확인 예정(버그 아님) | — |

---

## 1. 계산기 "파일 저장" — CSS/JS 미적용
- **증상**: `🔎 앱 미리보기`와 `📥 파일 저장` 저장본 렌더가 다름(저장본 CSS/JS 미적용).
- **원인**: 저장 파일명 `calc_{slug}_style.css` ↔ index.html의 `<link href="style.css">`/`<script src="script.js">` **상대경로 불일치**. (`ai_workspace.write_workspace_file`이 `/`를 `_`로 sanitize → 하위폴더 저장 불가)
- **수정**: `dashboard.py`의 `cm_dl_{cid}` 콜백을 **계산기별 폴더 저장**으로. `data/workspace/{slug}/index.html·style.css·script.js`(원본 파일명, slug `/·\·..` sanitize, `os.makedirs`).
- **파일/무변경**: `dashboard.py` 콜백 1곳만. app_generator/템플릿/CSS/ai_workspace 무변경.
- **검증**: 폴더 생성·상대링크 유지·로컬 더블클릭 시안 동일 → 로컬=GitHub Pages 동일 구조.

## 2. 관련 계산기 링크 `href="#"`
- **증상**: 관련계산기 클릭 시 이동 안 됨(전부 `#`).
- **원인**: `_related_items_v2()`가 `href="#"`로 서버 렌더. `related.js`의 `smBuildRelated`는 자동 호출 안 되는 미사용 훅.
- **수정**: `href="#"` → **`href="../{slug}/" target="_self"`**(형제 폴더 상대경로 · iframe 자체 이동, 대시보드 안 튐). *(지시서 초안 `_top`은 의도와 반대여서 `_self`로 확정)*
- **파일/무변경**: `app_generator._related_items_v2` 1곳. related.js/템플릿/CSS 무변경.
- **검증**: 생성물 `../{slug}/ target="_self"`(자기 제외), `href="#"` 0.
  - 미리보기는 `components.html`의 **srcdoc iframe** → 상대경로 미해석(무동작·안전). **실제 이동은 로컬 `file://` 더블클릭**(형제 폴더 실존 시).
  - 재저장 안 한 옛 저장본은 `href="#"` 잔존 → **재저장 필요**.

## 3. 퇴직금 "수식 경고" 오탐
- **증상**: 퇴직금 미리보기에 불필요한 "수식 경고".
- **원인**: severance-pay는 `_compute_js`가 `start_date`/`end_date`로 계산(코드 내장), `formula` 필드 미사용. DB의 옛 formula `avg_monthly_wage * (total_days / 365)`가 `input_schema`에 없는 `total_days` 참조 → `validate_formula`=False → 경고.
- **수정**: `generate_calculator()`에 분기 — `slug=='severance-pay'`면 `validate_formula` 미호출, `(True, "날짜기반 계산(코드 내장) — 수식 검증 제외")`.
- **파일/무변경**: `app_generator.generate_calculator` 분기 1곳. `_compute_js`/템플릿/CSS 무변경, **DB formula 무변경**.
- **검증**: 퇴직금 `_formula_valid=True`(경고 사라짐). 주휴수당/4대보험 등은 `msg="OK"`로 기존 검증 정상.

## 4. 노출설정 미반영 (cfg 미전달)
- **증상**: `🎨 계산기 노출 설정`에서 `SHOW_*`/`SITE_MODE`를 바꿔 저장해도 생성물에 반영 안 됨.
- **원인**: `dashboard.py`에서 `generate_calculator(c)`를 **cfg 없이 호출** → `_sm_config(calc, cfg=None)`이 config를 못 읽어 항상 하드코딩 기본값 생성.
- **수정**: `generate_calculator(c)` → **`generate_calculator(c, cfg)`**(L1385, 1줄).
- **파일/무변경**: `dashboard.py` 1줄. app_generator/템플릿/CSS 무변경.
- **검증**: cfg 전달 시 `SHOW_RELATED=off`/`SHOW_FAQ=off`/`SITE_MODE=full`이 SM_CONFIG에 반영, 원복 시 기본값 복귀.

## ⏸ PWA (홈 화면 추가) — 보류(버그 아님)
- 로컬(`file://`)에서는 `beforeinstallprompt`가 발생하지 않아 설치 버튼이 안 뜨는 게 **정상**(브라우저 정책: HTTPS/서비스워커/매니페스트 필요).
- **GitHub Pages 등 실제 배포(HTTPS) 후 확인 예정.** 코드(`pwa.js`)는 배선 완료(설치 가능 환경에서만 버튼 노출, 불가 시 안내).

---

## 남은 확인(운영자)
- **Streamlit 재시작** 후 위 4건 실제 반영 확인(대시보드는 시작 시점 코드/설정을 메모리에 유지).
- `four-insurances`·`unemployment-benefit`는 `📥 파일 저장` 재실행으로 관련링크 갱신.
- 브라우저 전용(로컬 더블클릭 이동, PNG 저장, 카카오, PWA, 모바일)은 실제 브라우저·**배포 후** 확인.

> 관련 이력: `CHANGELOG_AI.md`(2026-07-04) · 커밋 `3ca475a`/`a4224f6`/`8827a88`/`da49650`/`8e91990`.
