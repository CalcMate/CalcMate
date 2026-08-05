# 전체 평가

점수: 75/100

## 장점
- **모듈화 및 책임 분리**: `modules/` 디렉토리 내에 다양한 기능을 담당하는 모듈들이 잘 분리되어 있습니다. `cleaner`, `duplicate_checker`, `strategist`, `planner`, `writer`, `editor`, `image_generator`, `publisher`, `scheduler` 등 각 모듈이 명확한 역할을 수행합니다. 특히 `calculator_pipeline`은 계산기 관련 파이프라인을 전담하여 기존 파이프라인(`main.py`)과의 분리를 명확히 했습니다.
- **Repository/Adapter 패턴 적용**: `repositories/`와 `adapters/` 디렉토리를 통해 데이터 접근 계층이 추상화되어 있습니다. `db` 및 `storage` 어댑터 팩토리를 사용해 다양한 백엔드(Sheets, SQLite, Drive, Local)를 유연하게 지원하는 구조는 칭찬할 만합니다.
- **설정 관리**: `config_loader`를 통해 `config.yaml`과 `secrets.yaml`을 분리하고 병합하는 방식은 보안 및 관리 측면에서 우수합니다.
- **재시도 및 복구 로직**: `main.py`의 `_process_one` 함수에서 비용 보호, DLQ, 실패 처리 로직이 잘 구현되어 있으며, `scheduler.py`의 `failure_mode`와 `retry_queue.py`를 통해 재시도 메커니즘이 잘 구축되어 있습니다.
- **품질 관리 게이트**: `calculator_pipeline.py`와 `publish_quality.py`에서 GPT 기반의 품질 점수화(Score)와 결정론적인 게이트(Gate) 검사를 분리하여 코드 품질을 관리하는 방식이 체계적입니다. 특히 `_quality_signature`를 통한 재평가 로직은 프롬프트/설정 변경 시 자동 재도전을 유도하여 운영 효율성을 높입니다.
- **백그라운드 스레드 관리**: `dashboard.py`에서 스케줄러와 콘텐츠 동기화 스레드를 `st.cache_resource`와 `threading`을 활용하여 효율적으로 관리하고, 중복 실행을 방지하는 로직이 잘 구현되어 있습니다.
- **사용자 친화적 대시보드**: Streamlit 기반의 운영 대시보드는 시스템 상태, KPI, Workflow 진행 상황, 로그, 비용 모니터링 등 다양한 정보를 시각적으로 제공하여 운영 편의성을 높입니다.

## 문제점
- **일부 함수/파일의 과도한 길이 및 책임**: `main.py`의 `_process_one` 함수와 `dashboard.py` 파일 자체가 너무 길고 여러 책임을 동시에 지고 있습니다. 특히 `dashboard.py`는 UI 렌더링 로직과 백그라운드 서비스(스케줄러, Content Sync) 기동, 액션 처리 로직 등이 혼재되어 있어 가독성 및 유지보수성이 저하됩니다.
- **중복 코드 및 패턴**: `dashboard_backup.py`, `dashboard_backup_ui.py`와 같은 백업 파일들이 존재하며, `dashboard.py` 내에서도 `_kpi_card`, `_run_action` 등 UI 컴포넌트 렌더링 및 액션 처리에 유사한 패턴이 반복됩니다. 또한 `telegram_ops.notify_level`과 같은 알림 로직이 여러 모듈에 분산되어 사용되고 있습니다.
- **로그 및 예외 처리의 일관성 부족**: 전반적으로 로그가 충실한 편이나, 일부 모듈에서는 `try-except` 블록 내에서 예외 처리가 단순히 `LOG.warning`으로만 처리되고 재시도 로직이 부족하거나, 특정 에러 상황에 대한 구체적인 대응 없이 `pass` 처리되는 경우가 있습니다. `scheduler.py`의 `_alert_throttled`는 좋은 패턴이나, 전체 시스템에 일관되게 적용되지 않습니다.
- **`session_state` 관리 문제 (Dashboard)**: `dashboard.py`에서 `st.session_state`를 직접 사용하여 UI 상태를 관리하는데, 이는 애플리케이션의 복잡성을 증가시키고, 테스트 및 디버깅을 어렵게 만들 수 있습니다. 특히 `st.rerun()`의 남발은 불필요한 재렌더링을 유발하여 성능에 영향을 줄 수 있습니다.
- **Streamlit 성능 저하 가능성**: `@st.cache_resource`, `@st.cache_data`를 사용하여 캐싱을 적극적으로 활용하고 있지만, 긴 함수 실행 (`_run_action`, `run_calculator_once` 등) 및 `st.rerun()` 호출이 잦아질 경우 Streamlit의 본질적인 단점과 결합하여 사용자 경험 저하를 유발할 수 있습니다.
- **Dead Code 후보**: `modules/collector/finance.py`, `modules/collector/affiliate.py`, `adapters/db/postgres_adapter.py`, `adapters/storage/s3_adapter.py`와 같은 파일들은 `return []` 또는 주석 처리된 `import`로 `❌ stub` 상태이거나 미사용 중인 것으로 보입니다. 이는 장기적으로 코드베이스를 복잡하게 만들고 혼란을 줄 수 있습니다.
- **`TODO`/`FIXME` 및 주석 관리**: 코드 내 `TODO` 및 `FIXME` 주석이 산재해 있습니다. 이들은 당장의 버그는 아니지만, 잠재적인 개선점이나 미완성된 기능을 나타내므로 체계적인 관리가 필요합니다. 일부 주석은 코드의 변경 사항을 반영하지 못하고 있을 수 있습니다.

## 우선 수정 TOP10

### 1. `main.py::_process_one` 함수 분리
- **수정 난이도**: 보통
- **예상 효과**: `_process_one`은 160줄이 넘는 매우 긴 함수로, 12단계 파이프라인의 모든 핵심 로직을 포함하고 있습니다. 이를 여러 개의 작은 함수(예: `_step_clean_and_deduplicate`, `_step_strategize_and_plan`, `_step_write_and_review`, `_step_publish_and_log`)로 분리하여 각 단계의 응집도를 높이고 가독성을 개선해야 합니다. 각 스텝 함수는 `item`, `cfg`, `budget`, `site_mgr`, `existing_titles`, `recent_titles` 등 필요한 인자만 명시적으로 받도록 하여 의존성을 명확히 해야 합니다.

### 2. `dashboard.py` UI 컴포넌트 모듈화
- **수정 난이도**: 보통
- **예상 효과**: `dashboard.py`에 직접 포함된 `render_header`, `_kpi_card`, `render_current_site_card`, `render_kpi_cards`, `render_pipeline_status`, `render_quick_actions`, `render_recent_activity`, `render_progress` 등 UI 렌더링 함수들을 별도의 모듈(예: `modules/dashboard_ui.py` 또는 `dashboard_components/`)로 분리해야 합니다. 이는 `dashboard.py`의 길이를 줄이고, UI 코드와 비즈니스 로직의 분리를 명확히 하여 유지보수성을 크게 향상시킬 수 있습니다.

### 3. `dashboard.py` 백그라운드 서비스 관리 로직 분리
- **수정 난이도**: 쉬움
- **예상 효과**: `_start_scheduler_thread` 및 `_start_content_sync_thread`와 같이 백그라운드 스레드를 시작하고 관리하는 로직을 `dashboard.py`에서 별도의 모듈(예: `modules/background_services.py`)로 분리해야 합니다. `dashboard.py`는 오직 해당 모듈의 함수를 호출하여 서비스를 시작하도록 하여 `dashboard.py`의 핵심 역할(UI 렌더링 및 사용자 상호작용)에 집중하도록 해야 합니다.

### 4. `scheduler.py` 예외 처리 및 로깅 강화
- **수정 난이도**: 쉬움
- **예상 효과**: `scheduler.py`의 `run_scheduler_loop` 내 `try-except` 블록에서 `_alert_throttled`를 호출하는 것은 좋으나, `execute_due_post` 내의 일반 `Exception` 처리도 `_alert_throttled`를 활용하거나, 최소한 에러 발생 시 더 구체적인 정보(예: `entry`의 `post_no`, `scheduled_time` 등)를 포함하여 로깅하도록 개선해야 합니다. 또한 `_acquire_lock`, `_release_lock`과 같은 락 관련 함수에서도 예외 발생 시 적절한 로깅이 추가되어야 합니다.

### 5. `calculator_pipeline.py` 중복 로직 제거 및 책임 분리
- **수정 난이도**: 보통
- **예상 효과**: `run_calculator_once` 함수는 키워드 수집, 점수화, 품질 게이트/스코어 검사, 본문 생성, 발행, 재시도/HOLD 처리 등 많은 단계를 포함합니다. 각 단계를 독립적인 작은 함수로 분리하고, 특히 `_write_article`과 `_assemble`과 같이 본문 생성 및 조립 로직이 `run_calculator_once` 내에 직접 호출되는 대신, 파이프라인의 명시적인 단계 함수로 분리되어야 합니다. 또한 `_quality_signature`, `_load_legal_basis` 등 헬퍼 함수들이 클래스나 별도의 모듈로 묶여 관리되어야 합니다.

### 6. Dead Code 후보 제거
- **수정 난이도**: 쉬움
- **예상 효과**: `modules/collector/finance.py`, `modules/collector/affiliate.py`, `adapters/db/postgres_adapter.py`, `adapters/storage/s3_adapter.py`, `dashboard_backup.py`, `dashboard_backup_ui.py` 등 `❌ stub` 상태이거나 미사용으로 보이는 파일들을 삭제하거나, 향후 사용 계획이 있다면 명확하게 주석 처리하고 `README.md` 등에 문서화해야 합니다. 이는 코드베이스를 깔끔하게 유지하고 혼란을 줄입니다.

### 7. `TODO`/`FIXME` 주석 정리
- **수정 난이도**: 쉬움
- **예상 효과**: 코드 내에 산재한 `TODO` 및 `FIXME` 주석들을 검토하고, 해결하거나 별도의 이슈 트래커로 옮겨 체계적으로 관리해야 합니다. 이는 잠재적인 개선 기회를 놓치지 않고, 코드의 완성도를 높이는 데 기여합니다.

### 8. `st.session_state` 사용 패턴 개선 (Dashboard)
- **수정 난이도**: 보통
- **예상 효과**: `st.session_state`를 직접 접근하는 방식 대신, 상태 관리 로직을 캡슐화하는 헬퍼 함수나 클래스를 도입하여 `session_state`의 사용을 최소화하고 명확하게 만들어야 합니다. 예를 들어, `_set_last_action`, `_get_current_site_id`와 같은 함수를 통해 상태를 읽고 쓰는 것을 추상화할 수 있습니다. 이는 코드의 예측 가능성을 높이고 테스트를 용이하게 합니다.

### 9. `telegram_ops.notify_level` 중앙 집중화 및 개선
- **수정 난이도**: 쉬움
- **예상 효과**: `telegram_ops.notify_level`과 같은 알림 함수가 여러 모듈에서 호출되고 있지만, 알림 로직의 일관된 적용(예: 메시지 포맷, 스로틀링, 재시도)을 위해 이들을 특정 알림 서비스 계층으로 추상화하고, 모든 알림 호출이 이 추상화 계층을 통하도록 개선해야 합니다. 이는 알림 정책 변경 시 수정 범위를 최소화하고, 알림 기능의 신뢰성을 높입니다.

### 10. 긴 문자열 리터럴 분리 및 상수화
- **수정 난이도**: 쉬움
- **예상 효과**: `dashboard.py` 내의 HTML/Markdown 문자열(`render_header`, `_kpi_card`, `render_pipeline_status` 등) 및 `calculator_pipeline.py`의 `CTA_TEXT`와 같은 긴 문자열 리터럴들을 별도의 상수로 분리하거나, 마크다운 파일로 관리하여 코드의 가독성을 높이고 유지보수를 용이하게 해야 합니다.

---