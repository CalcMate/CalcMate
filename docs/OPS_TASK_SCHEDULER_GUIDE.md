# 운영 가이드 — 스케줄러/동기화 상시 실행 (Windows 작업 스케줄러)

## 왜 필요한가 (배경)

예약 발행 스케줄러 스레드와 Content Sync 스레드는 **`dashboard.py` 모듈 최상위**에서 기동된다
(`dashboard.py:99-101`, `136-137`). 그런데 Streamlit은 `streamlit run dashboard.py`로 서버만 띄우면
스크립트 본문을 실행하지 않고, **브라우저 세션이 접속할 때** 비로소 실행한다.

→ 결과: **아무도 브라우저를 안 열면 스레드가 안 켜지고, 그날 자동 발행은 0건.**
(실측: 터미널만 켜두고 브라우저 미접속 → 발행 0건 / 접속한 날만 정상 발행.)

**해결:** 발행 스케줄러와 Content Sync를 대시보드와 무관한 **독립 프로세스**로 상시 구동한다.
독립 진입점은 이미 존재한다 — `python main.py --scheduler`, `python run_sync.py`.

---

## 생성된 파일

| 파일 | 역할 | 내부 실행 |
|---|---|---|
| `run_scheduler.bat` | 예약 발행 스케줄러 상시 런처 | `main.py --scheduler` → `run_scheduler_loop` |
| `run_sync.bat` | Content Sync 상시 런처 | `run_sync.py` → `run_sync_loop` |

두 .bat 모두:
- `%~dp0` 기준으로 **프로젝트 폴더/venv 파이썬을 자동 인식**(경로 하드코딩 없음, 폴더 이동에도 견고).
- **자동 재시작**: 프로세스가 죽거나 종료해도 10~30초 후 재기동(무한 루프).
- stdout/stderr를 `data\logs\scheduler_stdout.log` / `sync_stdout.log`에 남김(문제 진단용).

> 실제 값 참고 — venv 파이썬: `C:\Users\연수\Desktop\블로그자동_v12\.venv\Scripts\python.exe`,
> 작업 폴더: `C:\Users\연수\Desktop\블로그자동_v12`

---

## 등록 방법 A — schtasks 명령 (빠름, PowerShell 관리자 권한 권장)

두 작업을 **"로그온 시 시작"** 트리거로 등록한다(상시 실행은 .bat의 자기 재시작 루프가 담당).

```powershell
# 1) 예약 발행 스케줄러
schtasks /create /tn "SalaryMate Publish Scheduler" ^
  /tr "C:\Users\연수\Desktop\블로그자동_v12\run_scheduler.bat" ^
  /sc ONLOGON /rl LIMITED /f

# 2) Content Sync  (※ 시간 트리거 아님 — 03:00 판정은 루프 내부에서 함)
schtasks /create /tn "SalaryMate Content Sync" ^
  /tr "C:\Users\연수\Desktop\블로그자동_v12\run_sync.bat" ^
  /sc ONLOGON /rl LIMITED /f
```

> PowerShell에서 `^` 줄바꿈이 문제되면 한 줄로 붙여 실행. 한글 경로 인코딩 문제가 나면 아래 GUI 방식을 사용.

등록 확인 / 즉시 시작 / 삭제:
```powershell
schtasks /query /tn "SalaryMate Publish Scheduler" /v /fo LIST
schtasks /run   /tn "SalaryMate Publish Scheduler"      # 지금 바로 한 번 기동(테스트)
schtasks /end   /tn "SalaryMate Publish Scheduler"      # 실행 중지
schtasks /delete /tn "SalaryMate Publish Scheduler" /f  # 등록 해제
```

---

## 등록 방법 B — GUI (작업 스케줄러, 세밀 설정 포함)

`Win + R` → `taskschd.msc` → **작업 만들기**(단순 작업 아님).

**[일반] 탭**
- 이름: `SalaryMate Publish Scheduler`
- ● **사용자가 로그온할 때만 실행** (암호 저장 불필요, 사용자 세션에서 구동)
- ☑ **숨김**(콘솔 창 숨김; 완전 무창을 원하면 .bat의 `python.exe`를 `pythonw.exe`로 바꿔도 됨)

**[트리거] 탭** → 새로 만들기
- 작업 시작: **로그온할 때** → 확인

**[동작] 탭** → 새로 만들기
- 프로그램/스크립트: `C:\Users\연수\Desktop\블로그자동_v12\run_scheduler.bat`
- 시작 위치(중요): `C:\Users\연수\Desktop\블로그자동_v12`

**[설정] 탭** (상시 실행 보강)
- ☑ 작업이 실패하는 경우 다시 시작 간격: **1분**, 다시 시작 시도: **최대 999회**
- ☐ "다음 시간이 지나면 작업 중지" **체크 해제**(무한 실행 허용)
- "작업이 이미 실행 중인 경우 다음 규칙 적용": **새 인스턴스를 시작 안 함**(로그온 반복 시 중복 방지)

→ **Content Sync**도 동일하게 하나 더 만든다. 이름 `SalaryMate Content Sync`,
동작 프로그램만 `run_sync.bat`으로. **트리거는 반드시 "로그온할 때"** — 03:00 시간 트리거로 걸지 말 것.

---

## Content Sync가 기존 03:00과 겹치지 않는 이유 (검증됨)

`run_sync_loop`(`modules/content_sync.py:506`)은:
- `last_run_date`(영속 마커, 재시작에도 복원) `!= 오늘` **그리고** `run_at`(03:00) 도래일 때만 실행.
- 실행 시 `content_sync.lock` 획득 → 대시보드 내장 content-sync 스레드와 **락으로 조율**(동시 실행 차단).
- 실행 후 `last_run_date = 오늘`로 갱신 → **하루 1회 보장**.
- 시작 시 catch-up: 재부팅으로 03:00을 놓쳤으면 밀린 오늘분 1회만 즉시 처리.

→ 독립 프로세스 + 대시보드 스레드가 동시에 떠 있어도 **03:00 동기화는 하루 1번**만 일어난다.
그래서 작업 스케줄러 트리거는 "시간"이 아니라 "로그온 시 상시 실행"이어야 한다(타이밍은 루프가 판정).

## 대시보드 내장 스레드는 그대로 유지

`dashboard.py`의 스레드 기동 코드(`_start_scheduler_thread` / `_start_content_sync_thread`)는
**제거하지 않는다.** 파일 락(`_acquire_lock` / `content_sync.lock`)이 독립 프로세스와의 동시 발행을
막으므로, 대시보드를 열었을 때 켜지는 스레드는 **락으로 보호되는 보조 안전장치**로 남는다.

---

## 등록 후 검증 — 브라우저를 아예 열지 않고 발행 확인

목표: **대시보드/브라우저 없이** 예약 시각에 실제 발행이 되는지 확인.

1. **대시보드 완전 종료**(Streamlit 프로세스 끔). 이래야 "독립 프로세스가 발행함"을 순수 검증.
2. **테스트 슬롯을 몇 분 뒤로 설정**(브라우저 없이):
   - `config/config.yaml`의 `PUBLISH_SCHEDULE.weekday`(또는 오늘이 주말이면 `weekend`) 슬롯 하나를
     현재시각 +3~5분 구간으로 편집(예: 지금 14:00이면 `start: '14:05' / end: '14:10'`).
   - `data\schedule\today_schedule.json` **삭제**(다음 폴링에서 새 슬롯으로 재생성되게).
3. **런처 시작**: `schtasks /run /tn "SalaryMate Publish Scheduler"` (또는 로그오프→로그온).
4. **로그 확인** — `data\logs\scheduler_stdout.log`:
   - 기동: `슬롯 발행 스케줄러 시작 (poll=30s)`
   - 도래 시: `▶ 글N 발행 실행 (예약 HH:MM / 실제 HH:MM)` → `✅ 글N 발행 완료`
5. **일정 파일 확인** — `data\schedule\today_schedule.json`의 해당 항목 `status`가 `completed`로 바뀌고
   `actual_time`이 채워짐(브라우저 무접속 상태에서).
6. **결과물 확인** — Google Sheets `articles` 탭 새 행 / WordPress 새 글.
7. **프로세스 확인** — `tasklist | findstr python` 에 python.exe 상주.

> 빠른 상시화 확인: 위 4~6이 브라우저 0접속으로 통과하면 원인(브라우저 의존)이 해소된 것.
> Content Sync는 `data\logs\sync_stdout.log`에 `[sync] Content Sync 스케줄러 시작 (run_at=03:00 ...)`
> 및 catch-up/03:00 실행 로그로 확인.

---

## 롤백 / 중지

```powershell
schtasks /end    /tn "SalaryMate Publish Scheduler"
schtasks /delete /tn "SalaryMate Publish Scheduler" /f
schtasks /delete /tn "SalaryMate Content Sync" /f
```
작업을 지워도 대시보드 내장 스레드(브라우저 접속 시 기동)는 그대로 동작한다(원상복귀).

## 주의

- 두 .bat는 **콘솔 창**을 띄운다(로그온 세션). 창을 닫으면 프로세스가 종료되니, 숨김 실행 또는
  최소화 상태로 둔다. 완전 무창을 원하면 .bat 안 `".venv\Scripts\python.exe"`를
  `".venv\Scripts\pythonw.exe"`로 교체(단, 콘솔 stdout 로그는 앱 자체 로거로 대체 확인).
- 스케줄러/동기화가 API·시트를 호출하므로, `config/secrets.yaml`의 키가 유효해야 발행이 성공한다.
- 예산 한도 도달 시 스케줄러는 자동 일시정지(익일 재개)된다 — 이는 정상 동작.
