# TABLE_BUILDER_INVESTIGATION.md

## 1. 현재 데이터 구조
- **Single Source of Truth**: 모든 계산기 메타데이터와 로직은 `docs/legal_basis.master.yaml`에 집중되어 있음.
- **레지스트리**: `docs/registry/*.yaml`을 통해 카테고리, 태그, 슬러그가 관리됨.
- **계산 로직**: `modules/*_calculator.py`에 파이썬 로직이 존재하고, `legal_basis.master.yaml`의 `compute_rules`가 이를 미러링함.

## 2. 표 생성 가능 데이터 후보
`legal_basis.master.yaml` 내에서 다음 데이터를 추출하여 표로 구성 가능:
- `threshold`: 기준선 표 (예: 주휴수당 15시간)
- `rates`: 세율/요율 표 (예: 4대보험 요율)
- `transition`: 전환 구간 표 (예: 육아휴직 6+6 특례 구간)
- `formula`: 계산 단계별 체크리스트/공식 표

## 3. 계산기별 추천 표
| 계산기 | 추천 표 항목 |
| :--- | :--- |
| weekly-holiday-allowance | 근무시간별 주휴수당 지급 여부 |
| unemployment-benefit | 가입기간별/연령별 지급 기간 |
| parental-leave-benefit | 구간별(1~6개월/7개월~) 지급률 및 상한액 |
| four-insurances | 보험별 근로자/사업주 요율 비교 |
| severance-pay | 근속기간별 지급 공식 및 예시 |
| annual-leave-allowance | 근속기간별 연차 발생 일수 |
| 연말정산환급액계산기 | 과세표준 구간별 세율 및 공제율 |

## 4. HTML 삽입 위치
본문의 **"계산 방법"** 섹션 직후 또는 **"조건 설명"** 섹션 내부에 위치시키는 것이 사용자의 정보 충족도를 높이는 데 가장 자연스러움.

## 5. 공통 Table Builder 설계안
- **클래스**: `TableBuilder` (modules/utils/ 또는 content_pipeline/)
- **입력**: `List[Dict]` (데이터), `List[str]` (헤더), `str` (표 스타일/CSS)
- **출력**: `str` (HTML `<table>` 태그 문자열)
- **동작**: 입력된 데이터를 파싱하여 HTML 테이블로 자동 변환하는 유틸리티.

## 6. 구현 시 수정이 필요한 파일 목록
- `content_pipeline/metadata_builder.py`: 본문에 표 삽입 로직 추가.
- `modules/calculator_prompt_manager.py`: 표 삽입을 위한 프롬프트 가이드 수정.
- `content_pipeline/engine_adapter.py`: 표 데이터를 빌드하여 전달하도록 수정.
