# UI_INDEPENDENCE.md — UI 독립성 원칙 (Phase B)
> 작성: 2026-07-22
> 목적: Phase C(UI/UX 개선)에서 카드/FAQ/CTA/레이아웃 변경이 Phase B 테스트를 깨뜨리지 않도록 경계를 명확히 한다.

---

## 원칙 요약

**계산 로직 테스트는 HTML/CSS/JS UI 변경과 독립적으로 통과해야 한다.**

---

## 경계 정의

### 테스트가 검증하는 것 (UI 무관)
- `computeResult(inputs)` 반환값: `_detail`, `_formula`, `notices`, 각 금액 키
- Python mirror 함수 계산 결과
- 법령 상수 ↔ YAML 동기화 (요율, 구간, 한도)
- 불변식: 단조성, 음수 불가, 대수 항등식

### 테스트가 검증하지 않는 것 (UI 담당)
- HTML 구조 (result-card, detail-rows, faq-accordion 등)
- CSS 클래스명, 레이아웃, 색상
- CTA 버튼, 공유 버튼, 관련 계산기 카드 렌더링
- 광고 슬롯 위치
- 애니메이션, 반응형 breakpoint

---

## 테스트 파일 분류

| 파일 | 종류 | UI 영향 |
|---|---|---|
| `tests/test_*_compute.py` | **계산 테스트** | UI 변경 시 절대 실패하면 안 됨 |
| `tests/test_invariants.py` | **불변식 테스트** | UI 변경 시 절대 실패하면 안 됨 |
| `tests/snapshot_calculators.py` | **스냅샷 테스트** | UI 변경 시 해시가 바뀜 — 의도적 업데이트 필요 |

### 스냅샷 테스트 운영 원칙
- `tests/snapshot_calculators.py`는 생성된 HTML/JS/CSS 파일의 해시를 검증한다.
- Phase C(UI 개선)에서 템플릿 변경 시: **스냅샷만 갱신**, 계산 테스트는 유지.
- 갱신 방법: `py scripts/regen_and_snapshot.py` (workspace 재생성 + 해시 갱신)
- 갱신 후 반드시 계산 테스트 (test_*_compute.py, test_invariants.py)를 별도 실행하여 통과 확인.

---

## Phase C 작업 지침

Phase C에서 다음을 변경할 때 계산 테스트가 깨지면 **안 된다**:

| Phase C 작업 | 영향받는 테스트 | 허용 여부 |
|---|---|---|
| CTA 버튼 추가 | snapshot_calculators.py | ✅ 스냅샷 갱신으로 해결 |
| FAQ 아코디언 UI 교체 | snapshot_calculators.py | ✅ 스냅샷 갱신으로 해결 |
| 관련 계산기 카드 디자인 변경 | snapshot_calculators.py | ✅ 스냅샷 갱신으로 해결 |
| `_formula` 표시 형식 변경 | **test_*_compute.py** | ⚠️ 변경 전 사용자 승인 필요 |
| `notices` 문구 변경 | **test_*_compute.py** | ⚠️ 변경 전 사용자 승인 필요 |
| `computeResult` 반환 키 추가 | **test_*_compute.py** | ✅ 기존 키 유지 시 통과 |
| `computeResult` 반환 키 제거 | **test_*_compute.py** | ❌ 테스트 실패 — 법령 검토 필요 |
| 계산 공식 수정 | **test_*_compute.py + test_invariants.py** | ❌ 반드시 Verified 게이트 통과 |

---

## app_generator.py 영역 분리

```
app_generator.py
  ├── _compute_js(calc)          ← 계산 엔진 영역 (변경 → 계산 테스트 실행 필수)
  │    ├── _js_open()            ← 공통 헬퍼 (UI와 무관)
  │    ├── _js_read()
  │    ├── _js_init_out()
  │    └── _js_close()
  ├── generate_html(calc)        ← UI 영역 (변경 → 스냅샷 갱신)
  ├── generate_css(calc)         ← UI 영역 (변경 → 스냅샷 갱신)
  ├── render_article(calc)       ← 콘텐츠 영역 (변경 → SP-8 감사 필요)
  └── render_faq(calc)           ← 콘텐츠 영역 (변경 → SP-8 감사 필요)
```

---

## Phase C 시작 전 체크리스트

- [ ] `py -m pytest tests/test_*_compute.py tests/test_invariants.py -q` → ALL PASS 확인
- [ ] 위 테스트가 Phase C 작업 후에도 그대로 통과하는지 확인
- [ ] 스냅샷 변경이 있을 경우: `py scripts/regen_and_snapshot.py` 후 계산 테스트 재확인
- [ ] `_formula` / `notices` 문구 변경 계획이 있으면 사용자 승인 선행

---

## 배경 — 왜 이 원칙이 필요한가

Phase A~B에서 계산 로직과 UI 템플릿이 `app_generator.py` 한 파일에 혼재해 있다. Phase C에서 UI를 대규모로 개선할 때, "계산은 그대로인데 UI가 바뀌었다"를 테스트로 분리 보증하지 않으면:

- 스냅샷 해시가 바뀐다 → 실제 계산 결과 변경과 UI 변경을 구분할 수 없게 됨
- 의도치 않은 계산 로직 변경이 UI 변경에 묻혀 Verified 기준을 우회하게 됨

테스트를 UI 독립 영역과 스냅샷 영역으로 명확히 분리하면, Phase C 이후에도 "계산 240 PASS"가 보증으로 기능한다.
