# -*- coding: utf-8 -*-
"""
===================================
预测校验服务层
===================================

职责：
1. 协调分析历史数据获取
2. 调用 CalculationService 进行校验计算
3. 保存校验结果到数据库
4. 提供统计和列表查询接口
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, select

from src.repositories.verification_repo import VerificationRepository
from src.services.calculation_service import CalculationService
from src.storage import AnalysisHistory, DatabaseManager, PredictionVerification, StockDaily

logger = logging.getLogger(__name__)


class VerificationService:
    """
    预测校验服务层

    协调数据获取、计算和存储
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化校验服务

        Args:
            db_manager: 数据库管理器（可选，默认使用单例）
        """
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = VerificationRepository(self.db)
        self.calc = CalculationService()

    def verify_analysis(
        self,
        analysis_id: int,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        校验单条分析记录

        Args:
            analysis_id: 分析历史记录 ID
            force: 是否强制重新校验

        Returns:
            校验结果字典，None 表示失败
        """
        try:
            # Check existing verification
            existing = self.repo.get_by_analysis_id(analysis_id)
            if existing and not force:
                logger.info(f"分析记录 {analysis_id} 已校验，跳过")
                return self._record_to_dict(existing)

            # Fetch analysis history
            with self.db.get_session() as session:
                analysis = session.execute(
                    select(AnalysisHistory).where(AnalysisHistory.id == analysis_id)
                ).scalar_one_or_none()

                if not analysis:
                    logger.warning(f"分析记录 {analysis_id} 不存在")
                    return None

                # Copy needed fields before session closes
                analysis_data = {
                    "id": analysis.id,
                    "code": analysis.code,
                    "name": analysis.name,
                    "sentiment_score": analysis.sentiment_score,
                    "operation_advice": analysis.operation_advice,
                    "trend_prediction": analysis.trend_prediction,
                    "stop_loss": analysis.stop_loss,
                    "take_profit": analysis.take_profit,
                    "ideal_buy": analysis.ideal_buy,
                    "secondary_buy": analysis.secondary_buy,
                    "created_at": analysis.created_at,
                    "context_snapshot": analysis.context_snapshot,
                    "raw_result": analysis.raw_result,
                }

            # Parse analysis date
            analysis_date = self._resolve_analysis_date(analysis_data)
            if not analysis_date:
                logger.warning(f"无法确定分析日期: {analysis_id}")
                return None

            # Determine holding period
            holding_period = self.calc.determine_holding_period(
                operation_advice=analysis_data.get("operation_advice"),
                stop_loss=analysis_data.get("stop_loss"),
                current_price=None,
            )

            # Fetch stock daily data for holding period
            daily_data = self._fetch_daily_data(
                code=analysis_data["code"],
                start_date=analysis_date,
                holding_period=holding_period,
            )

            if not daily_data:
                logger.warning(f"无行情数据: {analysis_data['code']} @ {analysis_date}")
                return self._save_missing_data_result(
                    analysis_data=analysis_data,
                    analysis_date=analysis_date,
                    holding_period=holding_period,
                )

            # Build price series
            prices = [d.close for d in daily_data if d.close is not None]

            # Calculate verification metrics
            trend_actual, trend_hit = self.calc.verify_trend(
                predicted=analysis_data.get("trend_prediction"),
                actual_prices=prices,
            )

            sniper_points = self._parse_sniper_points(analysis_data)
            sniper_result = self.calc.verify_sniper(
                points=sniper_points,
                actual_prices=prices,
            )

            # Calculate sentiment correlation
            if prices and len(prices) >= 2:
                actual_change = (prices[-1] - prices[0]) / prices[0] * 100
            else:
                actual_change = None

            sentiment_correlation = self.calc.verify_sentiment(
                predicted_score=analysis_data.get("sentiment_score"),
                actual_change=actual_change,
            )

            # Calculate action return
            action_return, action_hit = self.calc.verify_action(
                advice=analysis_data.get("operation_advice"),
                prices=prices,
                sniper_points=sniper_points,
            )

            # Map sentiment score to actual
            sentiment_actual = self._map_change_to_sentiment(actual_change)

            # Normalize predicted trend
            trend_predicted = self.calc._normalize_trend(analysis_data.get("trend_prediction"))

            # Normalize predicted action
            action_predicted = self.calc._normalize_action(analysis_data.get("operation_advice"))

            # Save verification result
            verification_id = self.repo.save(
                analysis_history_id=analysis_data["id"],
                stock_code=analysis_data["code"],
                analysis_date=analysis_date,
                verification_date=date.today(),
                holding_period=holding_period,
                trend_predicted=trend_predicted,
                trend_actual=trend_actual,
                trend_hit=trend_hit,
                sniper_points_json=json.dumps(sniper_points, ensure_ascii=False) if sniper_points else None,
                sniper_hit_count=sniper_result["hit_count"],
                sniper_total_count=sniper_result["total_count"],
                sniper_hit_rate=sniper_result["hit_rate"],
                sentiment_predicted=analysis_data.get("sentiment_score"),
                sentiment_actual=sentiment_actual,
                sentiment_correlation=sentiment_correlation,
                action_predicted=action_predicted,
                action_return=action_return,
                action_hit=action_hit,
            )

            if verification_id <= 0:
                logger.error(f"保存校验结果失败: {analysis_id}")
                return None

            # Return saved record
            saved = self.repo.get_by_id(verification_id)
            if saved:
                result = self._record_to_dict(saved)
                result["verification_status"] = "completed"
                return result

            return None

        except Exception as e:
            logger.error(f"校验分析记录失败: {analysis_id}, {e}", exc_info=True)
            return None

    def _record_to_dict(self, record: PredictionVerification) -> Dict[str, Any]:
        """Convert record to dict within session context."""
        with self.db.get_session() as session:
            refreshed = session.merge(record)
            return {
                "id": refreshed.id,
                "analysis_history_id": refreshed.analysis_history_id,
                "stock_code": refreshed.stock_code,
                "analysis_date": refreshed.analysis_date.isoformat() if refreshed.analysis_date else None,
                "trend_predicted": refreshed.trend_predicted,
                "trend_actual": refreshed.trend_actual,
                "trend_hit": refreshed.trend_hit,
                "sniper_points_json": refreshed.sniper_points_json,
                "sniper_hit_count": refreshed.sniper_hit_count,
                "sniper_total_count": refreshed.sniper_total_count,
                "sniper_hit_rate": refreshed.sniper_hit_rate,
                "sentiment_predicted": refreshed.sentiment_predicted,
                "sentiment_actual": refreshed.sentiment_actual,
                "sentiment_correlation": refreshed.sentiment_correlation,
                "action_predicted": refreshed.action_predicted,
                "action_return": refreshed.action_return,
                "action_hit": refreshed.action_hit,
                "verification_date": refreshed.verification_date.isoformat() if refreshed.verification_date else None,
                "holding_period": refreshed.holding_period,
            }

    def _resolve_analysis_date(self, analysis_data: Dict[str, Any]) -> Optional[date]:
        """Resolve analysis date from record."""
        # Try context_snapshot first
        context_snapshot = analysis_data.get("context_snapshot")
        if context_snapshot:
            try:
                snapshot = json.loads(context_snapshot)
                enhanced = snapshot.get("enhanced_context", {})
                date_str = enhanced.get("date")
                if date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
            except (json.JSONDecodeError, ValueError):
                pass

        # Fall back to created_at
        created_at = analysis_data.get("created_at")
        if created_at:
            return created_at.date()

        return None

    def _fetch_daily_data(
        self,
        code: str,
        start_date: date,
        holding_period: int,
    ) -> List[StockDaily]:
        """Fetch stock daily data for verification window."""
        try:
            end_date = start_date + timedelta(days=holding_period)

            with self.db.get_session() as session:
                results = session.execute(
                    select(StockDaily)
                    .where(
                        and_(
                            StockDaily.code == code,
                            StockDaily.date >= start_date,
                            StockDaily.date <= end_date,
                        )
                    )
                    .order_by(StockDaily.date)
                ).scalars().all()

                return list(results)
        except Exception as e:
            logger.error(f"获取日线数据失败: {code}, {e}")
            return []

    def _parse_sniper_points(self, analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse sniper points from analysis record."""
        points = []

        # From DB columns
        ideal_buy = analysis_data.get("ideal_buy")
        secondary_buy = analysis_data.get("secondary_buy")
        stop_loss = analysis_data.get("stop_loss")
        take_profit = analysis_data.get("take_profit")

        if ideal_buy:
            points.append({"type": "ideal_buy", "price": float(ideal_buy)})
        if secondary_buy:
            points.append({"type": "secondary_buy", "price": float(secondary_buy)})
        if stop_loss:
            points.append({"type": "stop_loss", "price": float(stop_loss)})
        if take_profit:
            points.append({"type": "take_profit", "price": float(take_profit)})

        # From raw_result if available
        raw_result = analysis_data.get("raw_result")
        if raw_result and not points:
            try:
                raw = json.loads(raw_result)
                dashboard = raw.get("dashboard", {})
                battle = dashboard.get("battle_plan", {})
                sniper = battle.get("sniper_points", {})

                for key in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit"):
                    value = sniper.get(key)
                    if value:
                        price = self._parse_price(value)
                        if price:
                            points.append({"type": key, "price": price})
            except (json.JSONDecodeError, TypeError):
                pass

        return points

    def _parse_price(self, value: Any) -> Optional[float]:
        """Parse price value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").strip())
            except ValueError:
                return None
        return None

    def _map_change_to_sentiment(self, change: Optional[float]) -> Optional[int]:
        """Map actual price change to sentiment score."""
        if change is None:
            return None

        # Linear mapping: -5% -> 0, 0% -> 50, +5% -> 100
        score = 50 + change * 10
        return max(0, min(100, int(score)))

    def _save_missing_data_result(
        self,
        analysis_data: Dict[str, Any],
        analysis_date: date,
        holding_period: int,
    ) -> Dict[str, Any]:
        """Save result when daily data is missing."""
        verification_id = self.repo.save(
            analysis_history_id=analysis_data["id"],
            stock_code=analysis_data["code"],
            analysis_date=analysis_date,
            verification_date=date.today(),
            holding_period=holding_period,
        )

        return {
            "analysis_history_id": analysis_data["id"],
            "stock_code": analysis_data["code"],
            "analysis_date": analysis_date.isoformat(),
            "verification_date": date.today().isoformat(),
            "verification_status": "data_missing",
            "verification_id": verification_id,
        }

    def verify_expired_predictions(
        self,
        days_back: int = 30,
        holding_period: int = 5,
        limit: int = 100,
    ) -> Dict[str, int]:
        """
        批量校验到期预测

        Args:
            days_back: 回溯天数
            holding_period: 默认持有周期
            limit: 处理数量限制

        Returns:
            {
                "processed": 处理总数,
                "verified": 成功校验数,
                "failed": 失败数,
                "skipped": 跳过数（已校验）
            }
        """
        try:
            pending = self.repo.get_pending_verifications(
                days_back=days_back,
                holding_period=holding_period,
                limit=limit,
            )

            processed = len(pending)
            verified = 0
            failed = 0
            skipped = 0

            for item in pending:
                analysis_id = item.get("analysis_id")
                if not analysis_id:
                    continue

                # Check if already verified
                existing = self.repo.get_by_analysis_id(analysis_id)
                if existing:
                    skipped += 1
                    continue

                result = self.verify_analysis(analysis_id=analysis_id)
                if result and result.get("verification_status") != "failed":
                    verified += 1
                else:
                    failed += 1

            return {
                "processed": processed,
                "verified": verified,
                "failed": failed,
                "skipped": skipped,
            }

        except Exception as e:
            logger.error(f"批量校验失败: {e}", exc_info=True)
            return {
                "processed": 0,
                "verified": 0,
                "failed": 0,
                "skipped": 0,
            }

    def get_stats(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        获取校验统计数据

        Args:
            stock_code: 股票代码筛选（可选，None 表示全部）
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            统计数据字典
        """
        try:
            if stock_code:
                return self.repo.get_stats_by_stock(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                )

            # Overall stats: aggregate across all stocks
            records = self.repo.get_list(
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            if not records:
                return {
                    "stock_code": None,
                    "total_count": 0,
                    "trend_hit_rate": None,
                    "sniper_avg_hit_rate": None,
                    "action_profit_rate": None,
                    "action_avg_return": None,
                }

            # Calculate aggregated metrics
            with self.db.get_session() as session:
                trend_hits = sum(1 for r in records if session.merge(r).trend_hit is True)
                trend_misses = sum(1 for r in records if session.merge(r).trend_hit is False)
                trend_verified = trend_hits + trend_misses

                sniper_records = [r for r in records if session.merge(r).sniper_hit_rate is not None]
                sniper_avg = (
                    sum(session.merge(r).sniper_hit_rate for r in sniper_records) / len(sniper_records)
                    if sniper_records else None
                )

                action_hits = sum(1 for r in records if session.merge(r).action_hit is True)
                action_verified = sum(1 for r in records if session.merge(r).action_hit is not None)

                returns = [session.merge(r).action_return for r in records if session.merge(r).action_return is not None]

            return {
                "stock_code": None,
                "total_count": len(records),
                "trend_hit_rate": (
                    trend_hits / trend_verified * 100 if trend_verified > 0 else None
                ),
                "sniper_avg_hit_rate": sniper_avg,
                "action_profit_rate": (
                    action_hits / action_verified * 100 if action_verified > 0 else None
                ),
                "action_avg_return": (
                    sum(returns) / len(returns) if returns else None
                ),
            }

        except Exception as e:
            logger.error(f"获取校验统计失败: {e}", exc_info=True)
            return {}

    def get_list(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        获取校验结果列表

        Args:
            stock_code: 股票代码筛选
            start_date: 起始日期
            end_date: 结束日期
            limit: 每页数量
            page: 页码

        Returns:
            {
                "total": 总数,
                "page": 页码,
                "limit": 每页数量,
                "items": 结果列表
            }
        """
        try:
            offset = max(page - 1, 0) * limit

            records = self.repo.get_list(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            )

            # Get total count
            if stock_code:
                total = self.repo.count_by_stock(stock_code, start_date, end_date)
            else:
                # Approximate total from unpaginated query
                all_records = self.repo.get_list(
                    start_date=start_date,
                    end_date=end_date,
                    limit=10000,
                )
                total = len(all_records)

            items = []
            for record in records:
                item = self._record_to_dict(record)
                item["stock_name"] = self._get_stock_name(record.stock_code)
                items.append(item)

            return {
                "total": total,
                "page": page,
                "limit": limit,
                "items": items,
            }

        except Exception as e:
            logger.error(f"获取校验列表失败: {e}", exc_info=True)
            return {
                "total": 0,
                "page": page,
                "limit": limit,
                "items": [],
            }

    def _get_stock_name(self, code: str) -> Optional[str]:
        """Get stock name from code."""
        try:
            with self.db.get_session() as session:
                history = session.execute(
                    select(AnalysisHistory)
                    .where(AnalysisHistory.code == code)
                    .limit(1)
                ).scalar_one_or_none()

                if history:
                    return history.name
        except Exception:
            pass
        return None