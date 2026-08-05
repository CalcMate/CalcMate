# H-4-B Competitive Analysis Engine Completion Document

## 1. 개요
경쟁 콘텐츠를 분석하고, 부족한 영역을 탐지하여 구체적인 콘텐츠 개선 작업을 제안하는 자동화 엔진입니다.

## 2. 모듈 아키텍처
`SERPCollector` → `CompetitorParser` → `TopicExtractor` → `ContentGapAnalyzer` → `ImprovementGenerator` → `CompetitiveValidator`

## 3. 검증 규칙
- **Legal Safety**: 핵심 항목(법적 기준, 조건 등) 무단 수정 시 HOLD.
- **Duplicate Risk**: 경쟁 콘텐츠 복사 위험 탐지 시 WARNING.
- **Quality Compatibility**: 품질 엔진과 충돌하는 과도한 기준(예: 글자 수 등) 사용 시 WARNING.

## 4. 결과 및 운영
- **Golden Snapshot**: `tests/snapshots/competitive_analysis_snapshot.json`에 3개 계산기 기준 데이터 저장.
- **운영**: 신규 키워드 분석 시 파이프라인(`run_pipeline_for_calculator`)을 통해 즉시 가용.

## 5. 최종 결과
- 전체 테스트(H-3, H-4-A, H-4-B) PASS 완료.
- False PASS 0건.
