# docs/experiments — 격리 실험 프롬프트 보관소

격리(isolation) 실험을 할 때는 **monkeypatch/런타임 주입만 하지 말고, 실제 모델에 넣은 프롬프트 블록 원문을 이 디렉토리에 반드시 함께 남긴다.** (직전 B-1 격리검증 블록이 대화 컨텍스트에만 있고 저장소에 없어 diff 불가였던 사고 재발 방지.)

## 파일명 규칙
```
YYYY-MM-DD_실험명_prompt.md
```
예: `2026-07-13_B1_prompt.md`

## 각 파일에 담을 것
- 실험 목적 / 대상 계산기
- **실제 사용한 프롬프트 블록 verbatim**(코드펜스로 감싸 공백·줄바꿈 보존)
- 블록이 삽입된 위치(파일 경로 + 조립 순서)
- 검증 결과 요약(통과율 등)과 커밋 해시

## 검증 하니스
`scripts/reverify_forbidden.py` — legal_basis forbidden_articles 혼입 여부를 실제 writer 호출로 N회 측정.
