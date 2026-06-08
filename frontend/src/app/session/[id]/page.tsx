'use client';
import ReactMarkdown from 'react-markdown';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import ToolCallIndicator from '@/components/ToolCallIndicator';
import StudyPlanConfirm from '@/components/StudyPlanConfirm';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import apiClient, { streamChat, streamConfirmPlan } from '@/lib/apiClient';
import type { Session, SSEProgress, StudyPlanEvent, TranscriptMessage, SSEPlanPending, SSEResponse } from '@/types';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  id: string;
  streaming?: boolean;
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

  const [ending, setEnding] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

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
  }, [messages, progressEvents]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return;
    const msg = input.trim();
    setInput('');
    setProgressEvents([]);
    setPendingPlan(null);

    const userMsgId = `user-${Date.now()}`;
    const asstMsgId = `asst-${Date.now()}`;

    setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: msg }]);
    setIsStreaming(true);
    setMessages((prev) => [...prev, { id: asstMsgId, role: 'assistant', content: '', streaming: true }]);

    abortRef.current = new AbortController();
    let fullContent = '';

    try {
      await streamChat(sessionId, msg, (event, data) => {
        if (event === 'progress') {
          const progress = data as SSEProgress;
          setProgressEvents((prev) => [...prev, progress]);
        } else if (event === 'plan_pending') {
          const pending = data as SSEPlanPending;
          setPendingPlan(pending.proposed_events ?? []);
        } else if (event === 'response') {
          const response = data as SSEResponse;
          fullContent = response.content ?? '';
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: false } : m))
          );
        } else if (event === 'error') {
          const err = data as Record<string, any>;
          fullContent = `⚠ Error: ${err.detail}`;
          setMessages((prev) =>
            prev.map((m) => (m.id === asstMsgId ? { ...m, content: fullContent, streaming: false } : m))
          );
        }
      }, abortRef.current.signal);
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        setMessages((prev) =>
          prev.map((m) => m.id === asstMsgId ? { ...m, content: '⚠ Connection error. Try again.', streaming: false } : m)
        );
      }
    } finally {
      setIsStreaming(false);
      setProgressEvents([]);
      inputRef.current?.focus();
    }
  }, [input, isStreaming, sessionId]);

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
          const content = (d.content as string) ?? 'Calendar events created! ✅';
          setMessages((prev) => [...prev, { id: `cal-${Date.now()}`, role: 'assistant', content }]);
        }
      });
      setPendingPlan(null);
    } catch {
      setMessages((prev) => [...prev, { id: `cal-err-${Date.now()}`, role: 'system', content: '⚠ Could not create calendar events.' }]);
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-[#0a0d14]">
      {/* Header */}
      <header className="flex-shrink-0 glass border-b border-[#1f2d4a] px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-slate-100">{subjectName || 'Study Session'}</h1>
                <Badge color="green">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
                  Active
                </Badge>
              </div>
              {session && (
                <p className="text-xs text-slate-500 mt-0.5">
                  {session.documents_used.length} document{session.documents_used.length !== 1 ? 's' : ''} loaded
                </p>
              )}
            </div>
          </div>

          <Button variant="danger" size="sm" loading={ending} onClick={handleEndSession}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
            </svg>
            End Chat
          </Button>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-6 px-4 space-y-1">
          {/* Welcome message */}
          {messages.length === 0 && !isStreaming && (
            <div className="text-center py-16 fade-in">
              <div className="text-5xl mb-4">🧠</div>
              <h2 className="text-xl font-semibold text-slate-300 mb-2">Ready to study!</h2>
              <p className="text-slate-500 text-sm max-w-md mx-auto">
                Ask questions about your documents, request a quiz, generate flashcards, or ask me to build a study plan.
              </p>
              <div className="flex flex-wrap gap-2 justify-center mt-6">
                {['Summarize my notes', 'Quiz me on the key concepts', 'What are the gaps in my knowledge?', 'Create a study plan for my exam'].map((s) => (
                  <button
                    key={s}
                    onClick={() => { setInput(s); inputRef.current?.focus(); }}
                    className="px-3 py-1.5 text-xs text-slate-400 border border-[#1f2d4a] rounded-full hover:border-indigo-500/50 hover:text-indigo-400 transition-all"
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
                    msg.role === 'user' ? 'chat-user text-white' : 'chat-assistant text-slate-200'
                  }`}
                >
                  {msg.streaming ? (
                    <span className="flex items-center gap-1.5 text-slate-400">
                      <Spinner size="sm" />
                      <span>Thinking...</span>
                    </span>
                  ) : (
                    <div className="prose prose-invert prose-sm max-w-none leading-relaxed text-slate-200">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Tool call indicators */}
          {isStreaming && progressEvents.length > 0 && (
            <ToolCallIndicator events={progressEvents} isStreaming={isStreaming} />
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
      <div className="flex-shrink-0 glass border-t border-[#1f2d4a] px-4 py-4">
        <div className="max-w-4xl mx-auto flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question, request a quiz, or say 'make a study plan'..."
              rows={1}
              disabled={isStreaming || session?.status !== 'active'}
              className="w-full px-4 py-3 rounded-xl bg-[#0f1623] border border-[#1f2d4a] text-slate-100 placeholder-slate-600 text-sm resize-none transition-all disabled:opacity-50 max-h-32"
              style={{ minHeight: '48px' }}
            />
          </div>
          <Button
            onClick={sendMessage}
            loading={isStreaming}
            disabled={!input.trim() || session?.status !== 'active'}
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
