1Phase C 지시서 (최종본) — Calculator UX/UI V2 (정적 개선)

전제 조건 (착수 전 확인)
- Phase B 산출물(Quality Standard V1.0, UI Independence, Changelog, run_regression.py 240 tests) 존재 확인
- 계산 로직 변경 금지. UI Independence 원칙에 따라 Phase B 회귀 테스트(240개)는
  작업 전/후 동일하게 PASS해야 한다.
  - 착수 전 처리: `_related_items_v2` [:4] 제한 해제, `needs_human_legal: true`
    상태값을 Verified 완료 7개 계산기 기준으로 정리
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    C-1. 공통 UI
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - 결과 카드 개선 (main_result + result_items 구조 유지, 디자인만 개선)
    - 입력폼 UI 개선 (placeholder/예시값 추가)
    - 버튼 디자인 통일
    - 안내 박스(notice 표시용) 컴포넌트화
    - 모바일 최적화 (반응형)
    - Design Token v1.0(#2C5AA0 딥블루 기준) 그대로 적용
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    C-2. CTA 개선
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - 결과 하단 CTA / 본문 중간 CTA / 페이지 하단 CTA
    - 정적 문구/링크만 (동적 CTA·개인화는 Phase D 범위)
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    C-3. FAQ
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - Accordion(드롭다운) 적용
    - FAQ 공통 컴포넌트화 (7개 계산기 동일 구조)
    - 기존 FAQ Schema(구조화 데이터) 유지 확인
    - SP-8 재발 방지: 컴포넌트 교체 시 변수명/코드식 노출 없는지 재확인
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    C-4. 관련 계산기
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - 카드 UI 구현
    - 추천 우선순위 규칙 고정 (알고리즘 도입 전까지 이 순서 그대로 사용):
      1순위: 같은 카테고리
        2순위: 입력값이 이어지는 계산기 (예: 퇴직금→실업급여)
          3순위: 함께 많이 사용하는 계산기
            4순위: 관리자 지정 추천
              5순위: 없으면 최신 계산기
              - `_related_items_v2` 제한 해제 반영, 내부 링크 연결
              
              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              C-5. 관련 글
              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              - 카드 UI
              - 기본 내부 링크 (계산기 지원용 블로그와 연결 — 정부정책 블로그 Set 1은 제외)
              
              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              C-6. 계산 과정 보기 (연말정산 우선, 범용 구조로)
              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
              - 연말정산 11단계(①총급여→⑪환급/추가납부) `_detail`/`_formula`를
                아코디언 형태로 펼쳐보는 UI 구현
                - 단계 수가 계산기마다 다르므로 하드코딩 금지, 다른 계산기도 재사용 가능하게 설계
                
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                C-7. 공통 컴포넌트화
                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                - C-1~C-6 컴포넌트(결과카드/CTA/FAQ/관련계산기/관련글/계산과정)를
                  7개 계산기 전체가 동일하게 사용하도록 공통 모듈로 정리
                  - app_generator.py의 UI 템플릿 렌더링 로직과 계산 엔진 로직을
                    코드 레벨에서 명확히 분리 (UI Independence 원칙 반영)
                    
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    C-8. Accessibility
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    - label과 input 연결 (for/id 매칭)
                    - 키보드(Tab) 이동 가능
                    - Accordion ARIA 속성 (aria-expanded 등)
                    - 버튼 focus 표시
                    - 모바일 터치 영역 44px 이상
                    - C-7과 동시 작업 (공통 컴포넌트 설계 단계에 포함)
                    
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    검증 (착수 전/완료 시 동일하게 실행)
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    - run_regression.py 240개 테스트 ALL PASS 확인 (작업 전/후 동일 결과)
                    - SP-8 grep (변수명/코드식/구 HTML form) 전체 재확인
                    - 7개 계산기 전부 동일 컴포넌트 사용 여부 확인
                    
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    스크린샷 체크리스트 (7개 계산기 각각)
                    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    □ PC       □ 모바일
                    확인 항목:
                    □ 입력폼   □ 결과카드   □ CTA   □ FAQ
                    □ 관련 계산기   □ 관련 글   □ 계산과정(연말정산)
                    □ 다크모드(지원 시)   □ 레이아웃 깨짐 없음
                    
                    산출물
                    1. 공통 컴포넌트 모듈 (결과카드/CTA/FAQ/관련계산기/관련글/계산과정보기, Accessibility 반영)
                    2. 7개 계산기 전체 적용 완료 스크린샷 (위 체크리스트 기준)
                    3. Regression 240개 유지 확인 리포트
                    4. SP-8 재확인 grep 결과
                    5. `_related_items_v2` 제한 해제 + `needs_human_legal` 정리 완료 확인
                    6. 관련 계산기 추천 우선순위 규칙 적용 확인 (1~5순위 로직 반영 여부)
                    
                    주의
                    - 계산 결과값(_detail/_formula/notices의 숫자·판정)은 절대 변경 금지
                    - 동적 연동(입력값→본문 텍스트 변경, 개인화 CTA/추천 알고리즘)은 Phase D 범위 — 이번엔 포함 안 함# -*- coding: utf-8 -*-
"""
modules/calculator_form_engine.py — 계산기 입력폼 엔진 (SalaryMate)

계산기 이름을 분석해 입력폼 스키마를 자동 생성하고 HTML로 렌더.
지원 타입: text/number/currency/date/select/radio/checkbox
골드 템플릿(templates/library/*.json)이 매칭되면 그 fields를 우선 사용.
"""
import html as _html
import json
import re
from pathlib import Path

from .ai_provider import build_provider_for_role
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()
LIB = Path(__file__).resolve().parent.parent / "templates" / "library"
TYPES = ["text", "number", "currency", "date", "select", "radio", "checkbox"]

# 이름 키워드 → 라이브러리 파일 매칭
_LIB_HINT = {
    "퇴직": "retirement", "연차": "annual_leave", "주휴": "weekly_allowance",
    "실업": "unemployment", "4대보험": "insurance", "보험": "insurance",
    "육아휴직": "parental_leave",
}


def _from_library(name: str):
    for kw, key in _LIB_HINT.items():
        if kw in name:
            f = LIB / f"{key}.json"
            if f.exists():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    return None
    return None


def get_library_template(name: str):
    """이름에 매칭되는 골드 템플릿(dict) 또는 None."""
    return _from_library(name)


def _slug(label: str, i: int) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", label.encode("ascii", "ignore").decode()).strip("_").lower()
    return s or f"field_{i}"


def generate_form_schema(cfg: dict, name: str) -> dict:
    """계산기 이름 → 입력폼 스키마 {fields:[{type,label,name}]}.
    골드 템플릿 우선, 없으면 AI(MODEL_WRITER) 추론, 실패 시 기본 폼."""
    lib = _from_library(name)
    if lib and lib.get("fields"):
        fields = []
        for i, f in enumerate(lib["fields"]):
            fields.append({"type": f.get("type", "number"),
                           "label": f.get("label", ""),
                           "name": f.get("name") or _slug(f.get("label", ""), i)})
        return {"fields": fields, "_source": "library"}

    system = ("너는 웹폼 설계자다. 주어진 계산기에 필요한 입력 필드를 설계하라. "
              f"type은 {TYPES} 중 하나. 순수 JSON만 반환: "
              '{"fields":[{"type":"","label":"","name":""}]}')
    try:
        provider, model = build_provider_for_role("writing", cfg)
        text, tokens = provider.chat(system, f"계산기명: {name}", model, max_tokens=500)
        try: BudgetTracker(cfg).record(model, tokens)
        except Exception: pass
        d = parse_json_lenient(text)
        fields = []
        for i, f in enumerate(d.get("fields", [])):
            t = f.get("type", "number")
            fields.append({"type": t if t in TYPES else "text",
                           "label": f.get("label", f"입력 {i+1}"),
                           "name": f.get("name") or _slug(f.get("label", ""), i)})
        if fields:
            return {"fields": fields, "_source": "ai"}
        raise ValueError("빈 폼")
    except Exception as e:
        LOG.warning("폼 스키마 AI 생성 실패(%s)→기본: %s", name, e)
        return {"fields": [{"type": "number", "label": "값1", "name": "value1"},
                           {"type": "number", "label": "값2", "name": "value2"}],
                "_source": "default"}


def build_form_html(schema: dict, el_prefix: str = "in") -> str:
    """스키마 → 입력폼 HTML(라벨+입력). 타입별 위젯."""
    fields = (schema or {}).get("fields", [])
    rows = []
    for f in fields:
        t = f.get("type", "text"); label = _html.escape(f.get("label", "")); nm = f.get("name", "")
        fid = f"{el_prefix}_{nm}"
        if t in ("number", "currency"):
            inp = f'<input type="number" id="{fid}" data-key="{nm}" placeholder="0">'
        elif t == "date":
            inp = f'<input type="date" id="{fid}" data-key="{nm}">'
        elif t == "select":
            opts = "".join(f'<option value="{o}">{o}</option>' for o in f.get("options", ["선택1", "선택2"]))
            inp = f'<select id="{fid}" data-key="{nm}">{opts}</select>'
        elif t == "radio":
            inp = "".join(
                f'<label class="sm-rdo"><input type="radio" name="{fid}" value="{o}" data-key="{nm}">{o}</label>'
                for o in f.get("options", ["예", "아니오"]))
        elif t == "checkbox":
            inp = f'<input type="checkbox" id="{fid}" data-key="{nm}">'
        else:
            inp = f'<input type="text" id="{fid}" data-key="{nm}">'
        suffix = ' <span class="sm-unit">원</span>' if t == "currency" else ""
        rows.append(f'<div class="sm-row"><label for="{fid}">{label}</label>'
                    f'<span class="sm-inp">{inp}{suffix}</span></div>')
    return "".join(rows) or "<p>입력 항목이 없습니다.</p>"
