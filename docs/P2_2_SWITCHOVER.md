# CalcMate Phase2 — P2-2 Registry Soft Switchover 완료

기준일: 2026-08-08  
실행: P2-2-A Shadow Mode → P2-2-B Soft Switchover

---

## 1. 목표

Registry v3 (`docs/registry/*.yaml`)를 사이트 생성의 **Primary Source**로 전환.  
레거시 상수 (`_LABELS` / `_CALC_DESCS` / `_SLUG_ORDER`)는 삭제하지 않고 Fallback으로 유지.

---

## 2. P2-2-A 결과 (전제 조건)

| 비교 항목 | diff |
|---|---|
| `display_order` vs `_SLUG_ORDER` | 0건 |
| `card_desc` vs `_CALC_DESCS` | 0건 |
| `field_labels` vs `_LABELS` | 0건 (26개 필드) |

모든 비교에서 diff 0건 → P2-2-B 진행 승인.

---

## 3. 변경 파일

### 3-1. `modules/site_generator.py`

#### `generate_index()`
- **Before**: `_SLUG_ORDER` 순서로 카드 렌더, `_CALC_DESCS`에서 설명 문구
- **After**: Registry v3 `display_order` 기준 정렬(int 오름차순), `card_desc` 우선 사용
- **Fallback**: registry v3 없을 시 `_SLUG_ORDER` 순서 + `_CALC_DESCS` fallback 자동 적용

#### `generate_sitemap()`
- **Before**: `_SLUG_ORDER` 순서로 URL 목록 생성
- **After**: Registry v3 `display_order` 기준 정렬
- **Fallback**: registry v3 없을 시 `_SLUG_ORDER` fallback

### 3-2. `modules/app_generator.py`

#### `_effective_labels(calc)` (신규 헬퍼)
```python
def _effective_labels(calc: dict) -> dict:
    # registry v3 field_labels(primary) + DB labels(override) 병합
    # _LABELS는 _label() 내부에서 최종 fallback (코드 미삭제)
```

- 우선순위: DB labels (최우선) > Registry v3 field_labels > `_LABELS` (최종 fallback)

#### `_sm_config(calc, cfg)`
- `labels = _pj(calc.get("labels"), {})` → `labels = _effective_labels(calc)`

#### `generate_html(calc, cfg)`
- `labels = _pj(calc.get("labels"), {})` → `labels = _effective_labels(calc)`

---

## 4. 검증 결과

| 검증 항목 | 결과 |
|---|---|
| 빌드 성공 (에러 없음) | ✓ |
| HTML diff (이전/이후) | **0건** — byte 단위 완전 일치 |

---

## 5. 보존된 레거시 상수

아래 상수들은 삭제되지 않고 코드에 남아있음(rollback용):

| 상수 | 위치 | 역할 |
|---|---|---|
| `_LABELS` | `app_generator.py` | `_label()` 최종 fallback |
| `_CALC_DESCS` | `site_generator.py` | `generate_index()` card_desc fallback |
| `_SLUG_ORDER` | `app_generator.py` | sitemap/index 순서 fallback |

---

## 6. 다음 단계

| 단계 | 내용 | 조건 |
|---|---|---|
| P2-2-C | 레거시 상수 제거 (`_LABELS` / `_CALC_DESCS` / `_SLUG_ORDER`) | 별도 승인 필요 |
| P2-3+ | `calculator_seed.py` SSOT 통합 | 별도 계획 수립 |
