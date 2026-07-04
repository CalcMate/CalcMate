# -*- coding: utf-8 -*-
"""
modules/internal_link_engine.py — 계산기 ↔ 블로그 내부링크 엔진 (SalaryMate 확장, 신규)

관련 계산기/블로그 추천, 본문 CTA 생성, 내부링크 블록 주입.
데이터 접근은 Repository(CalculatorRepository/ArticleRepository) 경유.
"""
import html as _html
import re

from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository
from .logger import get_logger

LOG = get_logger()


def generate_related_calculators(cfg: dict, calculator_id: str = "", n: int = 3) -> list:
    """같은 카테고리 우선, 활성 계산기 중 자기 자신 제외 n개. [{id,name,url}]."""
    try:
        repo = CalculatorRepository(get_db_adapter(cfg))
        calcs = repo.get_active()
    except Exception as e:
        LOG.warning("관련 계산기 조회 실패: %s", e)
        return []
    me = next((c for c in calcs if c.get("id") == calculator_id), None)
    my_cat = (me or {}).get("category", "")
    others = [c for c in calcs if c.get("id") != calculator_id]
    others.sort(key=lambda c: 0 if c.get("category") == my_cat and my_cat else 1)
    out = []
    for c in others:
        if len(out) >= n:
            break
        url = c.get("published_url", "")
        # 죽은 링크 방지: published_url이 있고 상태가 활성일 때만 링크 생성
        # (상태 판단은 Repository.is_active — 엔진은 상태값 문자열을 직접 비교하지 않음)
        if not url or not repo.is_active(c.get("id", "")):
            continue
        out.append({"id": c.get("id", ""), "name": c.get("name", ""), "url": url})
    return out


def generate_related_articles(cfg: dict, keyword: str = "", n: int = 3) -> list:
    """발행완료 글 중 키워드 토큰이 제목에 겹치는 것 n개. [{title,url}]."""
    try:
        repo = ArticleRepository(get_db_adapter(cfg))
        rows = repo.get_all()
    except Exception as e:
        LOG.warning("관련 글 조회 실패: %s", e)
        return []
    published = [r for r in rows if r.get("상태값") in ("발행완료", "검수대기")]
    tokens = [t for t in re.split(r"\s+", keyword or "") if len(t) >= 2]

    def _score(r):
        title = str(r.get("최종추천제목", "") or r.get("정책명", ""))
        return sum(1 for t in tokens if t in title)
    published.sort(key=_score, reverse=True)
    out = []
    for r in published[:n]:
        out.append({"title": r.get("최종추천제목") or r.get("정책명", ""),
                    "url": r.get("발행 URL", "")})
    return out


def generate_cta(calc: dict) -> str:
    """계산기 CTA HTML."""
    name = _html.escape(calc.get("name", "계산기"))
    url = calc.get("published_url", "")
    link = f' <a href="{_html.escape(url)}">{name} 바로가기 →</a>' if url else ""
    return (f'<div class="sm-cta"><strong>🧮 {name}</strong> — '
            f'아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다.{link}</div>')


def inject_internal_links(html_body: str, related_calcs: list = None,
                          related_articles: list = None) -> str:
    """본문 끝에 관련 계산기/관련 글 내부링크 블록을 추가."""
    blocks = []
    if related_calcs:
        # url 없는 항목은 렌더 생략(href="#" 죽은 링크 금지)
        items = "".join(
            f'<li><a href="{_html.escape(c.get("url",""))}">{_html.escape(c.get("name",""))}</a></li>'
            for c in related_calcs if c.get("name") and c.get("url"))
        if items:
            blocks.append(f"<h3>관련 계산기</h3><ul>{items}</ul>")
    if related_articles:
        items = "".join(
            f'<li><a href="{_html.escape(a.get("url",""))}">{_html.escape(a.get("title",""))}</a></li>'
            for a in related_articles if a.get("title") and a.get("url"))
        if items:
            blocks.append(f"<h3>함께 보면 좋은 글</h3><ul>{items}</ul>")
    # 관련 항목이 0개면 섹션 헤딩도 표시하지 않음
    if not blocks:
        return html_body
    return html_body + '\n<hr/>\n<div class="internal-links">' + "".join(blocks) + "</div>"
