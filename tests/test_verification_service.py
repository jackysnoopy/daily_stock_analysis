# -*- coding: utf-8 -*-
"""Unit tests for VerificationService and CalculationService.

Tests run against a temporary SQLite database following the same pattern
as test_verification_repo.py.
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import select

from src.config import Config
from src.repositories.verification_repo import VerificationRepository
from src.services.calculation_service import CalculationService
from src.services.verification_service import VerificationService
from src.storage import (
    AnalysisHistory,
    DatabaseManager,
    PredictionVerification,
    StockDaily,
)


class CalculationServiceTestCase(unittest.TestCase):
    """Test cases for CalculationService."""

    def setUp(self) -> None:
        """Set up calculation service for tests."""
        self.calc = CalculationService()

    def test_determine_holding_period_short_term(self) -> None:
        """Test inferring short-term holding period."""
        self.assertEqual(self.calc.determine_holding_period("短线买入"), 3)
        self.assertEqual(self.calc.determine_holding_period("短线操作，快进快出"), 3)
        self.assertEqual(self.calc.determine_holding_period("短期持有"), 3)

    def test_determine_holding_period_medium_term(self) -> None:
        """Test inferring medium-term holding period."""
        self.assertEqual(self.calc.determine_holding_period("中线布局"), 7)
        self.assertEqual(self.calc.determine_holding_period("中线持有"), 7)
        self.assertEqual(self.calc.determine_holding_period("中期看涨"), 7)

    def test_determine_holding_period_long_term(self) -> None:
        """Test inferring long-term holding period."""
        self.assertEqual(self.calc.determine_holding_period("长线投资"), 25)
        self.assertEqual(self.calc.determine_holding_period("长期持有"), 25)

    def test_determine_holding_period_default(self) -> None:
        """Test default holding period when no indicators."""
        self.assertEqual(self.calc.determine_holding_period("观望"), 5)
        self.assertEqual(self.calc.determine_holding_period(""), 5)
        self.assertEqual(self.calc.determine_holding_period(None), 5)

    def test_verify_trend_up_hit(self) -> None:
        """Test trend verification when predicted up and actual is up."""
        prices = [100.0, 102.0, 104.0, 106.0]  # +6%
        actual, hit = self.calc.verify_trend(predicted="上涨", actual_prices=prices)

        self.assertEqual(actual, "上涨")
        self.assertTrue(hit)

    def test_verify_trend_down_hit(self) -> None:
        """Test trend verification when predicted down and actual is down."""
        prices = [100.0, 98.0, 96.0, 94.0]  # -6%
        actual, hit = self.calc.verify_trend(predicted="下跌", actual_prices=prices)

        self.assertEqual(actual, "下跌")
        self.assertTrue(hit)

    def test_verify_trend_flat_hit(self) -> None:
        """Test trend verification when predicted flat and actual is flat."""
        prices = [100.0, 100.5, 101.0, 100.5]  # +0.5%
        actual, hit = self.calc.verify_trend(predicted="震荡", actual_prices=prices)

        self.assertEqual(actual, "震荡")
        self.assertTrue(hit)

    def test_verify_trend_miss(self) -> None:
        """Test trend verification when prediction is wrong."""
        prices = [100.0, 102.0, 104.0, 106.0]  # +6%
        actual, hit = self.calc.verify_trend(predicted="下跌", actual_prices=prices)

        self.assertEqual(actual, "上涨")
        self.assertFalse(hit)

    def test_verify_trend_insufficient_data(self) -> None:
        """Test trend verification with insufficient data."""
        actual, hit = self.calc.verify_trend(predicted="上涨", actual_prices=[])
        self.assertIsNone(actual)
        self.assertIsNone(hit)

        actual, hit = self.calc.verify_trend(predicted="上涨", actual_prices=[100.0])
        self.assertIsNone(actual)
        self.assertIsNone(hit)

    def test_verify_sniper_support_hit(self) -> None:
        """Test sniper verification when support is touched."""
        points = [
            {"type": "support", "price": 95.0},
            {"type": "buy", "price": 96.0},
        ]
        prices = [100.0, 98.0, 94.5, 96.0, 97.0]  # Low touched 94.5 < 95.0

        result = self.calc.verify_sniper(points=points, actual_prices=prices)

        self.assertEqual(result["hit_count"], 2)
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(result["hit_rate"], 100.0)

    def test_verify_sniper_no_points(self) -> None:
        """Test sniper verification with no sniper points."""
        prices = [100.0, 102.0, 104.0]
        result = self.calc.verify_sniper(points=[], actual_prices=prices)

        self.assertEqual(result["hit_count"], 0)
        self.assertEqual(result["total_count"], 0)
        self.assertIsNone(result["hit_rate"])

    def test_verify_action_buy_profit(self) -> None:
        """Test action verification for profitable buy."""
        prices = [100.0, 102.0, 105.0, 108.0]
        return_pct, hit = self.calc.verify_action(
            advice="买入",
            prices=prices,
            sniper_points=None,
        )

        self.assertEqual(return_pct, 8.0)
        self.assertTrue(hit)

    def test_verify_action_buy_loss(self) -> None:
        """Test action verification for losing buy."""
        prices = [100.0, 98.0, 95.0, 92.0]
        return_pct, hit = self.calc.verify_action(
            advice="买入",
            prices=prices,
            sniper_points=None,
        )

        self.assertEqual(return_pct, -8.0)
        self.assertFalse(hit)

    def test_verify_action_hold(self) -> None:
        """Test action verification for hold/watch."""
        prices = [100.0, 102.0, 105.0]
        return_pct, hit = self.calc.verify_action(
            advice="观望",
            prices=prices,
            sniper_points=None,
        )

        self.assertEqual(return_pct, 0.0)
        self.assertTrue(hit)

    def test_verify_sentiment_positive_correlation(self) -> None:
        """Test sentiment verification with positive correlation."""
        # Predicted 80 (bullish), actual +5%
        correlation = self.calc.verify_sentiment(predicted_score=80, actual_change=5.0)

        # Expected change for score 80: (80-50)/10 = 3%
        # Correlation should be positive (> 0.5)
        self.assertGreater(correlation, 0.5)

    def test_verify_sentiment_neutral_score(self) -> None:
        """Test sentiment verification with neutral score."""
        # Predicted 50 (neutral), actual +1%
        correlation = self.calc.verify_sentiment(predicted_score=50, actual_change=1.0)
        self.assertIsNotNone(correlation)


class VerificationServiceTestCase(unittest.TestCase):
    """Test cases for VerificationService."""

    def setUp(self) -> None:
        """Set up temporary database for each test."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_verification.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        # Seed test data
        self._seed_test_data()

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _seed_test_data(self) -> None:
        """Seed analysis history and stock daily data."""
        # Use a fixed analysis date that matches context_snapshot
        analysis_date = datetime(2024, 1, 1)

        with self.db.get_session() as session:
            # Analysis history
            analysis = AnalysisHistory(
                query_id="test_query_verify",
                code="600519",
                name="贵州茅台",
                report_type="simple",
                sentiment_score=80,
                operation_advice="买入",
                trend_prediction="上涨",
                analysis_summary="看多",
                stop_loss=95.0,
                take_profit=110.0,
                created_at=analysis_date,
                context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
            )
            session.add(analysis)
            session.commit()
            session.flush()
            self.analysis_id = analysis.id

            # Stock daily data for verification window (starting from 2024-01-01)
            base_price = 100.0
            for i in range(10):
                daily_date = date(2024, 1, 1 + i)
                session.add(StockDaily(
                    code="600519",
                    date=daily_date,
                    open=base_price + i * 0.5,
                    high=base_price + i * 0.8,
                    low=base_price + i * 0.2,
                    close=base_price + i * 0.6 + i * 0.5,  # Upward trend
                    volume=1000000,
                ))
                base_price += i * 0.3

            session.commit()

    def test_verify_analysis_success(self) -> None:
        """Test verifying a single analysis record."""
        service = VerificationService(self.db)

        result = service.verify_analysis(analysis_id=self.analysis_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "600519")
        self.assertEqual(result["trend_predicted"], "上涨")
        self.assertEqual(result["verification_status"], "completed")

    def test_verify_analysis_no_price_data(self) -> None:
        """Test verifying when stock daily data is missing."""
        service = VerificationService(self.db)

        # Analysis for stock without daily data
        with self.db.get_session() as session:
            analysis = AnalysisHistory(
                query_id="test_no_data",
                code="999999",
                name="无数据股票",
                report_type="simple",
                sentiment_score=60,
                operation_advice="买入",
                trend_prediction="上涨",
                created_at=datetime.now() - timedelta(days=10),
                context_snapshot='{}',
            )
            session.add(analysis)
            session.commit()
            session.flush()
            no_data_id = analysis.id

        result = service.verify_analysis(analysis_id=no_data_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["verification_status"], "data_missing")

    def test_get_stats(self) -> None:
        """Test getting verification statistics."""
        service = VerificationService(self.db)

        # Verify the test analysis
        service.verify_analysis(analysis_id=self.analysis_id)

        stats = service.get_stats(stock_code="600519")

        self.assertIsNotNone(stats)
        self.assertEqual(stats["stock_code"], "600519")
        self.assertIn("total_count", stats)
        self.assertIn("trend_hit_rate", stats)

    def test_get_list(self) -> None:
        """Test getting verification list."""
        service = VerificationService(self.db)

        # Verify test analysis
        service.verify_analysis(analysis_id=self.analysis_id)

        result = service.get_list(stock_code="600519", limit=10)

        self.assertIsNotNone(result)
        self.assertIn("total", result)
        self.assertIn("items", result)
        self.assertGreater(result["total"], 0)


if __name__ == '__main__':
    unittest.main()