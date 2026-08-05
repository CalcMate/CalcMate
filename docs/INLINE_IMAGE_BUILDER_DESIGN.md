# INLINE_IMAGE_BUILDER_DESIGN.md

## 1. 삽입 위치 조사
- **삽입 로직**: `MetadataBuilder` 내부에서 HTML 파싱을 통해 `<h2>` 섹션 식별자 탐색.
- **우선순위**:
  1. 섹션 식별자(`<h2>계산방법</h2>`, `<h2>계산예시</h2>` 등)를 이용한 구조적 삽입.
  2. Alias 목록("계산방법", "계산 방법", "계산예시", "계산 예시" 등) 기반 검색.
- **적정 삽입점**:
  - `<h2>계산방법</h2>` 뒤 (절차 설명용)
  - `<h2>계산예시</h2>` 뒤 (비교/인포그래픽)
  - `<h2>주의사항</h2>` 뒤 (체크리스트)

## 2. 이미지 생성 기준 매핑표
| 섹션 | 이미지/표 사용 기준 |
| :--- | :--- |
| 계산방법 | 이미지(Flow) + 표 |
| 조건설명 | 이미지(개념 설명 일러스트) |
| 계산예시 | 이미지(비교 인포그래픽) + 표 |
| 주의사항 | 이미지(아이콘형/체크리스트) |

## 3. 이미지 타입별 프롬프트 템플릿
- **공통 제약**: No Text, No Numbers, No Legal Claims.
- **개념 일러스트**: "Modern minimalist illustration representing [Concept], flat vector art, clean background, high quality."
- **절차(Flow) 다이어그램**: "Modern infographic flow chart illustrating process steps, minimalist, vector, clean style, no text."
- **인포그래픽**: "Comparison infographic style illustration, clean, professional, flat vector."

## 4. 계산기별 이미지 타입 매핑표
| 계산기 | 추천 이미지 타입 |
| :--- | :--- |
| 주휴수당 | 일러스트(시간 개념), 체크리스트(조건) |
| 실업급여 | 타임라인(수급 기간), 인포그래픽(조건) |
| 육아휴직 | 타임라인(특례 구간), 일러스트(육아 개념) |
| 4대보험 | 인포그래픽(요율 비교) |
| 퇴직금 | 일러스트(근속 기간), 인포그래픽(공식) |
| 연차수당 | 일러스트(휴가 개념), 체크리스트(발생 기준) |
| 연말정산 | 인포그래픽(공제 구간) |

## 5. WordPress 처리 방식 설계
- **기존 인프라 재사용**: `WordPressMediaUploader` 활용.
- **본문 삽입**: 이미지 업로드 후 반환된 URL을 본문 내 적절한 위치에 `<img src="...">` 태그로 자동 삽입.
- **ALT 생성**: 본문 내 해당 이미지 주변 텍스트와 계산기 제목을 결합하여 SEO 친화적 ALT 생성.
- **구분**: Featured Image는 `metadata_builder`의 `featured_media` 필드로 처리하고, 본문 이미지는 `content` HTML 내부에 직접 삽입.

## 6. 수정 예정 파일 목록
- **신규 생성**: `content_pipeline/image_builder.py`
- **수정**: `content_pipeline/metadata_builder.py` (이미지 HTML 주입 로직 추가)
