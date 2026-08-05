# H-3 FAQ Engine 2.0 Completion Document

## 1. 개요
기존 나열식 FAQ 구조를 검색의도 및 계산기 검증 데이터 기반 구조로 전환.

## 2. 데이터 흐름
`faq_source_mapper` (매핑 허브) → `faq_question_selector` (질문 선정) → `faq_generator` (답변 생성) → `faq_validator` (검증 게이트)

## 3. Validator 규칙 (5개)
- `validate_threshold_rule`: 계산 기준선 준수 (예: 주휴수당 15시간)
- `validate_numeric_rule`: 숫자 일치 (예: 상한액)
- `validate_condition_rule`: 대상/조건 준수
- `validate_exception_rule`: 예외 케이스 DB 참조
- `validate_transition_rule`: 로직 전환점(6+6 등) 검증

## 4. 금지 사항
- AI의 법령 창작, 근거 없는 예외 생성, 최신 법 개정 추측, 계산 모순, 모호한 표현.

## 5. 결과 요약
- Unit Test, Critical HOLD, Integration Tests (전체 9개 통과, 70개 케이스 대응 가능)
- False PASS 건수: 0건

## 6. 운영
- 신규 계산기 추가 시 `legal_basis.master.yaml` 및 `compute_rules` 추가 시 자동 적용.
- `tests/snapshots/faq_golden_snapshot.json`을 사용하여 품질 회귀 감지.
