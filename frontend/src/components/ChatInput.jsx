import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Sparkles, Send } from 'lucide-react';
import apiClient from '../api/client';

/**
 * ChatInput — top-bar conversational prompt bar.
 * Calls POST /finance/chat and hands the raw ChatResponse (QUERY / ADD / EDIT /
 * DELETE / CONFIRM_NEEDED) back to the parent via onResult for routing.
 *
 * Exposes a `resend(message, confirmId)` method via ref so a
 * DisambiguationPanel can re-fire the same prompt with a `confirm_id` once
 * the user picks one of several ambiguous candidates, reusing this
 * component's request/loading/error handling instead of duplicating it.
 */
const ChatInput = forwardRef(function ChatInput({ onResult }, ref) {
  const [message, setMessage] = useState('');
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

  async function sendChat(text, confirmId) {
    setLoading(true);
    try {
      const payload = confirmId != null ? { message: text, confirm_id: confirmId } : { message: text };
      const { data } = await apiClient.post('/finance/chat', payload);
      onResult({ type: 'success', ...data, query: text });
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errMessage = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : (detail || 'Something went wrong. Please try again.');
      onResult({ type: 'error', message: errMessage, query: text });
      return false;
    } finally {
      setLoading(false);
    }
  }

  useImperativeHandle(ref, () => ({
    resend: (text, confirmId) => sendChat(text, confirmId),
  }));

  async function handleSubmit(e) {
    e.preventDefault();
    if (!message.trim() || loading) return;
    const text = message.trim();
    const ok = await sendChat(text);
    if (ok) setMessage('');
  }

  return (
    <form className="query-bar" onSubmit={handleSubmit}>
      <span className="query-bar-icon"><Sparkles size={15} /></span>
      <input
        ref={inputRef}
        id="chat-input"
        type="text"
        className="query-bar-input"
        placeholder='Try: "Add ₹500 Zomato dinner" or "What did I spend last week?"'
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        disabled={loading}
      />
      <button
        id="chat-submit"
        type="submit"
        className="query-bar-btn"
        disabled={!message.trim() || loading}
        title="Send"
      >
        {loading
          ? <span className="spinner" style={{ width: 13, height: 13, borderWidth: 1.5 }} />
          : <Send size={13} />
        }
      </button>
    </form>
  );
});

export default ChatInput;
