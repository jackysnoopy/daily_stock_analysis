# -*- coding: utf-8 -*-
"""
===================================
预测校验接口
===================================

职责：
1. 提供 GET /api/v1/verification/stats 获取统计接口
2. 提供 GET /api/v1/verification/list 获取列表接口
3. 提供 GET /api/v1/verification/{id} 获取详情接口
4. 提供 POST /api/v1/verification/run 批量触发校验接口
5. 提供 POST /api/v1/verification/run/{analysis_id} 单条校验接口

特性：
- 支持按股票/日期筛选
- 支持分页查询
- 支持多维度统计（趋势/狙击/情绪/操作）
"""

import json
import logging
from datetime import date
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body

from api.v1.schemas.verification import (
    VerificationStatsRequest,
    VerificationStatsResponse,
    StockStats,
    PeriodStats,
    VerificationListRequest,
    VerificationListResponse,
    VerificationListItem,
    VerificationDetailResponse,
    SniperPointDetail,
    VerificationRunRequest,
    VerificationRunResponse,
    VerificationSingleRunResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.repositories.verification_repo import VerificationRepository
from src.repositories.analysis_repo import AnalysisRepository
from src.storage import DatabaseManager, AnalysisHistory

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_verification_repo() -> VerificationRepository:
    """Get verification repository instance."""
    return VerificationRepository()


def _get_analysis_repo() -> AnalysisRepository:
    """Get analysis repository instance."""
    return AnalysisRepository()


def _get_db() -> DatabaseManager:
    """Get database manager instance."""
    return DatabaseManager.get_instance()


# ============================================================
# GET /stats - 获取统计
# ============================================================

@router.get(
    "/stats",
    response_model=VerificationStatsResponse,
    responses={
        200: {"description": "校验统计", "model": VerificationStatsResponse},
        500: {"description": "查询失败", "model": ErrorResponse},
    },
    summary="获取预测准确率统计",
    description="查询预测校验的统计数据，支持按股票和时间筛选，可指定维度。"
)
def get_verification_stats(
    stock_code: Optional[str] = Query(
        None,
        description="股票代码筛选",
        json_schema_extra={"example": "600519"},
    ),
    start_date: Optional[date] = Query(
        None,
        description="起始日期（分析日期）",
        json_schema_extra={"example": "2024-01-01"},
    ),
    end_date: Optional[date] = Query(
        None,
        description="结束日期（分析日期）",
        json_schema_extra={"example": "2024-12-31"},
    ),
    dimension: Optional[str] = Query(
        None,
        description="统计维度：trend/sniper/sentiment/action",
        pattern="^(trend|sniper|sentiment|action)$",
        json_schema_extra={"example": "trend"},
    ),
    repo: VerificationRepository = Depends(_get_verification_repo),
) -> VerificationStatsResponse:
    """
    获取预测准确率统计

    流程：
    1. 根据筛选条件获取校验记录列表
    2. 计算整体统计指标
    3. 按股票分组计算
    4. 按时间段分组计算

    Args:
        stock_code: 股票代码筛选（可选）
        start_date: 起始日期（可选）
        end_date: 结束日期（可选）
        dimension: 统计维度（可选）
        repo: VerificationRepository 实例

    Returns:
        VerificationStatsResponse: 统计数据

    Raises:
        HTTPException: 500 - 查询失败
    """
    try:
        # 获取校验记录列表（最大 1000 条用于统计）
        records = repo.get_list(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        if not records:
            return VerificationStatsResponse(
                total_count=0,
                trend_hit_rate=None,
                sniper_avg_hit_rate=None,
                sentiment_avg_correlation=None,
                action_profit_rate=None,
                action_avg_return=None,
                by_stock=[],
                by_period=[],
            )

        # 计算整体统计
        trend_hits = [r for r in records if r.trend_hit is True]
        trend_misses = [r for r in records if r.trend_hit is False]
        trend_verified = len(trend_hits) + len(trend_misses)
        trend_hit_rate = (
            len(trend_hits) / trend_verified * 100 if trend_verified > 0 else None
        )

        sniper_records = [r for r in records if r.sniper_hit_rate is not None]
        sniper_avg_hit_rate = (
            sum(r.sniper_hit_rate for r in sniper_records) / len(sniper_records)
            if sniper_records else None
        )

        sentiment_records = [r for r in records if r.sentiment_correlation is not None]
        sentiment_avg_correlation = (
            sum(r.sentiment_correlation for r in sentiment_records) / len(sentiment_records)
            if sentiment_records else None
        )

        action_hits = [r for r in records if r.action_hit is True]
        action_misses = [r for r in records if r.action_hit is False]
        action_verified = len(action_hits) + len(action_misses)
        action_profit_rate = (
            len(action_hits) / action_verified * 100 if action_verified > 0 else None
        )

        returns = [r.action_return for r in records if r.action_return is not None]
        action_avg_return = sum(returns) / len(returns) if returns else None

        # 按股票分组统计
        stock_groups: Dict[str, List[Any]] = {}
        for r in records:
            stock_groups.setdefault(r.stock_code, []).append(r)

        by_stock = []
        db = _get_db()
        for stock_code_key, stock_records in stock_groups.items():
            # 获取股票名称
            stock_name = None
            try:
                history_records = db.get_analysis_history(
                    code=stock_code_key,
                    limit=1,
                )
                if history_records:
                    stock_name = history_records[0].name
            except Exception:
                pass

            s_trend_hits = [r for r in stock_records if r.trend_hit is True]
            s_trend_verified = len([r for r in stock_records if r.trend_hit is not None])
            s_trend_hit_rate = (
                len(s_trend_hits) / s_trend_verified * 100 if s_trend_verified > 0 else None
            )

            s_sniper_records = [r for r in stock_records if r.sniper_hit_rate is not None]
            s_sniper_avg = (
                sum(r.sniper_hit_rate for r in s_sniper_records) / len(s_sniper_records)
                if s_sniper_records else None
            )

            s_sentiment_records = [r for r in stock_records if r.sentiment_correlation is not None]
            s_sentiment_avg = (
                sum(r.sentiment_correlation for r in s_sentiment_records) / len(s_sentiment_records)
                if s_sentiment_records else None
            )

            s_action_hits = [r for r in stock_records if r.action_hit is True]
            s_action_verified = len([r for r in stock_records if r.action_hit is not None])
            s_action_profit_rate = (
                len(s_action_hits) / s_action_verified * 100 if s_action_verified > 0 else None
            )

            s_returns = [r.action_return for r in stock_records if r.action_return is not None]
            s_action_avg_return = sum(s_returns) / len(s_returns) if s_returns else None

            by_stock.append(StockStats(
                stock_code=stock_code_key,
                stock_name=stock_name,
                total_count=len(stock_records),
                trend_hit_rate=s_trend_hit_rate,
                sniper_avg_hit_rate=s_sniper_avg,
                sentiment_avg_correlation=s_sentiment_avg,
                action_profit_rate=s_action_profit_rate,
                action_avg_return=s_action_avg_return,
            ))

        # 按周分组统计（简化实现，按 analysis_date 所属周分组）
        week_groups: Dict[str, List[Any]] = {}
        for r in records:
            if r.analysis_date:
                # 计算周标识（ISO week）
                iso_year, iso_week, _ = r.analysis_date.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                week_groups.setdefault(week_key, []).append(r)

        by_period = []
        for week_key, week_records in sorted(week_groups.items(), reverse=True):
            # 计算周的起始和结束日期
            first_date = min(r.analysis_date for r in week_records)
            last_date = max(r.analysis_date for r in week_records)

            w_trend_hits = [r for r in week_records if r.trend_hit is True]
            w_trend_verified = len([r for r in week_records if r.trend_hit is not None])
            w_trend_hit_rate = (
                len(w_trend_hits) / w_trend_verified * 100 if w_trend_verified > 0 else None
            )

            w_returns = [r.action_return for r in week_records if r.action_return is not None]
            w_action_avg_return = sum(w_returns) / len(w_returns) if w_returns else None

            by_period.append(PeriodStats(
                period=week_key,
                start_date=first_date,
                end_date=last_date,
                total_count=len(week_records),
                trend_hit_rate=w_trend_hit_rate,
                action_avg_return=w_action_avg_return,
            ))

        return VerificationStatsResponse(
            total_count=len(records),
            trend_hit_rate=trend_hit_rate,
            sniper_avg_hit_rate=sniper_avg_hit_rate,
            sentiment_avg_correlation=sentiment_avg_correlation,
            action_profit_rate=action_profit_rate,
            action_avg_return=action_avg_return,
            by_stock=by_stock,
            by_period=by_period,
        )

    except Exception as e:
        logger.error(f"查询校验统计失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"查询校验统计失败: {str(e)}"
            }
        )


# ============================================================
# GET /list - 获取列表（分页）
# ============================================================

@router.get(
    "/list",
    response_model=VerificationListResponse,
    responses={
        200: {"description": "校验列表", "model": VerificationListResponse},
        500: {"description": "查询失败", "model": ErrorResponse},
    },
    summary="获取预测校验列表",
    description="查询预测校验记录列表，支持按股票、日期、命中状态筛选，支持分页。"
)
def get_verification_list(
    stock_code: Optional[str] = Query(
        None,
        description="股票代码筛选",
        json_schema_extra={"example": "600519"},
    ),
    start_date: Optional[date] = Query(
        None,
        description="起始日期（分析日期）",
        json_schema_extra={"example": "2024-01-01"},
    ),
    end_date: Optional[date] = Query(
        None,
        description="结束日期（分析日期）",
        json_schema_extra={"example": "2024-12-31"},
    ),
    trend_hit: Optional[bool] = Query(
        None,
        description="趋势命中筛选",
        json_schema_extra={"example": True},
    ),
    action_hit: Optional[bool] = Query(
        None,
        description="操作建议盈利筛选",
        json_schema_extra={"example": True},
    ),
    page: int = Query(
        1,
        description="页码（从 1 开始）",
        ge=1,
        json_schema_extra={"example": 1},
    ),
    limit: int = Query(
        20,
        description="每页数量",
        ge=1,
        le=100,
        json_schema_extra={"example": 20},
    ),
    repo: VerificationRepository = Depends(_get_verification_repo),
) -> VerificationListResponse:
    """
    获取预测校验列表

    流程：
    1. 根据筛选条件查询校验记录
    2. 应用命中状态筛选
    3. 分页返回结果

    Args:
        stock_code: 股票代码筛选（可选）
        start_date: 起始日期（可选）
        end_date: 结束日期（可选）
        trend_hit: 趋势命中筛选（可选）
        action_hit: 操作建议盈利筛选（可选）
        page: 页码
        limit: 每页数量
        repo: VerificationRepository 实例

    Returns:
        VerificationListResponse: 校验列表

    Raises:
        HTTPException: 500 - 查询失败
    """
    try:
        offset = (page - 1) * limit

        # 获取记录列表
        records = repo.get_list(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit * 2,  # 预留空间用于命中筛选
            offset=offset,
        )

        # 应用命中状态筛选（Repository 层未支持）
        if trend_hit is not None:
            records = [r for r in records if r.trend_hit == trend_hit]

        if action_hit is not None:
            records = [r for r in records if r.action_hit == action_hit]

        # 获取总数（简化实现，直接统计）
        total_records = repo.get_list(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )
        if trend_hit is not None:
            total_records = [r for r in total_records if r.trend_hit == trend_hit]
        if action_hit is not None:
            total_records = [r for r in total_records if r.action_hit == action_hit]
        total = len(total_records)

        # 限制返回数量
        records = records[:limit]

        # 获取股票名称
        db = _get_db()
        stock_names: Dict[str, str] = {}
        for r in records:
            if r.stock_code not in stock_names:
                try:
                    history_records = db.get_analysis_history(
                        code=r.stock_code,
                        limit=1,
                    )
                    if history_records:
                        stock_names[r.stock_code] = history_records[0].name
                except Exception:
                    pass

        # 转换为响应模型
        items = [
            VerificationListItem(
                id=r.id,
                analysis_history_id=r.analysis_history_id,
                stock_code=r.stock_code,
                stock_name=stock_names.get(r.stock_code),
                analysis_date=r.analysis_date,
                verification_date=r.verification_date,
                holding_period=r.holding_period,
                trend_predicted=r.trend_predicted,
                trend_actual=r.trend_actual,
                trend_hit=r.trend_hit,
                sniper_hit_rate=r.sniper_hit_rate,
                sniper_hit_count=r.sniper_hit_count,
                sniper_total_count=r.sniper_total_count,
                sentiment_predicted=r.sentiment_predicted,
                sentiment_actual=r.sentiment_actual,
                sentiment_correlation=r.sentiment_correlation,
                action_predicted=r.action_predicted,
                action_return=r.action_return,
                action_hit=r.action_hit,
            )
            for r in records
        ]

        return VerificationListResponse(
            total=total,
            page=page,
            limit=limit,
            items=items,
        )

    except Exception as e:
        logger.error(f"查询校验列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"查询校验列表失败: {str(e)}"
            }
        )


# ============================================================
# GET /{id} - 获取详情
# ============================================================

@router.get(
    "/{id}",
    response_model=VerificationDetailResponse,
    responses={
        200: {"description": "校验详情", "model": VerificationDetailResponse},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "查询失败", "model": ErrorResponse},
    },
    summary="获取预测校验详情",
    description="根据校验记录 ID 获取详情，包含预测内容与实际走势对比。"
)
def get_verification_detail(
    verification_id: int = Path(..., description="校验记录 ID"),
    repo: VerificationRepository = Depends(_get_verification_repo),
) -> VerificationDetailResponse:
    """
    获取预测校验详情

    流程：
    1. 根据 ID 查询校验记录
    2. 查询关联的分析历史记录
    3. 解析狙击点位 JSON
    4. 构建详情响应

    Args:
        verification_id: 校验记录 ID
        repo: VerificationRepository 实例

    Returns:
        VerificationDetailResponse: 校验详情

    Raises:
        HTTPException: 404 - 记录不存在
        HTTPException: 500 - 查询失败
    """
    try:
        # 查询校验记录
        record = repo.get_by_id(verification_id)

        if not record:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"校验记录 {verification_id} 不存在"
                }
            )

        # 查询关联的分析历史记录
        db = _get_db()
        history_records = db.get_analysis_history(
            id=record.analysis_history_id,
            limit=1,
        )

        stock_name = None
        original_sentiment_score = None
        original_operation_advice = None
        original_analysis_summary = None

        if history_records:
            history = history_records[0]
            stock_name = history.name
            original_sentiment_score = history.sentiment_score
            original_operation_advice = history.operation_advice
            original_analysis_summary = history.analysis_summary

        # 解析狙击点位 JSON
        sniper_points = []
        if record.sniper_points_json:
            try:
                points_data = json.loads(record.sniper_points_json)
                if isinstance(points_data, list):
                    for p in points_data:
                        sniper_points.append(SniperPointDetail(
                            type=p.get("type", "unknown"),
                            price=p.get("price", 0.0),
                            label=p.get("label"),
                            hit=p.get("hit"),
                            hit_price=p.get("hit_price"),
                            hit_date=p.get("hit_date"),
                        ))
            except json.JSONDecodeError:
                logger.warning(f"狙击点位 JSON 解析失败: {record.sniper_points_json}")

        # 计算涨跌幅（简化，从 action_return 推算）
        trend_change_pct = None
        if record.action_return is not None and record.action_predicted:
            if record.action_predicted == "买入":
                trend_change_pct = record.action_return
            elif record.action_predicted == "卖出":
                trend_change_pct = -record.action_return

        # 模拟入场价/出场价（简化，从 sniper_points 推算）
        action_entry_price = None
        action_exit_price = None
        if sniper_points:
            buy_point = next((p for p in sniper_points if p.type == "buy"), None)
            sell_point = next((p for p in sniper_points if p.type == "sell"), None)
            if buy_point:
                action_entry_price = buy_point.price
            if sell_point and record.action_predicted == "卖出":
                action_exit_price = sell_point.price

        return VerificationDetailResponse(
            id=record.id,
            analysis_history_id=record.analysis_history_id,
            stock_code=record.stock_code,
            stock_name=stock_name,
            analysis_date=record.analysis_date,
            verification_date=record.verification_date,
            holding_period=record.holding_period,
            trend_predicted=record.trend_predicted,
            trend_actual=record.trend_actual,
            trend_hit=record.trend_hit,
            trend_change_pct=trend_change_pct,
            sniper_points=sniper_points,
            sniper_hit_count=record.sniper_hit_count,
            sniper_total_count=record.sniper_total_count,
            sniper_hit_rate=record.sniper_hit_rate,
            sentiment_predicted=record.sentiment_predicted,
            sentiment_actual=record.sentiment_actual,
            sentiment_correlation=record.sentiment_correlation,
            action_predicted=record.action_predicted,
            action_return=record.action_return,
            action_hit=record.action_hit,
            action_entry_price=action_entry_price,
            action_exit_price=action_exit_price,
            original_sentiment_score=original_sentiment_score,
            original_operation_advice=original_operation_advice,
            original_analysis_summary=original_analysis_summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询校验详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"查询校验详情失败: {str(e)}"
            }
        )


# ============================================================
# POST /run - 批量触发校验
# ============================================================

@router.post(
    "/run",
    response_model=VerificationRunResponse,
    responses={
        200: {"description": "校验完成", "model": VerificationRunResponse},
        202: {"description": "校验任务已接受", "model": VerificationRunResponse},
        500: {"description": "触发失败", "model": ErrorResponse},
    },
    summary="批量触发预测校验",
    description="触发批量校验任务，校验已到期的分析记录。"
)
def trigger_verification_run(
    request: VerificationRunRequest = Body(default=VerificationRunRequest()),
    repo: VerificationRepository = Depends(_get_verification_repo),
) -> VerificationRunResponse:
    """
    批量触发预测校验

    流程：
    1. 查询待校验的分析记录
    2. 对每条记录调用 verification_service.verify_analysis()
    3. 统计校验结果

    Args:
        request: 校验请求参数
        repo: VerificationRepository 实例

    Returns:
        VerificationRunResponse: 校验结果

    Raises:
        HTTPException: 500 - 触发失败

    Note:
        当前为简化实现，直接调用 Service 层。
        未来可改为异步任务队列模式。
    """
    try:
        from src.services.verification_service import VerificationService

        service = VerificationService()

        # 获取待校验记录
        pending = repo.get_pending_verifications(
            days_back=request.days_back,
            limit=100,
        )

        # 按股票/日期筛选
        if request.stock_code:
            pending = [p for p in pending if p.get("stock_code") == request.stock_code]

        if request.analysis_date:
            pending = [
                p for p in pending
                if p.get("analysis_date") == request.analysis_date.isoformat()
            ]

        if not pending:
            return VerificationRunResponse(
                status="completed",
                message="未找到待校验的分析记录",
                verified_count=0,
                verification_ids=[],
            )

        # 执行校验
        verification_ids = []
        for p in pending:
            try:
                verification = service.verify_analysis(p.get("analysis_id"))
                if verification:
                    verification_ids.append(verification.id)
            except Exception as e:
                logger.warning(f"校验分析记录 {p.get('analysis_id')} 失败: {e}")

        return VerificationRunResponse(
            status="completed",
            message=f"校验完成，共校验 {len(verification_ids)} 条记录",
            verified_count=len(verification_ids),
            verification_ids=verification_ids,
        )

    except ImportError:
        logger.warning("VerificationService 尚未实现，返回模拟响应")
        return VerificationRunResponse(
            status="accepted",
            message="校验任务已接受（Service 层未实现）",
            verified_count=0,
            verification_ids=[],
        )
    except Exception as e:
        logger.error(f"触发校验失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"触发校验失败: {str(e)}"
            }
        )


# ============================================================
# POST /run/{analysis_id} - 校验指定记录
# ============================================================

@router.post(
    "/run/{analysis_id}",
    response_model=VerificationSingleRunResponse,
    responses={
        200: {"description": "校验完成", "model": VerificationSingleRunResponse},
        202: {"description": "校验任务已接受", "model": VerificationSingleRunResponse},
        404: {"description": "分析记录不存在", "model": ErrorResponse},
        500: {"description": "校验失败", "model": ErrorResponse},
    },
    summary="校验指定分析记录",
    description="对指定的分析记录执行校验，生成校验结果。"
)
def trigger_single_verification(
    analysis_id: int = Path(..., description="分析历史记录 ID"),
    repo: VerificationRepository = Depends(_get_verification_repo),
) -> VerificationSingleRunResponse:
    """
    校验指定分析记录

    流程：
    1. 检查分析记录是否存在
    2. 检查是否已有校验结果
    3. 调用 verification_service.verify_analysis()
    4. 返回校验结果

    Args:
        analysis_id: 分析历史记录 ID
        repo: VerificationRepository 实例

    Returns:
        VerificationSingleRunResponse: 校验结果

    Raises:
        HTTPException: 404 - 分析记录不存在
        HTTPException: 500 - 校验失败
    """
    try:
        # 检查是否已有校验结果
        existing = repo.get_by_analysis_id(analysis_id)
        if existing:
            return VerificationSingleRunResponse(
                status="completed",
                message="该分析记录已校验",
                verification_id=existing.id,
                analysis_history_id=analysis_id,
            )

        # 检查分析记录是否存在
        db = _get_db()
        history_records = db.get_analysis_history(id=analysis_id, limit=1)

        if not history_records:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"分析记录 {analysis_id} 不存在"
                }
            )

        from src.services.verification_service import VerificationService

        service = VerificationService()

        # 执行校验
        verification = service.verify_analysis(analysis_id)

        if verification:
            return VerificationSingleRunResponse(
                status="completed",
                message="校验完成",
                verification_id=verification.id,
                analysis_history_id=analysis_id,
            )
        else:
            return VerificationSingleRunResponse(
                status="completed",
                message="校验完成（无校验结果，可能缺少行情数据）",
                verification_id=None,
                analysis_history_id=analysis_id,
            )

    except ImportError:
        logger.warning("VerificationService 尚未实现，返回模拟响应")
        return VerificationSingleRunResponse(
            status="accepted",
            message="校验任务已接受（Service 层未实现）",
            verification_id=None,
            analysis_history_id=analysis_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"校验分析记录失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"校验分析记录失败: {str(e)}"
            }
        )