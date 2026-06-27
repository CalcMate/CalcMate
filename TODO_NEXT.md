# TODO_NEXT.md — 향후 개선 과제

작업일 기준: 2026-06-21 · 우선순위: 🔴 즉시 / 🟠 단기 / 🟡 중기 / ⚪ 장기

---

## 🔴 즉시 (운영 재개 선결)

1. **Google Sheet/Drive 서비스 계정 재공유**
   - 시트(`13wz-fd...`)·Drive 루트 폴더를 `blog-982@blog-499303.iam.gserviceaccount.com`에 **편집자**로 공유.
   - 현재 403 → 헬스체크 CRITICAL 실패로 파이프라인 중단 상태. (코드 무관, 외부 권한 문제)
2. **노출됐던 Gemini 키 재발급**
   - 과거 `test_img.py`(삭제됨)에 하드코딩됐던 키가 `secrets.yaml`/`config.yaml`에 잔존. 폐기 후 신규 발급.

---

## 🟠 단기

3. **AI Provider 입력/출력 토큰 반환 확장**
   - `ai_provider`의 3개 provider `chat()`이 (text, total_tokens)만 반환 → 입력/출력 분리 반환으로 확장.
   - 확장 시 `_process_one`에서 `budget.record(model, in_tokens=, out_tokens=)` 호출 → 비용 정확도 완성(BudgetTracker는 이미 지원).
4. **임베딩 비용 집계**
   - `duplicate_checker`의 `text-embedding-3-small` 토큰을 budget에 기록(현재 누락).
5. **스케줄러 ↔ 수동 실행 락 통합**
   - `run_once`(수동)도 스케줄러와 동일한 파일 락을 확인/획득하도록 하여 동시 발행 충돌 원천 차단.
6. **보안 하드닝**
   - API 키를 환경변수/secrets로 일원화(config.yaml 평문 제거).
   - git 도입 시 `.gitignore`에 `config.yaml`, `credentials.json` 추가.

---

## 🟡 중기

7. **수집기 완성**
   - `collector/finance.py`, `affiliate.py` 실제 구현(현재 stub) 또는 factory 등록 해제.
   - `calculator` 수집용 `calculators` 시트 데이터 입력 가이드.
8. **DLQ ↔ 상태전이 통합**
   - `main._check_dlq`(파일 카운터+알림)와 `ArticleRepository.increment_fail`(상태 "재처리대기" 전이)을 일원화.
   - 재처리대기 항목을 다음 실행/스케줄러에서 자동 재시도.
9. **내부 링크 생성**
   - `writer`에 전달되는 `related=[None,None,None]` 하드코딩 → 최근 발행/유사 글 기반 내부링크 자동 구성.
10. **운영로그 시트 컬럼 확장**
    - 스케줄러 `history.jsonl`의 예약/실제/지연/결과를 운영로그 시트에도 반영(스키마 마이그레이션 포함).
11. **대시보드 score_weights 편집 UI**
    - `config/score_weights.yaml`(strategist가 로드)을 대시보드에서 직접 편집.

---

## ⚪ 장기 / 확장

12. **DB/Storage 어댑터 확장**
    - `postgres_adapter`, `s3_adapter` 실제 구현(현재 stub) → 시트 의존 탈피, 운영 규모 확장.
13. **멀티 사이트 운영 고도화**
    - `sites` 탭 기반 사이트별 AI 프로필/WP 프로필/슬롯 스케줄 분리 운영.
14. **app_factory(계산기/템플릿) 재설계**
    - 제거된 `queue/template_repository` 자리에 실제 사용 흐름이 생기면 재도입(시트 탭은 이미 존재).
15. **비용/성과 리포트 자동화**
    - 전략회의실 분석을 스케줄러와 연동해 일/주간 자동 리포트 발송(Telegram).
16. **테스트 스위트**
    - json_utils/scheduler/BudgetTracker/config_loader 단위 테스트를 `tests/`로 정식화(pytest).

---

## 🟠 단기 (운영센터 UI 후속)

17. **장시간 작업 비동기화** — 대시보드의 '파이프라인 1회/발행 1건/즉시발행'은 현재 동기 실행(화면 블로킹). 백그라운드 실행(subprocess/큐)으로 전환해 UI 응답성 확보.
18. **즉시발행 ↔ 스케줄러 락 공유 검증** — 별도 프로세스(run_scheduler.bat 가동 중) + 대시보드 즉시발행 동시 상황의 락 경합 실환경 테스트.
19. **칸반 드래그/액션** — 작업 보드에서 상태 수동 이동·재처리 트리거(현재는 보기 전용).
20. **운영센터 자동 새로고침** — 홈 KPI/서비스 상태도 옵션 자동 갱신(현재 수동/탭 진입 시 갱신).

## 🟡 중기 (v12.0 플랫폼 확장 후속)

21. **MODEL_EDITOR 갱신** — `claude-3-5-sonnet-latest`(retired) → `claude-sonnet-4-6`로 교체(설정 또는 config). 현재는 GPT fallback.
22. **App Factory 계산기 → 실제 발행 연결** — 생성된 HTML 템플릿을 WordPress 페이지/포스트로 발행하는 경로(calculator collector·publisher 연계).
23. **AI Workspace 함수호출(tool-use) 고도화** — 현재는 컨텍스트 첨부 방식. provider tool-calling으로 파일 자동 읽기/수정 루프(여전히 백업+확인 게이트 유지).
24. **App Factory 멀티턴 품질 루프** — 검수 AI로 생성 HTML 자동 점검·수정 1회.
25. **AI Pipeline 실시간 상태 영속화** — 로그 파싱 대신 `_process_one`에서 단계 상태 파일 기록(옵션, 비behavioral)으로 정확도 향상.
26. **Gemini 유료 전환/쿼터** — 2.5-pro 쓰려면 결제 키 필요(현재 free 429).

## 🟢 재검증 후 차기 과제 (2026-06-21)

27. **json_utils shim 단계적 제거** — 신규 코드는 `modules.utils.parser` 직접 사용. app_factory/ai_workspace 등 shim 경유 import도 점진 이전 후 shim 제거.
28. **MODEL_EDITOR 갱신**(claude-sonnet-4-6) — retired 모델 교체로 STEP8 fallback 제거.
29. **대시보드 AI 호출 비동기화** — 즉시발행/파이프라인/App Factory의 동기 블로킹 해소.
30. **사이트별 설정 편집 UI** — 생성 후 AI 프로필/WP 계정/슬롯을 사이트별로 수정(현재 생성 시에만 지정).

## 🟠 단기 (대시보드 리팩토링 후속)

31. ~~score_weights 키 정합화~~ — ✅ **완료(2026-06-21)**: `_load_weights`가 `_score` 키로 정규화하여 `compute_final_score` 정상화. (검증 72.0)
32. **로그 페이지네이션/검색** — 실시간 로그에 키워드 검색·날짜 필터 추가.
33. **대량 발행 진행률 표시** — 마스터 발행 시 건별 진행 상황(스피너→프로그레스) 표시.

## 참고: 이번 작업으로 해결 완료된 항목

- Gemini deprecated SDK / WordPress 키 혼재 / 단건 처리 / 비용 근사(모델별로 개선) / JSON 파싱 산발 / 무음 except / dead code 5종 / 대시보드 비용·오류 탭 / 발행 시간 슬롯 스케줄러 / schedule 모드 백업 버그 / Pillow 미선언 / 사이트·계산기 생성 마법사 / 운영센터 홈·빠른실행·칸반·즉시발행·발행방식 통합 — **모두 처리됨**(상세 CHANGELOG_AI.md, UI_REPORT.md).
