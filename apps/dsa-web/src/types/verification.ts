/**
 * Verification API type definitions
 * Mirrors api/v1/schemas/verification.py
 */

// ============ Request / Response ============

export interface VerificationStatsRequest {
  stockCode?: string;
  startDate?: string;
  endDate?: string;
  dimension?: 'trend' | 'sniper' | 'sentiment' | 'action';
}

export interface VerificationStatsResponse {
  totalCount: number;
  trendHitRate?: number;
  sniperAvgHitRate?: number;
  sentimentAvgCorrelation?: number;
  actionProfitRate?: number;
  actionAvgReturn?: number;
  byStock: StockVerificationStats[];
  byPeriod: PeriodVerificationStats[];
}

export interface StockVerificationStats {
  stockCode: string;
  stockName?: string;
  totalCount: number;
  trendHitRate?: number;
  sniperAvgHitRate?: number;
  sentimentAvgCorrelation?: number;
  actionProfitRate?: number;
  actionAvgReturn?: number;
}

export interface PeriodVerificationStats {
  period: string;
  startDate: string;
  endDate: string;
  totalCount: number;
  trendHitRate?: number;
  actionAvgReturn?: number;
}

// ============ List Item ============

export interface VerificationListItem {
  id: number;
  analysisHistoryId: number;
  stockCode: string;
  stockName?: string;
  analysisDate: string;
  verificationDate: string;
  holdingPeriod: number;
  trendPredicted?: string;
  trendActual?: string;
  trendHit?: boolean;
  sniperHitRate?: number;
  sniperHitCount?: number;
  sniperTotalCount?: number;
  sentimentPredicted?: number;
  sentimentActual?: number;
  sentimentCorrelation?: number;
  actionPredicted?: string;
  actionReturn?: number;
  actionHit?: boolean;
  verificationStatus?: 'verified' | 'pending' | 'data_missing';
}

export interface VerificationListResponse {
  total: number;
  page: number;
  limit: number;
  items: VerificationListItem[];
}

// ============ Detail ============

export interface SniperPointVerification {
  type: string;
  price: number;
  label?: string;
  hit?: boolean;
  hitPrice?: number;
  hitDate?: string;
}

export interface VerificationDetail extends VerificationListItem {
  trendChangePct?: number;
  sniperPoints: SniperPointVerification[];
  actionEntryPrice?: number;
  actionExitPrice?: number;
  originalSentimentScore?: number;
  originalOperationAdvice?: string;
  originalAnalysisSummary?: string;
}

// ============ Run Request ============

export interface VerificationRunRequest {
  stockCode?: string;
  analysisDate?: string;
  daysBack?: number;
}

export interface VerificationRunResponse {
  status: string;
  message: string;
  verifiedCount: number;
  verificationIds: number[];
}

export interface VerificationSingleRunResponse {
  status: string;
  message: string;
  verificationId?: number;
  analysisHistoryId: number;
}