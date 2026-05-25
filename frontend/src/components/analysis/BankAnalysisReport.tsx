import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Shield, User, Calendar, CreditCard, CheckCircle, AlertTriangle, X,
  TrendingUp, ArrowUpRight, ArrowDownRight, Activity,
  Network, Layers, ArrowLeftRight, Store, Eye,
  ChevronDown, ChevronRight, Zap, Target, Fingerprint, Clock,
  PieChart as PieChartIcon, FileText, Sparkles, Download, Loader2,
  Moon, Copy, CircleDollarSign, UserX
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis
} from 'recharts';
import { KaspiAnalysisResult, bankAnalysisAPI } from '../../services/api';
import { RiskScoreGauge } from './RiskScoreGauge';
import { ModuleScoreCard } from './ModuleScoreCard';

interface BankAnalysisReportProps {
  result: KaspiAnalysisResult;
  onClose: () => void;
}

type SectionId = 'overview' | 'financial' | 'antifraud' | 'details' | 'conclusions';

// Map i18n language code \u2192 BCP47 locale used by Intl APIs.
function intlLocale(lang: string): string {
  if (lang === 'kk') return 'kk-KZ';
  if (lang === 'en') return 'en-US';
  return 'ru-RU';
}

const CHART_COLORS = ['#1a73e8', '#4285f4', '#f9ab00', '#ea4335', '#0891b2', '#5f6368', '#8ab4f8', '#1557b0'];

export function BankAnalysisReport({ result, onClose }: BankAnalysisReportProps) {
  const { t, i18n } = useTranslation();
  const [activeSection, setActiveSection] = useState<SectionId>('overview');
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  const [showAllTransactions, setShowAllTransactions] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Transaction filter state (Details section)
  const [txSearch, setTxSearch] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState<'all' | 'income' | 'expense'>('all');

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

  // Helper: safely get count from a field that might be array or number
  const safeLen = (val: any): number => {
    if (Array.isArray(val)) return val.length;
    if (typeof val === 'number') return val;
    return 0;
  };

  const getModuleIcon = (name: string) => {
    const iconMap: Record<string, any> = {
      velocity: <Zap className="w-4 h-4" />,
      graph: <Network className="w-4 h-4" />,
      structuring: <Layers className="w-4 h-4" />,
      cross_reference: <ArrowLeftRight className="w-4 h-4" />,
      merchant_risk: <Store className="w-4 h-4" />,
      night_transactions: <Moon className="w-4 h-4" />,
      duplicate_payments: <Copy className="w-4 h-4" />,
      round_amounts: <CircleDollarSign className="w-4 h-4" />,
      profile_mismatch: <UserX className="w-4 h-4" />,
    };
    return iconMap[name] || <Activity className="w-4 h-4" />;
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
              <motion.div
                key="overview"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {/* KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                  {[
                    { label: t('analyses.report.kpi.totalIncome'), value: result.summary.total_income, icon: ArrowUpRight, color: 'green', prefix: '+' },
                    { label: t('analyses.report.kpi.totalExpense'), value: result.summary.total_expense, icon: ArrowDownRight, color: 'red', prefix: '-' },
                    { label: t('analyses.report.kpi.netFlow'), value: result.summary.net_flow, icon: TrendingUp, color: result.summary.net_flow >= 0 ? 'blue' : 'red', prefix: result.summary.net_flow >= 0 ? '+' : '' },
                    { label: t('analyses.report.kpi.avgDailyExpense'), value: result.summary.avg_daily_expense, icon: Activity, color: 'slate', prefix: '' },
                  ].map((kpi) => {
                    const Icon = kpi.icon;
                    const colorMap: Record<string, { bg: string; iconBg: string; text: string; border: string }> = {
                      green: { bg: 'from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20', iconBg: 'bg-green-500', text: 'text-green-700 dark:text-green-300', border: 'border-green-200/50 dark:border-green-800/40' },
                      red: { bg: 'from-red-50 to-red-50 dark:from-red-900/20 dark:to-red-900/20', iconBg: 'bg-red-500', text: 'text-red-700 dark:text-red-300', border: 'border-red-200/50 dark:border-red-800/40' },
                      blue: { bg: 'from-blue-50 to-blue-50 dark:from-blue-900/20 dark:to-blue-900/20', iconBg: 'bg-blue-500', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200/50 dark:border-blue-800/40' },
                      slate: { bg: 'from-slate-50 to-gray-50 dark:from-slate-900/20 dark:to-gray-900/20', iconBg: 'bg-slate-500', text: 'text-slate-700 dark:text-slate-300', border: 'border-slate-200/50 dark:border-slate-800/40' },
                    };
                    const c = colorMap[kpi.color];
                    return (
                      <div
                        key={kpi.label}
                        className={`relative p-5 bg-gradient-to-br ${c.bg} rounded-2xl border ${c.border} group`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{kpi.label}</span>
                          <div className={`p-2 ${c.iconBg} rounded-xl shadow-lg`}>
                            <Icon className="w-4 h-4 text-white" />
                          </div>
                        </div>
                        <p className={`text-2xl font-bold ${c.text}`}>
                          {kpi.prefix}{formatCurrency(Math.abs(kpi.value))}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Account Summary Card */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Balance info */}
                  <div
                    className="p-6 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40"
                  >
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.account.title')}
                    </h3>
                    <div className="space-y-3">
                      {[
                        { label: t('analyses.report.account.owner'), value: result.account.owner },
                        { label: t('analyses.report.account.card'), value: result.account.card },
                        { label: t('analyses.report.account.accountNumber'), value: result.account.account_number || '---' },
                        { label: t('analyses.report.account.balanceStart'), value: formatCurrency(result.account.balance_start || 0) },
                        { label: t('analyses.report.account.balanceEnd'), value: formatCurrency(result.account.balance_end || 0) },
                        { label: t('analyses.report.account.currency'), value: result.account.currency || 'KZT' },
                      ].map((row) => (
                        <div key={row.label} className="flex justify-between items-center py-1.5 border-b border-gray-200/50 dark:border-gray-700/30 last:border-0">
                          <span className="text-sm text-gray-500 dark:text-gray-400">{row.label}</span>
                          <span className="text-sm font-medium text-gray-900 dark:text-white">{row.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Quick risk summary */}
                  {fraud && (
                    <div
                      className="p-6 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/30 rounded-2xl border border-blue-200/50 dark:border-blue-800/40"
                    >
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Shield className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.risk.title')}
                      </h3>
                      <div className="flex items-center gap-6">
                        <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={160} />
                        <div className="flex-1 space-y-2">
                          <p
                            className="text-sm text-gray-600 dark:text-gray-300"
                            dangerouslySetInnerHTML={{ __html: t('analyses.report.risk.description', { count: result.summary.total_transactions }) }}
                          />
                          {fraud.red_flags && fraud.red_flags.length > 0 && (
                            <div className="flex items-center gap-2 mt-3">
                              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                              <span className="text-sm text-red-600 dark:text-red-400 font-medium">
                                {t('analyses.report.risk.redFlagsDetected', { count: fraud.red_flags.length })}
                              </span>
                            </div>
                          )}
                          <button
                            onClick={() => setActiveSection('antifraud')}
                            className="mt-3 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1 transition-colors"
                          >
                            {t('analyses.report.risk.viewDetails')} <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Financial Health */}
                {result.analytics?.financial_health && (
                  <div
                    className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40"
                  >
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Activity className="w-5 h-5 text-emerald-500" />
                      {t('analyses.report.health.title')}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { label: t('analyses.report.health.savingsRate'), value: `${(result.analytics.financial_health.savings_rate * 100).toFixed(1)}%`, color: result.analytics.financial_health.savings_rate > 0.1 ? 'text-green-600' : 'text-red-600' },
                        { label: t('analyses.report.health.balanceTrend'), value: result.analytics.financial_health.balance_trend === 'growing' ? t('analyses.report.health.growing') : result.analytics.financial_health.balance_trend === 'declining' ? t('analyses.report.health.declining') : t('analyses.report.health.stable'), color: result.analytics.financial_health.balance_trend === 'growing' ? 'text-green-600' : result.analytics.financial_health.balance_trend === 'declining' ? 'text-red-600' : 'text-blue-600' },
                        { label: t('analyses.report.health.financialBuffer'), value: `${result.analytics.financial_health.financial_buffer_days} ${t('analyses.report.health.days')}`, color: result.analytics.financial_health.financial_buffer_days > 30 ? 'text-green-600' : 'text-yellow-600' },
                        { label: t('analyses.report.health.essentialRatio'), value: `${(result.analytics.financial_health.essential_ratio * 100).toFixed(0)}%`, color: 'text-gray-700 dark:text-gray-300' },
                      ].map((item) => (
                        <div key={item.label} className="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{item.label}</p>
                          <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* SECTION 2: FINANCIAL PROFILE */}
            {activeSection === 'financial' && (
              <motion.div
                key="financial"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {/* Financial summary KPIs (always shown) */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: t('analyses.report.kpi.totalIncome'), value: result.summary?.total_income || 0, color: 'green' },
                    { label: t('analyses.report.kpi.totalExpense'), value: result.summary?.total_expense || 0, color: 'red' },
                    { label: t('analyses.report.kpi.netFlow'), value: result.summary?.net_flow || 0, color: (result.summary?.net_flow || 0) >= 0 ? 'blue' : 'red' },
                    { label: t('analyses.report.kpi.avgDailyExpenseShort'), value: result.summary?.avg_daily_expense || 0, color: 'slate' },
                  ].map((kpi) => {
                    const colors: Record<string, string> = {
                      green: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border-green-200/50 dark:border-green-800/40',
                      red: 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border-red-200/50 dark:border-red-800/40',
                      blue: 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border-blue-200/50 dark:border-blue-800/40',
                      slate: 'bg-slate-50 dark:bg-slate-900/20 text-slate-700 dark:text-slate-300 border-slate-200/50 dark:border-slate-800/40',
                    };
                    return (
                      <div key={kpi.label} className={`p-4 rounded-xl border ${colors[kpi.color]}`}>
                        <p className="text-xs font-medium opacity-70 mb-1">{kpi.label}</p>
                        <p className="text-xl font-bold">{formatCurrency(Math.abs(kpi.value))}</p>
                      </div>
                    );
                  })}
                </div>

                {/* Monthly breakdown chart */}
                {result.analytics?.monthly_breakdown && result.analytics.monthly_breakdown.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.charts.monthlyDynamics')}
                    </h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={result.analytics.monthly_breakdown}>
                        <defs>
                          <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#34a853" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#34a853" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorExpense" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ea4335" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#ea4335" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.15)', background: 'rgba(255,255,255,0.95)' }}
                          formatter={(value: number, name: string) => [formatCurrency(value), name === 'income' ? t('analyses.report.charts.income') : t('analyses.report.charts.expense')]}
                        />
                        <Area type="monotone" dataKey="income" stroke="#34a853" fill="url(#colorIncome)" strokeWidth={2.5} name="income" />
                        <Area type="monotone" dataKey="expense" stroke="#ea4335" fill="url(#colorExpense)" strokeWidth={2.5} name="expense" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Category breakdown */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Expense categories */}
                  {result.analytics?.category_breakdown?.expense && result.analytics.category_breakdown.expense.length > 0 && (
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <PieChartIcon className="w-5 h-5 text-red-500" />
                        {t('analyses.report.charts.expenseCategories')}
                      </h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={result.analytics.category_breakdown.expense.slice(0, 8)}
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            innerRadius={50}
                            paddingAngle={2}
                            dataKey="amount"
                            nameKey="category"
                          >
                            {result.analytics.category_breakdown.expense.slice(0, 8).map((_, i) => (
                              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                            formatter={(value: number) => [formatCurrency(value)]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-2 mt-2">
                        {result.analytics.category_breakdown.expense.slice(0, 6).map((cat, i) => (
                          <div key={cat.category} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                              <span className="text-gray-600 dark:text-gray-400">{cat.category}</span>
                            </div>
                            <span className="font-medium text-gray-900 dark:text-white">{formatCurrency(cat.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Income categories */}
                  {result.analytics?.category_breakdown?.income && result.analytics.category_breakdown.income.length > 0 && (
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <PieChartIcon className="w-5 h-5 text-green-500" />
                        {t('analyses.report.charts.incomeCategories')}
                      </h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={result.analytics.category_breakdown.income.slice(0, 8)}
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            innerRadius={50}
                            paddingAngle={2}
                            dataKey="amount"
                            nameKey="category"
                          >
                            {result.analytics.category_breakdown.income.slice(0, 8).map((_, i) => (
                              <Cell key={i} fill={CHART_COLORS[(i + 3) % CHART_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                            formatter={(value: number) => [formatCurrency(value)]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-2 mt-2">
                        {result.analytics.category_breakdown.income.slice(0, 6).map((cat, i) => (
                          <div key={cat.category} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS[(i + 3) % CHART_COLORS.length] }} />
                              <span className="text-gray-600 dark:text-gray-400">{cat.category}</span>
                            </div>
                            <span className="font-medium text-gray-900 dark:text-white">{formatCurrency(cat.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Top merchants */}
                {result.analytics?.top_merchants && result.analytics.top_merchants.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Store className="w-5 h-5 text-slate-500" />
                      {t('analyses.report.charts.topMerchants')}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {result.analytics.top_merchants.slice(0, 9).map((merchant, i) => (
                        <div
                          key={merchant.merchant}
                          className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-900/30 flex items-center justify-center flex-shrink-0">
                              <span className="text-sm font-bold text-slate-600 dark:text-slate-400">
                                {i + 1}
                              </span>
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{merchant.merchant}</p>
                              <p className="text-xs text-gray-500">{t('analyses.report.charts.operationsCount', { count: merchant.count })}</p>
                            </div>
                          </div>
                          <span className="text-sm font-semibold text-gray-900 dark:text-white ml-2 flex-shrink-0">
                            {formatCurrency(merchant.amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Weekday analysis */}
                {result.analytics?.weekday_analysis && result.analytics.weekday_analysis.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.charts.weekdayActivity')}
                    </h3>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={result.analytics.weekday_analysis}>
                        <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                          formatter={(value: number) => [formatCurrency(value), t('analyses.report.charts.turnover')]}
                        />
                        <Bar dataKey="amount" fill="#2563eb" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Fallback when no charts/analytics data */}
                {(!result.analytics?.monthly_breakdown || result.analytics.monthly_breakdown.length === 0) &&
                 (!result.analytics?.category_breakdown?.expense || result.analytics.category_breakdown.expense.length === 0) &&
                 (!result.analytics?.top_merchants || result.analytics.top_merchants.length === 0) && (
                  <div className="text-center py-12">
                    <TrendingUp className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.charts.noAnalyticsData')}</p>
                  </div>
                )}
              </motion.div>
            )}

            {/* SECTION 3: ntFAST ANTIFRAUD */}
            {activeSection === 'antifraud' && (
              <motion.div
                key="antifraud"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {fraud ? (
                  <>
                    {/* ntFAST Analysis Pipeline Header */}
                    <div className="text-center mb-2">
                      <div
                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 rounded-full border border-blue-200/50 dark:border-blue-800/40 mb-3"
                      >
                        <Fingerprint className="w-4 h-4 text-blue-500" />
                        <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                          {t('analyses.report.antifraud.pipelineBadge')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">
                        {t('analyses.report.antifraud.pipelineDesc')}
                      </p>
                    </div>

                    {/* Main Risk Score */}
                    <div className="flex flex-col lg:flex-row items-center gap-8 p-8 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={220} />

                      <div className="flex-1 w-full">
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                          {t('analyses.report.antifraud.resultTitle')}
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                          {t('analyses.report.antifraud.resultDesc')}
                        </p>

                        {/* Radar chart of modules */}
                        <ResponsiveContainer width="100%" height={220}>
                          <RadarChart data={[
                            { module: t('analyses.report.modules.velocity.short'), score: fraud.velocity.risk_score },
                            { module: t('analyses.report.modules.graph.short'), score: fraud.graph.risk_score },
                            { module: t('analyses.report.modules.structuring.short'), score: fraud.structuring.risk_score },
                            { module: t('analyses.report.modules.crossReference.short'), score: fraud.cross_reference.risk_score },
                            { module: t('analyses.report.modules.merchantRisk.short'), score: fraud.merchant_risk.risk_score },
                            ...(fraud.night_transactions ? [{ module: t('analyses.report.modules.nightTransactions.short'), score: fraud.night_transactions.risk_score }] : []),
                            ...(fraud.duplicate_payments ? [{ module: t('analyses.report.modules.duplicatePayments.short'), score: fraud.duplicate_payments.risk_score }] : []),
                            ...(fraud.round_amounts ? [{ module: t('analyses.report.modules.roundAmounts.short'), score: fraud.round_amounts.risk_score }] : []),
                            ...(fraud.profile_mismatch ? [{ module: t('analyses.report.modules.profileMismatch.short'), score: fraud.profile_mismatch.risk_score }] : []),
                          ]}>
                            <PolarGrid strokeDasharray="3 3" className="text-gray-300 dark:text-gray-600" />
                            <PolarAngleAxis dataKey="module" tick={{ fontSize: 11, fill: '#6b7280' }} />
                            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                            <Radar name="Risk Score" dataKey="score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.25} strokeWidth={2} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Module Score Cards Grid */}
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Layers className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.antifraud.modulesTitle')}
                        <span className="text-xs text-gray-400 font-normal ml-2">{t('analyses.report.antifraud.clickForDetails')}</span>
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                          { key: 'velocity', name: t('analyses.report.modules.velocity.name'), score: fraud.velocity.risk_score, detail: `${fraud.velocity.burst_alerts.length} / ${fraud.velocity.daily_spikes.length}` },
                          { key: 'graph', name: t('analyses.report.modules.graph.name'), score: fraud.graph.risk_score, detail: `${fraud.graph.node_count} / ${fraud.graph.cycles.length}` },
                          { key: 'structuring', name: t('analyses.report.modules.structuring.name'), score: fraud.structuring.risk_score, detail: `${fraud.structuring.just_under_threshold.length} / ${fraud.structuring.split_groups.length}` },
                          { key: 'cross_reference', name: t('analyses.report.modules.crossReference.name'), score: fraud.cross_reference.risk_score, detail: `Ratio: ${fraud.cross_reference.income_expense_ratio?.toFixed(2)} / ${fraud.cross_reference.rapid_pass_through.length}` },
                          { key: 'merchant_risk', name: t('analyses.report.modules.merchantRisk.name'), score: fraud.merchant_risk.risk_score, detail: `${fraud.merchant_risk.high_risk_merchants.length} / ${fraud.merchant_risk.medium_risk_merchants.length}` },
                          ...(fraud.night_transactions ? [{ key: 'night_transactions', name: t('analyses.report.modules.nightTransactions.name'), score: fraud.night_transactions.risk_score, detail: `${fraud.night_transactions.night_count} / ${(fraud.night_transactions.night_ratio * 100).toFixed(1)}%` }] : []),
                          ...(fraud.duplicate_payments ? [{ key: 'duplicate_payments', name: t('analyses.report.modules.duplicatePayments.name'), score: fraud.duplicate_payments.risk_score, detail: `${fraud.duplicate_payments.total_duplicates}` }] : []),
                          ...(fraud.round_amounts ? [{ key: 'round_amounts', name: t('analyses.report.modules.roundAmounts.name'), score: fraud.round_amounts.risk_score, detail: `${fraud.round_amounts.round_count} / ${(fraud.round_amounts.round_ratio * 100).toFixed(1)}%` }] : []),
                          ...(fraud.profile_mismatch ? [{ key: 'profile_mismatch', name: t('analyses.report.modules.profileMismatch.name'), score: fraud.profile_mismatch.risk_score, detail: `${safeLen(fraud.profile_mismatch.mismatches)}` }] : []),
                        ].map((mod, i) => (
                          <ModuleScoreCard
                            key={mod.key}
                            name={mod.name}
                            score={mod.score}
                            detail={mod.detail}
                            icon={getModuleIcon(mod.key)}
                            index={i}
                            onClick={() => setExpandedModule(expandedModule === mod.key ? null : mod.key)}
                            isExpanded={expandedModule === mod.key}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Expanded Module Details */}
                    <AnimatePresence>
                      {expandedModule && (
                        <motion.div
                          key={`detail-${expandedModule}`}
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.4 }}
                          className="overflow-hidden"
                        >
                          {/* Velocity */}
                          {expandedModule === 'velocity' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Zap className="w-5 h-5 text-amber-500" />
                                  {t('analyses.report.modules.velocity.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.velocity.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {fraud.velocity.burst_alerts.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-orange-600 dark:text-orange-400 mb-2 flex items-center gap-1.5">
                                      <Zap className="w-3.5 h-3.5" />
                                      {t('analyses.report.modules.velocity.burstAlerts', { count: fraud.velocity.burst_alerts.length })}
                                    </h5>
                                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                                      {fraud.velocity.burst_alerts.map((burst, i) => (
                                        <div
                                          key={i}
                                          className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl text-sm border border-orange-200/50 dark:border-orange-800/30"
                                        >
                                          <div className="flex justify-between items-center">
                                            <span className="font-semibold text-orange-700 dark:text-orange-300">{burst.transaction_count} {t('analyses.report.transactionsSuffix')}</span>
                                            <span className="text-xs text-gray-500">{burst.window_hours}h</span>
                                          </div>
                                          <div className="text-gray-600 dark:text-gray-400 mt-1">
                                            Сумма: {formatCurrency(burst.total_amount)}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.velocity.daily_spikes.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2 flex items-center gap-1.5">
                                      <Activity className="w-3.5 h-3.5" />
                                      {t('analyses.report.modules.velocity.dailySpikes', { count: fraud.velocity.daily_spikes.length })}
                                    </h5>
                                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                                      {fraud.velocity.daily_spikes.map((spike, i) => (
                                        <div
                                          key={i}
                                          className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-sm border border-red-200/50 dark:border-red-800/30"
                                        >
                                          <div className="flex justify-between items-center">
                                            <span className="font-semibold text-red-700 dark:text-red-300">{spike.date}</span>
                                            <span className="text-xs bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 px-2 py-0.5 rounded-full font-medium">
                                              Z-score: {spike.z_score.toFixed(1)}
                                            </span>
                                          </div>
                                          <div className="text-gray-600 dark:text-gray-400 mt-1">
                                            {spike.transaction_count} операций &bull; {formatCurrency(spike.total_amount)}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {fraud.velocity.burst_alerts.length === 0 && fraud.velocity.daily_spikes.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.velocity.noAnomalies')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Graph */}
                          {expandedModule === 'graph' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Network className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.graph.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.graph.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-3 gap-4 mb-4">
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.graph.node_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.nodes')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.graph.edge_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.edges')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{fraud.graph.cycles.length}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.cycles')}</p>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {fraud.graph.cycles.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">{t('analyses.report.modules.graph.circular')}</h5>
                                    <div className="space-y-2 max-h-48 overflow-y-auto">
                                      {fraud.graph.cycles.slice(0, 10).map((cycle, i) => (
                                        <div key={i} className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-xs border border-red-200/50 dark:border-red-800/30">
                                          <div className="font-medium text-red-700 dark:text-red-300 truncate">
                                            {cycle.nodes.join(' \u2192 ')}
                                          </div>
                                          <div className="text-red-500 mt-1">{formatCurrency(cycle.total_flow)}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.graph.hub_nodes.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">{t('analyses.report.modules.graph.hubs')}</h5>
                                    <div className="space-y-2 max-h-48 overflow-y-auto">
                                      {fraud.graph.hub_nodes.slice(0, 10).map((hub, i) => (
                                        <div key={i} className="p-3 bg-slate-50 dark:bg-slate-900/20 rounded-xl text-xs border border-slate-200/50 dark:border-slate-800/30 flex justify-between items-center">
                                          <div>
                                            <span className="font-medium text-slate-700 dark:text-slate-300">{hub.name}</span>
                                            <span className="text-gray-400 ml-1">({t('analyses.report.modules.graph.connections', { count: hub.connections })})</span>
                                          </div>
                                          <span className="text-slate-600 font-medium">{formatCurrency(hub.total_volume)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Structuring */}
                          {expandedModule === 'structuring' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Layers className="w-5 h-5 text-amber-500" />
                                  {t('analyses.report.modules.structuring.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.structuring.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {fraud.structuring.just_under_threshold.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-amber-600 dark:text-amber-400 mb-2">
                                      {t('analyses.report.modules.structuring.underThreshold', { count: fraud.structuring.just_under_threshold.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.just_under_threshold.slice(0, 8).map((item, i) => (
                                        <div key={i} className="text-xs p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200/50 dark:border-amber-800/30">
                                          <span className="font-medium">{formatCurrency(item.amount)}</span>
                                          <span className="text-gray-500 ml-1">({t('analyses.report.modules.structuring.ofThreshold', { pct: item.pct_of_threshold })})</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.structuring.split_groups.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">
                                      {t('analyses.report.modules.structuring.splitting', { count: fraud.structuring.split_groups.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.split_groups.map((group, i) => (
                                        <div key={i} className="text-xs p-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200/50 dark:border-red-800/30">
                                          <div className="font-medium text-red-700 dark:text-red-300 truncate">{group.counterparty}</div>
                                          <div className="text-gray-500">{group.transaction_count} op = {formatCurrency(group.total_amount)}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.structuring.smurfing_patterns.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                      {t('analyses.report.modules.structuring.smurfing', { count: fraud.structuring.smurfing_patterns.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.smurfing_patterns.map((p, i) => (
                                        <div key={i} className="text-xs p-2 bg-slate-50 dark:bg-slate-900/20 rounded-lg border border-slate-200/50 dark:border-slate-800/30">
                                          <div className="font-medium">{formatCurrency(p.amount)} x{p.occurrence_count}</div>
                                          <div className="text-gray-500">{t('analyses.report.modules.structuring.recipients', { count: p.unique_counterparties })}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {fraud.structuring.just_under_threshold.length === 0 && fraud.structuring.split_groups.length === 0 && fraud.structuring.smurfing_patterns.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.structuring.noPatterns')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Cross Reference */}
                          {expandedModule === 'cross_reference' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <ArrowLeftRight className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.crossReference.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.crossReference.desc')}
                                </p>
                              </div>
                              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl mb-4">
                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                  {t('analyses.report.modules.crossReference.ratio')}: <span className="font-bold text-blue-600 dark:text-blue-400">{fraud.cross_reference.income_expense_ratio?.toFixed(2)}</span>
                                </p>
                              </div>
                              {fraud.cross_reference.rapid_pass_through.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-semibold text-orange-600 dark:text-orange-400 mb-2">
                                    {t('analyses.report.modules.crossReference.rapidPassThrough', { count: fraud.cross_reference.rapid_pass_through.length })}
                                  </h5>
                                  <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {fraud.cross_reference.rapid_pass_through.map((pt, i) => (
                                      <div
                                        key={i}
                                        className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl text-sm border border-orange-200/50 dark:border-orange-800/30"
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="text-green-600 font-semibold">+{formatCurrency(pt.income_amount)}</span>
                                          <div className="flex items-center gap-1 text-gray-400 text-xs">
                                            <Clock className="w-3 h-3" />
                                            {pt.time_gap_hours}h
                                          </div>
                                          <span className="text-red-600 font-semibold">-{formatCurrency(pt.expense_amount)}</span>
                                        </div>
                                        <div className="text-xs text-gray-500 mt-1 truncate">
                                          {pt.income_source} \u2192 {pt.expense_dest}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {fraud.cross_reference.rapid_pass_through.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.crossReference.noTransits')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Merchant Risk */}
                          {expandedModule === 'merchant_risk' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Store className="w-5 h-5 text-red-500" />
                                  {t('analyses.report.modules.merchantRisk.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.merchantRisk.desc')}
                                </p>
                              </div>
                              <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl mb-2">
                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                  {t('analyses.report.modules.merchantRisk.highRiskShare', { pct: fraud.merchant_risk.total_high_risk_pct.toFixed(1), amount: formatCurrency(fraud.merchant_risk.total_high_risk_amount) })}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {fraud.merchant_risk.high_risk_merchants.length > 0 && (
                                  <div>
                                    <h5 className="text-xs font-bold text-red-500 uppercase mb-2">{t('analyses.report.modules.merchantRisk.highRisk')}</h5>
                                    <div className="space-y-2">
                                      {fraud.merchant_risk.high_risk_merchants.map((m, i) => (
                                        <div key={i} className="flex justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-xs border border-red-200/50 dark:border-red-800/30">
                                          <div>
                                            <span className="font-medium text-red-700 dark:text-red-300">{m.name}</span>
                                            <span className="text-gray-400 ml-1">({m.category})</span>
                                          </div>
                                          <div className="text-right">
                                            <span className="font-medium">{formatCurrency(m.amount)}</span>
                                            <span className="text-gray-400 ml-1">x{m.count}</span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.merchant_risk.medium_risk_merchants.length > 0 && (
                                  <div>
                                    <h5 className="text-xs font-bold text-yellow-500 uppercase mb-2">{t('analyses.report.modules.merchantRisk.mediumRisk')}</h5>
                                    <div className="space-y-2">
                                      {fraud.merchant_risk.medium_risk_merchants.map((m, i) => (
                                        <div key={i} className="flex justify-between p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-xs border border-yellow-200/50 dark:border-yellow-800/30">
                                          <div>
                                            <span className="font-medium text-yellow-700 dark:text-yellow-300">{m.name}</span>
                                            <span className="text-gray-400 ml-1">({m.category})</span>
                                          </div>
                                          <div className="text-right">
                                            <span className="font-medium">{formatCurrency(m.amount)}</span>
                                            <span className="text-gray-400 ml-1">x{m.count}</span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {fraud.merchant_risk.high_risk_merchants.length === 0 && fraud.merchant_risk.medium_risk_merchants.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.merchantRisk.noRisky')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Night Transactions */}
                          {expandedModule === 'night_transactions' && fraud.night_transactions && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Moon className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.nightTransactions.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.nightTransactions.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.night_transactions.night_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightCount')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{(fraud.night_transactions.night_ratio * 100).toFixed(1)}%</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightRatio')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(fraud.night_transactions.night_total_amount)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightAmount')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.night_transactions.large_night_transfers)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.largeNight')}</p>
                                </div>
                              </div>
                              {safeLen(fraud.night_transactions.night_clusters) > 0 && (
                                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl">
                                  <p className="text-sm text-amber-700 dark:text-amber-300">
                                    <AlertTriangle className="w-4 h-4 inline mr-1" />
                                    {t('analyses.report.modules.nightTransactions.clustersWarn', { count: safeLen(fraud.night_transactions.night_clusters) })}
                                  </p>
                                </div>
                              )}
                              {fraud.night_transactions.night_count === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.nightTransactions.noNight')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Duplicate Payments */}
                          {expandedModule === 'duplicate_payments' && fraud.duplicate_payments && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Copy className="w-5 h-5 text-orange-500" />
                                  {t('analyses.report.modules.duplicatePayments.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.duplicatePayments.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-3 gap-4 mb-4">
                                <div className="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{fraud.duplicate_payments.total_duplicates}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.totalDuplicates')}</p>
                                </div>
                                <div className="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{safeLen(fraud.duplicate_payments.duplicate_groups)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.groups')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.duplicate_payments.same_amount_diff_recipient)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.fanOut')}</p>
                                </div>
                              </div>
                              {fraud.duplicate_payments.total_duplicate_amount > 0 && (
                                <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                                  <p className="text-sm text-gray-600 dark:text-gray-300">
                                    {t('analyses.report.modules.duplicatePayments.totalAmount')}: <span className="font-bold text-orange-600 dark:text-orange-400">{formatCurrency(fraud.duplicate_payments.total_duplicate_amount)}</span>
                                  </p>
                                </div>
                              )}
                              {fraud.duplicate_payments.total_duplicates === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.duplicatePayments.noDuplicates')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Round Amounts */}
                          {expandedModule === 'round_amounts' && fraud.round_amounts && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <CircleDollarSign className="w-5 h-5 text-emerald-500" />
                                  {t('analyses.report.modules.roundAmounts.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.roundAmounts.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{fraud.round_amounts.round_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundCount')}</p>
                                </div>
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{(fraud.round_amounts.round_ratio * 100).toFixed(1)}%</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundRatio')}</p>
                                </div>
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(fraud.round_amounts.round_total_amount)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundAmount')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.round_amounts.consecutive_round)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.consecutive')}</p>
                                </div>
                              </div>
                              {fraud.round_amounts.round_count === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.roundAmounts.noRound')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Profile Mismatch */}
                          {expandedModule === 'profile_mismatch' && fraud.profile_mismatch && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <UserX className="w-5 h-5 text-red-500" />
                                  {t('analyses.report.modules.profileMismatch.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.profileMismatch.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.mismatches)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.mismatches')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.oversized_transactions)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.oversized')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.unexpected_activity)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.unexpected')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.income_anomalies)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.incomeAnomalies')}</p>
                                </div>
                              </div>
                              {safeLen(fraud.profile_mismatch.mismatches) === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.profileMismatch.noMismatches')}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </>
                ) : (
                  <div className="text-center py-16">
                    <Shield className="w-16 h-16 text-gray-300 dark:text-gray-700 mx-auto mb-4" />
                    <p className="text-gray-500 dark:text-gray-400 text-lg">{t('analyses.report.antifraud.noData')}</p>
                    <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
                      {t('analyses.report.antifraud.noDataDesc')}
                    </p>
                  </div>
                )}
              </motion.div>
            )}

            {/* SECTION 4: TRANSACTIONS */}
            {activeSection === 'details' && (
              <motion.div
                key="details"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                {/* Account profile info (from fraud engine) */}
                {fraud?.account_profile && (
                  <div className="p-5 bg-gradient-to-br from-blue-50 to-blue-50 dark:from-blue-900/20 dark:to-blue-900/20 rounded-2xl border border-blue-200/50 dark:border-blue-800/40">
                    <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
                      <Fingerprint className="w-4 h-4" />
                      {t('analyses.report.accountProfile.title')}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.type')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white capitalize">
                          {fraud.account_profile.account_type?.replace('_', ' ') || t('analyses.report.accountProfile.unknown')}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.avgIncome')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {formatCurrency(fraud.account_profile.avg_monthly_income || 0)}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.avgExpense')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {formatCurrency(fraud.account_profile.avg_monthly_expense || 0)}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.regularity')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {((fraud.account_profile.income_regularity_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between flex-wrap gap-3">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    {t('analyses.report.transactions.all', { count: result.transactions?.length || 0 })}
                  </h3>
                  {/* Search + type filter */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <input
                      type="text"
                      value={txSearch}
                      onChange={(e) => setTxSearch(e.target.value)}
                      placeholder={t('analyses.report.transactions.searchPlaceholder') || 'Search by description / category…'}
                      aria-label={t('analyses.report.transactions.searchPlaceholder') || 'Search transactions'}
                      className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400"
                      style={{ minWidth: 220 }}
                    />
                    <select
                      value={txTypeFilter}
                      onChange={(e) => setTxTypeFilter(e.target.value as 'all' | 'income' | 'expense')}
                      aria-label={t('analyses.report.transactions.typeFilter') || 'Type filter'}
                      className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    >
                      <option value="all">{t('analyses.report.transactions.typeAll') || 'All'}</option>
                      <option value="income">{t('analyses.report.charts.income') || 'Income'}</option>
                      <option value="expense">{t('analyses.report.charts.expense') || 'Expense'}</option>
                    </select>
                    {(txSearch || txTypeFilter !== 'all') && (
                      <button
                        onClick={() => { setTxSearch(''); setTxTypeFilter('all'); }}
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline px-2"
                      >
                        {t('common.reset') || 'Reset'}
                      </button>
                    )}
                  </div>
                </div>

                {result.transactions && result.transactions.length > 0 ? (() => {
                  // Apply search + type filter
                  const needle = txSearch.trim().toLowerCase();
                  const filtered = result.transactions.filter((tx: any) => {
                    if (txTypeFilter === 'income' && tx.amount < 0) return false;
                    if (txTypeFilter === 'expense' && tx.amount >= 0) return false;
                    if (!needle) return true;
                    const desc = String(tx.details || '').toLowerCase();
                    const cat = String(tx.category || '').toLowerCase();
                    return desc.includes(needle) || cat.includes(needle);
                  });
                  const visibleSlice = showAllTransactions ? filtered : filtered.slice(0, 50);
                  return (
                <div className="overflow-hidden rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                  {/* Result count + Show all toggle */}
                  <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200/50 dark:border-gray-700/40 text-xs text-gray-500 dark:text-gray-400">
                    <span>
                      {filtered.length === result.transactions.length
                        ? `${filtered.length}`
                        : `${filtered.length} / ${result.transactions.length}`}
                    </span>
                    {filtered.length > 50 && (
                      <button
                        onClick={() => setShowAllTransactions(!showAllTransactions)}
                        className="text-blue-600 dark:text-blue-400 font-medium hover:text-blue-700 flex items-center gap-1"
                      >
                        {showAllTransactions ? t('analyses.report.transactions.showFirst50') : t('analyses.report.transactions.showAll')}
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAllTransactions ? 'rotate-180' : ''}`} />
                      </button>
                    )}
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800/80 sticky top-0 z-10">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">#</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">{t('analyses.report.transactions.dateCol')}</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">{t('analyses.report.transactions.descriptionCol')}</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">{t('analyses.report.transactions.categoryCol')}</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">{t('analyses.report.transactions.amountCol')}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800/50">
                        {visibleSlice.map((tx: any, i: number) => (
                          <tr
                            key={i}
                            className="hover:bg-gray-50/80 dark:hover:bg-gray-800/30 transition-colors"
                          >
                            <td className="px-4 py-3 text-gray-400 text-xs">{i + 1}</td>
                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                              {new Date(tx.date).toLocaleDateString(locale)}
                            </td>
                            <td className="px-4 py-3 text-gray-900 dark:text-white max-w-xs truncate">
                              {tx.details}
                            </td>
                            <td className="px-4 py-3">
                              <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400">
                                {tx.category}
                              </span>
                            </td>
                            <td className={`px-4 py-3 text-right font-semibold whitespace-nowrap ${
                              tx.amount >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                            }`}>
                              {tx.amount >= 0 ? '+' : ''}{formatCurrency(tx.amount)}
                            </td>
                          </tr>
                        ))}
                        {visibleSlice.length === 0 && (
                          <tr>
                            <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                              {t('analyses.report.transactions.noMatch') || 'No transactions match the filter'}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                  );
                })() : (
                  <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/30 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <FileText className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.transactions.noTransactions')}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{t('analyses.report.transactions.infoInAntifraud')}</p>
                  </div>
                )}

                {/* Anomalies */}
                {result.analytics?.anomalies && result.analytics.anomalies.length > 0 && (
                  <div className="p-6 bg-yellow-50 dark:bg-yellow-900/20 rounded-2xl border border-yellow-200/50 dark:border-yellow-800/40">
                    <h3 className="text-lg font-semibold text-yellow-700 dark:text-yellow-400 mb-3 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5" />
                      {t('analyses.report.transactions.anomalies', { count: result.analytics.anomalies.length })}
                    </h3>
                    <div className="space-y-2">
                      {result.analytics.anomalies.map((anomaly, i) => (
                        <div key={i} className="p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl text-sm flex items-start gap-3 border border-yellow-200/50 dark:border-yellow-800/30">
                          <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <span className="font-medium text-gray-900 dark:text-white">{anomaly.type}</span>
                            {anomaly.date && <span className="text-gray-500 ml-2">{anomaly.date}</span>}
                            {anomaly.amount && <span className="text-gray-500 ml-2">{formatCurrency(anomaly.amount)}</span>}
                            {anomaly.details && <p className="text-xs text-gray-500 mt-0.5">{anomaly.details}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* SECTION 5: CONCLUSIONS */}
            {activeSection === 'conclusions' && (
              <motion.div
                key="conclusions"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {fraud ? (
                  <>
                    {/* Final verdict */}
                    <div
                      className="p-8 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 text-center"
                    >
                      <div className="flex justify-center mb-4">
                        <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={180} />
                      </div>
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                        {t('analyses.report.conclusions.title')}
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                        {t('analyses.report.conclusions.summary', {
                          count: result.summary.total_transactions,
                          period: `${result.account.period?.from ? t('analyses.report.conclusions.periodFrom', { from: result.account.period.from }) : ''}${result.account.period?.to ? t('analyses.report.conclusions.periodTo', { to: result.account.period.to }) : ''}`,
                        })} <span className="font-bold">
                          {t(`analyses.report.conclusions.riskLevels.${fraud.risk_level}`)}
                        </span> ({fraud.composite_score.toFixed(1)}/100).
                      </p>
                    </div>

                    {/* Analysis summary - what was found step by step */}
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Fingerprint className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.conclusions.stages')}
                      </h3>
                      <div className="space-y-3">
                        {[
                          {
                            step: 1, name: 'Velocity-анализ', score: fraud.velocity.risk_score,
                            desc: fraud.velocity.burst_alerts.length > 0 || fraud.velocity.daily_spikes.length > 0
                              ? `Обнаружено ${fraud.velocity.burst_alerts.length} серий быстрых транзакций (burst) и ${fraud.velocity.daily_spikes.length} дней с аномальной активностью (Z-score > 2.5). ${fraud.velocity.amount_acceleration?.length > 0 ? `Крупные оттоки за 24ч: ${fraud.velocity.amount_acceleration.length} случаев.` : ''} ${fraud.velocity.counterparty_churn?.high_churn_days > 0 ? `Высокая частота новых контрагентов: ${fraud.velocity.counterparty_churn.high_churn_days} дней.` : ''}`
                              : 'Серий быстрых транзакций и аномальных дней не обнаружено. Частота операций в пределах нормы.'
                          },
                          {
                            step: 2, name: 'Сетевой/Графовый анализ', score: fraud.graph.risk_score,
                            desc: fraud.graph.node_count > 0
                              ? `Построен граф: ${fraud.graph.node_count} контрагентов, ${fraud.graph.edge_count} связей. ${fraud.graph.cycles.length > 0 ? `⚠️ Обнаружено ${fraud.graph.cycles.length} круговых переводов (round-tripping).` : 'Круговых переводов не обнаружено.'} ${fraud.graph.hub_nodes?.length > 0 ? `Ключевые хабы: ${fraud.graph.hub_nodes.slice(0, 3).map((h: any) => h.name).join(', ')}.` : ''}`
                              : 'Граф контрагентов пуст — нет данных о контрагентах для сетевого анализа.'
                          },
                          {
                            step: 3, name: 'Структурирование (AML)', score: fraud.structuring.risk_score,
                            desc: (fraud.structuring.just_under_threshold.length > 0 || fraud.structuring.split_groups.length > 0 || fraud.structuring.smurfing_patterns.length > 0)
                              ? `${fraud.structuring.just_under_threshold.length > 0 ? `${fraud.structuring.just_under_threshold.length} сумм близких к порогу 1M KZT (90-99%).` : ''} ${fraud.structuring.split_groups.length > 0 ? `${fraud.structuring.split_groups.length} случаев дробления суммы одному получателю.` : ''} ${fraud.structuring.smurfing_patterns.length > 0 ? `${fraud.structuring.smurfing_patterns.length} паттернов smurfing (одна сумма → разные получатели).` : ''}`.trim()
                              : 'Признаков структурирования (дробления для обхода порогов) не обнаружено.'
                          },
                          {
                            step: 4, name: 'Транзитные переводы доходов/расходов', score: fraud.cross_reference.risk_score,
                            desc: `Соотношение доходов к расходам: ${fraud.cross_reference.income_expense_ratio?.toFixed(2) || 'N/A'}. ${fraud.cross_reference.rapid_pass_through.length > 0 ? `⚠️ ${fraud.cross_reference.rapid_pass_through.length} транзитных операций (приход → быстрый отток похожей суммы за 48ч).` : 'Транзитных операций (pass-through) не обнаружено.'}`
                          },
                          {
                            step: 5, name: 'Рисковые мерчанты', score: fraud.merchant_risk.risk_score,
                            desc: (fraud.merchant_risk.high_risk_merchants.length > 0 || fraud.merchant_risk.medium_risk_merchants?.length > 0)
                              ? `${fraud.merchant_risk.high_risk_merchants.length > 0 ? `Высокий риск: ${fraud.merchant_risk.high_risk_merchants.map((m: any) => `${m.name} (${m.category})`).join(', ')} — ${fraud.merchant_risk.total_high_risk_pct.toFixed(1)}% расходов.` : ''} ${fraud.merchant_risk.medium_risk_merchants?.length > 0 ? `Средний риск: ${fraud.merchant_risk.medium_risk_merchants.slice(0, 3).map((m: any) => `${m.name} (${m.category})`).join(', ')}.` : ''}`.trim()
                              : 'Операций с высокорисковыми мерчантами (гемблинг, крипто, ломбарды) не обнаружено.'
                          },
                          ...(fraud.night_transactions ? [{
                            step: 6, name: 'Ночные транзакции (23:00-06:00)', score: fraud.night_transactions.risk_score,
                            desc: fraud.night_transactions.no_time_data
                              ? 'Анализ пропущен — в выписке отсутствует информация о времени транзакций (только даты).'
                              : fraud.night_transactions.night_count > 0
                                ? `${fraud.night_transactions.night_count} ночных операций (${(fraud.night_transactions.night_ratio * 100).toFixed(1)}% от всех). ${fraud.night_transactions.large_night_transfers?.length > 0 ? `Крупных ночных переводов (>50K): ${fraud.night_transactions.large_night_transfers.length}.` : ''} ${fraud.night_transactions.night_clusters?.length > 0 ? `Серий ночных транзакций: ${fraud.night_transactions.night_clusters.length}.` : ''}`
                                : 'Подозрительных ночных операций не обнаружено.'
                          }] : []),
                          ...(fraud.duplicate_payments ? [{
                            step: 7, name: 'Дублирующие платежи', score: fraud.duplicate_payments.risk_score,
                            desc: fraud.duplicate_payments.total_duplicates > 0
                              ? `${fraud.duplicate_payments.total_duplicates} дубликатов в ${safeLen(fraud.duplicate_payments.duplicate_groups)} группах. ${fraud.duplicate_payments.total_duplicate_amount > 0 ? `Общая сумма дублей: ${Math.round(fraud.duplicate_payments.total_duplicate_amount).toLocaleString('ru-RU')} KZT.` : ''} ${fraud.duplicate_payments.same_amount_diff_recipient?.length > 0 ? `⚠️ ${fraud.duplicate_payments.same_amount_diff_recipient.length} случаев веерной отправки одной суммы разным получателям.` : ''}`
                              : 'Повторных/дублирующих платежей одному получателю не обнаружено.'
                          }] : []),
                          ...(fraud.round_amounts ? [{
                            step: 8, name: 'Круглые суммы', score: fraud.round_amounts.risk_score,
                            desc: fraud.round_amounts.round_count > 0
                              ? `${fraud.round_amounts.round_count} круглых исходящих переводов (${(fraud.round_amounts.round_ratio * 100).toFixed(1)}% от исходящих). ${fraud.round_amounts.consecutive_round?.length > 0 ? `Серии круглых сумм подряд: ${fraud.round_amounts.consecutive_round.length}.` : ''} ${fraud.round_amounts.round_total_amount > 0 ? `Общая сумма: ${Math.round(fraud.round_amounts.round_total_amount).toLocaleString('ru-RU')} KZT.` : ''}`
                              : 'Подозрительных паттернов круглых сумм в исходящих переводах не обнаружено.'
                          }] : []),
                          ...(fraud.profile_mismatch ? [{
                            step: 9, name: 'Профиль клиента', score: fraud.profile_mismatch.risk_score,
                            desc: (safeLen(fraud.profile_mismatch.mismatches) > 0)
                              ? `${safeLen(fraud.profile_mismatch.oversized_transactions)} транзакций превышают норму для профиля. ${safeLen(fraud.profile_mismatch.unexpected_activity)} случаев нехарактерной активности. ${safeLen(fraud.profile_mismatch.income_anomalies)} аномальных поступлений.`
                              : 'Активность соответствует определённому профилю клиента. Отклонений не обнаружено.'
                          }] : []),
                        ].map((item, i, arr) => {
                          const scoreColor = item.score >= 50 ? 'text-red-500 bg-red-50 dark:bg-red-900/20' : item.score >= 25 ? 'text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' : 'text-green-500 bg-green-50 dark:bg-green-900/20';
                          const lineColor = item.score >= 50 ? 'bg-red-400' : item.score >= 25 ? 'bg-yellow-400' : 'bg-green-400';
                          return (
                            <div
                              key={item.step}
                              className="flex items-start gap-4"
                            >
                              {/* Step number with connecting line */}
                              <div className="flex flex-col items-center">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${scoreColor}`}>
                                  {item.step}
                                </div>
                                {i < arr.length - 1 && <div className={`w-0.5 h-8 ${lineColor} opacity-30`} />}
                              </div>
                              <div className="flex-1 pb-2">
                                <div className="flex items-center justify-between">
                                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">{item.name}</h4>
                                  <span className={`text-xs font-bold ${item.score >= 50 ? 'text-red-500' : item.score >= 25 ? 'text-yellow-500' : 'text-green-500'}`}>
                                    {item.score.toFixed(0)}/100
                                  </span>
                                </div>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.desc}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Red Flags */}
                    {fraud.red_flags && fraud.red_flags.length > 0 && (
                      <div
                        className="p-6 bg-red-50 dark:bg-red-900/20 rounded-2xl border border-red-200/50 dark:border-red-800/40"
                      >
                        <h3 className="text-lg font-semibold text-red-700 dark:text-red-400 mb-4 flex items-center gap-2">
                          <AlertTriangle className="w-5 h-5" />
                          {t('analyses.report.conclusions.redFlags', { count: fraud.red_flags.length })}
                        </h3>
                        <div className="space-y-2">
                          {fraud.red_flags.map((flag, i) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl border border-red-200/30 dark:border-red-800/20"
                            >
                              <div className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center flex-shrink-0">
                                <span className="text-xs font-bold text-red-600 dark:text-red-400">{i + 1}</span>
                              </div>
                              <span className="text-sm text-gray-700 dark:text-gray-300">{flag}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {fraud.recommendations && fraud.recommendations.length > 0 && (
                      <div
                        className="p-6 bg-blue-50 dark:bg-blue-900/20 rounded-2xl border border-blue-200/50 dark:border-blue-800/40"
                      >
                        <h3 className="text-lg font-semibold text-blue-700 dark:text-blue-400 mb-4 flex items-center gap-2">
                          <Sparkles className="w-5 h-5" />
                          {t('analyses.report.conclusions.recommendations', { count: fraud.recommendations.length })}
                        </h3>
                        <div className="space-y-2">
                          {fraud.recommendations.map((rec, i) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl border border-blue-200/30 dark:border-blue-800/20"
                            >
                              <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
                                <CheckCircle className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                              </div>
                              <span className="text-sm text-gray-700 dark:text-gray-300">{rec}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* ntFAST Footer */}
                    <div
                      className="text-center py-6 border-t border-gray-200/50 dark:border-gray-700/30"
                    >
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-400 dark:text-gray-500">
                        <Shield className="w-4 h-4" />
                        <span>{t('analyses.report.conclusions.reportGenerated')} <span className="font-semibold text-blue-500">ntFAST AI v2.0</span></span>
                      </div>
                      <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">
                        {t('analyses.report.subtitle')} &bull; {new Date().toLocaleString(locale)}
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-16">
                    <Target className="w-16 h-16 text-gray-300 dark:text-gray-700 mx-auto mb-4" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.conclusions.noConclusions')}</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
