"""Tests for F1 Score Measurement Script"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.measure_f1 import calc_f1, load_ground_truth, run_measurement


@pytest.fixture
def sample_ground_truth(tmp_path):
    """Create a minimal ground truth file for testing"""
    gt_data = {
        "brands": [
            {
                "id": 1,
                "name": "Samsung",
                "aliases": ["삼성"],
                "keywords": ["galaxy"]
            },
            {
                "id": 2,
                "name": "Apple",
                "aliases": ["애플"],
                "keywords": ["iphone"]
            }
        ],
        "samples": [
            {
                "id": "test-001",
                "text": "Samsung Galaxy S24 is excellent",
                "language": "en",
                "difficulty": "easy",
                "expected_matches": [
                    {"brand_name": "Samsung", "match_type": "exact"}
                ]
            },
            {
                "id": "test-002",
                "text": "Apple iPhone vs Samsung Galaxy comparison",
                "language": "en",
                "difficulty": "medium",
                "expected_matches": [
                    {"brand_name": "Apple", "match_type": "exact"},
                    {"brand_name": "Samsung", "match_type": "exact"}
                ]
            }
        ]
    }

    gt_path = tmp_path / "test_gt.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_data, f, ensure_ascii=False)

    return str(gt_path)


class TestF1Measurement:
    def test_load_ground_truth(self, sample_ground_truth):
        """Ground truth file should load correctly"""
        data = load_ground_truth(sample_ground_truth)

        assert "brands" in data
        assert "samples" in data
        assert len(data["brands"]) == 2
        assert len(data["samples"]) == 2

    def test_run_measurement_returns_results(self, sample_ground_truth):
        """Measurement should produce valid output structure"""
        results = run_measurement(gt_path=sample_ground_truth, fuzzy_threshold=0.85)

        assert "aggregate" in results
        assert "per_brand" in results
        assert "per_difficulty" in results
        assert "per_sample" in results

        agg = results["aggregate"]
        assert "precision" in agg
        assert "recall" in agg
        assert "f1_score" in agg
        assert "total_tp" in agg
        assert "total_fp" in agg
        assert "total_fn" in agg

    def test_f1_above_threshold(self, sample_ground_truth):
        """F1 score should be reasonable for simple test cases"""
        results = run_measurement(gt_path=sample_ground_truth, fuzzy_threshold=0.85)

        f1_score = results["aggregate"]["f1_score"]
        # With simple exact matches, F1 should be high
        assert f1_score >= 50.0  # At least 50% on simple cases
        assert isinstance(f1_score, (int, float))

    def test_precision_recall_values(self, sample_ground_truth):
        """Precision and recall should be valid percentages"""
        results = run_measurement(gt_path=sample_ground_truth, fuzzy_threshold=0.85)

        precision = results["aggregate"]["precision"]
        recall = results["aggregate"]["recall"]

        assert 0.0 <= precision <= 100.0
        assert 0.0 <= recall <= 100.0

    def test_per_brand_metrics(self, sample_ground_truth):
        """Each brand should have calculated metrics"""
        results = run_measurement(gt_path=sample_ground_truth, fuzzy_threshold=0.85)

        per_brand = results["per_brand"]

        # At least one brand should have metrics
        assert len(per_brand) >= 1

        for brand_name, metrics in per_brand.items():
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1" in metrics
            assert "tp" in metrics
            assert "fp" in metrics
            assert "fn" in metrics


class TestF1Helpers:
    def test_calc_f1_perfect_score(self):
        """Perfect prediction should yield 100% F1"""
        metrics = {"tp": 10, "fp": 0, "fn": 0}
        result = calc_f1(metrics)

        assert result["f1"] == 100.0
        assert result["precision"] == 100.0
        assert result["recall"] == 100.0

    def test_calc_f1_zero_score(self):
        """No correct predictions should yield 0% F1"""
        metrics = {"tp": 0, "fp": 5, "fn": 5}
        result = calc_f1(metrics)

        assert result["f1"] == 0.0
