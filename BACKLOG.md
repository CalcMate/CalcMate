# BACKLOG — 미완 작업

> 아직 하지 않은 작업. 우선순위 HIGH/MEDIUM/LOW. 착수 시 각 항목은 조사→보고→승인 게이트를 따른다.
> 관련: [MASTER_ROADMAP](MASTER_ROADMAP.md) · [KNOWN_ISSUES](KNOWN_ISSUES.md)

---

## 🔴 HIGH

| 항목 | 내용 | 근거 |
|------|------|------|
| **법령·요율 자동 감지** | 법령/요율 변경을 감지해 알림/갱신. 운영 시작 시 가장 먼저·자주 발생하는 유지보수 | 계산기·글 쌓이기 전 구축이 유리(권장 다음 Sprint) |
| **4대보험 요율 갱신 자동화** | 국민연금 4.5%/건강 3.545%/고용 0.9%가 formula에 하드코딩 → 연 1회 코드 갱신 필요(콘텐츠 갱신과 별개) | registry `content.evergreen:false/update_cycle:yearly`로 표식만 있음 |
| **Score 안정화** | normalized 실행간 변동(59~85), S5(고유정보) 저점. 데이터 축적 후 WARN 임계/writer 콘텐츠 판단 | 작업지시서 F 관찰 트랙(임계 섣불리 낮추면 노이즈보정·루브릭수정 혼선) |

## 🟡 MEDIUM

| 항목 | 내용 |
|------|------|
| **_LABELS / field_labels 이관** | 계산기별 라벨을 registry `field_labels`로 이관. 사람이 field_labels 채운 뒤 진행(현재 빈 {} placeholder) |
| **needs_human_legal 플래그 정정** | 7종 registry가 전부 `true`(검증완료인데 잘못 표시). 동작은 `_legal_unverified`가 실데이터로 판단해 무해. 다음 legal_basis.draft.yaml 수정 시 `false`로 정정 |
| **WordPress 실서버 구축** | 현재 로컬 salarymate.test만. 실서버 배포 + 발행글 published_url 확보 |
| **internal_link G5 부트스트랩** | 계산기 published_url 미확보(GitHub Pages 미배포)로 초기 발행글에서 G5 링크 후보 부족 가능 |
| **Telegram 미배선 이벤트 / 양방향** | daily_summary 등 일부 이벤트 미배선. 양방향은 설계(`TELEGRAM_BIDIRECTIONAL_DESIGN.md`)만 존재 |

## 🟢 LOW

| 항목 | 내용 |
|------|------|
| **통계 / 그래프 대시보드** | 발행량·품질·비용 시각화 |
| **검색 기능** | 대시보드 계산기/글 검색 |
| **루트 문서 정리** | 구버전 루트 `ARCHITECTURE.md`/`FILE_STRUCTURE.md`/`ROADMAP.md`(정책 12단계 중심) 현행화 또는 archive 이동 |
| **calculator_template_engine 제거** | seed 로직 v2 이관 후 구 엔진 제거 가능(현재 calculator_seed가 사용 중) |
| **관련카드 [:4] cap** | 연말정산/육아휴직이 cap 뒤라 관련카드 미노출. cap 상향 시 card_label override 최초 노출 → 재검증 필요 |
