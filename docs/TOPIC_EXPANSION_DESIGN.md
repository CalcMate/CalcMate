# TOPIC_EXPANSION_DESIGN.md

## 1. 개요
현재 "계산기 1개 = 1개 문서" 구조를 "계산기 1개 = 콘텐츠 허브(복수 Intent 문서)" 구조로 확장하기 위한 설계안입니다.
목표는 검색 의도(Search Intent)를 세분화하여 E-E-A-T를 강화하고, 콘텐츠 클러스터를 형성하여 체류시간과 탐색성을 높이는 것입니다.

## 2. Intent 분류 및 데이터 소스 분석

| Intent | 커버 가능성 | 신규 데이터 확보 방안 |
| :--- | :--- | :--- |
| **계산** | 완벽 커버 | 기존 법령/공식 데이터 기반 생성 |
| **자격/조건** | 완벽 커버 | 기존 법령/조건 데이터 기반 생성 |
| **사례** | 커버 가능 | 기존 계산 로직의 '예시 사례' 시나리오 확장 |
| **문제해결** | 데이터 필요 | 노동청 신고 등 외부 절차는 `legal_basis.master.yaml`의 절차 정보 섹션 확장 필요 |
| **제도/법령** | 완벽 커버 | 기존 법령 근거 섹션 활용 |
| **FAQ** | 커버 가능 | 기존 FAQ 데이터 확장 |

## 3. 제목 생성 규칙 초안

*   **계산:** "{연도} {계산기명} 공식 및 자동 계산기 활용 가이드"
*   **자격:** "{연도} {계산기명} 대상자 총정리: 15시간 미만도 가능할까?"
*   **사례:** "{연도} {계산기명} 실제 계산 예시로 쉽게 이해하기"
*   **문제해결:** "{연도} {계산기명} 미지급 시 대응법 및 신고 절차 가이드"
*   **제도/법령:** "근로기준법으로 보는 {계산기명}, 반드시 알아야 할 지급 근거"
*   **FAQ:** "{계산기명}에 대해 궁금한 모든 것: 핵심 질문 5가지 답변"

## 4. 콘텐츠 허브 구조 설계

*   **계산기 메인 페이지:** 계산기 위젯이 메인이며, 위 하위 6종 Intent 문서로 향하는 내부 링크 맵(Navigation Map) 탑재.
*   **내부 링크 구조:**
    1.  모든 Intent 문서는 계산기 메인 페이지를 참조.
    2.  서로 연관된 Intent 문서 간(예: 계산 vs 사례, 자격 vs 제도) 상호 링크 구축.
    3.  `ArticleRepository` 저장 시 `cluster_id` 필드를 추가하여 쿼리 기반 자동 연결.

## 5. 파이프라인 연동 방식 제안

*   **구조:** `modules/calculator_pipeline.py`의 `run_calculator_once` 함수에 `intent` 파라미터를 추가.
*   **루프 방식:** `main.py` 또는 상위 호출 루프에서 각 Intent를 순회하며 `run_calculator_once(cfg, only_cid=cid, intent=intent_type)`를 개별 호출.
*   **장점:** `orchestrator.py` 및 핵심 파이프라인 비즈니스 로직(SEO/Writer 등)을 거의 수정하지 않고 기능 확장 가능.

## 6. Duplicate 정책 영향

*   **변경 필요:** 기존 제목 기반 중복 판정을 `(calculator_id, intent_type)` 조합 기반으로 판정하도록 `ArticleRepository`의 검색 로직 또는 `pipeline`의 차단 로직 수정 필요.

## 7. 수정 예정 파일 목록

*   **신규 생성:** `modules/collector/intent_registry.py` (Intent별 프롬프트 정의)
*   **수정 예정:** `modules/calculator_pipeline.py` (Intent 파라미터 수용), `modules/calculator_seo_generator.py` (Intent별 제목 생성), `repositories/article_repository.py` (중복 판정 로직 확장)
*   **수정 금지:** `orchestrator.py`, `table_builder.py`, `image_builder.py`, `legal_basis.master.yaml` (단, 법령 절차 정보 추가를 위해 `legal_basis`는 확장 가능성 열어둠)
