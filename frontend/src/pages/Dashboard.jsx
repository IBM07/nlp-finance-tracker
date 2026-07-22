import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import MetricsCards from '../components/MetricsCards';
import RecentActivityTable from '../components/RecentActivityTable';
import AddTransactionModal from '../components/AddTransactionModal';
import apiClient from '../api/client';
import { useToast } from '../context/ToastContext';
import { useDataRefresh } from '../context/DataRefreshContext';
import { formatCurrency, formatTrend } from '../utils/format';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts';

const COLORS = ['#4F46E5', '#818CF8', '#A5B4FC', '#C7D2FE', '#6366F1', '#3730A3'];

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const { pushToast } = useToast();
  const { refreshToken } = useDataRefresh();

  const [recent, setRecent]       = useState([]);
  const [analytics, setAnalytics] = useState([]);
  const [summary, setSummary]     = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [editingEntry, setEditingEntry] = useState(null);

  // Only the very first load shows the full-page spinner. Refetches
  // triggered by refreshToken (a chat mutation elsewhere, or the local
  // handlers below) swap data in silently — no spinner flicker on every
  // mutation, which was the worst UX bug in the previous implementation.
  const fetchData = useCallback(async () => {
    try {
      const [recentRes, analyticsRes, summaryRes] = await Promise.all([
        apiClient.get('/finance/recent'),
        apiClient.get('/finance/analytics'),
        apiClient.get('/finance/summary'),
      ]);
      setRecent(recentRes.data.data ?? []);
      setAnalytics(analyticsRes.data.data ?? []);
      setSummary(summaryRes.data.data ?? null);
    } catch (err) {
      console.error('Dashboard data fetch error:', err);
    } finally {
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData, refreshToken]);

  // One-time notice on a fresh login. Login.jsx sets justLoggedIn in
  // router state; we clear it via replace so a page refresh or revisiting
  // the dashboard later doesn't repeat it. The noticeShownRef guard keeps
  // it to a single toast even under StrictMode's double-invoked effects.
  const noticeShownRef = useRef(false);
  useEffect(() => {
    if (location.state?.justLoggedIn && !noticeShownRef.current) {
      noticeShownRef.current = true;
      pushToast({
        kind: 'warning',
        message:
          '⚠ Please use this application in light mode — some UI/UX fixes are still pending for dark mode.',
      });
      navigate(location.pathname, { replace: true, state: {} });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleInlineEdit(row) {
    setEditingEntry(row);
  }

  function handleEditSuccess() {
    setEditingEntry(null);
    fetchData();
  }

  // Manual inline delete: nothing is committed yet, so the Undo window can
  // genuinely cancel the write — the DELETE call only fires once the toast
  // expires untouched.
  function handleInlineDelete(row) {
    setRecent((prev) => prev.filter((r) => r.id !== row.id));
    pushToast({
      message: `✦ Deleted "${row.item}" · ${formatCurrency(row.amount)}`,
      undoable: true,
      onUndo: () => {
        setRecent((prev) => [row, ...prev]);
      },
      onExpire: async () => {
        await apiClient.delete(`/finance/entries/${row.id}`);
        fetchData(); // resync KPI cards, not just the row list
      },
    });
  }

  const revenue        = summary?.revenue ?? { value: 0, change_pct: null };
  const expenses       = summary?.expenses ?? { value: 0, change_pct: null };
  const netProfitData  = summary?.net_profit ?? { value: 0, change_pct: null };
  const savingsData    = summary?.savings_rate ?? { value: 0, change_pts: null };

  const metrics = [
    { label: 'Total Revenue',    value: `$${Number(revenue.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,      ...formatTrend(revenue.change_pct) },
    { label: 'Monthly Expenses', value: `$${Number(expenses.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,     ...formatTrend(expenses.change_pct) },
    { label: 'Net Profit',       value: `$${Number(netProfitData.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, ...formatTrend(netProfitData.change_pct) },
    { label: 'Savings Rate',     value: `${savingsData.value}%`,                                                                 ...formatTrend(savingsData.change_pts, ' pts') },
  ];

  const chartData = analytics.map(a => ({
    name: a.category,
    amount: Math.abs(parseFloat(a.total)),
  }));

  if (initialLoading) {
    return (
      <div className="flex-center" style={{ height: 320 }}>
        <span className="spinner spinner-dark" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
    );
  }

  return (
    <>
      <AddTransactionModal
        open={Boolean(editingEntry)}
        editEntry={editingEntry}
        onClose={() => setEditingEntry(null)}
        onSuccess={handleEditSuccess}
      />

      <div className="page-title">Dashboard</div>
      <p className="page-sub">Your finances at a glance.</p>

      <MetricsCards metrics={metrics} />

      <div className="dashboard-grid">
        <div className="dashboard-left">
          <RecentActivityTable
            rows={recent}
            onEdit={handleInlineEdit}
            onDelete={handleInlineDelete}
            onViewAll={() => navigate('/transactions')}
          />

          {chartData.length > 0 && (
            <div className="card">
              <div className="chart-title">Spending by Category</div>
              <div className="chart-sub">All-time breakdown from your transactions</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--gray-100)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
                  <Tooltip
                    formatter={(v) => [`$${v.toFixed(2)}`, 'Amount']}
                    contentStyle={{ borderRadius: 8, border: '1px solid var(--gray-200)', fontSize: 13 }}
                  />
                  <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="dashboard-right">
          {chartData.length > 0 && (
            <div className="card">
              <div className="chart-title">Category Split</div>
              <div className="chart-sub">Proportional view</div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="amount"
                    nameKey="name"
                    cx="50%" cy="50%"
                    outerRadius={72}
                    strokeWidth={0}
                  >
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(v) => [`$${v.toFixed(2)}`, 'Spent']}
                    contentStyle={{ borderRadius: 8, border: '1px solid var(--gray-200)', fontSize: 13 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card card-sm">
            <div className="chart-title" style={{ marginBottom: 16 }}>Quick Stats</div>
            {[
              { label: 'Total Entries',   value: summary?.total_entries ?? 0 },
              { label: 'Categories',       value: analytics.length },
              { label: 'Largest Expense',  value: `$${Number(summary?.largest_expense ?? 0).toFixed(2)}` },
            ].map((stat, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: i < 2 ? '1px solid var(--gray-100)' : 'none' }}>
                <span className="text-sm text-muted">{stat.label}</span>
                <span className="text-sm font-bold">{stat.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
