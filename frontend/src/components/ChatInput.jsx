import { useState, useRef, useEffect } from 'react';
import { Sparkles, Send, Mic } from 'lucide-react';
import apiClient from '../api/client';
import { useChat } from '../context/ChatContext';
import ChatTranscriptPanel from './ChatTranscriptPanel';

/**
 * ChatInput — top-bar conversational prompt bar. Delegates the actual
 * POST /finance/chat request/response handling and transcript state to
 * ChatContext (lifted out of this component so the conversation history
 * survives navigating between pages, since AppShell now persists across
 * routes). This component only owns the input box and voice recording.
 *
 * Voice input: the mic button records a short clip via MediaRecorder and
 * sends it to POST /finance/transcribe. The returned transcript is placed
 * into the input box for the user to review and submit manually — it NEVER
 * calls sendMessage(), so voice never bypasses the normal submit flow.
 */
const MAX_RECORD_MS = 30000;   // safety auto-stop so a forgotten recording can't run forever
const MIME_TYPE = 'audio/webm'; // MediaRecorder default across Chrome/Edge/Firefox

export default function ChatInput() {
  const { sendMessage, loading, panelOpen, openPanel, closePanel } = useChat();
  const [message, setMessage] = useState('');
  const [micState, setMicState] = useState('idle'); // 'idle' | 'recording' | 'transcribing'
  const [micError, setMicError] = useState(null);
  const inputRef = useRef(null);
  const wrapRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordTimeoutRef = useRef(null);

  // Cmd/Ctrl+K focuses the input; Escape closes the transcript panel
  useEffect(() => {
    function handler(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape' && panelOpen) {
        closePanel();
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [panelOpen, closePanel]);

  // Close the panel on outside click
  useEffect(() => {
    function handleClick(e) {
      if (panelOpen && wrapRef.current && !wrapRef.current.contains(e.target)) {
        closePanel();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [panelOpen, closePanel]);

  // Stop any in-flight recording / timers if the component unmounts mid-record
  useEffect(() => () => {
    clearTimeout(recordTimeoutRef.current);
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!message.trim() || loading) return;
    const text = message.trim();
    setMessage('');
    await sendMessage(text);
  }

  // ── Voice input ──────────────────────────────────────────────
  // transcribeAndFill ONLY calls setMessage() — never sendMessage() — so a
  // spoken command lands in the input box for manual review, exactly like
  // typed text. This enforces "no auto-submit" structurally.
  async function transcribeAndFill(blob) {
    setMicState('transcribing');
    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
      const { data } = await apiClient.post('/finance/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (data.transcript) {
        setMessage(data.transcript);
        inputRef.current?.focus();
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMicError(typeof detail === 'string' ? detail : 'Transcription failed. Please try again.');
    } finally {
      setMicState('idle');
    }
  }

  async function startRecording() {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: MIME_TYPE });
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop()); // release the mic (clears the browser recording indicator)
        const blob = new Blob(audioChunksRef.current, { type: MIME_TYPE });
        await transcribeAndFill(blob);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setMicState('recording');
      recordTimeoutRef.current = setTimeout(() => stopRecording(), MAX_RECORD_MS);
    } catch (err) {
      setMicError(
        err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError'
          ? 'Microphone access denied. Enable it in your browser settings.'
          : 'Could not access microphone.'
      );
      setMicState('idle');
    }
  }

  function stopRecording() {
    clearTimeout(recordTimeoutRef.current);
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }

  function handleMicClick() {
    if (micState === 'recording') stopRecording();
    else if (micState === 'idle') startRecording();
    // no-op while 'transcribing'
  }

  const micTitle = micState === 'recording'
    ? 'Stop recording'
    : micState === 'transcribing'
      ? 'Transcribing…'
      : 'Speak a command';

  return (
    <div className="query-bar-wrap" ref={wrapRef}>
      <form className="query-bar" onSubmit={handleSubmit}>
        <button
          type="button"
          className="query-bar-icon-btn"
          onClick={openPanel}
          title="Conversation history"
          aria-label="Conversation history"
        >
          <Sparkles size={15} />
        </button>
        <input
          ref={inputRef}
          id="chat-input"
          type="text"
          className="query-bar-input"
          placeholder='Try: "Add ₹500 Zomato dinner" or "What did I spend last week?"'
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onFocus={openPanel}
          disabled={loading}
        />
        <button
          type="button"
          className={`query-bar-mic-btn ${micState === 'recording' ? 'is-recording' : ''}`}
          onClick={handleMicClick}
          disabled={loading || micState === 'transcribing'}
          title={micTitle}
          aria-label={micTitle}
        >
          {micState === 'transcribing'
            ? <span className="spinner spinner-dark" style={{ width: 13, height: 13, borderWidth: 1.5 }} />
            : <Mic size={14} />
          }
        </button>
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
      {micError && <div className="query-bar-mic-error">{micError}</div>}
      {panelOpen && <ChatTranscriptPanel />}
    </div>
  );
}
