# 운영 가이드 — Content Sync 상시 실행 (Windows 작업 스케줄러)

> Calculator 자동 Scheduler(`run_scheduler.bat`/`main.py --scheduler`)는 제거되었다(Calculator는 수동 생성).
> 이 문서는 여전히 유효한 **Content Sync**(WordPress→Sheets 상태 동기화)의 상시 실행 절차만 다룬다.

## 왜 필요한가 (배경)

Content Sync 스레드는 **`dashboard.py` 모듈 최상위**에서 기동된다(`_start_content_sync_thread`).
그런데 Streamlit은 `streamlit run dashboard.py`로 서버만 띄우면 스크립트 본문을 실행하지 않고,
**브라우저 세션이 접속할 때** 비로소 실행한다.

→ 결과: **아무도 브라우저를 안 열면 스레드가 안 켜지고, 그날 03:00 동기화가 안 됨.**

**해결:** Content Sync를 대시보드와 무관한 **독립 프로세스**로 상시 구동한다.
독립 진입점은 이미 존재한다 — `python run_sync.py`.

> 참고: Blog Schedule(`_start_blog_scheduler_thread`)도 동일한 구조(대시보드 모듈 최상위 기동)를
> 쓰므로 브라우저 미접속 시 동일하게 안 켜진다. 다만 Blog Schedule은 아직 `run_scheduler.bat`에
> 해당하는 독립 프로세스 launcher가 없다(`scripts/run_blog_scheduler.py`는 1회성 CLI이지 상시 루프가
> 아님) — 상시 자동 운영이 필요해지면 이 문서와 동일한 패턴(bat + 작업 스케줄러)으로 별도 launcher를
> 만드는 것을 검토한다(이번 문서 정리 범위 밖).

---

## 생성된 파일

| 파일 | 역할 | 내부 실행 |
|---|---|---|
| `run_sync.bat` | Content Sync 상시 런처 | `run_sync.py` → `run_sync_loop` |

- `%~dp0` 기준으로 **프로젝트 폴더/venv 파이썬을 자동 인식**(경로 하드코딩 없음, 폴더 이동에도 견고).
- **자동 재시작**: 프로세스가 죽거나 종료해도 10~30초 후 재기동(무한 루프).
- stdout/stderr를 `data\logs\sync_stdout.log`에 남김(문제 진단용).

> 실제 값 참고 — venv 파이썬: `C:\Users\연수\Desktop\블로그자동_v12\.venv\Scripts\python.exe`,
> 작업 폴더: `C:\Users\연수\Desktop\블로그자동_v12`

---

## 등록 방법 A — schtasks 명령 (빠름, PowerShell 관리자 권한 권장)

**"로그온 시 시작"** 트리거로 등록한다(상시 실행은 .bat의 자기 재시작 루프가 담당).

```powershell
schtasks /create /tn "SalaryMate Content Sync" ^
  /tr "C:\Users\연수\Desktop\블로그자동_v12\run_sync.bat" ^
  /sc ONLOGON /rl LIMITED /f
```

> PowerShell에서 `^` 줄바꿈이 문제되면 한 줄로 붙여 실행. 한글 경로 인코딩 문제가 나면 아래 GUI 방식을 사용.

등록 확인 / 즉시 시작 / 삭제:
```powershell
schtasks /query /tn "SalaryMate Content Sync" /v /fo LIST
schtasks /run   /tn "SalaryMate Content Sync"      # 지금 바로 한 번 기동(테스트)
schtasks /end   /tn "SalaryMate Content Sync"      # 실행 중지
schtasks /delete /tn "SalaryMate Content Sync" /f  # 등록 해제
```

---

## 등록 방법 B — GUI (작업 스케줄러, 세밀 설정 포함)

`Win + R` → `taskschd.msc` → **작업 만들기**(단순 작업 아님).

**[일반] 탭**
- 이름: `SalaryMate Content Sync`
- ● **사용자가 로그온할 때만 실행** (암호 저장 불필요, 사용자 세션에서 구동)
- ☑ **숨김**(콘솔 창 숨김; 완전 무창을 원하면 .bat의 `python.exe`를 `pythonw.exe`로 바꿔도 됨)

**[트리거] 탭** → 새로 만들기
- 작업 시작: **로그온할 때** → 확인 (※ 시간 트리거 아님 — 03:00 판정은 루프 내부에서 함)

**[동작] 탭** → 새로 만들기
- 프로그램/스크립트: `C:\Users\연수\Desktop\블로그자동_v12\run_sync.bat`
- 시작 위치(중요): `C:\Users\연수\Desktop\블로그자동_v12`

**[설정] 탭** (상시 실행 보강)
- ☑ 작업이 실패하는 경우 다시 시작 간격: **1분**, 다시 시작 시도: **최대 999회**
- ☐ "다음 시간이 지나면 작업 중지" **체크 해제**(무한 실행 허용)
- "작업이 이미 실행 중인 경우 다음 규칙 적용": **새 인스턴스를 시작 안 함**(로그온 반복 시 중복 방지)

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

`dashboard.py`의 `_start_content_sync_thread`는 **제거하지 않는다.** 파일 락(`content_sync.lock`)이
독립 프로세스와의 동시 실행을 막으므로, 대시보드를 열었을 때 켜지는 스레드는 **락으로 보호되는
보조 안전장치**로 남는다.

---

## 등록 후 검증 — 브라우저를 아예 열지 않고 동기화 확인

목표: **대시보드/브라우저 없이** 03:00에 실제 동기화가 되는지 확인.

1. **대시보드 완전 종료**(Streamlit 프로세스 끔). 이래야 "독립 프로세스가 동기화함"을 순수 검증.
2. **런처 시작**: `schtasks /run /tn "SalaryMate Content Sync"` (또는 로그오프→로그온).
3. **로그 확인** — `data\logs\sync_stdout.log`에 `[sync] Content Sync 스케줄러 시작 (run_at=03:00 ...)`
   및 catch-up/03:00 실행 로그가 남는지 확인.
4. **프로세스 확인** — `tasklist | findstr python` 에 python.exe 상주.

---

## 롤백 / 중지

```powershell
schtasks /end    /tn "SalaryMate Content Sync"
schtasks /delete /tn "SalaryMate Content Sync" /f
```
작업을 지워도 대시보드 내장 스레드(브라우저 접속 시 기동)는 그대로 동작한다(원상복귀).

## 주의

- .bat는 **콘솔 창**을 띄운다(로그온 세션). 창을 닫으면 프로세스가 종료되니, 숨김 실행 또는
  최소화 상태로 둔다. 완전 무창을 원하면 .bat 안 `".venv\Scripts\python.exe"`를
  `".venv\Scripts\pythonw.exe"`로 교체(단, 콘솔 stdout 로그는 앱 자체 로거로 대체 확인).
- Content Sync가 API·시트를 호출하므로, `config/secrets.yaml`의 키가 유효해야 동작이 성공한다.
