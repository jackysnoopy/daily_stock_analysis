# -*- coding: utf-8 -*-
"""
===================================
预测校验数据访问层
===================================

职责：
1. 封装预测校验数据的数据库操作
2. 提供 CRUD 接口
3. 按股票/日期筛选校验记录
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import and_, desc, select, func

from src.storage import DatabaseManager, PredictionVerification, AnalysisHistory

logger = logging.getLogger(__name__)


class VerificationRepository:
    """
    预测校验数据访问层

    封装 PredictionVerification 表的数据库操作
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化数据访问层

        Args:
            db_manager: 数据库管理器（可选，默认使用单例）
        """
        self.db = db_manager or DatabaseManager.get_instance()

    def save(
        self,
        analysis_history_id: int,
        stock_code: str,
        analysis_date: date,
        verification_date: date,
        holding_period: int = 5,
        trend_predicted: Optional[str] = None,
        trend_actual: Optional[str] = None,
        trend_hit: Optional[bool] = None,
        sniper_points_json: Optional[str] = None,
        sniper_hit_count: int = 0,
        sniper_total_count: int = 0,
        sniper_hit_rate: Optional[float] = None,
        sentiment_predicted: Optional[int] = None,
        sentiment_actual: Optional[int] = None,
        sentiment_correlation: Optional[float] = None,
        action_predicted: Optional[str] = None,
        action_return: Optional[float] = None,
        action_hit: Optional[bool] = None,
    ) -> int:
        """
        保存校验结果

        Args:
            analysis_history_id: 关联的分析历史记录 ID
            stock_code: 股票代码
            analysis_date: 分析日期
            verification_date: 校验日期
            holding_period: 持有天数
            其他字段: 校验维度数据

        Returns:
            保存的记录 ID，失败返回 0
        """
        try:
            with self.db.get_session() as session:
                record = PredictionVerification(
                    analysis_history_id=analysis_history_id,
                    stock_code=stock_code,
                    analysis_date=analysis_date,
                    verification_date=verification_date,
                    holding_period=holding_period,
                    trend_predicted=trend_predicted,
                    trend_actual=trend_actual,
                    trend_hit=trend_hit,
                    sniper_points_json=sniper_points_json,
                    sniper_hit_count=sniper_hit_count,
                    sniper_total_count=sniper_total_count,
                    sniper_hit_rate=sniper_hit_rate,
                    sentiment_predicted=sentiment_predicted,
                    sentiment_actual=sentiment_actual,
                    sentiment_correlation=sentiment_correlation,
                    action_predicted=action_predicted,
                    action_return=action_return,
                    action_hit=action_hit,
                    created_at=datetime.now(),
                )
                session.add(record)
                session.commit()
                session.flush()
                return record.id
        except Exception as e:
            logger.error(f"保存校验结果失败: {e}")
            return 0

    def get_by_analysis_id(self, analysis_history_id: int) -> Optional[PredictionVerification]:
        """
        根据分析历史 ID 获取校验记录

        Args:
            analysis_history_id: 分析历史记录 ID

        Returns:
            PredictionVerification 对象，不存在返回 None
        """
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    select(PredictionVerification)
                    .where(PredictionVerification.analysis_history_id == analysis_history_id)
                ).scalar_one_or_none()
                return result
        except Exception as e:
            logger.error(f"查询校验记录失败: {e}")
            return None

    def get_by_id(self, verification_id: int) -> Optional[PredictionVerification]:
        """
        根据校验记录 ID 获取记录

        Args:
            verification_id: 校验记录主键 ID

        Returns:
            PredictionVerification 对象，不存在返回 None
        """
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    select(PredictionVerification)
                    .where(PredictionVerification.id == verification_id)
                ).scalar_one_or_none()
                return result
        except Exception as e:
            logger.error(f"查询校验记录失败: {e}")
            return None

    def get_list(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PredictionVerification]:
        """
        获取校验记录列表（带筛选）

        Args:
            stock_code: 股票代码筛选
            start_date: 分析日期起始（含）
            end_date: 分析日期结束（含）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            PredictionVerification 对象列表
        """
        try:
            with self.db.get_session() as session:
                conditions = []

                if stock_code:
                    conditions.append(PredictionVerification.stock_code == stock_code)
                if start_date:
                    conditions.append(PredictionVerification.analysis_date >= start_date)
                if end_date:
                    conditions.append(PredictionVerification.analysis_date <= end_date)

                query = (
                    select(PredictionVerification)
                    .where(and_(*conditions) if conditions else True)
                    .order_by(desc(PredictionVerification.verification_date))
                    .offset(offset)
                    .limit(limit)
                )

                results = session.execute(query).scalars().all()
                return list(results)
        except Exception as e:
            logger.error(f"获取校验列表失败: {e}")
            return []

    def get_pending_verifications(
        self,
        days_back: int = 30,
        holding_period: int = 5,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取待校验的分析记录

        查询条件：
        - 已超过持有周期的分析记录
        - 尚未生成校验结果

        Args:
            days_back: 回溯天数
            holding_period: 默认持有周期
            limit: 返回数量限制

        Returns:
            待校验分析记录列表（包含分析历史字段）
        """
        try:
            cutoff_date = date.today() - timedelta(days=days_back)
            expected_verification_date = date.today() - timedelta(days=holding_period)

            with self.db.get_session() as session:
                # 查询未校验且已到期的分析记录
                query = (
                    select(AnalysisHistory)
                    .where(
                        and_(
                            AnalysisHistory.created_at >= datetime.combine(cutoff_date, datetime.min.time()),
                        )
                    )
                    .order_by(desc(AnalysisHistory.created_at))
                    .limit(limit)
                )

                # 排除已有校验记录的
                verified_ids = session.execute(
                    select(PredictionVerification.analysis_history_id)
                ).scalars().all()

                results = session.execute(query).scalars().all()
                pending = [
                    r for r in results
                    if r.id not in verified_ids and (r.trend_prediction or r.operation_advice)
                ]

                return [
                    {
                        'analysis_id': r.id,
                        'stock_code': r.code,
                        'stock_name': r.name,
                        'analysis_date': r.created_at.date() if r.created_at else None,
                        'trend_prediction': r.trend_prediction,
                        'operation_advice': r.operation_advice,
                        'sentiment_score': r.sentiment_score,
                    }
                    for r in pending
                ]
        except Exception as e:
            logger.error(f"获取待校验记录失败: {e}")
            return []

    def count_by_stock(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """
        统计指定股票的校验记录数

        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            记录数量
        """
        try:
            with self.db.get_session() as session:
                conditions = [PredictionVerification.stock_code == stock_code]

                if start_date:
                    conditions.append(PredictionVerification.analysis_date >= start_date)
                if end_date:
                    conditions.append(PredictionVerification.analysis_date <= end_date)

                result = session.execute(
                    select(func.count(PredictionVerification.id))
                    .where(and_(*conditions))
                ).scalar()

                return result or 0
        except Exception as e:
            logger.error(f"统计校验记录失败: {e}")
            return 0

    def delete(self, verification_id: int) -> bool:
        """
        删除校验记录

        Args:
            verification_id: 校验记录 ID

        Returns:
            是否删除成功
        """
        try:
            with self.db.get_session() as session:
                record = session.execute(
                    select(PredictionVerification)
                    .where(PredictionVerification.id == verification_id)
                ).scalar_one_or_none()

                if record:
                    session.delete(record)
                    session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"删除校验记录失败: {e}")
            return False

    def get_stats_by_stock(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        获取指定股票的校验统计

        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            统计数据字典
        """
        try:
            records = self.get_list(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            if not records:
                return {
                    'stock_code': stock_code,
                    'total_count': 0,
                    'trend_hit_rate': None,
                    'sniper_avg_hit_rate': None,
                    'action_profit_rate': None,
                    'action_avg_return': None,
                }

            trend_hits = [r for r in records if r.trend_hit is True]
            trend_misses = [r for r in records if r.trend_hit is False]
            trend_verified = len(trend_hits) + len(trend_misses)

            sniper_records = [r for r in records if r.sniper_hit_rate is not None]
            sniper_avg = (
                sum(r.sniper_hit_rate for r in sniper_records) / len(sniper_records)
                if sniper_records else None
            )

            action_hits = [r for r in records if r.action_hit is True]
            action_verified = len([r for r in records if r.action_hit is not None])

            returns = [r.action_return for r in records if r.action_return is not None]

            return {
                'stock_code': stock_code,
                'total_count': len(records),
                'trend_hit_rate': (
                    len(trend_hits) / trend_verified * 100 if trend_verified > 0 else None
                ),
                'sniper_avg_hit_rate': sniper_avg,
                'action_profit_rate': (
                    len(action_hits) / action_verified * 100 if action_verified > 0 else None
                ),
                'action_avg_return': (
                    sum(returns) / len(returns) if returns else None
                ),
            }
        except Exception as e:
            logger.error(f"获取校验统计失败: {e}")
            return {}