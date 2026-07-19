# -*- coding: utf-8 -*-
"""four-insurances computeResult Python 미러 + 회귀 테스트 4종.

JS computeResult와 동일 로직을 Python으로 재현하여:
  1. 계산 순서 회귀 (LTC = HI × LTC_RATE, 급여 직접 곱 금지)
  2. 내부 합계 검증 (total == sum(개별항목))
  3. legal_basis ↔ 코드 동기화 (YAML 요율 → 정부 기준 fixture 비교)
  4. 경계값 3점 세트 + 일반/극단값

테스트 추가/삭제 금지 — 회귀 안전망. 요율 변경 시 YAML + fixture만 갱신.
"""
import math, sys, os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ─── 요율 상수 (legal_basis.draft.yaml insurance_rates와 동기화) ──────────────
NP_RATE  = 0.045
NP_MIN   = 390_000
NP_MAX   = 6_170_000
HI_RATE  = 0.03545
LTC_RATE = 0.1296
EI_RATE  = 0.009


def compute_fi(monthly_salary: float) -> dict | None:
    """JS computeResult 완전 미러."""
    if monthly_salary <= 0:
        return None
    out = {}

    # FI-2: 국민연금 기준소득월액 클램프
    np_base = min(max(monthly_salary, NP_MIN), NP_MAX)
    national_pension = np_base * NP_RATE

    # FI-1: 장기요양보험 = 건강보험료 × LTC_RATE (급여 직접 곱 금지)
    health_insurance = monthly_salary * HI_RATE
    long_term_care   = health_insurance * LTC_RATE
    employment_insurance = monthly_salary * EI_RATE

    # FI-3: total = 4종 합산
    total = national_pension + health_insurance + long_term_care + employment_insurance

    out["national_pension"]     = national_pension
    out["health_insurance"]     = health_insurance
    out["long_term_care"]       = long_term_care
    out["employment_insurance"] = employment_insurance
    out["total"]                = total

    # FI-9: notices — 우선순위별 별도 배열 → concat으로 명시적 순서 확정
    # 순서: [1] 국민연금 상·하한, [2] 산재보험 안내
    _np_notices = []
    _si_notices = []

    if monthly_salary < NP_MIN:
        _np_notices.append(
            f"월급여({monthly_salary:,.0f}원)가 기준소득월액 하한({NP_MIN:,}원)보다 낮아 "
            "국민연금은 하한 기준으로 계산됩니다 (국민연금법 제88조)."
        )
    elif monthly_salary > NP_MAX:
        _np_notices.append(
            f"월급여({monthly_salary:,.0f}원)가 기준소득월액 상한({NP_MAX:,}원)을 초과하여 "
            "국민연금은 상한 기준으로 계산됩니다 (국민연금법 제88조)."
        )

    _si_notices.append(
        "산재보험은 사업주가 전액 부담합니다 — "
        "근로자 급여에서 공제되지 않습니다 (산업재해보상보험법 제13조)."
    )

    out["notices"] = _np_notices + _si_notices

    # FI-8: _formula — 5단계 순서 표시 (장기요양 단계에 건강보험료 금액 명시)
    np_label_val = (NP_MIN if monthly_salary < NP_MIN
                    else (NP_MAX if monthly_salary > NP_MAX else monthly_salary))
    out["_formula"] = (
        f"국민연금 {np_label_val:,.0f}원 × {NP_RATE*100:g}% = {round(national_pension):,}원 | "
        f"건강보험 {monthly_salary:,.0f}원 × {HI_RATE*100:g}% = {round(health_insurance):,}원 | "
        f"장기요양 건강보험료 {round(health_insurance):,}원 × {LTC_RATE*100:g}% = {round(long_term_care):,}원 | "
        f"고용보험 {monthly_salary:,.0f}원 × {EI_RATE*100:g}% = {round(employment_insurance):,}원"
    )

    return out


def _round(v): return round(v)


# ═══════════════════════════════════════════════════════════════════════════════
# 헬퍼: 모든 케이스에서 total == sum(개별항목) 검증 (내부 합계 회귀)
# ═══════════════════════════════════════════════════════════════════════════════

def _assert_total_equals_sum(out: dict, tol: float = 0.01):
    """FI-3 회귀: total이 개별 보험료 4종의 합과 일치하는지 검증.

    향후 필드 추가/계산식 변경 시 total 누락을 자동 감지.
    """
    expected = (out["national_pension"]
                + out["health_insurance"]
                + out["long_term_care"]
                + out["employment_insurance"])
    assert abs(out["total"] - expected) < tol, (
        f"total({out['total']:.4f}) ≠ 개별합({expected:.4f}) — FI-3 회귀 실패"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 입력 검증
# ═══════════════════════════════════════════════════════════════════════════════

def test_invalid_zero():
    assert compute_fi(0) is None

def test_invalid_negative():
    assert compute_fi(-1_000_000) is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 정상 케이스 (300만원)
# ═══════════════════════════════════════════════════════════════════════════════

def test_normal_300():
    out = compute_fi(3_000_000)
    assert out is not None
    assert _round(out["national_pension"])    == 135_000   # 3,000,000 × 4.5%
    assert _round(out["health_insurance"])    == 106_350   # 3,000,000 × 3.545%
    assert _round(out["long_term_care"])      == 13_783    # 106,350 × 12.96%
    assert _round(out["employment_insurance"])== 27_000    # 3,000,000 × 0.9%
    assert _round(out["total"])              == 282_133    # 합산
    _assert_total_equals_sum(out)
    # 정상 범위: NP notices 없음, 산재보험 notice만 1개
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. [회귀 1] 장기요양보험 계산 순서 — salary × LTC_RATE 방식 명시적 실패 검출
# ═══════════════════════════════════════════════════════════════════════════════

def test_ltc_order_must_use_health_insurance():
    """FI-1 핵심: long_term_care = health_insurance × LTC_RATE.

    잘못된 방식(salary × LTC_RATE)은 300만원 기준 375,017원 초과 → 반드시 실패해야 함.
    이 테스트가 통과하면 올바른 계산 순서가 유지된 것.
    """
    salary = 3_000_000
    out = compute_fi(salary)
    assert out is not None

    wrong_ltc = salary * LTC_RATE            # 388,800원 (급여에 직접 곱)
    correct_ltc = salary * HI_RATE * LTC_RATE  # 13,783원 (건강보험료에 곱)

    # 두 값의 차이가 충분히 커서 혼동 불가능
    assert abs(wrong_ltc - correct_ltc) > 370_000, "테스트 설계 오류: 두 값이 너무 가까움"

    # 실제 계산 결과는 올바른 값이어야 함
    assert abs(out["long_term_care"] - correct_ltc) < 1, (
        f"장기요양 계산 오류: {out['long_term_care']:.2f}원 (올바른 값 {correct_ltc:.2f}원, "
        f"잘못된 값 {wrong_ltc:.2f}원) — 급여에 직접 곱한 것으로 의심"
    )
    _assert_total_equals_sum(out)


def test_ltc_order_extreme():
    """1000만원 급여에서도 올바른 순서 유지 확인."""
    salary = 10_000_000
    out = compute_fi(salary)
    assert out is not None

    hi = salary * HI_RATE
    correct_ltc = hi * LTC_RATE    # 45,943원
    wrong_ltc   = salary * LTC_RATE  # 1,296,000원

    assert abs(out["long_term_care"] - correct_ltc) < 1, (
        f"장기요양 순서 오류: 실제={out['long_term_care']:.2f}, 올바른={correct_ltc:.2f}"
    )
    _assert_total_equals_sum(out)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. [회귀 2] 내부 합계 검증 — 모든 일반/경계 케이스
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("salary", [
    200_000, 390_000, 391_000,
    3_000_000,
    6_170_000, 6_169_000, 6_171_000,
    10_000_000,
])
def test_total_equals_sum_all_cases(salary):
    """FI-3 회귀: 모든 급여 수준에서 total == 4종 합산."""
    out = compute_fi(salary)
    assert out is not None
    _assert_total_equals_sum(out)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. [회귀 3] legal_basis ↔ 코드 동기화 (YAML 요율 → 정부 기준 fixture 비교)
# ═══════════════════════════════════════════════════════════════════════════════

def test_legal_basis_sync_300():
    """YAML 요율(NP_RATE/HI_RATE/LTC_RATE/EI_RATE)로 계산한 값이 정부 기준 fixture와 일치.

    내년 요율 변경 시: YAML insurance_rates 수정 → 상수 동기화 → 이 fixture 갱신.
    """
    out = compute_fi(3_000_000)
    # 정부 기준 fixture (2025년 요율 기준)
    assert _round(out["national_pension"])     == 135_000   # 3,000,000 × 4.5%
    assert _round(out["health_insurance"])     == 106_350   # 3,000,000 × 3.545%
    assert _round(out["long_term_care"])       == 13_783    # 106,350 × 12.96%
    assert _round(out["employment_insurance"]) == 27_000    # 3,000,000 × 0.9%
    _assert_total_equals_sum(out)


def test_legal_basis_sync_np_rates():
    """국민연금 요율 4.5% 적용 확인 — 상한 범위 내 일반값."""
    salary = 2_000_000
    out = compute_fi(salary)
    expected_np = 2_000_000 * 0.045  # = 90,000
    assert abs(out["national_pension"] - expected_np) < 0.01
    _assert_total_equals_sum(out)


def test_legal_basis_sync_ltc_rate():
    """장기요양 12.96% 적용 확인."""
    salary = 5_000_000
    out = compute_fi(salary)
    expected_hi  = 5_000_000 * HI_RATE
    expected_ltc = expected_hi * LTC_RATE
    assert abs(out["long_term_care"] - expected_ltc) < 0.01
    _assert_total_equals_sum(out)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. [회귀 4] 경계값 3점 세트 (NP 상한/하한) + 일반값 + 극단값
# ═══════════════════════════════════════════════════════════════════════════════

# ── 하한 경계 3점 ──────────────────────────────────────────────────────────────

def test_np_boundary_below_min():
    """하한 미만(200,000원): NP는 하한 기준으로 계산, notices [NP하한, 산재] 순서."""
    out = compute_fi(200_000)
    assert out is not None
    expected_np = NP_MIN * NP_RATE  # 390,000 × 4.5% = 17,550
    assert abs(out["national_pension"] - expected_np) < 0.01
    assert len(out["notices"]) == 2
    assert "하한" in out["notices"][0]
    assert "산재보험" in out["notices"][1]
    _assert_total_equals_sum(out)

def test_np_boundary_at_min():
    """하한 정확히(390,000원): NP 클램프 미발동, notices [산재] 1개."""
    out = compute_fi(NP_MIN)
    assert out is not None
    expected_np = NP_MIN * NP_RATE  # 17,550
    assert abs(out["national_pension"] - expected_np) < 0.01
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]
    _assert_total_equals_sum(out)

def test_np_boundary_just_above_min():
    """하한 직후(390,001원): 급여 기준 계산, notices [산재] 1개."""
    salary = NP_MIN + 1
    out = compute_fi(salary)
    assert out is not None
    expected_np = salary * NP_RATE
    assert abs(out["national_pension"] - expected_np) < 0.01
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]
    _assert_total_equals_sum(out)

# ── 상한 경계 3점 ──────────────────────────────────────────────────────────────

def test_np_boundary_just_below_max():
    """상한 직전(6,169,999원): 급여 기준 계산, notices [산재] 1개."""
    salary = NP_MAX - 1
    out = compute_fi(salary)
    assert out is not None
    expected_np = salary * NP_RATE
    assert abs(out["national_pension"] - expected_np) < 0.01
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]
    _assert_total_equals_sum(out)

def test_np_boundary_at_max():
    """상한 정확히(6,170,000원): NP 클램프 미발동, notices [산재] 1개."""
    out = compute_fi(NP_MAX)
    assert out is not None
    expected_np = NP_MAX * NP_RATE  # 277,650
    assert abs(out["national_pension"] - expected_np) < 0.01
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]
    _assert_total_equals_sum(out)

def test_np_boundary_above_max():
    """상한 초과(10,000,000원): NP는 상한 기준, notices [NP상한, 산재] 순서."""
    salary = 10_000_000
    out = compute_fi(salary)
    assert out is not None
    expected_np = NP_MAX * NP_RATE  # 277,650 (상한 기준)
    assert abs(out["national_pension"] - expected_np) < 0.01, (
        f"NP 상한 미적용 의심: {out['national_pension']:.0f}원 (올바른 {expected_np:.0f}원)"
    )
    assert len(out["notices"]) == 2
    assert "상한" in out["notices"][0]
    assert "산재보험" in out["notices"][1]
    _assert_total_equals_sum(out)

# ── 진단에서 실제 오차가 드러난 극단값 ─────────────────────────────────────────

def test_extreme_below_min_large_error():
    """진단 케이스: 200,000원 → 이전 코드 9,000원, 올바른 17,550원 (8,550원 오차).

    경계 3점 테스트만으로는 이 오차를 발견할 수 없었음.
    """
    out = compute_fi(200_000)
    expected_np = NP_MIN * NP_RATE  # 17,550
    assert abs(out["national_pension"] - expected_np) < 0.01, (
        f"하한 미적용: {out['national_pension']:.0f}원 (올바른 17,550원) — 8,550원 오차"
    )
    _assert_total_equals_sum(out)

def test_extreme_above_max_large_error():
    """진단 케이스: 10,000,000원 → 이전 코드 450,000원, 올바른 277,650원 (172,350원 오차).

    경계 3점 테스트만으로는 이 오차를 발견할 수 없었음.
    """
    out = compute_fi(10_000_000)
    expected_np = NP_MAX * NP_RATE  # 277,650
    assert abs(out["national_pension"] - expected_np) < 0.01, (
        f"상한 미적용: {out['national_pension']:.0f}원 (올바른 277,650원) — 172,350원 오차"
    )
    _assert_total_equals_sum(out)

def test_normal_case_300_full_diff():
    """정상 케이스(300만원): 이전 코드 total=268,350원, 올바른 282,133원 (13,783원 차이 = 장기요양 누락분)."""
    out = compute_fi(3_000_000)
    # 이전 코드 결과 (장기요양 누락)
    wrong_total = 3_000_000 * (0.045 + 0.03545 + 0.009)  # 268,350
    assert abs(out["total"] - wrong_total) > 13_000, (
        f"장기요양 누락 의심: total={out['total']:.0f}원이 잘못된 값({wrong_total:.0f}원)과 너무 가까움"
    )
    _assert_total_equals_sum(out)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. [회귀 3] YAML ↔ Python 상수 동기화 확인 (요율 변경 시 자동 감지)
# ═══════════════════════════════════════════════════════════════════════════════

def test_yaml_sync_constants():
    """legal_basis.draft.yaml의 insurance_rates가 Python 상수와 일치하는지 검증.

    내년 요율 변경 시 YAML만 수정하면 이 테스트가 실패 → 상수도 함께 갱신 유도.
    실업급여 테스트와 동일한 YAML-상수 동기화 패턴.
    """
    from modules.registry_loader import load_registry
    reg = load_registry()
    fi_reg = reg.get("four-insurances") or {}
    ir = fi_reg.get("insurance_rates") or {}

    assert abs(float(ir.get("np_rate",  0))   - NP_RATE)  < 1e-6, f"np_rate 불일치: YAML={ir.get('np_rate')}, 상수={NP_RATE}"
    assert int(ir.get("np_min",  0)) == NP_MIN,  f"np_min 불일치: YAML={ir.get('np_min')}, 상수={NP_MIN}"
    assert int(ir.get("np_max",  0)) == NP_MAX,  f"np_max 불일치: YAML={ir.get('np_max')}, 상수={NP_MAX}"
    assert abs(float(ir.get("hi_rate",  0))   - HI_RATE)  < 1e-6, f"hi_rate 불일치: YAML={ir.get('hi_rate')}, 상수={HI_RATE}"
    assert abs(float(ir.get("ltc_rate", 0))   - LTC_RATE) < 1e-6, f"ltc_rate 불일치: YAML={ir.get('ltc_rate')}, 상수={LTC_RATE}"
    assert abs(float(ir.get("ei_rate",  0))   - EI_RATE)  < 1e-6, f"ei_rate 불일치: YAML={ir.get('ei_rate')}, 상수={EI_RATE}"


def test_yaml_driven_300():
    """YAML에서 로드한 요율로 300만원 계산 → 정부 기준 fixture와 비교.

    이 흐름: YAML → load_registry → compute_fi → 정부 기준.
    """
    from modules.registry_loader import load_registry
    reg = load_registry()
    ir  = reg.get("four-insurances", {}).get("insurance_rates", {})
    # YAML 요율로 직접 계산
    np_rate  = float(ir.get("np_rate",  NP_RATE))
    np_min   = int(ir.get("np_min",   NP_MIN))
    np_max   = int(ir.get("np_max",   NP_MAX))
    hi_rate  = float(ir.get("hi_rate",  HI_RATE))
    ltc_rate = float(ir.get("ltc_rate", LTC_RATE))
    ei_rate  = float(ir.get("ei_rate",  EI_RATE))

    salary = 3_000_000
    np_base = min(max(salary, np_min), np_max)
    np_val  = np_base * np_rate
    hi_val  = salary * hi_rate
    ltc_val = hi_val * ltc_rate
    ei_val  = salary * ei_rate
    total   = np_val + hi_val + ltc_val + ei_val

    # 정부 기준 fixture (2025년 기준)
    assert _round(np_val)  == 135_000
    assert _round(hi_val)  == 106_350
    assert _round(ltc_val) == 13_783
    assert _round(ei_val)  == 27_000
    assert abs(total - (np_val + hi_val + ltc_val + ei_val)) < 0.01


# ─── 기타 ──────────────────────────────────────────────────────────────────────

def test_notices_empty_for_normal():
    """정상 범위 급여에서 NP notice 없음 — 산재보험 notice는 항상 1개."""
    out = compute_fi(3_000_000)
    assert len(out["notices"]) == 1
    assert "산재보험" in out["notices"][0]

def test_notices_floor_clamp():
    """하한 미만 급여에서 하한 notice 포함."""
    out = compute_fi(200_000)
    assert any("하한" in n for n in out["notices"])

def test_notices_ceiling_clamp():
    """상한 초과 급여에서 상한 notice 포함."""
    out = compute_fi(10_000_000)
    assert any("상한" in n for n in out["notices"])

def test_formula_key_exists():
    """_formula 키 존재 및 비어 있지 않음."""
    out = compute_fi(3_000_000)
    assert "_formula" in out
    assert len(out["_formula"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 8. [Phase 3] FI-8 — _formula 5단계 순서 검증
# ═══════════════════════════════════════════════════════════════════════════════

def test_formula_stage_order():
    """_formula 5단계 순서: 국민연금 | 건강보험 | 장기요양 | 고용보험."""
    out = compute_fi(3_000_000)
    f = out["_formula"]

    # 4개 파이프 구분자 존재
    assert f.count(" | ") == 3, f"파이프 구분자 수 오류: {f.count(' | ')}"

    idx_np  = f.index("국민연금")
    idx_hi  = f.index("건강보험 ")
    idx_ltc = f.index("장기요양")
    idx_ei  = f.index("고용보험")

    assert idx_np < idx_hi < idx_ltc < idx_ei, (
        f"_formula 단계 순서 오류: NP={idx_np}, HI={idx_hi}, LTC={idx_ltc}, EI={idx_ei}"
    )


def test_formula_ltc_shows_health_insurance_amount():
    """FI-8 강화: 장기요양 단계에 '건강보험료 N원 × 12.96%' 형태 — 금액 명시."""
    out = compute_fi(3_000_000)
    f = out["_formula"]

    # 장기요양 단계 추출 (| 뒤 세 번째 세그먼트)
    segments = f.split(" | ")
    assert len(segments) == 4
    ltc_seg = segments[2]  # "장기요양 건강보험료 106,350원 × 12.96% = 13,783원"

    # 건강보험료 금액이 명시되는지 확인
    assert "건강보험료" in ltc_seg, f"'건강보험료' 없음: {ltc_seg!r}"
    assert "× 12.96%" in ltc_seg or "× 12.960%" in ltc_seg or "× 12.96%" in ltc_seg, (
        f"장기요양 비율 표시 없음: {ltc_seg!r}"
    )
    # 건강보험료 실제 금액(106,350)이 포함되어 있어야 함
    expected_hi_str = f"{round(3_000_000 * HI_RATE):,}"  # "106,350"
    assert expected_hi_str in ltc_seg, (
        f"건강보험료 금액({expected_hi_str}) 미포함: {ltc_seg!r}"
    )


def test_formula_clamp_cases():
    """NP 클램프 케이스에서도 _formula 5단계 순서 유지."""
    for salary in [200_000, 10_000_000]:
        out = compute_fi(salary)
        f = out["_formula"]
        assert "국민연금" in f and "건강보험" in f and "장기요양" in f and "고용보험" in f
        assert f.count(" | ") == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 9. [Phase 3] FI-9 — notices 우선순위 순서 검증 (동시 발생 케이스)
# ═══════════════════════════════════════════════════════════════════════════════

def test_notices_sangjae_always_present():
    """산재보험 notice는 모든 케이스에서 항상 존재."""
    for salary in [200_000, NP_MIN, 3_000_000, NP_MAX, 10_000_000]:
        out = compute_fi(salary)
        assert any("산재보험" in n for n in out["notices"]), (
            f"salary={salary:,}: 산재보험 notice 없음"
        )


def test_notices_order_np_ceiling_with_sangjae():
    """FI-9: 상한 초과 케이스 — notices[0]=국민연금 상한, notices[1]=산재보험."""
    out = compute_fi(10_000_000)
    assert len(out["notices"]) == 2
    assert "상한" in out["notices"][0], f"notices[0] 국민연금 상한 아님: {out['notices'][0]!r}"
    assert "산재보험" in out["notices"][1], f"notices[1] 산재보험 아님: {out['notices'][1]!r}"


def test_notices_order_np_floor_with_sangjae():
    """FI-9: 하한 미만 케이스 — notices[0]=국민연금 하한, notices[1]=산재보험."""
    out = compute_fi(200_000)
    assert len(out["notices"]) == 2
    assert "하한" in out["notices"][0], f"notices[0] 국민연금 하한 아님: {out['notices'][0]!r}"
    assert "산재보험" in out["notices"][1], f"notices[1] 산재보험 아님: {out['notices'][1]!r}"


def test_notices_sangjae_is_last():
    """산재보험 notice는 항상 마지막 위치."""
    for salary in [200_000, NP_MIN, 3_000_000, NP_MAX, 10_000_000]:
        out = compute_fi(salary)
        notices = out["notices"]
        assert len(notices) >= 1
        assert "산재보험" in notices[-1], (
            f"salary={salary:,}: 산재보험이 마지막 아님 — {notices[-1]!r}"
        )


@pytest.mark.parametrize("salary,expected_len", [
    (200_000,    2),   # 하한 미만: NP하한 + 산재
    (NP_MIN,     1),   # 하한 정확히: 산재만
    (3_000_000,  1),   # 정상: 산재만
    (NP_MAX,     1),   # 상한 정확히: 산재만
    (10_000_000, 2),   # 상한 초과: NP상한 + 산재
])
def test_notices_count_parametrized(salary, expected_len):
    """케이스별 notices 개수 검증."""
    out = compute_fi(salary)
    assert len(out["notices"]) == expected_len, (
        f"salary={salary:,}: notices 개수 오류 — 기대={expected_len}, 실제={len(out['notices'])}"
    )
