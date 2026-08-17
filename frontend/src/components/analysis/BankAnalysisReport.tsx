import { useState, useMemo } from 'react';
import { AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Shield, User, Calendar, CreditCard, CheckCircle, AlertTriangle, X,
  TrendingUp, Eye, FileText, Target, Sparkles, Download, Loader2,
} from 'lucide-react';
import { KaspiAnalysisResult, bankAnalysisAPI } from '../../services/api';
import { SectionId, TxSortField, intlLocale } from './report/shared';
import { OverviewSection } from './report/OverviewSection';
import { FinancialSection } from './report/FinancialSection';
import { AntifraudSection } from './report/AntifraudSection';
import { DetailsSection } from './report/DetailsSection';
import { ConclusionsSection } from './report/ConclusionsSection';

interface BankAnalysisReportProps {
  result: KaspiAnalysisResult;
  onClose: () => void;
}

export function BankAnalysisReport({ result, onClose }: BankAnalysisReportProps) {
  const { t, i18n } = useTranslation();
  const [activeSection, setActiveSection] = useState<SectionId>('overview');
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  const [showAllTransactions, setShowAllTransactions] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Transaction filter state (Details section)
  const [txSearch, setTxSearch] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState<'all' | 'income' | 'expense'>('all');
  // Sorting for the transaction table. Default: newest first — an analyst
  // opens a statement to see the most recent activity.
  const [txSort, setTxSort] = useState<{ field: TxSortField; dir: 'asc' | 'desc' }>(
    { field: 'date', dir: 'desc' }
  );

  const toggleTxSort = (field: TxSortField) => {
    setTxSort(prev =>
      prev.field === field
        ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { field, dir: field === 'date' || field === 'amount' ? 'desc' : 'asc' }
    );
  };

  const fraud = result.fraud_report;
  const locale = intlLocale(i18n.language);

  // Locale-aware currency formatter — switches grouping/separators with the language.
  const formatCurrency = useMemo(() => {
    return (value: number): string => {
      const safe = Number.isFinite(value) ? value : 0;
      return new Intl.NumberFormat(locale).format(Math.round(safe)) + ' ₸';
    };
  }, [locale]);

  const SECTION_NAV: { id: SectionId; label: string; icon: any; description: string }[] = [
    { id: 'overview', label: t('analyses.report.nav.overview'), icon: Eye, description: t('analyses.report.nav.overviewDesc') },
    { id: 'financial', label: t('analyses.report.nav.financial'), icon: TrendingUp, description: t('analyses.report.nav.financialDesc') },
    { id: 'antifraud', label: t('analyses.report.nav.antifraud'), icon: Shield, description: t('analyses.report.nav.antifraudDesc') },
    { id: 'details', label: t('analyses.report.nav.details'), icon: FileText, description: t('analyses.report.nav.detailsDesc') },
    { id: 'conclusions', label: t('analyses.report.nav.conclusions'), icon: Target, description: t('analyses.report.nav.conclusionsDesc') },
  ];

  const handleExportPDF = async () => {
    try {
      setPdfLoading(true);
      const blob = await bankAnalysisAPI.exportPDF(result);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const owner = result.account?.owner || 'report';
      const safeName = owner.replace(/[^a-zA-Z0-9\u0400-\u04FF _-]/g, '').trim().slice(0, 30) || 'report';
      link.download = `ntFAST_${safeName}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
      toast.error(t('analyses.exportError'));
    } finally {
      setPdfLoading(false);
    }
  };

  // CSV export \u2014 pure client-side, builds spreadsheet from result.transactions.
  // Uses UTF-8 BOM so Excel correctly displays Cyrillic. Escapes embedded
  // commas/quotes/newlines per RFC 4180.
  const handleExportCSV = () => {
    try {
      const txs = (result.transactions || []) as any[];
      if (txs.length === 0) {
        toast.error(t('analyses.report.transactions.noTransactions') || 'No transactions to export');
        return;
      }
      const escape = (v: any): string => {
        if (v === null || v === undefined) return '';
        const s = String(v);
        // If value contains comma, quote, or newline \u2192 wrap in quotes and double-up inner quotes
        if (/[",\n\r]/.test(s)) {
          return `"${s.replace(/"/g, '""')}"`;
        }
        return s;
      };
      const header = ['Date', 'Type', 'Description', 'Category', 'Subcategory', 'Amount', 'Currency'].join(',');
      const rows = txs.map(tx => [
        tx.date || '',
        tx.type || '',
        tx.details || '',
        tx.category || '',
        tx.subcategory || '',
        tx.amount ?? '',
        tx.currency || 'KZT',
      ].map(escape).join(','));
      // BOM ensures Excel detects UTF-8
      const csv = '\uFEFF' + [header, ...rows].join('\r\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const owner = result.account?.owner || 'report';
      const safeName = owner.replace(/[^a-zA-Z0-9\u0400-\u04FF _-]/g, '').trim().slice(0, 30) || 'report';
      link.download = `ntFAST_${safeName}_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success(t('analyses.exportCsvSuccess') || 'CSV downloaded');
    } catch (err) {
      console.error('CSV export failed:', err);
      toast.error(t('analyses.exportError') || 'Export failed');
    }
  };

  return (
    <div className="mb-8 fade-in">
      <div className="backdrop-blur-xl bg-white/95 dark:bg-gray-900/95 rounded-3xl border border-gray-200/50 dark:border-gray-800/50 shadow-2xl overflow-hidden">

        {/* ===== HEADER WITH ntFAST BRANDING ===== */}
        <div className="relative overflow-hidden">
          {/* Gradient Background — theme-aware: deep navy in light mode, near-black in dark mode */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-black dark:from-zinc-900 dark:via-zinc-900 dark:to-black" />
          {/* Animated pattern */}
          <div className="absolute inset-0 opacity-[0.07]">
            <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '20px 20px' }} />
          </div>
          {/* Glow orbs */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/20 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl" />

          <div className="relative p-8">
            {/* Top row: Logo & Close */}
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="relative">
                  <div className="w-14 h-14 rounded-2xl bg-[#2563eb] flex items-center justify-center shadow-xl shadow-blue-500/20">
                    <Shield className="w-7 h-7 text-white" />
                  </div>
                  <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-slate-900 flex items-center justify-center">
                    <Sparkles className="w-2 h-2 text-white" />
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-2xl font-bold text-white">ntFAST</h1>
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-500/30 text-blue-300 border border-blue-500/30">
                      AI v2.0
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 mt-0.5">{t('analyses.report.subtitle')}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleExportCSV}
                  className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-xl transition-all text-sm font-medium text-white border border-white/10 hover:border-white/20"
                  title={t('analyses.exportCsv') || 'Export CSV'}
                  aria-label={t('analyses.exportCsv') || 'Export CSV'}
                >
                  <FileText className="w-4 h-4" />
                  <span className="hidden sm:inline">CSV</span>
                </button>
                <button
                  onClick={handleExportPDF}
                  disabled={pdfLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 disabled:opacity-50 rounded-xl transition-all text-sm font-medium text-white border border-white/10 hover:border-white/20"
                  title={t('analyses.report.downloadPdf')}
                >
                  {pdfLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  <span className="hidden sm:inline">{pdfLoading ? t('common.generating') : 'PDF'}</span>
                </button>
                <button
                  onClick={onClose}
                  // Кнопка состоит из одной иконки: без метки её не
                  // прочитает ни программа чтения с экрана, ни автотест.
                  aria-label={t('common.close')}
                  className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                >
                  <X className="w-6 h-6 text-white/70 hover:text-white" />
                </button>
              </div>
            </div>

            {/* Account info */}
            <div className="flex flex-wrap items-center gap-6 text-sm text-gray-300">
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-blue-400" />
                <span className="font-medium text-white">{result.account.owner}</span>
              </div>
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-400" />
                <span>{result.account.card}</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-blue-400" />
                <span>{result.account.period?.from || '?'} &mdash; {result.account.period?.to || '?'}</span>
              </div>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span>{result.summary.total_transactions} {t('analyses.report.transactionsSuffix')}</span>
              </div>
              {/* Extraction status: did we read the statement completely?
                  Kept separate from balance reconciliation below — a
                  multi-currency statement can be extracted perfectly and still
                  not reconcile on the KZT leg alone. */}
              {result.validation.is_valid ? (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium" style={{ background: 'rgba(52,168,83,0.2)', color: '#34a853', borderWidth: 1, borderStyle: 'solid', borderColor: 'rgba(52,168,83,0.3)' }}>
                  <CheckCircle className="w-3.5 h-3.5" />
                  {t('analyses.report.verified')}
                </span>
              ) : (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium" style={{ background: 'rgba(217,119,6,0.2)', color: '#f59e0b', borderWidth: 1, borderStyle: 'solid', borderColor: 'rgba(217,119,6,0.3)' }}>
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {t('analyses.report.hasDiscrepancies')}
                </span>
              )}
              {result.validation.balance_reconciled === false && (
                <span
                  className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
                  style={{ background: 'rgba(217,119,6,0.2)', color: '#f59e0b', borderWidth: 1, borderStyle: 'solid', borderColor: 'rgba(217,119,6,0.3)' }}
                  title={result.validation.errors?.join(' ') || undefined}
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  {t('analyses.report.balanceNotReconciled')}
                </span>
              )}
            </div>

            {/* Section Navigation */}
            <div className="flex gap-1.5 mt-6 overflow-x-auto pb-1">
              {SECTION_NAV.map((section) => {
                const Icon = section.icon;
                const isActive = activeSection === section.id;
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap ${
                      isActive
                        ? 'bg-white text-slate-900 shadow-lg shadow-white/20'
                        : 'bg-white/10 text-white/80 hover:bg-white/20 hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {section.label}
                    {section.id === 'antifraud' && fraud && (
                      <span className={`ml-1 w-2 h-2 rounded-full ${
                        fraud.composite_score >= 50 ? 'bg-red-400 animate-pulse' :
                        fraud.composite_score >= 25 ? 'bg-yellow-400' : 'bg-green-400'
                      }`} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ===== CONTENT SECTIONS ===== */}
        <div className="p-8">
          <AnimatePresence mode="wait">
            {/* SECTION 1: OVERVIEW */}
            {activeSection === 'overview' && (
              <OverviewSection
                result={result} fraud={fraud} formatCurrency={formatCurrency}
                setActiveSection={setActiveSection}
              />
            )}

            {/* SECTION 2: FINANCIAL PROFILE */}
            {activeSection === 'financial' && (
              <FinancialSection result={result} formatCurrency={formatCurrency} />
            )}

            {/* SECTION 3: ntFAST ANTIFRAUD */}
            {activeSection === 'antifraud' && (
              <AntifraudSection
                result={result} fraud={fraud} formatCurrency={formatCurrency}
                expandedModule={expandedModule} setExpandedModule={setExpandedModule}
              />
            )}

            {/* SECTION 4: TRANSACTIONS */}
            {activeSection === 'details' && (
              <DetailsSection
                result={result} fraud={fraud} formatCurrency={formatCurrency}
                showAllTransactions={showAllTransactions} setShowAllTransactions={setShowAllTransactions}
                txSearch={txSearch} setTxSearch={setTxSearch}
                txTypeFilter={txTypeFilter} setTxTypeFilter={setTxTypeFilter}
                txSort={txSort} toggleTxSort={toggleTxSort}
              />
            )}

            {/* SECTION 5: CONCLUSIONS */}
            {activeSection === 'conclusions' && (
              <ConclusionsSection result={result} fraud={fraud} />
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
