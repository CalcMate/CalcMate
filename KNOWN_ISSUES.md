# KNOWN ISSUES — 알려진 문제

> 현재 인지된 제약/문제. 각 항목: 원인 · 영향 · 우회 · 향후 개선.
> 관련: [BACKLOG](BACKLOG.md) · [MASTER_ROADMAP](MASTER_ROADMAP.md)

---

## 1. legal_basis 수동 입력 (설계상 의도)
- **원인**: 법령/조항은 AI에게 조사시키면 환각(잘못된 조항 인용)이 재발. 실제로 퇴직금을 근로기준법 제34조로
  인용하는 등 환각 관측됨.
- **영향**: 신규 계산기는 사람이 legal을 검증·입력하기 전까지 발행 불가(품질보류 HOLD).
- **우회**: 없음 — 의도된 안전장치. legal은 사람이 law.go.kr 등으로 검증.
- **개선**: 법령 자동 감지(BACKLOG HIGH)는 "변경 알림" 용도이지 자동 입력이 아님. 검증은 계속 사람.

## 2. Score 변동성
- **원인**: GPT Score(S1~S6)가 실행마다 요동(normalized 59~85 관측). S5(고유정보)가 자주 저점.
- **영향**: 법적으로 정확하고 Gate를 통과한 글도 특정 차원이 낮아 WARN/REWRITE 될 수 있음.
- **우회**: WARN(≥80)은 발행되므로 대부분 통과. Retry로 재생성.
- **개선**: 데이터 축적 후 WARN 임계 또는 writer 콘텐츠 개선 판단(BACKLOG HIGH). 지금 임계를 낮추면 노이즈
  보정과 루브릭 수정이 섞여 추적 어려움 → 분리 대응.

## 3. 실업급여 — 복합 수급요건 미산출
- **원인**: 계산기는 급여액만 계산하고 180일·수급자격 등 요건은 산출하지 않음(설계).
- **영향**: 사용자가 "받을 수 있다"로 오인할 여지.
- **우회**: forbidden_phrases(받을 수 있습니다/지급됩니다)로 확정형 표현 차단 + G8. writer는 "가능성/심사" 표현.
- **개선**: 요건 체크리스트는 계산기 범위 밖 — 콘텐츠 안내로만 처리.

## 4. 연말정산 — 간이 근사 계산
- **원인**: 누진세율·항목별 세액공제 미반영 단순 근사(total_income - deductions).
- **영향**: 실제 정산 결과와 차이.
- **우회**: registry `content.content_caveat: crude_estimate` + 강한 면책 문구 강제(홈택스/회사 정산과 다를 수 있음).
- **개선**: 정밀 세액 엔진은 별도 트랙(우선순위 낮음).

## 5. 4대보험 — 요율 하드코딩
- **원인**: 국민연금 4.5%/건강 3.545%/고용 0.9%가 계산 formula에 박혀 있음.
- **영향**: 요율 고시 변경 시 글 재작성이 아니라 formula 코드를 직접 갱신해야 함(연 1회).
- **우회**: registry `content.evergreen:false/update_cycle:yearly` 표식.
- **개선**: 요율 자동 업데이트(BACKLOG HIGH).

## 6. WordPress 실서버 미구축
- **원인**: 현재 로컬 Laragon `salarymate.test`만. 실서버 미배포.
- **영향**: 발행은 로컬에서만 검증됨. 계산기 published_url 미확보 → 관련 계산기 내부링크 후보 부족 가능.
- **우회**: 로컬 E2E로 CRUD/발행 전 과정 검증 완료.
- **개선**: 실서버 구축 + GitHub Pages 배포로 canonical URL 확보(BACKLOG MEDIUM).

## 7. needs_human_legal 플래그 의미 오류 (무해)
- **원인**: 7종 registry가 전부 `needs_human_legal: true`(Phase A 일괄부여 — 실제로는 검증완료).
- **영향**: 플래그만 보면 "미검증?" 오해 소지. **동작에는 문제없음**(`_legal_unverified`가 실제 legal 데이터
  존재로 판단하므로 검증완료로 취급).
- **우회**: 불필요(동작 정상).
- **개선**: 다음 legal_basis.draft.yaml 수정 시 7종 `false`로 정정(BACKLOG MEDIUM).

## 8. 관련카드 [:4] cap — 일부 계산기 미노출 (잠재)
- **원인**: `_related_items_v2`가 관련카드를 `[:4]`로 자름. 순서상 연말정산/육아휴직은 항상 cap 뒤.
- **영향**: 현재 이 둘은 관련카드로 렌더되지 않음(무증상).
- **우회**: 불필요.
- **개선**: cap을 4→5/6으로 올리면 card_label override가 처음 노출 → 그때 7종 표시명 재검증 필요.

## 9. 대시보드 Schedule 탭 자동 새로고침 불안정 (구조적 한계)
- **원인**: `location.hash` 기반 탭 감지 방식이 브라우저마다 fragment 새로고침 동작이 달라 자동 갱신이
  작동하지 않는 경우 있음. signal-file polling 방식이 제안됐으나 미구현.
- **영향**: 스케줄러 실행 중 대시보드 Status 표시가 실시간 갱신 안 될 수 있음.
- **우회**: 대시보드 수동 F5 새로고침 후 확인.
- **개선**: signal-file 기반 polling 전환(BACKLOG MEDIUM).

## 10. 연말정산 — REWRITE 한도 초과 품질보류 (운영 발생)
- **원인**: 연말정산 계산기가 writer 생성 시 Score 임계 또는 Gate 반복 실패로 `MAX_TOTAL_RETRY` 소진.
  간이 근사 계산(#4)으로 G1(정확성 관련) 또는 S 차원에서 저점 가능성.
- **영향**: 연말정산이 발행 불가 상태(HOLD). 기존 발행글은 유지되나 신규 발행 불가.
- **우회**: 없음. prompt_version 변경 후 재평가로 HOLD 해제 가능.
- **개선**: writer 프롬프트 격리 실험 후 개선 적용(BACKLOG HIGH). docs/experiments/에 실험 결과 저장 예정.

## 11. 실험 cleanup 시 WordPress 게시물 미삭제 (운영 관측)
- **원인**: `session_experiment_cleanup` 실행 시 Google Sheet 행만 삭제하고 WordPress 게시물은
  삭제하지 않음. 이 시점에 WP에 발행된 글이 있으면 고아(ORPHAN_WP) 상태로 남음.
- **영향**: Content Sync에서 ORPHAN_WP 경고 발생. WP 고아 게시물이 공개 상태로 잔존할 수 있음.
- **우회**: ORPHAN_WP 감지 시 WP 게시물 직접 확인 후 휴지통 이동.
- **개선**: cleanup 단계에서 Sheet 행 삭제 전에 해당 wp_post_id의 WP 게시물도 함께 삭제
  (하나의 원자적 작업으로 처리). 우선순위 LOW~MEDIUM.
- **최초 관측**: 2026-07-16 — WordPress Post ID 39 (2026-07-12 실험 생성물).

## 12. SEO 제목 생성 — "세금" 등 추상적 키워드 미반영
- **원인**: `generate_seo`가 일부 추상적/짧은 키워드(예: "세금")를 제목에 반영하지 못하고
  기존 발행 제목과 동일한 제목을 생성 → dup 필터링됨.
- **영향**: 해당 키워드 후보가 소진 처리됨 (연말정산 테스트에서 7건 중 1건).
- **우회**: 없음. 롱테일 키워드 풀이 넓으면 영향 미미.
- **개선**: dup 재시도 로직 도입 시 함께 해결 예정 (BACKLOG MEDIUM).
- **최초 관측**: 2026-07-17 (연말정산 7키워드 검증).

## 13. SEO 제목 생성 — 유사 키워드 배치 내 수렴
- **원인**: "계산"과 "계산 방법"처럼 유사한 키워드가 동일 제목으로 수렴.
- **영향**: 배치 내 유니크 제목 수 감소 (경미).
- **우회**: 없음.
- **개선**: dup 재시도 로직 도입 시 함께 해결 예정 (BACKLOG MEDIUM). #12와 동일 해법으로 묶어서 처리.
- **최초 관측**: 2026-07-17.

## 14. SEO 제목 길이 규칙 미준수
- **원인**: 프롬프트에 28~40자 지시했으나 실제 생성 제목은 17~21자 — 모델(GPT-4o-mini)이
  길이 규칙을 안정적으로 따르지 않음.
- **영향**: SEO 노출 최적화 관점에서 제목이 다소 짧음 (기능 장애 아님).
- **우회**: 없음.
- **개선**: 프롬프트 문구 보강 또는 길이 미달 시 post-processing 검토 (BACKLOG LOW).
- **최초 관측**: 2026-07-17.

## 15. 연말정산 G1 글자수 미달 → 전체 계산기 시스템 문제로 확장 확인
Status: 🟡 Monitoring

- **원인**: G1 REWRITE 지시가 threshold(1800)를 목표처럼 사용하여
  writer가 최소 통과선으로 수렴하는 구조적 문제. 연말정산 전용이 아니라
  7개 계산기 전체에서 발생 (당초 가설과 다름 — 연말정산은 오히려 평균 1,915자로 양호)
- **해결(F1)**: REWRITE 지시 기준을 threshold(1800)에서 writer target(1900)으로
  변경 (`publish_quality.py`, `config.yaml` WRITER_TARGET_LENGTH 추가)
- **F1 검증**: 8건(4계산기×2키워드) 중 SUCCESS 6 / PARTIAL 1 / FAIL 1 (75%)
  - Threshold 수렴 패턴(1812→1805→1807류) 8건 중 0건 확인 — 핵심 문제는 해소
  - 잔여 실패는 LLM 고유 출력 변동성(±300~500자)으로 추정, threshold 수렴과는 다른 원인
- **F2**(섹션별 최소량 명시)는 불필요 판정, 보류
- **다음 확인**: 로컬 자동 스케줄 실제 운영에서 10~20건 추가 관찰 — threshold 수렴
  재발 0건 + G1 실패 재현 안 됨 확인되면 Resolved로 이동
- **최초 관측**: 2026-07-18 (연말정산), 조사 확장: 2026-07-18 (전체 계산기)

## 16. G7 AI 문체 표현 잔존 ("알아보도록 하겠습니다" 등)
- **원인**: writer가 전형적 AI 문체 표현을 간헐적으로 생성. 프롬프트 금지 목록에 있으나 완전 차단 안 됨.
- **영향**: minor severity. 현재 retry로 대부분 소화되며 발행 HOLD까지 이어지는 경우 드묾.
- **우회**: 불필요 (자동 소화).
- **개선**: 우선순위 낮음, 관찰만. 반복 패턴 누적 시 금지 목록 보강 검토.
- **최초 관측**: 2026-07-18.

## 17. G8 forbidden_articles — 계산기 HTML·DB faq 경로 미적용 (구조적 사각지대)
- **원인**: G8 게이트(`_check_g8`)는 writer가 생성한 `body_html`만 검사. 계산기 HTML은
  `app_generator._faq_items_v2()`가 DB `faq` 필드를 직접 렌더링하고, `article_content` 필드도
  직접 HTML에 삽입됨 — G8 적용 경로 밖.
- **영향**: DB faq·article_content에 법령 오류가 있으면 계산기 HTML에 그대로 노출.
  (예: 퇴직금 "근로기준법 제34조", 연말정산 "소득세법 제55조·제63조", 육아휴직 "근로기준법 제74조·고용보험법 제40조")
- **우회**: DB 직접 수정(`calculator_repository.update`) + HTML 재생성. R8에서 3개 계산기 수동 패치.
- **개선**: 계산기 HTML 생성 시 DB faq·article_content에도 forbidden_articles 스캔 추가 (BACKLOG).
  또는 계산기 콘텐츠 생성 파이프라인에 검증 단계 삽입.
- **최초 관측**: 2026-07-19 (SP-2 조사).

---

## 해결된 이슈 (이력 보존)

### R1. 텔레그램 알림 침묵 (2026-07-16 해결)
- **원인**: 슬롯 실행 후 알림 호출 위치 누락 — `telegram_notifier.send()` 연결선이 scheduler.py에 없었음.
- **해결**: scheduler.py에 발행 성공 이벤트 후 `send()` 호출 추가. 슬롯-레벨 이벤트
  (모든 후보 HOLD / 후보 소진) 알림도 함께 추가.

### R2. 대시보드 Schedule 이력 소실 (2026-07-16 해결)
- **원인**: `today_schedule.json` 재생성 시 기존 슬롯 결과를 덮어써서 이전 실행 결과가 사라짐.
- **해결**: 스케줄러가 슬롯 결과 저장 시 기존 `today_schedule.json`을 로드해 결과를 병합한 뒤 저장.

### R4. G4 연말정산 반복 HOLD — 예시 인식 오류 해결 (2026-07-18)
- **원인**: `publish_quality._count_examples`의 정규식이 "만원/억원" 단위 금액과
  "또 다른 예로" 같은 두 번째 예시 표현을 인식하지 못함. writer는 실제로
  요구사항(예시 2개)을 정확히 생성했으나 게이트가 오판정하여 REWRITE 3회
  소진 후 HOLD. 노동법 계산기 6개는 소액이라 기존 패턴(80,000원)과 우연히
  맞아 문제가 드러나지 않았음.
- **해결**: `_count_examples`의 마커/수치 정규식 확장 (writer/legal_basis/DB 변경 없음).
  G5 Adaptive Gate와 동일하게 품질 기준 완화가 아니라 게이트 판정 정확도 개선.
- **검증**: false negative 3건, false positive 5건, 기존 6개 계산기 회귀 6건,
  실제 writer 출력 E2E 2건 전부 통과.

### R5. G1 글자수 미달 — Rewrite 목표 수렴 문제 해결 (2026-07-18)

- **원인**: 특정 계산기 문제가 아니라 7개 계산기 전체에서 발생한 구조 문제.
  G1 threshold(1800자)이 Rewrite 지시 목표로 사용되면서 writer가 최소 통과선으로 수렴.
  G1 실패 시 `"본문 N자 → 1800~2500자 필요"` 지시가 threshold를 목표값처럼 제시하여,
  모델이 1800~1850자 근처로만 재생성 후 재실패하는 루프 유발.
- **조사 결과**: 56개 runs(7계산기×8회) 기준 연말정산 avg=1,915자로 오히려 양호.
  주휴수당(avg=1,696), 육아휴직(avg=1,736)이 더 높은 미달률. 연말정산-특수 문제가 아니었음.
- **해결**: G1 REWRITE 지시를 threshold(1800) 기준에서 writer target(1900) 기준으로 변경.
  `"본문 N자 → 최소 1,900자(가시 텍스트) 필요, M자 추가 작성 필요"`.
  `QUALITY_GATE.WRITER_TARGET_LENGTH: 1900`으로 config에서 조정 가능.
- **영향**: gate threshold(1800)는 안전망으로 유지. writer target과 rewrite 목표를 정렬.
- **성격**: 품질 기준 변경 아님. 생성 피드백 목표 정렬 문제.

### R10. 실업급여 Phase 1 — 계산 로직 전면 교체 (2026-07-19)

- **원인**: 기존 `computeResult`가 `avg_daily_wage × 0.6`만 계산 — 상한/하한 클램프 없음, 소정급여일수 미산출, total_benefit 미반환, 입력 오류 처리 없음.
- **발견**: 실업급여 전수 검증 (UB-1~9 진단).
- **해결**:
  - UB-1(major): `avg_daily_wage ≤ 0 || age ≤ 0 || employment_months ≤ 0` → `return null`
  - UB-3(critical): `employment_months < 6` → `daily_benefit=0, total_benefit=0 + notice("고용보험법 제40조")`
  - UB-4(critical): 상한 클램프 `min(raw_daily, 66,000원)` (고용노동부 고시)
  - UB-5(critical): 하한 클램프 `max(raw_daily, 최저임금 × 8 × 0.8)` = 64,192원 (고용보험법 제46조 제2항)
  - 소정급여일수 2차원 테이블 (고용보험법 별표1, 2019년 개정 이후): 가입기간 × 연령(50세 미만/이상) → 120~270일
  - `total_benefit = daily_benefit × benefit_days` 출력 추가
  - `_formula` 문자열 반환 (계산 과정 표시)
- **수치 소스**: `docs/legal_basis.draft.yaml` unemployment-benefit.benefit_amounts/benefit_days_table (연 1회 갱신 체계)
- **아키텍처**: `modules/app_generator._compute_js()`에 `slug=="unemployment-benefit"` 전용 분기 추가.
- **테스트**: `tests/test_unemployment_benefit_compute.py` 15케이스 영구 등록. ALL PASS.
  - 경계 케이스: 5개월 수급불가, 6개월 경계, 49/50세 경계, 10년 이상 최대 일수
  - 클램프 케이스: 상한 초과, 하한 미만
- **회귀**: 기존 22케이스(주휴수당 11 + 퇴직금 11) ALL PASS.
- **이번 범위 아님**: Phase 2·3는 R10-P2, R10-P3 참조.

### R10-P2. 실업급여 Phase 2 — 콘텐츠 정확성 (2026-07-19)
- **UB-2**: DB faq[0/2/6] + article_content "최대 300일" → "가입기간·연령에 따라 120~270일 (고용보험법 별표1)"
- **UB-9**: DB faq[4] 법령 근거 보강 — 고용보험법 제40조/제45조/제46조/별표1 명시
- **예시 금액**: `compute_ub()` 함수 실행 결과값만 인용 (수기 계산 금지 원칙 확립)
- **"최대 300일" 오류 표현 잔존**: 0건 확인
- **기준 사례**: `docs/reference_cases/unemployment_benefit.md` 10대 케이스 + 연 갱신 절차

### R10-P3. 실업급여 Phase 3 — UX 마무리 (2026-07-19)
- **UB-6**: `_formula` 케이스별 단계 표시 — 하한/상한/정상 3가지 분기
  - 하한: "기초일액 48,000원 → 하한액 적용(64,192원) → 64,192원/일 × 150일 = 9,628,800원"
  - 상한: "기초일액 72,000원 → 상한액 적용(66,000원) → 66,000원/일 × 150일 = 9,900,000원"
  - 정상: "기초일액 66,000원/일 × 150일 = 9,900,000원"
- **UB-7**: notices 우선순위 구현 — 6개월 미만(수급 불가) return 이후 상한/하한 notice 불가, 모순 notice 없음
- **UB-8**: `legal_basis.draft.yaml` 외부화 최종 확인 — daily_max=66,000·min_wage=10,030·테이블 5×2행 yaml에서 로드
- **테스트**: 22케이스 추가 (UB-6 3케이스·UB-7 3케이스·기존 15 → 총 22케이스), 전체 44/44 PASS

### R9. SP-6 상여금/초과근무수당 포함 여부 설명 오류 해결 (2026-07-19)

- **원인**: 퇴직금 계산기 HTML 주의사항 및 FAQ 4번에 "초과 근무수당이나 상여금은 포함하지 않아야 합니다"라고 안내. 근로기준법 제2조제1항제6호·시행령 제2조 기준과 정반대.
- **법령 근거**: 평균임금 = 퇴직 전 3개월 지급 임금 총액 ÷ 3개월 총일수. **포함**: 기본급 + 연장·야간·휴일 가산수당 + 통상 지급 상여금(연간총액의 1/12). **제외**: 임시 지급 수당, 1회성 급부 (시행령 제2조).
- **영향**: 사용자가 올바른 평균임금 금액을 입력해도 계산기 안내가 오류를 유발하도록 유도 → 계산 결과 신뢰도 훼손. major급.
- **해결**:
  - DB `faq[4].answer`: 오류 서술 → 포함 항목 정확히 명시
  - DB `article_content` 주의사항·FAQ 4번: 동일 오류 교체
  - `legal_basis.draft.yaml` `writer_note`: 평균임금 산정 포함/제외 항목 명시 추가
  - severance-pay HTML 재생성 → 오류 문구 0건, 올바른 내용(연장·야간·휴일·상여금·근로기준법제2조·시행령제2조) 확인
- **회귀**: 22/22 PASS (SP-1~4 로직 무영향, 콘텐츠 수정만).

### R8. SP-2 폐지 법령 인용 오류 해결 — 3개 계산기 DB faq + article_content 수정 (2026-07-19)

- **원인**: 계산기 생성 초기 AI가 폐지·부정확한 법령을 인용하여 DB에 저장됨.
  G8 forbidden_articles가 writer body_html만 검사하는 구조적 사각지대로 인해 계산기 HTML에 그대로 노출(#17).
- **발견**: SP-2 조사 (퇴직금 품질 검증 2라운드). 계산기 HTML workspace + DB faq 전수 스캔.
- **해결**:
  - severance-pay DB `faq[5].answer`: "근로기준법 제34조" → "근로자퇴직급여보장법 제8조"
  - severance-pay DB `article_content`: 동일 오류 교체
  - 연말정산_환급액_계산기 DB `faq[5].answer`: "소득세법 제55조 및 제63조" → "소득세법 제137조(근로소득에 대한 연말정산)"
  - 육아휴직_급여_계산기 DB `faq[5].answer`: "근로기준법 제74조 및 고용보험법 제40조" → "고용보험법 제70조(육아휴직 급여)"
  - 육아휴직_급여_계산기 DB `article_content`: 동일 오류 교체
  - 3개 계산기 HTML 재생성 → forbidden 전수 재검증 ALL OK
- **조문 검증 근거**: `legal_basis.draft.yaml` (`verification_source: [law.go.kr, easylaw.go.kr]`)
  - 소득세법 제137조: "근로소득에 대한 연말정산" — 원천징수의무자의 과세기간 말 정산 절차
  - 고용보험법 제70조: "육아휴직 급여" — 30일 이상 육아휴직 피보험자 급여 지급 조항
  - (제55조·제63조·제74조·제40조는 해당 내용과 무관한 조문임을 법령 내용으로 확인)
- **스크립트**: `scripts/fix_sp2_faq.py`, `scripts/fix_sp2_article_content.py`, `scripts/regen_sp2_calcs.py`

### R7. 퇴직금 computeResult 경계값 버그 3종 해결 (2026-07-19)

- **원인**: JS `computeResult` 함수가 재직 1년 미만 조건 분기 없이 계산 → 1일 재직에도 퇴직금 표시(법적으로 지급 의무 없음). 날짜 미입력 시 0원 결과카드 표시. 음수/0 평균임금에 음수 결과 표시.
- **발견**: 퇴직금 계산기 품질 검증 2라운드 (계산기 품질 표준 v1.0 적용).
- **해결**:
  - SP-1(critical): `total_days < 365` → `severance_pay=0 + notices(근로자퇴직급여보장법 제8조)`
  - SP-3(major): `isNaN(s.getTime()) || isNaN(e.getTime())` → `return null`
  - SP-4(major): `avg_monthly_wage <= 0` → `return null`
  - 추가: 정상 케이스에 `_formula` 문자열 반환 (계산 과정 표시)
- **아키텍처**: date_based 계산기는 `_compute_js()` 하드코딩 분기에 직접 검증 로직 삽입. `compute_rules` 구조(주휴수당)는 date_based에 적용 안 됨 — `out.notices[]` 배열 구조는 공유.
- **테스트**: `tests/test_severance_compute.py` 11케이스 영구 등록. ALL PASS.
- **회귀 방지**: `tests/golden/calculator_snapshots.json` 업데이트 완료. severance-pay script.js 해시 고정.
- **잔여(미수정)**: SP-5(날짜 레이블 영문), SP-6(상여금 설명 오류) — 콘텐츠 재생성 또는 별도 배치로 처리. SP-2는 R8로 해결.

### R6. 주휴수당 computeResult 경계값 버그 3종 해결 (2026-07-19)

- **원인**: JS `computeResult` 함수가 주 15시간 미만 조건 분기 없이 계산 → 14시간 입력 시 28,000원 표시(법적으로 지급 불가).
  음수/0 시급 입력에도 결과 반환(UX 오류). 최저임금 경고 안내 없음.
- **발견**: 계산기 품질 표준 v1.0 경계값 검증(B-1/B-2/B-3) — 주휴수당이 기준 모델.
- **해결**:
  - B-1(critical): `compute_rules.min_weekly_hours: 15` → JS `if (weekly_hours < 15) { return 0 + notice }`
  - B-2(major): `compute_rules.positive_inputs` → JS `if (hourly_wage <= 0 || weekly_hours <= 0) { return null }`
  - B-3(major): `compute_rules.min_wage: 10030` → JS `out.notices.push(...)` (계산 차단 없음)
  - B-4(minor): `out._formula` 문자열 반환 → UI 계산 과정 표시
- **아키텍처**: `legal_basis.draft.yaml`의 `compute_rules` 필드(YAML 단일 진실 소스)
  → `app_generator._compute_validation_js()` → 생성 JS에 주입. 나머지 6개 계산기에 동일 패턴 적용 가능.
- **테스트**: `tests/test_weekly_holiday_compute.py` 11케이스 영구 등록 (7 핵심 + 4 SEO 정합성). ALL PASS.
- **회귀 방지**: `tests/golden/calculator_snapshots.json` 업데이트 완료. weekly-holiday-allowance script.js 해시 고정.

### R3. G5 내부링크 게이트 — Cold Start 순환 교착 (2026-07-18 해결)
- **원인**: 로컬 데이터 초기화(07-17) 이후 발행완료 기사가 0건이 되면서, 내부링크 최소 2개 요구(G5)가
  "발행할 기사가 없어 내부링크 후보도 없고, 내부링크가 없어 발행도 안 되는" 순환 교착에 빠짐.
  어제 dedup 범위 축소 배포가 더 많은 후보를 시도하게 해서 기존에 숨어있던 G5 전면 실패를 노출시킴(회귀 아님).
- **해결**: G5를 Adaptive 방식으로 변경. `required = min(valid_candidate_count, MIN_INTERNAL_LINKS)`.
  가용 후보가 적을 땐 요구치도 낮아지고(0건→0, 1건→1), pool이 2건 이상 쌓이면 자동으로
  정상 기준(2)으로 복귀. `href="#"` 데드링크 검사는 풀 크기와 무관하게 항상 적용.
  기존 Bootstrap Mode 분기를 Adaptive G5 수식 안에 통합(분기 3개→2개).
- **검증**: pool 0/1/1(inject 버그)/5/5(inject 버그)/dead-link 6케이스 단위테스트 전부 통과.
  E2E Cold Start부터 pool 0→1→2 연속 발행 확인 (wp_post_id 54→55→56).

---

## 4대보험 계산기 — ✅ VERIFIED (Phase 1~3 완료)

> 진단일: 2026-07-19 | Phase 1 완료: 2026-07-19 | Phase 2 완료: 2026-07-19 | Phase 3 완료: 2026-07-19
> 상세: `docs/reference_cases/four_insurances_diagnosis.md` | 기준 케이스: `docs/reference_cases/four_insurances_2026.md`
> 테스트: `tests/test_four_insurances_compute.py` 43케이스 ALL PASS

### FI-1 [Critical] ✅ 해결 — 장기요양보험 구현
- `health_insurance × 0.1296` 순서 엄수. 급여 직접 곱 방지 테스트 영구 등록.

### FI-2 [Critical] ✅ 해결 — 국민연금 상한/하한 클램프
- `clamp(salary, 390000, 6170000) × 0.045`. 경계 3점 + 극단값(20만원·1000만원) 테스트 등록.

### FI-3 [Critical] ✅ 해결 — total 4종 합산 + 내부 합계 검증 테스트
- `total = NP + HI + LTC + EI`. `_assert_total_equals_sum` 8케이스 parametrize로 영구 보호.

### FI-4 [Major] ✅ 해결 — 입력 검증
- `monthly_salary ≤ 0 → return null`.

### FI-5 [Major] ✅ 해결 — 산재보험 UI 안내 추가
- article_content 주의사항: "산재보험은 사업주가 전액 부담합니다 — 근로자 급여에서 공제되지 않음 (산업재해보상보험법 제13조)."

### FI-6 [Major] ✅ 해결 — faq[2] 건강보험 예시 교정 + 장기요양보험 신규
- faq[2]: 106,500원 → 106,350원. 장기요양 1만 3천 783원 예시 추가. total 26만 8천 500원 → 28만 2천 133원.

### FI-7 [Major] ✅ 해결 — faq[3] 고용보험 부담 비율 교정
- "각 보험료 절반씩 부담" → 국민연금·건강보험·장기요양은 절반씩, 고용보험 근로자 0.9%·사업주 0.9%+α, 산재보험 사업주 전액으로 정확히 구분.

### FI-8 [Minor] ✅ 해결 — _formula 구현 (Phase 3 강화)
- 케이스별(하한/상한/정상) 5단계 순서 표시. 장기요양 단계: "건강보험료 N원 × 12.96% = Y원" 형태(건강보험료 금액 명시). 테스트: `test_formula_stage_order`, `test_formula_ltc_shows_health_insurance_amount`.

### FI-9 [Minor] ✅ 해결 — notices 명시적 우선순위 구조 (Phase 3 강화)
- 별도 배열(`_np_notices`, `_si_notices`) + `[].concat(...)` 으로 순서 확정. 산재보험 notice 항상 마지막. 동시 발생 케이스 테스트: `test_notices_order_np_ceiling_with_sangjae`, `test_notices_order_np_floor_with_sangjae`.

### FI-10 [Minor] ✅ 해결 — legal_basis 외부화
- `docs/legal_basis.draft.yaml` four-insurances.insurance_rates 섹션 추가.
- `test_yaml_sync_constants`로 YAML↔Python 상수 동기화 자동 감지.

**2025년 기준표:**

| 보험 | 근로자 요율 | 상한/하한 | 출처 |
|---|---|---|---|
| 국민연금 | 4.5% | 기준소득월액 하한 390,000원 / 상한 6,170,000원 (2024.7~2025.6) | 국민연금법 제88조 |
| 건강보험 | 3.545% (총 7.09%) | 실질 상한 없음 | 국민건강보험법 제69조 |
| 장기요양보험 | 건강보험료 × 12.96% | — | 노인장기요양보험법 제9조 |
| 고용보험 | 0.9% | 상한 없음 | 고용보험법 제49조 |
| 산재보험 | 근로자 0% (사업주 전액) | 업종별 상이 | 산업재해보상보험법 제13조 |

---

## 연차수당 계산기 — ✅ VERIFIED (Phase 1·2 완료)

> 진단일: 2026-07-19 | Phase 1 완료: 2026-07-19 | Phase 2 완료: 2026-07-19
> 상세: `docs/reference_cases/annual_leave_allowance_diagnosis.md`

### 설계 범위 규정

이 계산기는 **"미사용 연차수당 금액 계산기"** — `daily_wage × unused_days` 공식.
사용자가 1일 통상임금과 미사용 연차 일수를 직접 입력. 연차 발생 개수 계산 없음.

### AL-1 [Critical] ✅ 해결 — 입력 검증 추가
- `if (daily_wage <= 0 || unused_days <= 0) return null;` 추가.
- 재사용 패턴: `weekly-holiday-allowance`, `severance-pay` 동일 구조

### AL-2 [Critical급] ✅ 해결 — 통상임금 정의 오류 정정
- 수정: "기본 일급만 기준" → "통상임금 = 기본급 + 고정수당 (시행령 제6조)"
- faq[3] + article_content HTML 두 위치 동시 수정. 잔존 0건 확인.
- 근거: 근로기준법 제2조제1항제5호, 시행령 제6조

### AL-3 [Critical급] ✅ 해결 — 지급 의무 오류 정정
- 수정: "지급되지 않을 수 있다" → "퇴직 시 의무 지급 (제36조 금품 청산). 제61조 촉진제도 시만 예외."
- faq[1] + article_content HTML 두 위치 동시 수정. 잔존 0건 확인.
- 근거: 근로기준법 제36조, 제61조

### AL-4 [Major] ✅ 해결 — 원칙-예외 구조 확립 + 제61조 요건 구체화
- 수정: faq[1]을 "원칙 → 예외" 구조로 재서술.
  - 원칙: "반드시 지급 (제60조제5항·제36조)"
  - 예외: 제61조 촉진제도 — 6개월 전 서면 통지 + 사용 시기 서면 지정 두 절차 모두 완료 시만 면제
- 일관성 3곳 확인: faq 배열 / article HTML FAQ 목록 / article 주의사항 본문 — 전부 동일 구조 PASS

### AL-5 [Minor] ✅ 해결 — notices 추가
- `unused_days > 25` 시 법정 상한 초과 경고 (근로기준법 제60조제4항) 표시.

### AL-6 [Minor] ✅ 해결 — _formula 추가
- "통상임금(일급) N원 × M일 = Y원" 계산 과정 표시.

### AL-7 [Minor] ✅ 해결 — "일급" 표현 통상임금 병기
- FAQ[2], article_content 계산 원리·결과 해설·form label·CTA 등 전위치 "통상임금(일급)" 병기.

### AL-8 [설계 확장 검토] — 연차 발생 개수 계산 (별도 트랙)
- 이 계산기는 미사용 연차수당 금액 계산기. 연차 발생 개수 자동 계산은 별도 트랙.
- 연차 개수 계단 구조: 1년=15일, 3년차부터 2년마다 +1일, 최대 25일 (21년차 이상).
- 핵심 엣지: 20년→24일, 21년→25일(상한), 22년→25일(유지) — 미래 구현 시 반드시 검증.

---

## 육아휴직급여 계산기 — 진단 완료 (수정 대기)

> 진단일: 2026-07-19 | 제도 기준일: 2024년 1월 1일 (6+6 특례 시행)
> 상세: `docs/reference_cases/parental_leave_diagnosis.md`

### 설계 범위 규정

현재 계산기는 **계산식 구조 자체가 법령과 무관** — 전면 재설계 필요.
올바른 설계: **예상 월 육아휴직급여 계산기** — 통상임금 입력, 일반(80%)/6+6 특례 분기.

### PL-1 [Critical — 설계] — 계산식 근본 오류
- 현재: `avg_monthly_wage × leave_months × (gov_pct + company_pct) / 100`
- 올바른: 통상임금 × 80% (하한 70만, 상한 150만) / 6+6 특례 100% (단계적 상한)
- 사용자가 "정부 지원 비율"을 직접 입력하는 구조 자체가 오류

### PL-2 [Critical — 설계] — 입력 구조 오류
- `government_support_percentage`, `company_policy_support_percentage`는 법령 고정값
- 사용자 입력이 아닌 코드에서 결정해야 함

### PL-3 [Critical] — FAQ[0] 자녀 연령 오류
- "출산 후 1년 이내" → 현행 **만 8세 이하(초등 2학년 이하)**
- 남녀고용평등과 일·가정 양립 지원에 관한 법률 제19조

### PL-4 [Critical] — FAQ[1] 수급 요건 오류
- 핵심 요건 **피보험단위기간 180일** 전혀 미언급
- "최저임금 미충족" 언급 → 수급 제외 요건 아님

### PL-5 [Critical] — FAQ[6] 육아휴직 권리 오류
- "추가 6개월 연장은 회사 정책에 따라 다를 수 있습니다"
- 육아휴직 1년은 **법적 권리** (남녀고용평등과 일·가정 양립 지원에 관한 법률 제19조)

### PL-6 [Critical — SP-8 재발] — FAQ[2] 코드 문자열 노출
- `avg_monthly_wage`, `government_support_percentage` 등 코드 변수명 4종 FAQ에 노출

### PL-7 [Major] — 상한·하한 미구현
- 일반 급여: 상한 150만원, 하한 70만원 없음

### PL-8 [Major] — 6+6 부모 육아휴직 특례 미구현 (2024년 1월 시행)
- 부모 모두 육아휴직 시 1~6개월 100%, 단계별 상한(200만~450만) 없음

### PL-9 [Major] — 입력 검증 없음
- null 반환, 음수/0 처리 없음 (AL-1 패턴 미적용)

### PL-10 [Major] — notices 없음

### PL-11 [Major] — _formula 미반환
- computeResult에서 `out._formula` 미설정

### PL-12 [Major] — 피보험단위기간 180일 경계 처리 없음
- 180일 미만 → 0 + notice 미구현 (UB-3 패턴)

### PL-13 [Major] — FAQ[7] 복귀 의사 사전 표명 오류
- "육아휴직 후 근무 복귀 의사를 사전에 밝혀야 합니다" — 법적 요건 아님

### PL-14 [Minor] — formula_engine 빈 문자열
### PL-15 [Minor] — C-13 원칙-예외 3곳 미준수

**상태**: Critical 6건 / Major 7건 / Minor 2건 — **Phase 1 (콘텐츠)부터 시작, Phase 2는 전면 재설계**
