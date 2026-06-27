# dashboard_ui_refactor.md — 운영센터 홈 SaaS 레이아웃 재구성

작업일: 2026-06-22 · 대상: `dashboard.py` (UI 코드만) · 백업: `dashboard_backup_ui.py`

> ★ 비즈니스 로직 / Repository / Adapter / Pipeline **수정 없음**. 대시보드 UI(🏠 운영센터 홈)의 **레이아웃 구조**만 SaaS 형태로 재구성.

---

## 1. 변경 개요

기존 `🏠 운영센터` 탭은 인라인으로 KPI·빠른실행·상태를 나열(Streamlit 기본 흐름)했다.
이를 **명시적 컴포넌트 함수**로 분리하고 다음 구조로 재배치했다(Linear/Vercel/OpenAI Platform 풍).

```
┌ Header ── SalaryMate OS / AI Content Operating System ─┐
├ KPI ─ Sites │ Articles │ Queue │ Revenue (st.columns(4)) ┤
├ Pipeline Status ─ 📥수집 → 🧠전략 → ✍작성 → 🔍검수 → 🚀발행 ┤
├ Quick Actions (좌)        │  Recent Activity (우)         ┤
└────────────────────────────────────────────────────────┘
```

`if tab == "🏠 운영센터":` 블록(135줄)을 **`render_dashboard_home()` 단일 호출**로 교체.
나머지 탭(작업보드/일정/사이트관리/계산기/설정/…)은 **그대로 유지** — 사이드바 클릭 시에만 표시.

---

## 2. 추가된 컴포넌트 (dashboard.py, UI 전용)

| 함수 | 역할 | 사용 CSS 클래스 | 데이터(읽기 전용) |
|------|------|----------------|-------------------|
| `render_header()` | 상단 타이틀 카드 | `sm-card` | — |
| `render_kpi_cards()` | Sites/Articles/Queue/Revenue 4카드 | `sm-kpi` + `st.columns(4)` | `cached_table("sites")`, `cached_posts()` |
| `render_pipeline_status()` | 수집→전략→작성→검수→발행 가로 카드(emoji) | `sm-card` `sm-pipe` `sm-step` | `pipeline_status.get_pipeline_state` |
| `render_quick_actions()` | 파이프라인/계산기/글/워드프레스 발행 버튼 | `st.container(border)` | `main.run_once`, `calculator_pipeline`, `scheduler.immediate_publish` (트리거만) |
| `render_recent_activity()` | 최근 로그 20줄(없으면 "No Activity") | `st.container(border)` | `_tail_lines(pipeline.log,20)` |
| `_kpi_card()` | KPI 카드 렌더 헬퍼 | `sm-kpi` | — |
| `render_dashboard_home()` | 위 컴포넌트 조합(헤더→KPI→파이프라인→[좌:액션 \| 우:활동]) | — | — |

## 3. 수정된 함수/블록

| 위치 | 변경 |
|------|------|
| `dashboard.py` `if tab == "🏠 운영센터":` | 인라인 UI 135줄 → `render_dashboard_home()` 호출로 교체 |
| (상단) | `render_*` 컴포넌트 7개 신규 정의 |

> KPI/액션/활동의 데이터·동작은 **기존 함수를 그대로 재사용**(`cached_posts`/`cached_table`/`run_once`/`run_calculator_once`/`immediate_publish`/`get_pipeline_state`). 새 로직 없음.

## 4. Quick Actions 매핑 (기존 기능 트리거)

| 버튼 | 호출 |
|------|------|
| ▶ 파이프라인 실행 | `main.run_once(cfg)` |
| 🧮 계산기 생성 | `calculator_pipeline.run_calculator_once(cfg, max_count=1)` |
| 📝 글 생성 | `main.run_once(cfg, max_count=1)` |
| 🌐 워드프레스 발행 | `scheduler.immediate_publish(cfg, run_once, "pull")` |

액션 후 `_run_action`이 `st.cache_data.clear()` + 미러 invalidate로 데이터 갱신.

## 5. 검증
- `dashboard.py` 컴파일 OK
- 헤드리스 구동 + 실제 스크린샷 캡처로 4섹션(헤더/KPI4/파이프라인5/액션·활동) 렌더 확인
- 다크/글래스 테마 적용(`assets/css/dashboard.css`의 `sm-card`/`sm-kpi`/`sm-pipe`/`sm-step`)
- 기존 탭·로직·파이프라인 무변경, 백업 `dashboard_backup_ui.py` 보관

## 6. 실행
```
scripts\run_dashboard.bat        # = streamlit run dashboard.py (재구성된 SaaS 홈)
```
> 첫 진입 시 KPI는 Google Sheet 콜드 조회로 수 초 소요될 수 있음(이후 캐시로 즉시). `scripts\sync_cache.bat` 주기 실행 시 첫 진입도 빠름.
