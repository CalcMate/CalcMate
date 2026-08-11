# CA-3-2 사전조사 보고서 — AI Formula 제안 구조 조사

> 조사 기준일: 2026-08-10  
> 원칙: 코드 수정 0건 / 구현 없음 / 조사 전용  
> 기준 상태: CA-3-1 PASS (512 PASS / 1 FAIL known)

---

## 1. 현재 AI Formula 생성 구조

### 1-1. Formula 생성 위치

`generate_app()` (`modules/app_factory.py:545`) 내 **Step 1**:

```python
sys1 = (
    "너는 웹 계산기 기획자다. 주어진 계산기에 대해 입력/출력 스키마와 산식을 설계하라.\n"
    ...
    '{"calculator_type":"","input_schema":{},"output_schema":{},"formula":"또는{}","labels":{}}\n'
)
u1 = f"계산기명: {name}\n카테고리: {category}\n설명: {desc}"
t1, m1, k1 = _chat(cfg, "orchestrator", sys1, u1, 800)
spec = parse_json_lenient(t1)
# ← formula 여기서 추출:
formula = spec.get("formula", "")
```

**Formula는 항상 전체 스펙(입력/출력/수식/라벨)의 일부로 생성된다.** Formula만을 생성하는 단독 경로가 현재 없다.

### 1-2. 각 AI 단계별 역할

| 단계 | 담당 | Formula 관련 |
|------|------|-------------|
| Step 1 (orchestrator, 800 tok) | 기획자 — 스펙 설계 | **formula 생성** + input_schema + output_schema + labels |
| Step 2 (code, 4000 tok) | HTML 생성 | spec.formula를 HTML JS로 구현 |
| Step 3 (writer, 1500 tok) | SEO/FAQ/초안 | formula 무관 |
| Step 4 (image, 400 tok) | 이미지 프롬프트 | formula 무관 |

**CA-3-3 신규 함수는 Step 1 역할만 단독으로 수행하는 경량 버전이다.** Step 2/3/4 없음.

### 1-3. Formula 추출 및 검증 (기존)

```python
# Step 1 후 validate_formula() 즉시 실행 + 1회 재시도
ok, msg = validate_formula(spec.get("formula", ""), spec.get("input_schema", {}))
if not ok:
    retry_sys = sys1 + f"...(사유: {msg})..."
    t1b, m1b, k1b = _chat(cfg, "orchestrator", retry_sys, u1, 800)
    spec2 = parse_json_lenient(t1b)
    ok2, msg2 = validate_formula(spec2.get("formula", ""), spec2.get("input_schema", {}))
    if ok2:
        spec = spec2   # 유효하면 재시도 결과 채택
spec["_formula_valid"] = ok
spec["_formula_msg"]   = msg
```

### 1-4. Formula 전달 경로 (Mode B)

```
generate_app_with_contract()
    ↓
generate_app(cfg, ..., _contract=contract)
    ↓ _build_contract_enforcement_prompt(contract) → sys1에 삽입
    ↓ formula가 contract에 있으면 "고정 Formula" 섹션으로 AI에 전달
    ↓
spec["formula"] → 반환 dict
    ↓
save_app() → DB + Registry 저장
```

**Contract의 formula가 `None`이면 AI가 임의로 생성한다.** Contract의 formula가 있으면 `_build_contract_enforcement_prompt()`로 AI에 고정 지시.

### 1-5. AI vs 운영자 Formula 구분 가능 여부

현재: **구분 불가.** `generate_app()` 결과 `spec["formula"]`는 AI가 생성했는지, Contract에서 넘어왔는지 구분하는 플래그가 없다.

CA-3-3에서 `suggest_formula()`를 별도 함수로 구현하면, 그 반환값의 `formula_status="ai_suggested"`로 구분이 가능해진다.

### 1-6. 기존 기능 vs 신규 기능 경계

| | 기존 (`generate_app()`) | 신규 (`suggest_formula()`) |
|--|------------------------|--------------------------|
| 목적 | 계산기 전체 생성 | Formula만 제안 |
| AI 호출 수 | 4회 (스펙+HTML+SEO+이미지) | 1회 |
| 결과 | 완전한 app dict | formula 텍스트 + 검증 결과 |
| 저장 | `save_app()` 별도 호출 | 저장 없음 — Dashboard 표시만 |
| 진입점 | Mode A / Mode B 생성 버튼 | Contract Builder 내 [🤖 AI Formula 제안] 버튼 |
| formula_status | 기존 로직 그대로 | `"ai_suggested"` 반환 |

**두 경로는 완전히 독립이다. suggest_formula()는 generate_app()을 호출하지 않는다.**

---

## 2. suggest_formula() 최적 삽입 위치

**결론: `modules/app_factory.py`에 독립 함수로 추가**

이유:
- `_chat()` 함수가 app_factory.py에 있음 → 재사용 가능
- `build_contract()`, `check_hold_rules()` 와 같은 파일에 위치 → Contract 관련 함수 집약
- `generate_app()` 내부를 변경하지 않아도 됨

삽입 위치: `generate_app_with_contract()` 이전 (약 line 455 이전)

```python
def suggest_formula(cfg: dict, contract: dict) -> dict:
    """Contract 정보를 기반으로 AI가 formula를 제안한다. (CA-3-3 구현 예정)"""
    ...
```

---

## 3. 입력 데이터 선정

| 입력 | 필요성 | 근거 | 필수/선택 |
|------|--------|------|----------|
| calculator name | HIGH | AI 맥락 파악의 출발점 | 필수 |
| category | MEDIUM | Tier/도메인 암시적 맥락 | 선택 |
| description | MEDIUM | 계산기 목적 구체화 | 선택 |
| input_fields | **CRITICAL** | Level 2 변수 검증의 허용 목록 — 이것 없으면 검증 불가 | **필수** |
| output_fields | HIGH | dict vs str formula 결정 (복수 출력이면 dict 필요) | 필수 |
| legal_refs | HIGH | `load_legal_master()`로 `calculation_flow` 조회 가능 | 선택 (권장) |
| calculation_flow | HIGH | AI에게 가장 직접적인 formula 힌트 | legal_refs에서 자동 조회 |
| scope_exclusions | LOW | 수식 계산에 직접 영향 없음 (주의문 용도) | 선택 |
| test_cases | MEDIUM | Level 3 검증에 사용 가능하나 CA-3에서 필수 아님 | 선택 |

**최소 필수 입력**: `name`, `input_fields`, `output_fields`

**권장 입력**: + `legal_refs` (calculation_flow 자동 조회) + `desc`

---

## 4. legal_master 활용 가능성

### 4-1. 전체 entity 구조 (4개 파일)

| 파일 | entity_id | law | confidence |
|------|-----------|-----|-----------|
| labor.yaml | `labor_standards_act_55` | 근로기준법 제55조 | high |
| labor.yaml | `worker_retirement_benefit_act_8` | 근로자퇴직급여 보장법 제8조 | high |
| labor.yaml | `labor_standards_act_60` | 근로기준법 제60조 | high |
| employment.yaml | `employment_insurance_act_40` | 고용보험법 제40조 | **medium** |
| employment.yaml | `employment_insurance_act_70` | 고용보험법 제70조 | high |
| insurance.yaml | `four_major_insurances` | 4대보험 (복합) | high |
| tax.yaml | `income_tax_act_137` | 소득세법 제137조 | **medium** |
| tax.yaml | `income_tax_act_127` | 소득세법 제127조 | high |

**`load_legal_master()` 반환 구조**: `{entity_id: {law, article, confidence, calculation_flow, ...}}`

`calculation_flow` 조회:
```python
lm = load_legal_master()
calc_flows = []
for ref in contract.get("legal_refs") or []:
    flow = (lm.get(ref) or {}).get("calculation_flow") or []
    calc_flows.extend(flow)
```

### 4-2. calculation_flow 유형별 분류

| entity_id | calculation_flow 핵심 내용 | 유형 | AI Formula 변환 가능성 |
|-----------|--------------------------|------|----------------------|
| `labor_standards_act_55` | `"주휴수당 = 1일 소정근로시간 × 시급"` | **A** | ✅ 직접 변환 가능 |
| `income_tax_act_127` | `"합산 원천징수세액 = 총 수입 × 3.3%"` | **A** | ✅ 직접 변환 가능 |
| `worker_retirement_benefit_act_8` | `"퇴직금 = 평균임금 일액 × 30 × (근속일수 ÷ 365)"` | **A** (간이 방식) | ✅ 직접 변환 가능 |
| `labor_standards_act_60` | `"연차수당 = 일급 × 미사용 연차일수"` (수당 부분) | **A** | ✅ 직접 변환 가능 |
| `labor_standards_act_60` | `"3년 이상: 2년마다 1일 추가(최대 25일)"` (잔여 부분) | **B** | ⚠️ min/max 필요 — 해석 후 변환 |
| `four_major_insurances` | `"국민연금 = 월급여 × 4.5%", "건강보험 × 3.545%"...` | **B** | ⚠️ dict formula, 요율 매년 변경 |
| `employment_insurance_act_40` | `"소정급여일수 = 나이·피보험기간 별표"`, `"상한 매년 변경"` | **D** | ❌ 테이블 의존 |
| `employment_insurance_act_70` | `"일반: 월 통상임금의 80% (매년 변경 상·하한)"` | **D** | ❌ CUSTOM_COMPUTE_SLUGS |
| `income_tax_act_137` | 다단계 공제 + 세율 구간 + deduction_rules | **D** | ❌ CUSTOM_COMPUTE_SLUGS + confidence=medium |

**유형 정의**:
- **A**: Python Formula로 직접 변환 가능 (단순 산술식)
- **B**: 약간의 해석 후 변환 가능 (min/max, dict formula)
- **C**: 조건/선택지 필요 (formula_engine만으로 한계, test_cases 없으면 검증 한계)
- **D**: 테이블/법정 기준값 의존 → formula_engine으로 불가

---

## 5. 계산기 유형별 AI Formula 제안 가능성

### Type A — 단순 산술 (AI Formula: ✅ 높음)

| 계산기 | slug | 현재 formula | legal_refs | AI 제안 가능 |
|--------|------|-------------|-----------|------------|
| 주휴수당 | `weekly-holiday-allowance` | `hourly_wage * (weekly_hours / 40) * 8` | `labor_standards_act_55` | ✅ |
| 연차수당 | `annual-leave-allowance` | `daily_wage * unused_days` | `labor_standards_act_60` | ✅ |
| 퇴직금 (간이) | `severance-pay` | `avg_monthly_wage * (total_days / 365)` | `worker_retirement_benefit_act_8` | ✅ |
| 3.3% 원천징수 | (미구현) | `income * 0.033` | `income_tax_act_127` | ✅ |

**운영자 검토 필수**: 법적 정확성은 AI가 보증하지 않는다.

### Type B — 다중 출력 / 복합 산식 (AI Formula: ⚠️ 중간)

| 계산기 | slug | 현재 formula (요약) | legal_refs | AI 제안 가능 |
|--------|------|-------------------|-----------|------------|
| 4대보험 | `four-insurances` | dict: 연금/건강/장기요양/고용/총액 | `four_major_insurances` | ⚠️ dict 생성 가능, 요율 검증 필수 |
| 연차 잔여일 | `annual-leave-remaining` | `15 + min(max(0, (years-1)//2), 10)` | `labor_standards_act_60` | ⚠️ min/max 표현 가능, 조건 검증 필수 |

**제한**: 요율이 매년 변경되는 경우(4대보험), AI가 이전 연도 값을 사용할 수 있다. 운영자가 최신 요율을 직접 확인 후 수정해야 한다.

### Type C — 조건부 (AI Formula: ⚠️ 중간-낮음)

formula_engine이 `min()`, `max()`를 지원하므로 단순 capping은 표현 가능하다. 그러나:
- 다중 조건분기 (`if/else`)는 formula_engine이 지원하지 않음
- AI가 조건을 `min(max(...))` 패턴으로 표현할 수 있는지 불확실
- test_cases 없이는 Level 3 검증 불가 → 논리 오류 무감지 위험

**판정**: AI Formula 제안 허용하되 test_cases 입력을 강력 권장.

### Type D — 테이블/법령 데이터 의존 (AI Formula: ❌ 제한/금지)

| 계산기 | 이유 | 처리 |
|--------|------|------|
| 실업급여 (`unemployment-benefit`) | `소정급여일수`는 나이·피보험기간 별표 참조 필요. `employment_insurance_act_40` confidence=**medium** → HOLD-3 발동 | CA-4 이연 또는 금지 |
| 연말정산 (`연말정산_환급액_계산기`) | CUSTOM_COMPUTE_SLUGS, confidence=medium, 다단계 공제 | formula 방식 완전 불가 |
| 육아휴직 (`육아휴직_급여_계산기`) | CUSTOM_COMPUTE_SLUGS, 매년 상·하한 변경 | formula 방식 완전 불가 |

**Type D 계산기에 AI Formula 제안 버튼이 활성화되면 안 된다.** Dashboard에서 `CUSTOM_COMPUTE_SLUGS` + confidence=medium entity를 포함하는 경우 버튼 비활성 처리 필요.

---

## 6. Prompt 설계 권고

### 6-1. 구성요소별 필요성

```
[필수]
- 계산기명: {name}
- 입력 변수: {input_fields}  ← Level 2 검증의 허용 목록과 동일
- 출력 변수: {output_fields} ← dict vs str 결정

[권장]
- 설명: {desc}
- 법령 계산 흐름: {calculation_flow items}

[선택]
- 제외 범위: {scope_exclusions}
```

### 6-2. 핵심 질문 답변

**Q1. `calculation_flow`를 그대로 AI에게 전달해도 되는가?**

A: 대부분 YES. `calculation_flow`의 내용이 이미 사람이 검토한 법령 설명이기 때문이다. 단, Type D (테이블/상한 변경)의 경우 AI가 하드코딩된 숫자를 임의로 사용할 수 있어 위험하다. 전달 전에 유형을 판단하거나, 프롬프트에 "변경 가능한 법정 기준값은 하드코딩하지 말 것" 제약을 추가해야 한다.

**Q2. 자연어 calculation_flow를 AI가 잘못 해석할 위험은?**

A: Type A/B는 낮음 — 수식이 명확하기 때문. Type C는 중간 — 조건 표현을 잘못 변환 가능. Type D는 높음 — 상한/하한/테이블을 AI가 고정값으로 추정할 수 있음.

**Q3. AI가 법률 내용을 임의로 만들지 않도록 필요한 제약은?**

A: 두 가지:
1. 프롬프트에 `"입력 변수({input_fields})만 사용. 다른 변수 절대 금지."` → Level 2가 자동 방어
2. 프롬프트에 `"calculation_flow에 없는 상수·요율을 추가하지 말 것."` → 논리 오류 부분 방어

**Q4. `legal_refs`가 없는 경우 Formula 제안을 허용할 것인가?**

A: 허용하되, Dashboard에 경고 표시. `legal_refs` 없이 AI가 Formula를 제안하면 법적 근거 없는 임의 수식이 될 수 있다. HOLD-3는 medium confidence일 때만 발동하므로 별도 경고 필요.

**Q5. `confidence=medium` 법령 사용 시 필요한 경고는?**

A: `check_hold_rules()` HOLD-3이 자동으로 발동한다. `suggest_formula()` 자체에서는 추가 경고가 없어도 HOLD-3 처리로 충분하다. 단, `suggest_formula()` 반환값에 `"warnings": ["confidence=medium 법령 포함"]`을 추가하면 Dashboard에서 운영자에게 즉시 전달 가능.

**Q6. AI가 Formula를 만들 수 없는 경우 반환값은?**

A:
```python
{"formula": None, "formula_status": "not_generated", "valid": False, "message": "AI가 Formula를 생성하지 못했습니다.", "warnings": ["..."]}
```

Dashboard는 이 경우 formula text_area를 건드리지 않고 error 메시지만 표시.

### 6-3. 권장 프롬프트 구조

```python
sys_suggest = (
    "너는 계산기 수식 설계자다. 아래 정보로 Python 산술 수식만 제안하라.\n"
    f"입력 변수(이것만 사용 가능): {input_fields}\n"
    f"출력 변수: {output_fields}\n"
    + (f"계산기 설명: {desc}\n" if desc else "")
    + (f"법령 계산 흐름(참고):\n" + "\n".join(f"  - {f}" for f in calc_flows) if calc_flows else "")
    + "\n규칙:\n"
    "1. 입력 변수 목록 외 다른 변수 절대 사용 금지\n"
    "2. 단일 출력: 산술 표현식 문자열\n"
    "   복수 출력: {출력키: 산술식} JSON (출력 변수 목록과 일치)\n"
    "3. 대입문(=), 함수 정의, 외부 함수 호출 금지\n"
    "4. 허용 함수: min, max, round, abs, int, float 만\n"
    "5. 법령에 명시되지 않은 상수·요율 추가 금지\n"
    "6. Formula만 반환 — 설명문 없음\n"
    "   단일: \"a * b\"\n"
    "   복수: {\"out1\": \"a + b\", \"out2\": \"a * 0.045\"}"
)
```

---

## 7. AI 출력 Schema 권고

### 7-1. 후보 비교

**후보 A (formula only)**
```
a * hourly_wage
```
- Pro: 파싱 간단
- Con: warnings/이유 없음, 파싱 실패 시 fallback 없음

**후보 B (formula + warnings)**
```json
{"formula": "a * hourly_wage", "warnings": ["요율이 매년 변경될 수 있습니다"]}
```
- Pro: 운영자에게 warnings 전달, `parse_json_lenient()`으로 처리 가능
- Con: dict 반환 시 formula 값이 dict인데 JSON 중첩이 복잡해짐

**후보 C (formula + reason + assumptions + warnings)**
```json
{"formula": "...", "reason": "...", "assumptions": [], "warnings": []}
```
- Pro: 완전한 메타데이터
- Con: max_tokens 증가 필요, 파싱 복잡도 증가

### 7-2. 권고: **후보 B (formula + warnings)**

이유:
- 기존 `parse_json_lenient()` 그대로 사용 가능
- dict formula의 경우 `formula` 필드에 JSON object → `json.dumps(formula)` 필요하지만 처리 가능
- `warnings`는 list of str → Dashboard에서 `st.warning()`으로 표시
- max_tokens 300으로 충분 (후보 C는 500+)

**suggest_formula() 반환 Schema**:
```python
{
    "formula": str | dict | None,   # AI 제안 수식
    "formula_status": "ai_suggested" | "not_generated",
    "valid": bool,                  # Level 1+2 검증 결과
    "message": str,                 # 검증 메시지
    "sample_results": list,         # Level 3 (test_cases 있을 때)
    "warnings": list[str],          # AI 제안 시 주의사항
}
```

---

## 8. Formula Lifecycle 연결

### 8-1. 권장 Lifecycle (CA-3-1에서 확정)

```
not_generated
    ↓ [🤖 AI Formula 제안] 클릭
ai_suggested          ← suggest_formula() 반환
    ↓ 운영자 수동 수정
pending_validation    ← CA-3-1 수정 감지 로직 작동
    ↓ [🔍 Formula 검증] 통과
pending_validation    ← 기존 로직 유지 (버튼 클릭 시 pending_validation 유지)
    ↓ [✅ Formula 확정]
operator_confirmed
```

**주의**: AI 제안 후 검증 통과만으로 `operator_confirmed` 자동 부여 금지.
- `[✅ Formula 확정]` 버튼은 `_fv_passed=True`일 때만 활성화됨 (CA-2-6-2 기존 로직)
- `ai_suggested` → `pending_validation` → `operator_confirmed` 흐름은 운영자 2번의 명시적 행동이 필요

### 8-2. ai_suggested에서 직접 operator_confirmed로 가는 경로 차단

- `check_hold_rules()`: `ai_suggested != "operator_confirmed"` → HOLD-1 발동 (CA-3-1에서 확인)
- Dashboard [✅ Formula 확정] 버튼: `disabled=not _fv_passed` (기존 로직)
- `_fv_passed`는 [🔍 Formula 검증] 결과이며, AI 제안 직후 자동 검증 통과 여부와 무관

**따라서 기존 코드 변경 없이 차단이 보장된다.** ✅

---

## 9. validate_formula_with_samples() 연결

### 9-1. AI 제안 Formula 즉시 검증 가능 여부

YES — 변경 없이 그대로 재사용 가능.

```python
# suggest_formula() 내부에서:
schema = {f: "number" for f in contract.get("input_fields") or []}
result = validate_formula_with_samples(formula, schema, contract.get("test_cases") or None)
```

### 9-2. input_fields → input_schema 변환

```python
schema = {f: "number" for f in input_fields}
```

이 패턴은 Dashboard CA-2-6-2에서 이미 동일하게 사용 중. 검증됨.

### 9-3. test_cases 필요성

| Level | 조건 | 검증 내용 |
|-------|------|----------|
| Level 1 | 항상 | 구문 오류, 금지 노드 |
| Level 2 | 항상 (input_schema 있을 때) | input_fields에 없는 변수 사용 |
| Level 3 | test_cases 있을 때만 | 실제 계산 결과 확인 |

**test_cases 없어도 Level 1+2로 기본 안전성 검증 가능.** Level 3는 선택적.

### 9-4. 새 검증 함수 필요 여부

불필요. `validate_formula_with_samples()` 그대로 재사용.

---

## 10. Dashboard 연결점

### 10-1. 현재 Contract Builder UI 구조

```
[Line 2225] Contract Builder expander
  [Line 2232] slug 입력
  [Line 2236] input_fields 입력
  [Line 2240] output_fields 입력
  [Line 2244] Formula text_area (key="af_contract_formula")
              ↑ ── [🤖 AI Formula 제안] 버튼 삽입 위치 ──
  [Line 2250] formula_status 배지 (CA-2-6-2)
  [Line 2267] test_cases text_area
  [Line 2274] Formula 수정 감지 블록 (CA-2-6-2)
  [Line 2283] CA-3-1 ai_suggested 수정 감지 블록
  [Line 2291] [🔍 Formula 검증] 버튼
  [Line 2326] [✅ Formula 확정] 버튼
  [Line ~2395] [📋 Contract 기반 생성] 버튼
```

### 10-2. [🤖 AI Formula 제안] 버튼 최적 위치

**Formula text_area 직후 (line 2249 이후), 배지 이전.**

이 위치가 자연스러운 이유:
1. 운영자가 formula를 직접 입력하거나 AI에게 제안받는 선택지가 같은 위치에 있음
2. AI 제안 클릭 → formula text_area에 자동 주입 → 배지가 `ai_suggested`로 표시 → [🔍 Formula 검증] → [✅ Formula 확정]의 흐름이 위에서 아래로 자연스럽게 연결됨

### 10-3. 버튼 비활성 조건 (CA-3-4에서 구현)

```python
_af_suggest_disabled = (
    not _af_input_fields.strip()    # input_fields 없음
    or not _af_output_fields.strip() # output_fields 없음
)
```

CUSTOM_COMPUTE_SLUGS + Type D 계산기에 대한 추가 비활성은 CA-4에서 처리.

### 10-4. text_area 자동 주입 방법

```python
# suggest_formula() 결과 수신 후:
st.session_state["af_contract_formula"] = str(result["formula"])
st.session_state["af_formula_ai_suggested_text"] = str(result["formula"])  # CA-3-1 수정 감지용
if st.session_state.get("af_contract"):
    st.session_state["af_contract"]["formula_status"] = "ai_suggested"
st.rerun()
```

`st.session_state["af_contract_formula"]` 주입 + `st.rerun()`은 기존 `af_formula_confirmed_text` 처리와 동일 패턴. 작동 검증됨.

### 10-5. 기존 formula 덮어쓰기 방지 (2-click 패턴)

```python
if st.button("🤖 AI Formula 제안", key="af_formula_ai_suggest", disabled=_af_suggest_disabled):
    if _af_formula.strip() and not st.session_state.get("_af_ai_suggest_override"):
        st.warning("⚠️ 기존 Formula가 있습니다. 다시 클릭하면 덮어씁니다.")
        st.session_state["_af_ai_suggest_override"] = True
    else:
        st.session_state.pop("_af_ai_suggest_override", None)
        # suggest_formula() 실제 호출 — CA-3-4에서 구현
```

---

## 11. 위험요소 및 방어책

| 위험 | 발생 가능성 | 현재 방어 | CA-3 대응 | CA-4 이연 |
|------|------------|----------|----------|----------|
| **R-1** AI가 없는 입력 변수 사용 | **높음** | Level 2 자동 차단 ✅ | 추가 불필요 | — |
| **R-2** AI가 없는 출력 키 사용 (dict) | 중간 | 없음 | dict 키 ⊆ output_fields 검사 추가 | — |
| **R-3** calculation_flow 잘못 해석 | 중간 (Type A/B 낮음, C/D 높음) | Level 1/2 부분 차단 | 유형 제한 + 운영자 확인 | Type D 완전 차단 |
| **R-4** AI가 법률 내용 임의 추론 | 중간 | HOLD-1 (운영자 확인 필수) ✅ | Prompt 제약 추가 | — |
| **R-5** 미검증 formula → operator_confirmed | **낮음** | [✅ 확정] disabled until 검증 ✅ | 추가 불필요 | — |
| **R-6** AI 제안이 기존 formula 덮어씀 | **높음** | 없음 | 2-click 확인 패턴 구현 | — |
| **R-7** AI 호출 실패 | 낮음 | 없음 | try/except → error 반환 | — |
| **R-8** AI 응답 파싱 불가 | 중간 | `parse_json_lenient()` 부분 방어 | 경량 파싱 + Level 1 fallback | — |

### CA-3에서 반드시 구현할 방어 (R-2, R-6, R-7, R-8)

**R-2 대응**: `suggest_formula()` 내부에서:
```python
if isinstance(formula, dict):
    output_fields = set(contract.get("output_fields") or [])
    if output_fields and not set(formula.keys()).issubset(output_fields):
        return {"formula": None, "formula_status": "not_generated",
                "valid": False, "message": f"AI가 잘못된 출력 키를 사용했습니다: {set(formula.keys()) - output_fields}"}
```

**R-6 대응**: 2-click override 패턴 (10-5 참조)

**R-7 대응**: try/except around `_chat()` call → error dict 반환

**R-8 대응**: 
```python
raw = t.strip()
try:
    parsed = json.loads(raw)
    formula = parsed.get("formula", raw)  # B형 출력이면 formula 키 추출
    warnings = parsed.get("warnings", [])
except:
    formula = raw.strip('"\'')  # A형 — raw text를 formula로 사용
    warnings = []
```

---

## 12. 기존 기능 영향도

| 기능 | 영향 | 근거 |
|------|------|------|
| Mode A (`generate_app()` 직접 호출) | ✅ 없음 | `suggest_formula()`는 독립 함수 |
| Mode B (`generate_app_with_contract()`) | ✅ 없음 | 별도 경로 |
| 기존 9개 Calculator 생성 | ✅ 없음 | Registry 변경 없음 |
| `validate_against_contract()` | ✅ 없음 | 변경 없음 |
| `check_hold_rules()` | ✅ 없음 | `ai_suggested` 이미 CA-3-1에서 처리 |
| `save_app()` | ✅ 없음 | `suggest_formula()`는 저장하지 않음 |
| `delete_app()` | ✅ 없음 | 무관 |
| Contract Instance 저장/로드 | ✅ 없음 | `formula_status="ai_suggested"` 이미 CA-3-1에서 처리 |
| 블로그 생성 Pipeline | ✅ **완전 분리** | 블로그 파이프라인은 Registry v3 + DB 읽음. `suggest_formula()`는 Dashboard 세션 내에서만 작동 |
| WordPress Publishing Pipeline | ✅ 없음 | 동일 이유 |
| `CUSTOM_COMPUTE_SLUGS` | ✅ 없음 | `suggest_formula()`는 slug를 받지 않으므로 간섭 없음 |

**블로그/WordPress 파이프라인 경계 확인**:
- 블로그 파이프라인 → `load_registry_v3()` → `docs/registry/*_af.yaml` 읽음
- `suggest_formula()` → Dashboard 세션 상태만 → 파이프라인에 연결되지 않음
- **완전 분리** ✅

---

## 13. Regression 영향 예측

### 예상 수정 파일 및 위험도

| 파일 | 변경 내용 | 위험도 |
|------|-----------|--------|
| `modules/app_factory.py` | `suggest_formula()` 신규 함수 추가 | 낮음 (기존 함수 무변경) |
| `dashboard.py` | [🤖 AI Formula 제안] 버튼 + 세션 스테이트 + 확인 패턴 | 중간 (Streamlit rerun 순서) |
| `tests/test_formula_contract.py` | `suggest_formula()` 단위 테스트 (AI mock 사용) | 낮음 |

### 기존 테스트 깨질 가능성

| 테스트 파일 | 위험 | 이유 |
|------------|------|------|
| `test_formula_contract.py` | ✅ 없음 | 신규 함수만 추가 |
| `test_app_factory_contract.py` | ✅ 없음 | `generate_app()` 변경 없음 |
| `test_af_contract_dashboard.py` | ⚠️ 낮음 | Dashboard 변경 시 일부 재확인 필요 |
| `test_review_center.py` | ✅ 없음 | 무관 |
| `production_validation_test.py` | ✅ FAIL 유지 (known) | 기존 이유 그대로 |
| Blog pipeline 테스트 | ✅ 없음 | suggest_formula()와 분리 |

---

## 14. 예상 수정 파일

| 단계 | 파일 | 예상 변경 줄수 |
|------|------|--------------|
| CA-3-3 | `modules/app_factory.py` | +40-50줄 (suggest_formula 함수) |
| CA-3-3 | `tests/test_formula_contract.py` 또는 신규 | +50-60줄 (mock AI 테스트) |
| CA-3-4 | `dashboard.py` | +60-80줄 (버튼 + 세션 로직) |

**변경 금지 파일**: `docs/registry/*.yaml`, `docs/legal_master/*.yaml`, `docs/contract_schema/instances/*.yaml`

---

## 15. CA-3-3 이후 구현 순서

```
CA-3-1  ai_suggested 상태 도입              ✅ 완료
CA-3-2  AI Formula 제안 구조 조사           ← 현재 (완료)
CA-3-3  suggest_formula() 구현             ← 다음
          - modules/app_factory.py에 함수 추가
          - AI 호출: _chat(cfg, "orchestrator", sys_suggest, ...)
          - parse → dict or str formula
          - R-2 dict 키 검증
          - validate_formula_with_samples() 실행
          - try/except AI 호출 오류 처리
          - 반환: {formula, formula_status, valid, message, sample_results, warnings}
CA-3-4  Dashboard AI 제안 버튼 연결         ← CA-3-3 후
          - [🤖 AI Formula 제안] 버튼 추가
          - 2-click override 패턴
          - spinner 중 실행
          - 결과 → text_area + af_formula_ai_suggested_text
          - warnings → st.warning() 표시
CA-3-5  E2E + Regression
          - 전체 pytest 실행
          - 기준선: 512 PASS / 1 FAIL (known) + 신규 PASS 추가
CA-3-F  최종 검증
          - CA-3 완료 보고서
```

---

## 16. 최종 판정

### ① 구현 가능 여부

**CONDITIONAL PASS**

- `suggest_formula()` 구현 자체는 기술적으로 가능
- R-2(출력 키 검증), R-6(덮어쓰기 확인), R-7(예외 처리), R-8(파싱) 4개 방어책을 반드시 CA-3에서 구현해야 함
- Type D 계산기 UI 비활성은 CA-4에서 처리 가능 (CUSTOM_COMPUTE_SLUGS 기반)

### ② 권장 AI Formula 제안 범위

| 유형 | 허용 여부 | 조건 |
|------|----------|------|
| Type A (단순 산술) | ✅ 허용 | 운영자 확인 필수 |
| Type B (다중 출력) | ⚠️ 허용 | 요율 변경 주의 경고 + 운영자 확인 필수 |
| Type C (min/max 조건) | ⚠️ 조건부 허용 | test_cases 강력 권장 + 운영자 확인 필수 |
| Type D (테이블/상한) | ❌ CA-4 이연 | CUSTOM_COMPUTE_SLUGS 또는 confidence=medium → HOLD-3 자동 차단 |

### ③ CA-3-3 구현 권고안

**최소 변경 원칙**:

```python
# modules/app_factory.py — suggest_formula() 신규 함수
def suggest_formula(cfg: dict, contract: dict) -> dict:
    # 1. input/output 정보 추출
    # 2. legal_refs → load_legal_master() → calculation_flow 조회
    # 3. sys_suggest 프롬프트 구성 (6-3 템플릿 기반)
    # 4. _chat(cfg, "orchestrator", sys_suggest, u_suggest, 300)
    # 5. 응답 파싱 (B형 JSON 또는 raw string)
    # 6. R-2: dict 키 검증
    # 7. validate_formula_with_samples(formula, schema, test_cases)
    # 8. 반환
```

삽입 위치: `generate_app_with_contract()` 이전 (~line 455)

**Dashboard (CA-3-4)**:
- 삽입 위치: `st.text_area(..., key="af_contract_formula")` 이후, 배지 이전
- 세션 스테이트: `_af_ai_suggest_override` (2-click 패턴용)
- `af_formula_ai_suggested_text`: CA-3-1에서 이미 수정 감지 로직 준비 완료

### ④ CA-4 이연 항목

| 항목 | 이유 |
|------|------|
| Type D 계산기에 AI 제안 버튼 비활성 | CUSTOM_COMPUTE_SLUGS 기반 slug 검사 필요 — CA-3에서 가능하나 별도 조사 필요 |
| AI test_cases 자동 제안 | 별도 복잡도 |
| Formula 버전 관리/히스토리 | Contract Instance 구조 확장 |
| multi-formula 후보 제시 | UI 복잡도 |
| AI 제안 결과 로깅 | audit trail 필요 |
| legal_master confidence=medium 자동 비활성 | HOLD-3 기존 처리로 충분하나 UI 개선 가능 |

---

**핵심 결론**:

> CA-3-3에서 `suggest_formula()`가 제안하는 것은 "운영자가 검토할 Formula 초안"이다.
> AI 제안 ≠ Formula 검증 ≠ 운영자 확정 ≠ 법적 정확성 보증.
> 기존 HOLD-1 + [🔍 검증] + [✅ 확정] 2단계가 모든 안전장치다.
> `suggest_formula()`는 이 흐름의 시작점(not_generated → ai_suggested)만 담당한다.
