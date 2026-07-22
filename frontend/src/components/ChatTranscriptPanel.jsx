import { useEffect, useRef } from 'react';
import { X, Sparkles } from 'lucide-react';
import { useChat } from '../context/ChatContext';
import DisambiguationPanel from './DisambiguationPanel';

/**
 * ChatTranscriptPanel — dropdown showing the full conversation history with
 * the assistant (Decision: chat evolves from a single overwritten result
 * into a persistent transcript). Lives inside ChatInput's wrapper so it
 * anchors directly under the input bar.
 */
export default function ChatTranscriptPanel() {
  const { transcript, resendWithConfirm, cancelConfirm, closePanel } = useChat();
  const bodyRef = useRef(null);
  const lastEntry = transcript[transcript.length - 1];

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [transcript.length, lastEntry?.status]);

  return (
    <div className="chat-panel" role="dialog" aria-label="Assistant conversation">
      <div className="chat-panel-header">
        <span className="chat-panel-title"><Sparkles size={13} /> Assistant</span>
        <button
          type="button"
          className="chat-panel-close"
          onClick={closePanel}
          aria-label="Close conversation"
        >
          <X size={15} />
        </button>
      </div>

      <div className="chat-panel-body" ref={bodyRef}>
        {transcript.length === 0 ? (
          <div className="chat-panel-empty">
            Ask about your spending, or add a transaction — try "What did I spend on food last month?"
          </div>
        ) : (
          transcript.map((entry) => (
            <div key={entry.id} className="chat-turn">
              <div className="chat-bubble chat-bubble-user">{entry.prompt}</div>

              {entry.status === 'pending' && (
                <div className="chat-bubble chat-bubble-assistant chat-bubble-pending">
                  <span className="spinner spinner-dark" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
                  Thinking…
                </div>
              )}

              {entry.status === 'error' && (
                <div className="chat-bubble chat-bubble-assistant chat-bubble-error">{entry.message}</div>
              )}

              {entry.status === 'done' && entry.kind === 'confirm' && (
                <div className="chat-bubble chat-bubble-assistant chat-bubble-confirm">
                  <DisambiguationPanel
                    message={entry.message}
                    candidates={entry.candidates}
                    onSelect={(candidateId) => resendWithConfirm(entry.id, entry.query, candidateId)}
                    onCancel={() => cancelConfirm(entry.id)}
                  />
                </div>
              )}

              {entry.status === 'done' && entry.kind !== 'confirm' && (
                <div className="chat-bubble chat-bubble-assistant">
                  <p className="chat-bubble-message">{entry.message}</p>
                  {entry.kind === 'query' && entry.rows?.length > 0 && (
                    <div className="table-wrap chat-result-table">
                      <table>
                        <thead>
                          <tr>
                            {Object.keys(entry.rows[0]).map((k) => <th key={k}>{k.toUpperCase()}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {entry.rows.map((row, i) => (
                            <tr key={i}>
                              {Object.values(row).map((v, j) => <td key={j}>{String(v)}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
