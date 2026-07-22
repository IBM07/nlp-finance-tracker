import { createContext, useContext, useState, useCallback } from 'react';
import apiClient from '../api/client';
import { useToast } from './ToastContext';
import { useDataRefresh } from './DataRefreshContext';
import { normalizeEntry, formatCurrency } from '../utils/format';

// ─────────────────────────────────────────────────────────
//  ChatContext — owns the conversation transcript for the AI
//  assistant. Lives above the router (in AppShell) so the history
//  survives navigating between Dashboard / Transactions / Analytics
//  instead of resetting on every page mount.
//
//  Each transcript entry: { id, prompt, status: 'pending'|'done'|'error',
//    kind: 'query'|'mutation'|'confirm'|'cancelled', message, rows?,
//    candidates?, query? }
//
//  Mutations (ADD/EDIT/DELETE) push an Undo toast via ToastContext and
//  signal other pages to refetch via DataRefreshContext — the transcript
//  itself only ever renders a short confirmation line for those, never
//  raw request/response payloads.
// ─────────────────────────────────────────────────────────

const ChatContext = createContext(null);

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function extractErrorMessage(err) {
  const detail = err.response?.data?.detail;
  return Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : (detail || 'Something went wrong. Please try again.');
}

export function ChatProvider({ children }) {
  const [transcript, setTranscript] = useState([]);
  const [loading, setLoading] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const { pushToast } = useToast();
  const { bumpRefresh } = useDataRefresh();

  const openPanel = useCallback(() => setPanelOpen(true), []);
  const closePanel = useCallback(() => setPanelOpen(false), []);
  const togglePanel = useCallback(() => setPanelOpen((v) => !v), []);

  const updateEntry = useCallback((id, patch) => {
    setTranscript((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const routeResponse = useCallback((entryId, data, promptText) => {
    switch (data.intent) {
      case 'QUERY': {
        updateEntry(entryId, { status: 'done', kind: 'query', message: data.message, rows: data.data || [] });
        break;
      }

      case 'ADD': {
        const entry = normalizeEntry(data.data);
        updateEntry(entryId, { status: 'done', kind: 'mutation', message: data.message });
        bumpRefresh();
        pushToast({
          message: `✦ Added "${entry.item}" · ${formatCurrency(entry.amount)} · ${entry.category}`,
          undoable: true,
          onUndo: async () => {
            try {
              await apiClient.delete(`/finance/entries/${entry.id}`);
              bumpRefresh();
            } catch {
              pushToast({ kind: 'error', message: `⚠ Couldn't undo "${entry.item}" — please remove it manually.`, undoable: false });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'EDIT': {
        const entry = normalizeEntry(data.data);
        const previous = normalizeEntry(data.previous_state);
        updateEntry(entryId, { status: 'done', kind: 'mutation', message: `Updated "${entry.item}"` });
        bumpRefresh();
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
              bumpRefresh();
            } catch {
              pushToast({ kind: 'error', message: `⚠ Couldn't undo the change to "${entry.item}" — please edit it back manually.`, undoable: false });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'DELETE': {
        const entry = normalizeEntry(data.data);
        updateEntry(entryId, { status: 'done', kind: 'mutation', message: `Deleted "${entry.item}"` });
        bumpRefresh();
        pushToast({
          message: `✦ Deleted "${entry.item}" · ${formatCurrency(entry.amount)}`,
          undoable: true,
          onUndo: async () => {
            try {
              await apiClient.post('/finance/entries', {
                purchased: entry.item,
                categorization: entry.category,
                amount: entry.amount,
                date: entry.date,
                payment_type: entry.payment_type,
              });
              bumpRefresh();
            } catch {
              pushToast({ kind: 'error', message: `⚠ Couldn't restore "${entry.item}" — please re-add it manually.`, undoable: false });
            }
          },
          onExpire: () => {},
        });
        break;
      }

      case 'CONFIRM_NEEDED': {
        updateEntry(entryId, {
          status: 'done',
          kind: 'confirm',
          message: data.message,
          candidates: (data.candidates || []).map(normalizeEntry),
          query: promptText,
        });
        break;
      }

      default:
        updateEntry(entryId, { status: 'done', kind: 'query', message: data.message || 'Done.', rows: [] });
    }
  }, [pushToast, bumpRefresh, updateEntry]);

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const id = makeId();
    setTranscript((prev) => [...prev, { id, prompt: trimmed, status: 'pending' }]);
    setPanelOpen(true);
    setLoading(true);
    try {
      const { data } = await apiClient.post('/finance/chat', { message: trimmed });
      routeResponse(id, data, trimmed);
    } catch (err) {
      updateEntry(id, { status: 'error', message: extractErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }, [routeResponse, updateEntry]);

  // Re-fires a prompt with confirm_id set (from a DisambiguationPanel pick),
  // resolving it server-side as an explicit EDIT/DELETE, then replaces the
  // ambiguous CONFIRM_NEEDED entry in place with the resolved result.
  const resendWithConfirm = useCallback(async (entryId, promptText, confirmId) => {
    try {
      const { data } = await apiClient.post('/finance/chat', { message: promptText, confirm_id: confirmId });
      routeResponse(entryId, data, promptText);
    } catch (err) {
      updateEntry(entryId, { status: 'error', message: extractErrorMessage(err) });
    }
  }, [routeResponse, updateEntry]);

  const cancelConfirm = useCallback((entryId) => {
    updateEntry(entryId, { status: 'done', kind: 'cancelled', message: 'Cancelled.' });
  }, [updateEntry]);

  return (
    <ChatContext.Provider value={{
      transcript, loading, sendMessage, resendWithConfirm, cancelConfirm,
      panelOpen, openPanel, closePanel, togglePanel,
    }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within <ChatProvider>');
  return ctx;
}
