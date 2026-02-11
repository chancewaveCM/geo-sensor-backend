"""Unit tests for TrendDetector service."""


from app.services.campaign.trend_detector import (
    TrendDetector,
    TrendDirection,
)


class TestCalculateTrend:
    """Tests for calculate_trend method."""

    def test_rising_trend(self) -> None:
        """Test with rising data returns 'up' direction."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.UP

    def test_declining_trend(self) -> None:
        """Test with declining data returns 'down' direction."""
        data = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.DOWN

    def test_flat_trend(self) -> None:
        """Test with flat data returns 'flat' direction."""
        data = [3.0, 3.0, 3.0, 3.0, 3.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.FLAT

    def test_empty_data(self) -> None:
        """Test with empty data returns 'flat' direction."""
        data: list[float] = []
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.FLAT

    def test_single_data_point(self) -> None:
        """Test with single data point returns 'flat' direction."""
        data = [5.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.FLAT

    def test_two_points_rising(self) -> None:
        """Test with two rising points detects upward trend."""
        data = [1.0, 10.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.UP

    def test_two_points_declining(self) -> None:
        """Test with two declining points detects downward trend."""
        data = [10.0, 1.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.DOWN

    def test_slight_noise_is_flat(self) -> None:
        """Test that minor fluctuations are treated as flat."""
        # 1% threshold means changes < 1% of mean are flat
        data = [100.0, 100.1, 100.2, 100.1, 100.0]
        result = TrendDetector.calculate_trend(data)
        assert result == TrendDirection.FLAT


class TestCalculateChange:
    """Tests for calculate_change method."""

    def test_positive_change(self) -> None:
        """Test positive change calculation."""
        result = TrendDetector.calculate_change(current=120.0, previous=100.0)
        assert result.change_percent == 20.0
        assert result.change_absolute == 20.0
        assert result.direction == TrendDirection.UP

    def test_negative_change(self) -> None:
        """Test negative change calculation."""
        result = TrendDetector.calculate_change(current=80.0, previous=100.0)
        assert result.change_percent == -20.0
        assert result.change_absolute == -20.0
        assert result.direction == TrendDirection.DOWN

    def test_zero_previous_value_positive_current(self) -> None:
        """Test division by zero prevention with positive current."""
        result = TrendDetector.calculate_change(current=50.0, previous=0.0)
        assert result.change_percent == 100.0
        assert result.change_absolute == 50.0
        assert result.direction == TrendDirection.UP

    def test_zero_previous_value_negative_current(self) -> None:
        """Test division by zero prevention with negative current."""
        result = TrendDetector.calculate_change(current=-50.0, previous=0.0)
        assert result.change_percent == -100.0
        assert result.change_absolute == -50.0
        assert result.direction == TrendDirection.DOWN

    def test_both_zero(self) -> None:
        """Test when both current and previous are zero."""
        result = TrendDetector.calculate_change(current=0.0, previous=0.0)
        assert result.change_percent == 0.0
        assert result.change_absolute == 0.0
        assert result.direction == TrendDirection.FLAT

    def test_small_change_is_flat(self) -> None:
        """Test that changes < 1% are marked as flat."""
        result = TrendDetector.calculate_change(current=100.5, previous=100.0)
        assert result.change_percent == 0.5  # < 1%
        assert result.direction == TrendDirection.FLAT

    def test_rounding(self) -> None:
        """Test that results are properly rounded."""
        result = TrendDetector.calculate_change(current=123.456789, previous=100.0)
        assert result.change_percent == 23.46  # rounded to 2 decimals
        assert result.change_absolute == 23.4568  # rounded to 4 decimals


class TestCalculateMovingAverage:
    """Tests for calculate_moving_average method."""

    def test_simple_moving_average(self) -> None:
        """Test basic moving average calculation."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = TrendDetector.calculate_moving_average(data, window=3)

        # First entry: avg of [1.0] = 1.0
        # Second entry: avg of [1.0, 2.0] = 1.5
        # Third entry: avg of [1.0, 2.0, 3.0] = 2.0
        # Fourth entry: avg of [2.0, 3.0, 4.0] = 3.0
        # Fifth entry: avg of [3.0, 4.0, 5.0] = 4.0
        assert result == [1.0, 1.5, 2.0, 3.0, 4.0]

    def test_empty_data(self) -> None:
        """Test with empty data returns empty list."""
        result = TrendDetector.calculate_moving_average([], window=3)
        assert result == []

    def test_window_size_one(self) -> None:
        """Test window size of 1 returns original data."""
        data = [1.0, 2.0, 3.0]
        result = TrendDetector.calculate_moving_average(data, window=1)
        assert result == data

    def test_window_larger_than_data(self) -> None:
        """Test window larger than data uses expanding window."""
        data = [1.0, 2.0, 3.0]
        result = TrendDetector.calculate_moving_average(data, window=10)
        # All entries use expanding window
        assert result == [1.0, 1.5, 2.0]

    def test_invalid_window_zero(self) -> None:
        """Test window size of 0 returns empty list."""
        data = [1.0, 2.0, 3.0]
        result = TrendDetector.calculate_moving_average(data, window=0)
        assert result == []

    def test_result_length_matches_input(self) -> None:
        """Test result has same length as input data."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
        result = TrendDetector.calculate_moving_average(data, window=4)
        assert len(result) == len(data)


class TestDetectAnomalies:
    """Tests for detect_anomalies method."""

    def test_detect_outliers(self) -> None:
        """Test detection of clear outliers using z-score."""
        data = [10.0, 11.0, 10.5, 11.5, 100.0, 10.0, 11.0]
        # 100.0 is a clear outlier
        result = TrendDetector.detect_anomalies(data, threshold=2.0)
        assert 4 in result  # Index of 100.0

    def test_no_anomalies(self) -> None:
        """Test data with no anomalies returns empty list."""
        data = [10.0, 11.0, 10.5, 11.5, 10.2, 10.8]
        result = TrendDetector.detect_anomalies(data, threshold=2.0)
        assert result == []

    def test_empty_data(self) -> None:
        """Test empty data returns empty list."""
        result = TrendDetector.detect_anomalies([], threshold=2.0)
        assert result == []

    def test_insufficient_data(self) -> None:
        """Test data with fewer than 3 points returns empty list."""
        result = TrendDetector.detect_anomalies([1.0, 2.0], threshold=2.0)
        assert result == []

    def test_zero_variance(self) -> None:
        """Test data with zero variance (all same values) returns empty list."""
        data = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = TrendDetector.detect_anomalies(data, threshold=2.0)
        assert result == []

    def test_custom_threshold(self) -> None:
        """Test using different threshold values."""
        data = [10.0, 10.0, 10.0, 15.0, 10.0]
        # With low threshold, moderate deviation detected
        result_strict = TrendDetector.detect_anomalies(data, threshold=1.0)
        assert len(result_strict) > 0

        # With high threshold, moderate deviation not detected
        result_lenient = TrendDetector.detect_anomalies(data, threshold=10.0)
        assert len(result_lenient) == 0

    def test_multiple_anomalies(self) -> None:
        """Test detection of multiple anomalies."""
        data = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 100.0, -80.0]
        # Both 100.0 and -80.0 are outliers (z-score ~2.0), use threshold=1.5
        result = TrendDetector.detect_anomalies(data, threshold=1.5)
        assert len(result) >= 2
        assert 6 in result  # Index of 100.0
        assert 7 in result  # Index of -80.0
