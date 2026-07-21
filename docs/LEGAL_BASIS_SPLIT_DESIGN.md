# LEGAL_BASIS_SPLIT_DESIGN.md
> 작성: 2026-07-22 (Phase B)
> 목적: `legal_basis.draft.yaml` 3분리 구조 설계안. 실제 마이그레이션은 Phase G에서 수행.

---

## 현재 상태 분석

### 파일 구조 (2026-07-22 기준)

```
docs/
  legal_basis.draft.yaml        ← 단일 파일 (7개 계산기 + schema_version 2)
  legal_master/
    employment.yaml             ← 고용/실업급여 법령 엔티티 (법조문 단위)
    insurance.yaml              ← 보험 법령 엔티티
    labor.yaml                  ← 근로 법령 엔티티
    tax.yaml                    ← 세금 법령 엔티티
```

### `legal_basis.draft.yaml` 내 검증 상태

| 계산기 slug | 검증 상태 | 근거 | confidence |
|---|---|---|---|
| weekly-holiday-allowance | ✅ 검증 완료 | law.go.kr + Verified (2026-07-19) | high |
| severance-pay | ✅ 검증 완료 | law.go.kr + Verified (2026-07-19). SP-2 법령 오류 수정 | high |
| unemployment-benefit | ✅ 검증 완료 | law.go.kr + Verified (2026-07-19). UB-2 300일 오류 수정 | high |
| four-insurances | ✅ 검증 완료 | 요율 외부화 + YAML↔상수 동기화 테스트 + Verified (2026-07-19) | high |
| annual-leave-allowance | ✅ 검증 완료 | 법령 법조문 직접 확인 + Verified (2026-07-19) | high |
| 육아휴직_급여_계산기 | ✅ 검증 완료 | nts.go.kr 제도 확인 + Verified (2026-07-19) | high |
| 연말정산_환급액_계산기 | ✅ 검증 완료 | 소득세법 직접 전개 3케이스 오차 0원 + Verified (2026-07-21) | high |

**결론**: 7개 계산기 전체 검증 완료 상태. 단, `evergreen` 여부와 갱신 주기에 따라 관리 분리 필요.

---

## 3분리 설계안

### 분리 기준

| 파일 | 내용 | 갱신 주기 | 담당 |
|---|---|---|---|
| `legal_basis.master.yaml` | 검증 완료 + evergreen(불변) 항목 | 법령 개정 시만 | 개발자 수동 |
| `legal_basis.draft.yaml` | 검증 완료 + 갱신 필요 항목 + 신규 조사 중 | 연간 or 수시 | AI 보조 |
| `docs/legal_master/archive/` | 단종된 계산기 또는 폐기된 법령 참조 | 이동 후 Read-only | N/A |

### 각 파일 분류 기준

#### `legal_basis.master.yaml`에 포함될 항목
- `evergreen: true` 이고 `update_cycle: null` 인 계산기
- 법령 자체가 안정적이고 자주 개정되지 않는 항목
- 예: **주휴수당** (근로기준법 제55조 — 수십 년간 안정)

#### `legal_basis.draft.yaml`에 유지될 항목
- `evergreen: false` 또는 `update_cycle` 이 있는 항목
- 연간 요율/금액이 변동하는 항목
- 예:
  - **4대보험** (`update_cycle: yearly` — 요율 매년 고시)
  - **연말정산** (`update_cycle: yearly` — 세율표/공제한도 매년 변동)
  - **실업급여** (상한/하한 매년 고시)
  - **육아휴직** (제도 개정 빈번)

#### 현재 7개 계산기 분류

| 계산기 | 제안 위치 | 이유 |
|---|---|---|
| weekly-holiday-allowance | master | evergreen: true — 법령 안정 |
| severance-pay | master | evergreen: true — 법령 안정. 요율 없음 |
| annual-leave-allowance | master | evergreen: true — 법령 안정 |
| unemployment-benefit | draft | update_cycle: yearly — 상한/하한 매년 고시 |
| four-insurances | draft | update_cycle: yearly — 요율 매년 고시 |
| 육아휴직_급여_계산기 | draft | 제도 개정 빈번 (6+6 특례 2024년 신설) |
| 연말정산_환급액_계산기 | draft | update_cycle: yearly — 세율표/공제한도 매년 |

---

## 마이그레이션 실행 순서 (Phase G)

> **Phase B에서는 설계까지만. 실제 파일 분리·코드 변경은 Phase G에서 수행.**

### G-1. 준비
1. `registry_loader.py`가 `master.yaml` + `draft.yaml`을 merge 로드하도록 수정
2. merge 순서: `master` 먼저 → `draft`가 override (draft가 더 최신)
3. 기존 `legal_basis.draft.yaml` 로드 경로를 유지하면서 `master.yaml`을 추가 소스로 추가

### G-2. 분리 실행
1. `legal_basis.draft.yaml`에서 master 항목 추출 → `legal_basis.master.yaml` 작성
2. `legal_basis.draft.yaml`에서 master 항목 제거
3. 전체 회귀 테스트 실행 (240 passed 유지 확인)

### G-3. archive 구조
```
docs/legal_master/archive/
  YYYYMMDD_<slug>_deprecated.yaml   ← 단종 계산기 법령 참조
  YYYYMMDD_<law>_superseded.yaml    ← 폐지된 조항 참조 (예: 근로기준법 제34조)
```

---

## 법령 변경 감지(RMS) 연계

Phase G의 legal_basis 분리와 Phase G의 RMS는 동시 설계:
- RMS는 `draft.yaml`의 `last_verified` + `update_cycle`을 기준으로 갱신 알림
- `master.yaml` 항목은 RMS 체크 대상에서 제외 (법령 개정 공식 알림 대기)
- 갱신 필요 항목은 RMS → draft.yaml 업데이트 → 해당 계산기 workspace 재생성

---

## 현재 상태에서 즉시 적용 가능한 개선

Phase G 전에도 즉시 가능한 개선 (코드 변경 없음):
1. `legal_basis.draft.yaml`의 각 항목에 `phase_b_verified: true` 필드 추가 (완료 표시)
2. `update_cycle: yearly` 항목에 `next_review: 2027-01-01` 명시 (다음 갱신 기준일)
3. `confidence: high` 재확인 (7종 모두 high — 이미 완료)
