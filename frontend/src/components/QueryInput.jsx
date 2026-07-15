import { useState, useRef, useEffect } from 'react';
import { Sparkles, Send } from 'lucide-react';
import apiClient from '../api/client';

/**
 * QueryInput — top-bar NL query bar.
 * Calls POST /finance/query and returns results via onResult callback.
 */
export default function QueryInput({ onResult }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  // Cmd/Ctrl+K focuses the input
  useEffect(() => {
    function handler(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    try {
      const { data } = await apiClient.post('/finance/query', { question: query.trim() });
      onResult({ type: 'success', data, query: query.trim() });
      setQuery('');
    } catch (err) {
      const message = err.response?.data?.detail || 'Query failed. Please try again.';
      onResult({ type: 'error', message, query: query.trim() });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="query-bar" onSubmit={handleSubmit}>
      <span className="query-bar-icon"><Sparkles size={15} /></span>
      <input
        ref={inputRef}
        id="query-input"
        type="text"
        className="query-bar-input"
        placeholder='Try: "What were my top 3 expense categories this month?"'
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={loading}
      />
      <button
        id="query-submit"
        type="submit"
        className="query-bar-btn"
        disabled={!query.trim() || loading}
        title="Run query"
      >
        {loading
          ? <span className="spinner" style={{ width: 13, height: 13, borderWidth: 1.5 }} />
          : <Send size={13} />
        }
      </button>
    </form>
  );
}
