"""
duplicate_checker.py — STEP 3: 유사도 판별 + AI Judge (v11.6)
PART 5-A 규격 구현
"""
import json
import numpy as np
from .ai_provider import build_provider, retry_call
from .utils.parser import parse_json_lenient
from .logger import get_logger

LOG = get_logger()

JUDGE_SYSTEM = """아래 두 문서가 실질적으로 동일한 주제를 다루는지 판정하라.
판단 기준: 핵심 정책명 동일 여부, 수혜 대상 동일 여부, 지원 내용 실질적 동일 여부.
인사말 없이 아래 JSON만 반환하라: {"duplicate": true, "reason": "판정 근거 50자 이내", "confidence": 0.92}"""

def _embed(text: str, cfg: dict) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=cfg["OPENAI_API_KEY"])
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding

def _cosine(a, b) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0

def _ai_judge(doc_a: str, doc_b: str, similarity: float, cfg: dict) -> bool:
    provider = build_provider("openai", cfg)
    model = cfg["MODEL_CLEANER"]
    user_msg = f"임베딩 유사도: {similarity:.3f}\n\n[문서 A]\n{doc_a}\n\n[문서 B]\n{doc_b}"
    def _call():
        text, _ = provider.chat(JUDGE_SYSTEM, user_msg, model, max_tokens=200)
        return parse_json_lenient(text)
    try:
        result = retry_call(_call, 2)
        return result.get("duplicate", False)
    except Exception:
        return similarity >= 0.80  # 판정 실패 시 보수적 처리

def check_duplicate(new_doc: str, existing_docs: list[str], cfg: dict) -> tuple[bool, float]:
    """
    Returns (is_duplicate, max_similarity)
    3단계 판정:
    >= 0.85 → 즉시 차단
    <= 0.75 → 즉시 통과
    0.76~0.84 → AI Judge
    """
    threshold = cfg.get("DUPLICATE_THRESHOLD", 0.85)
    if not existing_docs:
        return False, 0.0
    try:
        new_vec = _embed(new_doc, cfg)
        max_sim = 0.0
        max_doc = ""
        for doc in existing_docs:
            vec = _embed(doc, cfg)
            sim = _cosine(new_vec, vec)
            if sim > max_sim:
                max_sim = sim
                max_doc = doc

        if max_sim >= threshold:
            return True, max_sim
        elif max_sim <= 0.75:
            return False, max_sim
        else:
            # AI Judge 구간
            is_dup = _ai_judge(new_doc, max_doc, max_sim, cfg)
            return is_dup, max_sim
    except Exception as e:
        LOG.warning("유사도 검사 오류 → 통과 처리: %s", e,
                    exc_info=(cfg.get("LOG_LEVEL", "INFO") == "DEBUG"))
        return False, 0.0
