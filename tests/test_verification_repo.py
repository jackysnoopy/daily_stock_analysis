# -*- coding: utf-8 -*-
"""Unit tests for VerificationRepository.

Tests run against a temporary SQLite database following the same pattern
as test_backtest_service.py.
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import select

from src.config import Config
from src.repositories.verification_repo import VerificationRepository
from src.storage import (
    AnalysisHistory,
    DatabaseManager,
    PredictionVerification,
)


class VerificationRepositoryTestCase(unittest.TestCase):
    """Test cases for VerificationRepository."""

    def setUp(self) -> None:
        """Set up temporary database for each test."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_verification.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        # Seed analysis history for verification testing
        self._seed_analysis_history()

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _seed_analysis_history(self) -> None:
        """Seed test analysis history records."""
        with self.db.get_session() as session:
            # Recent analysis (within holding period)
            session.add(
                AnalysisHistory(
                    query_id="test_query_1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="上涨",
                    analysis_summary="看多",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=datetime.now() - timedelta(days=2),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )

            # Older analysis (expired holding period)
            session.add(
                AnalysisHistory(
                    query_id="test_query_2",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=60,
                    operation_advice="观望",
                    trend_prediction="震荡",
                    analysis_summary="中性",
                    created_at=datetime.now() - timedelta(days=10),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )

            # Another stock
            session.add(
                AnalysisHistory(
                    query_id="test_query_3",
                    code="000001",
                    name="平安银行",
                    report_type="simple",
                    sentiment_score=40,
                    operation_advice="卖出",
                    trend_prediction="下跌",
                    analysis_summary="看空",
                    created_at=datetime.now() - timedelta(days=7),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )

            session.commit()

    def _get_record_by_id(self, verification_id: int) -> Optional[PredictionVerification]:
        """Helper to get a record within session context."""
        with self.db.get_session() as session:
            return session.execute(
                select(PredictionVerification)
                .where(PredictionVerification.id == verification_id)
            ).scalar_one_or_none()

    def _get_record_by_analysis_id(self, analysis_id: int) -> Optional[PredictionVerification]:
        """Helper to get a record by analysis_id within session context."""
        with self.db.get_session() as session:
            return session.execute(
                select(PredictionVerification)
                .where(PredictionVerification.analysis_history_id == analysis_id)
            ).scalar_one_or_none()

    def test_save_verification(self) -> None:
        """Test saving a verification record."""
        repo = VerificationRepository(self.db)

        verification_id = repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
            trend_predicted="上涨",
            trend_actual="上涨",
            trend_hit=True,
            sniper_points_json='[{"type": "support", "price": 100}]',
            sniper_hit_count=1,
            sniper_total_count=1,
            sniper_hit_rate=100.0,
            sentiment_predicted=80,
            sentiment_actual=75,
            sentiment_correlation=0.85,
            action_predicted="买入",
            action_return=5.2,
            action_hit=True,
        )

        self.assertGreater(verification_id, 0)

        # Verify record exists
        record = self._get_record_by_id(verification_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.stock_code, "600519")
        self.assertEqual(record.trend_hit, True)
        self.assertEqual(record.action_return, 5.2)

    def test_get_by_analysis_id(self) -> None:
        """Test retrieving verification by analysis_history_id."""
        repo = VerificationRepository(self.db)

        # Save verification
        repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
            trend_predicted="上涨",
            trend_actual="上涨",
            trend_hit=True,
        )

        # Retrieve by analysis_history_id using helper
        record = self._get_record_by_analysis_id(1)
        self.assertIsNotNone(record)
        self.assertEqual(record.analysis_history_id, 1)

    def test_get_list_with_filters(self) -> None:
        """Test listing verifications with filters."""
        repo = VerificationRepository(self.db)

        # Save multiple verifications
        repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
            trend_hit=True,
        )

        repo.save(
            analysis_history_id=3,
            stock_code="000001",
            analysis_date=date.today() - timedelta(days=7),
            verification_date=date.today(),
            holding_period=5,
            trend_hit=False,
        )

        # Filter by stock code
        records = repo.get_list(stock_code="600519")
        self.assertEqual(len(records), 1)
        # Check within session since objects are detached
        with self.db.get_session() as session:
            for r in records:
                refreshed = session.merge(r)
                self.assertEqual(refreshed.stock_code, "600519")

        # Filter by date range
        records = repo.get_list(
            start_date=date.today() - timedelta(days=9),
            end_date=date.today() - timedelta(days=6),
        )
        self.assertEqual(len(records), 1)

    def test_get_pending_verifications(self) -> None:
        """Test retrieving pending verification candidates."""
        repo = VerificationRepository(self.db)

        # Without any verifications, should return all expired analyses
        pending = repo.get_pending_verifications(days_back=30, holding_period=3)

        # Should include the 10-day-old analysis (expired 3-day holding)
        # Should not include the 2-day-old analysis (still within holding)
        self.assertGreater(len(pending), 0)

        # After saving a verification, it should be excluded
        repo.save(
            analysis_history_id=2,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
        )

        pending = repo.get_pending_verifications(days_back=30, holding_period=3)
        verified_ids = [p['analysis_id'] for p in pending]
        self.assertNotIn(2, verified_ids)

    def test_delete_verification(self) -> None:
        """Test deleting a verification record."""
        repo = VerificationRepository(self.db)

        # Save verification
        verification_id = repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
        )

        # Verify exists
        record = self._get_record_by_id(verification_id)
        self.assertIsNotNone(record)

        # Delete
        result = repo.delete(verification_id)
        self.assertTrue(result)

        # Verify deleted
        record = self._get_record_by_id(verification_id)
        self.assertIsNone(record)

    def test_count_by_stock(self) -> None:
        """Test counting verifications by stock."""
        repo = VerificationRepository(self.db)

        # Save multiple verifications for same stock
        repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
        )

        repo.save(
            analysis_history_id=2,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=5),
            verification_date=date.today(),
            holding_period=5,
        )

        repo.save(
            analysis_history_id=3,
            stock_code="000001",
            analysis_date=date.today() - timedelta(days=7),
            verification_date=date.today(),
            holding_period=5,
        )

        # Count for 600519
        count = repo.count_by_stock("600519")
        self.assertEqual(count, 2)

        # Count for 000001
        count = repo.count_by_stock("000001")
        self.assertEqual(count, 1)

    def test_get_stats_by_stock(self) -> None:
        """Test getting statistics by stock."""
        repo = VerificationRepository(self.db)

        # Save verifications with various results
        repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today(),
            holding_period=5,
            trend_hit=True,
            sniper_hit_rate=80.0,
            action_return=5.0,
            action_hit=True,
        )

        repo.save(
            analysis_history_id=2,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=5),
            verification_date=date.today(),
            holding_period=5,
            trend_hit=False,
            sniper_hit_rate=40.0,
            action_return=-2.0,
            action_hit=False,
        )

        stats = repo.get_stats_by_stock("600519")

        self.assertEqual(stats['stock_code'], "600519")
        self.assertEqual(stats['total_count'], 2)
        self.assertEqual(stats['trend_hit_rate'], 50.0)  # 1 hit, 1 miss
        self.assertEqual(stats['sniper_avg_hit_rate'], 60.0)  # (80 + 40) / 2
        self.assertEqual(stats['action_profit_rate'], 50.0)  # 1 profit, 1 loss
        self.assertEqual(stats['action_avg_return'], 1.5)  # (5 - 2) / 2


if __name__ == '__main__':
    unittest.main()