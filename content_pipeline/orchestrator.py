# -*- coding: utf-8 -*-
"""orchestrator.py — Pipeline 실행 관리"""
import json
from pathlib import Path
from .state_manager import PipelineState
from .engine_adapter import EngineAdapter
from .publish_gate import PublishGate

class ContentPipelineOrchestrator:
    STAGE_LIST = ["H4B_COMPETITIVE", "CONTENT_GENERATION", "H3_FAQ", "H4A_QUALITY", "PUBLISH"]

    def __init__(self):
        self.adapter = EngineAdapter()
        self.gate = PublishGate()

    def run(self, calculator_id, input_data, mock_fail_stage=None):
        state = PipelineState(f"p_{calculator_id}", calculator_id)
        log_dir = Path("logs/content_pipeline")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            for stage in self.STAGE_LIST:
                state.data["current_stage"] = stage
                if stage == mock_fail_stage:
                    state.data["status"] = "FAILED"
                    state.data["errors"].append(f"Stage {stage} failed")
                    self.save_log(state, log_dir)
                    return state

                result = self.execute_stage(stage, state, input_data)
                if not result:
                    state.data["status"] = "FAILED"
                    self.save_log(state, log_dir)
                    return state
            
            state.data["status"] = "SUCCESS"
        except Exception as e:
            from modules.logger import get_logger
            logger = get_logger("pipeline")
            logger.exception("Temporary traceback capture")
            logger.error("locals=%s", {
                k: type(v).__name__
                for k, v in locals().items()
            })
            state.data["status"] = "FAILED"
            state.data["errors"].append(str(e))
        
        self.save_log(state, log_dir)
        return state

    def execute_stage(self, stage, state, input_data):
        try:
            if stage == "H4B_COMPETITIVE":
                res = self.adapter.run_h4b(state.data["calculator"], input_data.get("profile", {}))
            elif stage == "CONTENT_GENERATION":
                res = self.adapter.run_content_generation(state.data["results"].get("H4B_COMPETITIVE", {}))
            elif stage == "H3_FAQ":
                res = self.adapter.run_h3_faq(state.data["results"].get("CONTENT_GENERATION", {}))
            elif stage == "H4A_QUALITY":
                content_gen_res = state.data["results"].get("CONTENT_GENERATION", {})
                content = ""
                if isinstance(content_gen_res, dict):
                    content = content_gen_res.get("data", {}).get("metadata", {}).get("content", "")
                res = self.adapter.run_h4a_quality(content)
            elif stage == "PUBLISH":
                h4a_result = state.data["results"].get("H4A_QUALITY", {})
                content_res = state.data["results"].get("CONTENT_GENERATION", {})
                metadata = {}
                if isinstance(content_res, dict):
                    metadata = content_res.get("data", {}).get("metadata", {})
                # DEBUG HERE
                print(f"DEBUG PUBLISH: h4a_result={h4a_result}, metadata={metadata}")
                res = {"status": self.gate.gate(h4a_result, metadata)}
            else:
                return False

            if isinstance(res, dict) and res.get("status") in ["PASS", "PUBLISHED", "PUBLISHED_WITH_WARNING_LOG", "WARNING"]:
                state.data["results"][stage] = res
                return True
            else:
                state.data["errors"].append(f"Stage {stage} returned {res.get('status') if isinstance(res, dict) else 'invalid_res'}")
                return False
        except Exception as e:
            from modules.logger import get_logger
            logger = get_logger("pipeline")
            logger.exception("Temporary traceback capture in execute_stage")
            logger.error("locals=%s", {
                k: type(v).__name__
                for k, v in locals().items()
            })
            state.data["errors"].append(str(e))
            return False

    def save_log(self, state, log_dir):
        log_file = log_dir / f"pipeline_{state.data['pipeline_id']}.json"
        log_file.write_text(json.dumps(state.data, indent=2), encoding="utf-8")
