import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  VerificationStatsRequest,
  VerificationStatsResponse,
  VerificationListResponse,
  VerificationListItem,
  VerificationDetail,
  VerificationRunRequest,
  VerificationRunResponse,
  VerificationSingleRunResponse,
} from '../types/verification';

// ============ API ============

export const verificationApi = {
  /**
   * Get verification statistics
   */
  getStats: async (params: VerificationStatsRequest = {}): Promise<VerificationStatsResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.stockCode) queryParams.stock_code = params.stockCode;
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.dimension) queryParams.dimension = params.dimension;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/verification/stats',
      { params: queryParams },
    );
    return toCamelCase<VerificationStatsResponse>(response.data);
  },

  /**
   * Get paginated verification list
   */
  getList: async (params: {
    stockCode?: string;
    startDate?: string;
    endDate?: string;
    trendHit?: boolean;
    actionHit?: boolean;
    page?: number;
    limit?: number;
  } = {}): Promise<VerificationListResponse> => {
    const { stockCode, startDate, endDate, trendHit, actionHit, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number | boolean> = { page, limit };
    if (stockCode) queryParams.stock_code = stockCode;
    if (startDate) queryParams.start_date = startDate;
    if (endDate) queryParams.end_date = endDate;
    if (trendHit !== undefined) queryParams.trend_hit = trendHit;
    if (actionHit !== undefined) queryParams.action_hit = actionHit;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/verification/list',
      { params: queryParams },
    );

    const data = toCamelCase<VerificationListResponse>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: (data.items || []).map(item => toCamelCase<VerificationListItem>(item)),
    };
  },

  /**
   * Get verification detail by ID
   */
  getDetail: async (id: number): Promise<VerificationDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/verification/${id}`,
    );
    return toCamelCase<VerificationDetail>(response.data);
  },

  /**
   * Trigger batch verification task
   */
  runVerification: async (params: VerificationRunRequest = {}): Promise<VerificationRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.stockCode) requestData.stock_code = params.stockCode;
    if (params.analysisDate) requestData.analysis_date = params.analysisDate;
    if (params.daysBack) requestData.days_back = params.daysBack;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/verification/run',
      requestData,
    );
    return toCamelCase<VerificationRunResponse>(response.data);
  },

  /**
   * Trigger single record verification
   */
  runSingleVerification: async (analysisId: number): Promise<VerificationSingleRunResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/verification/run/${analysisId}`,
    );
    return toCamelCase<VerificationSingleRunResponse>(response.data);
  },
};