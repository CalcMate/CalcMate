# V2 아키텍처 설계 검증 보고서 (Audit Report)

## 1. 모듈별 영향도 분석
| 모듈명 | 영향도 | 분석 근거 |
| :--- | :--- | :--- |
| `modules/collector/calculator.py` | 수정 필요 | 계산기 수집 단계에서 `intent` 메타데이터 생성 로직 추가 필요 |
| `modules/calculator_pipeline.py` | 수정 필요 | `run_calculator_once`의 파라미터 확장 및 파이프라인 흐름 제어 변경 |
| `modules/calculator_seo_generator.py` | 수정 필요 | Intent별 제목/설명 생성 로직 고도화 |
| `modules/calculator_writer.py` | 영향 없음 | 프롬프트 주입 방식을 통한 확장 가능 |
| `modules/calculator_reviewer.py` | 영향 없음 | 콘텐츠 품질 검수 기준은 Intent와 무관하게 일관성 유지 |
| `modules/html_generator.py` | 영향 없음 | HTML 생성 규칙은 intent 무관 |
| `state_manager` | 수정 필요 | Intent 기반 상태 관리 추적 ID 추가 필요 |
| `ArticleRepository` | 수정 필요 | `(calculator_id, intent)` 기반의 중복 판정 및 조회 기능 확장 필요 |

## 2. 데이터 모델 제안
*   **신규 필요 데이터:** `intent_type` (필수), `cluster_id` (선택), `hub_article` (boolean)
*   **구현 방법:** 기존 DB 스키마에 컬럼을 추가하는 대신, `ArticleRepository`의 `history` JSON 필드 또는 `meta` 필드를 활용하여 마이그레이션 없이 메타데이터만으로 대응 가능함.

## 3. 기존 운영과의 호환성
*   **호환성 확인:** 기존 모듈 호출 시 `intent=None`을 전달하여 기본 파이프라인(Legacy mode)을 호출하면 수정 없이 기존 동작 100% 보장됨.
*   **주의점:** `ArticleRepository`의 기존 데이터에 `intent` 필드가 누락되어 있으므로, 쿼리 시 NULL 처리가 필수적임.

## 4. Duplicate 정책 비교
*   **현재 (calculator_id):** 단순하지만 동일 계산기 내 다양한 의도 수용 불가.
*   **변경안 (calculator_id + intent):** 클러스터 구조에 적합하며 카니발라이제이션 방지.
*   **결론:** 구현 시점에는 `(calculator_id, intent)` 단위로 전환하는 것이 옳음.

## 5. MAX_ARTICLES_PER_CALCULATOR 정책 비교
*   **A. 현재 유지:** 기존 구조와 동일하여 구현이 빠름 (단, 의도별 콘텐츠가 부족해질 수 있음).
*   **B. Intent별 제한:** 가장 권장됨. Intent별 콘텐츠 균형 유지 가능.
*   **C. Hub 단위 제한:** 관리가 어려움.
*   **결론:** **B 안**을 지향하되, 초기에는 A의 상한을 Intent 개수만큼 늘리는 방식으로 운영.

## 6. 마이그레이션 전략
1.  **자동 분류:** 과거 발행 이력을 바탕으로 제목/키워드 분석을 통한 Intent 자동 태깅(초기 1회성 스크립트).
2.  **신규 콘텐츠만 적용:** 기존 콘텐츠는 유지하되, 향후 발행 건부터 신규 정책 적용. (가장 추천)

## 7. 추천 구현 순서
1.  **레벨 1 (Low Risk):** 파이프라인에 `intent` 파라미터 전달 및 제목 생성 로직 분리 (현 상태 유지).
2.  **레벨 2 (Medium Risk):** `ArticleRepository` 조회 로직에 Intent 필터링 추가.
3.  **레벨 3 (High Risk):** 중복 판정 정책을 `(id, intent)` 조합으로 전환.

---
**최종 판단:** **선행 수정 필요**
- **근거:** 현재 DB 상의 기존 콘텐츠들에 `intent` 정보가 부재하므로, 로직 전환 시 기존 콘텐츠의 `intent`를 어떻게 처리할지(NULL 처리 등)에 대한 구체적인 마이그레이션 스크립트가 선행되어야 안전합니다.
