# BUGFIX — 계산기 파일 저장/링크/수식 경고 (2026-07-04)

> 계산기 정적 앱(app_generator, design v2) 관련 3건 버그 수정 기록.
> 공통 원칙: UI/디자인/레이아웃/계산식(formula·computeResult) 무변경, 최소 범위 수정.

---

## 1. 계산기 "파일 저장" — CSS/JS 미적용 버그

- **증상**: 대시보드 `🔎 앱 미리보기`와 `📥 파일 저장`으로 저장한 파일의 렌더가 다름(저장본은 CSS/JS 미적용).
- **원인**: 저장 파일명이 `calc_{slug}_style.css` 형태 → index.html의 `<link href="style.css">` / `<script src="script.js">` **상대경로와 불일치** → CSS/JS 로드 실패. (`ai_workspace.write_workspace_file`이 `/`를 `_`로 sanitize하여 하위폴더 저장 불가)
- **수정**: `dashboard.py`의 `cm_dl_{cid}` 콜백을 **계산기별 폴더 저장**으로 변경.
  `data/workspace/{slug}/index.html · style.css · script.js` (원본 파일명 유지, slug의 `/`·`\`·`..` sanitize, `os.makedirs(exist_ok=True)`).
- **파일**: `dashboard.py` (콜백 1곳). `app_generator`/`calculator_v2.html`/`design_system.css`/`ai_workspace` 무변경.
- **커밋**: `3ca475a` (+ 이력 `a4224f6`)
- **검증**: 폴더 생성 확인, index.html 상대링크(`href="style.css"`/`src="script.js"`) 유지, 로컬 더블클릭 시 시안과 동일 렌더 → **로컬=GitHub Pages 동일 구조**.

---

## 2. 관련 계산기 링크 — `href="#"` 정적 버그

- **증상**: 관련 계산기 클릭 시 이동 안 됨(모두 `#`).
- **원인**: `app_generator._related_items_v2()`가 앵커를 `href="#"`로 서버 렌더링. `related.js`의 `smBuildRelated`는 자동 호출되지 않는 미사용 훅이라 덮어쓰지 않음.
- **수정**: `_related_items_v2()`의 `href="#"` → **`href="../{slug}/" target="_self"`**.
  - `_RELATED` slug 기반 **형제 계산기 폴더 상대경로**.
  - `target="_self"`: 미리보기 iframe 자체가 이동(대시보드 상위 프레임 안 튐). *(지시서 초안의 `_top`은 의도와 반대여서 `_self`로 확정)*
- **파일**: `app_generator.py` (`_related_items_v2` 함수 1곳). `related.js`/`calculator_v2.html`/`design_system.css` 무변경.
- **커밋**: `8827a88`
- **검증**: 생성물 관련그리드가 `../{slug}/ target="_self"`(자기 자신 제외), `href="#"` 잔여 0.
  - 참고: 대시보드 미리보기는 `components.html`의 **srcdoc iframe**이라 상대경로 미해석(무동작·안전). **실제 이동은 로컬 `file://` 더블클릭**에서 동작(형제 폴더 실존 시).
  - 기존 저장본 중 재저장 안 한 것(`four-insurances`·`unemployment-benefit`)은 옛 `href="#"` → **재저장 필요**.

---

## 3. 퇴직금 "수식 경고" 오탐

- **증상**: 퇴직금 `🔎 앱 미리보기`에서 불필요한 "수식 경고" 표시.
- **원인**: `severance-pay`는 `_compute_js`가 `start_date`/`end_date`로 계산(코드 내장)하고 `formula` 필드를 쓰지 않음. 그런데 DB에 남은 formula `avg_monthly_wage * (total_days / 365)`가 `input_schema`에 없는 `total_days`를 참조 → `validate_formula`가 False 반환 → 경고.
- **수정**: `generate_calculator()`에 분기 추가. `slug=='severance-pay'`면 `validate_formula` 미호출, `(True, "날짜기반 계산(코드 내장) — 수식 검증 제외")` 반환.
- **파일**: `app_generator.py` (`generate_calculator` 분기 1곳). `_compute_js`/`calculator_v2.html`/`design_system.css` 무변경. **DB formula 값 무변경**(코드 분기만).
- **커밋**: `da49650`
- **검증**: 퇴직금 `_formula_valid=True`(경고 사라짐), 주휴수당/4대보험 등은 `msg="OK"`로 기존 `validate_formula` 정상 동작.

---

## 남은 확인(운영자)
- **Streamlit 재시작** 후 위 3건 실제 반영 확인(대시보드는 시작 시점 코드를 메모리에 유지).
- `four-insurances`·`unemployment-benefit`는 `📥 파일 저장` 재실행하여 관련링크 갱신.
- 브라우저 전용 항목(로컬 더블클릭 이동, PNG 저장, 카카오, PWA, 모바일)은 실제 브라우저 확인.

> 관련 전체 이력: `CHANGELOG_AI.md`(2026-07-04 항목) · 커밋 `3ca475a`/`a4224f6`/`8827a88`/`da49650`.
