# jeonse-vs-monthly 배포 경로 진단 결과

**진단일**: 2026-08-09
**진단 범위**: 읽기 전용. 코드/설정/Registry/`_site` 변경 없음.

---

## 1. 로컬 `_site` 확인

```
data/workspace/_site/jeonse-vs-monthly/
  index.html   15,218 bytes  (2026-08-09 09:16)
  script.js    23,913 bytes  (2026-08-09 09:16)
  style.css    15,309 bytes  (2026-08-09 09:16)
```

**결과**: ✅ 로컬에 정상 존재. 3개 파일 모두 있음.

---

## 2. `_site/index.html` 메인 카드 확인

```html
<!-- data/workspace/_site/index.html line 44 -->
<a class="cm-calc-card" href="https://calcmate.kr/jeonse-vs-monthly/"
   aria-label="전세 vs 월세 비교 계산기">
  <span class="cm-calc-emoji">🧮</span>
  <div class="cm-calc-name">전세 vs 월세 비교 계산기</div>
  <div class="cm-calc-desc">전세보증금과 월세 조건을 입력하면...</div>
</a>
```

**결과**: ✅ 로컬 index.html에 jeonse-vs-monthly 카드 포함.

---

## 3. `_site/sitemap.xml` URL 확인

```xml
<!-- data/workspace/_site/sitemap.xml line 16 -->
<url>
  <loc>https://calcmate.kr/jeonse-vs-monthly/</loc>
  <lastmod>2026-08-09</lastmod>
  <changefreq>weekly</changefreq>
  <priority>0.8</priority>
</url>
```

**결과**: ✅ 로컬 sitemap.xml에 jeonse-vs-monthly URL 포함.

---

## 4. Git 커밋 상태

### 커밋 포함 파일 (`git show --stat 27dad7a`)

```
data/workspace/_site/index.html                   |   1 +
data/workspace/_site/jeonse-vs-monthly/index.html | 238 +++
data/workspace/_site/jeonse-vs-monthly/script.js  | 583 +++
data/workspace/_site/jeonse-vs-monthly/style.css  | 283 +++
data/workspace/_site/sitemap.xml                  |  27 +-
(+ 6개 파일)
```

**결과**: ✅ `_site/jeonse-vs-monthly/` 파일들이 27dad7a 커밋에 포함됨.

### 원격 브랜치 상태 (`git remote show origin`)

```
Remote branch:
  master  new (next fetch will store in remotes/origin)
Local ref configured for 'git push':
  master pushes to master (fast-forwardable)
```

**결과**: ❌ `origin/master` 추적 브랜치가 로컬에 없음.
`git log --oneline origin/master..HEAD` → `fatal: unknown revision`

### 브랜치 장식자 (`git log --decorate`)

```
27dad7a (HEAD -> master)   ← origin/master 포인터 없음
419cc84
7189e7c (tag: v2.1.0)
...
```

**결론**: **`git push`가 한 번도 실행되지 않음.** 로컬에만 커밋들이 있고 GitHub remote에 없음.

---

## 5. GitHub Actions 배포 이력

**`gh` CLI 미설치** → 런 기록 직접 조회 불가.

**워크플로 파일 (`.github/workflows/deploy.yml`) 내용**:
```yaml
on:
  push:
    branches: [master]
    paths:
      - 'data/workspace/_site/**'
      - '.github/workflows/deploy.yml'

jobs:
  deploy:
    steps:
      - uses: actions/upload-pages-artifact@v3
        with:
          path: 'data/workspace/_site'
      - uses: actions/deploy-pages@v4
```

**분석**:
- 트리거 조건: `master` 브랜치에 `data/workspace/_site/**` 경로 변경이 포함된 push
- 27dad7a는 이 조건을 만족하지만 **push가 없었으므로 트리거 불가**
- 이전에 한번 push됐던 커밋(Pages Last-Modified: 2026-08-08 02:05 UTC)에서 워크플로가 실행되었고, 그 배포 결과가 현재도 유지 중

---

## 6. GitHub Pages 설정

**Pages 응답 헤더**:
```
Last-Modified: Sat, 08 Aug 2026 02:05:29 GMT   ← 2026-08-08 KST 11:05
```

27dad7a 커밋 시각: `Sun Aug 9 07:18:06 2026 +0900` (KST)

**결론**: GitHub Pages가 27dad7a **이전** 커밋 기준 배포본을 서비스 중.
Pages 소스는 `data/workspace/_site` 폴더 전체이고 설정 자체는 정상.

---

## 7. 실제 calcmate.kr 접속 결과

| URL | 응답 | 비고 |
|---|---|---|
| `https://calcmate.kr/` | **200 OK** | 정상 응답 |
| `https://calcmate.kr/jeonse-vs-monthly/` | **404 Not Found** | 미배포 |

**메인 페이지 실제 계산기 목록** (curl 응답 기준):

| 순서 | 계산기 | 사이트 노출 |
|---|---|---|
| 1 | 주휴수당 | ✅ |
| 2 | 퇴직금 | ✅ |
| 3 | 연차수당 | ✅ |
| 4 | 실업급여 | ✅ |
| 5 | 4대보험 | ✅ |
| 6 | 연말정산 환급액 | ✅ |
| 7 | 육아휴직 급여 | ✅ |
| 8 | freelancer-tax-3p3 | ❌ (미배포) |
| 9 | jeonse-vs-monthly | ❌ (미배포) |

**7개 계산기만 실제 서비스 중.** 8번째(phase3-1), 9번째(phase3-2) 계산기 모두 미배포.

---

## 8. 원인 분류 및 근거

### 확정 원인: **원인 2 — `_site`는 생성·커밋됐으나 GitHub에 push되지 않음**

```
파이프라인 단계별 상태:

[단계 1] 로컬 _site 생성           ✅ data/workspace/_site/jeonse-vs-monthly/ 존재
[단계 2] Git 로컬 커밋              ✅ 27dad7a에 _site 파일 포함
[단계 3] git push to GitHub        ❌ push 미실행 — 여기서 끊김
[단계 4] GitHub Actions 트리거      ❌ push 없으므로 트리거 불가
[단계 5] Pages 배포 업데이트        ❌ 2026-08-08 이전 버전 유지
[단계 6] calcmate.kr 반영           ❌ 구 버전 7개 계산기만 서비스
```

### 근거

1. `git remote show origin` → `master new (next fetch will store in remotes/origin)`: 로컬에 origin/master 추적 브랜치 없음 = fetch/push 미실행
2. `git log --decorate` → `(HEAD -> master)` 뒤에 `(origin/master)` 없음
3. `git log origin/master..HEAD` → `fatal: unknown revision`: remote에 해당 커밋 없음
4. Pages Last-Modified: 2026-08-08 02:05 UTC < 27dad7a 커밋 2026-08-09 07:18 KST
5. 실제 사이트에 freelancer-tax-3p3(phase3-1, 419cc84)도 없음 = 419cc84, 27dad7a 모두 미push

### 제외된 원인들

| 원인 후보 | 제외 근거 |
|---|---|
| 1. `_site` 생성 자체 안 됨 | _site 파일 로컬 정상 존재 |
| 3. Actions 트리거 안 됨/실패 | push 자체가 없어서 도달 불가 |
| 4. Pages 소스 설정 문제 | deploy.yml `path: data/workspace/_site` 정상 |
| 5. CDN 캐시 지연 | push가 없었으므로 캐시 문제 아님 |
| 6. HOLD 필터 의도적 제외 | READY 전환 후 커밋된 파일에 카드 포함됨 (로컬 index.html 확인) |

---

## 다음 단계

**필요한 조치**: `git push origin master`

이 push로 27dad7a(+ 419cc84)가 GitHub에 올라가면:
1. `data/workspace/_site/**` 경로 변경 감지 → Actions 자동 트리거
2. `data/workspace/_site` 전체 → GitHub Pages 배포
3. calcmate.kr에 9개 계산기 반영

**push 전 추가 확인 권고**:
- `data/workspace/_site/jeonse-vs-monthly/script.js`의 computeResult 버그 (3개 출력 중 1개만 처리) → push와 함께 또는 별도로 수정 여부 결정 필요
- push는 `feat(app-factory)` + `feat(phase3-2)` 두 커밋이 함께 올라감

---

*진단 기준: 2026-08-09 / 읽기 전용 / 코드·설정·파일 변경 없음*
