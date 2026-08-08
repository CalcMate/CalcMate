# Phase3-1 설계 문서: 프리랜서 3.3% 원천징수 계산기

작성일: 2026-08-08  
기준: Phase3-0 구조조사 완료 (v2.0.0)  
상태: **설계 전용 — 코드 수정 금지**  
대상 계산기: `freelancer-tax-3p3` (프리랜서 3.3% 원천징수 계산기)

---

## 1. Registry v3 신규 YAML 설계

**파일**: `docs/registry/tax.yaml`  
**위치**: `연말정산_환급액_계산기` 항목 아래에 추가

```yaml
freelancer-tax-3p3:
  name: 프리랜서 3.3% 원천징수 계산기
  slug: freelancer-tax-3p3
  category: 세금/정부혜택
  emoji: 🧮
  card_label: 프리랜서 원천징수 계산기
  compute_type: single
  date_fields: []
  validation_mode: formula
  field_labels:
    gross_income: "총 수입(원)"
    withholding_tax: "원천징수세액(원)"
    net_income: "실수령액(원)"
  display_order: 8
  card_desc: "프리랜서·강사·작가 수입에서 3.3% 원천징수 세액과 실수령액을 계산해보세요"
  difficulty: simple
  difficulty_status: provisional
  content:
    evergreen: true
    update_cycle: null
    content_caveat: null
  related_slugs:
  - 연말정산_환급액_계산기
  - four-insurances
  - weekly-holiday-allowance
  legal_refs:
  - income_tax_act_127
  writer_context:
    emphasize:
    - "3.3% = 소득세 3% + 지방소득세 0.3% (소득세법 제127조)"
    - "5월 종합소득세 신고 의무 — 원천징수는 납세 완료가 아님"
    - "인적용역 소득에 한정 (부가세 별도, 근로소득 해당 없음)"
    example_patterns:
    - "월 200만원 수입 프리랜서 강사 케이스"
    - "투잡 직장인 + 프리랜서 겸업, 연간 수입 합산 케이스"
    - "계약금·잔금 분할 수령 케이스 (건당 원천징수)"
    calculation_story:
    - "원천징수 3.3% = 소득세 3% + 지방소득세 0.3%. 실수령액은 총 수입의 96.7%"
```

**결정 근거**:
- `display_order: 8` — 기존 7개 이후 순서 (1~7은 기존 고정, 충돌 없음)
- `compute_type: single` — 단일 입력, 2개 출력 (아래 §5 참고)
- `legal_refs: [income_tax_act_127]` — 소득세법 제127조 원천징수 조항

---

## 2. legal_master 데이터 설계

**파일**: `docs/legal_master/tax.yaml`  
**위치**: `income_tax_act_137` 항목 아래에 추가

```yaml
income_tax_act_127:
  law: 소득세법
  article: 제127조
  related_articles:
  - 제164조의3
  - 소득세법 시행령 제184조의2
  authority: 국세청
  confidence: high
  last_verified: 2026-08-08
  verification_source:
  - law.go.kr
  - nts.go.kr
  writer_note: |
    소득세법 제127조(원천징수의무)에 따라 원천징수의무자(사업자·기관)는
    인적용역 소득 지급 시 소득세 3%를 원천징수해야 한다. 지방소득세(소득세의 10%) 0.3%를
    포함하여 실무에서는 3.3%라고 표현한다.

    ⚠️ 반드시 포함할 문구:
    - 원천징수는 납세 완료가 아니며, 매년 5월 종합소득세 신고를 통해 정산됨
    - "이 계산기는 인적용역 소득(사업소득)에만 적용되며, 근로소득·기타소득은 해당하지 않습니다"
    - "계산 결과는 참고용이며 실제 납부세액은 신고 내용에 따라 달라질 수 있습니다"

    ⚠️ 절대 쓰지 말 것:
    - "세금을 다 낸 것" 또는 "원천징수하면 종합소득세 신고 불필요"
    - 근로소득에도 적용된다는 서술
  reviewer_expectation:
  - 소득세법 제127조 조항 언급
  - 3.3% = 소득세 3% + 지방소득세 0.3% 명시
  - 종합소득세 신고 의무 언급
  - 참고용 예상치 면책 문구 포함
  forbidden_articles: []
  forbidden_phrases:
  - "원천징수로 납세 완료"
  - "종합소득세 신고 불필요"
  needs_human_legal: false
  calculation_flow:
  - "원천징수세액 = 총 수입 × 3% (소득세)"
  - "지방소득세 = 소득세 × 10% = 총 수입 × 0.3%"
  - "합산 원천징수세액 = 총 수입 × 3.3%"
  - "실수령액 = 총 수입 × (1 - 0.033) = 총 수입 × 0.967"
```

**Tier 분류**: Tier 2 (순수 산술). `needs_human_legal: false`.  
법령 조항은 참조용이며 calculation_flow가 단순 산술이므로 법률 전문가 검토 불필요.

---

## 3. legal_basis.master.yaml 추가 설계

**파일**: `docs/legal_basis.master.yaml`  
**위치**: 마지막 항목 아래 추가  
**이유**: `app_generator._registry()`가 여전히 이 파일을 사용 (`load_registry()` 구 경로)

```yaml
freelancer-tax-3p3:
  name: 프리랜서 3.3% 원천징수 계산기
  law: 소득세법
  article: 제127조
  related_articles:
  - 소득세법 시행령 제184조의2
  authority: 국세청
  confidence: high
  last_verified: 2026-08-08
  verification_source: [law.go.kr, nts.go.kr]
  writer_note: >
    소득세법 제127조에 따라 인적용역 소득에 대한 원천징수세율은 소득세 3% +
    지방소득세 0.3% = 3.3%이다. 원천징수는 납세 완료가 아니며 종합소득세 신고 의무가
    별도로 존재함을 반드시 언급한다.
  reviewer_expectation:
    - 소득세법 제127조 언급
    - 3.3% 구성(소득세 3% + 지방소득세 0.3%) 설명
    - 종합소득세 신고 의무 언급
  forbidden_articles: []
  forbidden_phrases:
    - "원천징수로 납세 완료"
    - "종합소득세 신고 불필요"
  needs_human_legal: false
  # --- registry v2 미러 ---
  slug: freelancer-tax-3p3
  category: 세금/정부혜택
  emoji: "🧮"
  card_label: 프리랜서 원천징수 계산기
  compute_type: single
  date_fields: []
  validation_mode: formula
  field_labels: {}
  difficulty: simple
  difficulty_status: provisional
  needs_human_legal: false
  content:
    evergreen: true
    update_cycle: null
    content_caveat: null
  related_slugs:
  - 연말정산_환급액_계산기
  - four-insurances
  - weekly-holiday-allowance
  compute_rules:
    positive_inputs: [gross_income]
```

**주의**: `legal_basis.master.yaml` 파일 상단 주석에 "직접 편집 금지 — rms_promote.py 통해 승격"이라고 쓰여 있다. 그러나 이 주석은 RMS 감지된 변경사항의 워크플로에 관한 것이며, 신규 계산기 최초 등록은 수동 추가가 현행 관행(기존 7개도 migrate_legal_master.py로 생성됨). **구현 시 이 점을 확인하고 진행한다.**

---

## 4. input/output schema 설계

### 입력 필드

| 필드명 | 타입 | 표시명 | 단위 | 검증 |
|---|---|---|---|---|
| `gross_income` | number | 총 수입 | 원 | 양수 필수, 정수 |

### 출력 필드

| 필드명 | 타입 | 표시명 | 계산 |
|---|---|---|---|
| `withholding_tax` | number | 원천징수세액 | `gross_income × 0.033` |
| `net_income` | number | 실수령액 | `gross_income - withholding_tax` |

### DB JSON 표현

```json
input_schema:  {"gross_income": "number"}
output_schema: {"withholding_tax": "number", "net_income": "number"}
```

---

## 5. 계산 공식 및 검증 기준 설계

### 핵심 공식

```
withholding_tax = round(gross_income * 0.033)
net_income      = gross_income - withholding_tax
```

원 단위 절사/반올림: `round()` 사용 (법령 명시 없음, 실무 관행상 원 단위 반올림).

### DB formula 필드

```
gross_income * 0.033
```

formula 필드는 primary output(`withholding_tax`)의 수식만 저장. `net_income`은 JS에서 `gross_income - withholding_tax`로 파생.

### _compute_js() 처리 방향 — 중요

> **Phase3-0 감사 결론 재검토**: generic formula fallback은 **단일 output** 계산기를 가정한다. 이 계산기는 `withholding_tax`와 `net_income` 두 값을 모두 표시해야 하므로 generic fallback 그대로는 불완전하다.

#### 선택지

| | 방법 | 코드 변경 | UX |
|---|---|---|---|
| **A (권장)** | `_compute_js()` 내 `freelancer-tax-3p3` 분기 추가 (5줄 JS) | 최소 추가 | 완전 (withholding + net 모두 표시) |
| B | formula fallback으로 `net_income`만 표시 | 없음 | 불완전 (withholding_tax 미표시) |

**권장: 옵션 A.** 추가 코드는 아래 5줄이 전부:

```javascript
// _compute_js() 내 추가 (freelancer-tax-3p3 분기)
} else if (slug === "freelancer-tax-3p3") {
  const withholding = Math.round(vals.gross_income * 0.033);
  const net = vals.gross_income - withholding;
  return {withholding_tax: withholding, net_income: net};
}
```

이 분기를 추가하면 기존 generic fallback은 변하지 않으며, 기존 7개 계산기에 영향 없음.

### 검증 기준

| 조건 | 처리 |
|---|---|
| `gross_income <= 0` | `null` 반환 (입력 오류) |
| `gross_income` 미입력 | 결과 미표시 |
| `gross_income` 소수 | 소수점 입력 허용 (용역비가 소수일 수 있음) |
| 최대값 상한 | 없음 (상한 적용 없는 원천징수) |

---

## 6. DB calculators 등록 방식

### 등록 방법 선택

| 방법 | 설명 | 권장 여부 |
|---|---|---|
| `python main.py --seed-calculators` 재실행 | `calculator_seed.py SAMPLE_CALCULATORS`에 추가 후 실행 | **권장** |
| 직접 SQL INSERT | `CalculatorRepository.upsert_by_slug()` 호출 | 대안 |

**권장 방법**: `calculator_seed.py SAMPLE_CALCULATORS`에 새 항목 추가 + `--seed-calculators` 실행.  
이렇게 하면 향후 환경 초기화 시에도 재현 가능.

### 삽입 레코드 설계

```python
# calculator_seed.py SAMPLE_CALCULATORS 추가 항목
{
    "id": "calc_freelancer_tax_3p3",
    "name": "프리랜서 3.3% 원천징수 계산기",
    "slug": "freelancer-tax-3p3",
    "category": "세금/정부혜택",
    "calculator_type": "프리랜서 3.3% 계산기",
    "status": "active",
    "seo_title": "2026 프리랜서 3.3% 원천징수 계산기 | 실수령액 자동 계산",
    "seo_desc": "프리랜서·강사·작가 인적용역 수입의 원천징수세액(3.3%)과 실수령액을 자동 계산합니다. 소득세 3% + 지방소득세 0.3%",
    "formula": "gross_income * 0.033",
    "input_schema": {"gross_income": "number"},
    "output_schema": {"withholding_tax": "number", "net_income": "number"},
    "faq": [
        {
            "q": "3.3%는 어디서 나온 숫자인가요?",
            "a": "소득세법 제127조에 따른 원천징수세율 3%(소득세)에 지방소득세 0.3%를 더한 값입니다."
        },
        {
            "q": "원천징수를 하면 세금 신고를 안 해도 되나요?",
            "a": "아닙니다. 원천징수는 선납 개념이며 매년 5월 종합소득세 신고를 통해 정산해야 합니다. 과납이면 환급, 부족이면 추가 납부합니다."
        },
        {
            "q": "125만원 미만 용역비는 원천징수가 면제된다는데 사실인가요?",
            "a": "개인에게 지급하는 인적용역비는 금액 무관하게 3.3% 원천징수 대상입니다. 125만원 면제 기준은 일부 기타소득에 적용되며 프리랜서 사업소득과는 다릅니다."
        },
        {
            "q": "부가가치세(VAT)는 이 계산에 포함되나요?",
            "a": "포함되지 않습니다. 부가가치세 과세 사업자라면 공급가(본 계산기 입력값)에 VAT 10%를 별도로 청구합니다. 원천징수는 VAT 제외 공급가 기준으로 계산합니다."
        },
        {
            "q": "직장인이 프리랜서 부업을 하면 어떻게 되나요?",
            "a": "근로소득과 합산하여 다음 해 5월에 종합소득세 신고를 해야 합니다. 부업 수입에서 원천징수된 3.3%는 기납부세액으로 차감됩니다."
        }
    ]
}
```

### articles 테이블

신규 계산기 DB 등록 후 `run_calculator_once(slug="freelancer-tax-3p3")` 실행 시 자동 생성됨. 사전 수동 입력 불필요.

---

## 7. GitHub Pages 자동 생성 경로

### 자동 처리 확인

| 생성 파일 | 자동 여부 | 조건 |
|---|---|---|
| `_site/index.html` (카드 표시) | **자동** | registry v3 항목 추가 + `_rebuild_site.py` 실행 |
| `_site/freelancer-tax-3p3/index.html` | **자동** | DB 등록 + `_rebuild_site.py` 실행 |
| `_site/sitemap.xml` | **자동** | registry v3 항목 추가 + `_rebuild_site.py` 실행 |
| `_site/robots.txt` | **변경 없음** | 정적 파일 |

### 생성 명령

```bash
python scripts/_rebuild_site.py
```

실행 후 `data/workspace/_site/freelancer-tax-3p3/index.html` 존재 확인으로 검증.

### GitHub Actions 배포

`data/workspace/_site/**` 변경사항 push 시 `.github/workflows/deploy.yml` 자동 실행 → `calcmate.kr` 배포.  
별도 배포 설정 변경 불필요.

---

## 8. SEO/FAQ/H-4 연동

### SEO

`calculator_seo_generator` — calc.name + registry writer_context 읽어 자동 생성. 추가 설정 불필요.

**예상 SEO 출력** (설계값, 실제 생성기가 오버라이드 가능):
```
seo_title: 2026 프리랜서 3.3% 원천징수 계산기 | 실수령액 자동 계산
seo_desc: 프리랜서·강사·작가 인적용역 수입의 원천징수세액(3.3%)과 실수령액을 자동 계산합니다. 소득세 3% + 지방소득세 0.3%
```

### FAQ

`calculator_faq_generator` — DB `faq` 필드(위 §6에서 5개 설계) + writer_context → 자동 H2 FAQ 섹션 생성. 추가 설정 불필요.

### H-4 품질 검수

legal_master `reviewer_expectation` 기준:
- ✓ 소득세법 제127조 조항 언급
- ✓ 3.3% 구성(소득세 3% + 지방소득세 0.3%) 설명
- ✓ 종합소득세 신고 의무 언급
- ✓ 참고용 예상치 면책 문구

`QUALITY_GATE.MIN_LENGTH: 1800` — 프리랜서 세금 관련 콘텐츠는 도달 가능.  
`BLOCK_UNVERIFIED_LEGAL: true` → legal_master에 `income_tax_act_127` 등록 완료 시 통과.

---

## 9. WordPress 콘텐츠 생성 연동

### V2 자동 포함 조건

DB `calculators` 테이블에 `status='active'`로 등록되면 다음 `run_calculator_once()` 실행 시 자동으로 콘텐츠 생성 대상에 포함됨. 별도 코드 변경 불필요.

### 실행 방법

```bash
# 신규 계산기만 단발 실행
python main.py --once --calculator-id calc_freelancer_tax_3p3
# 또는 slug로
python main.py --once --only-slug freelancer-tax-3p3
```

### 생성 순서

1. `calculator_pipeline.run_calculator_once(slug="freelancer-tax-3p3")`
2. → Planner → Writer → H-4 검수 → (PASS 시) WordPress publish
3. → `articles` 테이블에 신규 row 생성 (`상태값='발행완료'`, `wp_post_id` 부여)

---

## 10. P2-3 rewrite 대상 편입 여부

### time-based (자동)

발행 완료 후 365일 경과 시 `_time_based_candidates()`가 자동으로 탐지. **추가 작업 없음.**

### RMS (수동 등록 필요)

`modules/rms.py IMPACT_MAP`에 추가:

```python
# 기존 IMPACT_MAP에 추가
"income_tax_act_127": ["freelancer-tax-3p3"],
```

소득세법 제127조 원천징수율(3.3%)은 고정값이지만, 지방소득세율 변경이나 면세 범위 확대 등 법령 개정 가능성이 있으므로 RMS 연동을 등록해 두는 것이 안전하다.

**IMPACT_MAP 등록 결정**: YES (등록 권장).

---

## 11. 기존 7개 계산기 회귀 방지

### 위험 분석

| 변경 파일 | 기존 계산기 영향 | 근거 |
|---|---|---|
| `docs/registry/tax.yaml` (항목 추가) | 없음 | YAML 키가 독립적, 기존 키 변경 없음 |
| `docs/legal_master/tax.yaml` (항목 추가) | 없음 | 기존 `income_tax_act_137` 변경 없음 |
| `docs/legal_basis.master.yaml` (항목 추가) | 없음 | 기존 7개 항목 변경 없음 |
| `modules/app_generator._compute_js()` (분기 추가) | 없음 | elif 체인에 추가 → 기존 분기 미변경 |
| `modules/rms.py IMPACT_MAP` (항목 추가) | 없음 | dict 항목 추가만, 기존 키 변경 없음 |
| `modules/calculator_seed.py` (항목 추가) | 없음 | list append만, 기존 항목 변경 없음 |
| DB (INSERT) | 없음 | 신규 row만, 기존 row 변경 없음 |

**결론: 모든 변경이 추가(append/insert) 전용이며, 기존 7개 계산기 코드 경로를 건드리지 않는다.**

### 회귀 방지 검증 방법

구현 완료 후 다음 명령으로 기존 7개 계산기의 `_site/` 파일이 정상 존재함을 확인:

```bash
python scripts/_rebuild_site.py
# 확인 대상 (8개 모두 존재해야 함)
ls data/workspace/_site/weekly-holiday-allowance/
ls data/workspace/_site/severance-pay/
ls data/workspace/_site/annual-leave-allowance/
ls data/workspace/_site/unemployment-benefit/
ls data/workspace/_site/four-insurances/
ls data/workspace/_site/연말정산_환급액_계산기/
ls data/workspace/_site/육아휴직_급여_계산기/
ls data/workspace/_site/freelancer-tax-3p3/     # 신규
```

---

## 12. 실제 구현 파일 목록

### 수동 작성 필요 (7개 파일)

| 순서 | 파일 | 작업 | 분류 |
|---|---|---|---|
| 1 | `docs/registry/tax.yaml` | `freelancer-tax-3p3` 항목 추가 (§1 내용) | Registry v3 |
| 2 | `docs/legal_master/tax.yaml` | `income_tax_act_127` 엔티티 추가 (§2 내용) | legal_master |
| 3 | `docs/legal_basis.master.yaml` | `freelancer-tax-3p3` 항목 추가 (§3 내용) | 구 SSOT 미러 |
| 4 | `modules/calculator_seed.py` | `SAMPLE_CALCULATORS` 에 새 항목 추가 (§6 내용) | DB 시드 |
| 5 | `modules/app_generator.py` | `_compute_js()` 에 `freelancer-tax-3p3` 분기 추가 (§5 내용) | JS 로직 |
| 6 | `modules/rms.py` | `IMPACT_MAP` 에 `income_tax_act_127` → `[freelancer-tax-3p3]` 추가 (§10 내용) | RMS 연동 |
| 7 | *(선택)* `modules/site_generator.py` | title/desc 텍스트에 "프리랜서 계산기" 추가 | SEO 문구 |

### 자동 처리 (코드 변경 없음)

- `index.html` 카드 생성 — `generate_index()` 자동
- `sitemap.xml` 갱신 — `generate_sitemap()` 자동
- `freelancer-tax-3p3/index.html` 생성 — `_rebuild_site.py` 자동
- SEO/FAQ 생성 — pipeline 자동
- H-4 검수 — 자동
- WordPress 발행 — pipeline 자동

### 구현 우선순위 (의존 관계)

```
1, 2, 3 (YAML 3종) → 동시 진행 가능
4 (seed) → 독립 진행 가능
5 (app_generator) → 독립 진행 가능
6 (rms) → 독립 진행 가능
---
DB 등록 (--seed-calculators 실행) → 4 완료 후
사이트 생성 (_rebuild_site.py) → 1, 4, 5 완료 후
V2 콘텐츠 생성 (--once) → DB 등록 완료 후
```

---

## 13. QA 테스트 케이스

### 13-1. 계산 정확도 테스트

| 입력 | 기대 withholding_tax | 기대 net_income | 검증 공식 |
|---|---|---|---|
| `gross_income = 1,000,000` | `33,000` | `967,000` | 1000000 × 0.033 = 33000 |
| `gross_income = 500,000` | `16,500` | `483,500` | 500000 × 0.033 = 16500 |
| `gross_income = 3,000,000` | `99,000` | `2,901,000` | 3000000 × 0.033 = 99000 |
| `gross_income = 100` | `3` (반올림) | `97` | 100 × 0.033 = 3.3 → round = 3 |

### 13-2. 검증 오류 테스트

| 입력 | 기대 동작 |
|---|---|
| `gross_income = 0` | 결과 null, 오류 안내 |
| `gross_income = -1` | 결과 null, 오류 안내 |
| `gross_income = ""` | 계산 버튼 비활성 또는 null |

### 13-3. 사이트 생성 테스트

| 항목 | 검증 방법 |
|---|---|
| `index.html`에 카드 존재 | `grep "freelancer-tax-3p3" data/workspace/_site/index.html` |
| 계산기 페이지 존재 | `ls data/workspace/_site/freelancer-tax-3p3/index.html` |
| sitemap에 URL 포함 | `grep "freelancer-tax-3p3" data/workspace/_site/sitemap.xml` |
| 기존 7개 페이지 존재 | `ls data/workspace/_site/weekly-holiday-allowance/` (7개 반복) |

### 13-4. Registry 연동 테스트

```python
from modules.registry_loader import load_registry_v3, resolve
reg = load_registry_v3()
assert "freelancer-tax-3p3" in reg, "registry v3 미등록"
entry = resolve("freelancer-tax-3p3")
assert "income_tax_act_127" in str(entry.get("legal_refs", [])), "legal_refs 누락"
```

### 13-5. 기존 계산기 회귀 테스트

```python
# 기존 7개 slug가 load_registry_v3() 에서 모두 반환되는지
expected = {"weekly-holiday-allowance", "severance-pay", "annual-leave-allowance",
            "unemployment-benefit", "four-insurances", "연말정산_환급액_계산기", "육아휴직_급여_계산기"}
reg = load_registry_v3()
missing = expected - set(reg.keys())
assert not missing, f"기존 계산기 누락: {missing}"
```

### 13-6. WordPress V2 콘텐츠 품질 테스트 (H-4)

| 기준 | 통과 조건 |
|---|---|
| 길이 | 1800자 이상 |
| H2 개수 | 5~7개 |
| FAQ | 5개 이상 |
| 법령 조항 | "소득세법 제127조" 포함 |
| 3.3% 구성 설명 | "소득세 3%" + "지방소득세 0.3%" 또는 동등 표현 |
| 종합소득세 언급 | "5월 종합소득세" 또는 "종합소득세 신고" 포함 |
| 면책 문구 | 참고용 예상치 문구 포함 |

---

## 14. 완료 기준

Phase3-1 완료로 인정하는 조건 (전부 충족 필요):

### 필수 (전부 통과)

| # | 기준 | 검증 |
|---|---|---|
| C-01 | `docs/registry/tax.yaml`에 `freelancer-tax-3p3` 항목 존재 | `grep "freelancer-tax-3p3" docs/registry/tax.yaml` |
| C-02 | `docs/legal_master/tax.yaml`에 `income_tax_act_127` 항목 존재 | `grep "income_tax_act_127" docs/legal_master/tax.yaml` |
| C-03 | `docs/legal_basis.master.yaml`에 `freelancer-tax-3p3` 항목 존재 | `grep "freelancer-tax-3p3" docs/legal_basis.master.yaml` |
| C-04 | DB `calculators` 테이블에 slug `freelancer-tax-3p3` row 존재 | SQL SELECT |
| C-05 | `_site/freelancer-tax-3p3/index.html` 존재 | `ls` 확인 |
| C-06 | `_site/index.html`에 freelancer-tax-3p3 카드 포함 | `grep` 확인 |
| C-07 | `_site/sitemap.xml`에 URL 포함 | `grep` 확인 |
| C-08 | JS 계산: gross=1,000,000 → withholding=33,000, net=967,000 | 브라우저 직접 검증 또는 자동화 |
| C-09 | 기존 7개 계산기 `_site/` 페이지 모두 존재 (회귀 없음) | `ls` 7개 확인 |
| C-10 | `run_calculator_once("freelancer-tax-3p3")` 실행 완료 (WordPress 발행 또는 dry-run 확인) | CLI 실행 |
| C-11 | H-4 검수 PASS (QUALITY_SCORE ≥ 90) | pipeline 로그 |

### 선택 (권장)

| # | 기준 | 비고 |
|---|---|---|
| C-12 | `rms.py IMPACT_MAP`에 `income_tax_act_127` 등록 | P2-3 RMS 연동용 |
| C-13 | `site_generator.py` title/desc 문구 갱신 | SEO 보완, 낮은 우선순위 |

---

## 스케줄러 관련 결정 사항

**Phase3에서 스케줄러 연결하지 않는다.**

이번 Phase3-1에서 신규 계산기 추가 구조(YAML → DB → 사이트 생성 → V2 발행)가 처음으로 검증된다. 구조 안정성이 확인된 이후, 주 1~2개 계산기를 정기 추가하는 운영 단계에 진입할 때 스케줄러를 붙인다. Phase3-1 코드에 스케줄러 코드를 포함하지 않는다.

---

*이 문서는 Phase3-1 설계 전용입니다. 승인 전까지 코드 수정 없음.*
