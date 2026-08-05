# -*- coding: utf-8 -*-
"""
QA-1: 실제 파이프라인 경로 dual 모드 검증

검증 대상:
  1) calculators 테이블 dual-write (CalculatorRepository)
  2) 마스터_DB (articles) dual-write (ArticleRepository — 저장 + 상태전환)
  3) 운영로그 (logs) dual-write (sheet_sync.append_log)
  4) pending_sync.json 비어있음
  5) H-3 FAQ 엔진 정상 작동 (import + 인스턴스화)
  6) H-4 Competitive Analysis 엔진 정상 작동 (import + 인스턴스화)

AI/WP 호출 없음(비용 최소화). DB 경로만 실제 파이프라인 함수를 그대로 사용.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

from datetime import datetime
from pathlib import Path

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from adapters.db.dual_adapter import list_pending_sync, _SYNC_QUEUE_PATH
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository
import modules.sheet_sync as sheet_sync

cfg = load_config()
assert cfg.get("DB_ADAPTER", "").lower() == "dual", f"DB_ADAPTER가 dual이 아님: {cfg.get('DB_ADAPTER')}"

PASS = "PASS ✅"
FAIL = "FAIL ❌"
results = {}

def check(name, condition, evidence=""):
    status = PASS if condition else FAIL
    results[name] = status
    print(f"  [{status}] {name}")
    if evidence:
        print(f"         증거: {evidence}")
    return condition

# ── 공통 어댑터 (dual) ──────────────────────────────────────────
db = get_db_adapter(cfg)
assert type(db).__name__ == "DualAdapter", f"어댑터 타입 오류: {type(db).__name__}"
print(f"어댑터: DualAdapter ✅ (primary={type(db._primary).__name__}, secondary={type(db._secondary).__name__})")
print()

# ══════════════════════════════════════════════════════════════
# 1. calculators 테이블 dual-write (CalculatorRepository)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("1. calculators 테이블 — CalculatorRepository.create()")
print("=" * 60)

TEST_CALC_ID = "qa_sync_test_002_calc"
calc_repo = CalculatorRepository(db)

# 잔여 정리
try:
    existing = calc_repo.get_by_id(TEST_CALC_ID)
    if existing:
        calc_repo.delete(TEST_CALC_ID)
except Exception:
    pass

test_calc = {
    "id": TEST_CALC_ID,
    "name": "[QA-1] 파이프라인 dual 검증 계산기",
    "slug": "qa-sync-test-002-calc",
    "category": "qa",
    "status": "draft",
    "site_id": "qa_site",
    "created_at": datetime.now().isoformat(),
}

try:
    rid = calc_repo.create(dict(test_calc))
    check("CalculatorRepository.create 정상 반환", bool(rid), f"id={rid}")

    # Sheets 확인
    sheets_calcs = db._primary.get_all("calculators", force_refresh=True)
    sh_hit = [r for r in sheets_calcs if str(r.get("id","")) == TEST_CALC_ID]
    check("calculators → Sheets 기록됨", bool(sh_hit), f"조회 {len(sh_hit)}건")

    # SQLite 확인
    sq_calcs = db._secondary.get_all("calculators")
    sq_hit = [r for r in sq_calcs if str(r.get("id","")) == TEST_CALC_ID]
    check("calculators → SQLite 기록됨", bool(sq_hit), f"조회 {len(sq_hit)}건")

    # 핵심 필드 비교
    if sh_hit and sq_hit:
        for field in ("id", "name", "slug", "status"):
            sv = str(sh_hit[0].get(field,""))
            lv = str(sq_hit[0].get(field,""))
            check(f"calculators [{field}] Sheets==SQLite", sv == lv,
                  f"Sheets={sv!r} SQLite={lv!r}")
except Exception as e:
    check("CalculatorRepository.create 예외 없음", False, str(e))

# ══════════════════════════════════════════════════════════════
# 2. 마스터_DB (articles) dual-write — 저장 + 상태전환
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("2. 마스터_DB — ArticleRepository.save() + update_status()")
print("=" * 60)

art_repo = ArticleRepository(db)
TEST_ART_ID = None

test_article = {
    "ID":          "qa_sync_test_002",
    "calculator_id": TEST_CALC_ID,
    "정책명":      "QA-1 파이프라인 dual 검증",
    "상태값":      "대기",
    "우선발행점수": "99",
    "site_id":     "qa_site",
}

try:
    TEST_ART_ID = art_repo.save(dict(test_article))
    check("ArticleRepository.save 정상 반환", bool(TEST_ART_ID), f"ID={TEST_ART_ID}")

    # Sheets 확인
    sh_arts = db._primary.get_all("articles", force_refresh=True)
    sh_a = [r for r in sh_arts if str(r.get("ID","")) == TEST_ART_ID]
    check("마스터_DB → Sheets 기록됨", bool(sh_a), f"조회 {len(sh_a)}건")

    # SQLite 확인
    sq_arts = db._secondary.get_all("articles")
    sq_a = [r for r in sq_arts if str(r.get("ID","")) == TEST_ART_ID]
    check("마스터_DB → SQLite 기록됨", bool(sq_a), f"조회 {len(sq_a)}건")

    # 필드 비교
    if sh_a and sq_a:
        for field in ("ID", "calculator_id", "상태값", "정책명"):
            sv = str(sh_a[0].get(field,""))
            lv = str(sq_a[0].get(field,""))
            check(f"마스터_DB [{field}] Sheets==SQLite", sv == lv,
                  f"Sheets={sv!r} SQLite={lv!r}")

    # 상태 전환 테스트: 대기 → 발행완료
    art_repo.update_status(TEST_ART_ID, "발행완료", {"발행URL": "http://test.local/qa-1"})

    sh_arts2 = db._primary.get_all("articles", force_refresh=True)
    sh_a2 = [r for r in sh_arts2 if str(r.get("ID","")) == TEST_ART_ID]
    sq_arts2 = db._secondary.get_all("articles")
    sq_a2 = [r for r in sq_arts2 if str(r.get("ID","")) == TEST_ART_ID]

    sh_status = sh_a2[0].get("상태값","") if sh_a2 else ""
    sq_status = sq_a2[0].get("상태값","") if sq_a2 else ""
    check("상태전환 후 Sheets 상태값=발행완료", sh_status == "발행완료", f"Sheets={sh_status!r}")
    check("상태전환 후 SQLite 상태값=발행완료", sq_status == "발행완료", f"SQLite={sq_status!r}")

except Exception as e:
    check("ArticleRepository 예외 없음", False, str(e))

# ══════════════════════════════════════════════════════════════
# 3. 운영로그 dual-write — sheet_sync.append_log()
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("3. 운영로그 — sheet_sync.append_log()")
print("=" * 60)

TEST_LOG_ID = "qa1_log_" + datetime.now().strftime("%H%M%S")
test_log = {
    "로그ID":     TEST_LOG_ID,
    "실행일시":   datetime.now().isoformat(),
    "마스터ID":   TEST_ART_ID or "qa_sync_test_002",
    "대상 정책명": "QA-1 파이프라인 dual 검증",
    "가동 결과":  "성공",
    "실패 모듈명": "",
    "오류 원인 내용": "",
    "발행 URL (성공 시)": "http://test.local/qa-1",
    "총 소요시간(초)": 0,
    "사용 토큰 합계": 0,
}

try:
    sheet_sync.append_log(cfg, test_log)
    check("sheet_sync.append_log 예외 없음", True, "")

    # Sheets 확인
    sh_logs = db._primary.get_all("logs", force_refresh=True)
    sh_l = [r for r in sh_logs if str(r.get("로그ID","")) == TEST_LOG_ID]
    check("운영로그 → Sheets 기록됨", bool(sh_l), f"조회 {len(sh_l)}건")

    # SQLite 확인
    sq_logs = db._secondary.get_all("logs")
    sq_l = [r for r in sq_logs if str(r.get("로그ID","")) == TEST_LOG_ID]
    check("운영로그 → SQLite 기록됨", bool(sq_l), f"조회 {len(sq_l)}건")

    # 핵심 필드 비교 — Sheets 실제 헤더명 기준
    if sh_l and sq_l:
        for field in ("로그ID", "가동 결과 (성공/오류)", "마스터ID"):
            sv = str(sh_l[0].get(field,""))
            lv = str(sq_l[0].get(field,""))
            check(f"운영로그 [{field}] Sheets==SQLite", sv == lv,
                  f"Sheets={sv!r} SQLite={lv!r}")

except Exception as e:
    check("sheet_sync.append_log 예외 없음", False, str(e))

# ══════════════════════════════════════════════════════════════
# 4. pending_sync 비어있음 확인
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("4. pending_sync.json 비어있음 확인")
print("=" * 60)

pending = list_pending_sync()
check("pending_sync.json — 대기 항목 0건", len(pending) == 0,
      f"대기 항목 {len(pending)}건 (0이어야 함)")

if pending:
    print("  ⚠️ 미처리 동기화 항목:")
    for p in pending:
        print(f"    id={p.get('id')} op={p.get('op')} table={p.get('table')} err={p.get('error','')[:60]}")

# ══════════════════════════════════════════════════════════════
# 5. H-3 FAQ 엔진 정상 작동
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("5. H-3 FAQ 엔진 Smoke Test")
print("=" * 60)

try:
    from modules.faq_engine import FAQGenerator, FAQValidator, FAQQuestionSelector, mapper
    check("H-3 faq_engine import 정상", True, "FAQGenerator, FAQValidator, FAQQuestionSelector, mapper")

    gen = FAQGenerator()
    val = FAQValidator()
    sel = FAQQuestionSelector()
    check("H-3 FAQGenerator 인스턴스화", isinstance(gen, FAQGenerator), "")
    check("H-3 FAQValidator 인스턴스화", isinstance(val, FAQValidator), "")
    check("H-3 FAQQuestionSelector 인스턴스화", isinstance(sel, FAQQuestionSelector), "")
except Exception as e:
    check("H-3 FAQ 엔진 Smoke Test", False, str(e))

# ══════════════════════════════════════════════════════════════
# 6. H-4 Competitive Analysis 엔진 정상 작동
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("6. H-4 Competitive Analysis 엔진 Smoke Test")
print("=" * 60)

try:
    from modules.competitive_analysis import (
        SERPCollector, MockSERPProvider, CompetitorParser,
        TopicExtractor, ContentGapAnalyzer, ImprovementGenerator, CompetitiveValidator
    )
    check("H-4 competitive_analysis import 정상", True, "7개 클래스")

    mock = MockSERPProvider()
    parser = CompetitorParser()
    extractor = TopicExtractor()
    gap = ContentGapAnalyzer()
    imprv = ImprovementGenerator()
    validator = CompetitiveValidator()
    check("H-4 모든 클래스 인스턴스화", True, "6개 인스턴스 생성 완료")
except Exception as e:
    check("H-4 Competitive Analysis Smoke Test", False, str(e))

# ══════════════════════════════════════════════════════════════
# 7. 품질 엔진 (content_quality) Smoke Test
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("7. 품질 엔진 (content_quality) Smoke Test")
print("=" * 60)

try:
    from modules.content_quality import improve_content
    from modules.content_quality.quality_validator import QualityValidator

    check("content_quality import 정상", True, "improve_content, QualityValidator")
    qv = QualityValidator()
    check("QualityValidator 인스턴스화", isinstance(qv, QualityValidator), "")

    # 간단한 샘플 HTML로 검증 호출
    sample_html = """
    <h2>계산기소개</h2><p>주휴수당 계산기로 주휴수당을 계산합니다. 근로기준법 제55조에 따라 주 15시간 이상 근무 시 지급됩니다.</p>
    <h2>입력방법</h2><p>시급과 주 근로시간을 입력하세요.</p>
    <h2>결과확인</h2><p>계산 결과를 확인하세요.</p>
    <h2>계산원리</h2><p>주 소정 근로시간 / 5 × 시급으로 계산합니다.</p>
    <h2>주의사항</h2><p>정확한 세부 기준은 고용노동부에 확인하세요.</p>
    <h2>FAQ</h2><p>Q: 주 15시간 미만이면? A: 주휴수당 미지급.</p>
    """ * 5  # 품질 체크용 분량 확보
    result = qv.validate(sample_html, "weekly-holiday-allowance")
    check("QualityValidator.validate 정상 실행", result in ("PASS","WARNING","REWRITE","HOLD"),
          f"결과={result}")
    quality_result = result
except Exception as e:
    check("content_quality Smoke Test", False, str(e))
    quality_result = "ERROR"

# ══════════════════════════════════════════════════════════════
# 8. 테스트 데이터 정리
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("8. 테스트 데이터 정리")
print("=" * 60)

cleanup_db = get_db_adapter(cfg)

try:
    cleanup_db._primary.delete("calculators", TEST_CALC_ID)
    cleanup_db._secondary.delete("calculators", TEST_CALC_ID)
    print(f"  calculators [{TEST_CALC_ID}] 삭제 완료")
except Exception as e:
    print(f"  calculators 삭제 오류(무해): {e}")

try:
    if TEST_ART_ID:
        cleanup_db._primary.delete("articles", TEST_ART_ID)
        cleanup_db._secondary.delete("articles", TEST_ART_ID)
        print(f"  마스터_DB [{TEST_ART_ID}] 삭제 완료")
except Exception as e:
    print(f"  마스터_DB 삭제 오류(무해): {e}")

try:
    cleanup_db._primary.delete("logs", TEST_LOG_ID)
    cleanup_db._secondary.delete("logs", TEST_LOG_ID)
    print(f"  운영로그 [{TEST_LOG_ID}] 삭제 완료")
except Exception as e:
    print(f"  운영로그 삭제 오류(무해): {e}")

# 최종 검증: QA 잔여 없음
remaining_calcs = [r for r in cleanup_db._primary.get_all("calculators", force_refresh=True)
                   if str(r.get("id","")).startswith("qa_sync_test_002")]
remaining_arts  = [r for r in cleanup_db._primary.get_all("articles",    force_refresh=True)
                   if str(r.get("ID","")).startswith("qa_sync_test_002")]
check("정리: calculators QA 잔여 없음", len(remaining_calcs) == 0, f"잔여 {len(remaining_calcs)}건")
check("정리: 마스터_DB QA 잔여 없음",   len(remaining_arts) == 0,  f"잔여 {len(remaining_arts)}건")

# ══════════════════════════════════════════════════════════════
# 최종 결과
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("QA-1 최종 결과")
print("=" * 60)
all_pass = all(v == PASS for v in results.values())
for name, status in results.items():
    print(f"  {status}  {name}")

print()
fail_items = [k for k, v in results.items() if v != PASS]
if all_pass:
    print(f"결론: 전체 PASS ✅")
    print(f"  → QA-1 완료 — dual 모드 실운영 전환 가능")
    print(f"  → quality_validator 결과: {quality_result}")
else:
    print(f"결론: FAIL ❌ ({len(fail_items)}건 실패)")
    for f in fail_items:
        print(f"  ✗ {f}")

import sys
sys.exit(0 if all_pass else 1)
