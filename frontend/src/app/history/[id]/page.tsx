'use client';
import ReactMarkdown from 'react-markdown';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import Navbar from '@/components/Navbar';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Button from '@/components/ui/Button';
import apiClient from '@/lib/apiClient';
import type { Session } from '@/types';

export default function SessionHistoryPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [subjectName, setSubjectName] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await apiClient.get<Session>(`/sessions/${id}`);
        setSession(data);
        // Resolve subject name
        try {
          const { data: subjects } = await apiClient.get('/subjects');
          const match = subjects.find((s: { id: string; name: string }) => s.id === data.subject_id);
          if (match) setSubjectName(match.name);
        } catch { /* ignore */ }
      } catch {
        router.push('/history');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, router]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center"><Spinner size="lg" /></div>;
  }

  if (!session) return null;

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        {/* Back */}
        <Link
          href="/history"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-300 mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to History
        </Link>

        {/* Header */}
        <div className="glass rounded-2xl p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Badge color={session.status === 'completed' ? 'green' : session.status === 'active' ? 'yellow' : 'red'}>
                  {session.status}
                </Badge>
                <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">{subjectName || 'Study Session'}</h1>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500">
                <span>📅 {format(new Date(session.started_at.endsWith('Z') ? session.started_at : session.started_at + 'Z'), 'MMMM d, yyyy · h:mm a')}</span>
                {session.ended_at && (
                  <span>
                    ⏱ {Math.round((new Date(session.ended_at).getTime() - new Date(session.started_at).getTime()) / 60000)} min
                  </span>
                )}
                <span>💬 {session.transcript.length} messages</span>
                <span>📄 {session.documents_used.length} docs</span>
              </div>
            </div>
          </div>

          {/* Summary */}
          {session.summary && (
            <div className="mt-4 pt-4 border-t border-slate-200 dark:border-[#1f2d4a]">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Session Summary</p>
              <p className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed">{session.summary}</p>
            </div>
          )}

          {/* Evaluator scores — Day 7 placeholder */}
          <div className="mt-4 pt-4 border-t border-slate-200 dark:border-[#1f2d4a]">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Evaluator Scores</p>
            <div className="grid grid-cols-3 gap-3">
              {['Relevance', 'Depth', 'Accuracy'].map((label) => (
                <div key={label} className="text-center p-3 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a]">
                  <p className="text-2xl font-bold text-slate-600">—</p>
                  <p className="text-xs text-slate-600 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-700 mt-2 text-center">Evaluator scores available after Day 7</p>
          </div>
        </div>

        {/* Transcript */}
        <div className="glass rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide mb-6">
            Full Transcript
          </h2>
          {session.transcript.length === 0 ? (
            <p className="text-slate-600 text-sm text-center py-8">No messages in this session.</p>
          ) : (
            <div className="space-y-4">
              {session.transcript.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className="max-w-[80%]">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-xs text-slate-600">
                        {msg.role === 'user' ? 'You' : '🧠 Agent'}
                      </span>
                      {msg.timestamp && (
                        <span className="text-xs text-slate-700">
                          · {format(new Date(msg.timestamp.endsWith('Z') ? msg.timestamp : msg.timestamp + 'Z'), 'h:mm a')}
                        </span>
                      )}
                      {msg.metadata?.intent && (
                        <Badge color="indigo">{msg.metadata.intent}</Badge>
                      )}
                    </div>
                    <div
                      className={`px-4 py-3 text-sm leading-relaxed ${
                        msg.role === 'user' ? 'chat-user text-white' : 'chat-assistant text-slate-800 dark:text-slate-200'
                      }`}
                    >
                      <div className="prose dark:prose-invert prose-sm max-w-none leading-relaxed text-slate-800 dark:text-slate-200">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                    {msg.metadata && (
                      <div className="flex items-center gap-2 mt-1 px-1">
                        {msg.metadata.confidence !== undefined && (
                          <span className="text-xs text-slate-700">
                            Confidence: {(msg.metadata.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                        {msg.metadata.chunks_used !== undefined && (
                          <span className="text-xs text-slate-700">
                            {msg.metadata.chunks_used} chunks
                          </span>
                        )}
                        {msg.metadata.answer_source && (
                          <span className="text-xs text-slate-700">📎 {msg.metadata.answer_source}</span>
                        )}
                        {msg.metadata.judge_verdict && (
                          <span className="text-xs text-slate-700">⚖️ {msg.metadata.judge_verdict}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
