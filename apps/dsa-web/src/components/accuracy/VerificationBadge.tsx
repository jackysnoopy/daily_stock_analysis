import type React from 'react';
import { Badge } from '../common';
import { StatusDot } from '../common';

interface VerificationBadgeProps {
  status?: 'verified' | 'pending' | 'data_missing';
  trendHit?: boolean | null;
  sniperHitRate?: number | null;
  actionReturn?: number | null;
  compact?: boolean;
}

function formatHitRate(rate: number | null | undefined): string {
  if (rate == null) return '--';
  return `${rate.toFixed(0)}%`;
}

function formatReturn(returnPct: number | null | undefined): string {
  if (returnPct == null) return '--';
  const sign = returnPct >= 0 ? '+' : '';
  return `${sign}${returnPct.toFixed(1)}%`;
}

export const VerificationBadge: React.FC<VerificationBadgeProps> = ({
  status = 'pending',
  trendHit,
  sniperHitRate,
  actionReturn,
  compact = false,
}) => {
  if (status === 'pending') {
    return (
      <Badge variant="default" className="flex items-center gap-1">
        <StatusDot tone="neutral" />
        {compact ? '待校验' : '待校验'}
      </Badge>
    );
  }

  if (status === 'data_missing') {
    return (
      <Badge variant="warning" className="flex items-center gap-1">
        <StatusDot tone="warning" />
        {compact ? '缺数据' : '数据缺失'}
      </Badge>
    );
  }

  // Verified status - show details
  const trendBadge = trendHit === true
    ? <Badge variant="success" glow className="text-xs">趋势命中</Badge>
    : trendHit === false
      ? <Badge variant="danger" glow className="text-xs">趋势未命中</Badge>
      : <Badge variant="default" className="text-xs">趋势--</Badge>;

  const sniperBadge = sniperHitRate != null
    ? <Badge variant={sniperHitRate >= 50 ? 'success' : 'warning'} className="text-xs">
        狙击 {formatHitRate(sniperHitRate)}
      </Badge>
    : null;

  const actionBadge = actionReturn != null
    ? <Badge variant={actionReturn > 0 ? 'success' : 'danger'} className="text-xs">
        收益 {formatReturn(actionReturn)}
      </Badge>
    : null;

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {trendHit === true && <StatusDot tone="success" />}
        {trendHit === false && <StatusDot tone="danger" />}
        {trendHit == null && <StatusDot tone="neutral" />}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      {trendBadge}
      {sniperBadge}
      {actionBadge}
    </div>
  );
};