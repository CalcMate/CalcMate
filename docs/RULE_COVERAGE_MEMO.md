# FAQ Validator Rule Coverage Analysis Memo

## 커버리지 없음 항목 판정
대부분의 "커버리지 없음" 항목은 해당 계산기의 법적 특성에 따른 것으로 판단됨 (예: 실업급여의 수급 요건은 FAQ 대상이나 계산기 파라미터가 아님).

## Transition Rule 승격 필요성
육아휴직의 "6+6 특례 -> 일반" 전환은 중요한 로직 변경임. 현재 `condition_rule`로 대략 매핑했으나, 향후 타 계산기(연말정산 누진세율 구간, 실업급여 급여일수 구간 등)에서도 동일한 패턴이 필요할 것으로 보임.

**판단:** `transition_rule`을 공통 규칙으로 승격하여 `FAQValidator`에 추가하는 것을 권장함.
