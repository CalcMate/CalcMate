"""
modules/collector/calculator.py — 계산기 DB 기반 키워드 수집기
calculators 테이블의 활성 계산기 → 블로그 키워드 생성.
"""
from .base import BaseCollector

# {base}=계산기명에서 '계산기' 접미사를 뗀 핵심어 (예: '주휴수당 계산기' → '주휴수당')
KEYWORD_TEMPLATES = [
    "{base} 계산",
    "{base} 계산법",
    "{base} 계산 방법",
    "{base} 조건",
    "{base} 지급기준",
    "{base} 세금",
    "{name} 사용법",
]


def _base_name(name: str) -> str:
    """'주휴수당 계산기' → '주휴수당' (접미사 제거)."""
    b = name.strip()
    for suf in ("계산기", "계산", "기"):
        if b.endswith(suf) and len(b) > len(suf):
            return b[: -len(suf)].strip()
    return b


class CalculatorCollector(BaseCollector):
    def collect(self, cfg: dict, site: dict = None) -> list[dict]:
        site = site or {}
        site_id = site.get("site_id", "")

        # Repository 경유 조회 (gspread/Drive 직접 호출 없음)
        try:
            from adapters.db.factory import get_db_adapter
            from repositories.calculator_repository import CalculatorRepository
            db = get_db_adapter(cfg)
            repo = CalculatorRepository(db)
            calcs = repo.get_by_site(site_id) if site_id else repo.get_active()
        except Exception as e:
            print(f"[CalculatorCollector] DB 조회 오류: {e}")
            calcs = []

        results = []
        seen = set()
        for calc in calcs:
            name = calc.get("name", "")
            if not name:
                continue
            base = _base_name(name)
            for tmpl in KEYWORD_TEMPLATES:
                kw = tmpl.format(name=name, base=base)
                if kw in seen:
                    continue
                seen.add(kw)
                results.append({
                    "title":       kw,                       # 키워드(글 주제)
                    "keyword":     kw,
                    "description": f"{name} 관련 정보 — {calc.get('seo_desc', '')}",
                    "link":        calc.get("published_url", ""),
                    "category":    calc.get("category", "계산기"),
                    "source_type": "calculator",
                    "site_id":     site_id,
                    "calculator_id": calc.get("id", ""),
                })
        return results

