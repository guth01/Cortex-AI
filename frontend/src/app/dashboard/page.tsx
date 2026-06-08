'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';
import Navbar from '@/components/Navbar';
import SubjectCard from '@/components/SubjectCard';
import AddSubjectModal from '@/components/AddSubjectModal';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import { useSubjects } from '@/lib/hooks/useSubjects';
import { useSessions } from '@/lib/hooks/useSessions';

export default function DashboardPage() {
  const router = useRouter();
  const { subjects, loading: subjectsLoading, createSubject, deleteSubject } = useSubjects();
  const { sessions, loading: sessionsLoading } = useSessions();
  const [addModal, setAddModal] = useState(false);
  const [oauthSuccess, setOauthSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      if (params.get('oauth') === 'success') {
        setOauthSuccess(params.get('google_email') || 'your account');
        // Clean up URL
        window.history.replaceState({}, '', '/dashboard');
      } else if (params.get('oauth') === 'error') {
        alert('Failed to connect Google Calendar: ' + params.get('reason'));
        window.history.replaceState({}, '', '/dashboard');
      }
    }
  }, []);

  const recentSessions = sessions
    .filter((s) => s.status === 'completed')
    .slice(0, 5);

  const activeSession = sessions.find((s) => s.status === 'active');

  const subjectMap = Object.fromEntries(subjects.map((s) => [s.id, s.name]));

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-100">Dashboard</h1>
            <p className="text-slate-500 mt-1 text-sm">Manage your subjects and study sessions</p>
          </div>
          <Button onClick={() => setAddModal(true)}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Subject
          </Button>
        </div>

        {/* OAuth Success banner */}
        {oauthSuccess && (
          <div className="mb-6 p-4 rounded-xl border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-between fade-in">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-200">Google Calendar Connected!</p>
                <p className="text-xs text-slate-400">
                  Successfully linked with <strong>{oauthSuccess}</strong>. The agent can now create study sessions for you.
                </p>
              </div>
            </div>
            <button onClick={() => setOauthSuccess(null)} className="text-slate-500 hover:text-slate-300">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
        )}

        {/* Active session banner */}
        {activeSession && (
          <div className="mb-6 p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 flex items-center justify-between fade-in">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-400 pulse-dot" />
              <div>
                <p className="text-sm font-medium text-emerald-400">Active session in progress</p>
                <p className="text-xs text-slate-500">
                  {subjectMap[activeSession.subject_id] ?? 'Unknown subject'} · Started {formatDistanceToNow(new Date(activeSession.started_at), { addSuffix: true })}
                </p>
              </div>
            </div>
            <Button size="sm" onClick={() => router.push(`/session/${activeSession.id}`)}>
              Resume →
            </Button>
          </div>
        )}

        {/* Subjects grid */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-300 mb-4">
            Your Subjects
            <span className="ml-2 text-sm text-slate-600 font-normal">({subjects.length})</span>
          </h2>

          {subjectsLoading ? (
            <div className="flex items-center justify-center h-40">
              <Spinner size="lg" />
            </div>
          ) : subjects.length === 0 ? (
            <div
              onClick={() => setAddModal(true)}
              className="border-2 border-dashed border-[#1f2d4a] rounded-2xl p-12 text-center cursor-pointer hover:border-indigo-500/50 hover:bg-[#111827] transition-all"
            >
              <div className="text-4xl mb-3">📚</div>
              <p className="text-slate-400 font-medium">No subjects yet</p>
              <p className="text-slate-600 text-sm mt-1">Click to add your first subject</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {subjects.map((subject) => (
                <SubjectCard
                  key={subject.id}
                  subject={subject}
                  onDelete={deleteSubject}
                />
              ))}
              {/* Add new card */}
              <button
                onClick={() => setAddModal(true)}
                className="h-full min-h-[180px] border-2 border-dashed border-[#1f2d4a] rounded-xl p-5 text-center hover:border-indigo-500/50 hover:bg-[#111827] transition-all flex flex-col items-center justify-center gap-2 text-slate-600 hover:text-slate-400"
              >
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                </svg>
                <span className="text-sm">Add Subject</span>
              </button>
            </div>
          )}
        </section>

        {/* Recent sessions */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-300">Recent Sessions</h2>
            <Link href="/history" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
              View all →
            </Link>
          </div>

          {sessionsLoading ? (
            <div className="flex items-center justify-center h-32"><Spinner /></div>
          ) : recentSessions.length === 0 ? (
            <div className="text-center py-10 text-slate-600">
              <div className="text-3xl mb-2">📝</div>
              <p className="text-sm">No completed sessions yet.</p>
              <p className="text-xs mt-1">Start a session from any subject card.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentSessions.map((session) => (
                <Link
                  key={session.id}
                  href={`/history/${session.id}`}
                  className="block p-4 rounded-xl border border-[#1f2d4a] bg-[#161d2e] hover:border-[#2a3a5c] hover:bg-[#1a2235] transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge color="green">Completed</Badge>
                      <span className="text-slate-300 text-sm font-medium">
                        {subjectMap[session.subject_id] ?? 'Unknown Subject'}
                      </span>
                    </div>
                    <span className="text-xs text-slate-600">
                      {formatDistanceToNow(new Date(session.started_at), { addSuffix: true })}
                    </span>
                  </div>
                  {session.summary && (
                    <p className="text-slate-500 text-xs mt-2 line-clamp-2">{session.summary}</p>
                  )}
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-slate-600">
                      {session.transcript.length} messages
                    </span>
                    <span className="text-xs text-slate-600">
                      {session.documents_used.length} docs used
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>

      <AddSubjectModal
        open={addModal}
        onClose={() => setAddModal(false)}
        onCreate={createSubject}
      />
    </>
  );
}
