import { TrendingUp, TrendingDown } from 'lucide-react';

/**
 * MetricsCards — 4-up KPI strip at the top of Dashboard.
 * `metrics` prop: array of { label, value, trend, trendDir }
 */
export default function MetricsCards({ metrics }) {
  return (
    <div className="metrics-grid">
      {metrics.map((m, i) => (
        <div key={i} className="metric-card">
          <div className="metric-label">{m.label}</div>
          <div className="metric-value">{m.value}</div>
          {m.trend !== undefined && (
            <div className={`metric-trend ${m.trendDir === 'up' ? 'up' : 'down'}`}>
              {m.trendDir === 'up'
                ? <TrendingUp size={13} />
                : <TrendingDown size={13} />
              }
              <span>{m.trend}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
