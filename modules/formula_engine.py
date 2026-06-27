# -*- coding: utf-8 -*-
"""
modules/formula_engine.py — 계산기 수식 실행 엔진 (SalaryMate 확장, 신규)

JSON 기반 수식 정의를 안전하게 실행한다.
보안: 파이썬 eval() 미사용. ast로 파싱 후 화이트리스트 노드/연산자/함수만 평가.

수식 정의 예시:
{
  "calculator_id": "retirement_pay",
  "inputs": {"monthly_salary": "number", "years": "number"},
  "formula": "(monthly_salary / 30) * 30 * years"          # 단일 출력
}
또는 다중 출력:
  "formula": {"severance_pay": "(monthly_salary/30)*30*years"}

데이터 접근은 Repository(CalculatorRepository) 경유. Sheets 직접 접근 없음.
"""
import ast
import json
import operator

from .logger import get_logger

LOG = get_logger()

# 허용 연산자
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
# 허용 함수
_FUNCS = {"min": min, "max": max, "round": round, "abs": abs, "int": int, "float": float}
_MAX_POW = 8   # 거듭제곱 폭주 방지


class FormulaError(Exception):
    pass


def _eval(node, vars: dict):
    if isinstance(node, ast.Expression):
        return _eval(node.body, vars)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise FormulaError(f"허용되지 않은 상수: {node.value!r}")
    if isinstance(node, ast.Num):  # py<3.8 호환
        return node.n
    if isinstance(node, ast.BinOp):
        op = _OPS.get(type(node.op))
        if op is None:
            raise FormulaError(f"허용되지 않은 연산자: {type(node.op).__name__}")
        left, right = _eval(node.left, vars), _eval(node.right, vars)
        if isinstance(node.op, ast.Pow) and (abs(right) > _MAX_POW):
            raise FormulaError("거듭제곱 지수 한도 초과")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _OPS.get(type(node.op))
        if op is None:
            raise FormulaError("허용되지 않은 단항 연산자")
        return op(_eval(node.operand, vars))
    if isinstance(node, ast.Name):
        if node.id in vars:
            return vars[node.id]
        raise FormulaError(f"미정의 변수: {node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise FormulaError("허용되지 않은 함수 호출")
        return _FUNCS[node.func.id](*[_eval(a, vars) for a in node.args])
    raise FormulaError(f"허용되지 않은 식: {type(node).__name__}")


def _coerce_numbers(inputs: dict) -> dict:
    out = {}
    for k, v in (inputs or {}).items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = 0.0
    return out


def _eval_expr(expr: str, inputs: dict):
    tree = ast.parse(str(expr), mode="eval")
    return _eval(tree, inputs)


def execute_formula(formula, inputs: dict, output_schema=None) -> dict:
    """수식 실행. formula는 str(단일) 또는 dict(출력키→식). 반환: {출력키: 값}."""
    vars_ = _coerce_numbers(inputs)
    results = {}
    if isinstance(formula, dict):
        for out_key, expr in formula.items():
            results[out_key] = round(float(_eval_expr(expr, vars_)), 2)
    else:
        # 단일 식 → output_schema 첫 키(없으면 'result')에 매핑
        keys = list((output_schema or {}).keys()) if isinstance(output_schema, dict) else []
        out_key = keys[0] if keys else "result"
        results[out_key] = round(float(_eval_expr(formula, vars_)), 2)
    return results


def validate_formula(formula, inputs_schema=None) -> tuple:
    """수식 안전성/변수 검증. (ok, message). 실제 계산은 더미값(1)으로 시도."""
    try:
        exprs = list(formula.values()) if isinstance(formula, dict) else [formula]
        allowed = set((inputs_schema or {}).keys())
        for expr in exprs:
            tree = ast.parse(str(expr), mode="eval")
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and allowed and node.id not in allowed:
                    return False, f"input_schema에 없는 변수: {node.id}"
                if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda,
                                     ast.ListComp, ast.comprehension)):
                    return False, f"허용되지 않은 구문: {type(node).__name__}"
        dummy = {k: 1.0 for k in (allowed or [])}
        execute_formula(formula, dummy, inputs_schema if isinstance(inputs_schema, dict) else None)
        return True, "OK"
    except Exception as e:
        return False, str(e)


# ── Repository 연동 (Sheets 직접 접근 금지) ───────────────────────
def _repo(cfg: dict):
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    return CalculatorRepository(get_db_adapter(cfg))


def load_formula(cfg: dict, calculator_id: str) -> dict:
    """calculators 시트에서 수식 정의 로드 → {calculator_id, inputs, output_schema, formula}."""
    calc = _repo(cfg).get_by_id(calculator_id)
    if not calc:
        raise FormulaError(f"계산기 없음: {calculator_id}")

    def _pj(v, default):
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v) if v else default
        except Exception:
            return default

    return {
        "calculator_id": calculator_id,
        "inputs": _pj(calc.get("input_schema"), {}),
        "output_schema": _pj(calc.get("output_schema"), {}),
        "formula": _pj(calc.get("formula"), calc.get("formula", "")),
    }


def save_formula(cfg: dict, calculator_id: str, formula) -> None:
    """수식을 calculators.formula에 저장(문자열/JSON)."""
    val = formula if isinstance(formula, str) else json.dumps(formula, ensure_ascii=False)
    _repo(cfg).update(calculator_id, {"formula": val})
    LOG.info("수식 저장: %s", calculator_id)
