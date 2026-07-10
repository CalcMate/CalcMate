# -*- coding: utf-8 -*-
"""Sprint B-1 마이그레이션: legal_basis.draft.yaml(slug 단위) → legal_master/ + registry/ (분리).

프로덕션 영향 0: 기존 파일/로더는 그대로. 새 구조를 '추가'만 한다.
resolve(slug) = registry[slug] + legal_master[legal_refs] 가 기존 엔트리와 동일해지도록 필드를 분리.
재실행 안전(idempotent): 새 파일을 매번 원본에서 재생성.
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import yaml

SRC = BASE / "docs" / "legal_basis.draft.yaml"
LM_DIR = BASE / "docs" / "legal_master"
REG_DIR = BASE / "docs" / "registry"

# 법령 필드(legal_master 소유) vs 계산기 필드(registry 소유). 합치면 기존 엔트리 = 두 집합의 합.
LEGAL_FIELDS = ["law", "article", "related_articles", "authority", "confidence",
                "last_verified", "verification_source", "writer_note",
                "reviewer_expectation", "forbidden_articles", "forbidden_phrases",
                "needs_human_legal"]
CALC_FIELDS = ["name", "slug", "category", "emoji", "card_label", "compute_type",
               "date_fields", "validation_mode", "field_labels", "difficulty",
               "difficulty_status", "content", "related_slugs"]

# slug → 법령 조항 엔티티 ID(불변). 4대보험은 복합 → 단일 복합 엔티티(조항 세분화는 후속).
SLUG_TO_ENTITY = {
    "weekly-holiday-allowance":  "labor_standards_act_55",
    "severance-pay":             "worker_retirement_benefit_act_8",
    "annual-leave-allowance":    "labor_standards_act_60",
    "unemployment-benefit":      "employment_insurance_act_40",
    "four-insurances":           "four_major_insurances",
    "연말정산_환급액_계산기":      "income_tax_act_137",
    "육아휴직_급여_계산기":        "employment_insurance_act_70",
}
# 엔티티 → 도메인 파일(legal_master/{domain}.yaml, registry/{domain}.yaml)
ENTITY_DOMAIN = {
    "labor_standards_act_55":          "labor",
    "worker_retirement_benefit_act_8": "labor",
    "labor_standards_act_60":          "labor",
    "employment_insurance_act_40":     "employment",
    "employment_insurance_act_70":     "employment",
    "four_major_insurances":           "insurance",
    "income_tax_act_137":              "tax",
}


def main():
    raw = yaml.safe_load(SRC.read_text(encoding="utf-8")) or {}
    raw.pop("schema_version", None)

    lm_by_domain = {}   # domain -> {entity_id: {법령필드}}
    reg_by_domain = {}  # domain -> {slug: {계산기필드 + legal_refs}}

    for slug, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        entity = SLUG_TO_ENTITY.get(slug)
        if not entity:
            print(f"[skip] 매핑 없는 slug: {slug}")
            continue
        domain = ENTITY_DOMAIN[entity]

        legal = {k: entry[k] for k in LEGAL_FIELDS if k in entry}
        calc = {k: entry[k] for k in CALC_FIELDS if k in entry}
        calc["legal_refs"] = [entity]

        lm_by_domain.setdefault(domain, {})[entity] = legal
        reg_by_domain.setdefault(domain, {})[slug] = calc

        # 누락/충돌 필드 감지(법령·계산기 외 필드가 있으면 경고 — 데이터 손실 방지)
        extra = set(entry) - set(LEGAL_FIELDS) - set(CALC_FIELDS)
        if extra:
            print(f"[warn] {slug}: 분류 안 된 필드 {extra} (resolve 결과에서 누락됨)")

    LM_DIR.mkdir(parents=True, exist_ok=True)
    REG_DIR.mkdir(parents=True, exist_ok=True)
    _LM_HEADER = "# legal_master/{d}.yaml — 법령 조항 엔티티(SSOT). scripts/migrate_legal_master.py 생성.\n"
    _REG_HEADER = "# registry/{d}.yaml — 계산기 정의(legal_refs로 법령 참조). scripts/migrate_legal_master.py 생성.\n"
    for domain, data in lm_by_domain.items():
        body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        (LM_DIR / f"{domain}.yaml").write_text(_LM_HEADER.format(d=domain) + body, encoding="utf-8")
    for domain, data in reg_by_domain.items():
        body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        (REG_DIR / f"{domain}.yaml").write_text(_REG_HEADER.format(d=domain) + body, encoding="utf-8")

    print(f"legal_master: {sum(len(v) for v in lm_by_domain.values())} 엔티티 / {len(lm_by_domain)} 파일")
    print(f"registry:     {sum(len(v) for v in reg_by_domain.values())} 계산기 / {len(reg_by_domain)} 파일")
    print("도메인:", {d: list(v) for d, v in reg_by_domain.items()})


if __name__ == "__main__":
    main()
