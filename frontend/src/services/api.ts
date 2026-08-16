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
  // Server-decided "this is the request that just asked" flag (matches UA+IP).
  // Falls back to most-recent session if no exact match exists.
  is_current?: boolean;
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
export interface NotificationSettings {
  email: boolean;
  in_app: boolean;
  security: boolean;
  analyses: boolean;
}

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

  getNotificationSettings: async (): Promise<NotificationSettings> => {
    const response = await api.get<NotificationSettings>('/users/me/notification-settings');
    return response.data;
  },

  updateNotificationSettings: async (patch: Partial<NotificationSettings>): Promise<NotificationSettings> => {
    const response = await api.put<NotificationSettings>('/users/me/notification-settings', patch);
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

/** Ответ на постановку файла в очередь анализа. */
export interface AnalysisUploadResponse {
  id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
  message: string;
}

// Analyses API
/**
 * Заключение по делу, составленное языковой моделью.
 *
 * `is_trustworthy` — не украшение: заключение с числом, которого нет в
 * фактах, или с неподтверждённой нормой показывается с оговоркой, а не
 * выдаётся за проверенное. Скрывать его нельзя — следователь должен видеть,
 * что именно было составлено.
 */
export interface AnalysisConclusion {
  text: string;
  provider?: string | null;
  citations: LegalArticle[];
  invented_numbers: string[];
  /** Текст упёрся в потолок длины и оборван на полуслове. */
  truncated?: boolean;
  is_trustworthy: boolean;
  exists?: boolean;
  error?: string | null;
}

/** Ответ следственного агента на вопрос по конкретному анализу. */
export interface AgentAnswer {
  text: string;
  tool_calls: { tool: string; params: Record<string, unknown>; ok: boolean }[];
  citations: LegalArticle[];
  steps: number;
  stopped_early: boolean;
  provider?: string | null;
  error?: string | null;
  has_unverified_citations: boolean;
}

/**
 * Разобрать накопленный буфер SSE на готовые события и остаток.
 *
 * Кадр заканчивается пустой строкой, а сеть режет поток где придётся: у
 * последнего куска буфера может не хватать хвоста, и разобрать его сейчас
 * значит потерять начало следующего события. Поэтому неполный остаток
 * возвращается обратно и ждёт следующего чтения.
 *
 * Вынесено из streamConclusion, чтобы это можно было проверить без сети.
 */
export function parseStreamFrames(buffer: string): { events: any[]; rest: string } {
  const frames = buffer.split('\n\n');
  // Последний элемент — либо неполный кадр, либо пустая строка после
  // завершённого. И то и другое возвращается как остаток.
  const rest = frames.pop() || '';

  const events: any[] = [];
  for (const frame of frames) {
    const line = frame.split('\n').find((l) => l.startsWith('data: '));
    if (!line) continue;
    try {
      events.push(JSON.parse(line.slice(6)));
    } catch {
      // Битый кадр — не повод потерять уже полученный текст.
    }
  }
  return { events, rest };
}

export const analysesAPI = {
  /** Ранее составленное заключение. Модель не вызывается. */
  getConclusion: async (analysisId: number): Promise<AnalysisConclusion> => {
    const response = await api.get<AnalysisConclusion>(`/analyses/${analysisId}/conclusion`);
    return response.data;
  },

  /**
   * Составить заключение. Занимает около полуминуты на локальной модели,
   * поэтому запускается по решению следователя, а не при открытии отчёта.
   */
  /**
   * Заключение потоком: текст приходит по мере написания.
   *
   * Не через axios — он отдаёт ответ целиком, а здесь нужен ровно обратный
   * порядок. `onChunk` вызывается на каждый кусок; возвращается тот же
   * проверенный итог, что и у обычного метода, потому что и проверяет его
   * тот же код на сервере.
   */
  streamConclusion: async (
    analysisId: number,
    onChunk: (text: string) => void,
  ): Promise<AnalysisConclusion> => {
    const response = await fetch(
      `${API_BASE_URL}/analyses/${analysisId}/conclusion/stream`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || ''}` },
      },
    );

    if (!response.ok || !response.body) {
      // Тело ошибки приходит обычным JSON — сообщение с сервера объясняет,
      // что включить, и терять его нельзя.
      let detail = `HTTP ${response.status}`;
      try {
        detail = (await response.json())?.detail || detail;
      } catch {
        /* не JSON — оставляем код состояния */
      }
      throw new Error(detail);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let final: AnalysisConclusion | null = null;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseStreamFrames(buffer);
      buffer = rest;

      for (const event of events) {
        if (event.type === 'chunk') onChunk(event.text);
        else if (event.type === 'done') final = event as AnalysisConclusion;
        else if (event.type === 'error') throw new Error(event.detail);
      }
    }

    if (!final) throw new Error('Поток завершился без результата');
    return final;
  },

  buildConclusion: async (analysisId: number): Promise<AnalysisConclusion> => {
    const response = await api.post<AnalysisConclusion>(
      `/analyses/${analysisId}/conclusion`, {}, { timeout: 300000 },
    );
    return response.data;
  },

  /** Вопрос следственного агента по конкретному анализу. */
  ask: async (analysisId: number, question: string): Promise<AgentAnswer> => {
    const response = await api.post<AgentAnswer>(
      `/analyses/${analysisId}/ask`, { question }, { timeout: 300000 },
    );
    return response.data;
  },

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

  /**
   * The single entry point for analysing a statement, whatever its format.
   *
   * Returns as soon as the file is queued — the response carries the created
   * Analysis with status `pending`. Progress arrives over
   * `/ws/analysis/{sessionId}`; the finished report is read back with
   * `getById`. There used to be a second, synchronous route for PDF/XLSX
   * (`POST /bank/analyze`) that produced a different result for the same file.
   */
  uploadFile: async (
    file: File,
    onProgress?: (progress: number) => void,
    sessionId?: string,
  ): Promise<AnalysisUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<AnalysisUploadResponse>('/analyses/upload', formData, {
      params: sessionId ? { session_id: sessionId } : {},
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
  /** Shell-company suspects — generic legal-entity names used to layer funds. */
  shell_companies?: Array<{
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
  flagged_patterns?: FlaggedPattern[];
  explained_flags?: ExplainedFlag[];
  applied_weights?: Record<string, number>;
}

/**
 * Обоснование одного сработавшего признака.
 *
 * `counter_evidence` — не украшение. Отчёт попадает в материалы дела, и
 * следователь обязан видеть не только довод «за», но и законное объяснение,
 * при котором тот же признак ничего не значит. Балл без контраргумента —
 * это обвинение без защиты.
 */
export interface ExplainedFlag {
  module: string;
  severity: string;
  reason: string;
  evidence?: Record<string, unknown>[];
  confidence: number;
  counter_evidence?: string;
  score_contribution: number;
}

/**
 * Норма права, сверенная с официальным текстом на adilet.zan.kz.
 *
 * `verified` не косметика: ссылки на статьи писались людьми по памяти, и
 * пять из шести указывали не на ту норму. Модель ошибается так же, только
 * увереннее. Показывать непроверенную ссылку как подтверждённую в документе
 * для следствия нельзя, скрывать — тоже: остаётся честно её пометить.
 */
export interface LegalArticle {
  citation: string;
  title: string;
  url: string;
  verified: boolean;
  verdict: string;
  detail?: string;
  /**
   * Название и ссылка на казахскую редакцию того же акта. Официальное
   * название нормы не переводится на ходу — оно берётся с adilet.zan.kz,
   * потому что сочинять формулировку закона в документе для следствия
   * нельзя. Пусто, если перевода в корпусе нет.
   */
  title_kk?: string;
  url_kk?: string;
}

/** Распознанная схема — с нормой права, по которой она квалифицируется. */
export interface FlaggedPattern {
  pattern_name: string;
  display_name: string;
  confidence: number;
  risk_contribution: number;
  evidence?: Record<string, unknown>[];
  /** Русская формулировка с бэкенда — запасной вариант, если перевода нет. */
  reason: string;
  counter_evidence?: string;
  regulatory_reference?: string;
  legal_articles?: LegalArticle[];
  /**
   * Числа для локализованной формулировки. Движок не знает языка читателя,
   * поэтому отдаёт `pattern_name` и параметры, а текст собирает интерфейс.
   */
  reason_params?: Record<string, number | string>;
  /** Какой контраргумент применим: у счёта ИП и личного они разные. */
  counter_evidence_variant?: string;
}

/** Найденный источник регулярного дохода — с обоснованием, а не флагом. */
export interface SalarySource {
  counterparty: string;
  payments: number;
  months: number;
  median_amount: number;
  day_of_month: number;
  reason: string;
}

/** Результат шага обогащения: см. backend/app/services/enrichment/. */
export interface EnrichmentInfo {
  classified: number;
  salary_sources: SalarySource[];
  classifier?: Record<string, unknown> | null;
  privacy?: Record<string, number | boolean> | null;
}

// Kaspi Bank Analysis API
export interface KaspiAnalysisResult {
  meta: {
    generated_at: string;
    pdf_file: string;
    parser_version: string;
    original_filename?: string;
    /** Нужен для вызовов заключения и агента по этому анализу. */
    analysis_id?: number;
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
    /** Extraction succeeded — transactions were read from the statement. */
    is_valid: boolean;
    /**
     * Does the document reconcile with itself (opening + flows == closing)?
     * `null` when the format carries no balances to check against (e.g. Binance,
     * where amounts are denominated in different coins). Deliberately separate
     * from `is_valid`: a multi-currency Halyk statement can be extracted
     * perfectly and still not reconcile on its KZT leg alone.
     */
    balance_reconciled: boolean | null;
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
  enrichment?: EnrichmentInfo | null;
}

/**
 * Helpers around statement analysis. Uploading is NOT here — a statement is
 * submitted through `analysesAPI.uploadFile`, which queues it for the worker.
 */
export const bankAnalysisAPI = {
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

// Notifications API
export type NotificationKind =
  | 'analysis_completed'
  | 'analysis_failed'
  | 'analysis_cancelled'
  | 'new_login'
  | 'parallel_session'
  | 'password_changed'
  | 'system_alert'
  | 'info';

export type NotificationSeverity = 'info' | 'success' | 'warning' | 'error';

export interface NotificationItem {
  id: number;
  kind: NotificationKind;
  severity: NotificationSeverity;
  title: string;
  body?: string | null;
  data?: Record<string, any> | null;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread: number;
}

export const notificationsAPI = {
  list: async (params?: { skip?: number; limit?: number; unread_only?: boolean }): Promise<NotificationListResponse> => {
    const response = await api.get<NotificationListResponse>('/notifications/', { params });
    return response.data;
  },

  markAsRead: async (id: number): Promise<NotificationItem> => {
    const response = await api.post<NotificationItem>(`/notifications/${id}/read`);
    return response.data;
  },

  markAllRead: async (): Promise<{ updated: number }> => {
    const response = await api.post<{ updated: number }>('/notifications/read-all');
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/notifications/${id}`);
  },

  deleteAll: async (): Promise<{ deleted: number }> => {
    const response = await api.delete<{ deleted: number }>('/notifications/');
    return response.data;
  },
};

export default api;
