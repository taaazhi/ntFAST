import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import Select from '../components/ui/Select';
import {
  Search, ScanSearch, Eye, Loader2,
  UploadCloud, File, X, FileType2, Sheet, Trash2, Inbox,
  CalendarDays, ChevronUp, ChevronDown, ChevronsLeft, ChevronsRight, ChevronLeft,
  ChevronRight, TrendingUp, ListFilter, ShieldCheck, RotateCcw,
} from 'lucide-react';
import { analysesAPI, KaspiAnalysisResult } from '../services/api';
import { BankAnalysisReport } from '../components/analysis/BankAnalysisReport';
import { EmptyState } from '../components/ui/EmptyState';
import ConfirmModal from '../components/ui/ConfirmModal';
import { useTranslation } from 'react-i18next';
import { useBackgroundAnalysis } from '../context/BackgroundAnalysisContext';

/* ───────── Types ───────── */

interface Analysis {
  id: number;
  subject_id: number | null;
  analyst_id: number;
  status: 'pending' | 'parsing' | 'analyzing' | 'in_progress' | 'completed' | 'failed';
  risk_score: number;
  analyst_notes: string | null;
  conclusion: string | null;
  file_name?: string | null;
  file_type?: string | null;
  bank_type?: string | null;
  bank_name?: string | null;
  account_owner?: string | null;
  account_number?: string | null;
  account_currency?: string | null;
  total_transactions?: number;
  suspicious_count?: number;
  fraud_composite_score?: number | null;
  fraud_risk_level?: string | null;
  fraud_report?: any | null;
  fraud_red_flags?: string[] | null;
  fraud_recommendations?: string[] | null;
  analytics_result?: any | null;
  parsed_account_info?: any | null;
  total_income?: number | null;
  total_expense?: number | null;
  total_amount?: number | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

type SortField = 'id' | 'created_at' | 'risk_score' | 'status' | 'total_transactions';
type SortOrder = 'asc' | 'desc';

const PAGE_SIZE = 15;

/* ───────── SortableHeader ───────── */

function SortableHeader({
  label, field, sortBy, sortOrder, onSort, className = '',
}: {
  label: string; field: SortField; sortBy: SortField; sortOrder: SortOrder;
  onSort: (field: SortField) => void; className?: string;
}) {
  const isActive = sortBy === field;
  return (
    <th
      onClick={() => onSort(field)}
      className={className}
      style={{ cursor: 'pointer', userSelect: 'none' }}
    >
      <div className="flex items-center gap-1.5">
        <span>{label}</span>
        <div className="flex flex-col" style={{ gap: -2 }}>
          <ChevronUp style={{ width: 11, height: 11, color: isActive && sortOrder === 'asc' ? 'var(--accent)' : 'rgba(0,0,0,0.15)' }} />
          <ChevronDown style={{ width: 11, height: 11, marginTop: -3, color: isActive && sortOrder === 'desc' ? 'var(--accent)' : 'rgba(0,0,0,0.15)' }} />
        </div>
      </div>
    </th>
  );
}

/* ═══════════ module-level cache ═══════════ */
let cachedAnalyses: Analysis[] = [];

/* ═══════════════════════════════════════════════════════════════
   ANALYSES PAGE
   ═══════════════════════════════════════════════════════════════ */

export function Analyses() {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'kk' ? 'kk-KZ' : i18n.language === 'en' ? 'en-US' : 'ru-RU';

  /* ── data state ── */
  const [analyses, setAnalyses] = useState<Analysis[]>(cachedAnalyses);
  const [loading, setLoading] = useState(cachedAnalyses.length === 0);

  /* ── filters state ── */
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterRiskLevel, setFilterRiskLevel] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  /* ── sort state ── */
  const [sortBy, setSortBy] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  /* ── pagination state ── */
  const [currentPage, setCurrentPage] = useState(1);

  /* ── batch select state ── */
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);

  /* ── confirm-dialog state ── */
  // Either null (closed), { kind: 'single', id } (single delete), or { kind: 'batch' } (batch delete)
  const [confirmAction, setConfirmAction] = useState<
    | { kind: 'single'; id: number }
    | { kind: 'batch' }
    | null
  >(null);


  /* ── upload state ── */
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  /* ── background analysis context ── */
  const bgAnalysis = useBackgroundAnalysis();
  const prevAnalyzingRef = useRef(bgAnalysis.isAnalyzing);

  /* ── view analysis state ── */
  const [viewingResult, setViewingResult] = useState<KaspiAnalysisResult | null>(null);
  const [viewingLoading, setViewingLoading] = useState<number | null>(null);

  /* ── select options ── */
  const statusOptions = [
    { value: 'all', label: t('analyses.allStatuses') },
    { value: 'pending', label: t('analyses.pending') },
    { value: 'in_progress', label: t('analyses.inProgress') },
    { value: 'completed', label: t('analyses.completed') },
    { value: 'failed', label: t('analyses.failed') || 'Failed' },
  ];

  const riskLevelOptions = [
    { value: 'all', label: t('analyses.allRiskLevels') || 'All Risks' },
    { value: 'low', label: t('dashboard.lowRisk') },
    { value: 'medium', label: t('dashboard.mediumRisk') },
    { value: 'high', label: t('dashboard.highRiskLevel') },
  ];

  /* ═════════��═════════ DATA LOADING ═══════════��═══════ */

  useEffect(() => { loadData(); }, []);

  useEffect(() => {
    if (prevAnalyzingRef.current && !bgAnalysis.isAnalyzing) { loadData(); }
    prevAnalyzingRef.current = bgAnalysis.isAnalyzing;
  }, [bgAnalysis.isAnalyzing]);

  const loadData = async () => {
    try {
      if (cachedAnalyses.length === 0) setLoading(true);
      const data = await analysesAPI.getAll();
      cachedAnalyses = data;
      setAnalyses(data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  /* ═══════════════════ FILTERING + SORTING + PAGINATION ═══════════════════ */

  const filteredAndSorted = useMemo(() => {
    let result = [...analyses];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(a =>
        (a.file_name || '').toLowerCase().includes(q) ||
        (a.account_owner || '').toLowerCase().includes(q) ||
        (a.bank_name || '').toLowerCase().includes(q)
      );
    }
    if (filterStatus !== 'all') {
      if (filterStatus === 'in_progress') {
        result = result.filter(a => a.status === 'in_progress' || a.status === 'parsing' || a.status === 'analyzing');
      } else {
        result = result.filter(a => a.status === filterStatus);
      }
    }
    if (filterRiskLevel !== 'all') {
      result = result.filter(a => {
        const s = a.fraud_composite_score ?? (a.risk_score * 10);
        if (filterRiskLevel === 'low') return s <= 30;
        if (filterRiskLevel === 'medium') return s > 30 && s <= 60;
        return s > 60;
      });
    }
    if (dateFrom) {
      const from = new Date(dateFrom).getTime();
      result = result.filter(a => new Date(a.created_at).getTime() >= from);
    }
    if (dateTo) {
      const to = new Date(dateTo).getTime() + 86400000;
      result = result.filter(a => new Date(a.created_at).getTime() <= to);
    }
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'id': cmp = a.id - b.id; break;
        case 'risk_score': cmp = (a.fraud_composite_score ?? a.risk_score * 10) - (b.fraud_composite_score ?? b.risk_score * 10); break;
        case 'status': cmp = a.status.localeCompare(b.status); break;
        case 'total_transactions': cmp = (a.total_transactions || 0) - (b.total_transactions || 0); break;
        case 'created_at': default: cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime(); break;
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [analyses, searchQuery, filterStatus, filterRiskLevel, dateFrom, dateTo, sortBy, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSorted.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const paginatedAnalyses = filteredAndSorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  useEffect(() => {
    setCurrentPage(1);
    setSelectedIds(new Set());
  }, [searchQuery, filterStatus, filterRiskLevel, dateFrom, dateTo, sortBy, sortOrder]);

  /* ═══════════════════ SORT HANDLER ═══════════════════ */

  const handleSort = useCallback((field: SortField) => {
    if (sortBy === field) setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortOrder('desc'); }
  }, [sortBy]);

  /* ═══════════════════ BATCH SELECT ═══════════════════ */

  const allOnPageSelected = paginatedAnalyses.length > 0 && paginatedAnalyses.every(a => selectedIds.has(a.id));

  const toggleSelectAll = () => {
    if (allOnPageSelected) {
      setSelectedIds(prev => { const n = new Set(prev); paginatedAnalyses.forEach(a => n.delete(a.id)); return n; });
    } else {
      setSelectedIds(prev => { const n = new Set(prev); paginatedAnalyses.forEach(a => n.add(a.id)); return n; });
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };

  // Open confirm dialog — actual delete runs from doBatchDelete after user confirms
  const handleBatchDelete = () => {
    if (selectedIds.size === 0) return;
    setConfirmAction({ kind: 'batch' });
  };

  const doBatchDelete = async () => {
    setBatchDeleting(true);
    try {
      const result = await analysesAPI.batchDelete(Array.from(selectedIds));
      toast.success(t('analyses.batchDeleted', { count: result.deleted }) || `${result.deleted} analyses deleted`);
      if (result.errors?.length) result.errors.forEach((err: string) => toast.error(err));
      setSelectedIds(new Set());
      await loadData();
    } catch (error) {
      console.error('Batch delete failed:', error);
      toast.error(t('common.error') || 'Error');
    } finally {
      setBatchDeleting(false);
      setConfirmAction(null);
    }
  };

  /* ═══════════════════ STATUS / RISK HELPERS ═══════════════════ */

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'completed': return 's-completed';
      case 'in_progress': case 'parsing': case 'analyzing': return 's-progress';
      case 'failed': return 's-failed';
      case 'pending': return 's-pending';
      default: return '';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed': return t('analyses.completed');
      case 'in_progress': case 'parsing': case 'analyzing': return t('analyses.inProgress');
      case 'failed': return t('analyses.failed') || 'Failed';
      case 'pending': return t('analyses.pending');
      default: return status;
    }
  };

  const getRiskColor = (score: number) => score <= 30 ? '#34a853' : score <= 60 ? '#f9ab00' : '#ea4335';
  const getRiskBg = (score: number) => score <= 30 ? 'var(--success)' : score <= 60 ? 'var(--warning)' : 'var(--danger)';
  const getRiskLabel = (score: number) => score <= 30 ? t('dashboard.lowRisk') : score <= 60 ? t('dashboard.mediumRisk') : t('dashboard.highRiskLevel');

  /* ═══════════════════ FILE UPLOAD HANDLERS ═══════════════════ */

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      const validFiles = files.filter(file => {
        const ext = file.name.split('.').pop()?.toLowerCase();
        return ext === 'pdf' || ext === 'csv' || ext === 'xlsx' || ext === 'xls';
      });
      setSelectedFiles(prev => [...prev, ...validFiles]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files) {
      const files = Array.from(e.dataTransfer.files);
      const validFiles = files.filter(file => {
        const ext = file.name.split('.').pop()?.toLowerCase();
        return ext === 'pdf' || ext === 'csv' || ext === 'xlsx' || ext === 'xls';
      });
      setSelectedFiles(prev => [...prev, ...validFiles]);
    }
  };
  const removeFile = (index: number) => setSelectedFiles(prev => prev.filter((_, i) => i !== index));

  const handleAnalyze = () => {
    if (selectedFiles.length === 0) {
      toast.warning(t('analyses.noFilesSelected') || 'Please select files to analyze');
      return;
    }
    const bankFile = selectedFiles.find(f => {
      const ext = f.name.toLowerCase().split('.').pop();
      return ext === 'pdf' || ext === 'xlsx' || ext === 'xls';
    });
    if (bankFile) {
      bgAnalysis.startAnalysis(bankFile, () => { loadData(); });
      setSelectedFiles([]);
    } else {
      (async () => {
        for (const file of selectedFiles) await analysesAPI.uploadFile(file, () => {});
        setSelectedFiles([]);
        await loadData();
        toast.success('Files uploaded');
      })();
    }
  };

  /* ═══════════════════ VIEW / DELETE HANDLERS ═══════════════════ */

  const handleViewAnalysis = async (analysis: Analysis) => {
    if (analysis.status !== 'completed') {
      toast.info(t('analyses.notCompleted') || 'Analysis is not completed yet');
      return;
    }
    setViewingLoading(analysis.id);
    try {
      const [fullAnalysis, txData] = await Promise.all([
        analysesAPI.getById(analysis.id) as Promise<Analysis>,
        analysesAPI
          .getTransactions(analysis.id)
          .catch(() => ({ transactions: [] as any[] })) as Promise<{ transactions?: any[] }>,
      ]);
      const parsedAccount = fullAnalysis?.parsed_account_info || {};
      const rawAnalytics = fullAnalysis?.analytics_result || {};
      const fraudReport = fullAnalysis?.fraud_report || null;
      const analyticsData = rawAnalytics.analytics || rawAnalytics;
      const contactsData = rawAnalytics.contacts || analyticsData.contacts || {};
      const rawTransactions: any[] = Array.isArray(txData?.transactions) ? txData!.transactions! : [];
      const transactions = rawTransactions.map((tx: any) => ({
        date: tx.transaction_date || tx.date || '',
        amount: parseFloat(tx.amount) || 0,
        type: tx.transaction_type || tx.type || '',
        details: tx.description || tx.details || '',
        category: tx.category || '',
        subcategory: tx.subcategory || '',
        currency: tx.currency || 'KZT',
        original_amount: tx.original_amount ? parseFloat(tx.original_amount) : null,
        original_currency: tx.original_currency || null,
      }));
      const reconstructed: KaspiAnalysisResult = {
        meta: {
          generated_at: fullAnalysis.completed_at || fullAnalysis.created_at,
          pdf_file: fullAnalysis.file_name || '',
          parser_version: '2.0',
          original_filename: fullAnalysis.file_name || undefined,
        },
        account: {
          owner: fullAnalysis.account_owner || parsedAccount.owner || 'N/A',
          card: parsedAccount.card || '',
          account_number: fullAnalysis.account_number || parsedAccount.account_number || '',
          currency: fullAnalysis.account_currency || parsedAccount.currency || 'KZT',
          period: parsedAccount.period || { from: null, to: null },
          balance_start: parsedAccount.balance_start || 0,
          balance_end: parsedAccount.balance_end || 0,
        },
        validation: parsedAccount.validation || rawAnalytics.validation || {
          total_transactions: fullAnalysis.total_transactions || 0,
          is_valid: true, expected: {}, actual: {}, differences: {}, errors: [],
        },
        summary: {
          total_transactions: fullAnalysis.total_transactions || 0,
          total_income: fullAnalysis.total_income || analyticsData.total_income || 0,
          total_expense: fullAnalysis.total_expense || analyticsData.total_expense || 0,
          net_flow: (fullAnalysis.total_income || 0) - Math.abs(fullAnalysis.total_expense || 0),
          avg_daily_expense: analyticsData.avg_daily_expense || analyticsData.financial_health?.monthly_avg_expense ? (analyticsData.financial_health.monthly_avg_expense / 30) : 0,
          median_transaction: analyticsData.median_transaction || 0,
        },
        transactions,
        analytics: {
          monthly_breakdown: analyticsData.monthly_breakdown || [],
          category_breakdown: analyticsData.category_breakdown || { expense: [], income: [], total_expense: 0, total_income: 0 },
          top_merchants: analyticsData.top_merchants || [],
          top_contacts: analyticsData.top_contacts || [],
          recurring_payments: analyticsData.recurring_payments || [],
          anomalies: analyticsData.anomalies || [],
          foreign_currency: analyticsData.foreign_currency || { transactions: [], total_foreign_kzt: 0 },
          financial_health: analyticsData.financial_health || {
            savings_rate: 0, essential_expenses: 0, non_essential_expenses: 0,
            essential_ratio: 0, balance_trend: 'stable', monthly_avg_income: 0,
            monthly_avg_expense: 0, financial_buffer_days: 0,
          },
          weekday_analysis: analyticsData.weekday_analysis || [],
          daily_patterns: analyticsData.daily_patterns || [],
        },
        contacts: contactsData,
        fraud_report: fraudReport,
      };
      setViewingResult(reconstructed);
    } catch (error) {
      console.error('Failed to load analysis:', error);
      toast.error(t('common.error') || 'Failed to load analysis details');
    } finally {
      setViewingLoading(null);
    }
  };

  // Opens confirm modal — real delete runs from doDeleteAnalysis
  const handleDeleteAnalysis = (id: number) => {
    setConfirmAction({ kind: 'single', id });
  };

  const doDeleteAnalysis = async (id: number) => {
    try {
      await analysesAPI.delete(id);
      setAnalyses(prev => prev.filter(a => a.id !== id));
      setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
      toast.success(t('analyses.deleted') || 'Analysis deleted');
    } catch (error) {
      console.error('Failed to delete analysis:', error);
      toast.error(t('common.error') || 'Error deleting analysis');
    } finally {
      setConfirmAction(null);
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return <FileType2 style={{ width: 18, height: 18, color: 'var(--danger)' }} />;
    if (ext === 'csv' || ext === 'xlsx' || ext === 'xls') return <Sheet style={{ width: 18, height: 18, color: 'var(--success)' }} />;
    return <File style={{ width: 18, height: 18, color: 'var(--text-muted)' }} />;
  };

  /* ═══════════════════ PAGINATION RENDER ═══════════════════ */

  const renderPagination = () => {
    if (totalPages <= 1) return null;
    const pages: (number | string)[] = [];
    const maxVisible = 5;
    if (totalPages <= maxVisible + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (safePage > 3) pages.push('...');
      const start = Math.max(2, safePage - 1);
      const end = Math.min(totalPages - 1, safePage + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (safePage < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }
    return (
      <div className="flex items-center justify-between" style={{ padding: '14px 20px', borderTop: '1px solid rgba(0,0,0,0.04)' }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          {t('analyses.showingPage') || 'Page'} {safePage} / {totalPages}
          <span style={{ marginLeft: 8, color: 'var(--text-muted)', opacity: 0.7 }}>
            ({t('analyses.totalRecords') || 'Total'}: {filteredAndSorted.length})
          </span>
        </span>
        <div className="flex items-center gap-1">
          {[
            { icon: ChevronsLeft, action: () => setCurrentPage(1), disabled: safePage === 1 },
            { icon: ChevronLeft, action: () => setCurrentPage(p => Math.max(1, p - 1)), disabled: safePage === 1 },
          ].map((btn, i) => (
            <button key={i} onClick={btn.action} disabled={btn.disabled}
              style={{ padding: 6, borderRadius: 8, border: 'none', background: 'none', cursor: btn.disabled ? 'not-allowed' : 'pointer', opacity: btn.disabled ? 0.3 : 1, color: 'var(--text-muted)' }}>
              <btn.icon style={{ width: 16, height: 16 }} />
            </button>
          ))}
          {pages.map((p, i) =>
            typeof p === 'string' ? (
              <span key={`dots-${i}`} style={{ padding: '0 6px', color: 'var(--text-muted)' }}>...</span>
            ) : (
              <button
                key={p} onClick={() => setCurrentPage(p)}
                style={{
                  width: 32, height: 32, borderRadius: 10, fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                  background: p === safePage ? 'var(--accent)' : 'transparent',
                  color: p === safePage ? 'white' : 'var(--text-muted)',
                  boxShadow: p === safePage ? '0 4px 12px var(--accent-glow)' : 'none',
                }}
              >{p}</button>
            )
          )}
          {[
            { icon: ChevronRight, action: () => setCurrentPage(p => Math.min(totalPages, p + 1)), disabled: safePage === totalPages },
            { icon: ChevronsRight, action: () => setCurrentPage(totalPages), disabled: safePage === totalPages },
          ].map((btn, i) => (
            <button key={i} onClick={btn.action} disabled={btn.disabled}
              style={{ padding: 6, borderRadius: 8, border: 'none', background: 'none', cursor: btn.disabled ? 'not-allowed' : 'pointer', opacity: btn.disabled ? 0.3 : 1, color: 'var(--text-muted)' }}>
              <btn.icon style={{ width: 16, height: 16 }} />
            </button>
          ))}
        </div>
      </div>
    );
  };

  /* ═══════════════════ LOADING STATE ═══════════════════ */

  if (loading) {
    return (
      <div className="px-8 pb-8 fade-in">
        <div className="mb-8">
          <div className="h-10 w-64 premium-skeleton rounded-xl mb-3" />
          <div className="h-5 w-80 premium-skeleton rounded-lg" />
        </div>
        <div className="glass-card animate-pulse" style={{ padding: 28 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-4 mb-4">
              <div className="h-5 w-8 premium-skeleton rounded" />
              <div className="h-5 w-40 premium-skeleton rounded" />
              <div className="h-5 w-20 premium-skeleton rounded" />
              <div className="h-5 w-16 premium-skeleton rounded" />
              <div className="h-5 flex-1 premium-skeleton rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ═══════════════════ RENDER ═══════════════════ */

  return (
    <div className="px-8 pb-8 fade-in">
      {/* ═══ Header ═══ */}
      <div className="mb-8">
        <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.03em', lineHeight: 1.2, color: 'var(--text)' }}>
          {t('analyses.title')}
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, marginTop: 6 }}>
          {t('analyses.subtitle')}
        </p>
      </div>

      {/* ═══ Upload Card ═══ */}
      <div className="glass-card mb-8" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Accent gradient bar */}
        <div style={{ height: 3, background: 'var(--accent)' }} />

        <div style={{ padding: '28px 28px 0' }}>
          <div className="flex items-start gap-4 mb-6">
            <div className="upload-orb flex-shrink-0">
              <UploadCloud style={{ width: 28, height: 28, color: 'white' }} />
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>
                {t('analyses.uploadFiles') || 'Upload Bank Statements'}
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 400, lineHeight: 1.6 }}>
                {t('analyses.uploadDescription')}
              </p>
            </div>
          </div>
        </div>

        {/* Drop zone */}
        <div style={{ padding: '0 28px 28px' }}>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`upload-zone ${isDragging ? 'dragging' : ''}`}
            style={{ padding: '36px 24px', textAlign: 'center' }}
          >
            <input type="file" id="file-upload" multiple accept=".pdf,.csv,.xlsx,.xls" onChange={handleFileSelect} className="hidden" />
            <label htmlFor="file-upload" style={{ cursor: 'pointer', display: 'block' }}>
              <UploadCloud style={{
                width: 36, height: 36, margin: '0 auto 12px',
                color: isDragging ? 'var(--accent)' : 'var(--text-muted)',
                transition: 'color 0.2s',
              }} />
              <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                {isDragging ? (t('analyses.dropFiles') || 'Drop files here') : (t('analyses.dragFiles') || 'Drag & drop files here')}
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                {t('analyses.orClickBrowse') || 'or click to browse'}
              </p>
              <div className="flex items-center justify-center gap-2">
                {['PDF', 'CSV', 'XLSX', 'XLS'].map(fmt => (
                  <span key={fmt} className="format-pill">{fmt}</span>
                ))}
              </div>
            </label>
          </div>

          {/* Selected files */}
          {selectedFiles.length > 0 && (
            <div style={{ marginTop: 20 }} className="fade-in">
              <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 12 }}>
                {t('analyses.selectedFiles') || 'Selected Files'} ({selectedFiles.length})
              </h3>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between group"
                    style={{ padding: '10px 14px', borderRadius: 12, background: 'rgba(0,0,0,0.02)', transition: 'background 0.2s' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent-subtle)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.02)')}>
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {getFileIcon(file.name)}
                      <div className="flex-1 min-w-0">
                        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }} className="truncate">{file.name}</p>
                        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{(file.size / 1024).toFixed(2)} KB</p>
                      </div>
                    </div>
                    <button onClick={() => removeFile(index)} style={{ padding: 6, borderRadius: 8, border: 'none', background: 'none', cursor: 'pointer', opacity: 0, transition: 'opacity 0.2s' }}
                      className="group-hover:!opacity-100">
                      <X style={{ width: 14, height: 14, color: '#ea4335' }} />
                    </button>
                  </div>
                ))}
              </div>
              <button onClick={handleAnalyze} disabled={bgAnalysis.isAnalyzing} className="btn-gradient" style={{ width: '100%', marginTop: 16, padding: '14px 24px', justifyContent: 'center' }}>
                {bgAnalysis.isAnalyzing ? (
                  <><Loader2 style={{ width: 18, height: 18, animation: 'spin 1s linear infinite' }} /> {t('analyses.analyzing')}</>
                ) : (
                  <><ScanSearch style={{ width: 18, height: 18 }} /> {t('analyses.startAnalysis')}</>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Background analysis result */}
      {bgAnalysis.result && <BankAnalysisReport result={bgAnalysis.result} onClose={() => bgAnalysis.dismissResult()} />}
      {viewingResult && <BankAnalysisReport result={viewingResult} onClose={() => setViewingResult(null)} />}

      {/* ═══ Filters Bar ═══ */}
      <div className="flex flex-wrap gap-3 mb-6 items-stretch" style={{ position: 'relative', zIndex: 20 }}>
        {/* Search */}
        <div className="flex-1 min-w-[250px] relative group">
          <Search style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', width: 16, height: 16, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder={t('analyses.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="glass-input"
            style={{ width: '100%', paddingLeft: 40, height: '100%' }}
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center glass-card" style={{ padding: 0, borderRadius: 14, overflow: 'visible', minWidth: 170 }}>
          <div style={{ padding: '0 12px', borderRight: '1px solid rgba(0,0,0,0.04)', display: 'flex', alignItems: 'center' }}>
            <ListFilter style={{ width: 14, height: 14, color: 'var(--accent)' }} />
          </div>
          <Select value={filterStatus} onChange={setFilterStatus} options={statusOptions} className="flex-1" noBorder />
        </div>

        {/* Risk filter */}
        <div className="flex items-center glass-card" style={{ padding: 0, borderRadius: 14, overflow: 'visible', minWidth: 160 }}>
          <div style={{ padding: '0 12px', borderRight: '1px solid rgba(0,0,0,0.04)', display: 'flex', alignItems: 'center' }}>
            <ShieldCheck style={{ width: 14, height: 14, color: 'var(--warning)' }} />
          </div>
          <Select value={filterRiskLevel} onChange={setFilterRiskLevel} options={riskLevelOptions} className="flex-1" noBorder />
        </div>

        {/* Date range */}
        <div className="flex items-center glass-card" style={{ padding: 0, borderRadius: 14, overflow: 'visible' }}>
          <div style={{ padding: '0 12px', borderRight: '1px solid rgba(0,0,0,0.04)', display: 'flex', alignItems: 'center' }}>
            <CalendarDays style={{ width: 14, height: 14, color: 'var(--accent)' }} />
          </div>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            style={{ padding: '10px 12px', background: 'transparent', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 13, width: 130, fontFamily: 'inherit' }}
            title={t('analyses.dateFrom') || 'From'} />
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>→</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            style={{ padding: '10px 12px', background: 'transparent', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 13, width: 130, fontFamily: 'inherit' }}
            title={t('analyses.dateTo') || 'To'} />
          {(dateFrom || dateTo) && (
            <button onClick={() => { setDateFrom(''); setDateTo(''); }}
              style={{ padding: '10px', borderLeft: '1px solid rgba(0,0,0,0.04)', border: 'none', background: 'none', cursor: 'pointer' }}>
              <X style={{ width: 12, height: 12, color: 'var(--text-muted)' }} />
            </button>
          )}
        </div>

        {/* Reset */}
        {(searchQuery || filterStatus !== 'all' || filterRiskLevel !== 'all' || dateFrom || dateTo) && (
          <button onClick={() => { setSearchQuery(''); setFilterStatus('all'); setFilterRiskLevel('all'); setDateFrom(''); setDateTo(''); }}
            className="glass-action-btn danger" style={{ padding: '10px 16px' }}>
            <RotateCcw style={{ width: 14, height: 14 }} />
            {t('common.reset') || 'Reset'}
          </button>
        )}
      </div>

      {/* ═══ Analyses Table ═══ */}
      <div className="glass-table" style={{ position: 'relative', zIndex: 10 }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ width: 48, padding: '14px 16px' }}>
                  <input type="checkbox" checked={allOnPageSelected && paginatedAnalyses.length > 0} onChange={toggleSelectAll}
                    style={{ width: 16, height: 16, cursor: 'pointer', accentColor: 'var(--accent)' }} />
                </th>
                <th>{t('analyses.subjectFIO') || 'Subject'}</th>
                <th>{t('analyses.status')}</th>
                <SortableHeader label={t('analyses.riskScore')} field="risk_score" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />
                <SortableHeader label={t('analyses.transactions') || 'Txns'} field="total_transactions" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />
                <SortableHeader label={t('analyses.date') || 'Date'} field="created_at" sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />
                <th>{t('analyses.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {paginatedAnalyses.map((analysis, idx) => {
                const pct = analysis.fraud_composite_score ?? (analysis.risk_score * 10);
                const avaClass = `subj-avatar ava-${(idx % 5) + 1}`;
                return (
                  <tr key={analysis.id} style={{ background: selectedIds.has(analysis.id) ? 'var(--accent-subtle)' : 'transparent' }}>
                    <td style={{ padding: '14px 16px' }}>
                      <input type="checkbox" checked={selectedIds.has(analysis.id)} onChange={() => toggleSelect(analysis.id)}
                        style={{ width: 16, height: 16, cursor: 'pointer', accentColor: 'var(--accent)' }} />
                    </td>
                    {/* Subject */}
                    <td>
                      <div className="flex items-center gap-3">
                        <div className={avaClass}>
                          {(analysis.account_owner || 'N')[0].toUpperCase()}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }} className="truncate" title={analysis.account_owner || ''}>
                            {analysis.account_owner || 'N/A'}
                          </p>
                          {analysis.file_name && (
                            <p style={{ fontSize: 11, color: 'var(--text-muted)' }} className="truncate" title={analysis.file_name}>
                              {analysis.file_name}
                            </p>
                          )}
                          {analysis.bank_name && (
                            <span style={{ display: 'inline-block', marginTop: 2, padding: '1px 6px', fontSize: 10, fontWeight: 600, borderRadius: 6, background: 'var(--accent-subtle)', color: 'var(--accent)' }}>
                              {analysis.bank_name}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    {/* Status */}
                    <td>
                      <span className={`status-pill ${getStatusClass(analysis.status)}`}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block',
                          animation: (analysis.status === 'in_progress' || analysis.status === 'parsing' || analysis.status === 'analyzing') ? 'pulse 1.5s infinite' : 'none' }} />
                        {getStatusLabel(analysis.status)}
                      </span>
                    </td>
                    {/* Risk */}
                    <td>
                      <div className="flex items-center gap-2">
                        <span style={{ fontSize: 13, fontWeight: 700, color: getRiskColor(pct) }}>{pct.toFixed(1)}%</span>
                        <div style={{ width: 50, height: 6, background: 'rgba(0,0,0,0.04)', borderRadius: 6, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(100, pct)}%`, borderRadius: 6, background: getRiskBg(pct), transition: 'width 0.5s' }} />
                        </div>
                      </div>
                      <span style={{ fontSize: 10, fontWeight: 600, color: getRiskColor(pct) }}>
                        {analysis.fraud_risk_level || getRiskLabel(pct)}
                      </span>
                    </td>
                    {/* Transactions */}
                    <td>
                      <div className="flex items-center gap-1.5">
                        <TrendingUp style={{ width: 13, height: 13, color: 'var(--text-muted)' }} />
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                          {analysis.total_transactions ?? '—'}
                        </span>
                      </div>
                    </td>
                    {/* Date */}
                    <td>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {new Date(analysis.created_at.endsWith('Z') ? analysis.created_at : `${analysis.created_at}Z`).toLocaleString(dateLocale, {
                          day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
                        })}
                      </span>
                    </td>
                    {/* Actions */}
                    <td>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleViewAnalysis(analysis)}
                          disabled={viewingLoading === analysis.id}
                          className="glass-action-btn"
                          style={{ padding: '6px 12px' }}
                          aria-label={t('analyses.view') || 'View'}
                        >
                          {viewingLoading === analysis.id ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> : <Eye style={{ width: 14, height: 14 }} />}
                          {t('analyses.view')}
                        </button>
                        <button
                          onClick={() => handleDeleteAnalysis(analysis.id)}
                          className="glass-action-btn danger"
                          style={{ padding: '6px 12px' }}
                          aria-label={t('analyses.delete') || 'Delete'}
                          title={t('analyses.delete') || 'Delete'}
                        >
                          <Trash2 style={{ width: 14, height: 14 }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filteredAndSorted.length === 0 && (
            <EmptyState
              icon={Inbox}
              title={analyses.length === 0 ? (t('analyses.noAnalyses') || 'No analyses') : (t('analyses.noResults') || 'Nothing found')}
              description={analyses.length === 0 ? (t('analyses.noAnalysesDesc') || 'Upload a bank statement file') : (t('analyses.noResultsDesc') || 'Try changing search parameters')}
            />
          )}
        </div>
        {renderPagination()}
      </div>

      {/* ═══ Floating Batch Action Bar ═══ */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 40 }}
            style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 50 }}
          >
            <div className="flex items-center gap-4"
              style={{
                padding: '12px 24px',
                backdropFilter: 'blur(24px)',
                background: 'rgba(9,9,11,0.95)',
                borderRadius: 18,
                boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
                border: '1px solid rgba(255,255,255,0.1)',
              }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'white' }}>
                {t('analyses.selected') || 'Selected'}: <span style={{ color: '#60a5fa', fontWeight: 700 }}>{selectedIds.size}</span>
              </span>
              <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.15)' }} />
              <button onClick={handleBatchDelete} disabled={batchDeleting}
                style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: 'var(--danger)', border: 'none', borderRadius: 12, color: 'white', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: batchDeleting ? 0.5 : 1, fontFamily: 'inherit' }}>
                {batchDeleting ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> : <Trash2 style={{ width: 14, height: 14 }} />}
                {t('analyses.deleteSelected') || 'Delete'}
              </button>
              <button onClick={() => setSelectedIds(new Set())}
                style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '8px 12px', background: 'none', border: 'none', borderRadius: 12, color: 'rgba(255,255,255,0.7)', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                <X style={{ width: 14, height: 14 }} /> {t('common.cancel')}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirm dialog — replaces native confirm() for both batch and single delete */}
      <ConfirmModal
        isOpen={confirmAction !== null}
        loading={batchDeleting}
        title={
          confirmAction?.kind === 'batch'
            ? t('analyses.confirmBatchDelete') || `Delete ${selectedIds.size} selected analyses?`
            : t('analyses.confirmDelete') || 'Delete this analysis record?'
        }
        confirmLabel={t('common.confirmDelete') || 'Delete'}
        cancelLabel={t('common.cancel')}
        onCancel={() => !batchDeleting && setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction?.kind === 'batch') {
            void doBatchDelete();
          } else if (confirmAction?.kind === 'single') {
            void doDeleteAnalysis(confirmAction.id);
          }
        }}
      />
    </div>
  );
}
