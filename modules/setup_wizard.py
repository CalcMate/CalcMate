"""
modules/setup_wizard.py — 초기 설정 마법사 v12
단계:
  1. credentials.json 업로드
  2. Google Sheets/Drive 자동 생성
  3. AI API Keys 입력
  4. WordPress + 계정 설정 (secrets.yaml)
  5. 운영 설정
  6. 완료
"""
import json
import yaml
import streamlit as st
from pathlib import Path

BASE         = Path(__file__).parent.parent
CFG_PATH     = BASE / "config" / "config.yaml"
SECRETS_PATH = BASE / "config" / "secrets.yaml"
CREDS_PATH   = BASE / "credentials.json"

DEFAULT_CONFIG = {
    "OPENAI_API_KEY":   "",
    "CLAUDE_API_KEY":   "",
    "GEMINI_API_KEY":   "",
    "ORCHESTRATOR_PROVIDER": "claude",
    "PLANNER_PROVIDER":      "gemini",
    "WRITER_PROVIDER":       "openai",
    "EDITOR_PROVIDER":       "claude",
    "MODEL_ORCHESTRATOR": "claude-opus-4-5",
    "MODEL_PLANNER":      "gemini-2.5-pro",
    "MODEL_WRITER":       "gpt-4o",
    "MODEL_EDITOR":       "claude-sonnet-4-5",
    "MODEL_CLEANER":      "gpt-4o-mini",
    "EDITOR_FALLBACK_PROVIDER": "openai",
    "MODEL_EDITOR_FALLBACK":    "gpt-4o",
    "GOOGLE_SERVICE_ACCOUNT_FILE":       "credentials.json",
    "GOOGLE_SHEET_ID":                   "",
    "GOOGLE_DRIVE_ROOT_ID":              "",
    "GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID": "",
    # WordPress (미구축 시 공란 — 발행 단계에서 자동 대기). 키명은 APP_PASSWORD로 단일화.
    "WORDPRESS_URL":          "",
    "WORDPRESS_USERNAME":     "",
    "WORDPRESS_APP_PASSWORD": "",
    "RUN_MODE":    "wordpress",
    "ADSENSE_MODE": "pre",
    "DB_ADAPTER":      "sheets",
    "STORAGE_ADAPTER": "drive",
    "SQLITE_PATH":     "data/blog_auto.db",
    "DAILY_POST_COUNT":   3,
    "DAILY_AI_BUDGET":    5,
    "MONTHLY_AI_BUDGET":  100,
    "DLQ_THRESHOLD":      3,
    "MAX_RETRY_COUNT":    3,
    "DUPLICATE_THRESHOLD": 0.85,
    "RSS_SOURCE_LIST":    ["https://www.korea.kr/rss/policy.xml"],
    "RSS_MAX_ITEMS_PER_SOURCE": 20,
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID":   "",
    "LOG_LEVEL":          "INFO",
    "ENABLE_STRATEGY_ROOM": True,
    "AUTO_TOPIC_EXPANSION": False,
}

STEPS = ["credentials", "google", "api_keys", "accounts", "settings", "done"]
STEP_LABELS = {
    "credentials": "1. 서비스 계정",
    "google":      "2. Sheets/Drive",
    "api_keys":    "3. AI API Keys",
    "accounts":    "4. WP 계정",
    "settings":    "5. 운영 설정",
    "done":        "6. 완료",
}


# ── 유틸 ──────────────────────────────────────────────────────────────────────
def config_exists() -> bool:
    return CFG_PATH.exists()

def save_config(d: dict):
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(d, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def save_secrets(d: dict):
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(d, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # .gitignore 등록
    gi = BASE / ".gitignore"
    content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if "secrets.yaml" not in content:
        with open(gi, "a", encoding="utf-8") as f:
            f.write("\n# 보안 파일\nconfig/secrets.yaml\n")

def save_credentials(uploaded) -> bool:
    try:
        data = json.loads(uploaded.read())
        required = ["type", "project_id", "private_key", "client_email"]
        if not all(k in data for k in required):
            return False
        with open(CREDS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def _step_idx(step: str) -> int:
    return STEPS.index(step)

def _progress(current: str):
    cols = st.columns(len(STEPS))
    idx  = _step_idx(current)
    for i, s in enumerate(STEPS):
        if i < idx:
            cols[i].success(f"✅ {STEP_LABELS[s]}")
        elif i == idx:
            cols[i].info(f"▶ {STEP_LABELS[s]}")
        else:
            cols[i].markdown(f"⬜ {STEP_LABELS[s]}")
    st.divider()

def _next(step: str):
    st.session_state.wizard_step = STEPS[_step_idx(step) + 1]
    st.rerun()

def _prev(step: str):
    st.session_state.wizard_step = STEPS[_step_idx(step) - 1]
    st.rerun()


# ── 메인 렌더러 ───────────────────────────────────────────────────────────────
def render_wizard():
    st.set_page_config(page_title="초기 설정 마법사", page_icon="🧙", layout="centered")
    st.title("🧙 블로그자동화 v12 — 초기 설정")

    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = "credentials"
    if "wizard_cfg" not in st.session_state:
        st.session_state.wizard_cfg = dict(DEFAULT_CONFIG)
    if "wizard_secrets" not in st.session_state:
        st.session_state.wizard_secrets = {"wordpress_profiles": {}, "ai_keys": {}}
    if "creds_ok" not in st.session_state:
        st.session_state.creds_ok = CREDS_PATH.exists()

    step = st.session_state.wizard_step
    _progress(step)

    dispatch = {
        "credentials": _step_credentials,
        "google":      _step_google,
        "api_keys":    _step_api_keys,
        "accounts":    _step_accounts,
        "settings":    _step_settings,
        "done":        _step_done,
    }
    dispatch[step]()


# ── STEP 1: 서비스 계정 JSON ──────────────────────────────────────────────────
def _step_credentials():
    st.subheader("1단계: Google 서비스 계정 JSON 업로드")
    st.markdown("""
**방법**
1. [Google Cloud Console](https://console.cloud.google.com/) → IAM 및 관리자 → 서비스 계정
2. 서비스 계정 선택 → 키 → 키 추가 → JSON 다운로드
3. 아래에 업로드
    """)

    if st.session_state.creds_ok:
        st.success(f"✅ credentials.json 저장됨 — {CREDS_PATH}")

    uploaded = st.file_uploader("서비스 계정 JSON", type=["json"])
    if uploaded:
        if save_credentials(uploaded):
            st.session_state.creds_ok = True
            st.success("✅ 저장 완료")
        else:
            st.error("유효하지 않은 서비스 계정 JSON입니다.")

    if st.button("다음 →", type="primary", disabled=not st.session_state.creds_ok):
        _next("credentials")


# ── STEP 2: Google Sheets / Drive 자동 생성 ───────────────────────────────────
def _step_google():
    st.subheader("2단계: Google Sheets / Drive 자동 생성")
    cfg = st.session_state.wizard_cfg

    already = cfg.get("GOOGLE_SHEET_ID", "")
    if already:
        st.success(f"✅ 이미 생성 완료 — Sheet ID: `{already}`")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← 이전"):
                _prev("google")
        with col2:
            if st.button("다음 →", type="primary"):
                _next("google")
        return

    st.info("버튼 클릭 시 Google Drive와 Sheets를 자동으로 생성하고 탭 구조를 세팅합니다.")
    st.warning("⚠️ 서비스 계정에 **Google Sheets API** 및 **Google Drive API**가 활성화되어 있어야 합니다.")

    col_auto, col_manual = st.columns(2)

    with col_auto:
        if st.button("🚀 자동 생성", type="primary"):
            with st.spinner("생성 중..."):
                try:
                    from modules.google_provisioner import provision
                    result = provision(str(CREDS_PATH))
                    st.session_state.wizard_cfg.update({
                        "GOOGLE_SHEET_ID":                    result["sheet_id"],
                        "GOOGLE_DRIVE_ROOT_ID":               result["drive_root_id"],
                        "GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID": result["placeholder_folder_id"],
                    })
                    st.session_state.wizard_secrets["ai_keys"]["images_folder"] = result["images_folder_id"]
                    st.success(f"""
✅ 생성 완료!
- **Sheet**: [{result['sheet_url']}]({result['sheet_url']})
- **Drive 루트**: `{result['drive_root_id']}`
- **이미지 폴더**: `{result['images_folder_id']}`
- **백업 폴더**: `{result['backups_folder_id']}`
                    """)
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")
                    st.info("API 활성화 여부를 확인하거나 수동 입력 탭을 이용하세요.")

    with col_manual:
        st.markdown("**직접 ID 입력**")
        sheet_id  = st.text_input("Sheet ID", placeholder="1BxiMVs0X...")
        drive_id  = st.text_input("Drive 루트 폴더 ID", placeholder="1A2B3C...")
        ph_id     = st.text_input("Placeholder 폴더 ID", placeholder="1A2B3C...", help="선택")
        if st.button("ID 적용"):
            if sheet_id and drive_id:
                st.session_state.wizard_cfg.update({
                    "GOOGLE_SHEET_ID":                    sheet_id.strip(),
                    "GOOGLE_DRIVE_ROOT_ID":               drive_id.strip(),
                    "GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID": ph_id.strip(),
                })
                st.rerun()
            else:
                st.error("Sheet ID와 Drive 폴더 ID를 입력하세요.")

    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("← 이전"):
            _prev("google")


# ── STEP 3: AI API Keys ───────────────────────────────────────────────────────
def _step_api_keys():
    st.subheader("3단계: AI API Keys")
    cfg = st.session_state.wizard_cfg

    st.markdown("파이프라인 단계별 AI 모델 설정")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔬 리서치 (M0/M2) — Gemini 권장**")
        gemini_key = st.text_input("Gemini API Key", value=cfg.get("GEMINI_API_KEY",""),
                                   type="password", placeholder="AIzaSy...")
        model_planner = st.text_input("리서치 모델", value=cfg.get("MODEL_PLANNER","gemini-2.5-pro"))

    with col2:
        st.markdown("**✍️ 작성 (M7/M9) — GPT 권장**")
        openai_key = st.text_input("OpenAI API Key", value=cfg.get("OPENAI_API_KEY",""),
                                   type="password", placeholder="sk-...")
        model_writer = st.text_input("작성 모델", value=cfg.get("MODEL_WRITER","gpt-4o"))

    st.markdown("**🔍 검수 (M8) — Claude 권장**")
    col3, col4 = st.columns(2)
    with col3:
        claude_key = st.text_input("Claude API Key", value=cfg.get("CLAUDE_API_KEY",""),
                                   type="password", placeholder="sk-ant-...")
    with col4:
        model_editor = st.text_input("검수 모델", value=cfg.get("MODEL_EDITOR","claude-sonnet-4-5"))
        model_orch   = st.text_input("오케스트레이터 모델", value=cfg.get("MODEL_ORCHESTRATOR","claude-opus-4-5"))

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← 이전"):
            _prev("api_keys")
    with col_next:
        if st.button("다음 →", type="primary"):
            if not any([gemini_key.strip(), openai_key.strip(), claude_key.strip()]):
                st.error("최소 1개 이상의 API Key를 입력하세요.")
            else:
                st.session_state.wizard_cfg.update({
                    "GEMINI_API_KEY": gemini_key.strip(),
                    "OPENAI_API_KEY": openai_key.strip(),
                    "CLAUDE_API_KEY": claude_key.strip(),
                    "MODEL_PLANNER":      model_planner.strip(),
                    "MODEL_WRITER":       model_writer.strip(),
                    "MODEL_EDITOR":       model_editor.strip(),
                    "MODEL_ORCHESTRATOR": model_orch.strip(),
                })
                st.session_state.wizard_secrets["ai_keys"].update({
                    "gemini_flash":  gemini_key.strip(),
                    "gpt4o":         openai_key.strip(),
                    "claude_sonnet": claude_key.strip(),
                    "claude_haiku":  claude_key.strip(),
                })
                _next("api_keys")


# ── STEP 4: WordPress 계정 (secrets.yaml) ─────────────────────────────────────
def _step_accounts():
    st.subheader("4단계: WordPress 계정 설정")
    st.info("입력 내용은 Google Sheets가 아닌 로컬 **secrets.yaml**에만 저장됩니다. (보안)")

    secrets = st.session_state.wizard_secrets
    profiles = secrets.get("wordpress_profiles", {})

    # 기존 프로필 목록
    profile_names = list(profiles.keys())
    if profile_names:
        st.markdown("**등록된 프로필**")
        for pid, pdata in profiles.items():
            st.markdown(f"- `{pid}` → {pdata.get('url','')}")

    st.markdown("---")
    st.markdown("**프로필 추가**")
    col1, col2 = st.columns(2)
    with col1:
        profile_id = st.text_input("프로필 ID", placeholder="wp_lifehelp",
                                   help="sites 탭의 wordpress_profile_id에 입력할 값")
        wp_url     = st.text_input("WordPress URL", placeholder="https://yourdomain.com")
    with col2:
        wp_user = st.text_input("사용자명", placeholder="admin")
        wp_pass = st.text_input("앱 비밀번호", type="password",
                                placeholder="xxxx xxxx xxxx xxxx xxxx xxxx",
                                help="WordPress 관리자 → 사용자 → 앱 비밀번호")

    if st.button("➕ 프로필 추가"):
        if profile_id and wp_url and wp_user and wp_pass:
            profiles[profile_id.strip()] = {
                "url":          wp_url.strip(),
                "username":     wp_user.strip(),
                "app_password": wp_pass.strip(),
            }
            st.session_state.wizard_secrets["wordpress_profiles"] = profiles
            st.success(f"✅ `{profile_id}` 추가됨")
            st.rerun()
        else:
            st.error("모든 항목을 입력하세요.")

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← 이전"):
            _prev("accounts")
    with col_next:
        label = "다음 →" if profiles else "건너뛰기 →"
        if st.button(label, type="primary"):
            _next("accounts")


# ── STEP 5: 운영 설정 ─────────────────────────────────────────────────────────
def _step_settings():
    st.subheader("5단계: 운영 설정")
    cfg = st.session_state.wizard_cfg

    col1, col2 = st.columns(2)
    with col1:
        adsense_mode  = st.selectbox("애드센스 모드", ["pre","post"],
                                     index=["pre","post"].index(cfg.get("ADSENSE_MODE","pre")),
                                     help="pre=승인 전 (학술형), post=승인 후 (마케팅형)")
        daily_count   = st.number_input("하루 발행 목표", 1, 20, cfg.get("DAILY_POST_COUNT", 3))
    with col2:
        daily_budget  = st.number_input("일 AI 예산 (USD)", 1, 100, cfg.get("DAILY_AI_BUDGET", 5))
        monthly_budget= st.number_input("월 AI 예산 (USD)", 10, 1000, cfg.get("MONTHLY_AI_BUDGET", 100))
        dlq_threshold = st.number_input("DLQ 임계값", 1, 10, cfg.get("DLQ_THRESHOLD", 3))

    st.divider()
    st.subheader("텔레그램 알림 (선택)")
    col3, col4 = st.columns(2)
    with col3:
        tg_token = st.text_input("봇 토큰", value=cfg.get("TELEGRAM_BOT_TOKEN",""),
                                 type="password", placeholder="1234567890:ABC...")
    with col4:
        tg_chat  = st.text_input("Chat ID", value=cfg.get("TELEGRAM_CHAT_ID",""),
                                 placeholder="-1001234567890")

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← 이전"):
            _prev("settings")
    with col_next:
        if st.button("✅ 저장 및 완료", type="primary"):
            st.session_state.wizard_cfg.update({
                "ADSENSE_MODE":      adsense_mode,
                "DAILY_POST_COUNT":  int(daily_count),
                "DAILY_AI_BUDGET":   int(daily_budget),
                "MONTHLY_AI_BUDGET": int(monthly_budget),
                "DLQ_THRESHOLD":     int(dlq_threshold),
                "TELEGRAM_BOT_TOKEN": tg_token.strip(),
                "TELEGRAM_CHAT_ID":   tg_chat.strip(),
            })
            # 저장
            save_config(st.session_state.wizard_cfg)
            save_secrets(st.session_state.wizard_secrets)
            _next("settings")


# ── STEP 6: 완료 ──────────────────────────────────────────────────────────────
def _step_done():
    st.success("🎉 설정 완료!")
    st.balloons()
    cfg = st.session_state.wizard_cfg

    st.markdown(f"""
| 항목 | 값 |
|---|---|
| Google Sheet | `{cfg.get('GOOGLE_SHEET_ID','-')}` |
| Drive 루트 | `{cfg.get('GOOGLE_DRIVE_ROOT_ID','-')}` |
| DB Adapter | `{cfg.get('DB_ADAPTER','sheets')}` |
| 일 발행 수 | `{cfg.get('DAILY_POST_COUNT',3)}` |
| 일 AI 예산 | `${cfg.get('DAILY_AI_BUDGET',5)}` |
| secrets.yaml | `config/secrets.yaml` (로컬 보관) |
    """)

    st.info("config.yaml과 secrets.yaml이 생성되었습니다. 대시보드를 새로고침하면 자동으로 전환됩니다.")

    if st.button("🚀 대시보드 시작", type="primary"):
        for k in ["wizard_step","wizard_cfg","wizard_secrets","creds_ok"]:
            st.session_state.pop(k, None)
        st.rerun()
