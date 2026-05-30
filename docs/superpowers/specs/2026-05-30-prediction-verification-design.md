# 分析准确率跟踪功能设计

## 概述

为股票分析系统新增预测准确率跟踪功能，包括：
- 存储历史分析的校验结果到数据库
- Web 端展示准确率统计仪表板
- 历史列表显示校验状态标签
- 详情页展示预测与实际走势对比

## 需求范围

### 新增数据类型
- 分析准确率跟踪（趋势预测、狙击点位、情绪评分、操作建议）

### 校验方式
- 按分析周期动态校验（根据每条分析的建议持有周期确定校验窗口）

### Web 展示
- 统计仪表板：整体准确率统计、按时间/股票筛选
- 历史列表：显示校验状态标签（✅命中、❌未命中、⏳待校验）
- 详情页：预测内容 vs 实际走势对比、点位图表、收益模拟

## 数据模型

新增 `PredictionVerification` 表：

```python
class PredictionVerification(Base):
    __tablename__ = "prediction_verifications"

    id: int                    # 主键
    analysis_history_id: int   # 关联 AnalysisHistory

    # 趋势预测校验
    trend_predicted: str       # 预测趋势：上涨/下跌/震荡
    trend_actual: str          # 实际趋势：上涨/下跌/震荡
    trend_hit: bool            # 是否命中

    # 狙击点位校验
    sniper_points_json: str    # 预测点位详情（JSON）
    sniper_hit_count: int      # 命中点位数
    sniper_total_count: int    # 总点位数
    sniper_hit_rate: float     # 命中率

    # 情绪评分校验
    sentiment_predicted: int    # 预测情绪评分 0-100
    sentiment_actual: int       # 实际情绪（根据涨跌幅映射）
    sentiment_correlation: float # 与实际涨跌的相关性

    # 操作建议校验
    action_predicted: str      # 预测建议：买入/卖出/观望
    action_return: float       # 模拟收益率 %
    action_hit: bool           # 是否盈利

    # 元数据
    verification_date: datetime # 校验日期
    holding_period: int        # 实际持有天数
    stock_code: str            # 股票代码
    analysis_date: datetime    # 原分析日期
```

索引：
- `analysis_history_id`（外键）
- `stock_code, analysis_date`（按股票+日期查询）
- `verification_date`（按校验日期查询）

## 后端架构

### 目录结构

```
src/
├── models/
│   └── prediction_verification.py    # 数据模型（新增）
├── repositories/
│   └── verification_repo.py          # 数据访问层（新增）
├── services/
│   ├── verification_service.py       # 校验服务（新增）
│   └── calculation_service.py        # 指标计算（新增）
├── schemas/
│   └── verification.py               # Pydantic Schema（新增）

api/v1/
├── endpoints/
│   └── verification.py               # API 端点（新增）
├── schemas/
│   └── verification.py               # API Schema（新增）
```

### 模块职责

| 模块 | 职责 |
|------|------|
| `verification_repo.py` | CRUD：查询校验结果、保存校验记录、按股票/日期筛选 |
| `verification_service.py` | 核心校验逻辑：获取历史分析、计算实际走势、对比预测、生成校验结果 |
| `calculation_service.py` | 指标计算工具：趋势判断、点位命中率、情绪映射、收益模拟 |
| `api/v1/endpoints/verification.py` | REST API：触发校验、查询统计、获取详情 |

### 数据流

```
AnalysisHistory ──▶ VerificationService ──▶ PredictionVerification
    (历史预测)         (对比计算)              (校验结果)
                          │
                          ▼
                   StockDaily 数据
                    (实际走势)
```

## API 设计

### 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/verification/stats` | GET | 获取准确率统计（支持筛选） |
| `/api/v1/verification/list` | GET | 获取校验结果列表（分页） |
| `/api/v1/verification/{id}` | GET | 获取单条校验详情 |
| `/api/v1/verification/run` | POST | 手动触发校验任务 |
| `/api/v1/verification/run/{analysis_id}` | POST | 校验指定分析记录 |

### Schema

**统计请求**
```python
class VerificationStatsRequest:
    stock_code: str | None
    start_date: date | None
    end_date: date | None
    dimension: str | None  # trend/sniper/sentiment/action
```

**统计响应**
```python
class VerificationStatsResponse:
    total_count: int
    trend_hit_rate: float
    sniper_avg_hit_rate: float
    sentiment_avg_correlation: float
    action_profit_rate: float
    action_avg_return: float
    by_stock: list
    by_period: list
```

**列表项**
```python
class VerificationListItem:
    id: int
    stock_code: str
    stock_name: str
    analysis_date: date
    verification_date: date
    trend_hit: bool
    sniper_hit_rate: float
    action_return: float
```

**触发请求**
```python
class VerificationRunRequest:
    stock_code: str | None
    analysis_date: date | None
    days_back: int = 5
```

## Web 前端设计

### 页面结构

```
apps/dsa-web/src/
├── pages/
│   └── AccuracyPage.tsx           # 统计仪表板（新增）
├── components/
│   ├── accuracy/
│   │   ├── StatsCard.tsx          # 统计卡片
│   │   ├── TrendChart.tsx         # 趋势准确率图表
│   │   ├── SniperChart.tsx        # 狙击点位图表
│   │   ├── ReturnChart.tsx        # 收益分布图表
│   │   ├── StockFilter.tsx        # 股票筛选器
│   │   └── PeriodFilter.tsx       # 时间筛选器
│   └── history/
│       └── VerificationBadge.tsx  # 校验状态标签（新增）
├── hooks/
│   └── useVerification.ts         # 校验数据查询 Hook（新增）
├── api/
│   └── verification.ts            # API 调用封装（新增）
```

### 统计仪表板布局

- 顶部筛选栏：股票筛选、时间范围、校验按钮
- 统计卡片行：趋势准确率、狙击命中率、情绪相关性、盈利比例
- 图表区域：趋势准确率趋势图（按周）、各股票准确率对比柱状图
- 校验结果列表：股票、分析日期、校验日期、趋势状态、狙击命中率、收益率

### 历史列表改造

每条记录后添加校验状态标签：
- `[趋势: ✅命中]` / `[趋势: ❌未命中]` / `[趋势: ⏳待校验]`
- `[狙击: 60%命中率]`

### 详情页改造

报告详情抽屉底部添加校验对比区域：
- 趋势预测 vs 实际趋势
- 狙击点位逐一对比（支撑位/压力位是否触及）
- 模拟收益率

## 校验逻辑

### 持有周期确定

| 来源字段 | 周期推断逻辑 |
|---------|-------------|
| `action_advice` 含"短线" | 1-3 天 |
| `action_advice` 含"中线" | 5-10 天 |
| `action_advice` 含"长线" | 20-30 天 |
| `sniper_points.stop_loss` 距现价比例 < 3% | 短线（3 天） |
| 无明确标记 | 默认 5 天 |

### 趋势预测校验

```python
def verify_trend(predicted: str, actual_prices: list) -> tuple[str, bool]:
    change_pct = (actual_prices[-1] - actual_prices[0]) / actual_prices[0] * 100

    if change_pct > 2:   actual = "上涨"
    elif change_pct < -2: actual = "下跌"
    else: actual = "震荡"

    hit = (predicted == actual)
    return actual, hit
```

### 狙击点位校验

```python
def verify_sniper(points: list, actual_prices: list) -> dict:
    hit_count = 0
    for point in points:
        point_type = point["type"]
        price = point["price"]

        if point_type in ["support", "buy"]:
            if min(actual_prices) <= price * 1.01:
                hit_count += 1
        else:
            if max(actual_prices) >= price * 0.99:
                hit_count += 1

    return {
        "hit_count": hit_count,
        "total_count": len(points),
        "hit_rate": hit_count / len(points) if points else 0
    }
```

### 情绪评分校验

```python
def verify_sentiment(predicted_score: int, actual_change: float) -> float:
    expected_change = (predicted_score - 50) / 10
    correlation = 1 - abs(expected_change - actual_change) / max(abs(expected_change), abs(actual_change), 1)
    return correlation
```

### 操作建议收益模拟

```python
def verify_action(advice: str, prices: list, sniper_points: list) -> tuple[float, bool]:
    if advice == "观望":
        return 0.0, True

    entry_price = prices[0]
    exit_price = prices[-1]

    if sniper_points:
        buy_point = next((p["price"] for p in sniper_points if p["type"] == "buy"), entry_price)
        sell_point = next((p["price"] for p in sniper_points if p["type"] == "sell"), exit_price)
        entry_price = buy_point
        exit_price = sell_point if advice == "卖出" else prices[-1]

    if advice == "买入":
        return_pct = (exit_price - entry_price) / entry_price * 100
    else:
        return_pct = (entry_price - exit_price) / entry_price * 100

    hit = return_pct > 0
    return return_pct, hit
```

## 定时任务集成

在现有 `main.py --schedule` 流程中新增校验步骤：

```python
def run_daily_schedule():
    run_market_review()
    run_stock_analysis()
    send_notifications()
    verify_expired_predictions()  # 新增
```

校验到期预测：
- 查询所有 `holding_period` 已到期的分析记录
- 对每条到期记录调用 `verification_service.verify()`

## 配置项

新增 `.env` 配置：

```
VERIFICATION_THRESHOLD_TREND=2      # 趋势判断涨跌阈值 %
VERIFICATION_SNIPER_TOLERANCE=1     # 狙击点位容差 %
VERIFICATION_DEFAULT_HOLDING=5      # 默认持有天数
VERIFICATION_AUTO_ENABLED=true      # 是否自动校验
```

需同步更新 `.env.example`。

## 文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/models/prediction_verification.py` | 数据模型 |
| `src/repositories/verification_repo.py` | 数据访问层 |
| `src/services/verification_service.py` | 校验服务 |
| `src/services/calculation_service.py` | 指标计算 |
| `src/schemas/verification.py` | Pydantic Schema |
| `api/v1/endpoints/verification.py` | API 端点 |
| `api/v1/schemas/verification.py` | API Schema |
| `apps/dsa-web/src/pages/AccuracyPage.tsx` | 统计仪表板页面 |
| `apps/dsa-web/src/components/accuracy/*.tsx` | 准确率组件 |
| `apps/dsa-web/src/components/history/VerificationBadge.tsx` | 校验状态标签 |
| `apps/dsa-web/src/hooks/useVerification.ts` | 查询 Hook |
| `apps/dsa-web/src/api/verification.ts` | API 调用封装 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/storage.py` | 导入新模型 |
| `src/core/scheduler.py` | 集成校验步骤 |
| `.env.example` | 新增配置项 |
| `apps/dsa-web/src/pages/HomePage.tsx` | 路由注册 AccuracyPage |
| `apps/dsa-web/src/components/history/HistoryList.tsx` | 添加校验标签 |
| `apps/dsa-web/src/components/ReportMarkdownDrawer.tsx` | 添加校验对比区域 |

## 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 持有期内无行情数据 | 标记校验状态为 `data_missing`，不计算准确率 |
| 狙击点位列表为空 | sniper_hit_rate 设为 `null`，其他维度正常计算 |
| 趋势预测字段为空 | trend_hit 设为 `null`，跳过趋势校验 |
| 操作建议为"观望" | action_return 为 0，action_hit 为 `true` |
| AnalysisHistory 被删除 | 关联的 PredictionVerification 保留，但 API 返回时标注"原分析已删除" |

## 验证要点

- 后端：`./scripts/ci_gate.sh` + 手动触发校验 API 测试
- Web：`npm run lint && npm run build` + 手动访问统计页验证展示
- 边界情况：测试无行情数据、空点位、观望建议等场景