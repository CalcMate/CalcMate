# -*- coding: utf-8 -*-
"""
주휴수당 계산기 Draft 단건 생성 검증 스크립트.
MAX_ARTICLES_PER_CALCULATOR 를 999 로 오버라이드해 파이프라인 직접 호출.
"""
import sys, io, json, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

def main():
    from modules.config_loader import load_config
    from modules.calculator_pipeline import run_calculator_once

    cfg = load_config()
    cfg["MAX_ARTICLES_PER_CALCULATOR"] = 999   # 제한 해제
    cfg["allow_duplicate"] = True

    JUHYU_CID = "calc_20260702221622_621a"

    print("=== 주휴수당 Draft 생성 시작 ===")
    result = run_calculator_once(
        cfg,
        max_count=1,
        only_cid=JUHYU_CID,
        allow_duplicate=True,
        skip_quality=False,
    )
    print("=== 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
