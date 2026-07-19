import { useState, useEffect, useCallback, useRef } from 'react';
import { Bell, HelpCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import AppShell from '../components/AppShell';
import ChatInput from '../components/ChatInput';
import MetricsCards from '../components/MetricsCards';
import RecentActivityTable from '../components/RecentActivityTable';
import AIActionFeedback from '../components/AIActionFeedback';
import AddTransactionModal from '../components/AddTransactionModal';
import DisambiguationPanel from '../components/DisambiguationPanel';
import apiClient from '../api/client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts';

const COLORS = ['#4F46E5', '#818CF8', '#A5B4FC', '#C7D2FE', '#6366F1', '#3730A3'];

function formatCurrency(n) {
  const value = parseFloat(n);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(isNaN(value) ? 0 : value);
}

// The backend returns entries in two different key shapes depending on the
// code path: create_entry()/update_entry() use {item, category}, while the
// NLP audit snapshot (_entry_snapshot in service.py) uses {purchased,
// categorization}. This normalizes either into one shape for the frontend.
function normalizeEntry(e = {}) {
  const amount = parseFloat(e.amount);
  return {
    id: e.id,
    item: e.item ?? e.purchased ?? '',
    category: e.category ?? e.categorization ?? '',
    amount: isNaN(amount) ? 0 : amount,
    date: e.date,
    payment_type: e.payment_type ?? null,
  };
}

export default function Dashboard() {
  const { user } = useAuth();
  const [recent, setRecent]       = useState([]);
  const [analytics, setAnalytics] = useState([]);
  const [summary, setSummary]     = useState(null);
  const [queryResult, setQueryResult] = useState(null);
  const [loadingData, setLoadingData] = useState(true);
  const [toasts, setToasts] = useState([]);
  const [editingEntry, setEditingEntry] = useState(null);
  const chatInputRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
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
      setLoadingData(false);
    }
  }, []);

  // Called by AppShell when a new entry is created via the modal — refresh data
  function handleNewTransaction() {
    fetchData();
  }

  useEffect(() => { fetchData(); }, [fetchData]);

  function pushToast(toast) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev, { id, kind: 'success', undoable: false, ...toast }]);
  }

  function removeToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  // Routes a ChatResponse (or a request-level error) from ChatInput to the
  // right UI reaction: QUERY renders a result table, ADD/EDIT commit
  // immediately and refresh the dashboard behind an Undo toast, DELETE
  // removes the row optimistically (the backend has already deleted it by
  // the time this fires) behind an Undo toast that re-creates it, and
  // CONFIRM_NEEDED surfaces the ambiguous candidates for the user to narrow
  // down their next prompt (full disambiguation UI lands in Phase C).
  function handleChatResult(result) {
    if (result.type === 'error') {
      setQueryResult({ type: 'error', message: result.message });
      return;
    }

    switch (result.intent) {
      case 'QUERY': {
        setQueryResult({ type: 'success', message: result.message, rows: result.data || [] });
        break;
      }

      case 'ADD': {
        const entry = normalizeEntry(result.data);
        setQueryResult(null);
        fetchData();
        pushToast({
          message: `✦ Added "${entry.item}" · ${formatCurrency(entry.amount)} · ${entry.category}`,
          undoable: true,
          onUndo: async () => {
            try {
              await apiClient.delete(`/finance/entries/${entry.id}`);
              fetchData();
            } catch (err) {
              console.error('Failed to undo add:', err);
              pushToast({
                kind: 'error',
                message: `⚠ Couldn't undo "${entry.item}" — please remove it manually.`,
                undoable: false,
              });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'EDIT': {
        const entry = normalizeEntry(result.data);
        const previous = normalizeEntry(result.previous_state);
        setQueryResult(null);
        fetchData();
        pushToast({
          message: `✦ Updated "${entry.item}" · ${formatCurrency(entry.amount)} · ${entry.category}`,
          undoable: true,
          onUndo: async () => {
            try {
              await apiClient.put(`/finance/entries/${entry.id}`, {
                purchased: previous.item,
                categorization: previous.category,
                amount: previous.amount,
                date: previous.date,
                payment_type: previous.payment_type,
              });
              fetchData();
            } catch (err) {
              console.error('Failed to undo edit:', err);
              pushToast({
                kind: 'error',
                message: `⚠ Couldn't undo the change to "${entry.item}" — please edit it back manually.`,
                undoable: false,
              });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'DELETE': {
        const entry = normalizeEntry(result.data);
        setQueryResult(null);
        setRecent((prev) => prev.filter((r) => r.id !== entry.id));
        pushToast({
          message: `✦ Deleted "${entry.item}" · ${formatCurrency(entry.amount)}`,
          undoable: true,
          onUndo: async () => {
            // The chat DELETE already committed server-side, so "undo" here
            // re-creates the entry rather than cancelling a pending write.
            try {
              await apiClient.post('/finance/entries', {
                purchased: entry.item,
                categorization: entry.category,
                amount: entry.amount,
                date: entry.date,
                payment_type: entry.payment_type,
              });
              fetchData();
            } catch (err) {
              console.error('Failed to restore deleted entry:', err);
              pushToast({
                kind: 'error',
                message: `⚠ Couldn't restore "${entry.item}" — please re-add it manually.`,
                undoable: false,
              });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'CONFIRM_NEEDED': {
        setQueryResult({
          type: 'confirm',
          message: result.message,
          candidates: (result.candidates || []).map(normalizeEntry),
          query: result.query,
        });
        break;
      }

      default:
        break;
    }
  }

  // User picked a candidate in the DisambiguationPanel — re-fire the
  // original prompt with confirm_id set, which resolves server-side as an
  // explicit, unambiguous EDIT/DELETE. Routed back through handleChatResult
  // like any other chat response.
  async function handleConfirmSelect(candidateId) {
    await chatInputRef.current?.resend(queryResult.query, candidateId);
  }

  function handleConfirmCancel() {
    setQueryResult(null);
  }

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
      },
    });
  }

  // Format a percent-change figure from the summary API into a display trend.
  // Returns undefined (not 0) when there's no prior-period baseline to compare
  // against, so MetricsCards omits the badge instead of showing a fake "+0%".
  function formatTrend(changeValue, suffix = '%') {
    if (changeValue === null || changeValue === undefined) return { trend: undefined, trendDir: undefined };
    const rounded = Math.round(changeValue * 10) / 10;
    return {
      trend: `${rounded >= 0 ? '+' : ''}${rounded}${suffix}`,
      trendDir: rounded >= 0 ? 'up' : 'down',
    };
  }

  // Current-calendar-month revenue/expenses/net-profit/savings-rate, each
  // compared against the previous calendar month — computed server-side
  // across the user's full transaction history (not just the 5 most recent).
  const revenue      = summary?.revenue ?? { value: 0, change_pct: null };
  const expenses      = summary?.expenses ?? { value: 0, change_pct: null };
  const netProfitData = summary?.net_profit ?? { value: 0, change_pct: null };
  const savingsData   = summary?.savings_rate ?? { value: 0, change_pts: null };

  const metrics = [
    { label: 'Total Revenue',    value: `$${Number(revenue.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,      ...formatTrend(revenue.change_pct) },
    { label: 'Monthly Expenses', value: `$${Number(expenses.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`,     ...formatTrend(expenses.change_pct) },
    { label: 'Net Profit',       value: `$${Number(netProfitData.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, ...formatTrend(netProfitData.change_pct) },
    { label: 'Savings Rate',     value: `${savingsData.value}%`,                                                                 ...formatTrend(savingsData.change_pts, ' pts') },
  ];

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??';

  // Format analytics for bar chart
  const chartData = analytics.map(a => ({
    name: a.category,
    amount: Math.abs(parseFloat(a.total)),
  }));

  return (
    <AppShell onTransactionAdded={handleNewTransaction}>
      {/* ── Edit-mode modal (inline edit from RecentActivityTable) ── */}
      <AddTransactionModal
        open={Boolean(editingEntry)}
        editEntry={editingEntry}
        onClose={() => setEditingEntry(null)}
        onSuccess={handleEditSuccess}
      />

      {/* ── Undo toasts ── */}
      <div className="toast-container">
        {toasts.map((t) => (
          <AIActionFeedback key={t.id} toast={t} onDone={() => removeToast(t.id)} />
        ))}
      </div>

      {/* ── Top bar ── */}
      <div className="topbar">
        <div className="topbar-query">
          <ChatInput ref={chatInputRef} onResult={handleChatResult} />
        </div>
        <div className="topbar-actions">
          <button id="topbar-notifications" className="topbar-icon-btn" title="Notifications">
            <Bell size={17} />
          </button>
          <button id="topbar-help" className="topbar-icon-btn" title="Help">
            <HelpCircle size={17} />
          </button>
          <div className="topbar-avatar" title={user?.email}>{initials}</div>
        </div>
      </div>

      {/* ── Page body ── */}
      <div className="page-body">
        {loadingData ? (
          <div className="flex-center" style={{ height: 320 }}>
            <span className="spinner spinner-dark" style={{ width: 32, height: 32, borderWidth: 3 }} />
          </div>
        ) : (
          <>
            <MetricsCards metrics={metrics} />

            {/* Chat result panel */}
            {queryResult && (
              <div className="query-result-card" style={{ marginBottom: 24 }}>
                <div className="query-result-label">
                  {queryResult.type === 'success' && '✦ AI Result'}
                  {queryResult.type === 'error' && '⚠ Error'}
                  {queryResult.type === 'confirm' && '⚠ Confirmation Needed'}
                </div>

                {queryResult.type === 'error' && (
                  <p className="query-result-message" style={{ color: 'var(--red)' }}>
                    {queryResult.message}
                  </p>
                )}

                {queryResult.type === 'confirm' && (
                  <DisambiguationPanel
                    message={queryResult.message}
                    candidates={queryResult.candidates}
                    onSelect={handleConfirmSelect}
                    onCancel={handleConfirmCancel}
                  />
                )}

                {queryResult.type === 'success' && (
                  <>
                    <p className="query-result-message">{queryResult.message}</p>
                    {queryResult.rows.length > 0 && (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              {Object.keys(queryResult.rows[0]).map(k => (
                                <th key={k}>{k.toUpperCase()}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {queryResult.rows.map((row, i) => (
                              <tr key={i}>
                                {Object.values(row).map((v, j) => (
                                  <td key={j}>{String(v)}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Main grid */}
            <div className="dashboard-grid">
              <div className="dashboard-left">
                <RecentActivityTable rows={recent} onEdit={handleInlineEdit} onDelete={handleInlineDelete} />

                {/* Spending by Category bar chart */}
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

              {/* Right sidebar */}
              <div className="dashboard-right">
                {/* Pie chart */}
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

                {/* Quick stats card */}
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
        )}
      </div>
    </AppShell>
  );
}
