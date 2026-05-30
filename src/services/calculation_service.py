# -*- coding: utf-8 -*-
"""
===================================
预测校验计算服务
===================================

职责：
1. 纯逻辑计算模块（无数据库操作）
2. 持有周期推断
3. 趋势预测校验
4. 狙击点位命中率计算
5. 情绪评分相关性计算
6. 操作建议收益模拟
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CalculationService:
    """
    预测校验计算服务

    纯逻辑模块，不依赖数据库
    """

    # Holding period keywords
    SHORT_TERM_KEYWORDS = ("短线", "短期", "快进快出", "short", "short-term")
    MEDIUM_TERM_KEYWORDS = ("中线", "中期", "medium", "medium-term")
    LONG_TERM_KEYWORDS = ("长线", "长期", "long", "long-term")

    # Trend thresholds (percentage)
    TREND_UP_THRESHOLD = 2.0
    TREND_DOWN_THRESHOLD = -2.0

    # Sniper point tolerance (percentage)
    SNIPER_TOLERANCE = 1.0

    # Default holding period
    DEFAULT_HOLDING_PERIOD = 5

    def determine_holding_period(
        self,
        operation_advice: Optional[str],
        stop_loss: Optional[float] = None,
        current_price: Optional[float] = None,
    ) -> int:
        """
        根据操作建议推断持有周期

        Args:
            operation_advice: 操作建议文本
            stop_loss: 止损价位（可选）
            current_price: 当前价位（可选）

        Returns:
            持有天数
        """
        text = str(operation_advice or "").lower()

        # Check explicit term keywords
        if self._contains_any_keyword(text, self.SHORT_TERM_KEYWORDS):
            return 3
        if self._contains_any_keyword(text, self.MEDIUM_TERM_KEYWORDS):
            return 7
        if self._contains_any_keyword(text, self.LONG_TERM_KEYWORDS):
            return 25

        # Check stop loss proximity (tight stop -> short-term)
        if stop_loss is not None and current_price is not None and current_price > 0:
            stop_loss_pct = (current_price - stop_loss) / current_price * 100
            if stop_loss_pct < 3.0:
                return 3

        return self.DEFAULT_HOLDING_PERIOD

    def _contains_any_keyword(self, text: str, keywords: Tuple[str, ...]) -> bool:
        """Check if text contains any of the keywords."""
        for kw in keywords:
            if kw.lower() in text:
                return True
        return False

    def verify_trend(
        self,
        predicted: Optional[str],
        actual_prices: List[float],
    ) -> Tuple[Optional[str], Optional[bool]]:
        """
        校验趋势预测

        Args:
            predicted: 预测趋势（上涨/下跌/震荡）
            actual_prices: 实际价格序列（持有期内）

        Returns:
            (实际趋势, 是否命中)
        """
        if not actual_prices or len(actual_prices) < 2:
            logger.warning("趋势校验数据不足")
            return None, None

        if not predicted:
            return None, None

        # Calculate change percentage
        start_price = actual_prices[0]
        end_price = actual_prices[-1]

        if start_price <= 0:
            return None, None

        change_pct = (end_price - start_price) / start_price * 100

        # Determine actual trend
        if change_pct > self.TREND_UP_THRESHOLD:
            actual = "上涨"
        elif change_pct < self.TREND_DOWN_THRESHOLD:
            actual = "下跌"
        else:
            actual = "震荡"

        # Normalize predicted trend
        predicted_normalized = self._normalize_trend(predicted)

        hit = (predicted_normalized == actual)
        return actual, hit

    def _normalize_trend(self, trend: Optional[str]) -> Optional[str]:
        """Normalize trend prediction text."""
        if not trend:
            return None
        text = str(trend).lower().strip()

        if text in ("上涨", "up", "bullish", "看涨", "涨"):
            return "上涨"
        if text in ("下跌", "down", "bearish", "看跌", "跌"):
            return "下跌"
        if text in ("震荡", "flat", "range-bound", "横盘", "中性"):
            return "震荡"

        return None

    def verify_sniper(
        self,
        points: List[Dict[str, Any]],
        actual_prices: List[float],
    ) -> Dict[str, Any]:
        """
        校验狙击点位

        Args:
            points: 狙击点位列表，每项包含 type 和 price
            actual_prices: 实际价格序列

        Returns:
            {
                "hit_count": 命中点位数,
                "total_count": 总点位数,
                "hit_rate": 命中率（百分比）
            }
        """
        if not points:
            return {
                "hit_count": 0,
                "total_count": 0,
                "hit_rate": None,
            }

        total_count = len(points)
        hit_count = 0

        if not actual_prices:
            return {
                "hit_count": 0,
                "total_count": total_count,
                "hit_rate": 0.0,
            }

        min_price = min(actual_prices)
        max_price = max(actual_prices)

        for point in points:
            point_type = point.get("type", "")
            price = point.get("price")

            if price is None or price <= 0:
                continue

            # Support/buy points: check if low touched
            if point_type in ("support", "buy", "ideal_buy", "secondary_buy"):
                tolerance_factor = 1 + self.SNIPER_TOLERANCE / 100
                if min_price <= price * tolerance_factor:
                    hit_count += 1

            # Resistance/sell/stop_loss/take_profit: check if high touched
            elif point_type in ("resistance", "sell", "stop_loss", "take_profit"):
                tolerance_factor = 1 - self.SNIPER_TOLERANCE / 100
                if max_price >= price * tolerance_factor:
                    hit_count += 1

        hit_rate = hit_count / total_count * 100 if total_count > 0 else None

        return {
            "hit_count": hit_count,
            "total_count": total_count,
            "hit_rate": hit_rate,
        }

    def verify_sentiment(
        self,
        predicted_score: Optional[int],
        actual_change: Optional[float],
    ) -> Optional[float]:
        """
        校验情绪评分

        将预测情绪评分映射为预期涨跌幅，计算与实际涨跌的相关性

        Args:
            predicted_score: 预测情绪评分 (0-100)
            actual_change: 实际涨跌幅（百分比）

        Returns:
            相关性分数 (0-1)，None 表示无法计算
        """
        if predicted_score is None or actual_change is None:
            return None

        # Normalize score to range
        score = max(0, min(100, int(predicted_score)))

        # Map score to expected change
        # Score 50 = neutral (0% expected)
        # Score 80 = bullish (+3% expected)
        # Score 20 = bearish (-3% expected)
        expected_change = (score - 50) / 10

        # Calculate correlation using absolute deviation
        # Formula: 1 - |expected - actual| / max(|expected|, |actual|, 1)
        deviation = abs(expected_change - actual_change)
        denominator = max(abs(expected_change), abs(actual_change), 1.0)

        correlation = 1 - deviation / denominator

        # Clamp to valid range
        return max(0.0, min(1.0, correlation))

    def verify_action(
        self,
        advice: Optional[str],
        prices: List[float],
        sniper_points: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[float, bool]:
        """
        模拟操作建议收益

        Args:
            advice: 操作建议（买入/卖出/观望）
            prices: 价格序列
            sniper_points: 狙击点位（可选）

        Returns:
            (收益率百分比, 是否盈利)
        """
        # Default for hold/watch
        advice_normalized = self._normalize_action(advice)
        if advice_normalized in ("hold", "watch", None):
            return 0.0, True

        if not prices or len(prices) < 2:
            return 0.0, False

        entry_price = prices[0]
        exit_price = prices[-1]

        # Use sniper points if available
        if sniper_points:
            buy_point = self._find_point_price(sniper_points, ("buy", "ideal_buy", "secondary_buy"))
            sell_point = self._find_point_price(sniper_points, ("sell", "take_profit"))

            if buy_point:
                entry_price = buy_point
            if sell_point and advice_normalized == "sell":
                exit_price = sell_point

        # Calculate return
        if advice_normalized == "buy":
            if entry_price <= 0:
                return 0.0, False
            return_pct = (exit_price - entry_price) / entry_price * 100
        elif advice_normalized == "sell":
            if entry_price <= 0:
                return 0.0, False
            # Short position: profit when price drops
            return_pct = (entry_price - exit_price) / entry_price * 100
        else:
            return 0.0, True

        hit = return_pct > 0
        return round(return_pct, 2), hit

    def _normalize_action(self, advice: Optional[str]) -> Optional[str]:
        """Normalize action advice text."""
        if not advice:
            return None
        text = str(advice).lower().strip()

        if text in ("买入", "buy", "建仓", "加仓", "strong buy"):
            return "buy"
        if text in ("卖出", "sell", "减仓", "清仓", "strong sell"):
            return "sell"
        if text in ("观望", "hold", "watch", "等待", "持有", "中性"):
            return "hold"

        return None

    def _find_point_price(
        self,
        points: List[Dict[str, Any]],
        types: Tuple[str, ...],
    ) -> Optional[float]:
        """Find price for a given point type."""
        for point in points:
            point_type = point.get("type", "")
            if point_type in types:
                return point.get("price")
        return None