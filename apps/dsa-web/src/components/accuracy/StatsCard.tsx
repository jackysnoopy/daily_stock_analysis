import type React from 'react';
import { useMemo } from 'react';

interface StatsCardProps {
  title: string;
  value?: number | null;
  format?: 'percent' | 'number' | 'currency';
  subtitle?: string;
  accent?: boolean;
  icon?: React.ReactNode;
}

function formatValue(value: number | null | undefined, format: 'percent' | 'number' | 'currency'): string {
  if (value == null) return '--';
  if (format === 'percent') return `${value.toFixed(1)}%`;
  if (format === 'currency') return `${value.toFixed(2)}`;
  return value.toFixed(1);
}

function getValueColor(value: number | null | undefined, format: 'percent' | 'number' | 'currency'): string {
  if (value == null) return 'text-muted-text';
  if (format === 'percent' && value >= 50) return 'text-success';
  if (format === 'percent' && value < 50) return 'text-danger';
  if (format === 'currency' && value > 0) return 'text-success';
  if (format === 'currency' && value < 0) return 'text-danger';
  return 'text-secondary-text';
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  format = 'percent',
  subtitle,
  accent = false,
  icon,
}) => {
  const displayValue = useMemo(() => formatValue(value, format), [value, format]);
  const valueColor = useMemo(() => getValueColor(value, format), [value, format]);

  return (
    <div className={`rounded-xl border border-subtle bg-card/75 p-4 shadow-soft-card ${accent ? 'border-cyan/18' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="mb-2">
            <span className="text-xs uppercase tracking-[0.22em] text-secondary-text">{title}</span>
          </div>
          <div className={`text-2xl font-bold ${valueColor}`}>
            {displayValue}
          </div>
          {subtitle && (
            <div className="mt-1 text-xs text-muted-text">
              {subtitle}
            </div>
          )}
        </div>
        {icon && (
          <div className="flex-shrink-0 opacity-60 text-cyan">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
};