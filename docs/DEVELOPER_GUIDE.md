# DEVELOPER GUIDE — 개발자 안내

> 계산기 서브시스템의 코드 구조·규칙·테스트. 파이프라인 코어(정책/RSS 12단계)는 루트 README 참조.

## 폴더 구조 (계산기 관련)

```
modules/
  app_factory.py         신규 계산기 생성(generate_app) + 저장(save_app) + calculator_index
  app_generator.py       계산기 정적앱(index.html/style.css/script.js) 생성 · compute/관련카드는 registry에서
  calculator_pipeline.py  writer 생성 → Gate/Score → Retry/HOLD → 발행 오케스트레이션
  publish_quality.py      Gate(check_gates + _check_g8) + Score(_score_with_gpt)
  registry_loader.py      legal_basis.draft.yaml + registry_auto.yaml merge 로더(단일 소스)
  publisher.py            WordPress REST CRUD(발행/수정/삭제/복원) — WP 호출은 이 파일에만
  internal_link_engine.py 관련 계산기/글 내부링크
docs/
  legal_basis.draft.yaml  사람 큐레이션 registry(legal 포함) — 코드는 읽기만
  registry_auto.yaml      App Factory 자동생성 registry — App Factory만 씀
  calculator_index.json   slug↔한글 name 매핑(순수 참조, 어떤 로직도 안 읽음)
templates/calculators/    계산기 UI 템플릿(v2) + assets(js/css)
tests/
  snapshot_calculators.py 계산기 생성물 회귀 스냅샷 하니스(save/check)
data/workspace/<slug>/    계산기 파일 저장(대시보드 "파일 저장" 시) — 폴더명 = slug
```

## 핵심 규칙

1. **slug = 내부 식별자(영문), name = 표시(한글).** 폴더/URL/registry 키/WP는 slug, 화면은 name.
   기존 계산기 slug는 변경 금지(registry 키·폴더·WP 참조).
2. **registry가 유일 소스.** compute 분기·관련카드는 `app_generator._registry()`(→ registry_loader)에서만
   읽는다. 하드코딩 폴백은 Phase D에서 제거됨. 새 계산기는 registry(자동/큐레이션)에 있어야 한다.
3. **Gate(결정론) vs Score(GPT) 책임 분리.** "존재/형식/개수"는 Gate(G1~G8), "품질/맥락"만 Score(S1~S6).
   Score 루브릭에 존재 판정을 넣지 말 것(작업지시서 F에서 S1/S2/S3의 존재판정 재판정을 제거함).
4. **legal은 사람이 검증.** AI에게 조사시키면 환각(잘못된 조항)이 재발한다. G8은 legal_basis의 검증값을
   문자열 매칭으로 확인하는 결정론 방어선.
5. **WordPress 호출은 publisher.py에만.** `_wp_auth(cfg)` 공유.

## 회귀 테스트 — 스냅샷 하니스

계산기 생성물은 순수 함수(`generate_calculator(calc, cfg)` — 타임스탬프 출력 없음)라 결정론적이다.

```bash
python -m tests.snapshot_calculators save    # 골든 저장(7종×5산출물=35 sha256)
python -m tests.snapshot_calculators check   # 회귀 비교 — 불일치 계산기/산출물 핀포인트
```

**registry/generator를 건드린 뒤에는 반드시 `check`로 35/35 동일을 확인**한다. 리팩터링·registry 변경이
출력을 바꾸지 않았음을 기계적으로 보장한다.

## 자주 쓰는 검증

```bash
# 컴파일
python -m py_compile modules/<file>.py
# registry 로드(3 소비자 동일해야)
python -c "from modules import app_generator as ag, calculator_pipeline as cp, publish_quality as pq; \
print(len(ag._registry()), len(cp._load_legal_basis()), len(pq._load_legal_basis()))"
# 한글 print 깨짐 방지(Windows)
PYTHONIOENCODING=utf-8 python ...
```

## 확장 시 유의

- **신규 계산기 추가**: App Factory 경유가 정석(registry_auto 자동기록). 수동 추가 시 registry에 엔트리 필수.
- **compute_type 확장**: `date_based`만 코드가 소비(날짜 JS 분기 + 수식검증 skip). single/dict는 현재 표식용.
- **Score 차원 변경**: `_SCORE_LABEL`/`_SCORE_GRADE` + 프롬프트. Gate가 이미 보는 것을 재판정하지 말 것.
- **Sheets 주의**: `sheets_adapter.insert()`는 헤더에 없는 새 컬럼을 자동 추가하지 않는다(신규 필드는 시트 헤더 수동 추가).
