import unittest
from unittest.mock import MagicMock
from content_pipeline.engine_adapter import EngineAdapter

class TestRunH4AQualityRobustness(unittest.TestCase):
    def setUp(self):
        self.adapter = EngineAdapter()
        # Mock quality_val
        self.adapter.quality_val = MagicMock()
        self.adapter.quality_val.validate.return_value = "PASS"

    def test_run_h4a_quality_with_dict(self):
        # Case 1: data is a dict
        data = {"metadata": {"content": "Test content"}}
        result = self.adapter.run_h4a_quality(data)
        self.assertEqual(result["status"], "PASS")
        self.adapter.quality_val.validate.assert_called_with("Test content", "weekly-holiday-allowance")

    def test_run_h4a_quality_with_str(self):
        # Case 2: data is a str
        data = "Test content"
        result = self.adapter.run_h4a_quality(data)
        self.assertEqual(result["status"], "PASS")
        self.adapter.quality_val.validate.assert_called_with("Test content", "weekly-holiday-allowance")

if __name__ == "__main__":
    unittest.main()
