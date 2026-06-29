# AI_ASSISTANT_ANALYSIS.md

> `modules/ai_assistant.py` 분석 보고서 (SPRINT 2B 작업10). **코드 변경 없음 — 분석/제안만.**
> 대상: `modules/ai_assistant.py`(250줄) + 대시보드 AI Assistant 탭(승인 게이트).

## 1. Workflow 처리 방식
```
대시보드 AI Assistant 탭
  → chat(cfg, model_label, messages)
      ├ CHAT_MODELS에서 provider/model 선택 (GPT/Claude/Gemini)
      ├ _context_for(last_user): analyze_project() 구조 + 최근 오류 + 키워드 매칭 파일 일부 자동 첨부
      ├ 최근 10개 메시지만 convo 구성 (window)
      ├ provider.chat(system, convo, model, max_tokens=2500)
      └ BudgetTracker.record(model, tokens)  → 비용 기록
```
- **단발 요청-응답**(stateful agent 아님). 멀티스텝 자동 실행/툴콜 루프 없음 — 모델이 텍스트로 "이 파일을 이렇게 바꾸라" 제안 → 운영자가 수동으로 파일 도구 사용.
- 모델 3종: GPT(CEO/전략) · Claude(편집장/코드) · Gemini(실무/분석). `cfg`로 키 주입(이제 secrets 병합).

## 2. Approval 게이트 동작
- 파일 쓰기는 **자동 호출 안 됨**. 대시보드 `📝 파일 수정/생성` 익스팬더에서:
  1. `propose_diff(rel, new)` → 기존/신규 내용·길이 미리보기
  2. 운영자 `✅ 승인 후 저장` 클릭 시에만 `write_file`/`create_file` 호출
  3. `write_file`은 원본을 `data/assistant/backups/{name}.{ts}.bak`로 **자동 백업**
- **삭제/시스템 명령 미구현**(설계상 부재) → 파괴적 작업 원천 차단.
- 경로 안전: `_safe()`가 워크스페이스(ROOT) 밖 접근 차단(`..` escape 방지).

## 3. Workspace 파일 도구 범위
| 도구 | 동작 | 비고 |
|------|------|------|
| `list_directory` | 디렉터리 목록 | SKIP(.venv/__pycache__/.git) 제외 |
| `read_file` | 읽기(기본 40KB 컷) | READ_EXT 화이트리스트 |
| `search_files` | 파일명+내용 검색(최대 50히트) | rglob 전체 순회 |
| `create_file` | 신규 생성(존재 시 거부) | 승인 후 |
| `write_file` | 덮어쓰기(+백업) | 승인 후 |
| `propose_diff` | 변경 미리보기 | 승인 UI용 |
| ~~delete~~ | **미구현** | 의도적 부재 |

## 4. Memory 구조
- 파일: `data/assistant/memory.json` → `{rules:[], todo:[], dev_log:[]}` (kind별 `{text, at}` 누적).
- `tasks.json` → 태스크 리스트(`id/title/status`), 상태 4종(Pending/Running/Completed/Failed) — **상태 플래그만**(실행 엔진 없음, Lite).
- 단순 append 모델 — 검색/요약/만료/우선순위 없음.

## 5. Tool 연결 현황
- `chat()`는 **파일 도구를 자동 호출하지 않음** — 모델 출력은 순수 텍스트. 도구(read/write/search)는 **UI 버튼**으로만 구동(모델↔도구 자동 연결 없음).
- 컨텍스트 자동 주입은 `_context_for`의 **하드코딩 키워드 매핑**(app factory/config/reviewer/form engine/template)에 의존 → 그 외 파일은 모델이 직접 못 봄.
- 비용은 `BudgetTracker`로 기록되나, `chat`의 max_tokens=2500 고정.

## 6. 개선 제안 (우선순위)
| P | 제안 | 이유 |
|---|------|------|
| P1 | **툴콜 연결**: 모델이 read_file/search_files를 함수콜로 호출(에이전트 루프) | 현재 컨텍스트가 하드코딩 키워드에 한정 — 모델이 임의 파일 탐색 불가 |
| P1 | **대화 영속화**: messages를 세션→파일 저장(현재 휘발) | 새로고침 시 대화 손실 |
| P2 | **diff 가시화**: propose_diff에 라인 단위 unified diff 추가(현재 old/new 전문) | 대형 파일 변경 검토 용이 |
| P2 | **메모리 활용**: load_memory(rules/todo)를 chat system 프롬프트에 주입 | 저장만 되고 대화에 미반영 |
| P2 | **검색 효율**: search_files가 rglob 전체 순회 → ripgrep/인덱스 또는 조기 종료 강화 | 대형 트리에서 느림 |
| P3 | **모델 폴백**: provider 호출 실패(429 등) 시 fallback 모델 | 현재 단일 호출, 실패 시 그대로 예외 |
| P3 | **토큰 가변화**: max_tokens 고정 2500 → 작업 유형별 조정 | 긴 코드 생성 시 잘림 |
| P3 | **태스크 실행 연결**: tasks.json 상태를 실제 액션과 연동 | 현재 상태 플래그만(장식적) |

## 7. 강점(유지 권장)
- 승인 게이트 + 백업 + 경로 샌드박스 + 삭제 미구현 → **안전 설계 우수**.
- provider 추상화 재사용(ai_provider) → 모델 교체 용이.
- 컨텍스트 자동 첨부로 일반 운영자도 사용 쉬움.

---
> 본 문서는 분석 한정. 개선 구현은 별도 Sprint·승인 필요(특히 P1 툴콜은 ai_assistant.py 구조 변경).
