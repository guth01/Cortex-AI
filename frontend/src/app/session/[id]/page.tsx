'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { BookOpen, AlertTriangle, XCircle } from 'lucide-react';
import ToolCallIndicator from '@/components/ToolCallIndicator';
import StudyPlanConfirm from '@/components/StudyPlanConfirm';
import StreamingMessage from '@/components/StreamingMessage';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import apiClient, { streamChat, streamConfirmPlan, streamChooseFallback } from '@/lib/apiClient';
import type {
  Session,
  SSEProgress,
  StudyPlanEvent,
  TranscriptMessage,
  SSEPlanPending,
  SSEResponse,
  SSEFallbackPending,
} from '@/types';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  id: string;
  streaming?: boolean;
}

// Payload stored when the judge triggers a fallback interrupt
interface PendingFallback {
  verdict: 'PARTIAL' | 'INSUFFICIENT';
  reason: string;
  message: string;
}

export default function SessionPage() {
  const { id: sessionId } = useParams<{ id: string }>();
  const router = useRouter();

  const [session, setSession] = useState<Session | null>(null);
  const [subjectName, setSubjectName] = useState('');
  const [loading, setLoading] = useState(true);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [progressEvents, setProgressEvents] = useState<SSEProgress[]>([]);

  const [pendingPlan, setPendingPlan] = useState<StudyPlanEvent[] | null>(null);
  const [confirmingPlan, setConfirmingPlan] = useState(false);

  // Fallback choice state — set when judge returns PARTIAL or INSUFFICIENT
  const [pendingFallback, setPendingFallback] = useState<PendingFallback | null>(null);
  const [choosingFallback, setChoosingFallback] = useState(false);

  const [ending, setEnding] = useState(false);
  const [exporting, setExporting] = useState(false);
  // ID of the assistant message that contained a revision sheet — shown a download button
  const [revisionSheetMsgId, setRevisionSheetMsgId] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // The id of the "Thinking..." assistant bubble that shows while streaming
  const asstMsgIdRef = useRef<string>('');

  // Load session
  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await apiClient.get<Session>(`/sessions/${sessionId}`);
        setSession(data);

        // Fetch subject name
        try {
          const { data: subject } = await apiClient.get(`/subjects`);
          const match = subject.find((s: { id: string; name: string }) => s.id === data.subject_id);
          if (match) setSubjectName(match.name);
        } catch { /* ignore */ }

        // Load existing transcript
        const existing = data.transcript.map((m: TranscriptMessage, i: number) => ({
          id: `existing-${i}`,
          role: m.role,
          content: m.content,
        }));
        setMessages(existing);
      } catch {
        router.push('/dashboard');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [sessionId, router]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, progressEvents, pendingFallback]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return;
    const msg = input.trim();
    setInput('');
    setProgressEvents([]);
    setPendingPlan(null);
    setPendingFallback(null);

    const userMsgId = `user-${Date.now()}`;
    const asstMsgId = `asst-${Date.now()}`;
    asstMsgIdRef.current = asstMsgId;

    setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: msg }]);
    setIsStreaming(true);
    setMessages((prev) => [...prev, { id: asstMsgId, role: 'assistant', content: '', streaming: true }]);

    abortRef.current = new AbortController();
    let fullContent = '';
    let gotResponse = false;

    try {
      await streamChat(sessionId, msg, (event, data) => {
        if (event === 'progress') {
          const progress = data as SSEProgress;
          setProgressEvents((prev) => [...prev, progress]);
          // If revision sheet was generated, mark this message for the download button
          if (
            progress.node === 'revision_sheet' ||
            (progress.node === 'synthesis' && (data as Record<string, unknown>).revision_sheet)
          ) {
            setRevisionSheetMsgId(asstMsgId);
          }

        } else if (event === 'fallback_choice_pending') {
          // Judge returned PARTIAL or INSUFFICIENT — graph is paused.
          // Remove the "Thinking..." bubble and show the fallback choice UI.
          const payload = data as SSEFallbackPending;
          gotResponse = true;
          setMessages((prev) => prev.filter((m) => m.id !== asstMsgId));
          setPendingFallback({
            verdict: payload.verdict,
            reason: payload.reason,
            message: payload.message,
          });

        } else if (event === 'plan_pending') {
          const pending = data as SSEPlanPending;
          setPendingPlan(pending.proposed_events ?? []);

        } else if (event === 'token') {
          const d = data as { content: string };
          fullContent += d.content;
          gotResponse = true;
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: true } : m))
          );

        } else if (event === 'response') {
          const response = data as SSEResponse;
          gotResponse = true;
          // Use already-streamed content if we got tokens, otherwise fall back to full response
          const finalContent = fullContent || response.content || '';
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: finalContent, streaming: false } : m))
          );

        } else if (event === 'error') {
          const err = data as Record<string, unknown>;
          fullContent = `Error: ${err.detail}`;
          gotResponse = true;
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: false } : m))
          );
        }
      }, abortRef.current.signal);
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === asstMsgId ? { ...m, content: 'Connection error. Try again.', streaming: false } : m
          )
        );
      }
    } finally {
      // If the graph paused for fallback choice we already removed the bubble —
      // make sure it doesn't linger in a streaming state
      if (!gotResponse) {
        setMessages((prev) =>
          prev.map((m) => (m.id === asstMsgId ? { ...m, content: '', streaming: false } : m))
        );
      }
      setIsStreaming(false);
      setProgressEvents([]);
      inputRef.current?.focus();
    }
  }, [input, isStreaming, sessionId]);

  // Called when the user clicks "Use Gemini" or "Search the web"
  const handleFallbackChoice = async (strategy: 'gemini' | 'tavily') => {
    if (choosingFallback) return;
    setChoosingFallback(true);
    setPendingFallback(null);

    const asstMsgId = `fallback-asst-${Date.now()}`;
    setMessages((prev) => [...prev, { id: asstMsgId, role: 'assistant', content: '', streaming: true }]);

    let fullContent = '';

    try {
      await streamChooseFallback(sessionId, strategy, (event, data) => {
        if (event === 'token') {
          const d = data as { content: string };
          fullContent += d.content;
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: true } : m))
          );
        } else if (event === 'response') {
          const d = data as SSEResponse;
          const finalContent = fullContent || d.content || '';
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: finalContent, streaming: false } : m))
          );
        } else if (event === 'error') {
          const err = data as Record<string, unknown>;
          fullContent = `Error: ${err.detail}`;
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: false } : m))
          );
        }
      });
    } catch (e: unknown) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstMsgId
            ? { ...m, content: e instanceof Error ? e.message : 'Could not get a response. Try again.', streaming: false }
            : m
        )
      );
    } finally {
      setChoosingFallback(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleConfirmPlan = async () => {
    setConfirmingPlan(true);
    try {
      await streamConfirmPlan(sessionId, 'confirm', (event, data) => {
        const d = data as Record<string, unknown>;
        if (event === 'response') {
      const content = (d.content as string) ?? 'Calendar events created!';
          setMessages((prev) => [...prev, { id: `cal-${Date.now()}`, role: 'assistant', content }]);
        }
      });
      setPendingPlan(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not create calendar events.';
      setMessages((prev) => [...prev, { id: `cal-err-${Date.now()}`, role: 'system', content: `Error: ${msg}` }]);
    } finally {
      setConfirmingPlan(false);
    }
  };

  const handleRejectPlan = async () => {
    try {
      await streamConfirmPlan(sessionId, 'reject', () => {});
    } catch { /* ignore */ }
    setPendingPlan(null);
    setMessages((prev) => [...prev, { id: `rej-${Date.now()}`, role: 'system', content: 'Study plan discarded.' }]);
  };

  const handleEndSession = async () => {
    setEnding(true);
    try {
      abortRef.current?.abort();
      await apiClient.post(`/sessions/${sessionId}/end`);
      router.push(`/history/${sessionId}`);
    } catch {
      setEnding(false);
    }
  };

  const handleExportPDF = async (documentText?: string) => {
    if (!session || exporting) return;
    setExporting(true);
    try {
      const response = await apiClient.post(
        `/export/revision-sheet/${session.subject_id}?session_id=${sessionId}`,
        { document_text: documentText },
        { responseType: 'blob' }
      );
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `revision_sheet.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('PDF export failed:', e);
      alert('Could not generate PDF. Try generating a revision sheet first by asking the agent.');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-[#0a0d14]">
      {/* Header */}
      <header className="flex-shrink-0 glass border-b border-slate-200 dark:border-[#1f2d4a] px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-slate-900 dark:text-slate-100">{subjectName || 'Study Session'}</h1>
                <Badge color="green">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
                  Active
                </Badge>
              </div>
              {session && (
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                  {session.documents_used.length} document{session.documents_used.length !== 1 ? 's' : ''} loaded
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="danger" size="sm" loading={ending} onClick={handleEndSession}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              End Chat
            </Button>
          </div>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-6 px-4 space-y-1">
          {/* Welcome message */}
          {messages.length === 0 && !isStreaming && (
            <div className="text-center py-16 fade-in">
              <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/20 flex items-center justify-center mx-auto mb-4">
                <BookOpen className="w-8 h-8 text-indigo-400" />
              </div>
              <h2 className="text-xl font-semibold text-slate-700 dark:text-slate-300 mb-2">Ready to study!</h2>
              <p className="text-slate-600 dark:text-slate-400 text-sm max-w-md mx-auto">
                Ask questions about your documents, request a quiz, generate flashcards, or ask me to build a study plan.
              </p>
              <div className="flex flex-wrap gap-2 justify-center mt-6">
                {['Summarize my notes', 'Quiz me on the key concepts', 'What are the gaps in my knowledge?', 'Create a study plan for my exam'].map((s) => (
                  <button
                    key={s}
                    onClick={() => { setInput(s); inputRef.current?.focus(); }}
                    className="px-3 py-1.5 text-xs text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-[#1f2d4a] rounded-full hover:border-indigo-500/50 hover:text-indigo-400 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-4 fade-in`}
            >
              {msg.role === 'system' ? (
                <div className="text-center w-full text-xs text-slate-600 py-1">{msg.content}</div>
              ) : (
                <div
                  className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user' ? 'chat-user text-white' : 'chat-assistant text-slate-800 dark:text-slate-200'
                  }`}
                >
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <StreamingMessage
                      content={msg.content}
                      streaming={!!msg.streaming}
                      revisionSheet={msg.id === revisionSheetMsgId}
                      exporting={exporting}
                      onExportPDF={handleExportPDF}
                    />
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Tool call indicators */}
          {isStreaming && progressEvents.length > 0 && (
            <ToolCallIndicator events={progressEvents} isStreaming={isStreaming} />
          )}

          {/* ----------------------------------------------------------------
              Fallback Choice Card
              Shown when the Sufficiency Judge returns PARTIAL or INSUFFICIENT.
              Lets the user choose between Gemini knowledge or Tavily web search.
          ---------------------------------------------------------------- */}
          {pendingFallback && (
            <div className="fade-in my-4">
              <div className="glass border border-amber-500/30 rounded-2xl p-5 max-w-lg mx-auto">
                {/* Verdict badge */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-amber-400">
                    {pendingFallback.verdict === 'PARTIAL'
                      ? <AlertTriangle className="w-5 h-5" />
                      : <XCircle className="w-5 h-5 text-red-400" />}
                  </span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    pendingFallback.verdict === 'PARTIAL'
                      ? 'bg-amber-500/20 text-amber-300'
                      : 'bg-red-500/20 text-red-300'
                  }`}>
                    {pendingFallback.verdict === 'PARTIAL' ? 'Partial Coverage' : 'Not in Notes'}
                  </span>
                </div>

                {/* Message */}
                <p className="text-slate-800 dark:text-slate-200 text-sm font-medium mb-1">
                  {pendingFallback.message}
                </p>
                <p className="text-slate-600 dark:text-slate-400 text-xs mb-4 leading-relaxed">
                  {pendingFallback.reason}
                </p>

                {/* Choice buttons */}
                <p className="text-slate-600 dark:text-slate-400 text-xs uppercase tracking-wider mb-3 font-semibold">
                  How would you like to proceed?
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                  <button
                    id="fallback-gemini-btn"
                    disabled={choosingFallback}
                    onClick={() => handleFallbackChoice('gemini')}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl
                      bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 text-sm font-medium
                      hover:bg-indigo-600/30 hover:border-indigo-400/60 transition-all
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {choosingFallback ? (
                      <Spinner size="sm" />
                    ) : (
                      <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    )}
                    Use Gemini&apos;s Knowledge
                  </button>

                  <button
                    id="fallback-tavily-btn"
                    disabled={choosingFallback}
                    onClick={() => handleFallbackChoice('tavily')}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl
                      bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 text-sm font-medium
                      hover:bg-emerald-600/30 hover:border-emerald-400/60 transition-all
                      disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {choosingFallback ? (
                      <Spinner size="sm" />
                    ) : (
                      <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    )}
                    Search the Web (Tavily)
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Study plan confirmation */}
          {pendingPlan && pendingPlan.length > 0 && (
            <StudyPlanConfirm
              events={pendingPlan}
              sessionId={sessionId}
              onConfirm={handleConfirmPlan}
              onReject={handleRejectPlan}
              loading={confirmingPlan}
            />
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 glass border-t border-slate-200 dark:border-[#1f2d4a] px-4 py-4">
        <div className="max-w-4xl mx-auto flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question, request a quiz, or say 'make a study plan'..."
              rows={1}
              disabled={isStreaming || choosingFallback || session?.status !== 'active'}
              className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a] text-slate-900 dark:text-slate-100 placeholder-slate-600 text-sm resize-none transition-all disabled:opacity-50 max-h-32"
              style={{ minHeight: '48px' }}
            />
          </div>
          <Button
            onClick={sendMessage}
            loading={isStreaming}
            disabled={!input.trim() || choosingFallback || session?.status !== 'active'}
            size="md"
            className="flex-shrink-0 h-12"
          >
            {isStreaming ? (
              'Thinking...'
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </Button>
        </div>
        <p className="text-center text-xs text-slate-700 mt-2">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
