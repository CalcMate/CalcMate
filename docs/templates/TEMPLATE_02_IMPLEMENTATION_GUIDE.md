# [계산기명] 계산기 — Phase 2 구현 지시서 템플릿
> Phase F에서 신규 계산기 구현 시 이 템플릿을 복사하여 사용.
> 전제: Phase 1(조사 + 법령 확정 게이트) 완료 상태.
> 작성일: YYYY-MM-DD

---

## 선행 조건 체크

- [ ] `docs/TEMPLATE_01_RESEARCH_GUIDE.md` 완료 (법령 확정 게이트 통과)
- [ ] `legal_basis.draft.yaml`에 해당 계산기 항목 존재
- [ ] 설계 범위 v1 합의 완료
- [ ] 정부 공식 계산기 비교 케이스 3개 확보

---

## 1. DB 업데이트

### 1-1. 입출력 스키마
```json
{
  "input_schema": {"[field1]": "number", "[field2]": "number"},
  "output_schema": {"[output_key]": "number"}
}
```

### 1-2. 레이블
```json
{
  "[field1]": "[한국어 레이블]",
  "[field2]": "[한국어 레이블]",
  "[output_key]": "[출력 레이블]"
}
```

### 1-3. FAQ 8개 초안 (SP-8 기준)
각 FAQ 항목은:
- 자연어로 작성 (변수명/코드 표현 절대 금지)
- 법령 조항 최소 1회 언급
- 구체적 수치/조건 포함

```
Q1: [가장 많이 묻는 질문]
A1: [자연어 답변, 법령 조항 포함]

Q2: [예외/경계 관련 질문]
A2: [원칙→예외 순서로 서술 (C-13)]
...
```

### 1-4. article_content 구조
```
1. 계산기 소개 (1~2문장)
2. [계산기명] 계산 방법 (법령 기준)
   - [단계별 설명]
3. 계산 예시 2개 (compute_xxx() 결과 직접 인용)
   - 예시 1: [입력값] → [결과]
   - 예시 2: [입력값] → [결과]
4. 주의사항
   - v1 제외 항목 안내
   - 참고용 예상치 안내
```

---

## 2. Python 계산 엔진

### 2-1. 파일 위치
`modules/[slug_snake_case]_calculator.py`

### 2-2. 핵심 함수 구조
```python
def compute_[slug_snake](input1: int, input2: int, ...) -> dict:
    """[계산기명] 전체 계산.
    
    반환:
        {"[output_key]": int, "_detail": [...], "_formula": str, "notices": [...]}
    """
    # 1단계: [단계 설명]
    # ...
```

### 2-3. 불변식 (Invariant) 목록
- [ ] [불변식 1: 예 "input1↑ → output↑ (단조 증가)"]
- [ ] [불변식 2: 예 "output ≥ 0 (음수 불가)"]
- [ ] [불변식 3: 예 "total == sum(parts) (대수 항등식)"]

---

## 3. app_generator.py 분기 추가

### 3-1. 위치
`_compute_js()` 함수 내, 기존 분기 직후, `date_based` 분기 이전.

### 3-2. JS computeResult 구조
```javascript
window.computeResult = function(inputs){
  var [field1] = inputs["[field1]"] || 0;
  var [field2] = inputs["[field2]"] || 0;
  if ([field1] <= 0 || [field2] <= 0) { return null; }
  var out = {};
  out.notices = [];
  
  // [계산 로직]
  
  out["[output_key]"] = [계산 결과];
  out._formula = "[formula 문자열]";
  out._detail = [{label:"[레이블]", value:[값]+"원"}];
  return out;
};
```

### 3-3. notices 우선순위
1. [경계값/수급 불가 안내] (가장 먼저)
2. [상한/하한 적용 안내]
3. [일반 disclaimer]

---

## 4. 단위 테스트

파일: `tests/test_[slug_snake]_compute.py`

### 4-1. 필수 테스트 그룹
- `TestBoundaryValues`: 경계 직전/기준점/직후 3점 세트
- `TestInvalidInputs`: 음수/0 → null
- `TestNormalCases`: 일반 케이스 3개 이상
- `TestFormula`: `_formula` 키 존재 및 형식 확인
- `TestNotices`: 경계 이하 → notice 포함, 정상 → notice 없음
- `TestInvariants`: 불변식 파라미터화 테스트
- `TestSEOExamples`: article_content 예시 금액 교차 확인

### 4-2. 정부 기준 3케이스 비교 테스트
```python
@pytest.mark.parametrize("input1,input2,expected", [
    ([값A], [값B], [정부기준결과A]),
    ([값C], [값D], [정부기준결과B]),
    ([값E], [값F], [정부기준결과C]),
])
def test_government_reference_cases(input1, input2, expected):
    r = compute_[slug_snake](input1, input2)
    assert abs(r["[output_key]"] - expected) == 0
```

---

## 5. legal_basis.draft.yaml 갱신

```yaml
[slug]:
  # ... (조사 지시서에서 작성한 항목)
  confidence: high   # Phase 2 완료 후 medium → high
  content:
    evergreen: [true/false]
    update_cycle: [null/"yearly"]
    content_caveat: null   # v1 완전 구현 시
```

---

## 6. workspace 재생성 + golden snapshot 갱신

```bash
py scripts/regen_and_snapshot.py --slug [slug]
# 또는 전체 재생성
py scripts/regen_all.py
```

---

## 7. Phase 2 완료 기준

- [ ] Python 계산 엔진 구현 완료
- [ ] app_generator.py JS 분기 추가
- [ ] DB inputs/outputs/labels/faq/article 업데이트
- [ ] 단위 테스트 최소 15개
- [ ] 정부 기준 3케이스 오차 0원
- [ ] SP-8 감사: article_content + FAQ 변수명 0건
- [ ] 전체 회귀 테스트 ALL PASS
- [ ] workspace 재생성 + snapshot 갱신
- [ ] `legal_basis.draft.yaml` confidence → high, content_caveat → null
