"""
dashboard.py — 블로그자동화 v11.9 운영 대시보드 (오류 완치 최종본)
최신 텍스트 AI 라인업 + 🎨 이미지 생성 AI 설정 (무료/유료 완벽 분기 및 인덱스 에러 방어 탑재)
"""
import streamlit as st
import json, yaml, sys, time, os
from pathlib import Path
from datetime import datetime, date

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

# ── 마법사 우선 체크 (config.yaml 없거나 미설정이면 마법사 실행) ────────
from modules.setup_wizard import config_exists, render_wizard

def _needs_setup() -> bool:
    if not config_exists():
        return True
    try:
        cfg_path = BASE / "config" / "config.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            c = yaml.safe_load(f) or {}
    except Exception:
        return True
    has_ai_key   = any(c.get(k) for k in ("OPENAI_API_KEY", "CLAUDE_API_KEY", "GEMINI_API_KEY"))
    has_sheet_id = bool(c.get("GOOGLE_SHEET_ID"))
    return not (has_ai_key or has_sheet_id)

if _needs_setup():
    render_wizard()
    st.stop()

# ── 일반 대시보드 진입 ────────────────────────────────────────
from modules.utils import health_monitor as hc_mod
from modules.slug_generator import generate_slug

st.set_page_config(
    page_title="블로그자동화 v12 운영센터",
    page_icon="🛰️",
    layout="wide",
)

# ── SaaS 다크/글래스 테마 적용 (UI 전용, 기존 로직 무관) ──────────
def load_css(path: str = "assets/css/dashboard.css"):
    f = BASE / path
    if f.exists():
        st.markdown(f"<style>{f.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

load_css()

# ── config 로드 ────────────────────────────────────────────────
@st.cache_resource(ttl=30)
def load_cfg():
    cfg_path = BASE / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        c = yaml.safe_load(f) or {}
    # 민감정보는 config/secrets.yaml에 분리 저장 → 런타임 병합(secrets 우선)
    from modules.config_loader import merge_secrets
    c = merge_secrets(c, str(cfg_path))
    c["_root"] = str(BASE)   # scheduler/backup 경로 기준
    return c

cfg = load_cfg()

# ── 예약 발행 스케줄러 백그라운드 자동 실행 ────────────────────────
# 대시보드만 띄우고 별도 run_scheduler.bat를 안 돌리면 슬롯 예약(예: 19:35)이
# 실행되지 않던 문제 수정. @st.cache_resource 로 프로세스당 1회만 스레드 기동
# (Streamlit rerun/멀티세션에도 중복 실행 안 됨). scheduler 내부 파일 락이
# run_scheduler.bat 를 병행 실행해도 동시 발행을 막아줌.
@st.cache_resource
def _start_scheduler_thread():
    import threading
    # 프로세스당 1개 보장: 이미 살아있는 scheduler-loop가 있으면 새로 만들지 않음
    # (st.cache_resource.clear() 등으로 캐시가 비워져 재호출돼도 스레드 중복 기동 방지)
    for _t in threading.enumerate():
        if _t.name == "scheduler-loop" and _t.is_alive():
            return _t
    from modules.scheduler import run_scheduler_loop
    import main as _PIPE

    def _loop():
        try:
            run_scheduler_loop(cfg, _PIPE.resolve_publish_fn(cfg))
        except Exception as e:  # 스레드가 죽어도 대시보드는 유지
            import logging
            logging.getLogger("dashboard").error("스케줄러 스레드 종료: %s", e, exc_info=True)
            # 자동화 정지 — 운영자 즉시 인지(Sprint 1 §1-1)
            try:
                from modules import telegram_ops
                telegram_ops.notify_level(cfg, "ERROR",
                    "발행 스케줄러 스레드 종료 — 예약 발행 중단됨", e, event="error")
            except Exception:
                pass

    t = threading.Thread(target=_loop, name="scheduler-loop", daemon=True)
    t.start()
    return t

# PUBLISH_SCHEDULE.enabled 가 true 이고 운영 모드가 scheduled 일 때만 기동
if cfg.get("OPERATION_MODE", "scheduled") == "scheduled" \
        and (cfg.get("PUBLISH_SCHEDULE") or {}).get("enabled", True):
    _start_scheduler_thread()

# ── Content Sync(WP→Sheets 동기화) 백그라운드 자동 실행 ────────────
# Publish Scheduler와 완전히 분리된 독립 서비스. 대시보드가 떠 있으면 매일
# CONTENT_SYNC.run_at(기본 03:00)에 1회 동기화가 자동 실행된다(별도 스레드/락/이력).
# run_sync.py 를 Windows 작업 스케줄러로 병행 등록해도 content_sync.lock +
# 하루 1회 실행 가드가 중복 실행을 막아준다.
@st.cache_resource
def _start_content_sync_thread():
    import threading
    # 프로세스당 1개 보장(scheduler와 동일 가드)
    for _t in threading.enumerate():
        if _t.name == "content-sync-loop" and _t.is_alive():
            return _t
    from modules.content_sync import run_sync_loop

    def _loop():
        try:
            run_sync_loop(cfg)
        except Exception as e:  # 스레드가 죽어도 대시보드는 유지
            import logging
            logging.getLogger("dashboard").error("content_sync 스레드 종료: %s", e, exc_info=True)
            # 자동화 정지 — 운영자 즉시 인지(Sprint 1 §1-2)
            try:
                from modules import telegram_ops
                telegram_ops.notify_level(cfg, "ERROR",
                    "Content Sync 스레드 종료 — 동기화 중단됨", e, event="error")
            except Exception:
                pass

    t = threading.Thread(target=_loop, name="content-sync-loop", daemon=True)
    t.start()
    return t

# CONTENT_SYNC.enabled 가 true 일 때만 기동(기본 True)
if (cfg.get("CONTENT_SYNC") or {}).get("enabled", True):
    _start_content_sync_thread()

# ── 빠른 읽기 헬퍼 (운영센터 5초 로딩 목표 — 모두 로컬 파일) ──────
def _read_health_cache() -> dict:
    p = BASE / "data" / "logs" / "health_last.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

# ── 로그 tail 읽기 (전체 읽기 금지: 끝부분 바이트만) ──────────────
def _tail_lines(rel: str, n: int = 150, blk: int = 65536) -> list:
    p = BASE / rel
    if not p.exists():
        return []
    try:
        sz = p.stat().st_size
        with open(p, "rb") as f:
            f.seek(max(0, sz - blk))
            data = f.read()
        return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []

def _recent_error_lines(n: int = 5) -> list:
    lines = _tail_lines("data/logs/pipeline.log", 400)
    return [l for l in lines if "[ERROR]" in l][-n:][::-1]

# ── 캐시 레이어 (Google Sheet 조회 60초 캐시 — 메뉴 이동 가속) ──────
#   ※ 기능/출력 불변: 데이터는 최대 60초 캐시. 발행/생성 액션 후 _run_action에서 캐시 무효화.
#   2단 캐시: st.cache_data(세션 60초) + SQLite 미러(세션간/만료 후 가속, 라이브 폴백)
@st.cache_data(ttl=60, show_spinner=False)
def cached_posts() -> list:
    from modules.dashboard_cache import read
    return read(cfg, "articles", ttl=120)

@st.cache_data(ttl=60, show_spinner=False)
def cached_table(table: str) -> list:
    from modules.dashboard_cache import read
    return read(cfg, table, ttl=120)

def _run_action(label: str, fn):
    """빠른 실행 패널 공통 래퍼 — 스피너 + 결과/오류 표시. 액션 후 캐시 무효화."""
    with st.spinner(f"{label} 실행 중..."):
        try:
            res = fn()
            st.session_state["_last_action"] = (True, f"✅ {label} 완료: {res if res is not None else ''}")
        except Exception as e:
            st.session_state["_last_action"] = (False, f"❌ {label} 실패: {e}")
    try:
        st.cache_data.clear()   # 발행/생성 등으로 데이터가 바뀌었을 수 있어 갱신
        from modules.dashboard_cache import invalidate_all
        invalidate_all(cfg)     # SQLite 미러도 만료 → 다음 읽기에서 원본 재조회
    except Exception:
        pass

# ── 사이드바 ───────────────────────────────────────────────────
st.sidebar.title("🛰️ 블로그자동화 v12")
st.sidebar.markdown("**운영 방식:** `예약 발행`")
st.sidebar.markdown(f"**애드센스:** `{cfg.get('ADSENSE_MODE','pre').upper()}`")
st.sidebar.markdown(f"**일 예산:** `${cfg.get('DAILY_AI_BUDGET',5)}`")

# v12 Lite: 8개 그룹으로 통합(기존 페이지 유지, 그룹→하위 2단 네비). 계산기 생성은 App Factory 단일화.
NAV_GROUPS = {
    "🏠 Dashboard":    ["🏠 운영센터", "📊 현황"],
    "📝 Content":      ["📋 발행 목록", "🗑️ 휴지통", "📋 작업 보드", "💬 AI Workspace", "🧠 전략회의실"],
    "🧮 Calculator":   ["🏭 App Factory", "🧮 계산기 관리"],
    "📅 Scheduler":    ["📅 오늘 발행 일정", "📊 AI Pipeline", "🌐 사이트 관리"],
    "💰 Revenue":      ["💰 비용 모니터"],
    "📡 Logs":         ["⚠️ 오류 로그", "📡 실시간 로그", "🏥 헬스체크"],
    "🔧 Settings":     ["🔧 설정"],
    "🤖 AI Assistant": ["🤖 AI Assistant"],
}
_group = st.sidebar.radio("메뉴", list(NAV_GROUPS.keys()), key="nav_group")
_subs = NAV_GROUPS[_group]
if len(_subs) > 1:
    tab = st.sidebar.radio(_group, _subs, key=f"sub_{_group}")
else:
    tab = _subs[0]

# ══════════════════════════════════════════════════════════════
# 탭: 🏠 운영센터 (홈) — 5초 안에 전체 상태 파악 + 빠른 실행
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# SaaS Dashboard Home 컴포넌트 (UI 전용 — 로직/Repository/Adapter/Pipeline 무관)
# ══════════════════════════════════════════════════════════════
def render_header():
    st.markdown(
        '<div class="sm-card" style="margin-bottom:16px">'
        '<div style="font-size:25px;font-weight:800;letter-spacing:-.5px;'
        'background:linear-gradient(90deg,#a5b4fc,#67e8f9);-webkit-background-clip:text;'
        'background-clip:text;-webkit-text-fill-color:transparent">CalcMate OS</div>'
        '<div class="sm-dim" style="font-size:13px;margin-top:3px">AI Content Operating System</div>'
        '</div>', unsafe_allow_html=True)

def _kpi_card(col, icon, label, value, sub=""):
    col.markdown(
        f'<div class="sm-kpi"><div class="ic">{icon}</div>'
        f'<div class="lab">{label}</div><div class="val">{value}</div>'
        f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)

def _list_sites_safe():
    """site_wizard.list_sites 안전 호출(읽기 전용). 실패 시 빈 목록."""
    try:
        from modules import site_wizard as SW
        return SW.list_sites(cfg) or []
    except Exception:
        return []

def _derive_platforms(has_calc: bool):
    """현재 설정 기준 활성 Platform 파생(읽기 전용 표시용)."""
    p = []
    if cfg.get("RUN_MODE") == "wordpress" or cfg.get("WORDPRESS_URL"):
        p.append("WordPress")
    if has_calc:
        p.append("Calculator")
    return p or ["—"]

def _derive_features():
    """현재 설정 기준 활성 공통 Feature 파생(표시용)."""
    f = ["Scheduler", "AI Assistant", "Cost Manager", "Retry Queue"]
    if cfg.get("TELEGRAM_BOT_TOKEN") and cfg.get("TELEGRAM_CHAT_ID"):
        f.append("Telegram")
    if cfg.get("ENABLE_STRATEGY_ROOM"):
        f.append("Strategy")
    return f

def render_current_site_card():
    """최상단 고정 '현재 Site' 카드 + Site 변경 셀렉터(읽기/세션상태만)."""
    sites = _list_sites_safe()
    with st.container(border=True):
        left, right = st.columns([2.2, 1])
        if sites:
            labels = [(s.get("site_name") or s.get("site_id") or "(이름없음)") for s in sites]
            ids = [s.get("site_id", "") for s in sites]
            cur = st.session_state.get("current_site_id", ids[0])
            idx = ids.index(cur) if cur in ids else 0
            with right:
                pick = st.selectbox("Site 변경", labels, index=idx, key="cur_site_pick")
            sel_i = labels.index(pick)
            st.session_state["current_site_id"] = ids[sel_i]
            site = sites[sel_i]
            name = site.get("site_name") or site.get("site_id") or "CalcMate"
        else:
            st.session_state["current_site_id"] = ""
            site, name = {}, "CalcMate"
            with right:
                st.caption("등록 사이트 없음 — 기본 사이트")
        try:
            has_calc = len(cached_table("calculators")) > 0
        except Exception:
            has_calc = False
        with left:
            st.markdown(f"#### 🏢 현재 Site: **{name}**")
            st.markdown(f"**Platform:** {'  +  '.join(_derive_platforms(has_calc))}")
            st.caption("활성 Feature: " + " / ".join(_derive_features()))

def render_kpi_cards():
    # 1) 시스템 상태 (health_last.json)
    h = _read_health_cache()
    crit = [v for v in h.values() if isinstance(v, dict) and v.get("level") == "CRITICAL"]
    ok_c = sum(1 for v in crit if v.get("status") == "OK")
    sys_val = "정상" if crit and ok_c == len(crit) else ("주의" if crit else "—")
    sys_sub = f"{ok_c}/{len(crit)} OK" if crit else "헬스 미실행"
    # pipeline 상태
    try:
        from modules.pipeline_status import get_pipeline_state
        ps = get_pipeline_state(cfg)
    except Exception:
        ps = {"stages": [], "cost_today": 0}
    stages = ps.get("stages", [])
    running = next((s for s in stages if s.get("status") == "running"), None)
    done = [s for s in stages if s.get("status") == "completed"]
    # 2) 현재 Workflow 단계
    if running:        wf = running.get("name", "-")
    elif ps.get("finished"): wf = "완료"
    elif done:         wf = done[-1].get("name", "-")
    else:              wf = "대기"
    # 3) 현재 AI 작업(활성 모델)
    ai = running.get("model", "-") if running else "대기"
    # 4) 오늘 운영 현황(발행/생성)
    try:
        from modules import scheduler as SCH
        pub = SCH.summarize(SCH.load_schedule(cfg)).get("completed", 0)
    except Exception:
        pub = "—"
    try:
        gen = len(cached_posts())
    except Exception:
        gen = "—"
    # 5) 오늘 AI 비용 (Cost Manager / BudgetTracker)
    try:
        from modules import cost_manager as CM
        cs = CM.status(cfg)
        cost_val, cost_sub = f"${cs['used']:.2f}", f"/ ${cs['limit']} ({cs['pct']:.0f}%)"
    except Exception:
        cost_val, cost_sub = f"${ps.get('cost_today', 0)}", "예산 정보"
    cols = st.columns(5)
    _kpi_card(cols[0], "🩺", "시스템", sys_val, sys_sub)
    _kpi_card(cols[1], "⛓️", "Workflow", wf, "현재 단계")
    _kpi_card(cols[2], "🤖", "AI 작업", ai, "활성 모델")
    _kpi_card(cols[3], "📦", "오늘", f"{pub}건", f"발행 / 생성 {gen}")
    _kpi_card(cols[4], "💰", "AI 비용", cost_val, cost_sub)

def render_pipeline_status():
    # 라이브 단계 상태(블로그 파이프라인) — pipeline_status.py 기준
    stage_status = {}
    try:
        from modules.pipeline_status import get_pipeline_state
        for s in get_pipeline_state(cfg)["stages"]:
            stage_status[s["name"]] = s["status"]
    except Exception:
        pass
    def _stat(keys):
        for nm, stt in stage_status.items():
            if any(k in nm for k in keys):
                return stt
        return "pending"
    cls = {"completed": "done", "running": "run", "error": "run", "pending": ""}
    # main.py STEP 순서 기준(추측 아님): 수집→정제→중복→전략→SEO→작성→검수→이미지→발행→기록
    blog = [("📥", "수집", ["수집"]), ("🧹", "정제", ["정제", "표준"]),
            ("🔁", "중복검사", ["중복", "유사"]), ("🧠", "전략", ["전략", "리서치"]),
            ("🔎", "SEO기획", ["SEO", "기획", "리서치"]), ("✍", "작성", ["작성"]),
            ("🔍", "검수", ["검수"]), ("🖼", "이미지", ["이미지"]),
            ("🚀", "발행", ["발행"]), ("🗂", "기록", ["기록", "DB"])]
    calc = [("🔑", "키워드", []), ("🔎", "SEO", []), ("❓", "FAQ", []),
            ("📝", "본문", []), ("🤖", "Reviewer", []), ("🧩", "HTML", []), ("🌐", "배포", [])]
    def _row(title, steps, live):
        cards = "".join(
            f'<div class="sm-step {cls.get(_stat(keys), "") if live else ""}">'
            f'<div class="s-ic">{ic}</div><div class="s-nm">{nm}</div></div>'
            for ic, nm, keys in steps)
        return f'<h4 style="margin:8px 0 8px;font-size:13px" class="sm-dim">{title}</h4><div class="sm-pipe">{cards}</div>'
    st.markdown(
        '<div class="sm-card"><h3 style="margin:0 0 8px">⛓️ Workflow</h3>'
        + _row("📰 블로그 파이프라인 (현재 단계 강조)", blog, True)
        + _row("🧮 계산기 파이프라인", calc, False)
        + '</div>', unsafe_allow_html=True)

def _resolve_run_site():
    """선택된 Site와 활성 platforms 반환. (site|None, platforms[list])"""
    site, platforms = None, []
    try:
        _sid = st.session_state.get("current_site_id", "")
        for s in (cached_table("sites") or []):
            if s.get("site_id") == _sid:
                site = s; break
    except Exception:
        site = None
    if site:
        try:
            platforms = json.loads(site.get("platforms") or "[]")
        except Exception:
            platforms = []
    return site, platforms

def render_quick_actions():
    import main as PIPE
    def _run_blog():
        return PIPE.run_once(cfg)
    def _run_calc():
        from modules.calculator_pipeline import run_calculator_once
        return run_calculator_once(cfg, max_count=1)
    def _run_seq():
        _run_calc(); _run_blog(); return "계산기→블로그 순차 완료"

    with st.container(border=True):
        st.markdown("**⚡ 실행**")
        site, platforms = _resolve_run_site()
        has_wp, has_calc = ("WordPress" in platforms), ("Calculator" in platforms)
        sname = site.get("site_name") if site else "기본(CalcMate)"
        if not platforms:
            st.caption(f"대상: **{sname}** · Platform 미설정 → 기본 블로그 파이프라인 실행")
        else:
            st.caption(f"대상: **{sname}** · Platform: {' + '.join(platforms)}")
        # 둘 다 활성 시 실행 방식 선택
        order = None
        if has_wp and has_calc:
            order = st.radio("실행 방식", ["순차(Calculator→WordPress)", "Calculator만", "WordPress만"],
                             key="qa_order", horizontal=True)
        # ── 통합 실행 버튼: 활성 Platform 기반 Pipeline 자동 결정 ──
        if st.button("▶ 실행", type="primary", use_container_width=True, key="qa_run"):
            if has_wp and has_calc:
                if order == "Calculator만":
                    _run_action("계산기 실행", _run_calc)
                elif order == "WordPress만":
                    _run_action("블로그 파이프라인 실행", _run_blog)
                else:
                    _run_action("순차 실행(Calc→WP)", _run_seq)
            elif has_calc:
                _run_action("계산기 실행", _run_calc)
            else:
                _run_action("블로그 파이프라인 실행", _run_blog)  # WP-only 또는 미설정 fallback
            st.rerun()
        # ── 고급 실행(수동) — 기존 개별 버튼 보존 ──
        with st.expander("🔧 고급 실행(수동)"):
            if st.button("▶ 파이프라인 실행(전량)", use_container_width=True, key="qa_pipe"):
                _run_action("파이프라인 실행", lambda: PIPE.run_once(cfg)); st.rerun()
            if st.button("🧮 계산기 생성", use_container_width=True, key="qa_calc"):
                from modules.calculator_pipeline import run_calculator_once
                _run_action("계산기 글 생성", lambda: run_calculator_once(cfg, max_count=1)); st.rerun()
            if st.button("📝 글 생성(1건)", use_container_width=True, key="qa_post"):
                _run_action("글 생성(1건)", lambda: PIPE.run_once(cfg, max_count=1)); st.rerun()
            if st.button("🌐 워드프레스 발행", use_container_width=True, key="qa_wp"):
                from modules import scheduler as SCH
                _run_action("즉시 발행", lambda: SCH.immediate_publish(cfg, PIPE.resolve_publish_fn(cfg), "pull")[1]); st.rerun()

def render_recent_activity():
    with st.container(border=True):
        st.markdown("**🕒 Recent Activity**")
        lines = _tail_lines("data/logs/pipeline.log", 20)[::-1]
        if lines:
            st.code("\n".join(lines), language="text")
        else:
            st.caption("No Activity")

def render_progress():
    """진행 현황: 오늘 일정 진행률 + Retry/실패/진행중/ETA (읽기 전용)."""
    try:
        from modules import scheduler as SCH
        sm = SCH.summarize(SCH.load_schedule(cfg))
    except Exception:
        sm = {}
    try:
        from modules.retry_queue import list_pending
        retry_n = len(list_pending())
    except Exception:
        retry_n = "—"
    total = sm.get("total", 0) or 0
    comp = sm.get("completed", 0) or 0
    pct = int(comp / total * 100) if total else 0
    with st.container(border=True):
        st.markdown("**📈 진행 현황**")
        st.progress((pct / 100) if total else 0.0, text=f"오늘 일정 {comp}/{total} ({pct}%)")
        m = st.columns(4)
        m[0].metric("Retry 대기", retry_n)
        m[1].metric("실패", sm.get("failed", 0))
        m[2].metric("진행중", sm.get("running", 0))
        m[3].metric("다음 발행(ETA)", sm.get("next") or "-")

def render_dashboard_home():
    a = st.session_state.pop("_last_action", None)
    if a:
        (st.success if a[0] else st.error)(a[1])
    render_header()
    render_current_site_card()        # 최상단 고정 '현재 Site' 카드 + 셀렉터
    render_kpi_cards()                # 운영 현황 5카드
    st.markdown("<br>", unsafe_allow_html=True)
    render_pipeline_status()          # 블로그 + 계산기 Workflow
    st.markdown("<br>", unsafe_allow_html=True)
    render_progress()                 # 진행 현황 패널
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.5])
    with c1:
        render_quick_actions()
    with c2:
        render_recent_activity()

if tab == "🏠 운영센터":
    render_dashboard_home()

elif tab == "📋 작업 보드":
    st.title("📋 작업 현황 보드")
    st.caption("마스터_DB 상태값 기준 칸반. (수집중→작성중→검수중→발행대기→발행완료 / 오류)")
    try:
        posts = cached_posts()
    except Exception as e:
        posts = []
        st.error(f"데이터 로드 실패(시트 권한 확인): {e}")
    KANBAN = [
        ("🟡 수집중", ["대기", "진행중"]),
        ("🔵 작성중", ["작성중"]),
        ("🟠 검수중", ["검수대기"]),
        ("⏳ 발행대기", ["보류", "복구대기", "재처리대기"]),
        ("🟢 발행완료", ["발행완료"]),
        ("🔴 오류", ["작성오류", "이미지오류", "발행실패", "만료"]),
    ]
    cols = st.columns(len(KANBAN))
    for col, (title, states) in zip(cols, KANBAN):
        items = [p for p in posts if p.get("상태값") in states]
        col.markdown(f"**{title}**")
        col.metric("건수", len(items))
        for p in items[:15]:
            t = str(p.get("최종추천제목") or p.get("정책명") or "(제목없음)")
            col.caption("• " + (t[:22] + ("…" if len(t) > 22 else "")))

# ══════════════════════════════════════════════════════════════
# 백그라운드 탭 로직 (현황, 목록, 오류, 비용)
# ══════════════════════════════════════════════════════════════
elif tab == "📊 현황":
    st.title("📊 실시간 상태 현황")
    try:
        posts = cached_posts()
        status_counts = {}
        for p in posts:
            s = p.get("상태값", "알 수 없음")
            status_counts[s] = status_counts.get(s, 0) + 1

        cols = st.columns(6)
        state_map = [("대기", "🟡"), ("작성중", "🔵"), ("검수대기", "🟠"), ("발행완료", "🟢"), ("이미지오류", "🔴"), ("재처리대기", "⚫")]
        for i, (state, icon) in enumerate(state_map):
            cols[i].metric(f"{icon} {state}", status_counts.get(state, 0))

        st.divider()
        daily_goal = cfg.get("DAILY_POST_COUNT", 3)
        today_str = date.today().isoformat()
        today_published = sum(1 for p in posts if p.get("상태값") in ("발행완료", "검수대기") and str(p.get("발행일시", "")).startswith(today_str))
        st.subheader(f"오늘 발행: {today_published}/{daily_goal}")
        st.progress(min(today_published / max(daily_goal, 1), 1.0))
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")

elif tab == "📋 발행 목록":
    st.title("📋 최근 발행 목록")
    # WordPress REST API 직접 호출 금지 — 수정은 publisher.update_post()만 사용(계층 분리).
    from modules import publisher as PUB
    from repositories.article_repository import ArticleRepository
    from adapters.db.factory import get_db_adapter
    # TODO(본문 편집 UI): 현재 WP 본문을 불러와 미리보기→수정→저장하는 흐름 +
    # 긴 본문 가독성 개선(리치 에디터/높이 조절). 이번 범위 제외.
    try:
        posts = cached_posts()
        published = [p for p in posts if p.get("상태값") in ("발행완료", "검수대기", "수정됨")]
        published.sort(key=lambda x: x.get("발행일시", ""), reverse=True)
        for p in published[:20]:
            pid = p.get("ID", "")
            wp_id = str(p.get("wp_post_id", "") or "").strip()
            with st.expander(f"✅ {p.get('최종추천제목','(제목없음)')} — {p.get('발행일시','')}"):
                st.write(f"**URL:** {p.get('발행 URL', '')}")
                st.write(f"**상태:** {p.get('상태값')}")
                if not wp_id:
                    st.caption("✏️ 수정 기능 미지원 (wp_post_id 없음 — 1차 이전 발행 글)")
                else:
                    with st.expander("✏️ 수정"):
                        e_title = st.text_input("제목", value=p.get("최종추천제목", ""), key=f"ed_t_{pid}")
                        e_excerpt = st.text_input("요약(excerpt)", value=p.get("메타설명", ""), key=f"ed_e_{pid}")
                        e_content = st.text_area(
                            "본문 교체", value="", key=f"ed_c_{pid}",
                            help="입력하면 WordPress 본문 전체를 이 내용으로 교체. 비워두면 본문은 수정하지 않음(전송 안 함).")
                        if st.button("💾 저장 (WordPress 반영)", key=f"ed_save_{pid}"):
                            # content: 비워두면 None(미전송=본문 유지). excerpt/title은 현재값 그대로 전송.
                            content_arg = e_content if e_content.strip() else None
                            res = PUB.update_post(cfg, wp_id, title=e_title,
                                                  content=content_arg, excerpt=e_excerpt)
                            if res.get("success"):
                                # WordPress 성공 후에만 로컬 DB/history 갱신
                                art_repo = ArticleRepository(get_db_adapter(cfg))
                                try:
                                    art_repo.update_status(pid, "수정됨")
                                    art_repo.append_history(pid, "update", {
                                        "wp_post_id": res.get("wp_post_id", ""),
                                        "modified": res.get("modified", ""),
                                        "operator": "dashboard"})
                                except Exception as _e:
                                    st.warning(f"WordPress 수정은 성공했으나 로컬 기록 일부 실패: {_e}")
                                st.success(f"수정 완료 — modified={res.get('modified','')}")
                                st.rerun()
                            else:
                                # 실패 시 로컬 DB/history 절대 미변경
                                st.error(f"수정 실패 (로컬 미변경): {res.get('error','')}")

                    # 🗑️ 삭제(휴지통 이동) — 2단계 확인. publisher만 호출, WP REST 직접호출 없음.
                    st.markdown("---")
                    if not st.session_state.get(f"del_confirm_{pid}"):
                        if st.button("🗑️ 삭제 (휴지통 이동)", key=f"del_btn_{pid}"):
                            # 확인 단계 진입 전 get_post 재조회(이미 삭제/권한/제목 확인)
                            check = PUB.get_post(cfg, wp_id)
                            if check.get("success"):
                                st.session_state[f"del_confirm_{pid}"] = True
                                st.session_state[f"del_check_{pid}"] = check
                                st.rerun()
                            else:
                                err = check.get("error", "")
                                msg = {
                                    "not_found": "이미 삭제되었거나 존재하지 않는 글입니다.",
                                    "authentication_failed": "WordPress 인증 실패 — 자격증명을 확인하세요.",
                                    "permission_denied": "WordPress 권한 부족 — 삭제 권한이 없습니다.",
                                }.get(err, f"조회 실패: {err}")
                                st.error(msg)  # 확인 단계 취소, 로컬 미변경
                    else:
                        check = st.session_state.get(f"del_check_{pid}", {})
                        st.warning("⚠️ 이 글을 WordPress 휴지통으로 이동합니다.")
                        st.write(f"- **제목:** {check.get('title','')}")
                        st.write(f"- **URL:** {check.get('link','')}")
                        st.write(f"- **WP 상태:** {check.get('status','')}")
                        conf = st.text_input('삭제하려면 "DELETE" 를 입력하세요', key=f"del_txt_{pid}")
                        dc = st.columns(2)
                        if dc[0].button("실행", key=f"del_exec_{pid}", type="primary",
                                        disabled=(conf != "DELETE")):
                            res = PUB.delete_post(cfg, wp_id)  # force=False → 휴지통
                            if res.get("success"):
                                art_repo = ArticleRepository(get_db_adapter(cfg))
                                try:
                                    art_repo.update_status(pid, "휴지통")
                                    art_repo.append_history(pid, "trash", {
                                        "wp_post_id": wp_id,
                                        "title": check.get("title", ""),
                                        "operator": "dashboard",
                                        "wp_status": res.get("wp_status", ""),
                                        "force": False})
                                except Exception as _e:
                                    st.warning(f"WordPress 삭제는 성공했으나 로컬 기록 일부 실패: {_e}")
                                st.session_state.pop(f"del_confirm_{pid}", None)
                                st.session_state.pop(f"del_check_{pid}", None)
                                st.success("🗑️ 휴지통으로 이동 완료")
                                st.rerun()
                            else:
                                # 실패 시 로컬 DB/history 절대 미변경
                                st.error(f"삭제 실패 (로컬 미변경): {res.get('error','')}")
                        if dc[1].button("취소", key=f"del_cancel_{pid}"):
                            st.session_state.pop(f"del_confirm_{pid}", None)
                            st.session_state.pop(f"del_check_{pid}", None)
                            st.rerun()
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")

elif tab == "🗑️ 휴지통":
    st.title("🗑️ 휴지통")
    st.caption("WordPress 휴지통(trash)으로 이동된 글. ♻️ 복원하면 발행(publish)으로 되돌립니다.")
    # WP REST 직접호출 금지 — 복원은 publisher.restore_post()만 사용(계층 분리).
    from modules import publisher as PUB
    from repositories.article_repository import ArticleRepository
    from adapters.db.factory import get_db_adapter
    try:
        posts = cached_posts()
        trashed = [p for p in posts if p.get("상태값") == "휴지통"]
        trashed.sort(key=lambda x: x.get("발행일시", ""), reverse=True)
        if not trashed:
            st.info("휴지통이 비어 있습니다.")
        for p in trashed[:30]:
            pid = p.get("ID", "")
            wp_id = str(p.get("wp_post_id", "") or "").strip()
            with st.expander(f"🗑️ {p.get('최종추천제목','(제목없음)')} — {p.get('발행일시','')}"):
                st.write(f"**URL:** {p.get('발행 URL', '')}")
                st.write(f"**로컬 상태:** {p.get('상태값')}")
                if not wp_id:
                    st.caption("♻️ 복원 미지원 (wp_post_id 없음)")
                elif st.button("♻️ 복원", key=f"restore_btn_{pid}"):
                    result = PUB.restore_post(cfg, wp_id)   # 내부 get_post 재조회 포함
                    if result.get("success"):
                        # already_restored여도 로컬이 발행완료가 아니면 동기화(WP-로컬 불일치 해소)
                        if result.get("already_restored") and p.get("상태값") == "발행완료":
                            st.info("이미 복원되어 있습니다.")
                        else:
                            art_repo = ArticleRepository(get_db_adapter(cfg))
                            try:
                                art_repo.update_status(pid, "발행완료")
                                art_repo.append_history(pid, "restore", {
                                    "wp_post_id": wp_id,
                                    "title": result.get("title", ""),
                                    "operator": "dashboard",
                                    "wp_status": result.get("wp_status", ""),
                                    "restored_from": "휴지통",
                                    "already_restored": bool(result.get("already_restored")),
                                })
                            except Exception as _e:
                                st.warning(f"WordPress 복원은 성공했으나 로컬 기록 일부 실패: {_e}")
                            st.success("♻️ 복원되었습니다" +
                                       (" (WP는 이미 발행 상태였음 — 로컬 동기화)" if result.get("already_restored") else ""))
                        st.rerun()
                    else:
                        # 실패 시 로컬 미변경
                        error_map = {
                            "not_found": "WP에서 글을 찾을 수 없습니다.",
                            "authentication_failed": "WordPress 인증 실패입니다.",
                            "permission_denied": "WordPress 권한이 부족합니다.",
                        }
                        err = result.get("error", "")
                        st.error(error_map.get(err, f"복원 실패 (로컬 미변경): {err}"))
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")

elif tab == "⚠️ 오류 로그":
    st.title("⚠️ 최근 오류 로그")
    st.caption("운영로그(logs) 실패 + 계산기(articles) 품질보류/REWRITE를 함께 조회합니다.")
    try:
        rows = cached_table("logs")
        # 가동결과에 '오류' 포함되거나 실패모듈이 있는 행
        errors = [r for r in rows
                  if "오류" in str(r.get("가동결과", "")) or str(r.get("실패모듈", "")).strip()]
        errors = errors[-20:][::-1]  # 최근 20건, 최신 우선

        # 계산기 파이프라인 실패는 logs가 아닌 articles에 기록됨 → 함께 표시(표시 전용).
        # 활성 실패 상태는 '품질보류' 하나뿐(REWRITE/legal 미검증 홀드 모두 이 상태값). quality_status는
        # 발행완료·재처리완료·삭제됨 행에도 'REWRITE'가 잔존해 오탐하므로, 상태값으로만 판정한다.
        def _is_calc_fail(r):
            return str(r.get("상태값", "")).strip() == "품질보류"
        try:
            calc_fails = [r for r in cached_table("articles") if _is_calc_fail(r)][-20:][::-1]
        except Exception:
            calc_fails = []

        st.metric("최근 오류 건수", len(errors) + len(calc_fails))
        import pandas as pd

        st.subheader("운영로그(logs) 오류")
        if errors:
            cols = ["실행일시", "마스터ID", "대상정책명", "실패모듈", "오류내용"]
            df = pd.DataFrame(errors)
            show = [c for c in cols if c in df.columns]
            st.dataframe(df[show] if show else df, use_container_width=True)
        else:
            st.caption("운영로그 오류 없음")

        st.subheader("계산기 품질보류 / REWRITE (articles)")
        if calc_fails:
            cols = ["발행일시", "최종추천제목", "정책명", "상태값", "quality_status", "quality_failed_rules"]
            df = pd.DataFrame(calc_fails)
            show = [c for c in cols if c in df.columns]
            st.dataframe(df[show] if show else df, use_container_width=True)
        else:
            st.caption("계산기 품질보류 없음")

        if not errors and not calc_fails:
            st.success("최근 오류 없음 ✅")
    except Exception as e:
        st.error(f"로그 로드 오류: {e}")
        st.caption("Google Sheet 권한(서비스 계정 공유) 또는 네트워크를 확인하세요.")

elif tab == "💰 비용 모니터":
    st.title("💰 AI 사용 비용 모니터")
    st.caption("data/logs/budget.json 기반 — 실제 호출 시 누적 기록됩니다.")
    try:
        from modules.logger import BudgetTracker
        bt = BudgetTracker(cfg)
        bs = bt.check_budget()

        c1, c2, c3 = st.columns(3)
        c1.metric("오늘 비용", f"${bs['daily_used']:.4f}", f"한도 ${bs['daily_limit']}")
        c2.metric("이번달 비용", f"${bs['monthly_used']:.4f}", f"한도 ${bs['monthly_limit']}")
        c3.metric("누적 비용(전체월)", f"${bt.get_total_cost():.4f}")
        # 예산 진행률
        st.progress(min(bs['daily_used'] / max(bs['daily_limit'], 0.0001), 1.0),
                    text=f"일 예산 사용률 {bs['daily_used']/max(bs['daily_limit'],0.0001)*100:.1f}%")
        if bs["daily_exceeded"]:
            st.error("⛔ 일 예산 초과 — 파이프라인이 자동 중단됩니다.")
        if bs["monthly_exceeded"]:
            st.error("⛔ 월 예산 초과 — 파이프라인이 자동 중단됩니다.")

        st.divider()
        colA, colB = st.columns(2)
        with colA:
            st.subheader("Provider별 (이번달)")
            prov = bt.get_provider_breakdown("monthly")
            prov = {k: v for k, v in prov.items() if v}
            if prov:
                import pandas as pd
                st.bar_chart(pd.Series(prov, name="USD"))
                st.dataframe(pd.DataFrame(
                    [{"Provider": k, "비용($)": v} for k, v in prov.items()]),
                    use_container_width=True, hide_index=True)
            else:
                st.caption("이번달 집계 없음")
        with colB:
            st.subheader("모델별 (이번달)")
            models = bt.get_model_breakdown("monthly")
            if models:
                import pandas as pd
                st.dataframe(pd.DataFrame(
                    [{"모델": k, "비용($)": v} for k, v in sorted(models.items(), key=lambda x: -x[1])]),
                    use_container_width=True, hide_index=True)
            else:
                st.caption("이번달 집계 없음")

        st.divider()
        t1, t2 = st.columns(2)
        t1.metric("오늘 토큰", f"{int(bt.get_today_tokens()):,}")
        st.caption("※ 비용은 모델별 입력/출력 단가표 기반 추정치입니다(blended 적용 구간 존재).")
    except Exception as e:
        st.error(f"비용 데이터 로드 오류: {e}")

    st.divider()
    # ── Cost Manager (80% 경고 / 100% 자동 일시정지 / 익일 재개) ──
    st.subheader("🛡️ Cost Manager")
    try:
        from modules import cost_manager as CM
        cs = CM.status(cfg)
        paused = CM.is_paused(cfg)
        cc = st.columns(3)
        cc[0].metric("일 예산 사용률", f"{cs['pct']:.0f}%")
        cc[1].metric("상태", "⛔ 일시정지" if paused else "🟢 정상")
        cc[2].metric("정책", "80%경고 / 100%정지")
        if paused:
            st.error("일 예산 한도 도달로 자동 일시정지됨(익일 자동 재개).")
            if st.button("▶ 지금 수동 재개", key="cm_resume"):
                CM.resume(cfg); st.success("재개됨"); st.rerun()
    except Exception as e:
        st.caption(f"Cost Manager 로드 실패: {e}")

    st.divider()
    # ── Retry Queue (WordPress 발행 실패분 재발행) ──
    st.subheader("🔁 발행 재시도 큐")
    try:
        from modules import retry_queue as RQ
        pend = RQ.list_pending()
        if not pend:
            st.caption("재발행 대기 없음")
        for it in pend[:20]:
            with st.container(border=True):
                st.markdown(f"**{it['seo'].get('seo_title','(제목없음)')}** · "
                            f"<span class='sm-dim'>{it.get('created_at','')[:16]} · {it.get('error','')[:60]}</span>",
                            unsafe_allow_html=True)
                rc = st.columns(2)
                if rc[0].button("🔁 재발행", key=f"rq_{it['id']}"):
                    ok, msg = RQ.retry(cfg, it["id"])
                    (st.success if ok else st.error)(msg); st.rerun()
                if rc[1].button("🗑 제거", key=f"rqd_{it['id']}"):
                    RQ.remove(it["id"]); st.rerun()
    except Exception as e:
        st.caption(f"Retry Queue 로드 실패: {e}")

# ══════════════════════════════════════════════════════════════
# 탭: 📅 오늘 발행 일정 (슬롯 스케줄러)
# ══════════════════════════════════════════════════════════════
elif tab == "📅 오늘 발행 일정":
    st.title("📅 오늘 발행 일정")
    from modules import scheduler as SCH
    from datetime import datetime as _dt

    def _parse_t(s, fallback="09:00"):
        try:
            return _dt.strptime(s, "%H:%M").time()
        except Exception:
            return _dt.strptime(fallback, "%H:%M").time()

    # ── 스케줄러 컨트롤 패널 (상태 + 원스톱 버튼) ──
    from modules import cost_manager as CM
    import threading as _th
    import main as PIPE
    today = date.today().isoformat()
    _sc = SCH.load_schedule(cfg)
    _summ = (SCH.summarize(_sc) if _sc and _sc.get("date") == today
             else {"completed": 0, "pending": 0, "failed": 0, "next": None})
    _enabled = bool((cfg.get("PUBLISH_SCHEDULE") or {}).get("enabled", True))
    _paused = CM.is_paused(cfg)
    _alive = any(t.name == "scheduler-loop" and t.is_alive() for t in _th.enumerate())
    _running = _alive and _enabled and not _paused
    with st.container(border=True):
        s1, s2, s3 = st.columns(3)
        s1.markdown("**상태**: " + ("🟢 Running" if _running else ("🔴 Paused(중지)" if _paused else "🔴 정지")))
        s2.markdown(f"**enabled**: {'on' if _enabled else 'off'} · 스레드 {'live' if _alive else 'dead'}")
        s3.markdown(f"**다음 실행**: {_summ.get('next') or '-'}")
        st.caption(f"오늘 요약 — 완료 {_summ['completed']} · 대기 {_summ['pending']} · 실패 {_summ['failed']}")
        bc = st.columns(6)
        if bc[0].button("🆕 생성", key="ctl_gen", use_container_width=True):
            SCH.generate_today_schedule(cfg); st.rerun()
        if bc[1].button("♻️ 재생성", key="ctl_regen", use_container_width=True):
            SCH.reset_today(cfg); SCH.generate_today_schedule(cfg); st.rerun()
        if bc[2].button("🗑️ 초기화", key="ctl_reset", use_container_width=True):
            SCH.reset_today(cfg); st.rerun()
        if bc[3].button("⚡ 즉시발행", key="ctl_now", use_container_width=True):
            st.session_state["_sched_confirm"] = True
        if bc[4].button("⏸️ 중지", key="ctl_pause", disabled=_paused, use_container_width=True):
            CM.pause(cfg); st.rerun()
        if bc[5].button("▶️ 재개", key="ctl_resume", disabled=not _paused, use_container_width=True):
            CM.resume(cfg); st.rerun()

    # ── Content Sync 수동 트리거 (WordPress ↔ Sheets 상태 동기화) ──
    # run_sync_once 100% 재사용. content_sync.lock으로 자동 03:00 실행과 상호배제.
    with st.expander("🔄 Content Sync (WordPress ↔ Sheets 상태 동기화 · 자동 03:00 + 수동)"):
        st.caption("발행글의 WP 상태를 조회해 시트 sync_flag 갱신(WP_DELETED/URL_CHANGED/ORPHAN). "
                   "매일 03:00 자동 실행 + 여기서 즉시 수동 실행.")
        _scm = st.radio("범위", ["recent", "full"], horizontal=True, key="sync_mode",
                        help="recent=최근 30일 발행분 / full=전체 스캔")
        if st.button("🔄 Sync Now", key="sync_now", type="primary"):
            from modules import content_sync as CS
            import time as _time
            if not CS._acquire_lock(cfg):
                st.warning("다른 동기화가 진행 중입니다(자동 03:00 또는 다른 창). 잠시 후 재시도하세요.")
            else:
                res = None
                try:
                    _t0 = _time.time()
                    with st.spinner("WordPress ↔ Sheets 동기화 중..."):
                        res = CS.run_sync_once(cfg, mode=_scm)
                    _el = round(_time.time() - _t0, 1)
                finally:
                    CS._release_lock(cfg)
                if not res or not res.get("ok"):
                    st.warning(f"동기화 미실행: {(res or {}).get('reason','?')} (WordPress 미구성 등)")
                else:
                    from collections import Counter as _Ctr
                    _fc = _Ctr(a.get("flag") for a in res.get("anomalies", []))
                    st.success(f"✅ 동기화 완료 · 검사 {res['checked']}건 / 변경 {res['changed']}건 / {_el}초")
                    st.write("이상: WP_DELETED %d · URL_CHANGED %d · ORPHAN_WP %d · ORPHAN_SHEET %d" % (
                        _fc.get("WP_DELETED",0), _fc.get("URL_CHANGED",0),
                        _fc.get("ORPHAN_WP",0), _fc.get("ORPHAN_SHEET",0)))
                    for a in res.get("anomalies", [])[:10]:
                        st.write(f"- {a.get('flag')} · {a.get('name','')} (post_id={a.get('post_id','-')})")

    # ── 현재 일정 표시 ──
    sched = SCH.load_schedule(cfg)
    today = date.today().isoformat()

    # ── 스케줄 탭 전용 자동 새로고침(테스트용) ──
    # 예약 시각이 지난 슬롯이 '예정/처리중/재시도'인 동안 1분마다 자동 새로고침하고,
    # '발행완료/실패/HOLD/Skip'(terminal)이 되면 즉시 종료. 안전장치로 최대 10분까지만.
    # 이 탭에서만 동작(다른 탭은 이 코드 미실행). UI 표시 전용 — 예약/스케줄러/발행/WP/Telegram 로직과
    # 무관. 새로고침 횟수·마지막 시각·감시상태는 session_state로만 관리.
    import time as _time
    _ss = st.session_state
    for _k, _v in (("sched_ar_start", 0.0), ("sched_ar_last", 0.0), ("sched_ar_count", 0),
                   ("sched_ar_watching", False), ("sched_ar_render", 0.0)):
        _ss.setdefault(_k, _v)

    def _hm2min(t):
        try:
            _h, _m = str(t).split(":")[:2]
            return int(_h) * 60 + int(_m)
        except Exception:
            return -1

    _AR_CAP = 600                                     # 안전장치: 최대 10분
    _ACTIVE_ST = ("pending", "running", "retry")      # 미완료(계속) / completed·failed = terminal(종료)
    _now = _dt.now()
    _now_min = _now.hour * 60 + _now.minute
    _now_ts = _time.time()
    _entries_today = (sched.get("schedule") or []) if (sched and sched.get("date") == today) else []
    # 예약시각이 도래했는데 아직 미완료인 슬롯이 있으면 '감시(watching)' → 계속 새로고침
    _due_pending = [e for e in _entries_today
                    if 0 <= _hm2min(e.get("scheduled_time")) <= _now_min
                    and str(e.get("status", "")).strip() in _ACTIVE_ST]
    _watching = len(_due_pending) > 0

    _prev_watching = _ss["sched_ar_watching"]
    if _watching and not _prev_watching:              # 감시 시작(에지) → 캡 기준시각·카운트 초기화
        _ss["sched_ar_start"] = _now_ts
        _ss["sched_ar_last"] = _now_ts
        _ss["sched_ar_count"] = 0
    elif (_watching or _prev_watching) and _ss["sched_ar_last"] and (_now_ts - _ss["sched_ar_last"]) >= 55:
        _ss["sched_ar_count"] += 1                    # 타이머 촉발 새로고침 1회로 집계(terminal 감지 tick 포함)
        _ss["sched_ar_last"] = _now_ts
    _ss["sched_ar_watching"] = _watching

    _elapsed = _now_ts - (_ss["sched_ar_start"] or _now_ts)
    _ar_active = _watching and _elapsed < _AR_CAP     # 미완료 슬롯 있고 & 10분 이내면 계속

    if _ar_active:
        _ar_interval = 60                             # 1분 간격 새로고침
    else:
        # 감시 아님 → 다음 예약(미도래 pending) 시각까지 대기, 없으면 정지
        _future_pending = sorted([_hm2min(e.get("scheduled_time")) for e in _entries_today
                                  if _hm2min(e.get("scheduled_time")) > _now_min
                                  and str(e.get("status", "")).strip() in ("pending", "retry")])
        _ar_interval = min(3600, max(20, (_future_pending[0] - _now_min) * 60 + 5)) if _future_pending else None

    _ss["sched_ar_render"] = _now_ts
    if _ar_interval is not None:
        @st.fragment(run_every=_ar_interval)
        def _sched_auto_refresh():
            # 타이머 만료 시에만 전체 앱 재실행(초기 렌더는 render_ts 가드로 제외 → 무한루프 방지)
            if _time.time() - _ss["sched_ar_render"] >= (_ar_interval - 3):
                st.rerun()
        _sched_auto_refresh()

    if _ar_active:
        st.caption(f"⏱ 자동 새로고침 중 · 미완료 슬롯 {len(_due_pending)}개 · {_ss['sched_ar_count']}회 · "
                   f"경과 {int(_elapsed // 60)}분/최대 10분 · {_now.strftime('%H:%M:%S')} (완료 시 자동 종료)")

    if sched and sched.get("date") == today:
        st.caption(f"기준일: {sched['date']} ({sched.get('day_type')}) · 실패모드: {sched.get('failure_mode')}")
        # 슬롯별 실행 결과 카드 — Empty 대신 상태 유지 표시(저장된 메타 keyword/title/wp만 읽어 표시).
        _entries = sched.get("schedule", [])

        def _slot_status(e):
            s = str(e.get("status", "")).strip()
            r = str(e.get("result", ""))
            if s == "completed":
                return "✅ 발행완료", "#16a34a"
            if s == "running":
                return "▶ 처리중", "#3b82f6"
            if s == "retry":
                return "🟠 재시도", "#f59e0b"
            if s == "pending":
                return "⏳ 예정", "#f59e0b"
            if s == "failed":
                if any(k in r for k in ("HOLD", "품질보류", "모든후보HOLD")):
                    return "⚠ HOLD", "#eab308"
                if any(k in r for k in ("후보소진", "no_calculators", "no_items", "budget")):
                    return "⏭ Skip", "#94a3b8"
                return "❌ 실패", "#ef4444"
            return "⏳ 예정", "#f59e0b"

        if _entries:
            for e in _entries:
                label, col = _slot_status(e)
                with st.container(border=True):
                    cA, cB = st.columns([1, 3])
                    cA.markdown(
                        f"<div style='font-size:18px;font-weight:700'>{e.get('scheduled_time') or e.get('slot_start','-')}</div>"
                        f"<div style='font-size:11px;color:#64748b'>슬롯 {e.get('slot_start','')}~{e.get('slot_end','')}</div>",
                        unsafe_allow_html=True)
                    parts = [f"<span style='color:{col};font-weight:600'>{label}</span>"]
                    if e.get("keyword"):
                        parts.append(f"🔑 {e['keyword']}")
                    if e.get("title"):
                        parts.append(f"📝 {e['title']}")
                    tail = []
                    _t = e.get("completed_at") or e.get("actual_time")
                    if _t:
                        tail.append(f"⏱ {_t}")
                    if e.get("wp_post_id"):
                        tail.append(f"<a href='{e['wp_url']}' target='_blank'>WP #{e['wp_post_id']}</a>"
                                    if e.get("wp_url") else f"WP #{e['wp_post_id']}")
                    if str(e.get("delay_min", "")) not in ("", "-", "None"):
                        tail.append(f"지연 {e['delay_min']}분")
                    if tail:
                        parts.append(f"<span style='font-size:12px;color:#64748b'>{' · '.join(str(x) for x in tail)}</span>")
                    if not e.get("keyword") and e.get("result"):
                        parts.append(f"<span style='font-size:12px;color:#64748b'>{e['result']}</span>")
                    cB.markdown("<br>".join(parts), unsafe_allow_html=True)
            done = sum(1 for e in _entries if e.get("status") == "completed")
            st.progress(done / max(len(_entries), 1), text=f"완료 {done}/{len(_entries)}")
        else:
            st.info("오늘 생성된 예약 슬롯이 없습니다. (설정 시각이 이미 지나 생성에서 제외됐을 수 있습니다.)")
            try:
                _daytype, _cfg_slots = SCH.get_slots_for(cfg, date.today())
            except Exception:
                _cfg_slots = []
            if _cfg_slots:
                st.caption("설정된 슬롯(참고 — 오늘 미생성):")
                for s in _cfg_slots:
                    st.write(f"• {s.get('start')}~{s.get('end')}  ⏭ 오늘 미생성")

        # 실패 건 즉시 재시도
        failed = [e for e in sched["schedule"] if e.get("status") == "failed"]
        if failed:
            st.warning(f"실패 {len(failed)}건 — 즉시 재시도 가능")
            rc1, rc2 = st.columns([2, 1])
            pick = rc1.selectbox("재시도할 글", [f"글{e['post_no']} ({e.get('result','')})" for e in failed],
                                 key="retry_pick")
            if rc2.button("🔁 즉시 재시도", type="primary"):
                import main as PIPE
                entry = failed[[f"글{e['post_no']} ({e.get('result','')})" for e in failed].index(pick)]
                entry["status"] = "pending"  # 재실행 대상으로 전환
                with st.spinner("재시도 실행 중..."):
                    SCH.execute_due_post(cfg, sched, entry, PIPE.resolve_publish_fn(cfg))
                st.rerun()
    else:
        st.info("오늘 생성된 일정이 없습니다. 아래에서 '스케줄 생성'을 누르세요.")

    # (생성/재생성/초기화/즉시발행 버튼은 상단 컨트롤 패널로 통합됨)
    if st.session_state.get("_sched_confirm"):
        with st.container(border=True):
            st.warning("즉시 1건 발행할까요? (예약시간 무시)")
            m = st.radio("모드", ["예정 글 당겨쓰기(기본)", "추가 발행"], key="_sched_mode")
            x1, x2 = st.columns(2)
            if x1.button("✅ 예, 발행", type="primary", key="_sched_yes"):
                import main as PIPE
                with st.spinner("즉시 발행 중..."):
                    ok, msg = SCH.immediate_publish(cfg, PIPE.resolve_publish_fn(cfg), "pull" if "당겨" in m else "add")
                (st.success if ok else st.error)(msg)
                st.session_state["_sched_confirm"] = False; st.rerun()
            if x2.button("취소", key="_sched_no"):
                st.session_state["_sched_confirm"] = False; st.rerun()

    st.divider()
    # ── 슬롯 설정 ──
    st.subheader("⚙️ 슬롯 설정 (평일/주말 분리)")
    ps = dict(cfg.get("PUBLISH_SCHEDULE", {}) or {})
    default_count = len(ps.get("weekday") or []) or int(cfg.get("DAILY_POST_COUNT", 1) or 1)
    count = int(st.number_input("하루 발행 개수 (= 슬롯 수, DAILY_POST_COUNT 자동 결정)",
                                1, 20, default_count, key="sch_count"))
    st.caption("슬롯 수가 곧 하루 발행 개수입니다. 시작 < 종료, 슬롯 겹침 금지.")

    enabled = st.toggle("스케줄러 사용(enabled)", value=ps.get("enabled", True), key="sch_enabled")
    fmode = st.selectbox(
        "실패 처리 모드", SCH.FAILURE_MODES,
        index=SCH.FAILURE_MODES.index(ps.get("failure_mode", "retry_in_slot"))
        if ps.get("failure_mode", "retry_in_slot") in SCH.FAILURE_MODES else 1,
        format_func=lambda m: {"none": "모드1: 재시도 안함",
                               "retry_in_slot": "모드2: 슬롯 내 재시도",
                               "next_slot": "모드3: 다음 빈 슬롯으로 이동"}.get(m, m),
        key="sch_fmode")

    def _slot_editor(day_type: str, label: str, is_today: bool = False):
        # 헤더 표시만 조건부(오늘 적용 요일 강조). 아래 슬롯 값/반환 로직은 무변경.
        if is_today:
            st.success(f"✅ {label} · 오늘 적용")
        else:
            st.markdown(f"**{label}**")
            st.caption("오늘 미적용 (다음 해당 요일에 적용)")
        existing = ps.get(day_type) or SCH.default_slots(count)
        new_slots = []
        for i in range(count):
            cur = existing[i] if i < len(existing) else {"start": "09:00", "end": "10:00"}
            c1, c2 = st.columns(2)
            s = c1.time_input(f"[{label}] 글{i+1} 시작", value=_parse_t(cur.get("start", "09:00")),
                              key=f"{day_type}_s_{i}", step=300)
            e = c2.time_input(f"[{label}] 글{i+1} 종료", value=_parse_t(cur.get("end", "10:00")),
                              key=f"{day_type}_e_{i}", step=300)
            new_slots.append({"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M")})
        return new_slots

    _today_type = "weekend" if date.today().weekday() >= 5 else "weekday"
    cwd, cwe = st.columns(2)
    with cwd:
        weekday_slots = _slot_editor("weekday", "평일(월~금)", is_today=(_today_type == "weekday"))
    with cwe:
        weekend_slots = _slot_editor("weekend", "주말(토~일)", is_today=(_today_type == "weekend"))

    # 검증
    errs = SCH.validate_slots(weekday_slots, count) + SCH.validate_slots(weekend_slots, count)
    if errs:
        for e in errs:
            st.warning(e)

    if st.button("💾 슬롯 설정 저장 + 즉시 반영", type="primary"):
        if errs:
            st.error("검증 오류를 먼저 해결하세요.")
        else:
            cfg_path = BASE / "config" / "config.yaml"
            with open(cfg_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            raw["PUBLISH_SCHEDULE"] = {
                "enabled": bool(enabled),
                "failure_mode": fmode,
                "weekday": weekday_slots,
                "weekend": weekend_slots,
            }
            raw["DAILY_POST_COUNT"] = int(count)  # 슬롯 수 = 하루 발행 개수 동기화
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            # cfg 캐시만 갱신(스케줄러 스레드 캐시는 건드리지 않음 — 스레드 중복 기동 방지)
            load_cfg.clear()
            cfg = load_cfg()
            # 저장 즉시 오늘 일정 반영: reset + generate. available_slots로 과거 슬롯 자동 제외.
            _, _day_slots = SCH.get_slots_for(cfg, date.today())
            _total = len(_day_slots)
            SCH.reset_today(cfg)
            _new = SCH.generate_today_schedule(cfg)
            _m = len(_new.get("schedule", []))
            _n = max(0, _total - _m)
            st.success(f"✅ 적용 완료 (오늘 일정 즉시 반영) · 과거 {_n}개 제외 / 새 {_m}개 슬롯 생성")
            st.rerun()

# ══════════════════════════════════════════════════════════════
# 탭: 🌐 사이트 관리 (사이트/계산기 생성 마법사 + 관리)
# ══════════════════════════════════════════════════════════════
elif tab == "🌐 사이트 관리":
    st.title("🌐 사이트 관리")
    from modules import site_wizard as SW
    import json as _json
    AI_PROFILES = ["gemini_flash", "gemini_pro", "gpt4o", "gpt4o_mini",
                   "claude_sonnet", "claude_haiku", "claude_opus"]

    # ── 현재 Site 헤더 + 셀렉터 (작업4 세션 공유) ──
    try:
        _sm_sites = SW.list_sites(cfg) or []
    except Exception:
        _sm_sites = []
    if _sm_sites:
        _ids = [s.get("site_id", "") for s in _sm_sites]
        _labels = [(s.get("site_name") or s.get("site_id") or "(이름없음)") for s in _sm_sites]
        _cur = st.session_state.get("current_site_id", _ids[0])
        _idx = _ids.index(_cur) if _cur in _ids else 0
        hc1, hc2 = st.columns([2, 1])
        with hc2:
            _pick = st.selectbox("현재 Site", _labels, index=_idx, key="sm_cur_pick")
        st.session_state["current_site_id"] = _ids[_labels.index(_pick)]
        hc1.info(f"현재 선택: **{_pick}**")
    else:
        st.caption("등록된 사이트 없음 — 기본 사이트(CalcMate). 아래에서 새 사이트를 추가하세요.")

    # ── ⬇️⬆️ Export / Import (메타데이터만 · 자격증명 제외) ──
    with st.expander("⬇️⬆️ Export / Import"):
        ec1, ec2 = st.columns(2)
        with ec1:
            st.download_button(
                "⬇️ 사이트 Export(JSON)",
                data=_json.dumps(_sm_sites, ensure_ascii=False, indent=2),
                file_name="sites_export.json", mime="application/json", key="sm_export")
            st.caption("WP 자격증명/시크릿은 포함되지 않습니다.")
        with ec2:
            up = st.file_uploader("⬆️ Import(JSON) — 검증 경유 신규 등록만", type=["json"], key="sm_import")
            if up is not None and st.button("Import 실행", key="sm_import_run"):
                try:
                    rows = _json.loads(up.read()); assert isinstance(rows, list)
                except Exception as e:
                    rows = None; st.error(f"JSON 파싱 실패: {e}")
                if rows:
                    okc, errs = 0, []
                    for r in rows:
                        stype = r.get("site_type", "custom")
                        label = next((k for k, v in SW.TYPE_DEFS.items() if v["site_type"] == stype), "사용자정의")
                        ok, msg = SW.create_site(cfg, label, {
                            "site_name": r.get("site_name", ""), "domain": r.get("domain", ""),
                            "category": r.get("site_tags", ""),
                            "wp_url": r.get("wordpress_url", ""), "wp_user": "", "wp_app_password": "",
                            "rss_sources": "",
                        })
                        okc += 1 if ok else 0
                        if not ok: errs.append(msg)
                    st.success(f"Import: {okc}건 등록 (WP 유형은 자격증명 필요 시 실패할 수 있음)")
                    for e in errs[:8]:
                        st.warning(e)
                    if okc:
                        st.cache_resource.clear(); st.rerun()

    # ── ⚙️ Site Settings (Global → Override) · 현재 선택 Site 대상 ──
    with st.expander("⚙️ Site Settings (Override)"):
        _cur_id = st.session_state.get("current_site_id", "")
        _site = next((s for s in _sm_sites if s.get("site_id") == _cur_id),
                     (_sm_sites[0] if _sm_sites else None))
        if not _site:
            st.caption("선택된 Site가 없습니다. 먼저 사이트를 추가하세요.")
        else:
            GLOB = "(Global 기본값)"
            st.caption(f"대상: **{_site.get('site_name','-')}** ({_site.get('site_id','')}) · "
                       "빈 값=Global 상속, 값 있으면 🔵 Override")
            def _ai_box(col, label, gdef, colobj):
                cur = _site.get(col, "")
                opts = [GLOB] + AI_PROFILES
                idx = opts.index(cur) if cur in AI_PROFILES else 0
                v = colobj.selectbox(label + (" 🔵" if cur in AI_PROFILES else ""),
                                     opts, index=idx, key=f"ss_{col}")
                colobj.caption(f"Global: {gdef}")
                return "" if v == GLOB else v
            st.markdown("**AI**")
            a1, a2, a3 = st.columns(3)
            o_res = _ai_box("research_ai", "Research AI", SW.DEFAULT_AI["research_ai"], a1)
            o_wri = _ai_box("writing_ai", "Writing AI", SW.DEFAULT_AI["writing_ai"], a2)
            o_rev = _ai_box("review_ai", "Review AI", SW.DEFAULT_AI["review_ai"], a3)

            st.markdown("**WordPress / SEO**")
            w1, w2 = st.columns(2)
            o_wpurl = w1.text_input("WordPress URL" + (" 🔵" if _site.get("wordpress_url") else ""),
                                    value=_site.get("wordpress_url", ""), key="ss_wpurl",
                                    placeholder=cfg.get("WORDPRESS_URL", ""))
            o_cat = w2.text_input("카테고리(site_tags)" + (" 🔵" if _site.get("site_tags") else ""),
                                  value=_site.get("site_tags", ""), key="ss_cat")
            s1, s2 = st.columns(2)
            o_kwc = s1.text_input("SEO 키워드 수" + (" 🔵" if _site.get("seo_keyword_count") else ""),
                                  value=str(_site.get("seo_keyword_count", "")), key="ss_kwc", placeholder="Global 5")
            o_len = s2.text_input("SEO 글 길이" + (" 🔵" if _site.get("seo_length") else ""),
                                  value=str(_site.get("seo_length", "")), key="ss_len", placeholder="Global 1500")

            st.markdown("**Scheduler / Image**")
            sc1, sc2 = st.columns(2)
            o_daily = sc1.text_input("일 발행수" + (" 🔵" if _site.get("daily_override") else ""),
                                     value=str(_site.get("daily_override", "")), key="ss_daily",
                                     placeholder=f"Global {cfg.get('DAILY_POST_COUNT',3)}")
            _img_opts = [GLOB, "free_pollinations", "openai", "none"]
            _imgcur = _site.get("image_mode", "")
            o_img = sc2.selectbox("이미지 생성 방식" + (" 🔵" if _imgcur else ""), _img_opts,
                                  index=_img_opts.index(_imgcur) if _imgcur in _img_opts else 0, key="ss_img")
            sc2.caption(f"Global 이미지: {cfg.get('IMAGE_PROVIDER','free_pollinations')}")

            st.markdown("**Telegram / Analytics**")
            t1, t2 = st.columns(2)
            _onoff = [GLOB, "ON", "OFF"]
            _tgcur = _site.get("telegram_enabled", "")
            o_tg = t1.selectbox("Telegram 알림" + (" 🔵" if _tgcur else ""), _onoff,
                                index=_onoff.index(_tgcur) if _tgcur in _onoff else 0, key="ss_tg")
            _ancur = _site.get("analytics_enabled", "")
            o_an = t2.selectbox("Analytics" + (" 🔵" if _ancur else ""), _onoff,
                                index=_onoff.index(_ancur) if _ancur in _onoff else 0, key="ss_an")

            st.markdown("**Calculator (활성 계산기)**")
            try:
                _allcalc = [c.get("name", "") for c in SW.list_calculators(cfg) if c.get("name")]
            except Exception:
                _allcalc = []
            try:
                _cursel = _json.loads(_site.get("calc_active") or "[]")
            except Exception:
                _cursel = []
            o_calc = st.multiselect("활성 계산기 목록", _allcalc,
                                    default=[c for c in _cursel if c in _allcalc], key="ss_calc")

            st.markdown("**Feature Flags (작업6 설정 — 표시)**")
            st.code(_site.get("features", "{}"), language="json")

            bc1, bc2 = st.columns(2)
            if bc1.button("💾 Override 저장", type="primary", key="ss_save"):
                ok, msg = SW.update_site(cfg, _site.get("site_id", ""), {
                    "research_ai": o_res, "writing_ai": o_wri, "review_ai": o_rev,
                    "wordpress_url": o_wpurl.strip(), "site_tags": o_cat.strip(),
                    "seo_keyword_count": o_kwc.strip(), "seo_length": o_len.strip(),
                    "daily_override": o_daily.strip(),
                    "image_mode": "" if o_img == GLOB else o_img,
                    "telegram_enabled": "" if o_tg == GLOB else o_tg,
                    "analytics_enabled": "" if o_an == GLOB else o_an,
                    "calc_active": _json.dumps(o_calc, ensure_ascii=False),
                })
                (st.success if ok else st.error)("Override 저장됨" if ok else msg)
                if ok: st.cache_resource.clear(); st.rerun()
            if bc2.button("↩️ Override 초기화(Global 복귀)", key="ss_reset"):
                # 코어 필드(wordpress_url/site_tags)는 보존, Override 전용 필드만 비움
                ok, msg = SW.update_site(cfg, _site.get("site_id", ""), {k: "" for k in [
                    "research_ai", "writing_ai", "review_ai", "seo_keyword_count", "seo_length",
                    "daily_override", "image_mode", "telegram_enabled", "analytics_enabled", "calc_active"]})
                (st.success if ok else st.error)("Global 기본값으로 초기화" if ok else msg)
                if ok: st.cache_resource.clear(); st.rerun()

    # ── 🧙 새 사이트 마법사 (5단계: Profile→Platform→Feature→Settings→Pipeline) ──
    with st.expander("🧙 새 사이트 마법사 (5단계)"):
        WP_FEATS = ["글 작성", "자동 발행", "SEO", "이미지 업로드", "카테고리"]
        CALC_FEATS = ["계산기 생성", "계산기 SEO 글", "FAQ 생성", "AI Reviewer", "HTML 생성"]
        COMMON_FEATS = ["Scheduler", "Telegram", "AI Assistant", "Analytics", "Cost Manager", "Retry Queue"]
        w = st.session_state.setdefault("wiz6", {"step": 1, "data": {}})
        step, d = w["step"], w["data"]
        st.caption(f"진행: {step}/5")

        if step == 1:
            st.markdown("**Step 1 · Site Profile**")
            d["site_name"] = st.text_input("사이트명 *", value=d.get("site_name", ""), key="w6_name")
            d["domain"]    = st.text_input("도메인 *", value=d.get("domain", ""), key="w6_dom")
            d["wp_url"]    = st.text_input("WordPress URL (선택)", value=d.get("wp_url", ""), key="w6_wpurl")
            if st.button("다음 →", key="w6_n1"):
                if d.get("site_name") and d.get("domain"):
                    w["step"] = 2; st.rerun()
                else:
                    st.error("사이트명과 도메인은 필수입니다.")

        elif step == 2:
            st.markdown("**Step 2 · Platform 선택 (독립 복수)**")
            pf = d.get("platforms", [])
            use_wp   = st.checkbox("WordPress", value=("WordPress" in pf), key="w6_pwp")
            use_calc = st.checkbox("Calculator", value=("Calculator" in pf), key="w6_pcalc")
            if use_wp:
                st.caption("WordPress 자격증명 (필수)")
                d["wp_user"] = st.text_input("WordPress ID *", value=d.get("wp_user", ""), key="w6_wpuser")
                d["wp_pw"]   = st.text_input("App Password *", type="password", value=d.get("wp_pw", ""), key="w6_wppw")
            c1, c2 = st.columns(2)
            if c1.button("← 이전", key="w6_b2"): w["step"] = 1; st.rerun()
            if c2.button("다음 →", key="w6_n2"):
                pf = (["WordPress"] if use_wp else []) + (["Calculator"] if use_calc else [])
                d["platforms"] = pf
                if use_wp and not (d.get("wp_url") and d.get("wp_user") and d.get("wp_pw")):
                    st.error("WordPress 선택 시 URL(Step1)/ID/App Password가 필요합니다.")
                else:
                    w["step"] = 3; st.rerun()

        elif step == 3:
            st.markdown("**Step 3 · Feature 선택 (Platform별 + 공통)**")
            pf, sel = d.get("platforms", []), {}
            if "WordPress" in pf:
                st.markdown("*WordPress*")
                sel["wordpress"] = [f for f in WP_FEATS if st.checkbox(f, value=True, key=f"w6_fw_{f}")]
            if "Calculator" in pf:
                st.markdown("*Calculator*")
                sel["calculator"] = [f for f in CALC_FEATS if st.checkbox(f, value=True, key=f"w6_fc_{f}")]
            st.markdown("*공통*")
            sel["common"] = [f for f in COMMON_FEATS if st.checkbox(f, value=True, key=f"w6_fco_{f}")]
            c1, c2 = st.columns(2)
            if c1.button("← 이전", key="w6_b3"): w["step"] = 2; st.rerun()
            if c2.button("다음 →", key="w6_n3"):
                d["features"] = sel; w["step"] = 4; st.rerun()

        elif step == 4:
            st.markdown("**Step 4 · Settings (Global 기본값 → Override)**")
            st.caption("미변경 시 Global 기본값 적용. 상세 항목은 작업7(Site Settings)에서 편집.")
            a1, a2, a3 = st.columns(3)
            d["research_ai"] = a1.selectbox("Research AI", AI_PROFILES,
                index=AI_PROFILES.index(d.get("research_ai", SW.DEFAULT_AI["research_ai"])), key="w6_rai")
            d["writing_ai"] = a2.selectbox("Writing AI", AI_PROFILES,
                index=AI_PROFILES.index(d.get("writing_ai", SW.DEFAULT_AI["writing_ai"])), key="w6_wai")
            d["review_ai"] = a3.selectbox("Review AI", AI_PROFILES,
                index=AI_PROFILES.index(d.get("review_ai", SW.DEFAULT_AI["review_ai"])), key="w6_vai")
            d["daily_override"] = st.number_input("일 발행수 (Override)", 1, 20,
                int(d.get("daily_override", cfg.get("DAILY_POST_COUNT", 3))), key="w6_daily")
            c1, c2 = st.columns(2)
            if c1.button("← 이전", key="w6_b4"): w["step"] = 3; st.rerun()
            if c2.button("다음 →", key="w6_n4"): w["step"] = 5; st.rerun()

        elif step == 5:
            st.markdown("**Step 5 · Pipeline 연결 확인**")
            pf = d.get("platforms", [])
            if "Calculator" in pf and "WordPress" in pf:
                pipe_msg = "이 Site는 **Calculator Pipeline → WordPress 발행** 순서로 실행됩니다."
            elif "Calculator" in pf:
                pipe_msg = "이 Site는 **Calculator Pipeline**으로 실행됩니다."
            elif "WordPress" in pf:
                pipe_msg = "이 Site는 **RSS/정책 Pipeline → WordPress 발행**으로 실행됩니다."
            else:
                pipe_msg = "Platform 미선택 — 나중에 Platform을 추가하면 Pipeline이 결정됩니다."
            st.info(pipe_msg)
            st.json({"profile": {"name": d.get("site_name"), "domain": d.get("domain")},
                     "platforms": pf, "features": d.get("features", {}),
                     "override": {"research_ai": d.get("research_ai"), "writing_ai": d.get("writing_ai"),
                                  "review_ai": d.get("review_ai"), "daily": d.get("daily_override")}})
            c1, c2 = st.columns(2)
            if c1.button("← 이전", key="w6_b5"): w["step"] = 4; st.rerun()
            if c2.button("✅ 사이트 생성", type="primary", key="w6_create"):
                needs_wp = "WordPress" in pf
                label = "사용자정의" if needs_wp else "계산기"
                ok, msg = SW.create_site(cfg, label, {
                    "site_name": d.get("site_name", ""), "domain": d.get("domain", ""), "category": "",
                    "wp_url": d.get("wp_url", ""), "wp_user": d.get("wp_user", ""),
                    "wp_app_password": d.get("wp_pw", ""), "rss_sources": "",
                    "research_ai": d.get("research_ai", ""), "writing_ai": d.get("writing_ai", ""),
                    "review_ai": d.get("review_ai", ""),
                })
                if ok:
                    try:  # platforms/features를 신규 컬럼으로 기록(create_site 무변경)
                        rows = SW.list_sites(cfg)
                        nm = d.get("site_name", "").strip()
                        nr = next((x for x in rows if str(x.get("site_name", "")).strip() == nm), None)
                        if nr:
                            SW.update_site(cfg, nr.get("site_id", ""), {
                                "platforms": _json.dumps(pf, ensure_ascii=False),
                                "features": _json.dumps(d.get("features", {}), ensure_ascii=False),
                                "daily_override": str(d.get("daily_override", "")),
                            })
                    except Exception as e:
                        st.warning(f"platforms/features 기록 경고: {e}")
                    st.success(msg + " · Platform/Feature 저장됨")
                    st.session_state.pop("wiz6", None)
                    st.cache_resource.clear(); st.rerun()
                else:
                    st.error(msg)

    # ── ➕ 사이트 추가 ──
    with st.expander("➕ 사이트 추가", expanded=True):
        type_label = st.selectbox("유형 선택", SW.SITE_TYPES, key="sw_type")
        spec = SW.TYPE_DEFS[type_label]
        st.caption(f"site_type=`{spec['site_type']}` · 수익화=`{spec['monetization']}` · "
                   f"content_mode=`{spec['content_mode']}`"
                   + (" · ⚠️ 수집기 미구현(stub)" if spec['site_type'] in SW.STUB_TYPES else ""))

        if type_label == "계산기":
            c1, c2 = st.columns(2)
            calc_name = c1.text_input("계산기명 *", placeholder="주휴수당 계산기", key="sw_calc_name")
            calc_cat  = c2.text_input("카테고리", placeholder="노무/급여", key="sw_calc_cat")
            calc_desc = st.text_area("설명", placeholder="예: 주휴수당 자동 계산", key="sw_calc_desc")
            st.caption("예시: 주휴수당 계산기 · 퇴직금 계산기 · 대출이자 계산기")
            if st.button("💾 계산기 등록", type="primary", key="sw_calc_save"):
                ok, msg = SW.create_calculator(cfg, {
                    "name": calc_name, "description": calc_desc, "category": calc_cat})
                (st.success if ok else st.error)(msg)
                if ok:
                    st.cache_resource.clear(); st.rerun()
        else:
            c1, c2 = st.columns(2)
            site_name = c1.text_input("사이트명 *", key="sw_name")
            domain    = c2.text_input("도메인 *", placeholder="example.com", key="sw_domain")
            category  = st.text_input("카테고리", placeholder="복지/정책", key="sw_cat")

            wp_url = wp_user = wp_pw = ""
            if spec["needs_wp"]:
                st.markdown("**WordPress 연동**")
                w1, w2 = st.columns(2)
                wp_url  = w1.text_input("WordPress URL *", placeholder="https://yourblog.com", key="sw_wpurl")
                wp_user = w2.text_input("WordPress ID *", placeholder="admin", key="sw_wpuser")
                wp_pw   = st.text_input("App Password *", type="password",
                                        placeholder="xxxx xxxx xxxx xxxx", key="sw_wppw")
            rss = ""
            if spec["uses_rss"]:
                rss = st.text_input("RSS 수집원(콤마 구분, 선택)",
                                    placeholder="https://www.korea.kr/rss/policy.xml", key="sw_rss")

            with st.expander("AI 프로필(선택) — 미선택 시 기본값"):
                a1, a2, a3 = st.columns(3)
                research = a1.selectbox("Research AI", AI_PROFILES,
                                        index=AI_PROFILES.index(SW.DEFAULT_AI["research_ai"]), key="sw_research")
                writing  = a2.selectbox("Writing AI", AI_PROFILES,
                                        index=AI_PROFILES.index(SW.DEFAULT_AI["writing_ai"]), key="sw_writing")
                review   = a3.selectbox("Review AI", AI_PROFILES,
                                        index=AI_PROFILES.index(SW.DEFAULT_AI["review_ai"]), key="sw_review")

            if st.button("💾 사이트 등록", type="primary", key="sw_site_save"):
                ok, msg = SW.create_site(cfg, type_label, {
                    "site_name": site_name, "domain": domain, "category": category,
                    "wp_url": wp_url, "wp_user": wp_user, "wp_app_password": wp_pw,
                    "rss_sources": rss,
                    "research_ai": research, "writing_ai": writing, "review_ai": review,
                })
                (st.success if ok else st.error)(msg)
                if ok:
                    st.cache_resource.clear(); st.rerun()

    st.divider()
    # ── 사이트 목록 / 관리 ──
    st.subheader("📋 등록된 사이트")
    try:
        sites = SW.list_sites(cfg)
    except Exception as e:
        sites = []
        st.error(f"사이트 목록 조회 실패(시트 권한 확인): {e}")
    if not sites:
        st.caption("등록된 사이트 없음")
    for s in sites:
        sid = s.get("site_id", "")
        active = str(s.get("status", "")).lower() == "active"
        icon = "🟢" if active else "⚪"
        with st.expander(f"{icon} {s.get('site_name','(이름없음)')} — {s.get('domain','')} "
                         f"[{s.get('site_type','')}] ({s.get('status','')})"):
            e1, e2 = st.columns(2)
            new_name = e1.text_input("사이트명", value=s.get("site_name", ""), key=f"ed_name_{sid}")
            new_dom  = e2.text_input("도메인", value=s.get("domain", ""), key=f"ed_dom_{sid}")
            new_cat  = st.text_input("카테고리", value=s.get("site_tags", ""), key=f"ed_cat_{sid}")
            from datetime import datetime as _dt, timedelta as _td
            status_l = str(s.get("status", "")).lower()
            archived = status_l == "archived"
            b1, b2, b3 = st.columns(3)
            if b1.button("💾 수정 저장", key=f"ed_save_{sid}"):
                ok, msg = SW.update_site(cfg, sid, {
                    "site_name": new_name, "domain": new_dom, "site_tags": new_cat})
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()
            if not archived:
                toggle_label = "⏸ 비활성화" if active else "▶ 활성화"
                if b2.button(toggle_label, key=f"ed_tog_{sid}"):
                    ok, msg = SW.set_site_status(cfg, sid, "inactive" if active else "active")
                    (st.success if ok else st.error)(msg)
                    if ok: st.rerun()
                if b3.button("🗑️ 삭제(보관 이동)", key=f"ed_arch_{sid}"):
                    ok, msg = SW.update_site(cfg, sid, {
                        "status": "archived", "deleted_at": _dt.now().isoformat()})
                    (st.success if ok else st.error)(
                        "보관함으로 이동됨 — 보관기간 내 복구 가능" if ok else msg)
                    if ok: st.rerun()
            else:
                ret_days = int(cfg.get("SITE_RETENTION_DAYS", 30) or 30)
                da = s.get("deleted_at", "")
                expired, exp_txt = False, "-"
                try:
                    exp = _dt.fromisoformat(da) + _td(days=ret_days)
                    expired = _dt.now() > exp
                    exp_txt = exp.strftime("%Y-%m-%d")
                except Exception:
                    pass
                st.warning(f"📦 보관됨 (삭제예정 {exp_txt}, 보관 {ret_days}일)"
                           + (" · ⚠️ 보관기간 만료 — 영구삭제 가능" if expired else ""))
                if b2.button("♻️ 복구", key=f"ed_restore_{sid}"):
                    ok, msg = SW.update_site(cfg, sid, {"status": "inactive", "deleted_at": ""})
                    (st.success if ok else st.error)("복구됨(비활성 상태)" if ok else msg)
                    if ok: st.rerun()
                with b3:
                    conf = st.text_input('영구삭제: "DELETE" 입력', key=f"ed_delconf_{sid}")
                    if st.button("⛔ 영구 삭제", key=f"ed_perm_{sid}"):
                        if conf.strip() == "DELETE":
                            ok, msg = SW.delete_site(cfg, sid)
                            (st.success if ok else st.error)(msg)
                            if ok: st.rerun()
                        else:
                            st.error('"DELETE"를 정확히 입력해야 합니다.')
            # ── 📑 복제(Clone) — 인라인 프리필 폼 ──
            with st.expander("📑 복제(Clone)"):
                cl_name = st.text_input("새 사이트명 *", value=f"{s.get('site_name','')} (복사본)",
                                        key=f"cl_name_{sid}")
                cl_dom = st.text_input("새 도메인 *", value="", key=f"cl_dom_{sid}")
                spec_lbl = next((k for k, v in SW.TYPE_DEFS.items()
                                 if v["site_type"] == s.get("site_type", "custom")), "사용자정의")
                cwu = cwz = cwp = ""
                if SW.TYPE_DEFS[spec_lbl]["needs_wp"]:
                    st.caption("이 유형은 WordPress 자격증명이 필요합니다(복제 시 재입력).")
                    cwu = st.text_input("WordPress URL *", key=f"cl_wpurl_{sid}")
                    cwz = st.text_input("WordPress ID *", key=f"cl_wpuser_{sid}")
                    cwp = st.text_input("App Password *", type="password", key=f"cl_wppw_{sid}")
                if st.button("📑 복제 실행", key=f"cl_run_{sid}"):
                    ok, msg = SW.create_site(cfg, spec_lbl, {
                        "site_name": cl_name, "domain": cl_dom, "category": s.get("site_tags", ""),
                        "wp_url": cwu, "wp_user": cwz, "wp_app_password": cwp, "rss_sources": "",
                        "research_ai": s.get("research_ai", ""), "writing_ai": s.get("writing_ai", ""),
                        "review_ai": s.get("review_ai", ""),
                    })
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.cache_resource.clear(); st.rerun()

    st.divider()
    # ── 계산기 목록 / 관리 ──
    st.subheader("🧮 등록된 계산기")
    try:
        calcs = SW.list_calculators(cfg)
    except Exception as e:
        calcs = []
        st.error(f"계산기 목록 조회 실패: {e}")
    if not calcs:
        st.caption("등록된 계산기 없음")
    for c in calcs:
        cid = c.get("id", "")
        with st.expander(f"🧮 {c.get('name','(이름없음)')} — {c.get('category','')} ({c.get('status','')})"):
            st.write(c.get("seo_desc", ""))
            if st.button("🗑️ 삭제", key=f"cdel_{cid}"):
                ok, msg = SW.delete_calculator(cfg, cid)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()

# ══════════════════════════════════════════════════════════════
# 탭: 🧮 Calculator Builder (계산기 CRUD — CalculatorRepository 경유)
# ══════════════════════════════════════════════════════════════
elif tab == "🧮 Calculator Builder":
    st.title("🧮 Calculator Builder")
    st.caption("계산기를 코드 수정 없이 생성/수정/상태변경 (CalculatorRepository 경유)")
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    repo = CalculatorRepository(get_db_adapter(cfg))

    ab1, ab2 = st.columns(2)
    if ab1.button("🌱 CalcMate 초기 5종 시드"):
        try:
            from modules.calculator_seed import seed_all
            r = seed_all(cfg)
            st.success(f"시드 완료 — 템플릿 {r['templates']}, 계산기 {r['calculators']}"); st.rerun()
        except Exception as e:
            st.error(f"시드 실패(시트 권한 확인): {e}")
    if ab2.button("▶ 계산기 글 1건 생성(SEO+CTA)"):
        try:
            from modules.calculator_pipeline import run_calculator_once
            with st.spinner("키워드→SEO→본문→계산기 위젯 생성 중..."):
                s = run_calculator_once(cfg, max_count=1)
            st.success(f"생산 {s.get('produced',0)}건 (발행대기 포함). 상세는 작업보드/오류로그 참고.")
        except Exception as e:
            st.error(f"생성 실패: {e}")

    # ── 품질보류 재평가(HOLD Re-evaluate) ──────────────────────────
    # 자동 재평가(품질 서명 변경 시 다음 스케줄에서 자동 재도전)와 별개로, 지금 즉시
    # "무엇이 재도전 대상인지" 확인/실행하는 운영 도구.
    with st.expander("♻️ 품질보류 재평가 (legal/게이트/프롬프트 변경 반영)"):
        st.caption("품질 서명이 바뀐 품질보류 글을 재도전 대상으로 집계합니다. "
                   "'재평가 확인'은 리포트만(비용 0), '재도전 즉시 실행'은 재생성(API 비용)까지 수행.")
        rc1, rc2 = st.columns(2)
        if rc1.button("🔍 재평가 확인 (리포트)", key="reeval_report"):
            try:
                from modules.calculator_pipeline import reevaluate_holds
                res = reevaluate_holds(cfg, apply=False)
                st.success(f"품질보류 {res['holds']}건 · 재도전 {len(res['released'])}건 · "
                           f"유지 {len(res['blocked'])}건 · 이미발행(정리대상) {len(res.get('already_published',[]))}건 · "
                           f"legal 입력필요 {len(res['legal_pending'])}건")
                if res["released"]:
                    st.write("**재도전 대상(released):**")
                    for it in res["released"]:
                        st.write(f"- {it['name']} (`{it['old']}`→`{it['new']}`)")
                if res.get("already_published"):
                    st.write("**이미 발행됨(옛 HOLD 정리 대상 — '재도전 즉시 실행' 시 재처리완료):**")
                    for it in res["already_published"]:
                        st.write(f"- {it['name']}")
                if res["legal_pending"]:
                    st.write("**legal_basis 입력 필요:**")
                    for it in res["legal_pending"]:
                        st.write(f"- {it['name']} (slug=`{it['slug']}`)")
            except Exception as e:
                st.error(f"재평가 실패: {e}")
        if rc2.button("▶ 재도전 즉시 실행 (재생성)", key="reeval_apply"):
            try:
                from modules.calculator_pipeline import reevaluate_holds
                with st.spinner("재도전 대상 재생성 중(키워드→SEO→본문→품질검수)..."):
                    res = reevaluate_holds(cfg, apply=True)
                st.success(f"재도전 {len(res['released'])}건 → 생산 {res.get('produced',0)}건 · "
                           f"옛 HOLD 정리(재처리완료) {res.get('resolved',0)}건. 상세는 작업보드/오류로그 참고.")
            except Exception as e:
                st.error(f"재생성 실패: {e}")
    st.divider()
    try:
        calcs = repo.get_all()
    except Exception as e:
        calcs = []
        st.error(f"계산기 목록 조회 실패(시트 권한 확인): {e}")

    options = ["+ 신규 생성"] + [f"{c.get('name','?')} ({c.get('id','')})" for c in calcs]
    sel = st.selectbox("대상 선택", options, key="cb_sel")
    editing = calcs[options.index(sel) - 1] if sel != "+ 신규 생성" else None

    def _v(k, d=""):
        return (editing or {}).get(k, d)

    c1, c2 = st.columns(2)
    name = c1.text_input("계산기명 *", value=_v("name"), key="cb_name")

    # Slug 자동생성: 편집 대상 전환 시 리셋, 신규 생성 + 공백이면 이름에서 자동생성
    _cb_editing_id = (editing or {}).get("id") or "__new__"
    if st.session_state.get("_cb_prev_editing_id") != _cb_editing_id:
        st.session_state["_cb_prev_editing_id"] = _cb_editing_id
        st.session_state["cb_slug"] = _v("slug")
    if not editing and not st.session_state.get("cb_slug") and name:
        _auto = generate_slug(name)
        if _auto:
            st.session_state["cb_slug"] = _auto

    slug = c2.text_input("slug (자동생성 — 수정 가능)", key="cb_slug")
    c3, c4 = st.columns(2)
    category = c3.text_input("category", value=_v("category"), key="cb_cat")
    ctype = c4.text_input("calculator_type", value=_v("calculator_type", "general"), key="cb_type")
    seo_title = st.text_input("seo_title", value=_v("seo_title"), key="cb_st")
    seo_desc = st.text_area("seo_desc", value=_v("seo_desc"), key="cb_sd")
    formula = st.text_area("formula", value=_v("formula"), key="cb_f")
    faq = st.text_area("faq", value=_v("faq"), key="cb_faq")
    insch = st.text_area("input_schema (JSON)",
                         value=_v("input_schema", '{"hourly_wage":"number","weekly_hours":"number"}'), key="cb_in")
    outsch = st.text_area("output_schema (JSON)",
                          value=_v("output_schema", '{"weekly_allowance":"number"}'), key="cb_out")
    stt = _v("status", "draft")
    status = st.selectbox("status", ["draft", "active", "inactive"],
                          index=["draft", "active", "inactive"].index(stt) if stt in ["draft", "active", "inactive"] else 0,
                          key="cb_status")
    if st.button("💾 저장", type="primary", key="cb_save"):
        if not name.strip():
            st.error("계산기명은 필수입니다.")
        else:
            row = {"name": name, "slug": slug, "category": category, "calculator_type": ctype,
                   "seo_title": seo_title, "seo_desc": seo_desc, "formula": formula, "faq": faq,
                   "input_schema": insch, "output_schema": outsch, "status": status}
            try:
                if editing:
                    repo.update(editing.get("id"), row); st.success("✅ 수정 완료")
                else:
                    repo.save(row); st.success("✅ 생성 완료")
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패(시트 권한 확인): {e}")
    if editing:
        st.divider(); st.caption(f"상태 변경 (현재: {editing.get('status')})")
        sc = st.columns(3)
        for i, s in enumerate(["draft", "active", "inactive"]):
            if sc[i].button(f"→ {s}", key=f"cb_s_{s}"):
                try:
                    repo.update(editing.get("id"), {"status": s}); st.success(f"상태 → {s}"); st.rerun()
                except Exception as e:
                    st.error(f"실패: {e}")

# ══════════════════════════════════════════════════════════════
# 탭: 🧮 계산기 관리 (앱 생성 + GitHub Pages 배포)
# ══════════════════════════════════════════════════════════════
elif tab == "🧮 계산기 관리":
    st.title("🧮 계산기 관리")
    st.caption("계산기 메타데이터로 정적 앱(HTML/CSS/JS) 생성 → GitHub Pages 배포 → URL/상태 관리. (모든 접근 Repository 경유)")
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    from modules import app_generator as AG, github_deployer as GH, formula_engine as FE
    repo = CalculatorRepository(get_db_adapter(cfg))

    if st.button("🌱 기본 계산기 5종 시드"):
        from modules.calculator_seeder import seed_default_calculators
        r = seed_default_calculators(cfg)
        if "error" in r:
            st.error(f"시드 실패(시트 권한 확인): {r['error']}")
        else:
            st.success(f"생성 {r.get('created',0)} / 스킵 {r.get('skipped',0)}"); st.rerun()

    st.caption("배포 설정: " + ("✅ GITHUB_TOKEN 있음" if GH.is_configured(cfg)
               else "⚠️ GITHUB_TOKEN 미설정 — 배포 비활성(로컬 미리보기만 가능)"))
    try:
        calcs = repo.get_all()
    except Exception as e:
        calcs = []
        st.error(f"계산기 조회 실패(시트 권한 확인): {e}")
    if not calcs:
        st.info("등록된 계산기 없음 — 위 시드 버튼 또는 🧮 Calculator Builder / 🏭 App Factory로 등록")

    def _inline(files):
        # 공통 렌더 함수 1개 공유(대시보드 미리보기 = WordPress 삽입 동일 산출물)
        from modules.app_generator import render_inline_calculator
        return render_inline_calculator(files)

    _just_saved = st.session_state.get("af_just_saved_name")
    for c in calcs:
        cid = c.get("id", "")
        url = c.get("published_url", "")
        status_icon = "🟢" if str(c.get("status")).lower() == "active" else "⚪"
        _auto_expand = bool(_just_saved) and c.get("name") == _just_saved
        with st.expander(f"{status_icon} {c.get('name','(이름없음)')} — {c.get('status','')}"
                         + (f" · 배포됨" if url else ""), expanded=_auto_expand):
            if url:
                st.markdown(f"**배포 URL:** [{url}]({url})")
            # 수식 편집(검증 후 저장)
            cur_formula = c.get("formula", "")
            new_formula = st.text_input("수식(formula)", value=str(cur_formula), key=f"cm_f_{cid}")
            _raw_ins = c.get("input_schema")
            try:
                import json as _json
                ins = _raw_ins if isinstance(_raw_ins, dict) else (_json.loads(_raw_ins) if _raw_ins else {})
            except Exception:
                ins = {}
            if st.button("💾 수식 저장(검증)", key=f"cm_fs_{cid}"):
                ok, msg = FE.validate_formula(new_formula, ins)
                if ok:
                    FE.save_formula(cfg, cid, new_formula); st.success("수식 저장 완료"); st.rerun()
                else:
                    st.error(f"수식 검증 실패: {msg}")

            # ── AI 자동 생성 ──
            st.markdown("**🤖 AI 자동 생성**")
            g = st.columns(5)
            if g[0].button("SEO 생성", key=f"ag_seo_{cid}"):
                from modules import calculator_seo_generator as SEO
                with st.spinner("SEO 생성 중..."):
                    repo.update_generated(cid, {"seo_title": SEO.generate_seo_title(cfg, c),
                                                "seo_description": SEO.generate_meta_description(cfg, c)})
                st.success("SEO 생성·저장"); st.rerun()
            if g[1].button("FAQ 생성", key=f"ag_faq_{cid}"):
                from modules.calculator_faq_generator import generate_faq
                import json as _j
                with st.spinner("FAQ 생성 중..."):
                    repo.update_generated(cid, {"faq": _j.dumps(generate_faq(cfg, c), ensure_ascii=False)})
                st.success("FAQ 생성·저장"); st.rerun()
            if g[2].button("본문 생성", key=f"ag_art_{cid}"):
                from modules.calculator_content_generator import generate_article
                with st.spinner("본문 생성 중..."):
                    repo.update_generated(cid, {"article_content": generate_article(cfg, c)})
                st.success("본문 생성·저장"); st.rerun()
            if g[3].button("이미지 프롬프트", key=f"ag_img_{cid}"):
                from modules import calculator_image_prompt_generator as IMG
                with st.spinner("이미지 프롬프트 생성 중..."):
                    repo.update_generated(cid, {"image_prompt_thumbnail": IMG.generate_thumbnail_prompt(cfg, c),
                                                "image_prompt_body": IMG.generate_body_prompt(cfg, c)})
                st.success("이미지 프롬프트 생성·저장"); st.rerun()
            if g[4].button("⚡ 전체 자동생성", key=f"ag_all_{cid}", type="primary"):
                from modules.calculator_content_generator import auto_generate_all
                with st.spinner("SEO→FAQ→본문→이미지→저장 진행 중... (수십 초)"):
                    r = auto_generate_all(cfg, c, save=True)
                (st.success if r.get("_saved") else st.warning)(
                    f"전체 자동생성 완료 (저장 {'성공' if r.get('_saved') else '실패: '+r.get('_save_error','')})")
                st.rerun()

            # 생성 결과 미리보기
            if c.get("seo_title") or c.get("article_content"):
                with st.expander("👁 생성 결과 미리보기"):
                    st.write(f"**SEO 제목:** {c.get('seo_title','-')}")
                    st.write(f"**메타설명:** {c.get('seo_description', c.get('seo_desc','-'))}")
                    if c.get("faq"):
                        import json as _j
                        try:
                            fq = _j.loads(c["faq"]) if isinstance(c["faq"], str) else c["faq"]
                            st.write(f"**FAQ {len(fq)}개:**")
                            for f in fq[:10]:
                                st.markdown(f"- **{f.get('question', f.get('q',''))}** — {f.get('answer', f.get('a',''))}")
                        except Exception:
                            pass
                    if c.get("image_prompt_thumbnail"):
                        st.caption(f"썸네일 프롬프트: {c.get('image_prompt_thumbnail')}")
                        st.caption(f"본문 프롬프트: {c.get('image_prompt_body','')}")
                    if c.get("article_content"):
                        st.markdown("**본문 미리보기:**")
                        st.markdown(c["article_content"][:1500] + (" …" if len(c["article_content"]) > 1500 else ""),
                                    unsafe_allow_html=True)
                    if c.get("generated_at"):
                        st.caption(f"생성 시각: {c.get('generated_at')}")

            files = AG.generate_calculator(c, cfg)
            if not files["_formula_valid"]:
                st.warning(f"수식 경고: {files['_formula_msg']}")
            with st.expander("🔎 앱 미리보기"):
                import streamlit.components.v1 as components
                components.html(_inline(files), height=440, scrolling=True)

            b = st.columns(4)
            deploy_label = "🚀 재배포" if url else "🚀 배포"
            if b[0].button(deploy_label, key=f"cm_dep_{cid}", disabled=not GH.is_configured(cfg)):
                ok, res = GH.deploy_app(cfg, files,
                                        repo=cfg.get("GITHUB_REPO", "salarymate-calculators"),
                                        subdir=c.get("slug", cid))
                if ok:
                    repo.publish(cid, res); st.success(f"배포 완료: {res}"); st.rerun()
                else:
                    st.error(res)
            if b[1].button("⏸ 상태토글", key=f"cm_tg_{cid}"):
                repo.update(cid, {"status": "inactive" if str(c.get("status")).lower() == "active" else "active"})
                st.rerun()
            if b[2].button("📥 파일 저장", key=f"cm_dl_{cid}"):
                import os
                # 계산기별 폴더 생성 후 3파일 저장(옵션 A). 상대경로(style.css/script.js) 유지 →
                # 로컬 더블클릭·GitHub Pages 구조 동일. app_generator/템플릿/CSS는 무변경.
                slug = str(c.get("slug", cid)).strip().replace("/", "_").replace("\\", "_").replace("..", "_") or cid
                outdir = BASE / "data" / "workspace" / slug
                os.makedirs(outdir, exist_ok=True)
                for fn in ("index.html", "style.css", "script.js"):
                    (outdir / fn).write_text(files[fn], encoding="utf-8")
                st.success(f"✅ 저장: data/workspace/{slug}/ (index.html · style.css · script.js). "
                           f"index.html 더블클릭 시 CSS/JS 상대경로 연결 정상 — GitHub Pages와 동일 구조.")
            if b[3].button("🗑 삭제", key=f"cm_del_{cid}"):
                repo.delete(cid); st.rerun()

    # 자동펼침 플래그는 한 번 사용 후 제거(다음 렌더부터는 평소처럼 접힌 채)
    if _just_saved:
        st.session_state["af_just_saved_name"] = None

    # ── 사이트 페이지 배포 ─────────────────────────────────────────
    st.divider()
    st.subheader("🌐 사이트 페이지 배포")
    st.caption("메인 홈 + 소개 / 개인정보처리방침 / 이용약관 / 문의하기 페이지를 GitHub Pages에 배포합니다.")

    from modules import site_generator as SG
    site_pages = SG.generate_all(cfg)
    page_list = [p for p in site_pages if not p.endswith(".css")]

    with st.expander("📄 생성 페이지 미리보기"):
        preview_page = st.selectbox("페이지 선택", page_list,
                                    key="site_preview_page")
        if preview_page:
            import streamlit.components.v1 as _comp
            _comp.html(site_pages[preview_page], height=500, scrolling=True)

    col_a, col_b = st.columns(2)
    if col_a.button("🚀 사이트 페이지 배포",
                    disabled=not GH.is_configured(cfg),
                    key="cm_site_deploy"):
        with st.spinner("사이트 페이지 업로드 중..."):
            _repo_name = cfg.get("GITHUB_REPO", "calcmate-calculators")
            ok_r, full_name = GH.create_repo(cfg, _repo_name)
            if not ok_r:
                st.error(f"저장소 생성 실패: {full_name}")
            else:
                _ok, _fail = 0, []
                for _path, _content in site_pages.items():
                    try:
                        GH._put_file(cfg, full_name, _path, _content)
                        _ok += 1
                    except Exception as _e:
                        _fail.append(f"{_path}: {_e}")
                GH._enable_pages(cfg, full_name)
                if _fail:
                    st.warning(f"배포 완료({_ok}개) — 실패: {'; '.join(_fail)}")
                else:
                    _site_url = cfg.get("SITE_URL", "https://calcmate.kr")
                    st.success(f"✅ {_ok}개 페이지 배포 완료 → {_site_url}/")

    if col_b.button("💾 로컬 저장", key="cm_site_local"):
        import os
        _out = BASE / "data" / "workspace" / "_site"
        for _path, _content in site_pages.items():
            _fp = _out / _path
            os.makedirs(_fp.parent, exist_ok=True)
            _fp.write_text(_content, encoding="utf-8")
        st.success(f"✅ data/workspace/_site/ 에 {len(site_pages)}개 파일 저장")

# ══════════════════════════════════════════════════════════════
# 탭: 🏭 App Factory (계산기 자동 생성)
# ══════════════════════════════════════════════════════════════
elif tab == "🏭 App Factory":
    st.title("🏭 App Factory")
    st.caption("자동 생성 흐름: GPT 스펙 → Claude 코드(HTML) → GPT SEO/FAQ/초안 → Gemini 이미지 프롬프트 → 저장")
    from modules import app_factory as AF

    # 🔍 키워드 기반 아이디어 제안 — 키워드를 중심으로 이름/카테고리/설명 자동채움.
    k1, k2 = st.columns([3, 1])
    af_keyword = k1.text_input("키워드로 아이디어 생성",
                               placeholder="예: 육아휴직, 4대보험, 연차",
                               key="af_keyword")
    if k2.button("🔍 키워드로 제안", key="af_suggest_kw"):
        with st.spinner("키워드 기반 아이디어 생성 중..."):
            try:
                idea = AF.suggest_idea(cfg, keyword=af_keyword)
                st.session_state["af_name"] = idea.get("name", "")
                st.session_state["af_cat"] = idea.get("category", "")
                st.session_state["af_desc"] = idea.get("desc", "")
            except Exception as e:
                st.warning(f"AI 제안 실패(직접 입력해주세요): {e}")

    # 💡 AI 아이디어 제안(수동 버튼) — 클릭 시에만 입력칸 자동채움. 위젯 키를 직접 세팅해야
    # 재클릭 시에도 갱신됨(text_input의 value= 방식은 위젯 생성 후 무시되는 Streamlit 제약 회피).
    if st.button("💡 AI 아이디어 제안", key="af_suggest"):
        with st.spinner("AI가 새 계산기 아이디어를 찾는 중..."):
            try:
                idea = AF.suggest_idea(cfg)
                st.session_state["af_name"] = idea.get("name", "")
                st.session_state["af_cat"] = idea.get("category", "")
                st.session_state["af_desc"] = idea.get("desc", "")
            except Exception as e:
                st.warning(f"AI 제안 실패(직접 입력해주세요): {e}")

    c1, c2 = st.columns(2)
    af_name = c1.text_input("계산기명 *", placeholder="퇴직금 계산기", key="af_name")
    af_cat = c2.text_input("카테고리", placeholder="노무/급여", key="af_cat")
    af_desc = st.text_area("설명", placeholder="예: 근속연수와 평균임금으로 퇴직금 계산", key="af_desc")
    if st.button("🏭 자동 생성", type="primary", key="af_gen"):
        if not af_name.strip():
            st.error("계산기명은 필수입니다.")
        else:
            with st.spinner("AI가 계산기를 생성 중입니다... (수십 초)"):
                try:
                    st.session_state["af_result"] = AF.generate_app(cfg, af_name, af_cat, af_desc)
                except Exception as e:
                    st.session_state["af_result"] = None
                    st.error(f"생성 실패: {e}")
    app = st.session_state.get("af_result")
    if app:
        st.success(f"생성 완료 — 토큰 {app['_tokens']}")
        if not app.get("_formula_valid", True):
            st.error(f"⚠️ 수식 검증 실패: {app.get('_formula_msg', '')}\n\n(저장은 가능하나 생성물 계산이 정상 동작하지 않을 수 있습니다. 운영자 확인 필요.)")
        st.write("**단계:** " + " → ".join(f"{s[0]}({s[1]})" for s in app["_steps"]))
        m = st.columns(3)
        m[0].metric("HTML 길이", len(app["html"]))
        m[1].metric("FAQ 수", len(app["faq"]) if isinstance(app["faq"], list) else 0)
        m[2].metric("계산기 유형", app["calculator_type"])
        st.text_input("SEO 제목", app["seo_title"], disabled=True, key="af_seo")
        with st.expander("입력/출력 스키마"):
            st.json({"input": app["input_schema"], "output": app["output_schema"]})
        with st.expander("HTML 코드"):
            st.code(app["html"][:4000], language="html")
        with st.expander("FAQ / 블로그 초안"):
            st.write(app["faq"]); st.write(app.get("blog_draft", ""))
        if app["html"]:
            with st.expander("🔎 실제 렌더 미리보기"):
                import streamlit.components.v1 as components
                components.html(app["html"], height=420, scrolling=True)
        # Slug 자동생성: 새 앱 생성 시 또는 af_slug 공백이면 자동완성
        _af_auto_slug = generate_slug(app.get("name", ""))
        if app.get("name") != st.session_state.get("_af_last_slug_for"):
            st.session_state["af_slug"] = _af_auto_slug
            st.session_state["_af_last_slug_for"] = app.get("name", "")
        elif not st.session_state.get("af_slug") and _af_auto_slug:
            st.session_state["af_slug"] = _af_auto_slug
        af_slug = st.text_input(
            "영문 slug * (폴더·URL·내부 식별자 — 저장 후 변경 불가)",
            key="af_slug",
            help="영문 소문자·숫자·하이픈만. 한글/공백 불가. 대시보드 표시는 계속 한글 이름(name)을 사용합니다.")
        if st.button("💾 calculators + app_templates 저장", type="primary", key="af_save"):
            import re as _re_slug
            slug_in = (af_slug or "").strip().lower()
            if not _re_slug.match(r"^[a-z0-9][a-z0-9-]*$", slug_in):
                st.error("영문 slug를 입력하세요 — 소문자·숫자·하이픈만 (예: annual-tax-settlement). "
                         "한글/공백/대문자 불가.")
            else:
                ok, msg = AF.save_app(cfg, app, slug=slug_in)
                if ok:
                    st.session_state["af_result"] = None
                    st.session_state["af_just_saved_name"] = app.get("name", "")
                    st.session_state["nav_group"] = "🧮 Calculator"
                    st.session_state["sub_🧮 Calculator"] = "🧮 계산기 관리"
                    st.success(f"{msg} — 계산기 관리로 이동합니다.")
                    st.rerun()
                else:
                    st.error(msg)

# ══════════════════════════════════════════════════════════════
# 탭: 💬 AI Workspace (대시보드 내 AI 대화 + 파일/데이터 도구)
# ══════════════════════════════════════════════════════════════
elif tab == "💬 AI Workspace":
    st.title("💬 AI Workspace")
    from modules import ai_workspace as WS
    role_map = {"총괄 (GPT)": "orchestrator", "코드 (Claude)": "code", "리서치 (Gemini)": "research"}
    role_label = st.selectbox("역할 / 모델", list(role_map.keys()), key="ws_role")
    role = role_map[role_label]

    with st.expander("📎 컨텍스트 첨부 (선택)"):
        try:
            files = WS.list_project_files()
        except Exception:
            files = []
        attach_file = st.selectbox("프로젝트 파일(읽기)", ["(없음)"] + files, key="ws_file")
        attach_repo = st.selectbox("Repository/시트 데이터", ["(없음)", "sites", "calculators", "articles", "templates"], key="ws_repo")
        attach_struct = st.checkbox("프로젝트 구조 요약", key="ws_struct")

    if "ws_msgs" not in st.session_state:
        st.session_state["ws_msgs"] = []
    for msg in st.session_state["ws_msgs"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("메시지 입력 (예: 퇴직금 계산기 HTML 만들어줘 / main.py 구조 분석해줘)")
    if prompt:
        ctx = ""
        try:
            if attach_file != "(없음)":
                ctx += f"# 파일: {attach_file}\n{WS.read_project_file(attach_file)}\n\n"
            if attach_repo != "(없음)":
                ctx += f"# {attach_repo} 데이터(최대 20행)\n{str(WS.query_repo(cfg, attach_repo)[:20])}\n\n"
            if attach_struct:
                ctx += f"# 프로젝트 구조\n{WS.analyze_structure()['by_dir']}\n\n"
        except Exception as e:
            ctx += f"(컨텍스트 첨부 실패: {e})"
        st.session_state["ws_msgs"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                try:
                    reply, model, tok = WS.chat(cfg, role, st.session_state["ws_msgs"], ctx)
                except Exception as e:
                    reply, model, tok = f"오류: {e}", "", 0
            st.markdown(reply)
            st.caption(f"{model} · {tok} tokens")
        st.session_state["ws_msgs"].append({"role": "assistant", "content": reply})

    st.divider()
    with st.expander("💾 코드/파일 저장 도구"):
        st.caption("기본은 샌드박스(data/workspace/)에 저장. 프로젝트 파일 덮어쓰기는 원본 백업 후 확인 시에만.")
        fname = st.text_input("파일명", "generated.html", key="ws_save_name")
        fcontent = st.text_area("내용", height=200, key="ws_save_content")
        if st.button("샌드박스 저장", key="ws_sb_save"):
            if fcontent.strip():
                st.success(f"저장: {WS.write_workspace_file(fname, fcontent)}")
            else:
                st.error("내용이 비어 있습니다.")
        st.markdown("---")
        st.caption("⚠️ 고급: 프로젝트 파일 덮어쓰기 (원본 자동 백업)")
        tgt = st.text_input("대상 경로 (예: data/workspace/x.py)", key="ws_tgt")
        confirm = st.checkbox("이 경로 덮어쓰기를 확인합니다", key="ws_confirm")
        if st.button("프로젝트 파일 저장", key="ws_proj_save"):
            if confirm and tgt.strip() and fcontent.strip():
                try:
                    st.success(f"저장(백업됨): {WS.write_project_file(tgt, fcontent)}")
                except Exception as e:
                    st.error(f"실패: {e}")
            else:
                st.error("대상 경로/내용/확인 체크가 필요합니다.")
    if st.button("🗑 대화 초기화", key="ws_clear"):
        st.session_state["ws_msgs"] = []; st.rerun()

# ══════════════════════════════════════════════════════════════
# 탭: 📊 AI Pipeline Monitor
# ══════════════════════════════════════════════════════════════
elif tab == "📊 AI Pipeline":
    st.title("📊 AI Pipeline Monitor")
    st.caption("pipeline.log 기반 단계 상태(비침습적). 파이프라인 실행 중 자동 반영.")
    from modules.pipeline_status import get_pipeline_state
    ps = get_pipeline_state(cfg)
    COLOR = {"pending": "🟡", "running": "🔵", "completed": "🟢", "error": "🔴"}
    cols = st.columns(len(ps["stages"]))
    for col, s in zip(cols, ps["stages"]):
        with col.container(border=True):
            st.markdown(f"### {COLOR.get(s['status'], '⬜')}")
            st.markdown(f"**{s['name']}**")
            st.caption(f"모델: {s['model']}")
            st.caption(f"상태: {s['status']}")
    st.divider()
    m = st.columns(3)
    m[0].metric("오늘 비용", f"${ps['cost_today']:.4f}")
    m[1].metric("오늘 토큰", f"{ps['tokens_today']:,}")
    m[2].metric("실행 상태", "🔴 오류" if ps["has_error"] else ("✅ 완료/대기" if ps["finished"] else "🔵 진행중"))
    if ps["model_costs"]:
        st.subheader("오늘 모델별 비용")
        import pandas as pd
        st.dataframe(pd.DataFrame([{"모델": k, "비용($)": v} for k, v in ps["model_costs"].items()]),
                     hide_index=True, use_container_width=True)
    st.subheader("최근 로그")
    st.code("\n".join(ps["last_lines"]) or "(로그 없음)", language="text")

# ══════════════════════════════════════════════════════════════
# 탭: 🤖 AI Assistant (운영비서 — 채팅/파일도구/메모리/태스크/분석)
# ══════════════════════════════════════════════════════════════
elif tab == "🤖 AI Assistant":
    st.title("🤖 AI Assistant — 운영비서")
    st.caption("채팅으로 프로젝트 분석·개선·수정. 파일 쓰기는 승인 후에만, 워크스페이스 내부 한정(삭제/시스템명령 불가).")
    from modules import ai_assistant as AS

    model_label = st.selectbox("모델", list(AS.CHAT_MODELS.keys()), key="asst_model")
    qc = st.columns(4)
    preset_labels = ["현재 프로젝트 분석해", "App Factory 분석해", "문제점 찾아", "개선안 제안해"]
    quick = None
    for i, lab in enumerate(preset_labels):
        if qc[i].button(lab, key=f"asst_qc_{i}"):
            quick = lab

    if "asst_msgs" not in st.session_state:
        st.session_state["asst_msgs"] = []
    for m in st.session_state["asst_msgs"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    prompt = st.chat_input("명령/질문 (예: config 수정해, 새 계산기 추가해, 최근 오류 분석해)") or quick
    if prompt:
        st.session_state["asst_msgs"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                try:
                    reply, model, tok = AS.chat(cfg, model_label, st.session_state["asst_msgs"])
                except Exception as e:
                    reply, model, tok = f"오류: {e}", "", 0
            st.markdown(reply)
            st.caption(f"{model} · {tok} tokens")
        st.session_state["asst_msgs"].append({"role": "assistant", "content": reply})

    st.divider()
    # ── 파일 수정/생성 (승인 게이트) ──
    with st.expander("📝 파일 수정/생성 (변경 미리보기 → 승인 후 저장)"):
        st.caption("워크스페이스 내부만. write 시 원본 자동 백업(data/assistant/backups/).")
        fpath = st.text_input("대상 경로", "data/workspace/example.txt", key="asst_path")
        fcontent = st.text_area("새 내용 (AI 답변에서 복사 가능)", height=200, key="asst_content")
        if st.button("🔍 변경 미리보기", key="asst_preview"):
            try:
                st.session_state["asst_diff"] = AS.propose_diff(fpath, fcontent)
            except Exception as e:
                st.error(str(e))
        diff = st.session_state.get("asst_diff")
        if diff and diff["path"] == fpath:
            st.write(f"{'✏️ 덮어쓰기' if diff['exists'] else '🆕 신규 생성'} — "
                     f"기존 {diff['old_len']}자 → 새 {diff['new_len']}자")
            if diff["exists"]:
                with st.expander("기존 내용 보기"):
                    st.code(diff["old"][:3000])
            c1, c2 = st.columns(2)
            if c1.button("✅ 승인 후 저장", type="primary", key="asst_apply"):
                try:
                    path = AS.write_file(fpath, fcontent) if diff["exists"] else AS.create_file(fpath, fcontent)
                    st.success(f"저장 완료: {path}")
                    st.session_state.pop("asst_diff", None)
                except Exception as e:
                    st.error(f"저장 실패: {e}")
            if c2.button("취소", key="asst_cancel"):
                st.session_state.pop("asst_diff", None); st.rerun()

    # ── 워크스페이스 탐색/읽기 ──
    with st.expander("📂 워크스페이스 탐색/읽기"):
        d = st.text_input("디렉터리", ".", key="asst_ls")
        try:
            for it in AS.list_directory(d):
                st.caption(("📁 " if it["type"] == "dir" else "📄 ") + it["path"])
        except Exception as e:
            st.error(str(e))
        rf = st.text_input("파일 읽기 경로", "modules/app_factory.py", key="asst_rf")
        if st.button("읽기", key="asst_rfb"):
            try:
                st.code(AS.read_file(rf, 8000))
            except Exception as e:
                st.error(str(e))

    # ── Memory ──
    with st.expander("🧠 Memory (운영규칙 / TODO / 개발기록)"):
        mem = AS.load_memory()
        k = st.selectbox("종류", ["rules", "todo", "dev_log"], key="asst_mk")
        nt = st.text_input("추가 내용", key="asst_mt")
        if st.button("메모리 추가", key="asst_ma") and nt.strip():
            AS.add_memory(k, nt); st.rerun()
        for kk in ["rules", "todo", "dev_log"]:
            items = mem.get(kk, [])
            if items:
                st.markdown(f"**{kk}** ({len(items)})")
                for it in items[-10:]:
                    st.caption("• " + it["text"])

    # ── Task (Lite) ──
    with st.expander("✅ Task (Lite: 상태만)"):
        nt2 = st.text_input("새 태스크", key="asst_tt")
        if st.button("태스크 추가", key="asst_ta") and nt2.strip():
            AS.add_task(nt2); st.rerun()
        for t in AS.load_tasks()[-15:]:
            cols = st.columns([3, 2])
            cols[0].caption(t["title"])
            ns = cols[1].selectbox("상태", AS.TASK_STATUS,
                                   index=AS.TASK_STATUS.index(t["status"]) if t["status"] in AS.TASK_STATUS else 0,
                                   key="asst_ts_" + t["id"], label_visibility="collapsed")
            if ns != t["status"]:
                AS.set_task_status(t["id"], ns); st.rerun()

    if st.button("🗑 대화 초기화", key="asst_clear"):
        st.session_state["asst_msgs"] = []; st.rerun()

# ══════════════════════════════════════════════════════════════
# 탭: 🧠 전략회의실 (AI 운영 분석)
# ══════════════════════════════════════════════════════════════
elif tab == "🧠 전략회의실":
    st.title("🧠 전략회의실")
    st.caption(
        f"분석 모델: `{cfg.get('ORCHESTRATOR_PROVIDER','openai')} / "
        f"{cfg.get('MODEL_ORCHESTRATOR','gpt-4o')}` · "
        f"AI가 최근 운영 데이터를 분석해 카테고리·RSS·발행시간·수익화 전략을 추천합니다 (실행만, 직접 적용 안 함)."
    )

    enabled = cfg.get("ENABLE_STRATEGY_ROOM", True)
    if not enabled:
        st.warning("⚠️ `ENABLE_STRATEGY_ROOM` 설정이 꺼져 있습니다. '🔧 설정 → 운영 설정'에서 켜주세요.")

    if st.button("▶ 전략회의실 실행", type="primary", disabled=not enabled):
        with st.spinner("AI가 최근 운영 데이터를 분석 중입니다..."):
            # ── 운영 데이터 수집 (가능한 범위, 실패해도 빈 값으로 진행) ──
            analytics = {}
            try:
                posts = cached_posts()
                published = [p for p in posts if p.get("상태값") in ("발행완료", "검수대기")]
                published.sort(key=lambda x: x.get("발행일시", ""), reverse=True)
                analytics["total_published"] = len(published)
                analytics["recent_posts"] = [
                    {"title": p.get("최종추천제목", ""), "url": p.get("발행 URL", ""),
                     "date": p.get("발행일시", "")}
                    for p in published[:7]
                ]
            except Exception as e:
                st.info(f"운영 데이터 일부 수집 실패 — 빈 값으로 진행합니다: {e}")

            try:
                from modules.strategy_room import run_strategy_room
                st.session_state["strategy_result"] = run_strategy_room(analytics, cfg)
            except Exception as e:
                st.session_state["strategy_result"] = {}
                st.error(f"전략회의실 실행 중 오류: {e}")

    result = st.session_state.get("strategy_result")
    if result is not None:
        if not result:
            st.error(
                "전략회의실이 빈 결과를 반환했습니다. "
                "LLM이 올바른 JSON을 반환하지 못했거나 설정이 꺼져 있을 수 있습니다. "
                "잠시 후 다시 실행해 보세요. ('📡 실시간 로그'에서 상세 확인 가능)"
            )
        else:
            st.divider()
            st.subheader("📝 요약")
            st.write(result.get("summary", "(요약 없음)"))

            ate = result.get("auto_topic_expansion_eligible", {}) or {}
            if ate:
                st.subheader("🚦 AUTO_TOPIC_EXPANSION 전환 조건")
                cols = st.columns(5)
                labels = [
                    ("애드센스 발행", "condition_1_adsense_post"),
                    ("게시물 수",     "condition_2_post_count"),
                    ("CTR",          "condition_3_ctr"),
                    ("긍정 추천",     "condition_4_positive_recommendation"),
                    ("전체 충족",     "all_met"),
                ]
                for col, (lab, key) in zip(cols, labels):
                    col.metric(lab, "✅" if ate.get(key) else "❌")

            def _show_list(title, items):
                st.subheader(title)
                if items:
                    st.write(items)
                else:
                    st.caption("추천 없음")

            _show_list("🆕 신규 카테고리 후보",   result.get("new_category_candidates", []))
            _show_list("📡 RSS 수집원 추천",      result.get("rss_recommendations", []))
            _show_list("♻️ 리라이팅 후보",        result.get("rewrite_candidates", []))
            _show_list("⏰ 최적 발행 시간대",      result.get("best_publish_time", []))

            st.subheader("💰 수익화 제안")
            mon = result.get("monetization_suggestions")
            st.write(mon if mon else "추천 없음 (ADSENSE_MODE=pre이면 비활성)")

            st.caption(f"사용 토큰: {result.get('_tokens', '-')}")
            with st.expander("🔧 원본 JSON 보기"):
                st.json(result)

# ══════════════════════════════════════════════════════════════
# 탭 5: 설정 ★ [팅김 버그 완치 검수 완료]
# ══════════════════════════════════════════════════════════════
elif tab == "🔧 설정":
    st.title("🔧 설정 관리")
    st.info("모든 모델 세팅을 마우스 클릭으로 제어하세요.")

    cfg_path = BASE / "config" / "config.yaml"

    with st.expander("🔑 AI API Keys", expanded=False):
        openai_key = st.text_input("OpenAI API Key", value=cfg.get("OPENAI_API_KEY",""), type="password", key="s_openai")
        claude_key = st.text_input("Claude API Key", value=cfg.get("CLAUDE_API_KEY",""), type="password", key="s_claude")
        gemini_key = st.text_input("Gemini API Key", value=cfg.get("GEMINI_API_KEY",""), type="password", key="s_gemini")

    # ── 1. 텍스트 AI 모델 설정 ──────────────────────────────
    with st.expander("🤖 최신 텍스트 AI 역할 및 모델 매칭", expanded=True):
        providers_list = ["openai", "claude", "gemini"]
        model_presets = {
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "claude": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
            "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"]
        }

        def render_model_selector(label, provider_val, current_model, key_prefix):
            st.markdown(f"**{label}**")
            col_p, col_m = st.columns(2)
            with col_p:
                p_idx = providers_list.index(provider_val) if provider_val in providers_list else 0
                chosen_provider = st.selectbox(f"{label} 제공사", providers_list, index=p_idx, key=f"{key_prefix}_prov", label_visibility="collapsed")
            with col_m:
                presets = model_presets.get(chosen_provider, ["gpt-4o"])
                # 현재 모델이 프리셋에 있으면 그 항목을, 없으면 첫 항목을 기본 선택
                m_idx = presets.index(current_model) if current_model in presets else 0
                    
                chosen_model = st.selectbox(f"{label} 모델명", presets, index=m_idx, key=f"{key_prefix}_model", label_visibility="collapsed")
            return chosen_provider, chosen_model

        orch_prov, orch_mod = render_model_selector("1. 전체 총괄 (Orchestrator)", cfg.get("ORCHESTRATOR_PROVIDER", "openai"), cfg.get("MODEL_ORCHESTRATOR", "gpt-4o"), "s_orch")
        plan_prov, plan_mod = render_model_selector("2. 키워드 기획 (Planner)", cfg.get("PLANNER_PROVIDER", "openai"), cfg.get("MODEL_PLANNER", "gpt-4o"), "s_plan")
        writ_prov, writ_mod = render_model_selector("3. 본문 초고 작성 (Writer)", cfg.get("WRITER_PROVIDER", "openai"), cfg.get("MODEL_WRITER", "gpt-4o"), "s_write")
        edit_prov, edit_mod = render_model_selector("4. SEO 교정 및 검수 (Editor)", cfg.get("EDITOR_PROVIDER", "claude"), cfg.get("MODEL_EDITOR", "claude-sonnet-4-6"), "s_edit")

        st.markdown("---")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            clean_mod = st.selectbox("뉴스 정리기 (Cleaner) 모델", model_presets["openai"], index=0, key="s_clean_mod")
        with col_s2:
            fb_mod = st.selectbox("교정 실패시 백업 (Fallback) 모델", model_presets["openai"], index=0, key="s_fb_mod")

    # ── 2. 🎨 이미지 생성 AI 설정 섹션 [팅김 방지 완벽 방어형 인덱싱 코드] ──────────────────────────────
    with st.expander("🎨 블로그 이미지 생성 AI 설정", expanded=True):
        st.markdown("### 썸네일 및 본문 삽입용 이미지 옵션")
        
        img_providers = ["free_pollinations", "gemini", "openai"]
        img_presets = {
            "free_pollinations": ["무료 이미지 엔진 (API키/결제 없음)"],
            "gemini": ["imagen-3.0-generate-002"],
            "openai": ["dall-e-3"]
        }
        
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            curr_img_prov = str(cfg.get("IMAGE_PROVIDER", "free_pollinations")).lower()
            # 팅김 원천 방지: 리스트에 존재하지 않는 값이 들어올 경우 무조건 0번(무료엔진)으로 매핑
            img_prov_idx = img_providers.index(curr_img_prov) if curr_img_prov in img_providers else 0
            image_provider = st.selectbox("이미지 AI 제공사 (구글 무료 계정은 'free_pollinations' 필수)", img_providers, index=img_prov_idx, key="s_img_prov")
        with col_img2:
            curr_img_mod = cfg.get("MODEL_IMAGE", "")
            img_models = img_presets.get(image_provider, ["무료 이미지 엔진 (API키/결제 없음)"])
            img_mod_idx = img_models.index(curr_img_mod) if curr_img_mod in img_models else 0
            image_model = st.selectbox("이미지 생성 모델명", img_models, index=img_mod_idx, key="s_img_mod")
            
        st.markdown("---")
        col_size, col_quality = st.columns(2)
        with col_size:
            size_options = ["auto (🤖 AI 자동 판단)", "1024x1024", "1792x1024 (가로형)"]
            curr_size = cfg.get("IMAGE_SIZE", "auto")
            if curr_size == "auto": size_idx = 0
            elif curr_size == "1024x1024": size_idx = 1
            else: size_idx = 2
            image_size_raw = st.selectbox("이미지 비율/사이즈", size_options, index=size_idx, key="s_img_size")
            image_size = "auto" if "auto" in image_size_raw else "1024x1024" if "1024x1024" in image_size_raw else "1792x1024"
        with col_quality:
            image_quality = st.selectbox("품질 등급 (DALL-E 전용)", ["standard", "hd"], index=0 if cfg.get("IMAGE_QUALITY", "standard") == "standard" else 1)

    # ── Google 및 운영 세팅 연동 ──────────────────────────────────
    with st.expander("📊 Google 연동", expanded=False):
        g_sheet = st.text_input("GOOGLE_SHEET_ID", value=cfg.get("GOOGLE_SHEET_ID",""), key="s_sheet")
        g_drive = st.text_input("GOOGLE_DRIVE_ROOT_ID", value=cfg.get("GOOGLE_DRIVE_ROOT_ID",""), key="s_drive")
        g_placeholder = st.text_input("GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID", value=cfg.get("GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID",""), key="s_ph")

    with st.expander("🌐 WordPress 연동", expanded=False):
        from modules import config_loader as _CL
        _ready = _CL.is_wordpress_ready(cfg)
        st.caption(("🟢 WordPress 연동됨" if _ready else "⚪ 미설정 — 발행은 '검수대기'로 대기(크래시 없음)"))
        wp_url = st.text_input("WORDPRESS_URL", value=cfg.get("WORDPRESS_URL",""),
                               placeholder="https://your-site.com", key="s_wpurl")
        wcol1, wcol2 = st.columns(2)
        wp_user = wcol1.text_input("WORDPRESS_USERNAME", value=cfg.get("WORDPRESS_USERNAME",""),
                                   placeholder="admin", key="s_wpuser")
        wp_pw = wcol2.text_input("WORDPRESS_APP_PASSWORD", type="password",
                                 value=cfg.get("WORDPRESS_APP_PASSWORD", cfg.get("WORDPRESS_PASSWORD","")),
                                 placeholder="xxxx xxxx xxxx xxxx", key="s_wppw")
        st.caption("앱 비밀번호=WordPress 관리자 → 사용자 → 프로필 → '애플리케이션 비밀번호' 생성. 일반 로그인 비번 아님.")
        if st.button("🔌 WordPress 연결 테스트", key="s_wptest"):
            _u = (wp_url or "").strip().rstrip("/")
            if not _u or not wp_user.strip() or not wp_pw.strip():
                st.warning("URL/사용자/앱 비밀번호를 모두 입력하세요.")
            else:
                try:
                    import requests
                    r = requests.get(f"{_u}/wp-json/wp/v2/users/me",
                                     auth=(wp_user.strip(), wp_pw.strip().replace(" ", "")), timeout=10)
                    if r.status_code == 200:
                        st.success(f"연결 성공 — 사용자: {r.json().get('name','?')}")
                    elif r.status_code in (401, 403):
                        st.error("인증 실패(401/403) — 사용자/앱 비밀번호 확인")
                    else:
                        st.error(f"응답 코드 {r.status_code} — URL/REST API 활성화 확인")
                except Exception as _e:
                    st.error(f"연결 실패: {_e}")

    with st.expander("⚙️ 운영 설정", expanded=False):
        st.markdown("**발행 방식** — 예약 발행(슬롯 스케줄러) 단일화 (v12 Lite)")
        operation_mode = "scheduled"
        st.caption("실행: 예약 발행 → `scripts/run_scheduler.bat` · 단발 → `scripts/run_pipeline.bat`")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            adsense_mode = st.selectbox("ADSENSE_MODE", ["pre","post"], index=["pre","post"].index(cfg.get("ADSENSE_MODE","pre")), key="s_adsense")
            st.metric("하루 발행 개수 (DAILY_POST_COUNT)", cfg.get("DAILY_POST_COUNT", 3))
            st.caption("※ '📅 오늘 발행 일정' 탭의 슬롯 수로 자동 결정")
            daily_count = cfg.get("DAILY_POST_COUNT", 3)
        with col2:
            daily_budget = st.number_input("DAILY_AI_BUDGET (USD)", 1, 100, cfg.get("DAILY_AI_BUDGET",5), key="s_db")
            monthly_budget = st.number_input("MONTHLY_AI_BUDGET (USD)", 10, 1000, cfg.get("MONTHLY_AI_BUDGET",100), key="s_mb")
            dlq_threshold = st.number_input("DLQ_THRESHOLD", 1, 10, cfg.get("DLQ_THRESHOLD",3), key="s_dlq")
        auto_topic = st.toggle("AUTO_TOPIC_EXPANSION", value=cfg.get("AUTO_TOPIC_EXPANSION",False), key="s_ate")
        enable_strategy = st.toggle("ENABLE_STRATEGY_ROOM", value=cfg.get("ENABLE_STRATEGY_ROOM",True), key="s_esr")

        st.divider()
        st.markdown("**📨 텔레그램 알림** (오류/예산경고/일일요약/발행승인)")
        tcol1, tcol2 = st.columns(2)
        tg_token = tcol1.text_input("TELEGRAM_BOT_TOKEN", value=cfg.get("TELEGRAM_BOT_TOKEN",""),
                                    type="password", placeholder="1234567890:ABC...", key="s_tgtoken")
        tg_chat = tcol2.text_input("TELEGRAM_CHAT_ID", value=cfg.get("TELEGRAM_CHAT_ID",""),
                                   placeholder="-1001234567890", key="s_tgchat")
        st.caption("봇 토큰=@BotFather로 생성 · Chat ID=@userinfobot 또는 그룹에 봇 초대 후 확인. 저장 후 아래 '테스트 전송'으로 확인.")
        if st.button("📤 텔레그램 테스트 전송", key="s_tgtest"):
            from modules import telegram_ops as _TG
            _tcfg = dict(cfg); _tcfg["TELEGRAM_BOT_TOKEN"] = tg_token.strip(); _tcfg["TELEGRAM_CHAT_ID"] = tg_chat.strip()
            if not tg_token.strip() or not tg_chat.strip():
                st.warning("토큰과 Chat ID를 먼저 입력하세요.")
            else:
                try:
                    _TG.notify(_tcfg, "✅ CalcMate 텔레그램 연결 테스트 — 정상")
                    st.success("전송 시도 완료. 텔레그램 메시지를 확인하세요(미수신 시 토큰/Chat ID 재확인).")
                except Exception as _e:
                    st.error(f"전송 실패: {_e}")
        st.markdown("**이벤트별 알림 ON/OFF**")
        _ev_def = cfg.get("TELEGRAM_EVENTS") or {}
        _EVENTS = [("error", "오류 발생"), ("budget", "비용 경고"),
                   ("daily_summary", "일일 요약"), ("publish_request", "발행 승인 요청"),
                   ("quality_critical_hold", "품질 HOLD(Critical)"), ("publish_success", "발행 완료")]
        _ecols = st.columns(len(_EVENTS))
        tg_events = {}
        for _i, (_k, _lbl) in enumerate(_EVENTS):
            tg_events[_k] = bool(_ecols[_i].toggle(_lbl, value=bool(_ev_def.get(_k, True)), key=f"s_tgev_{_k}"))
        st.caption("telegram_ops 경유 이벤트에 적용. 파이프라인 크리티컬 알림(오류/예산/헬스)은 항상 발송.")

    # ── 🎨 계산기 노출 설정 (Design v2) — SM_CONFIG 연동 ──
    with st.expander("🎨 계산기 노출 설정 (v2)"):
        st.caption("생성되는 계산기 앱의 노출/정책. 저장 시 config.yaml에 반영되어 재생성물에 적용됩니다. (UI/계산식 무변경)")
        _SITE_MODES = ["pre_adsense", "adsense", "cpa", "full"]
        _cur_sm = cfg.get("SITE_MODE", "pre_adsense")
        v2_site = st.selectbox("SITE_MODE", _SITE_MODES,
                               index=_SITE_MODES.index(_cur_sm) if _cur_sm in _SITE_MODES else 0,
                               help="pre_adsense=광고/CPA off · adsense=광고 · cpa=CPA · full=둘 다")
        _c = st.columns(3)
        v2_share = _c[0].toggle("SHOW_SHARE", value=bool(cfg.get("SHOW_SHARE", True)), key="v2_share")
        v2_pwa = _c[1].toggle("SHOW_PWA", value=bool(cfg.get("SHOW_PWA", True)), key="v2_pwa")
        v2_save = _c[2].toggle("SHOW_RESULT_SAVE", value=bool(cfg.get("SHOW_RESULT_SAVE", True)), key="v2_save")
        _c2 = st.columns(3)
        v2_faq = _c2[0].toggle("SHOW_FAQ", value=bool(cfg.get("SHOW_FAQ", True)), key="v2_faq")
        v2_notice = _c2[1].toggle("SHOW_NOTICE", value=bool(cfg.get("SHOW_NOTICE", True)), key="v2_notice")
        v2_related = _c2[2].toggle("SHOW_RELATED", value=bool(cfg.get("SHOW_RELATED", True)), key="v2_related")
        _c3 = st.columns(3)
        v2_detail = _c3[0].toggle("SHOW_DETAIL", value=bool(cfg.get("SHOW_DETAIL", True)), key="v2_detail")
        v2_ads = _c3[1].toggle("SHOW_ADSENSE(오버라이드)", value=bool(cfg.get("SHOW_ADSENSE", False)), key="v2_ads")
        v2_cpa = _c3[2].toggle("SHOW_CPA(오버라이드)", value=bool(cfg.get("SHOW_CPA", False)), key="v2_cpa")
        _c4 = st.columns(2)
        _EXP = ["png", "pdf", "both", "none"]
        _cur_exp = cfg.get("RESULT_EXPORT_TYPE", "png")
        v2_exp = _c4[0].selectbox("RESULT_EXPORT_TYPE", _EXP,
                                  index=_EXP.index(_cur_exp) if _cur_exp in _EXP else 0,
                                  help="현재 png만 구현. pdf/both/none은 구조만 준비.")
        v2_kakao = _c4[1].text_input("KAKAO_JS_KEY", value=cfg.get("KAKAO_JS_KEY", ""),
                                     help="카카오 JS 키(클라이언트용). 입력 시 카카오 공유 SDK 연동 준비.")
        _c5 = st.columns(2)
        v2_calcver = _c5[0].text_input("CALCULATOR_VERSION", value=cfg.get("CALCULATOR_VERSION", "2.0.0"))
        v2_lawver = _c5[1].text_input("LAW_VERSION", value=cfg.get("LAW_VERSION", "2026-07"))
        if st.button("💾 계산기 노출 설정 저장", key="v2_save_btn"):
            _p = BASE / "config" / "config.yaml"
            with open(_p, encoding="utf-8") as f:
                _raw = yaml.safe_load(f) or {}
            _raw.update({
                "SITE_MODE": v2_site,
                "SHOW_ADSENSE": bool(v2_ads), "SHOW_CPA": bool(v2_cpa),
                "SHOW_SHARE": bool(v2_share), "SHOW_PWA": bool(v2_pwa),
                "SHOW_RESULT_SAVE": bool(v2_save), "SHOW_FAQ": bool(v2_faq),
                "SHOW_NOTICE": bool(v2_notice), "SHOW_RELATED": bool(v2_related),
                "SHOW_DETAIL": bool(v2_detail),
                "RESULT_EXPORT_TYPE": v2_exp, "KAKAO_JS_KEY": v2_kakao.strip(),
                "CALCULATOR_VERSION": v2_calcver.strip(), "LAW_VERSION": v2_lawver.strip(),
            })
            with open(_p, "w", encoding="utf-8") as f:
                yaml.dump(_raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            st.success("✅ 저장 완료. 계산기 재생성 시 SM_CONFIG에 반영됩니다.")
            st.cache_resource.clear()

    # ── AI 역할 체계 (확장 기능 전용 — 기존 파이프라인 모델과 별개) ──
    with st.expander("🧠 AI 역할 체계 (AI Workspace / App Factory 용)", expanded=False):
        st.caption("총괄/리서치/코드/작성/검수/이미지 역할별 모델. 기존 ORCHESTRATOR/PLANNER/WRITER/EDITOR 설정과 별개로 동작합니다.")
        from modules.ai_roles import ROLE_DEFS, get_role
        providers_list2 = ["openai", "claude", "gemini"]
        role_inputs = {}
        for rk, base in ROLE_DEFS.items():
            cur_p, cur_m = get_role(cfg, rk)
            st.markdown(f"**{base['label']}** — {base['desc']}")
            rc1, rc2 = st.columns(2)
            pv = rc1.selectbox(f"{rk} provider", providers_list2,
                               index=providers_list2.index(cur_p) if cur_p in providers_list2 else 0,
                               key=f"role_p_{rk}", label_visibility="collapsed")
            mv = rc2.text_input(f"{rk} model", value=cur_m, key=f"role_m_{rk}", label_visibility="collapsed")
            role_inputs[rk] = {"provider": pv, "model": mv}
        if st.button("💾 AI 역할 저장", key="save_roles"):
            with open(cfg_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            raw["AI_ROLES"] = role_inputs
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            st.success("✅ AI 역할 저장 완료")
            st.cache_resource.clear()

    # ── AI 점수 가중치 슬라이더 편집기 (score_weights.yaml) ──
    with st.expander("⚖️ AI 점수 가중치 (score_weights.yaml)", expanded=False):
        st.caption("M2 Strategist가 글 우선순위를 매기는 기준. 슬라이더 조정 후 저장하면 yaml에 반영(합계 1.0 자동 정규화).")
        sw_path = BASE / "config" / "score_weights.yaml"
        try:
            with open(sw_path, encoding="utf-8") as f:
                sw_raw = yaml.safe_load(f) or {}
        except Exception:
            sw_raw = {}
        sw = sw_raw.get("score_weights", {}) or {}
        SW_LABELS = {
            "traffic": "검색량(트래픽)", "cpc": "클릭단가(CPC)",
            "competition": "경쟁도(낮을수록 유리)", "cluster": "클러스터 연관성",
            "calculator": "계산기 연동", "revenue": "수익모델 적합도",
        }
        defaults = {"traffic": 0.30, "cpc": 0.20, "competition": 0.20,
                    "cluster": 0.10, "calculator": 0.10, "revenue": 0.10}
        sw_vals = {}
        for k, label in SW_LABELS.items():
            sw_vals[k] = st.slider(label, 0.0, 1.0,
                                   float(sw.get(k, defaults[k])), 0.05, key=f"sw_{k}")
        total = sum(sw_vals.values())
        st.caption(f"현재 합계: {total:.2f} (저장 시 1.0으로 자동 정규화)")
        if st.button("💾 가중치 저장", key="save_weights"):
            if total <= 0:
                st.error("가중치 합계가 0보다 커야 합니다.")
            else:
                norm = {k: round(v / total, 4) for k, v in sw_vals.items()}
                sw_raw["score_weights"] = norm
                with open(sw_path, "w", encoding="utf-8") as f:
                    yaml.dump(sw_raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                st.success(f"✅ 가중치 저장(정규화) 완료: {norm}")

    # ── 저장 로직 ──────────────────────────────────────────
    st.divider()
    if st.button("💾 설정 저장", type="primary"):
        new_cfg = dict(cfg)
        
        safe_orch = orch_mod.replace("-latest", "") if orch_prov == "gemini" else orch_mod
        safe_plan = plan_mod.replace("-latest", "") if plan_prov == "gemini" else plan_mod
        safe_writ = writ_mod.replace("-latest", "") if writ_prov == "gemini" else writ_mod
        safe_edit = edit_mod.replace("-latest", "") if edit_prov == "gemini" else edit_mod

        updates = {
            "OPENAI_API_KEY": st.session_state.get("s_openai", cfg.get("OPENAI_API_KEY","")),
            "CLAUDE_API_KEY": st.session_state.get("s_claude", cfg.get("CLAUDE_API_KEY","")),
            "GEMINI_API_KEY": st.session_state.get("s_gemini", cfg.get("GEMINI_API_KEY","")),
            
            "ORCHESTRATOR_PROVIDER": orch_prov,
            "PLANNER_PROVIDER":      plan_prov,
            "WRITER_PROVIDER":       writ_prov,
            "EDITOR_PROVIDER":       edit_prov,
            
            "MODEL_ORCHESTRATOR":    safe_orch,
            "MODEL_PLANNER":         safe_plan,
            "MODEL_WRITER":          safe_writ,
            "MODEL_EDITOR":          safe_edit,
            "MODEL_CLEANER":         clean_mod,
            "MODEL_EDITOR_FALLBACK": fb_mod,
            
            "IMAGE_PROVIDER":        image_provider,
            "MODEL_IMAGE":           image_model,
            "IMAGE_SIZE":            image_size,
            "IMAGE_QUALITY":         image_quality,
            
            "GOOGLE_SHEET_ID":   st.session_state.get("s_sheet", cfg.get("GOOGLE_SHEET_ID","")),
            "GOOGLE_DRIVE_ROOT_ID": st.session_state.get("s_drive", cfg.get("GOOGLE_DRIVE_ROOT_ID","")),
            "GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID": st.session_state.get("s_ph", cfg.get("GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID","")),
            "WORDPRESS_URL":          wp_url.strip(),
            "WORDPRESS_USERNAME":     wp_user.strip(),
            "WORDPRESS_APP_PASSWORD": wp_pw.strip(),
            "RUN_MODE":           "wordpress",
            "ADSENSE_MODE":       adsense_mode,
            "DAILY_POST_COUNT":   int(daily_count),
            "DAILY_AI_BUDGET":    int(daily_budget),
            "MONTHLY_AI_BUDGET":  int(monthly_budget),
            "DLQ_THRESHOLD":      int(dlq_threshold),
            "TELEGRAM_BOT_TOKEN": tg_token.strip(),
            "TELEGRAM_CHAT_ID":   tg_chat.strip(),
            "TELEGRAM_EVENTS":    tg_events,
            "AUTO_TOPIC_EXPANSION": auto_topic,
            "ENABLE_STRATEGY_ROOM": enable_strategy,
            "OPERATION_MODE": operation_mode,
        }
        new_cfg.update(updates)

        # 민감정보는 config.yaml이 아닌 secrets.yaml에 저장(분리 유지)
        from modules.config_loader import split_secrets, save_secrets_flat
        public_cfg, secret_cfg = split_secrets(new_cfg)
        if secret_cfg:
            save_secrets_flat(secret_cfg, str(cfg_path))
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(public_cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        st.success("✅ 제미나이 안전 규격 및 무료 이미지 옵션이 반영되어 저장되었습니다!")
        st.cache_resource.clear()

        st.subheader("🏥 저장 후 자동 헬스체크")
        with st.spinner("연결 상태 확인 중..."):
            try:
                hc_results = hc_mod.run(new_cfg)
                for k, v in hc_results.items():
                    if k == "timestamp": continue
                    if isinstance(v, dict):
                        if v.get("status") == "OK": st.success(f"✅ {k}: 연결 정상")
                        else: st.error(f"❌ {k}: 실패 — {v.get('error','')}")
            except Exception as e:
                st.error(f"헬스체크 모듈 가동 실패: {e}")

elif tab == "🏥 헬스체크":
    st.title("🏥 헬스체크 센터")
    run_live = st.button("▶ 헬스체크 실행(실시간)", type="primary")
    results = None
    if run_live:
        with st.spinner("검사 중... (API 연결 확인, 최대 30초)"):
            results = hc_mod.run(cfg)
    else:
        results = _read_health_cache()
        if results:
            st.caption(f"마지막 검사: {results.get('timestamp','-')} (실시간 재검사하려면 위 버튼)")
        else:
            st.info("검사 기록이 없습니다. 위 버튼으로 실행하세요.")

    if results:
        labels = {"openai": "OpenAI", "claude": "Claude", "gemini": "Gemini",
                  "google_sheet": "Sheets", "google_drive": "Drive",
                  "wordpress": "WordPress", "service_account": "Service Account"}
        items = [(labels.get(k, k), v) for k, v in results.items()
                 if isinstance(v, dict) and "status" in v]
        cols = st.columns(3)
        for i, (name, v) in enumerate(items):
            ok = v.get("status") == "OK"
            with cols[i % 3].container(border=True):
                st.markdown(f"### {'🟢' if ok else '🔴'} {name}")
                st.write(f"상태: **{v.get('status')}** ({v.get('level','')})")
                if not ok and v.get("error"):
                    st.error(str(v.get("error"))[:200])

elif tab == "📡 실시간 로그":
    st.title("📡 실시간 로그 센터")
    log_path = BASE / "data" / "logs" / "pipeline.log"
    fc1, fc2 = st.columns([1, 2])
    auto = fc1.toggle("🔄 자동 갱신(5초)", value=True, key="log_auto")
    level_filter = fc2.radio("필터", ["전체", "ERROR만", "WARN+ERROR", "INFO만"],
                             horizontal=True, key="log_filter")

    def _classify(line: str) -> str:
        if "[ERROR]" in line:
            return "error"
        if "[WARN" in line:   # [WARNING]/[WARN]
            return "warn"
        if "[INFO]" in line:
            return "info"
        return "other"

    def _render_log():
        st.caption(f"마지막 갱신: {datetime.now().strftime('%H:%M:%S')}")
        if not log_path.exists():
            st.info("아직 로그 파일이 없습니다 (data/logs/pipeline.log).")
            return
        lines = _tail_lines("data/logs/pipeline.log", 300)
        want = {"전체": {"error", "warn", "info", "other"},
                "ERROR만": {"error"},
                "WARN+ERROR": {"error", "warn"},
                "INFO만": {"info"}}[level_filter]
        rows = [(l, _classify(l)) for l in lines if _classify(l) in want]
        cnt = {"error": 0, "warn": 0, "info": 0}
        for _, lv in [(l, _classify(l)) for l in lines]:
            if lv in cnt:
                cnt[lv] += 1
        m = st.columns(3)
        m[0].metric("🔴 ERROR", cnt["error"]); m[1].metric("🟡 WARN", cnt["warn"]); m[2].metric("🟢 INFO", cnt["info"])
        if not rows:
            st.caption("표시할 로그가 없습니다.")
            return
        color = {"error": "#ef4444", "warn": "#f59e0b", "info": "#16a34a", "other": "#9ca3af"}
        html = ['<div style="font-family:monospace;font-size:12px;line-height:1.5;'
                'max-height:460px;overflow:auto;background:#0f172a;padding:10px;border-radius:8px">']
        import html as _h
        import re as _re
        def _body(s):   # 타임스탬프 접두사 제외 본문(연속 반복 판정용)
            return _re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*', '', s)
        def _hms(s):
            m = _re.match(r'^\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2})', s)
            return m.group(1) if m else ''

        def _emit(_line, _lv):
            html.append(f'<div style="color:{color[_lv]};white-space:pre-wrap">{_h.escape(_line)}</div>')

        disp = rows[-200:]
        i = 0
        while i < len(disp):
            line, lv = disp[i]
            key = _body(line)
            j = i + 1
            while j < len(disp) and _body(disp[j][0]) == key:
                j += 1
            run = j - i
            _emit(line, lv)                      # 첫 줄은 항상 표시
            if run >= 3:                         # 3회 이상 연속 → 나머지 압축(표시만)
                note = f'⋯ 동일 메시지 {run - 1}회 생략(마지막: {_hms(disp[j - 1][0])})'
                html.append(f'<div style="color:#64748b;font-style:italic;white-space:pre-wrap">{_h.escape(note)}</div>')
            else:                                # 1~2회는 그대로 전부 표시
                for k in range(i + 1, j):
                    _emit(disp[k][0], disp[k][1])
            i = j
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)

    if auto:
        try:
            log_fragment = st.fragment(run_every=5)(_render_log)
            log_fragment()
        except Exception:
            # 구버전 Streamlit 폴백
            if st.button("🔄 새로고침"):
                st.rerun()
            _render_log()
    else:
        if st.button("🔄 새로고침"):
            st.rerun()
        _render_log()