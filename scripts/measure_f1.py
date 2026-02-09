#!/usr/bin/env python3
"""F1 Score Measurement Script for BrandMatcher"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.analysis.brand_matcher import Brand, BrandMatcher


def load_ground_truth(path: str) -> dict:
    """Load ground truth dataset"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ground truth file not found: {path}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_measurement(gt_path: str = None, fuzzy_threshold: float = 0.85) -> dict:
    """Run F1 measurement against ground truth"""
    if gt_path is None:
        gt_path = str(
            Path(__file__).parent.parent
            / "tests/fixtures/ground_truth/brand_matching_gt.json"
        )

    gt_data = load_ground_truth(gt_path)

    # Build brands
    brands = [
        Brand(
            id=b["id"],
            name=b["name"],
            aliases=b.get("aliases", []),
            keywords=b.get("keywords", [])
        )
        for b in gt_data["brands"]
    ]
    matcher = BrandMatcher(brands=brands, fuzzy_threshold=fuzzy_threshold)

    # Metrics
    total_tp = 0  # True Positives
    total_fp = 0  # False Positives
    total_fn = 0  # False Negatives

    per_sample_results = []
    per_brand_metrics = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    per_difficulty_metrics = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    per_match_type_metrics = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for sample in gt_data["samples"]:
        text = sample["text"]
        expected = sample["expected_matches"]

        # Run matcher
        predicted_matches = matcher.match(text)

        # Get sets of predicted and expected brand names
        predicted_brands = {m.brand_name for m in predicted_matches}
        expected_brands = {m["brand_name"] for m in expected}

        # Calculate TP, FP, FN for this sample
        tp = predicted_brands & expected_brands
        fp = predicted_brands - expected_brands
        fn = expected_brands - predicted_brands

        sample_tp = len(tp)
        sample_fp = len(fp)
        sample_fn = len(fn)

        total_tp += sample_tp
        total_fp += sample_fp
        total_fn += sample_fn

        # Per-brand tracking
        for brand in tp:
            per_brand_metrics[brand]["tp"] += 1
        for brand in fp:
            per_brand_metrics[brand]["fp"] += 1
        for brand in fn:
            per_brand_metrics[brand]["fn"] += 1

        # Per-difficulty tracking
        difficulty = sample.get("difficulty", "unknown")
        per_difficulty_metrics[difficulty]["tp"] += sample_tp
        per_difficulty_metrics[difficulty]["fp"] += sample_fp
        per_difficulty_metrics[difficulty]["fn"] += sample_fn

        # Per-match-type tracking (for expected matches that were found)
        for exp in expected:
            mt = exp.get("match_type", "unknown")
            if exp["brand_name"] in tp:
                per_match_type_metrics[mt]["tp"] += 1
            else:
                per_match_type_metrics[mt]["fn"] += 1

        per_sample_results.append({
            "id": sample["id"],
            "text_preview": text[:80] + "..." if len(text) > 80 else text,
            "language": sample.get("language", "?"),
            "difficulty": difficulty,
            "expected": list(expected_brands),
            "predicted": list(predicted_brands),
            "tp": list(tp),
            "fp": list(fp),
            "fn": list(fn),
            "correct": sample_fp == 0 and sample_fn == 0,
        })

    # Calculate aggregate metrics
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "aggregate": {
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "f1_score": round(f1 * 100, 2),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "total_samples": len(gt_data["samples"]),
            "correct_samples": sum(1 for r in per_sample_results if r["correct"]),
            "fuzzy_threshold": fuzzy_threshold,
        },
        "per_brand": {brand: calc_f1(m) for brand, m in per_brand_metrics.items()},
        "per_difficulty": {diff: calc_f1(m) for diff, m in per_difficulty_metrics.items()},
        "per_match_type": {mt: calc_f1(m) for mt, m in per_match_type_metrics.items()},
        "per_sample": per_sample_results,
    }


def calc_f1(metrics: dict) -> dict:
    """Calculate F1 from tp/fp/fn dict"""
    tp, fp, fn = metrics["tp"], metrics["fp"], metrics["fn"]
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {
        "precision": round(p * 100, 2),
        "recall": round(r * 100, 2),
        "f1": round(f1 * 100, 2),
        **metrics
    }


def print_report(results: dict):
    """Print formatted F1 report"""
    agg = results["aggregate"]

    print("=" * 60)
    print("   BrandMatcher F1 Score Report")
    print("=" * 60)
    print(f"\n  Fuzzy Threshold: {agg['fuzzy_threshold']}")
    print(f"  Total Samples:   {agg['total_samples']}")
    print(f"  Correct Samples: {agg['correct_samples']}/{agg['total_samples']}")
    print(f"\n  TP: {agg['total_tp']}  FP: {agg['total_fp']}  FN: {agg['total_fn']}")
    print(f"\n  Precision: {agg['precision']:.1f}%")
    print(f"  Recall:    {agg['recall']:.1f}%")
    print(f"  F1 Score:  {agg['f1_score']:.1f}%")

    # Pass/Fail
    status = "PASS" if agg["f1_score"] >= 80.0 else "FAIL"
    print(f"\n  Status: {status} (target >= 80%)")

    # Per-brand breakdown
    if results["per_brand"]:
        print(f"\n{'-' * 60}")
        print("  Per-Brand Breakdown:")
        for brand, m in sorted(results["per_brand"].items()):
            print(
                f"    {brand:15s}  "
                f"P={m['precision']:5.1f}%  R={m['recall']:5.1f}%  F1={m['f1']:5.1f}%"
            )

    # Per-difficulty breakdown
    if results["per_difficulty"]:
        print(f"\n{'-' * 60}")
        print("  Per-Difficulty Breakdown:")
        for diff, m in sorted(results["per_difficulty"].items()):
            print(
                f"    {diff:10s}  "
                f"P={m['precision']:5.1f}%  R={m['recall']:5.1f}%  F1={m['f1']:5.1f}%"
            )

    # Per-match-type breakdown
    if results["per_match_type"]:
        print(f"\n{'-' * 60}")
        print("  Per-Match-Type Breakdown:")
        for mt, m in sorted(results["per_match_type"].items()):
            print(
                f"    {mt:10s}  "
                f"P={m['precision']:5.1f}%  R={m['recall']:5.1f}%  F1={m['f1']:5.1f}%"
            )

    # Failed samples
    failed = [r for r in results["per_sample"] if not r["correct"]]
    if failed:
        print(f"\n{'-' * 60}")
        print(f"  Failed Samples ({len(failed)}):")
        for r in failed[:10]:  # Show first 10
            print(f"    #{r['id']} [{r['language']}/{r['difficulty']}]")
            print(f"      Text: {r['text_preview']}")
            if r["fp"]:
                print(f"      FP (unexpected): {r['fp']}")
            if r["fn"]:
                print(f"      FN (missed):     {r['fn']}")

    print(f"\n{'=' * 60}")

    # Save JSON report
    report_path = Path(__file__).parent.parent / "tests/fixtures/ground_truth/f1_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Full report saved to: {report_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Measure BrandMatcher F1 Score")
    parser.add_argument("--threshold", type=float, default=0.85, help="Fuzzy match threshold")
    parser.add_argument("--gt-path", type=str, default=None, help="Ground truth file path")
    args = parser.parse_args()

    try:
        results = run_measurement(gt_path=args.gt_path, fuzzy_threshold=args.threshold)
        print_report(results)

        # Exit with appropriate code
        sys.exit(0 if results["aggregate"]["f1_score"] >= 80.0 else 1)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Unexpected error during measurement: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
