"""
Evaluator & Ground Truth System
F16: F1 score measurement for brand detection accuracy
"""

from dataclasses import dataclass, field

from .brand_matcher import BrandMatch


@dataclass
class GroundTruthEntry:
    """Single ground truth annotation"""
    text_id: str
    brand_id: int
    brand_name: str
    position_start: int = 0
    position_end: int = 0
    match_type: str = "exact"


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for brand detection"""
    precision: float  # TP / (TP + FP)
    recall: float     # TP / (TP + FN)
    f1_score: float   # 2 * (precision * recall) / (precision + recall)
    true_positives: int
    false_positives: int
    false_negatives: int

    def to_dict(self) -> dict:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result"""
    overall_metrics: EvaluationMetrics
    per_brand_metrics: dict[str, EvaluationMetrics] = field(default_factory=dict)
    per_match_type_metrics: dict[str, EvaluationMetrics] = field(default_factory=dict)
    target_f1: float = 0.80
    passed: bool = False

    def to_dict(self) -> dict:
        return {
            "overall_metrics": self.overall_metrics.to_dict(),
            "per_brand_metrics": {k: v.to_dict() for k, v in self.per_brand_metrics.items()},
            "per_match_type_metrics": {
                k: v.to_dict() for k, v in self.per_match_type_metrics.items()
            },
            "target_f1": self.target_f1,
            "passed": self.passed,
        }


class Evaluator:
    """
    F1 Score Evaluator for Brand Detection

    Compares predicted brand matches against ground truth annotations.
    Target: F1 >= 80%

    Evaluation modes:
    - Strict: Require exact position match
    - Relaxed: Only require brand_id match per text (default)
    """

    TARGET_F1 = 0.80

    def __init__(self, strict_position: bool = False):
        """
        Args:
            strict_position: If True, require exact position match.
                           If False, only require brand_id match per text.
        """
        self.strict_position = strict_position
        self.ground_truth: dict[str, list[GroundTruthEntry]] = {}

    def load_ground_truth(self, entries: list[dict]) -> None:
        """
        Load ground truth annotations

        Args:
            entries: List of dicts with keys:
                - text_id: Identifier for the text
                - brand_id: Brand identifier
                - brand_name: Brand name
                - position_start: Optional start position
                - position_end: Optional end position
                - match_type: Optional match type
        """
        self.ground_truth.clear()

        for entry in entries:
            text_id = str(entry['text_id'])
            gt_entry = GroundTruthEntry(
                text_id=text_id,
                brand_id=entry['brand_id'],
                brand_name=entry['brand_name'],
                position_start=entry.get('position_start', 0),
                position_end=entry.get('position_end', 0),
                match_type=entry.get('match_type', 'exact'),
            )

            if text_id not in self.ground_truth:
                self.ground_truth[text_id] = []
            self.ground_truth[text_id].append(gt_entry)

    def evaluate(
        self,
        predictions: dict[str, list[BrandMatch]],
        ground_truth: dict[str, list[GroundTruthEntry]] | None = None,
    ) -> EvaluationResult:
        """
        Evaluate predictions against ground truth

        Args:
            predictions: Dict mapping text_id to list of predicted BrandMatch
            ground_truth: Optional override for loaded ground truth

        Returns:
            EvaluationResult with F1, precision, recall metrics
        """
        gt = ground_truth or self.ground_truth

        if not gt:
            raise ValueError("No ground truth loaded. Call load_ground_truth() first.")

        # Overall metrics
        total_tp, total_fp, total_fn = 0, 0, 0

        # Per-brand tracking
        brand_stats: dict[str, dict] = {}

        # Per-match-type tracking
        type_stats: dict[str, dict] = {}

        # Evaluate each text
        all_text_ids = set(gt.keys()) | set(predictions.keys())

        for text_id in all_text_ids:
            pred_matches = predictions.get(text_id, [])
            truth_entries = gt.get(text_id, [])

            tp, fp, fn = self._evaluate_text(pred_matches, truth_entries)

            total_tp += tp
            total_fp += fp
            total_fn += fn

            # Track per-brand stats
            for truth in truth_entries:
                brand_name = truth.brand_name
                if brand_name not in brand_stats:
                    brand_stats[brand_name] = {"tp": 0, "fp": 0, "fn": 0}

                # Check if this truth was matched
                matched = any(
                    p.brand_id == truth.brand_id
                    for p in pred_matches
                )
                if matched:
                    brand_stats[brand_name]["tp"] += 1
                else:
                    brand_stats[brand_name]["fn"] += 1

            for pred in pred_matches:
                brand_name = pred.brand_name
                if brand_name not in brand_stats:
                    brand_stats[brand_name] = {"tp": 0, "fp": 0, "fn": 0}

                # Check if prediction was false positive
                matched = any(
                    t.brand_id == pred.brand_id
                    for t in truth_entries
                )
                if not matched:
                    brand_stats[brand_name]["fp"] += 1

                # Track match types
                match_type = pred.match_type.value
                if match_type not in type_stats:
                    type_stats[match_type] = {"tp": 0, "fp": 0, "fn": 0}
                if matched:
                    type_stats[match_type]["tp"] += 1
                else:
                    type_stats[match_type]["fp"] += 1

        # Calculate overall metrics
        overall_metrics = self._calculate_metrics(total_tp, total_fp, total_fn)

        # Calculate per-brand metrics
        per_brand_metrics = {
            brand: self._calculate_metrics(s["tp"], s["fp"], s["fn"])
            for brand, s in brand_stats.items()
        }

        # Calculate per-type metrics
        per_type_metrics = {
            match_type: self._calculate_metrics(s["tp"], s["fp"], s["fn"])
            for match_type, s in type_stats.items()
        }

        return EvaluationResult(
            overall_metrics=overall_metrics,
            per_brand_metrics=per_brand_metrics,
            per_match_type_metrics=per_type_metrics,
            target_f1=self.TARGET_F1,
            passed=overall_metrics.f1_score >= self.TARGET_F1,
        )

    def _evaluate_text(
        self,
        predictions: list[BrandMatch],
        truth: list[GroundTruthEntry],
    ) -> tuple[int, int, int]:
        """
        Evaluate predictions for a single text

        Returns:
            (true_positives, false_positives, false_negatives)
        """
        if self.strict_position:
            return self._evaluate_strict(predictions, truth)
        else:
            return self._evaluate_relaxed(predictions, truth)

    def _evaluate_relaxed(
        self,
        predictions: list[BrandMatch],
        truth: list[GroundTruthEntry],
    ) -> tuple[int, int, int]:
        """Relaxed evaluation - only brand_id needs to match"""
        pred_brands = {p.brand_id for p in predictions}
        truth_brands = {t.brand_id for t in truth}

        tp = len(pred_brands & truth_brands)
        fp = len(pred_brands - truth_brands)
        fn = len(truth_brands - pred_brands)

        return tp, fp, fn

    def _evaluate_strict(
        self,
        predictions: list[BrandMatch],
        truth: list[GroundTruthEntry],
    ) -> tuple[int, int, int]:
        """Strict evaluation - position must also match"""
        matched_truth: set[int] = set()
        matched_pred: set[int] = set()

        for i, pred in enumerate(predictions):
            for j, t in enumerate(truth):
                if j in matched_truth:
                    continue

                if (pred.brand_id == t.brand_id and
                    abs(pred.position_start - t.position_start) <= 5 and
                    abs(pred.position_end - t.position_end) <= 5):
                    matched_truth.add(j)
                    matched_pred.add(i)
                    break

        tp = len(matched_pred)
        fp = len(predictions) - tp
        fn = len(truth) - len(matched_truth)

        return tp, fp, fn

    def _calculate_metrics(
        self,
        tp: int,
        fp: int,
        fn: int,
    ) -> EvaluationMetrics:
        """Calculate precision, recall, F1 from counts"""
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return EvaluationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
        )

    def generate_report(self, result: EvaluationResult) -> str:
        """Generate human-readable evaluation report"""
        lines = [
            "=" * 60,
            "BRAND DETECTION EVALUATION REPORT",
            "=" * 60,
            "",
            f"Target F1 Score: {result.target_f1:.0%}",
            f"Achieved F1 Score: {result.overall_metrics.f1_score:.2%}",
            f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}",
            "",
            "--- Overall Metrics ---",
            f"Precision: {result.overall_metrics.precision:.2%}",
            f"Recall: {result.overall_metrics.recall:.2%}",
            f"F1 Score: {result.overall_metrics.f1_score:.2%}",
            "",
            f"True Positives: {result.overall_metrics.true_positives}",
            f"False Positives: {result.overall_metrics.false_positives}",
            f"False Negatives: {result.overall_metrics.false_negatives}",
            "",
        ]

        if result.per_brand_metrics:
            lines.append("--- Per-Brand F1 Scores ---")
            for brand, metrics in sorted(result.per_brand_metrics.items()):
                lines.append(f"  {brand}: {metrics.f1_score:.2%}")
            lines.append("")

        if result.per_match_type_metrics:
            lines.append("--- Per-Match-Type F1 Scores ---")
            for match_type, metrics in sorted(result.per_match_type_metrics.items()):
                lines.append(f"  {match_type}: {metrics.f1_score:.2%}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)
