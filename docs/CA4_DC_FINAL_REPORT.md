# CA-4-D / CA-4-C 최종 보고서

**날짜**: 2026-08-11  
**작업 범위**: Git 정리 (CA-4-D) + ast.Num 기술부채 제거 (CA-4-C)  
**코드 수정**: 1건 (modules/formula_engine.py -2줄)  
**최종 판정**: **PASS**

---

## 1. CA-4-D 작업 결과

### 커밋 요약

| # | 커밋 해시 | 메시지 | 파일 수 | 변경 규모 |
|---|----------|--------|--------|---------|
| 1 | `79883a1` | feat(ca3): implement Contract Builder Formula lifecycle and AI suggestion engine | 4 files | +1,234줄 |
| 2 | `9bc460b` | feat(ca3-4): connect AI Formula suggestion button to Dashboard Mode B | 2 files | +725줄 |
| 3 | `8f4c89d` | docs(ca2-ca4): add investigation reports, update registry metadata and operational data | 42 files | +9,686줄 |
| 4 | `85ed892` | fix(ca4-c): remove ast.Num dead code for Python 3.14 compatibility | 1 file | -2줄 |

---

## 2. 커밋한 파일 목록

### Commit 1 — CA-3 Core Backend
- `modules/app_factory.py` (+395줄: suggest_formula, check_hold_rules, build_contract 확장, Contract Instance 함수)
- `tests/test_formula_contract.py` (+426줄: 44개 테스트)
- `tests/test_review_center.py` (+32줄)
- `tests/test_suggest_formula.py` (신규: 18개 테스트)

### Commit 2 — CA-3-4 Dashboard
- `dashboard.py` (+188줄: AI Formula 버튼, badge fallback, ai_suggested 감지)
- `tests/test_e2e_ca35.py` (신규: 17개 E2E 테스트)

### Commit 3 — Docs + Registry + Operational Data
**문서 (19개 신규)**:
- `docs/CA1A_CONTRACT_SCHEMA_DESIGN.md` through `docs/CA4_PRE_INVESTIGATION_REPORT.md`

**Registry (6개 수정)**:
- `docs/registry/employment.yaml`, `insurance.yaml`, `labor.yaml`, `tax.yaml` — input_labels/output_labels 메타데이터 추가
- `docs/registry/labor_af.yaml`, `realty_af.yaml` — App Factory _af 엔트리

**Contract Schema 인프라 (신규)**:
- `docs/contract_schema/instances/.gitkeep`
- `docs/contract_schema/registry.yaml`

**파이프라인 로그 (11개 수정)**:
- `logs/content_pipeline/pipeline_p_*.json` — 파이프라인 실행 로그

**스냅샷**:
- `tests/snapshots/competitive_analysis_snapshot.json`

### Commit 4 — CA-4-C
- `modules/formula_engine.py` (-2줄: ast.Num dead code 제거)

---

## 3. 커밋하지 않은 파일 목록

| 파일 | Category | 처리 |
|------|---------|------|
| `_secret_replace2.txt` | **C** — 민감 파일 | 미커밋 보호 유지 |
| `test_output.txt` | C — 임시 파일 | 미커밋 유지 |
| `test_upload.txt` | C — 임시 파일 | 미커밋 유지 |
| `docs/_backup_ca1b/` | **D** — 보류 | 미커밋 유지 |
| `logs/content_pipeline/pipeline_p_*.json` | B — 재갱신 | Regression 실행으로 재갱신됨 (정상) |
| `tests/snapshots/competitive_analysis_snapshot.json` | B — 재갱신 | 테스트 실행으로 재갱신됨 (정상) |

**참고**: pipeline_p_*.json 및 competitive_analysis_snapshot.json은 Regression 실행 후 자동 갱신됨. 다음 작업 사이클에서 재커밋 가능.

---

## 4. Category C 보호 확인

커밋 전 매번 실행한 보호 검사:
```
git diff --cached --name-only | grep -i "secret\|test_output\|test_upload"
→ (결과 없음)
```

`_secret_replace2.txt`, `test_output.txt`, `test_upload.txt` 모두 스테이징에 포함되지 않음 확인.

---

## 5. `_secret_replace2.txt` 보호 확인

- git status: `?? _secret_replace2.txt` (untracked 유지)
- 모든 4개 커밋에 미포함
- 내용 변경 없음

---

## 6. `docs/_backup_ca1b/` 보호 확인

- git status: `?? docs/_backup_ca1b/` (untracked 유지)
- 내용 수정 없음
- 삭제 없음
- 이동 없음
- Category D 처리 — 현상 유지

---

## 7. CA-4-C 수정 위치

**파일**: `modules/formula_engine.py`  
**위치**: `_eval()` 함수 내 (line 56-57, 구 번호 기준)

```python
# 삭제된 코드 (2줄)
    if isinstance(node, ast.Num):  # py<3.8 호환
        return node.n
```

**수정 전** (line 52-58):
```python
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise FormulaError(f"허용되지 않은 상수: {node.value!r}")
    if isinstance(node, ast.Num):  # py<3.8 호환  ← 삭제
        return node.n                               ← 삭제
    if isinstance(node, ast.BinOp):
```

**수정 후** (line 52-56):
```python
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise FormulaError(f"허용되지 않은 상수: {node.value!r}")
    if isinstance(node, ast.BinOp):
```

---

## 8. ast.Num 제거 결과

| 항목 | 내용 |
|------|------|
| 제거 대상 | `ast.Num` dead code (Python 3.8+ 미도달) |
| 제거 줄 수 | **2줄** |
| 동작 변화 | 없음 (ast.Constant 분기가 모든 숫자 상수 처리) |
| Python 3.14 영향 | 이전: AttributeError 위험 / 이후: 완전 호환 |

---

## 9. DeprecationWarning 결과

| | Before | After |
|--|--------|-------|
| **ast.Num DeprecationWarning** | **494개** | **0개** |
| 기타 Warning | 0 | 0 |

**검증**: `-W error::DeprecationWarning` 플래그로 formula 테스트 84개 실행 → **84/84 PASS**

---

## 10. Regression Before / After

| | Before (CA-3-F 완료 시점) | After (CA-4-D/C 완료) |
|--|--------------------------|----------------------|
| **PASS** | 554 | **554** |
| **FAIL** | 1 | **1** |
| **Warnings** | 494 | **0** |

---

## 11. 신규 FAIL 여부

**신규 FAIL: 0건**

---

## 12. 기존 WordPress known FAIL 상태

```
FAILED tests/production_validation_test.py::test_full_pipeline_execution
ERROR: HTTPConnectionPool(host='salarymate.test', port=80): Max retries exceeded
(Caused by NewConnectionError: WinError 10061 — 연결이 거부되었습니다)
```

CA-4-D/C 작업 전과 동일한 실패 내용. 이번 작업과 무관.

---

## 13. Registry 변경 여부

CA-4-D Commit 3에서 다음 Registry 변경을 커밋함:
- `docs/registry/employment.yaml`, `insurance.yaml`, `labor.yaml`, `tax.yaml` — input_labels/output_labels 메타데이터 **추가** (기능 변경 없음)
- `docs/registry/labor_af.yaml`, `realty_af.yaml` — App Factory 생성 계산기 엔트리 **추가**

기존 9개 계산기의 formula, input_schema, output_schema 변경 없음.

---

## 14. Contract Instance 변경 여부

`docs/contract_schema/instances/` — **변경 없음**  
(`.gitkeep` 파일만 존재. 실제 인스턴스 없음.)

`docs/contract_schema/registry.yaml` — `instances: {}` (빈 상태 유지)

---

## 15. Blog/WordPress 변경 여부

**변경 없음.**

CA-4-D/C 작업에서 Blog 생성, WordPress 게시, 콘텐츠 파이프라인 관련 코드 변경 없음.

---

## 16. 최종 판정

**CA-4-D: PASS**  
**CA-4-C: PASS**

| 검증 항목 | 결과 |
|---------|------|
| _secret_replace2.txt 보호 | ✅ 미커밋 |
| docs/_backup_ca1b/ 보호 | ✅ 미수정 |
| Category C 파일 미포함 | ✅ 전체 커밋에서 확인 |
| CA-3 구현 커밋 완료 | ✅ 4커밋 |
| ast.Num 제거 | ✅ 2줄 삭제 |
| DeprecationWarning | ✅ 494개 → 0개 |
| Regression 기준선 유지 | ✅ 554 PASS / 1 known FAIL |
| 신규 FAIL | ✅ 0건 |
| Registry 기능 변경 없음 | ✅ 메타데이터만 |
| Contract Instance 변경 없음 | ✅ |
| Blog/WordPress 변경 없음 | ✅ |
