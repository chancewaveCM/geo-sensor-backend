"""Trend detection utilities for campaign timeseries analytics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class TrendDirection(str, Enum):
    """Direction of a data trend."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass
class ChangeMetrics:
    """Metrics describing a change between two values."""

    change_percent: float
    change_absolute: float
    direction: TrendDirection


class TrendDetector:
    """Static utilities for detecting trends in timeseries data."""

    @staticmethod
    def calculate_trend(data_points: list[float]) -> TrendDirection:
        """Determine trend direction via linear regression slope.

        Uses simple least-squares regression. The slope threshold is 1% of the
        mean absolute value to distinguish meaningful movement from noise.
        """
        n = len(data_points)
        if n < 2:
            return TrendDirection.FLAT

        # Simple linear regression: y = a + b*x
        x_mean = (n - 1) / 2.0
        y_mean = sum(data_points) / n

        numerator = 0.0
        denominator = 0.0
        for i, y in enumerate(data_points):
            numerator += (i - x_mean) * (y - y_mean)
            denominator += (i - x_mean) ** 2

        if denominator == 0:
            return TrendDirection.FLAT

        slope = numerator / denominator

        # Threshold: 1% of mean absolute value (avoid division by zero)
        threshold = max(abs(y_mean) * 0.01, 1e-9)

        if slope > threshold:
            return TrendDirection.UP
        if slope < -threshold:
            return TrendDirection.DOWN
        return TrendDirection.FLAT

    @staticmethod
    def calculate_moving_average(
        data_points: list[float], window: int
    ) -> list[float]:
        """Calculate simple moving average with the given window size.

        Returns a list the same length as *data_points*. The first
        ``window - 1`` entries use a smaller effective window (expanding).
        """
        if not data_points or window < 1:
            return []

        result: list[float] = []
        running_sum = 0.0
        for i, val in enumerate(data_points):
            running_sum += val
            if i >= window:
                running_sum -= data_points[i - window]
            effective_window = min(i + 1, window)
            result.append(running_sum / effective_window)
        return result

    @staticmethod
    def detect_anomalies(
        data_points: list[float], threshold: float = 2.0
    ) -> list[int]:
        """Return indices of anomalous points using z-score method.

        A point is anomalous if ``|z-score| > threshold``.
        """
        n = len(data_points)
        if n < 3:
            return []

        mean = sum(data_points) / n
        variance = sum((x - mean) ** 2 for x in data_points) / n
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0:
            return []

        return [
            i
            for i, x in enumerate(data_points)
            if abs((x - mean) / std) > threshold
        ]

    @staticmethod
    def calculate_change(current: float, previous: float) -> ChangeMetrics:
        """Calculate percentage and absolute change between two values."""
        change_absolute = current - previous

        if previous != 0:
            change_percent = (change_absolute / abs(previous)) * 100.0
        elif current != 0:
            change_percent = 100.0 if current > 0 else -100.0
        else:
            change_percent = 0.0

        if change_percent > 1.0:
            direction = TrendDirection.UP
        elif change_percent < -1.0:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.FLAT

        return ChangeMetrics(
            change_percent=round(change_percent, 2),
            change_absolute=round(change_absolute, 4),
            direction=direction,
        )
