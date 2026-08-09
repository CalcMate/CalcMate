# Tier2-A 표준경로 (CalcMate Phase3 기준점)

**기준일**: 2026-08-09  
**태그**: v2.2.0  
**커밋**: `docs(phase3): establish Tier2-A standard path`  
**상태**: Production 검증 완료

---

## 1. 정의

**Tier2-A**는 산술/공식(formula) 기반 계산기의 App Factory 생성 경로다.

formula 또는 formula dict를 이용해 계산 로직을 표현할 수 있으며, `_compute_js()`에 계산기별 특수 분기 코드를 추가하지 않고도 정적 사이트 JS를 자동 생성할 수 있는 계산기 유형이다.

> **Tier2-A는 검증된 표준 생성 경로이며, 모든 신규 계산기가 자동으로 Tier2-A에 해당한다고 가정하지 않는다.**

---

## 2. 적용 범위

다음 조건을 모두 만족하는 계산기가 Tier2-A에 해당한다.

| 조건 | 설명 |
|---|---|
| 공식 기반 | 사칙연산·비율·고정계수 기반의 수식으로 표현 가능 |
| 분기 최소 | 복잡한 조건분기 없음 (단순 양수 입력 가드 정도는 허용) |
| 날짜 계산 아님 | 날짜 덧셈·빼기·기간 계산이 핵심 로직이 아님 |
| 구간 요율 아님 | 누진세·구간별 요율표 계산이 핵심 로직이 아님 |
| 독립 검증 가능 | 수식으로 계산 결과를 독립 검증할 수 있음 |
| formula dict 지원 | 단일 출력 또는 formula dict를 통한 복수 출력 가능 |

Tier2-A에 해당하지 않는 예:
- **Tier2-B**: 날짜 덧셈·군 복무기간 계산 등 JS `Date` 객체가 필요한 계산기
- **Tier1**: 퇴직금·실업급여처럼 구간별 요율표·복잡한 법령 분기가 있는 계산기

---

## 3. 공식 생성 경로

```
대시보드 App Factory
        ↓
계산기 이름 / 공식 / 입출력 스키마 입력
        ↓
formula 또는 formula dict 기반 계산기 생성
        ↓
DB 저장 (calculators 테이블)
        ↓
Registry v3 HOLD 등록 (docs/registry/*_af.yaml)
        ↓
자동 QA (계산값 + HTML 요소 + 회귀 테스트)
        ↓
법률/세율/계산 기준 등 검토 필요 항목 표시
        ↓
운영자 검토 및 PASS
        ↓
HOLD → READY 승격 (promote_to_ready())
        ↓
정적 사이트 빌드 (scripts/_rebuild_site.py)
        ↓
index 카드 + sitemap 반영
        ↓
Git commit / push
        ↓
GitHub Actions (deploy.yml)
        ↓
calcmate.kr Production 반영
```

### 현재 자동화 범위

Tier2-A 계산기의 Production 생성 경로가 검증되었으며, 향후 Phase3-3에서 대시보드 중심 운영 흐름으로 확장한다.

현재 구현에서 이 전체 흐름 중 완전 자동화된 구간:

| 구간 | 자동화 여부 |
|---|---|
| DB 저장 | ✅ App Factory `save_app()` |
| Registry v3 HOLD 등록 | ✅ `_write_registry_v3()` |
| 정적 사이트 빌드 | ✅ `_rebuild_site.py` |
| GitHub Actions 배포 | ✅ `deploy.yml` (push 트리거) |
| 법률 검토 / 운영자 PASS | ❌ 수동 (현재는 `promote_to_ready()` 직접 호출) |
| 대시보드에서 Git push까지 원클릭 | ❌ Phase3-3에서 설계 예정 |

---

## 4. 검증된 계산기

Phase3에서 Tier2-A 경로로 생성·배포·검증된 계산기:

### 4-1. freelancer-tax-3p3 (Phase3-1)

| 항목 | 내용 |
|---|---|
| 슬러그 | `freelancer-tax-3p3` |
| 설명 | 프리랜서 3.3% 원천징수 계산기 |
| 출력 수 | 2개 (`withholding_tax`, `net_income`) |
| 공식 유형 | 단일 formula (slug별 하드코딩 분기 경로) |
| 법적 근거 | 소득세법 제127조 (원천징수), 지방세법 제176조 (지방소득세) |
| 커밋 | `419cc84` (App Factory 연결), `7189e7c` (Phase3-1) |

### 4-2. jeonse-vs-monthly (Phase3-2)

| 항목 | 내용 |
|---|---|
| 슬러그 | `jeonse-vs-monthly` |
| 설명 | 전세 vs 월세 비교 계산기 |
| 출력 수 | 3개 (`jeonse_opp_cost`, `wolse_to_jeonse_equiv`, `monthly_savings`) |
| 공식 유형 | formula dict (Tier2-A 표준경로 최초 검증) |
| 법적 근거 | 주택임대차보호법 제7조의2, 동법 시행령 제9조 |
| 커밋 | `27dad7a` (Phase3-2), `8c320fe` (다중 출력 버그 수정) |

---

## 5. QA 필수 항목

Phase3-2 버그 사례를 통해 확정된 Tier2-A QA 3단계:

> **계산 로직 생성 성공은 Production 정상의 증거가 아니다.**

### 5-1. 계산값 검증

- formula dict의 각 출력 수식을 독립 계산하여 기댓값과 비교
- 경계값 테스트: rate=0, 음수, 동일 보증금 등
- 단위 테스트: `tests/test_<slug>.py`

### 5-2. HTML 출력 요소 검증

- `_site/<slug>/script.js`: `out["<key>"]` 모든 출력 key 존재 여부
- `_site/<slug>/index.html`: `id="out_<key>"` 모든 출력 요소 존재 여부
- `sm-result-extra` 컨테이너: 복수 출력 시 secondary 요소 포함 여부

### 5-3. Production URL 검증

- HTTP 200 응답 확인
- 실제 HTML에서 `id="out_<key>"` 요소 확인
- 메인 페이지 계산기 카드 노출 확인
- sitemap.xml URL 포함 확인

---

## 6. Production 검증 결과

**검증일**: 2026-08-09  
**기준 커밋**: `8c320fe`

| 항목 | 결과 |
|---|---|
| 총 계산기 수 (calcmate.kr) | 9개 |
| freelancer-tax-3p3 HTTP 응답 | 200 OK |
| jeonse-vs-monthly HTTP 응답 | 200 OK |
| 메인 카드 노출 (두 계산기) | ✅ |
| sitemap.xml URL 포함 | ✅ |
| jeonse-vs-monthly 출력 요소 | `out_jeonse_opp_cost` / `out_wolse_to_jeonse_equiv` / `out_monthly_savings` |
| freelancer-tax-3p3 출력 요소 | `out_withholding_tax` / `out_net_income` |
| 전체 테스트 (regression) | 318 PASS |
| Git push | ✅ origin/master 반영 |
| GitHub Actions 배포 | ✅ 성공 |

---

## 7. 발견·해결된 버그

### Bug 1 — formula dict 복수 출력 누락

**증상**: `jeonse-vs-monthly`의 `computeResult()`가 3개 출력 중 `jeonse_opp_cost` 하나만 반환.

**근본 원인**: `modules/app_generator.py` `_compute_js()` validation branch에서 `next(iter(fmap))`로 첫 번째 출력 key만 처리.

```python
# 수정 전 (Bug)
out_key = next(iter(fmap))
out_expr = _to_js(next(iter(fmap.values())))
body = ... + f'  out["{out_key}"] = ({out_expr});\n'  # 첫 번째만

# 수정 후
out_lines = "".join(
    f'  out["{k}"] = ({_to_js(expr)});\n' for k, expr in fmap.items()
)
body = ... + out_lines  # 모든 key
```

**영향**: validation이 없는 계산기(`else:` branch)는 처음부터 정상이었음. validation이 있는 formula dict 계산기만 영향.

**수정 커밋**: `8c320fe`

### Bug 2 — HTML 출력 요소 누락

**증상**: `computeResult()`가 3개를 반환해도 HTML에 `id="out_wolse_to_jeonse_equiv"` 등이 없어 화면에 값이 표시되지 않음.

**근본 원인**:
- `calculator_v2.html` 템플릿이 단일 출력(`id="out_{{PRIMARY_OUT}}"`)만 가짐
- `generate_html()`이 primary 출력만 HTML에 삽입
- `components.js` `renderResult()`가 primary에만 `countUp` 적용

**수정 내용**:
- `calculator_v2.html`: `{{EXTRA_OUTPUT_ROWS}}` 플레이스홀더 추가
- `generate_html()`: 복수 출력 시 `sm-result-extra` 컨테이너 + `id="out_<key>"` 요소 생성
- `design_system.css`: `.sm-result-extra`, `.sm-result-extra-row` 클래스 추가
- `components.js`: `CFG.outputs` 전체를 `countUp` 처리

**수정 커밋**: `8c320fe`

---

## 8. Tier2-A의 한계

Tier2-A 경로로 처리할 수 없는 유형:

| 한계 | 이유 | 대안 |
|---|---|---|
| 날짜 덧셈/기간 계산 | JS `Date` 없이 formula dict로 표현 불가 | Tier2-B (설계 중) |
| 구간별 누진세 | formula dict의 산술식으로 단순 표현 불가 | Tier1 하드코딩 또는 별도 설계 |
| 복잡한 조건 분기 | `_compute_js()`에 계산기별 분기 추가 필요 | Tier1 또는 Tier2-C (미정의) |
| 외부 데이터 테이블 참조 | formula dict는 상수만 참조 가능 | 별도 데이터 주입 구조 필요 |

---

## 9. Tier2-B와의 차이

| 항목 | Tier2-A | Tier2-B |
|---|---|---|
| 계산 핵심 | 산술 공식 | 날짜 연산 |
| formula dict | ✅ 사용 | ❌ 사용 불가 |
| `_compute_js()` 자동 생성 | ✅ | ❌ (JS Date 필요) |
| HTML 자동 생성 | ✅ | 별도 설계 필요 |
| 검증 사례 | `freelancer-tax-3p3`, `jeonse-vs-monthly` | 없음 (Phase3 이후) |
| 설계 문서 | 이 문서 | `docs/TIER2_B_DESIGN.md` |

Tier2-B 상세 설계는 `docs/TIER2_B_DESIGN.md` 참조.

---

## 10. Phase3-3에서 확장할 영역

Phase3-3의 목표:

> 운영자가 계산기 이름/기본 정보만 입력하면 App Factory가 나머지 데이터를 자동 생성하고, 시스템이 검토가 필요한 항목만 표시하며, 운영자가 PASS한 경우에만 READY → Build → Deploy 단계로 진행할 수 있는 구조를 설계한다.

Phase3-3에서 설계할 영역 (구현은 별도 승인 후):

| 영역 | 현재 상태 | Phase3-3 설계 목표 |
|---|---|---|
| 대시보드 입력 흐름 | 수동 App Factory 호출 | 이름만 입력 → 나머지 자동 제안 |
| 법률 검토 표시 | 없음 | 검토 필요 항목 자동 하이라이트 |
| HOLD → READY 승격 | CLI 호출 (`promote_to_ready()`) | 대시보드 버튼 1회 클릭 |
| Build → Deploy | CLI `_rebuild_site.py` + `git push` | 대시보드에서 원클릭 트리거 |
| QA 결과 표시 | 터미널 출력 | 대시보드 내 QA 결과 패널 |

Phase3-3에서는 먼저 설계만 수행하고 구현하지 않는다.

---

*작성일: 2026-08-09 | 기준 커밋: `8c320fe` | 태그: v2.2.0*
