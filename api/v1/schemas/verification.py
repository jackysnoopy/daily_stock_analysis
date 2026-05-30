# -*- coding: utf-8 -*-
"""
===================================
预测校验相关模型
===================================

职责：
1. 定义校验统计查询请求和响应模型
2. 定义校验列表查询请求和响应模型
3. 定义校验详情响应模型
4. 定义触发校验请求模型
"""

from datetime import date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 统计相关模型
# ============================================================

class VerificationStatsRequest(BaseModel):
    """校验统计查询请求"""

    stock_code: Optional[str] = Field(
        None,
        description="股票代码筛选",
        json_schema_extra={"example": "600519"},
    )
    start_date: Optional[date] = Field(
        None,
        description="起始日期（分析日期）",
        json_schema_extra={"example": "2024-01-01"},
    )
    end_date: Optional[date] = Field(
        None,
        description="结束日期（分析日期）",
        json_schema_extra={"example": "2024-12-31"},
    )
    dimension: Optional[str] = Field(
        None,
        description="统计维度：trend/sniper/sentiment/action",
        pattern="^(trend|sniper|sentiment|action)$",
        json_schema_extra={"example": "trend"},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "dimension": "trend"
        }
    })


class StockStats(BaseModel):
    """单只股票的校验统计"""

    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    total_count: int = Field(0, description="总校验记录数")
    trend_hit_rate: Optional[float] = Field(None, description="趋势命中率 %")
    sniper_avg_hit_rate: Optional[float] = Field(None, description="狙击点位平均命中率 %")
    sentiment_avg_correlation: Optional[float] = Field(None, description="情绪评分平均相关性")
    action_profit_rate: Optional[float] = Field(None, description="操作建议盈利比例 %")
    action_avg_return: Optional[float] = Field(None, description="操作建议平均收益率 %")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "total_count": 15,
            "trend_hit_rate": 65.5,
            "sniper_avg_hit_rate": 45.2,
            "sentiment_avg_correlation": 0.72,
            "action_profit_rate": 55.0,
            "action_avg_return": 3.2
        }
    })


class PeriodStats(BaseModel):
    """时间段校验统计"""

    period: str = Field(..., description="时间段标识（如 2024-W01）")
    start_date: date = Field(..., description="起始日期")
    end_date: date = Field(..., description="结束日期")
    total_count: int = Field(0, description="总校验记录数")
    trend_hit_rate: Optional[float] = Field(None, description="趋势命中率 %")
    action_avg_return: Optional[float] = Field(None, description="平均收益率 %")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "period": "2024-W01",
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "total_count": 5,
            "trend_hit_rate": 60.0,
            "action_avg_return": 2.5
        }
    })


class VerificationStatsResponse(BaseModel):
    """校验统计响应"""

    total_count: int = Field(0, description="总校验记录数")
    trend_hit_rate: Optional[float] = Field(None, description="整体趋势命中率 %")
    sniper_avg_hit_rate: Optional[float] = Field(None, description="狙击点位平均命中率 %")
    sentiment_avg_correlation: Optional[float] = Field(None, description="情绪评分平均相关性")
    action_profit_rate: Optional[float] = Field(None, description="操作建议盈利比例 %")
    action_avg_return: Optional[float] = Field(None, description="操作建议平均收益率 %")
    by_stock: List[StockStats] = Field(default_factory=list, description="按股票统计")
    by_period: List[PeriodStats] = Field(default_factory=list, description="按时间段统计")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_count": 50,
            "trend_hit_rate": 62.5,
            "sniper_avg_hit_rate": 48.3,
            "sentiment_avg_correlation": 0.68,
            "action_profit_rate": 56.0,
            "action_avg_return": 2.8,
            "by_stock": [],
            "by_period": []
        }
    })


# ============================================================
# 列表相关模型
# ============================================================

class VerificationListRequest(BaseModel):
    """校验列表查询请求"""

    stock_code: Optional[str] = Field(
        None,
        description="股票代码筛选",
        json_schema_extra={"example": "600519"},
    )
    start_date: Optional[date] = Field(
        None,
        description="起始日期（分析日期）",
        json_schema_extra={"example": "2024-01-01"},
    )
    end_date: Optional[date] = Field(
        None,
        description="结束日期（分析日期）",
        json_schema_extra={"example": "2024-12-31"},
    )
    trend_hit: Optional[bool] = Field(
        None,
        description="趋势命中筛选",
        json_schema_extra={"example": True},
    )
    action_hit: Optional[bool] = Field(
        None,
        description="操作建议盈利筛选",
        json_schema_extra={"example": True},
    )
    page: int = Field(
        1,
        description="页码（从 1 开始）",
        ge=1,
        json_schema_extra={"example": 1},
    )
    limit: int = Field(
        20,
        description="每页数量",
        ge=1,
        le=100,
        json_schema_extra={"example": 20},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "trend_hit": True,
            "page": 1,
            "limit": 20
        }
    })


class VerificationListItem(BaseModel):
    """校验列表项"""

    id: int = Field(..., description="校验记录 ID")
    analysis_history_id: int = Field(..., description="关联分析历史记录 ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    analysis_date: date = Field(..., description="分析日期")
    verification_date: date = Field(..., description="校验日期")
    holding_period: int = Field(5, description="持有天数")
    trend_predicted: Optional[str] = Field(None, description="预测趋势")
    trend_actual: Optional[str] = Field(None, description="实际趋势")
    trend_hit: Optional[bool] = Field(None, description="趋势是否命中")
    sniper_hit_rate: Optional[float] = Field(None, description="狙击点位命中率 %")
    sniper_hit_count: Optional[int] = Field(None, description="狙击点位命中数")
    sniper_total_count: Optional[int] = Field(None, description="狙击点位总数")
    sentiment_predicted: Optional[int] = Field(None, description="预测情绪评分")
    sentiment_actual: Optional[int] = Field(None, description="实际情绪评分")
    sentiment_correlation: Optional[float] = Field(None, description="情绪相关性")
    action_predicted: Optional[str] = Field(None, description="预测操作建议")
    action_return: Optional[float] = Field(None, description="模拟收益率 %")
    action_hit: Optional[bool] = Field(None, description="操作建议是否盈利")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 123,
            "analysis_history_id": 456,
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "analysis_date": "2024-01-15",
            "verification_date": "2024-01-20",
            "holding_period": 5,
            "trend_predicted": "上涨",
            "trend_actual": "上涨",
            "trend_hit": True,
            "sniper_hit_rate": 60.0,
            "sniper_hit_count": 3,
            "sniper_total_count": 5,
            "sentiment_predicted": 80,
            "sentiment_actual": 75,
            "sentiment_correlation": 0.85,
            "action_predicted": "买入",
            "action_return": 5.2,
            "action_hit": True
        }
    })


class VerificationListResponse(BaseModel):
    """校验列表响应"""

    total: int = Field(0, description="总记录数")
    page: int = Field(1, description="当前页码")
    limit: int = Field(20, description="每页数量")
    items: List[VerificationListItem] = Field(default_factory=list, description="校验记录列表")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 100,
            "page": 1,
            "limit": 20,
            "items": []
        }
    })


# ============================================================
# 详情相关模型
# ============================================================

class SniperPointDetail(BaseModel):
    """狙击点位详情"""

    type: str = Field(..., description="点位类型：support/resistance/buy/sell")
    price: float = Field(..., description="预测价位")
    label: Optional[str] = Field(None, description="点位标签")
    hit: Optional[bool] = Field(None, description="是否命中")
    hit_price: Optional[float] = Field(None, description="实际触及价位")
    hit_date: Optional[date] = Field(None, description="触及日期")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "support",
            "price": 1800.0,
            "label": "支撑位1",
            "hit": True,
            "hit_price": 1798.5,
            "hit_date": "2024-01-18"
        }
    })


class VerificationDetailResponse(BaseModel):
    """校验详情响应"""

    id: int = Field(..., description="校验记录 ID")
    analysis_history_id: int = Field(..., description="关联分析历史记录 ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    analysis_date: date = Field(..., description="分析日期")
    verification_date: date = Field(..., description="校验日期")
    holding_period: int = Field(5, description="持有天数")

    # 趋势校验详情
    trend_predicted: Optional[str] = Field(None, description="预测趋势")
    trend_actual: Optional[str] = Field(None, description="实际趋势")
    trend_hit: Optional[bool] = Field(None, description="趋势是否命中")
    trend_change_pct: Optional[float] = Field(None, description="实际涨跌幅 %")

    # 狙击点位校验详情
    sniper_points: List[SniperPointDetail] = Field(
        default_factory=list,
        description="狙击点位详情列表"
    )
    sniper_hit_count: int = Field(0, description="狙击点位命中数")
    sniper_total_count: int = Field(0, description="狙击点位总数")
    sniper_hit_rate: Optional[float] = Field(None, description="狙击点位命中率 %")

    # 情绪校验详情
    sentiment_predicted: Optional[int] = Field(None, description="预测情绪评分")
    sentiment_actual: Optional[int] = Field(None, description="实际情绪评分")
    sentiment_correlation: Optional[float] = Field(None, description="情绪相关性")

    # 操作建议校验详情
    action_predicted: Optional[str] = Field(None, description="预测操作建议")
    action_return: Optional[float] = Field(None, description="模拟收益率 %")
    action_hit: Optional[bool] = Field(None, description="操作建议是否盈利")
    action_entry_price: Optional[float] = Field(None, description="模拟入场价")
    action_exit_price: Optional[float] = Field(None, description="模拟出场价")

    # 原分析报告摘要
    original_sentiment_score: Optional[int] = Field(None, description="原分析情绪评分")
    original_operation_advice: Optional[str] = Field(None, description="原分析操作建议")
    original_analysis_summary: Optional[str] = Field(None, description="原分析摘要")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 123,
            "analysis_history_id": 456,
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "analysis_date": "2024-01-15",
            "verification_date": "2024-01-20",
            "holding_period": 5,
            "trend_predicted": "上涨",
            "trend_actual": "上涨",
            "trend_hit": True,
            "trend_change_pct": 5.2,
            "sniper_points": [],
            "sniper_hit_count": 3,
            "sniper_total_count": 5,
            "sniper_hit_rate": 60.0,
            "sentiment_predicted": 80,
            "sentiment_actual": 75,
            "sentiment_correlation": 0.85,
            "action_predicted": "买入",
            "action_return": 5.2,
            "action_hit": True,
            "action_entry_price": 1800.0,
            "action_exit_price": 1893.6,
            "original_sentiment_score": 80,
            "original_operation_advice": "买入",
            "original_analysis_summary": "看好短期走势"
        }
    })


# ============================================================
# 触发校验相关模型
# ============================================================

class VerificationRunRequest(BaseModel):
    """批量触发校验请求"""

    stock_code: Optional[str] = Field(
        None,
        description="股票代码筛选",
        json_schema_extra={"example": "600519"},
    )
    analysis_date: Optional[date] = Field(
        None,
        description="指定分析日期",
        json_schema_extra={"example": "2024-01-15"},
    )
    days_back: int = Field(
        5,
        description="回溯天数（用于查找待校验的分析记录）",
        ge=1,
        le=90,
        json_schema_extra={"example": 5},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "analysis_date": None,
            "days_back": 5
        }
    })


class VerificationRunResponse(BaseModel):
    """触发校验响应"""

    status: str = Field(..., description="任务状态：accepted/completed")
    message: str = Field(..., description="状态说明")
    verified_count: int = Field(0, description="已校验记录数")
    verification_ids: List[int] = Field(default_factory=list, description="校验记录 ID 列表")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "accepted",
            "message": "已触发校验任务，校验 3 条过期分析记录",
            "verified_count": 3,
            "verification_ids": [101, 102, 103]
        }
    })


class VerificationSingleRunResponse(BaseModel):
    """单条校验响应"""

    status: str = Field(..., description="任务状态：accepted/completed")
    message: str = Field(..., description="状态说明")
    verification_id: Optional[int] = Field(None, description="校验记录 ID")
    analysis_history_id: int = Field(..., description="分析历史记录 ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "completed",
            "message": "校验完成",
            "verification_id": 123,
            "analysis_history_id": 456
        }
    })