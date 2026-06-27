# -*- coding: utf-8 -*-
"""
dashboard_ui_refactor.py — SalaryMate OS (UI 전면 개편, 신규 파일)

★ UI 전용. 기존 dashboard.py / 모듈 / 파이프라인 일절 변경하지 않는다.
   기존 백엔드 함수/리포지토리는 '읽기·트리거' 용도로만 재사용한다.

실행:  streamlit run dashboard_ui_refactor.py
벤치마크: Linear · Vercel · Stripe · Notion · OpenAI Platform
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

import streamlit as st

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

st.set_page_config(page_title="SalaryMate OS", page_icon="🛰️", layout="wide",
                   initial_sidebar_state="expanded")


# ── CSS 로더 ──────────────────────────────────────────────────────
def load_css(path: str = "assets/css/dashboard.css"):
    f = BASE / path
    if f.exists():
        st.markdown(f"<style>{f.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS 파일 없음: {path}")


load_css()


# ── 설정/데이터 로더 (읽기 전용) ──────────────────────────────────
@st.cache_resource(ttl=30)
def load_cfg() -> dict:
    import yaml
    with open(BASE / "config" / "config.yaml", encoding="utf-8") as fp:
        c = yaml.safe_load(fp) or {}
    c["_root"] = str(BASE)
    return c


cfg = load_cfg()


def _read_json(rel: str, default):
    p = BASE / rel
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _budget():
    try:
        from modules.logger import BudgetTracker
        return BudgetTracker(cfg)
    except Exception:
        return None


def _sched_summary():
    try:
        from modules import scheduler as SCH
        s = SCH.load_schedule(cfg)
        if s and s.get("date") == date.today().isoformat():
            return SCH.summarize(s)
    except Exception:
        pass
    return {"total": 0, "completed": 0, "pending": 0, "failed": 0, "next": None}


def _counts():
    out = {"calc": None, "posts": None}
    try:
        from adapters.db.factory import get_db_adapter
        from repositories.calculator_repository import CalculatorRepository
        from repositories.article_repository import ArticleRepository
        db = get_db_adapter(cfg)
        out["calc"] = len(CalculatorRepository(db).get_all())
        arts = ArticleRepository(db).get_all()
        out["posts"] = sum(1 for a in arts if a.get("상태값") in ("발행완료", "검수대기"))
    except Exception:
        pass
    return out


def _health():
    return _read_json("data/logs/health_last.json", {})


def _kpi(col, icon, label, value, sub=""):
    col.markdown(
        f"""<div class="sm-kpi"><div class="ic">{icon}</div>
        <div class="lab">{label}</div><div class="val">{value}</div>
        <div class="sub">{sub}</div></div>""", unsafe_allow_html=True)


def _card_open(title=None):
    h = f'<div class="sm-card">' + (f'<h3 style="margin:0 0 10px">{title}</h3>' if title else "")
    st.markdown(h, unsafe_allow_html=True)


def _run(label, fn):
    with st.spinner(f"{label} 실행 중..."):
        try:
            r = fn()
            st.session_state["_act"] = (True, f"✅ {label} 완료: {r if r is not None else ''}")
        except Exception as e:
            st.session_state["_act"] = (False, f"❌ {label} 실패: {e}")


# ── 사이드바 네비게이션 (아이콘) ──────────────────────────────────
st.sidebar.markdown('<div class="sm-brand">🛰️ SalaryMate OS</div>'
                    '<div class="sm-brand-sub">Content & Calculator Platform</div>',
                    unsafe_allow_html=True)
NAV = ["🏠 Dashboard", "🧮 Calculators", "📝 Content", "🤖 AI Studio",
       "🌐 Sites", "📈 Analytics", "🚀 Deploy", "⚙️ Settings"]
nav = st.sidebar.radio("", NAV, label_visibility="collapsed")
st.sidebar.markdown("---")
hc = _health()
crit_ok = all(v.get("status") == "OK" for k, v in hc.items()
              if isinstance(v, dict) and v.get("level") == "CRITICAL") if hc else False
st.sidebar.markdown(
    f'<span class="sm-badge {"ok" if crit_ok else "warn"}">'
    f'<span class="dot {"ok" if crit_ok else "warn"}"></span>'
    f'{"시스템 정상" if crit_ok else "점검 필요"}</span>', unsafe_allow_html=True)

act = st.session_state.pop("_act", None)
if act:
    (st.success if act[0] else st.error)(act[1])


# ══════════════════════════════════════════════════════════════════
# 🏠 DASHBOARD
# ══════════════════════════════════════════════════════════════════
if nav == "🏠 Dashboard":
    st.markdown("## 🏠 운영 대시보드")
    bt = _budget()
    summ = _sched_summary()
    cnt = _counts()
    daily = bt.get_daily_cost() if bt else 0
    monthly = bt.get_monthly_cost() if bt else 0

    # ── KPI 카드 ──
    k = st.columns(5)
    _kpi(k[0], "💸", "오늘 AI 비용", f"${daily:.3f}", f"이번달 ${monthly:.2f}")
    _kpi(k[1], "🧮", "계산기 수", cnt["calc"] if cnt["calc"] is not None else "—",
         "등록된 계산기" if cnt["calc"] is not None else "시트 연결 필요")
    _kpi(k[2], "📝", "발행/대기 글", cnt["posts"] if cnt["posts"] is not None else "—",
         "articles" if cnt["posts"] is not None else "시트 연결 필요")
    _kpi(k[3], "👥", "방문자 수", "—", "Analytics 미연동")
    _kpi(k[4], "🩺", "AI 상태", "정상" if crit_ok else "점검", hc.get("timestamp", "미검사")[:16] if hc else "미검사")

    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([2, 1])

    # ── 콘텐츠 파이프라인 시각화 ──
    with left:
        _card_open("⛓️ 콘텐츠 파이프라인")
        try:
            from modules.pipeline_status import get_pipeline_state
            ps = get_pipeline_state(cfg)
            ic = {"pending": "🟡", "running": "🔵", "completed": "🟢", "error": "🔴"}
            cls = {"completed": "done", "running": "run", "error": "run", "pending": ""}
            steps = "".join(
                f'<div class="sm-step {cls.get(s["status"],"")}"><div class="s-ic">{ic.get(s["status"],"⬜")}</div>'
                f'<div class="s-nm">{s["name"]}</div><div class="sm-dim" style="font-size:11px">{s["model"]}</div></div>'
                for s in ps["stages"])
            st.markdown(f'<div class="sm-pipe">{steps}</div>', unsafe_allow_html=True)
            done = sum(1 for s in ps["stages"] if s["status"] == "completed")
            st.progress(done / max(len(ps["stages"]), 1),
                        text=f"진행 {done}/{len(ps['stages'])} · 오늘 비용 ${ps['cost_today']:.3f}")
        except Exception as e:
            st.caption(f"파이프라인 상태 로드 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 차트: AI 비용 추이 ──
        _card_open("📊 AI 비용 추이 (일별)")
        try:
            import pandas as pd
            data = _read_json("data/logs/budget.json", {})
            daily_map = data.get("daily", {})
            if daily_map:
                s = pd.Series({k: round(v, 4) for k, v in sorted(daily_map.items())[-14:]})
                st.line_chart(s, height=200)
            else:
                st.caption("비용 기록 없음")
        except Exception as e:
            st.caption(f"차트 로드 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 시스템 상태 + 빠른작업 ──
    with right:
        _card_open("🩺 시스템 상태")
        svc = [("OpenAI", "openai"), ("Claude", "claude"), ("Gemini", "gemini"),
               ("Google Sheets", "google_sheet"), ("Google Drive", "google_drive"),
               ("WordPress", "wordpress")]
        if hc:
            for nm, key in svc:
                ok = hc.get(key, {}).get("status") == "OK"
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:5px 0">'
                            f'<span class="sm-dim">{nm}</span>'
                            f'<span class="sm-badge {"ok" if ok else "err"}">'
                            f'<span class="dot {"ok" if ok else "err"}"></span>{"정상" if ok else "오류"}</span></div>',
                            unsafe_allow_html=True)
        else:
            st.caption("헬스체크 기록 없음 — 아래 헬스체크 실행")
        st.markdown("</div>", unsafe_allow_html=True)

        _card_open("⚡ 빠른 작업")
        import main as PIPE
        qa = [("🚀 즉시발행", lambda: __import__("modules.scheduler", fromlist=["immediate_publish"]).immediate_publish(cfg, PIPE.run_once, "pull")[1]),
              ("⚙️ 파이프라인", lambda: PIPE.run_once(cfg)),
              ("🖼 이미지재생성", lambda: __import__("modules.image_generator", fromlist=["generate"]).generate("ui"+datetime.now().strftime("%H%M%S"), {"image_prompt_thumbnail": "clean dashboard", "image_prompt_body": "office"}, cfg)),
              ("🧠 전략회의실", lambda: (__import__("modules.strategy_room", fromlist=["run_strategy_room"]).run_strategy_room({}, cfg) or {}).get("summary", "완료")),
              ("🩺 헬스체크", lambda: "OK" if __import__("health_check").critical_passed(__import__("health_check").run(cfg)) else "일부실패"),
              ("💾 백업", lambda: str(__import__("modules.backup_manager", fromlist=["BackupManager"]).BackupManager(cfg).run_daily_backup()))]
        cols = st.columns(2)
        for i, (lab, fn) in enumerate(qa):
            if cols[i % 2].button(lab, key=f"qa_{i}", use_container_width=True):
                _run(lab, fn); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption("※ 방문자/광고수익 등 Analytics 지표는 데이터 소스 미연동 상태입니다(추후 연동). 비용·계산기·발행글·상태는 실데이터입니다.")


# ══════════════════════════════════════════════════════════════════
# 🧮 CALCULATORS
# ══════════════════════════════════════════════════════════════════
elif nav == "🧮 Calculators":
    st.markdown("## 🧮 Calculators")
    try:
        from adapters.db.factory import get_db_adapter
        from repositories.calculator_repository import CalculatorRepository
        calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
    except Exception as e:
        calcs = []
        st.error(f"계산기 조회 실패(시트 권한 확인): {e}")
    k = st.columns(3)
    _kpi(k[0], "🧮", "전체", len(calcs))
    _kpi(k[1], "🟢", "활성", sum(1 for c in calcs if str(c.get("status")).lower() == "active"))
    _kpi(k[2], "🚀", "배포됨", sum(1 for c in calcs if c.get("published_url")))
    st.markdown("<br>", unsafe_allow_html=True)
    for c in calcs:
        _card_open()
        st.markdown(f"**🧮 {c.get('name','-')}**  ·  <span class='sm-dim'>{c.get('category','')} · {c.get('status','')}</span>",
                    unsafe_allow_html=True)
        if c.get("published_url"):
            st.markdown(f"[{c['published_url']}]({c['published_url']})")
        if c.get("seo_title"):
            st.caption(f"SEO: {c.get('seo_title')}")
        st.markdown("</div>", unsafe_allow_html=True)
    if not calcs:
        st.info("등록된 계산기 없음 — 기존 대시보드(🧮 계산기 관리)에서 시드/생성하세요.")
    st.caption("생성·배포·자동생성은 기존 dashboard.py의 🧮 계산기 관리 / 🏭 App Factory 탭에서 수행합니다(로직 동일).")


# ══════════════════════════════════════════════════════════════════
# 📝 CONTENT
# ══════════════════════════════════════════════════════════════════
elif nav == "📝 Content":
    st.markdown("## 📝 Content")
    try:
        from adapters.db.factory import get_db_adapter
        from repositories.article_repository import ArticleRepository
        arts = ArticleRepository(get_db_adapter(cfg)).get_all()
    except Exception as e:
        arts = []
        st.error(f"글 조회 실패(시트 권한 확인): {e}")
    pub = [a for a in arts if a.get("상태값") in ("발행완료", "검수대기")]
    pub.sort(key=lambda x: x.get("발행일시", ""), reverse=True)
    k = st.columns(3)
    _kpi(k[0], "📝", "발행/대기", len(pub))
    _kpi(k[1], "🟢", "발행완료", sum(1 for a in arts if a.get("상태값") == "발행완료"))
    _kpi(k[2], "🟠", "검수대기", sum(1 for a in arts if a.get("상태값") == "검수대기"))
    st.markdown("<br>", unsafe_allow_html=True)
    for a in pub[:30]:
        _card_open()
        st.markdown(f"**{a.get('최종추천제목','(제목없음)')}**  ·  "
                    f"<span class='sm-dim'>{a.get('상태값','')} · {a.get('발행일시','')[:16]}</span>",
                    unsafe_allow_html=True)
        if a.get("발행 URL"):
            st.caption(a.get("발행 URL"))
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# 🤖 AI STUDIO  ·  🌐 SITES  ·  🚀 DEPLOY  ·  ⚙️ SETTINGS
# ══════════════════════════════════════════════════════════════════
elif nav == "🤖 AI Studio":
    st.markdown("## 🤖 AI Studio")
    try:
        from modules.ai_roles import all_roles
        roles = all_roles(cfg)
        cols = st.columns(3)
        for i, (rk, info) in enumerate(roles.items()):
            with cols[i % 3]:
                _card_open()
                st.markdown(f"**{info['label']}**<br><span class='sm-dim'>{info['provider']} · {info['model']}</span><br>"
                            f"<span class='sm-dim' style='font-size:11px'>{info['desc']}</span>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"역할 로드 실패: {e}")
    st.caption("AI Workspace 채팅/파일도구는 기존 dashboard.py의 💬 AI Workspace 탭에서 동작합니다.")

elif nav == "🌐 Sites":
    st.markdown("## 🌐 Sites")
    try:
        from adapters.db.factory import get_db_adapter
        from repositories.site_repository import SiteRepository
        sites = SiteRepository(get_db_adapter(cfg), cfg).get_all()
    except Exception as e:
        sites = []
        st.error(f"사이트 조회 실패: {e}")
    if not sites:
        st.info("등록된 사이트 없음 — 기존 🌐 사이트 관리 탭에서 추가하세요.")
    for s in sites:
        _card_open()
        st.markdown(f"**{s.get('site_name','-')}**  ·  <span class='sm-dim'>{s.get('domain','')} · "
                    f"{s.get('site_type','')} · {s.get('status','')}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif nav == "📈 Analytics":
    st.markdown("## 📈 Analytics")
    bt = _budget()
    import pandas as pd
    c1, c2 = st.columns(2)
    with c1:
        _card_open("광고/AI 비용 추이 (일별)")
        data = _read_json("data/logs/budget.json", {})
        dm = data.get("daily", {})
        if dm:
            st.area_chart(pd.Series({k: round(v, 4) for k, v in sorted(dm.items())[-14:]}), height=220)
        else:
            st.caption("데이터 없음")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        _card_open("Provider별 비용 (이번달)")
        if bt:
            prov = {k: v for k, v in bt.get_provider_breakdown("monthly").items() if v}
            if prov:
                st.bar_chart(pd.Series(prov), height=220)
            else:
                st.caption("이번달 집계 없음")
        st.markdown("</div>", unsafe_allow_html=True)
    _card_open("🏆 계산기 사용량 TOP5")
    st.caption("사용량(트래픽) 지표는 외부 Analytics 미연동 — 현재는 등록 계산기 목록만 표시합니다.")
    try:
        from adapters.db.factory import get_db_adapter
        from repositories.calculator_repository import CalculatorRepository
        for c in CalculatorRepository(get_db_adapter(cfg)).get_all()[:5]:
            st.markdown(f"- {c.get('name','-')} <span class='sm-dim'>({c.get('category','')})</span>", unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"로드 실패: {e}")
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("※ 방문자/CTR/광고수익은 데이터 소스 미연동(추후 GA/AdSense 연동 시 활성화).")

elif nav == "🚀 Deploy":
    st.markdown("## 🚀 Deploy")
    try:
        from modules import github_deployer as GH
        ok = GH.is_configured(cfg)
    except Exception:
        ok = False
    _card_open("GitHub Pages")
    st.markdown(f'<span class="sm-badge {"ok" if ok else "warn"}"><span class="dot {"ok" if ok else "warn"}"></span>'
                f'{"GITHUB_TOKEN 설정됨 — 배포 가능" if ok else "GITHUB_TOKEN 미설정 — 배포 비활성"}</span>',
                unsafe_allow_html=True)
    st.caption("계산기 정적앱 배포는 기존 🧮 계산기 관리 탭의 [배포] 버튼에서 수행합니다(github_deployer).")
    st.markdown("</div>", unsafe_allow_html=True)

elif nav == "⚙️ Settings":
    st.markdown("## ⚙️ Settings")
    _card_open("운영 요약 (읽기 전용)")
    masked = {k: ("***" if any(s in k.upper() for s in ("KEY", "TOKEN", "PASSWORD", "SECRET")) else v)
              for k, v in cfg.items() if not k.startswith("_")}
    st.json(masked)
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("값 편집은 기존 dashboard.py의 🔧 설정 탭에서 수행합니다(이 화면은 SaaS UI 미러, 읽기 전용).")
