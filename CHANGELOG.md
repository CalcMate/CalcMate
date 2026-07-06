# CHANGELOG

> 계산기 품질·Registry 서브시스템의 주요 마일스톤. git 커밋 기준. 최신이 위.
> (전체 커밋: `git log`. AI 안정화 이력은 `CHANGELOG_AI.md` 참조.)

---

## v6 — Score/Gate 책임 분리 + 문서 체계 (2026-07-06)
실환경 E2E(작업지시서 F)에서 발견한 구조적 버그 수정 + 문서 정비.
- `d580d07` S1 예시 count 제거 + S4/S6 Gate 경계 가드 — Score/Gate 책임분리 완결
- `fa76e9a` S3(적용연도) evergreen 계산기 면제 — registry content.evergreen 연동
- `13ff0d4` S2 루브릭을 G8과 분리(법적근거 존재판정 제거) + critical→major
- `50353b9` App Factory 영문 slug 직접 입력 + calculator_index.json(식별자/표시 분리)
- `82bf9f7` 코드 정리(죽은 코드 제거) + docs/ 5종 문서화
> 핵심: S1/S2/S3가 "Gate가 확정한 존재/count를 GPT가 재판정"하는 동일 습관 → 실환경에서만 드러남.

## v5 — Registry 2.0 Phase C/D (2026-07-05~06)
Registry가 계산기 메타데이터 단일 소스로 완성.
- `a59eac3` registry_auto.yaml + 통합 merge 로더(큐레이션 우선), 3개 로더 위임
- `fa15024` save_app이 registry_auto.yaml에 자동 엔트리 기록
- `b484ea5` BLOCK_UNVERIFIED_LEGAL 정책 게이트 — legal 미검증 발행 차단 + 자동 해제
- `8b7c374` _legal_basis_block null-safe + legal 미확정 모드 블록
- `8349c75`/`fd0ed87` Phase D — _RELATED + compute 분기 하드코딩 폴백 **완전 제거**

## v4 — Calculator Registry 2.0 Phase A/B (2026-07-05)
- `3ba364a` legal_basis.draft.yaml schema_version 2 — 데이터 구조 신설(Phase A)
- `d906886` 계산기 생성물 스냅샷 회귀 하니스 + 골든(Phase B 2-a)
- `8ec5af2`/`61bf7a4` compute 분기·_RELATED을 registry로 이관 + 폴백(Phase B 2-b/2-c)

## v3 — legal_basis + G8 결정론 법적근거 (2026-07-05)
- `42f9a58`/`be81bfa` legal_basis 7종 사람 검증 데이터
- `61b7196`/`a95a2ca` writer에 검증 법적근거 "그대로 인용" 주입 + 표준 면책
- `64812d0` G8 결정론적 법적근거 검증 Gate 신설 · `b4e87aa` 약칭 매칭 수정
- `d00fbd1` forbidden_articles 통합 + forbidden_phrases

## v2 — 품질 파이프라인 Gate→Score→Retry→HOLD (2026-07-04~05)
- `c517242`/`c030c3b` Gate→Score→Rewrite Contract 발행 품질검수(QUALITY_STANDARD v1.2)
- `851b2a5` writer를 품질 게이트 v1.2에 정렬
- `f0661f7`/`01da15b` 후보 상한 + HOLD 재평가(품질보류) + Critical 반복실패 Telegram 알림
- `e6a497d` 기사 스냅샷 1회 로드로 sheet read 절감

## v1 — WordPress CRUD + 계산기 콘텐츠 배선 (2026-07-04)
- `f0a1947`/`6cc37af` WordPress 휴지통 삭제 + 복원
- `5f621c0` 발행 글 수정(update_post + 대시보드 UI)
- `e489eb1` WordPress 삽입 위젯을 app_generator(v2) 엔진으로 통일
- `ab33988` 계산기당 중복 발행 방지 · `6bbeac1` 죽은 관련링크(href="#") 제거

---

> 그 이전(v12 Lite 리팩토링, Sprint 2A/2B, Secrets 분리 등)은 `MIGRATION_NOTES.md`,
> `SPRINT_2A_REPORT.md`, `SPRINT_2B_REPORT.md`, `CHANGELOG_AI.md` 참조.
