import { useState, useEffect, useCallback } from 'react';
import { Bell, HelpCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import AppShell from '../components/AppShell';
import QueryInput from '../components/QueryInput';
import MetricsCards from '../components/MetricsCards';
import RecentActivityTable from '../components/RecentActivityTable';
import apiClient from '../api/client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts';

const COLORS = ['#4F46E5', '#818CF8', '#A5B4FC', '#C7D2FE', '#6366F1', '#3730A3'];

export default function Dashboard() {
  const { user } = useAuth();
  const [recent, setRecent]       = useState([]);
  const [analytics, setAnalytics] = useState([]);
  const [queryResult, setQueryResult] = useState(null);
  const [loadingData, setLoadingData] = useState(true);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      const [recentRes, analyticsRes] = await Promise.all([
        apiClient.get('/finance/recent'),
        apiClient.get('/finance/analytics'),
      ]);
      setRecent(recentRes.data.data ?? []);
      setAnalytics(analyticsRes.data.data ?? []);
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

  // Compute KPI metrics from analytics + recent data
  const totalRevenue  = recent.filter(r => parseFloat(r.amount) > 0).reduce((s, r) => s + parseFloat(r.amount), 0);
  const totalExpenses = recent.filter(r => parseFloat(r.amount) < 0).reduce((s, r) => s + Math.abs(parseFloat(r.amount)), 0);
  const netProfit     = totalRevenue - totalExpenses;
  const savingsRate   = totalRevenue > 0 ? Math.round((netProfit / totalRevenue) * 100) : 0;

  const metrics = [
    { label: 'Total Revenue',     value: `$${totalRevenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,  trend: '+12%', trendDir: 'up' },
    { label: 'Monthly Expenses',  value: `$${totalExpenses.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, trend: '-5%',  trendDir: 'down' },
    { label: 'Net Profit',        value: `$${netProfit.toLocaleString('en-US', { minimumFractionDigits: 2 })}`,     trend: '+8%',  trendDir: 'up' },
    { label: 'Savings Rate',      value: `${savingsRate}%`,                                                          trend: '+2%',  trendDir: 'up' },
  ];

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : '??';

  // Format analytics for bar chart
  const chartData = analytics.map(a => ({
    name: a.category,
    amount: Math.abs(parseFloat(a.total)),
  }));

  function handleQueryResult(result) {
    setQueryResult(result);
  }

  return (
    <AppShell onTransactionAdded={handleNewTransaction}>
      {/* ── Top bar ── */}
      <div className="topbar">
        <div className="topbar-query">
          <QueryInput onResult={handleQueryResult} />
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

            {/* Query result panel */}
            {queryResult && (
              <div className={`query-result-card`} style={{ marginBottom: 24 }}>
                <div className="query-result-label">
                  {queryResult.type === 'success' ? '✦ AI Result' : '⚠ Query Error'}
                </div>
                {queryResult.type === 'success' ? (
                  <>
                    <p className="query-result-message">{queryResult.data.message}</p>
                    {queryResult.data.sql && (
                      <div className="query-result-sql">{queryResult.data.sql}</div>
                    )}
                    {queryResult.data.data && queryResult.data.data.length > 0 && (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              {Object.keys(queryResult.data.data[0]).map(k => (
                                <th key={k}>{k.toUpperCase()}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {queryResult.data.data.map((row, i) => (
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
                ) : (
                  <p className="query-result-message" style={{ color: 'var(--red)' }}>
                    {queryResult.message}
                  </p>
                )}
              </div>
            )}

            {/* Main grid */}
            <div className="dashboard-grid">
              <div className="dashboard-left">
                <RecentActivityTable rows={recent} />

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
                    { label: 'Total Entries',   value: recent.length },
                    { label: 'Categories',       value: analytics.length },
                    { label: 'Largest Expense',  value: recent.length ? `$${Math.max(...recent.filter(r => parseFloat(r.amount) < 0).map(r => Math.abs(parseFloat(r.amount))), 0).toFixed(2)}` : '$0.00' },
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
