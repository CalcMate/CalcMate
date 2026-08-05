# -*- coding: utf-8 -*-
"""state_manager.py — Pipeline State 관리"""

class PipelineState:
    def __init__(self, pipeline_id, calculator):
        self.data = {
            "pipeline_id": pipeline_id,
            "calculator": calculator,
            "current_stage": "",
            "status": "RUNNING",
            "results": {},
            "errors": []
        }
