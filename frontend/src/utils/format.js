export function formatCurrency(n) {
  const value = parseFloat(n);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(isNaN(value) ? 0 : value);
}

export function formatSignedCurrency(n) {
  const value = parseFloat(n);
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', signDisplay: 'always',
  }).format(isNaN(value) ? 0 : value);
}

export function formatDate(dateStr) {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function formatMonthLabel(monthKey) {
  // monthKey: "YYYY-MM"
  const [year, month] = monthKey.split('-');
  const d = new Date(Number(year), Number(month) - 1, 1);
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

// Format a percent-change figure into a display trend. Returns undefined
// (not 0) when there's no prior-period baseline to compare against, so
// MetricsCards omits the badge instead of showing a fake "+0%".
export function formatTrend(changeValue, suffix = '%') {
  if (changeValue === null || changeValue === undefined) return { trend: undefined, trendDir: undefined };
  const rounded = Math.round(changeValue * 10) / 10;
  return {
    trend: `${rounded >= 0 ? '+' : ''}${rounded}${suffix}`,
    trendDir: rounded >= 0 ? 'up' : 'down',
  };
}

// The backend returns entries in two different key shapes depending on the
// code path: create_entry()/update_entry() use {item, category}, while the
// NLP audit snapshot (_entry_snapshot in service.py) uses {purchased,
// categorization}. This normalizes either into one shape for the frontend.
export function normalizeEntry(e = {}) {
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
