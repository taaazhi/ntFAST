import axios from 'axios';
import type {
  User,
  Subject,
  Analysis,
  Transaction,
  LoginCredentials,
  RegisterData,
  AuthResponse
} from '../types';

// Centralized URL config — override with VITE_API_URL env var for production
// Empty string = same origin (nginx proxy in Docker), otherwise direct backend URL
const BACKEND_HOST = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const API_BASE_URL = BACKEND_HOST ? `${BACKEND_HOST}/api` : '/api';
// Guard window access for SSR/test environments where `window` is undefined.
const _sameOriginWS = typeof window !== 'undefined'
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  : 'ws://localhost:8000';
export const WS_BASE_URL = BACKEND_HOST
  ? BACKEND_HOST.replace(/^http/, 'ws')
  : _sameOriginWS;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Common API response shapes
export interface ApiMessageResponse { message: string }
export interface LoginHistoryItem {
  id: number;
  login_time: string | null;
  logout_time: string | null;
  session_duration: number | null;
  ip_address: string | null;
  user_agent: string | null;
  location: string | null;
  is_suspicious: boolean;
}
export interface ActiveSession {
  id: number;
  login_time: string | null;
  ip_address: string | null;
  user_agent: string | null;
  location: string | null;
  is_suspicious: boolean;
}

// Auth API
export const authAPI = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await api.post<AuthResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  register: async (data: RegisterData): Promise<ApiMessageResponse & { verification_required?: boolean; email?: string }> => {
    const response = await api.post<ApiMessageResponse & { verification_required?: boolean; email?: string }>('/auth/register', data);
    return response.data;
  },

  getRegistrationConfig: async (): Promise<{ require_email_verification: boolean }> => {
    const response = await api.get('/auth/registration-config');
    return response.data;
  },

  completeRegistration: async (data: RegisterData): Promise<User> => {
    const response = await api.post<User>('/auth/complete-registration', data);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  changePassword: async (data: { current_password: string; new_password: string }): Promise<ApiMessageResponse> => {
    const response = await api.post<ApiMessageResponse>('/auth/change-password', data);
    return response.data;
  },

  forgotPassword: async (data: { email: string }): Promise<ApiMessageResponse> => {
    const response = await api.post<ApiMessageResponse>('/auth/forgot-password', data);
    return response.data;
  },

  resetPassword: async (data: { email: string; code: string; new_password: string }): Promise<ApiMessageResponse> => {
    const response = await api.post<ApiMessageResponse>('/auth/reset-password', data);
    return response.data;
  },

  loginHistory: async (limit: number = 10): Promise<{ history: LoginHistoryItem[] }> => {
    const response = await api.get<{ history: LoginHistoryItem[] }>(`/auth/login-history?limit=${limit}`);
    return response.data;
  },

  activeSessions: async (): Promise<{ active_sessions: ActiveSession[] }> => {
    const response = await api.get<{ active_sessions: ActiveSession[] }>('/auth/active-sessions');
    return response.data;
  },

  closeAllSessions: async (): Promise<ApiMessageResponse & { sessions_closed?: number }> => {
    const response = await api.post<ApiMessageResponse & { sessions_closed?: number }>('/auth/close-all-sessions');
    return response.data;
  },
};

// Email Verification API
export const emailVerificationAPI = {
  sendCode: async (email: string): Promise<any> => {
    const response = await api.post('/email-verification/send-code', { email });
    return response.data;
  },

  verifyCode: async (email: string, code: string): Promise<any> => {
    const response = await api.post('/email-verification/verify-code', { email, code });
    return response.data;
  },
};

// Users Management API
export const usersAPI = {
  getAll: async (): Promise<any> => {
    const response = await api.get('/users/');
    return response.data;
  },

  updateRole: async (userId: number, role: string): Promise<any> => {
    const response = await api.patch(`/users/${userId}/role`, { role });
    return response.data;
  },

  delete: async (userId: number): Promise<void> => {
    await api.delete(`/users/${userId}`);
  },

  getProfile: async (userId: number): Promise<any> => {
    const response = await api.get(`/users/${userId}/profile`);
    return response.data;
  },
};

// Subjects API
export const subjectsAPI = {
  getAll: async (params?: {
    skip?: number;
    limit?: number;
    risk_level?: string;
    status?: string;
    search?: string;
  }): Promise<Subject[]> => {
    const response = await api.get<Subject[]>('/subjects/', { params });
    return response.data;
  },

  getById: async (id: number): Promise<Subject> => {
    const response = await api.get<Subject>(`/subjects/${id}`);
    return response.data;
  },

  create: async (data: Partial<Subject>): Promise<Subject> => {
    const response = await api.post<Subject>('/subjects/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Subject>): Promise<Subject> => {
    const response = await api.put<Subject>(`/subjects/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/subjects/${id}`);
  },
};

// Analyses API
export const analysesAPI = {
  getAll: async (params?: {
    skip?: number;
    limit?: number;
    status_filter?: string;
    subject_id?: number;
    sort_by?: string;
    sort_order?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    search?: string;
  }): Promise<Analysis[]> => {
    const response = await api.get<Analysis[]>('/analyses/', { params });
    return response.data;
  },

  getById: async (id: number): Promise<Analysis> => {
    const response = await api.get<Analysis>(`/analyses/${id}`);
    return response.data;
  },

  create: async (data: Partial<Analysis>): Promise<Analysis> => {
    const response = await api.post<Analysis>('/analyses/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Analysis>): Promise<Analysis> => {
    const response = await api.put<Analysis>(`/analyses/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/analyses/${id}`);
  },

  uploadFile: async (file: File, onProgress?: (progress: number) => void): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/analyses/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  },

  getStats: async (): Promise<any> => {
    const response = await api.get('/analyses/stats');
    return response.data;
  },

  batchDelete: async (ids: number[]): Promise<{ deleted: number; errors: string[] }> => {
    const response = await api.post('/analyses/batch-delete', { ids });
    return response.data;
  },

  getTransactions: async (analysisId: number): Promise<any> => {
    const response = await api.get(`/analyses/${analysisId}/transactions`);
    return response.data;
  },

  reanalyze: async (analysisId: number): Promise<{ id: number; status: string; task_id: string; message: string }> => {
    const response = await api.post(`/analyses/${analysisId}/reanalyze`);
    return response.data;
  },

  cancel: async (analysisId: number): Promise<{ id: number; status: string; message: string }> => {
    const response = await api.post(`/analyses/${analysisId}/cancel`);
    return response.data;
  },
};

// Transactions API
export const transactionsAPI = {
  getAll: async (params?: {
    skip?: number;
    limit?: number;
    subject_id?: number;
    is_suspicious?: boolean;
    transaction_type?: string;
  }): Promise<Transaction[]> => {
    const response = await api.get<Transaction[]>('/transactions/', { params });
    return response.data;
  },

  getById: async (id: number): Promise<Transaction> => {
    const response = await api.get<Transaction>(`/transactions/${id}`);
    return response.data;
  },

  create: async (data: Partial<Transaction>): Promise<Transaction> => {
    const response = await api.post<Transaction>('/transactions/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Transaction>): Promise<Transaction> => {
    const response = await api.put<Transaction>(`/transactions/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/transactions/${id}`);
  },
};

// PDF Analysis API
export interface PDFAnalysisResult {
  success: boolean;
  analysis_id: string;
  analysis_date: string;
  pdf_filename: string;
  pdf_hash: string;
  period: {
    start: string | null;
    end: string | null;
  };
  summary: {
    total_transactions: number;
    total_income: number;
    total_expense: number;
    net_flow: number;
    avg_balance: number;
  };
  risk_assessment: {
    total_score: number;
    risk_level: string;
    gaming_gambling: {
      score: number;
      level: string;
      total_amount: number;
      transactions: number;
      platforms: string[];
      percentage_of_expenses: number;
    };
    money_laundering: {
      score: number;
      level: string;
      round_amounts: number;
      split_groups: number;
      transit_ops: number;
      cash_intensity: number;
    };
    p2p_analysis: {
      score: number;
      level: string;
      total_income: number;
      total_expense: number;
      unique_counterparties: number;
      dependency: number;
      top_counterparties: Array<{
        name: string;
        total_income: number;
        total_expense: number;
        transaction_count: number;
      }>;
    };
    red_flags: string[];
    recommendations: string[];
  };
  social_profile: {
    status: string;
    confidence: number;
    income_sources: string[];
    avg_monthly_income: number;
    avg_monthly_expense: number;
    financial_stability: string;
    subscriptions: string[];
  };
  ai_summary: string;
  transactions: Array<{
    date: string;
    amount: number;
    type: string;
    category: string;
    description: string;
    counterparty: string | null;
    risk_flags: string[];
  }>;
  anonymization: {
    customer_name: {
      original: string;
      tag: string;
    };
    counterparties_count: number;
  };
}

export const pdfAnalysisAPI = {
  analyze: async (file: File, useAI: boolean = false, onProgress?: (progress: number) => void): Promise<PDFAnalysisResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<PDFAnalysisResult>(`/pdf-analysis/analyze?use_ai=${useAI}&anonymize=true`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  },

  checkOllamaStatus: async (): Promise<{ available: boolean; host: string; model: string }> => {
    const response = await api.get('/pdf-analysis/ollama-status');
    return response.data;
  },
};

// Fraud Analysis Types

export interface VelocityData {
  burst_alerts: Array<{
    date: string;
    transaction_count: number;
    total_amount: number;
    window_hours: number;
  }>;
  daily_spikes: Array<{
    date: string;
    transaction_count: number;
    total_amount: number;
    z_score: number;
    avg_daily: number;
  }>;
  amount_acceleration: Array<{
    date: string;
    amount_24h: number;
    pct_of_monthly_income: number;
  }>;
  counterparty_churn: Record<string, any>;
  risk_score: number;
}

export interface GraphData {
  node_count: number;
  edge_count: number;
  cycles: Array<{ nodes: string[]; length: number; total_flow: number }>;
  communities: Array<{ members: string[]; size: number }>;
  centrality: Record<string, number>;
  hub_nodes: Array<{ name: string; total_volume: number; in_volume: number; out_volume: number; connections: number; is_bidirectional: boolean }>;
  risk_score: number;
  nodes: Array<{ id: string; is_owner: boolean; in_volume: number; out_volume: number; total_volume: number; connections: number }>;
  edges: Array<{ source: string; target: string; weight: number; count: number }>;
}

export interface BehavioralData {
  baseline_deviation_score: number;
  unusual_hours: Array<any>;
  spending_trend: string;
  category_anomalies: Array<{ category: string; amount: number; z_score: number; category_mean: number }>;
  weekday_pattern: Record<string, number>;
  risk_score: number;
}

export interface StructuringData {
  just_under_threshold: Array<{
    date: string;
    amount: number;
    threshold: number;
    pct_of_threshold: number;
    counterparty: string;
  }>;
  split_groups: Array<{
    counterparty: string;
    date: string;
    transaction_count: number;
    individual_amounts: number[];
    total_amount: number;
    exceeds_threshold: boolean;
  }>;
  smurfing_patterns: Array<{
    amount: number;
    occurrence_count: number;
    unique_counterparties: number;
    counterparties: string[];
    total_amount: number;
  }>;
  risk_score: number;
}

export interface CrossReferenceData {
  income_expense_ratio: number;
  unexplained_inflows: Array<any>;
  rapid_pass_through: Array<{
    income_date: string;
    income_amount: number;
    income_source: string;
    expense_date: string;
    expense_amount: number;
    expense_dest: string;
    match_ratio: number;
    time_gap_hours: number;
  }>;
  source_destination_map: {
    top_sources: Array<{ name: string; amount: number }>;
    top_destinations: Array<{ name: string; amount: number }>;
  };
  risk_score: number;
}

export interface MerchantRiskData {
  high_risk_merchants: Array<{
    name: string;
    amount: number;
    count: number;
    category: string;
  }>;
  medium_risk_merchants: Array<{
    name: string;
    amount: number;
    count: number;
    category: string;
  }>;
  total_high_risk_amount: number;
  total_high_risk_pct: number;
  risk_score: number;
}

export interface NightTransactionsData {
  night_count: number;
  night_total_amount: number;
  night_ratio: number;
  large_night_transfers: any[];
  night_clusters: any[];
  risk_score: number;
  no_time_data?: boolean;  // true если в выписке нет данных о времени
}

export interface DuplicatePaymentsData {
  duplicate_groups: any[];
  same_amount_diff_recipient: any[];
  total_duplicates: number;
  total_duplicate_amount: number;
  risk_score: number;
}

export interface RoundAmountsData {
  round_count: number;
  round_ratio: number;
  round_total_amount: number;
  amount_distribution: Record<string, number>;
  consecutive_round: any[];
  round_transactions: any[];
  risk_score: number;
}

export interface ProfileMismatchData {
  mismatches: any[];
  oversized_transactions: any[];
  unexpected_activity: any[];
  income_anomalies: any[];
  risk_score: number;
}

export interface AccountProfileData {
  account_type: string;
  avg_monthly_income: number;
  avg_monthly_expense: number;
  income_regularity_score: number;
  monthly_income_cv: number;
  unique_income_sources: number;
  unique_expense_destinations: number;
  has_salary_flag: boolean;
  has_pension_flag: boolean;
  has_crypto_activity: boolean;
  has_business_activity: boolean;
  pass_through_ratio: number;
}

export interface FraudReport {
  composite_score: number;
  risk_level: string;
  velocity: VelocityData;
  graph: GraphData;
  behavioral: BehavioralData;
  structuring: StructuringData;
  cross_reference: CrossReferenceData;
  merchant_risk: MerchantRiskData;
  night_transactions?: NightTransactionsData;
  duplicate_payments?: DuplicatePaymentsData;
  round_amounts?: RoundAmountsData;
  profile_mismatch?: ProfileMismatchData;
  red_flags: string[];
  recommendations: string[];
  account_profile?: AccountProfileData;
  flagged_patterns?: any[];
  explained_flags?: any[];
  applied_weights?: Record<string, number>;
}

// Kaspi Bank Analysis API
export interface KaspiAnalysisResult {
  meta: {
    generated_at: string;
    pdf_file: string;
    parser_version: string;
    original_filename?: string;
  };
  account: {
    owner: string;
    card: string;
    account_number: string;
    currency: string;
    period: {
      from: string | null;
      to: string | null;
    };
    balance_start: number;
    balance_end: number;
  };
  validation: {
    total_transactions: number;
    is_valid: boolean;
    expected: Record<string, number>;
    actual: Record<string, number>;
    differences: Record<string, number>;
    errors: string[];
  };
  summary: {
    total_transactions: number;
    total_income: number;
    total_expense: number;
    net_flow: number;
    avg_daily_expense: number;
    median_transaction: number;
  };
  transactions: Array<{
    date: string;
    amount: number;
    type: string;
    details: string;
    category: string;
    subcategory: string;
    currency: string;
    original_amount: number | null;
    original_currency: string | null;
  }>;
  analytics: {
    monthly_breakdown: Array<{
      month: string;
      month_name: string;
      income: number;
      expense: number;
      balance: number;
      transaction_count: number;
    }>;
    category_breakdown: {
      expense: Array<{
        category: string;
        amount: number;
        count: number;
        percentage: number;
      }>;
      income: Array<{
        category: string;
        amount: number;
        count: number;
        percentage: number;
      }>;
      total_expense: number;
      total_income: number;
    };
    top_merchants: Array<{
      merchant: string;
      amount: number;
      count: number;
      avg_transaction: number;
    }>;
    top_contacts: Array<{
      name: string;
      sent: number;
      received: number;
      balance: number;
      count: number;
    }>;
    recurring_payments: Array<{
      name: string;
      count: number;
      total_amount: number;
      avg_amount: number;
      frequency: string;
      avg_interval_days: number;
      last_payment: string;
    }>;
    anomalies: Array<{
      type: string;
      date: string;
      amount?: number;
      details?: string;
      transaction_count?: number;
      total_amount?: number;
      threshold?: number;
      deviation?: number;
    }>;
    foreign_currency: {
      transactions: Array<{
        currency: string;
        transaction_count: number;
        total_original: number;
        total_kzt: number;
        avg_exchange_rate: number;
      }>;
      total_foreign_kzt: number;
    };
    financial_health: {
      savings_rate: number;
      essential_expenses: number;
      non_essential_expenses: number;
      essential_ratio: number;
      balance_trend: string;
      monthly_avg_income: number;
      monthly_avg_expense: number;
      financial_buffer_days: number;
    };
    weekday_analysis: Array<{
      day: string;
      day_index: number;
      amount: number;
      count: number;
      avg_transaction: number;
    }>;
    daily_patterns: Array<{
      date: string;
      income: number;
      expense: number;
      balance: number;
    }>;
  };
  contacts: Record<string, {
    count: number;
    is_frequent: boolean;
  }>;
  fraud_report: FraudReport | null;
}

export const bankAnalysisAPI = {
  analyze: async (
    file: File,
    onProgress?: (progress: number) => void,
    sessionId?: string,
  ): Promise<KaspiAnalysisResult> => {
    const formData = new FormData();
    formData.append('file', file);

    // Добавляем session_id для WebSocket прогресса
    const params = sessionId ? { session_id: sessionId } : {};

    const response = await api.post<KaspiAnalysisResult>('/bank/analyze', formData, {
      params,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  },

  detect: async (file: File): Promise<{
    bank_type: string;
    bank_name: string;
    confidence: number;
    detected_keywords: string[];
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/bank/detect', formData);
    return response.data;
  },

  getSupportedBanks: async (): Promise<{
    banks: Array<{
      type: string;
      name: string;
      country: string;
      status: string;
      formats: string[];
    }>;
  }> => {
    const response = await api.get('/bank/supported-banks');
    return response.data;
  },

  getCategories: async (): Promise<{
    expense_categories: Array<{ id: string; name: string; keywords_count: number }>;
    transfer_categories: Array<{ id: string; name: string }>;
    income_categories: Array<{ id: string; name: string }>;
  }> => {
    const response = await api.get('/bank/categories');
    return response.data;
  },

  exportPDF: async (analysisData: KaspiAnalysisResult): Promise<Blob> => {
    const response = await api.post('/bank/export-pdf', analysisData, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export default api;
