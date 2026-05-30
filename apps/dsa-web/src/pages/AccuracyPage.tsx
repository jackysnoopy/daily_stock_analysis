import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { TrendingUp, Target, Brain, DollarSign, Play } from 'lucide-react';
import { verificationApi } from '../api/verification';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, EmptyState, Pagination } from '../components/common';
import { StatsCard } from '../components/accuracy/StatsCard';
import { TrendChart } from '../components/accuracy/TrendChart';
import { VerificationBadge } from '../components/accuracy/VerificationBadge';
import type {
  VerificationStatsResponse,
  VerificationListItem,
  VerificationRunResponse,
} from '../types/verification';

const ACCURACY_INPUT_CLASS =
  'input-surface input-focus-glow h-10 rounded-xl border bg-transparent px-3 py-2 text-xs transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

// ============ Helpers ============

function formatRate(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

function formatReturn(value?: number | null): string {
  if (value == null) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function trendIcon(hit?: boolean | null) {
  if (hit === true) return <span className="text-success">✓</span>;
  if (hit === false) return <span className="text-danger">✗</span>;
  return <span className="text-muted-text">--</span>;
}

// ============ Main Page ============

const AccuracyPage: React.FC = () => {
  // Set page title
  useEffect(() => {
    document.title = '准确率统计 - DSA';
  }, []);

  // Filter state
  const [stockCode, setStockCode] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<VerificationRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // Stats state
  const [stats, setStats] = useState<VerificationStatsResponse | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // List state
  const [items, setItems] = useState<VerificationListItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const pageSize = 20;

  // Fetch stats
  const fetchStats = useCallback(async (code?: string, from?: string, to?: string) => {
    setIsLoadingStats(true);
    try {
      const response = await verificationApi.getStats({
        stockCode: code,
        startDate: from,
        endDate: to,
      });
      setStats(response);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch verification stats:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingStats(false);
    }
  }, []);

  // Fetch list
  const fetchList = useCallback(async (
    page = 1,
    code?: string,
    from?: string,
    to?: string,
  ) => {
    setIsLoadingList(true);
    try {
      const response = await verificationApi.getList({
        stockCode: code,
        startDate: from,
        endDate: to,
        page,
        limit: pageSize,
      });
      setItems(response.items);
      setTotalItems(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch verification list:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchStats();
    fetchList(1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run verification
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const response = await verificationApi.runVerification({
        stockCode: stockCode.trim() || undefined,
        daysBack: 5,
      });
      setRunResult(response);
      // Refresh data
      fetchStats(stockCode.trim() || undefined, startDate, endDate);
      fetchList(1, stockCode.trim() || undefined, startDate, endDate);
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Filter
  const handleFilter = () => {
    const code = stockCode.trim() || undefined;
    setCurrentPage(1);
    fetchStats(code, startDate, endDate);
    fetchList(1, code, startDate, endDate);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFilter();
    }
  };

  // Pagination
  const totalPages = Math.ceil(totalItems / pageSize);
  const handlePageChange = (page: number) => {
    const code = stockCode.trim() || undefined;
    fetchList(page, code, startDate, endDate);
  };

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-white/5 px-3 py-3 sm:px-4">
        <div className="flex max-w-5xl flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-[1_1_220px]">
            <input
              type="text"
              value={stockCode}
              onChange={(e) => setStockCode(e.target.value.toUpperCase())}
              onKeyDown={handleKeyDown}
              placeholder="Filter by stock code (leave empty for all)"
              disabled={isRunning}
              className={ACCURACY_INPUT_CLASS}
            />
          </div>
          <button
            type="button"
            onClick={handleFilter}
            disabled={isLoadingStats || isLoadingList}
            className="btn-secondary flex items-center gap-1.5 whitespace-nowrap"
          >
            Filter
          </button>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">From</span>
            <input
              type="date"
              aria-label="Start date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${ACCURACY_INPUT_CLASS} w-40 text-center tabular-nums`}
            />
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">To</span>
            <input
              type="date"
              aria-label="End date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${ACCURACY_INPUT_CLASS} w-40 text-center tabular-nums`}
            />
          </div>
          <button
            type="button"
            onClick={handleRun}
            disabled={isRunning}
            className="btn-primary flex items-center gap-1.5 whitespace-nowrap"
          >
            {isRunning ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Run Verification
              </>
            )}
          </button>
        </div>
        {runResult && (
          <div className="mt-2 max-w-4xl flex items-center gap-4 text-xs">
            <span className="text-muted-text">Status: <span className="text-secondary-text font-mono">{runResult.status}</span></span>
            <span className="text-muted-text">Verified: <span className="text-success font-mono">{runResult.verifiedCount}</span></span>
          </div>
        )}
        {runError && (
          <ApiErrorAlert error={runError} className="mt-2 max-w-4xl" />
        )}
        <p className="mt-2 text-xs text-muted-text">
          分析准确率统计仪表板 - 校验历史分析的预测准确度
        </p>
      </header>

      {/* Main content */}
      <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-3 lg:flex-row">
        {/* Left sidebar - Stats cards */}
        <div className="flex max-h-[38vh] flex-col gap-3 overflow-y-auto lg:max-h-none lg:w-72 lg:flex-shrink-0">
          {isLoadingStats ? (
            <div className="flex items-center justify-center py-8">
              <div className="backtest-spinner sm" />
            </div>
          ) : stats ? (
            <>
              <StatsCard
                title="趋势准确率"
                value={stats.trendHitRate}
                format="percent"
                subtitle={`共 ${stats.totalCount} 条`}
                accent
                icon={<TrendingUp className="w-5 h-5" />}
              />
              <StatsCard
                title="狙击命中率"
                value={stats.sniperAvgHitRate}
                format="percent"
                subtitle="点位命中统计"
                icon={<Target className="w-5 h-5" />}
              />
              <StatsCard
                title="情绪相关性"
                value={stats.sentimentAvgCorrelation}
                format="number"
                subtitle="预测情绪与实际涨跌相关性"
                icon={<Brain className="w-5 h-5" />}
              />
              <StatsCard
                title="平均收益"
                value={stats.actionAvgReturn}
                format="number"
                subtitle={`盈利比例: ${formatRate(stats.actionProfitRate)}`}
                icon={<DollarSign className="w-5 h-5" />}
              />
              <TrendChart
                data={stats.byPeriod}
                title="趋势准确率趋势"
                className="mt-2"
              />
            </>
          ) : (
            <EmptyState
              title="No Stats Yet"
              description="Run verification to generate accuracy statistics."
              className="h-full min-h-[12rem] border-dashed bg-card/45 shadow-none"
            />
          )}
        </div>

        {/* Right content - Results table */}
        <section className="min-h-0 flex-1 overflow-y-auto">
          {pageError ? (
            <ApiErrorAlert error={pageError} className="mb-3" />
          ) : null}
          {isLoadingList ? (
            <div className="flex flex-col items-center justify-center h-64">
              <div className="backtest-spinner md" />
              <p className="mt-3 text-secondary-text text-sm">Loading results...</p>
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              title="No Verification Results"
              description="Run verification to evaluate historical analysis accuracy"
              className="backtest-empty-state border-dashed"
              icon={(
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              )}
            />
          ) : (
            <div className="animate-fade-in">
              <div className="backtest-table-toolbar">
                <div className="backtest-table-toolbar-meta">
                  <span className="label-uppercase">Verification Results</span>
                  <span className="text-xs text-secondary-text">
                    {stockCode.trim() ? `Filtered by ${stockCode.trim()}` : 'All stocks'}
                    {startDate ? ` · from ${startDate}` : ''}
                    {endDate ? ` · to ${endDate}` : ''}
                  </span>
                </div>
                <span className="backtest-table-scroll-hint">Scroll horizontally on small screens</span>
              </div>
              <div className="backtest-table-wrapper">
                <table className="backtest-table min-w-[960px] w-full text-sm">
                  <thead className="backtest-table-head">
                    <tr className="text-left">
                      <th className="backtest-table-head-cell">Stock</th>
                      <th className="backtest-table-head-cell">Analysis Date</th>
                      <th className="backtest-table-head-cell">Holding Period</th>
                      <th className="backtest-table-head-cell">Trend</th>
                      <th className="backtest-table-head-cell">Sniper Hit</th>
                      <th className="backtest-table-head-cell">Return</th>
                      <th className="backtest-table-head-cell">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr
                        key={row.id}
                        className="backtest-table-row"
                      >
                        <td className="backtest-table-cell backtest-table-code">
                          <div className="flex flex-col">
                            <span>{row.stockCode}</span>
                            <span className="text-xs text-muted-text">{row.stockName || '--'}</span>
                          </div>
                        </td>
                        <td className="backtest-table-cell text-secondary-text">{row.analysisDate || '--'}</td>
                        <td className="backtest-table-cell text-secondary-text">
                          {row.holdingPeriod ? `${row.holdingPeriod}d` : '--'}
                        </td>
                        <td className="backtest-table-cell">
                          <div className="flex items-center gap-2">
                            {trendIcon(row.trendHit)}
                            <span className="text-xs text-muted-text">
                              {row.trendPredicted || '--'} → {row.trendActual || '--'}
                            </span>
                          </div>
                        </td>
                        <td className="backtest-table-cell">
                          <span className={
                            row.sniperHitRate != null
                              ? row.sniperHitRate >= 50 ? 'text-success' : 'text-warning'
                              : 'text-muted-text'
                          }>
                            {formatRate(row.sniperHitRate)}
                          </span>
                          {row.sniperTotalCount != null && (
                            <span className="text-xs text-muted-text ml-1">
                              ({row.sniperHitCount}/{row.sniperTotalCount})
                            </span>
                          )}
                        </td>
                        <td className="backtest-table-cell">
                          <span className={
                            row.actionReturn != null
                              ? row.actionReturn > 0 ? 'text-success' : row.actionReturn < 0 ? 'text-danger' : 'text-secondary-text'
                              : 'text-muted-text'
                          }>
                            {formatReturn(row.actionReturn)}
                          </span>
                        </td>
                        <td className="backtest-table-cell">
                          <VerificationBadge
                            status={row.verificationStatus}
                            trendHit={row.trendHit}
                            sniperHitRate={row.sniperHitRate}
                            actionReturn={row.actionReturn}
                            compact
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-4">
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                />
              </div>

              <p className="text-xs text-muted-text text-center mt-2">
                {totalItems} result{totalItems !== 1 ? 's' : ''} total · page {currentPage} of {Math.max(totalPages, 1)}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default AccuracyPage;