import { useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import { useDataRefresh } from '../context/DataRefreshContext';
import { formatCurrency, formatMonthLabel } from '../utils/format';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts';

const COLORS = ['#4F46E5', '#818CF8', '#A5B4FC', '#C7D2FE', '#6366F1', '#3730A3', '#4C1D95', '#7C3AED', '#A78BFA', '#DDD6FE'];

export default function Analytics() {
  const { refreshToken } = useDataRefresh();
  const [analytics, setAnalytics] = useState([]);
  const [trend, setTrend] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [analyticsRes, trendRes] = await Promise.all([
        apiClient.get('/finance/analytics'),
        apiClient.get('/finance/analytics/trend', { params: { months: 6 } }),
      ]);
      setAnalytics(analyticsRes.data.data ?? []);
      setTrend(trendRes.data.data ?? []);
    } catch (err) {
      console.error('Analytics fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData, refreshToken]);

  const chartData = analytics.map((a) => ({
    name: a.category,
    amount: Math.abs(parseFloat(a.total)),
  }));
  const totalSpend = chartData.reduce((sum, c) => sum + c.amount, 0);
  const sortedChartData = [...chartData].sort((a, b) => b.amount - a.amount);

  const trendData = trend.map((t) => ({
    month: formatMonthLabel(t.month),
    revenue: parseFloat(t.revenue),
    expenses: parseFloat(t.expenses),
  }));
  const hasTrendData = trendData.some((t) => t.revenue > 0 || t.expenses > 0);

  if (loading) {
    return (
      <div className="flex-center" style={{ height: 320 }}>
        <span className="spinner spinner-dark" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
    );
  }

  return (
    <>
      <div className="page-title">Analytics</div>
      <p className="page-sub">Trends and category breakdowns across your transaction history.</p>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="chart-title">Revenue vs. Expenses</div>
        <div className="chart-sub">Last {trendData.length} months</div>
        {!hasTrendData ? (
          <div className="empty-state">
            <div className="empty-state-icon">📈</div>
            <div className="empty-state-title">Not enough data yet</div>
            <div className="empty-state-desc">Add some transactions to see monthly trends.</div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={trendData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--gray-100)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
              <Tooltip
                formatter={(v) => [`$${Number(v).toFixed(2)}`, '']}
                contentStyle={{ borderRadius: 8, border: '1px solid var(--gray-200)', fontSize: 13 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="revenue" name="Revenue" fill="var(--green)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expenses" name="Expenses" fill="var(--red)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-left">
          <div className="card">
            <div className="chart-title">Spending by Category</div>
            <div className="chart-sub">All-time breakdown</div>
            {sortedChartData.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📊</div>
                <div className="empty-state-title">No category data yet</div>
                <div className="empty-state-desc">Add a transaction to see your spending breakdown.</div>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(220, sortedChartData.length * 36)}>
                <BarChart data={sortedChartData} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--gray-100)" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11, fill: 'var(--gray-400)' }} />
                  <Tooltip
                    formatter={(v) => [`$${v.toFixed(2)}`, 'Amount']}
                    contentStyle={{ borderRadius: 8, border: '1px solid var(--gray-200)', fontSize: 13 }}
                  />
                  <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
                    {sortedChartData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="dashboard-right">
          <div className="card">
            <div className="chart-title">Category Split</div>
            <div className="chart-sub">Proportional view</div>
            {sortedChartData.length === 0 ? (
              <p className="text-sm text-muted">No data yet.</p>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={sortedChartData}
                      dataKey="amount"
                      nameKey="name"
                      cx="50%" cy="50%"
                      outerRadius={72}
                      strokeWidth={0}
                    >
                      {sortedChartData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => [`$${v.toFixed(2)}`, 'Spent']}
                      contentStyle={{ borderRadius: 8, border: '1px solid var(--gray-200)', fontSize: 13 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="analytics-legend">
                  {sortedChartData.map((c, i) => (
                    <div key={c.name} className="analytics-legend-row">
                      <span className="analytics-legend-dot" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="analytics-legend-label">{c.name}</span>
                      <span className="analytics-legend-value">{formatCurrency(c.amount)}</span>
                      <span className="text-xs text-muted">
                        {totalSpend > 0 ? Math.round((c.amount / totalSpend) * 100) : 0}%
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
