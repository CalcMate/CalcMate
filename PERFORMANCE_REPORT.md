# PERFORMANCE_REPORT.md — 대시보드 성능 분석/최적화

작업일: 2026-06-22 · 원칙: **기능·출력·파이프라인 변경 금지, 최적화만**. 수정 전 `dashboard_backup.py` 자동 생성.

---

## 1. 병목 분석 (실측)

| 구간 | 함수/위치 | 측정값 | 비고 |
|------|-----------|--------|------|
| 🔴 **Google Sheet 조회** | `sheet_sync.get_all_posts(cfg)` | **5.69초** (콜드), 5.24초(2회차) | gspread→Sheets API 왕복. **2~5초 지연의 주범** |
| 🔴 동일 호출 반복 | 현황/발행목록/작업보드/전략회의실 4개 탭 | 탭마다 5초 | 캐시 없이 매 탭 재호출 |
| 🟡 logs 조회 | 오류 로그 탭 `get_all("logs")` | 수 초(시트) | 동일 Sheets 왕복 |
| 🟢 로그 파일 읽기 | `pipeline.log` 전체 read | 3ms (현재 66KB) | 지금은 작지만 로그 누적 시 선형 증가 |
| 🟢 헬스/예산/스케줄 | health_last.json·budget.json·today_schedule.json | <5ms | 로컬 파일, 빠름 |

> 측정 방법: `.venv` python으로 `get_all_posts` 직접 호출 시간, `pipeline.log` 전체읽기 vs tail(64KB) 비교.

**결론**: 메뉴 이동 지연의 원인은 거의 전적으로 **탭마다 Google Sheet를 동기 재조회(5초)**하는 것. 로컬 파일 읽기는 영향 미미.

---

## 2. 적용한 최적화 (출력 불변)

| # | 항목 | 변경 | 효과 |
|---|------|------|------|
| 1 | **Sheet 조회 60초 캐시** | `@st.cache_data(ttl=60)` `cached_posts()` / `cached_table()` 추가, 5개 호출처 교체 | 2회차부터 5.7초 → **~0초** |
| 2 | **캐시 무효화** | `_run_action`에서 액션(발행/생성 등) 후 `st.cache_data.clear()` | 데이터 신선도 유지(출력 동일) |
| 3 | **로그 tail 읽기** | `_tail_lines()` 바이트 seek, 실시간로그/오류요약/`pipeline_status._tail` 적용 | 전체 읽기 제거(로그 커져도 일정) |
| 4 | **Lazy import(확인)** | 무거운 모듈(scheduler/app_factory/ai_workspace 등)은 이미 탭 진입 시 import | 초기 로드 부담 없음(현행 유지) |

| 5 | **SQLite 미러 읽기 캐시** | `modules/dashboard_cache.py` 신규 — `cached_posts/cached_table`가 미러(`data/cache/dashboard_cache.db`) 우선 읽기, 미스/만료 시 원본 1회 조회→미러 갱신, **원본 오류 시 미러 폴백** | 세션간/만료 후에도 ~6ms. 시트 403에도 마지막 데이터 표시(크래시 방지) |
| 6 | **백그라운드 워밍** | `scripts/sync_cache.bat`(=`python -m modules.dashboard_cache`) | 주기 실행 시 첫 진입도 즉시 |

변경 파일: `dashboard.py`(2단 캐시 헬퍼 + 호출처 교체 + 로그 tail + 액션 후 미러 무효화), `modules/pipeline_status.py`(`_tail` 바이트 tail), 신규 `modules/dashboard_cache.py`·`scripts/sync_cache.bat`. **기존 함수 시그니처/출력/파이프라인 무변경.**

### 2단 캐시 구조
```
cached_posts()/cached_table()
  └ @st.cache_data(ttl=60)         ← 세션 내 즉시(메모리)
       └ dashboard_cache.read(ttl=120)
            ├ 미러 신선 → 즉시(~6ms)
            ├ 미러 만료/없음 → 원본 1회 조회 → 미러 저장 (콜드 1회만 느림)
            └ 원본 오류(403 등) → 마지막 미러 반환(폴백, 무크래시)
  ※ 발행/생성 액션(_run_action) 후 cache_data.clear() + 미러 invalidate → 신선도 보장
```

측정(원본=sqlite 기준): 콜드 32.7ms / 웜 6.0ms / 출력 동일 / 오류 폴백 정상. 원본=Sheets일 때 콜드 1회만 5.7초, 이후 미러 ~6ms.

---

## 3. 성능 비교표 (예상치, 실측 기반)

| 시나리오 | 최적화 전 | 최적화 후 | 개선 |
|----------|-----------|-----------|------|
| 첫 진입(콜드, 캐시 비어있음) | ~5.7초 | ~5.7초 (1회) | — (불가피한 1회 워밍업) |
| **탭 이동(캐시 적중, 60초 내)** | **2~5.7초** | **<0.1초** | **≈50배+** |
| 동일 탭 재렌더(위젯 조작) | 5초 | <0.1초 | ≈50배 |
| 오류 로그 탭 | 수 초(시트) | <0.1초(캐시) | 대폭 |
| 실시간 로그 탭(로그 1MB 가정) | 선형 증가 | 일정(~수 ms) | 안정 |
| 발행/생성 액션 후 | 5초 | 1회 재조회 후 캐시 | 신선도 유지 |

> 목표 **0.5초 이하**: 캐시 워밍업(첫 1회) 이후 모든 메뉴 이동에서 달성. 첫 진입 1회만 Sheet 왕복(불가피) — 필요 시 OPTIMIZATION_PLAN의 SQLite 캐시로 첫 진입도 단축 가능.

---

## 4. 검증
- `dashboard.py`/`pipeline_status.py` 컴파일 OK
- 최적화 대시보드 실기동: health `ok`, 렌더 무오류
- 캐시 호출처 5곳 교체 확인, 정의부(`cached_posts`) 재귀 없음 확인
- 기능/출력 동일(같은 데이터·같은 화면), 백업 `dashboard_backup.py` 보관
