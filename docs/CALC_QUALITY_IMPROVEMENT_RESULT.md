# CALC_QUALITY_IMPROVEMENT_RESULT — 계산기·WordPress 파이프라인 품질 개선 (2026-07-04)

> 계산기 콘텐츠 파이프라인 + WordPress 발행/수정 경로의 구조·품질 버그를 단계별로
> 수정한 기록. 모든 항목 **작업별 보고→승인→커밋 게이트** 엄수, 실환경(로컬 WordPress
> `http://salarymate.test`) 검증 완료.
> 관련: `docs/BUGFIX_CALC_DESIGN_V2.md`(디자인 v2 버그 4건), `CHANGELOG_AI.md`.

---

## Part 1 — WordPress 발행 메타데이터 저장 구조 (1차)

**문제:** 발행 시 WordPress 응답의 숫자 `id`를 버리고 URL(link)만 저장 → 이후 글
수정/삭제 시 대상을 특정할 수 없었음. 이력(history)도 없음.

**수정:**
- `publisher._wordpress_api()` 반환을 str→dict로: `wp_post_id`/`wp_permalink`/`wp_status`/
  `published_at` 추가(`wordpress` 키는 하위호환 유지). skip 케이스 무변경. — `9a39edd`
- `article_repository.append_history(article_id, event, extra)` 신설. history(JSON
  문자열)에 이벤트 append. **상태값 검증(VALID_STATUSES) 우회 위해 저수준 `_db.update`**
  사용 → "검수대기" 등 어떤 상태에서도 `ValueError` 없이 기록.
- `main.py` STEP12 + `calculator_pipeline` 양쪽에서 wp 메타 저장 + `append_history("publish")`
  호출. — `9a39edd`, `0502d92`
- `count_active_articles`용 `calculator_id` 컬럼 추가(Part 3에서 활용). — `ab33988`

**시트 헤더 제약:** `sheets_adapter.insert()`는 헤더에 없는 컬럼을 자동추가하지 않음
(`update()`는 함). 따라서 `wp_post_id`/`wp_permalink`/`wp_status`/`published_at`/
`calculator_id`는 **마스터_DB 시트에 헤더 수동 추가 필요**(운영자 완료). `history`는
`append_history`가 update 경로라 자동 생성됨.

**실환경 검증:** 계산기 글 실발행 → 마스터_DB에 `wp_post_id`/permalink/status/
published_at/history/calculator_id 정상 기록, WordPress REST `GET posts/{id}` 200 확인.

---

## Part 2 — WordPress 삽입 위젯 엔진 통일 (치명적 계산 버그)

**문제:** WordPress 글에 삽입되는 계산기 위젯이 구버전 `calculator_template_engine.
build_calculator_html()`을 사용 → `formula`를 무시하고 **모든 입력을 단순 합산**
(`Object.values(v).reduce((a,b)=>a+b,0)`). 즉 실제 발행된 계산기가 **잘못된 계산
결과**를 출력.

**수정:** — `e489eb1`
- `app_generator.render_inline_calculator(files)` 신설: `generate_calculator()`의
  {index.html, style.css, script.js}를 문서 골격 없는 자체완결 조각(`<style>`+sm-wrap+
  SM_CONFIG+inline js)으로 변환.
- **대시보드 미리보기(`dashboard._inline`)와 WordPress 삽입(`calculator_pipeline`)이 이
  단일 함수를 공유** → 동일 계산엔진(v2 `computeResult`, formula/퇴직금 날짜로직 반영).
- WordPress 삽입 시 블로그 본문 중복 방지로 `SHOW_ARTICLE/FAQ/RELATED/ADSENSE/CPA/PWA=False`.
- `calculator_template_engine`은 `calculator_seed.py`가 아직 사용 → **삭제하지 않음**
  (백로그: seed도 v2 이관 후 제거).

**실환경 검증:** 주휴수당/연말정산/퇴직금 3종에서 대시보드==WP `computeResult` 동일,
naive 합산 제거(주휴수당 `hourly_wage*(weekly_hours/40*8)` 반영), 퇴직금 날짜로직 정상.

---

## Part 3 — 파이프라인 콘텐츠 조합 버그 4건

| # | 버그 | 수정 | 커밋 |
|---|------|------|------|
| 1 | "계산기 사용하기"/CTA 문구 2회 반복 | writer 프롬프트 §8/[필수 CTA] 삭제 + `_write_article` user 메시지의 CTA 요구 제거 → CTA는 파이프라인 하드코딩 1곳에서만 | `fae1cb5` |
| 2 | show_*=false 숨긴 섹션이 소스에 잔존(SEO 중복) | 섹션별 `render_*` 함수 분리 + `_show_flags` 단일소스. false면 **감싸는 태그 전체 생략**(JS display:none 아님). `SHOW_ARTICLE` 플래그 신설 | `93f2656` |
| 3 | 관련링크 `href="#"`(계산기 미배포 시 죽은 링크) | `CalculatorRepository.is_active()` 신설. `published_url` 있고 활성일 때만 링크, url 없으면 항목 생략, 0개면 헤딩도 생략 | `6bbeac1` |
| 4 | 같은 계산기 중복 발행(키워드만 다른 사실상 동일 글) | `MAX_ARTICLES_PER_CALCULATOR`(config) + `article_repository.count_active_articles(calculator_id)`. 발행 전 상한 비교 스킵 | `ab33988` |

**아키텍처 원칙(오늘 확립):**
- **상태값 문자열 비교는 Repository 계층에서만.** Pipeline/Engine은 `is_active()`/
  `count_active_articles()` 같은 헬퍼로만 판단(상태 종류 늘어도 Repository만 수정).
  비활성 집합 `INACTIVE_ARTICLE_STATUSES = {"삭제됨","휴지통","발행취소"}`는 repo 내부.
- **HTML 생성 경로는 `generate_html()` 단일.** 계산기 관리/미리보기/파일저장/GitHub
  Pages/WordPress 전부 `generate_calculator()`→`generate_html()` 공유.

**실환경 검증:**
- 신규 발행글: CTA "계산기 사용하기" **1회**, 숨김 섹션(sm-article/faq-card/related-card/
  adsense/cpa) **HTML 부존재**, `internal_link_engine` 죽은 링크 **0**, `calculator_id`
  정상 저장.
  (참고: 본문 내 `href="#"` 3개는 AI가 쓴 §7 "관련 계산기" 플레이스홀더 — 백로그의
  프롬프트 §7 이슈, 이번 범위 밖.)
- 상한 검증: 같은 계산기 재실행 → `dup=2` 스킵 + 다른 계산기 발행. 그 글을 "삭제됨"으로
  전환 → `count_active_articles=0` → 재실행 시 해당 계산기 **재포함·발행** 확인.

---

## Part 4 — WordPress 글 수정 기능 (2차)

**목표:** 발행된 글을 대시보드에서 수정(제목/본문/요약) → WordPress에 반영.

**수정:** — `5f621c0`
- `publisher.update_post(cfg, wp_post_id, title=None, content=None, excerpt=None)`:
  `POST /wp-json/wp/v2/posts/{id}`. **None=미전송(수정 안 함) / ""=전송(비움)** 구분.
  성공 `{success:True, wp_post_id, link, modified, status}` / 실패 `{success:False, error}`
  (예외 감싸 크래시 없음).
- **WordPress REST 직접 호출은 `publisher.py`에만**(update_post/_wordpress_api). 대시보드는
  `publisher.update_post`만 호출.
- `VALID_STATUSES`에 "수정됨" 추가. 대시보드 발행목록 `✏️수정` UI: `wp_post_id` 있는
  글만 편집, **success=True일 때만** 상태값="수정됨" 전환 + `append_history("update",
  {wp_post_id, modified, operator:"dashboard"})`. 실패 시 로컬 DB/history 미변경.

**실환경 검증:** 제목 수정 WP 반영(`modified` 갱신), excerpt `""`→raw 비움/`None`→raw
유지(context=edit raw로 확정), 존재하지 않는 post_id→`success:False`+404 error 크래시
없음·로컬 미변경, history `[publish, update]` append.

**미포함(TODO 주석으로 코드에 명시):**
- 동시 수정 감지(낙관적 잠금): 저장 직전 WP `modified` 조회 후 편집 시작 시점과 비교.
- 본문 편집 UI 개선(미리보기→수정→저장 흐름, 긴 본문 가독성).

---

## 알려진 제약 / 후속

- `sheets_adapter.insert()` 헤더 자동추가 미지원 → 새 필드는 시트 헤더 수동 추가 필요.
- 계산기 미배포(`published_url` 없음) 시 관련 계산기 내부링크는 생략됨(정상). 계산기
  canonical URL 정책은 GitHub Pages 배포 또는 WordPress 페이지화 결정 필요.
- 본문 §7 "관련 계산기"는 AI가 `href="#"` 플레이스홀더로 작성 → 프롬프트 §7 개선 필요.
- WordPress 글 **삭제**는 미구현(3차): article 상태 "삭제됨"은 현재 DB만 바뀌고 실제
  WP 글은 남음. 3차에서 `publisher.delete_post`(휴지통 이동) + 대시보드 삭제버튼 배선.
