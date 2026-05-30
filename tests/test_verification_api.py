# -*- coding: utf-8 -*-
"""Unit tests for verification API endpoints.

Tests run against a temporary SQLite database with seeded data,
using a minimal FastAPI app to avoid full dependency chain.
"""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import Config
from src.repositories.verification_repo import VerificationRepository
from src.storage import (
    AnalysisHistory,
    DatabaseManager,
)

# Import the verification router directly by loading the module file
# This avoids the api.v1 module hierarchy which imports all endpoints
import importlib.util
spec = importlib.util.spec_from_file_location(
    "verification_endpoint",
    "api/v1/endpoints/verification.py"
)
verification_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification_module)
verification_router = verification_module.router


class VerificationAPITestCase(unittest.TestCase):
    """Test cases for verification API endpoints."""

    def setUp(self) -> None:
        """Set up temporary database and test client."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_verification_api.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        # Seed test data
        self._seed_test_data()

        # Create minimal FastAPI app with just verification router
        app = FastAPI()
        app.include_router(verification_router, prefix="/api/v1/verification")
        self.client = TestClient(app)

        # Create repository
        self.repo = VerificationRepository(self.db)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _seed_test_data(self) -> None:
        """Seed test analysis history and verification records."""
        with self.db.get_session() as session:
            # Analysis history records
            session.add(
                AnalysisHistory(
                    query_id="test_query_1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="上涨",
                    analysis_summary="看好短期走势",
                    stop_loss=1800.0,
                    take_profit=2000.0,
                    created_at=datetime.now() - timedelta(days=10),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-15"}}',
                )
            )

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
                    created_at=datetime.now() - timedelta(days=15),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-10"}}',
                )
            )

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
                    context_snapshot='{"enhanced_context": {"date": "2024-01-18"}}',
                )
            )

            session.commit()

        # Seed verification records
        self.repo.save(
            analysis_history_id=1,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=10),
            verification_date=date.today() - timedelta(days=5),
            holding_period=5,
            trend_predicted="上涨",
            trend_actual="上涨",
            trend_hit=True,
            sniper_points_json='[{"type": "support", "price": 1850, "label": "支撑位"}, {"type": "resistance", "price": 1950, "label": "压力位"}]',
            sniper_hit_count=1,
            sniper_total_count=2,
            sniper_hit_rate=50.0,
            sentiment_predicted=80,
            sentiment_actual=75,
            sentiment_correlation=0.85,
            action_predicted="买入",
            action_return=5.2,
            action_hit=True,
        )

        self.repo.save(
            analysis_history_id=2,
            stock_code="600519",
            analysis_date=date.today() - timedelta(days=15),
            verification_date=date.today() - timedelta(days=10),
            holding_period=5,
            trend_predicted="震荡",
            trend_actual="下跌",
            trend_hit=False,
            sniper_points_json=None,
            sniper_hit_count=0,
            sniper_total_count=0,
            sniper_hit_rate=None,
            sentiment_predicted=60,
            sentiment_actual=40,
            sentiment_correlation=0.5,
            action_predicted="观望",
            action_return=0.0,
            action_hit=True,
        )

        self.repo.save(
            analysis_history_id=3,
            stock_code="000001",
            analysis_date=date.today() - timedelta(days=7),
            verification_date=date.today() - timedelta(days=2),
            holding_period=5,
            trend_predicted="下跌",
            trend_actual="下跌",
            trend_hit=True,
            sniper_points_json=None,
            sniper_hit_count=0,
            sniper_total_count=0,
            sniper_hit_rate=None,
            sentiment_predicted=40,
            sentiment_actual=45,
            sentiment_correlation=0.6,
            action_predicted="卖出",
            action_return=2.5,
            action_hit=True,
        )

    def test_get_stats_no_filters(self) -> None:
        """Test GET /stats without filters."""
        response = self.client.get("/api/v1/verification/stats")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_count"], 3)

        # Trend hit rate: 2 hits, 1 miss = 66.67%
        self.assertAlmostEqual(data["trend_hit_rate"], 66.67, places=1)

        # Sniper avg: only 1 record with rate = 50.0
        self.assertEqual(data["sniper_avg_hit_rate"], 50.0)

        # Action profit rate: all 3 profitable
        self.assertEqual(data["action_profit_rate"], 100.0)

        # By stock
        self.assertEqual(len(data["by_stock"]), 2)  # 600519 and 000001

    def test_get_stats_with_stock_filter(self) -> None:
        """Test GET /stats with stock_code filter."""
        response = self.client.get("/api/v1/verification/stats?stock_code=600519")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total_count"], 2)
        self.assertEqual(len(data["by_stock"]), 1)
        self.assertEqual(data["by_stock"][0]["stock_code"], "600519")

    def test_get_stats_with_date_filter(self) -> None:
        """Test GET /stats with date range filter."""
        start_date = (date.today() - timedelta(days=14)).isoformat()
        end_date = (date.today() - timedelta(days=6)).isoformat()

        response = self.client.get(
            f"/api/v1/verification/stats?start_date={start_date}&end_date={end_date}"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Should include record from days_back=10 and days_back=7
        self.assertEqual(data["total_count"], 2)

    def test_get_list_no_filters(self) -> None:
        """Test GET /list without filters."""
        response = self.client.get("/api/v1/verification/list")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 20)
        self.assertEqual(len(data["items"]), 3)

    def test_get_list_with_pagination(self) -> None:
        """Test GET /list with pagination."""
        response = self.client.get("/api/v1/verification/list?page=1&limit=2")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 2)
        self.assertEqual(len(data["items"]), 2)

    def test_get_list_with_stock_filter(self) -> None:
        """Test GET /list with stock_code filter."""
        response = self.client.get("/api/v1/verification/list?stock_code=600519")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        for item in data["items"]:
            self.assertEqual(item["stock_code"], "600519")

    def test_get_list_with_trend_hit_filter(self) -> None:
        """Test GET /list with trend_hit filter."""
        response = self.client.get("/api/v1/verification/list?trend_hit=true")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["total"], 2)
        for item in data["items"]:
            self.assertEqual(item["trend_hit"], True)

    def test_get_detail_existing(self) -> None:
        """Test GET /{id} with existing verification."""
        # Get verification ID from list
        list_response = self.client.get("/api/v1/verification/list?limit=1")
        verification_id = list_response.json()["items"][0]["id"]

        response = self.client.get(f"/api/v1/verification/{verification_id}")

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["id"], verification_id)
        self.assertIn("stock_code", data)
        self.assertIn("analysis_date", data)
        self.assertIn("sniper_points", data)

    def test_get_detail_not_found(self) -> None:
        """Test GET /{id} with non-existent verification."""
        response = self.client.get("/api/v1/verification/99999")

        self.assertEqual(response.status_code, 404)

        data = response.json()
        self.assertIn("error", data["detail"])
        self.assertEqual(data["detail"]["error"], "not_found")

    def test_post_run_batch(self) -> None:
        """Test POST /run for batch verification."""
        response = self.client.post(
            "/api/v1/verification/run",
            json={"days_back": 30},
        )

        self.assertIn(response.status_code, [200, 202])

        data = response.json()
        self.assertIn("status", data)
        self.assertIn("message", data)

    def test_post_run_single_existing(self) -> None:
        """Test POST /run/{analysis_id} with existing analysis."""
        # Analysis ID 1 already has verification
        response = self.client.post("/api/v1/verification/run/1")

        self.assertIn(response.status_code, [200, 202])

        data = response.json()
        self.assertEqual(data["analysis_history_id"], 1)
        self.assertIn("verification_id", data)

    def test_post_run_single_not_found(self) -> None:
        """Test POST /run/{analysis_id} with non-existent analysis."""
        response = self.client.post("/api/v1/verification/run/99999")

        self.assertEqual(response.status_code, 404)

        data = response.json()
        self.assertIn("error", data["detail"])
        self.assertEqual(data["detail"]["error"], "not_found")


if __name__ == '__main__':
    unittest.main()