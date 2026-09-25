import json
from datetime import date
from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flasheats_pipeline.config import PipelineConfig
from flasheats_pipeline.extract import extract_local_sources
from flasheats_pipeline.metrics import build_metrics
from flasheats_pipeline.model import build_order_journey
from flasheats_pipeline.validate import run_validations, validation_status, ValidationError


class PipelineTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = PipelineConfig(repo_root=ROOT)
        cls.sources, _ = extract_local_sources(cls.config, __import__("logging").getLogger("test"))
        cls.dispatch = pd.DataFrame(json.loads(cls.config.api_source_path.read_text(encoding="utf-8")))

    def test_validation_gate_is_warn_not_fail_for_known_source_issues(self):
        results = run_validations(self.sources, self.dispatch, date(2026, 9, 25), 60)
        self.assertEqual(validation_status(results), "WARN")
        self.assertNotIn("FAIL", {result.status for result in results})

    def test_order_journey_preserves_order_grain(self):
        journey = build_order_journey(self.sources, self.dispatch, __import__("logging").getLogger("test"))
        self.assertEqual(len(journey), 1600)
        self.assertTrue(journey["order_id"].is_unique)
        self.assertEqual(int(journey["duplicate_order_source_flag"].sum()), 3)

    def test_metrics_match_expected_outcome_layer(self):
        journey = build_order_journey(self.sources, self.dispatch, __import__("logging").getLogger("test"))
        metrics, evidence = build_metrics(journey)
        self.assertEqual(metrics["late_delivery_count"], 843)
        self.assertEqual(metrics["measurable_deliveries"], 1495)
        self.assertEqual(metrics["late_delivery_rate_pct"], 56.39)
        self.assertEqual(len(evidence), 6)

    def test_required_column_failure_is_hard(self):
        broken = dict(self.sources)
        broken["orders"] = self.sources["orders"].drop(columns=["promised_eta"])
        with self.assertRaises(ValidationError):
            run_validations(broken, self.dispatch, date(2026, 9, 25), 60)


if __name__ == "__main__":
    unittest.main()
