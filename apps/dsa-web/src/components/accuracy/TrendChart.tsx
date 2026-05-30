import type React from 'react';
import { useMemo } from 'react';
import type { PeriodVerificationStats } from '../../types/verification';

interface TrendChartProps {
  data: PeriodVerificationStats[];
  title?: string;
  className?: string;
}

function getBarColor(hitRate: number | undefined): string {
  if (hitRate == null) return 'bg-muted-text/30';
  if (hitRate >= 60) return 'bg-success';
  if (hitRate >= 40) return 'bg-warning';
  return 'bg-danger';
}

export const TrendChart: React.FC<TrendChartProps> = ({
  data,
  title = '趋势准确率',
  className = '',
}) => {
  const maxValue = useMemo(() => {
    const values = data.map(d => d.trendHitRate ?? 0);
    return Math.max(...values, 100);
  }, [data]);

  const avgHitRate = useMemo(() => {
    if (data.length === 0) return 0;
    const sum = data.reduce((acc, d) => acc + (d.trendHitRate ?? 0), 0);
    return sum / data.length;
  }, [data]);

  if (data.length === 0) {
    return (
      <div className={`rounded-xl border border-subtle bg-surface/45 p-4 ${className}`}>
        <div className="mb-2 text-xs uppercase tracking-[0.22em] text-secondary-text">{title}</div>
        <div className="flex items-center justify-center h-24 text-sm text-muted-text">
          暂无数据
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-subtle bg-surface/45 p-4 ${className}`}>
      <div className="mb-3 text-xs uppercase tracking-[0.22em] text-secondary-text">{title}</div>
      <div className="flex items-end gap-2 h-24">
        {data.slice(0, 10).map((item, index) => {
          const height = (item.trendHitRate ?? 0) / maxValue * 100;
          const barColor = getBarColor(item.trendHitRate);

          return (
            <div
              key={index}
              className="flex flex-col items-center gap-1 flex-1"
            >
              <div className="relative w-full flex flex-col items-center justify-end h-20">
                <div
                  className={`w-full max-w-[2rem] rounded-t-sm ${barColor} transition-all`}
                  style={{ height: `${Math.max(height, 4)}%` }}
                />
              </div>
              <div className="text-xs text-muted-text truncate max-w-[3rem]">
                {item.period}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted-text">
        <span>命中率</span>
        <span className="font-mono">
          平均: {avgHitRate.toFixed(1)}%
        </span>
      </div>
    </div>
  );
};