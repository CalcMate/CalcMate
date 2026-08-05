# -*- coding: utf-8 -*-
"""competitive_validator.py — 경쟁 분석 개선 작업 검증"""

class CompetitiveValidator:
    def validate(self, gap_result: dict, improvement_tasks: dict) -> dict:
        """개선 작업이 검증 원칙을 준수하는지 확인합니다."""
        status = "PASS"
        issues = []
        
        # 1. Duplicate Risk 검사
        tasks = improvement_tasks.get("tasks", [])
        for task in tasks:
            if "복사" in task.get("action", ""):
                status = "WARNING"
                issues.append("Duplicate risk detected in action")

        # 2. Legal Safety 검사
        essential_topics = ["법적 기준", "계산 조건", "예외 규칙"]
        for task in tasks:
            if task.get("topic") in essential_topics and "임의" in task.get("action", ""):
                status = "HOLD"
                issues.append(f"Legal safety violation: {task.get('topic')} modification restricted")

        # 3. Quality Engine 충돌 확인
        for task in tasks:
            if "글자 수" in task.get("action", ""):
                if status == "PASS": status = "WARNING"
                issues.append("Quality Engine policy conflict: Length requirement ignored")

        return {
            "status": status,
            "issues": issues
        }
