'use client';
import Link from 'next/link';
import { formatDistanceToNow, format } from 'date-fns';
import { Clock, MessageSquare, FileText, History } from 'lucide-react';
import Navbar from '@/components/Navbar';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import { useSessions } from '@/lib/hooks/useSessions';
import { useSubjects } from '@/lib/hooks/useSubjects';

const statusColors: Record<string, 'green' | 'yellow' | 'red'> = {
  completed: 'green',
  active: 'yellow',
  interrupted: 'red',
};

export default function HistoryPage() {
  const { sessions, loading } = useSessions();
  const { subjects } = useSubjects();
  const subjectMap = Object.fromEntries(subjects.map((s) => [s.id, s.name]));

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Session History</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1 text-sm">All your past study sessions</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16">
            <History className="w-12 h-12 mx-auto mb-4 text-slate-600" />
            <p className="text-slate-600 dark:text-slate-400 font-medium">No sessions yet</p>
            <p className="text-slate-600 text-sm mt-2">
              Start your first session from the dashboard.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <Link
                key={session.id}
                href={`/history/${session.id}`}
                className="block p-5 glass rounded-2xl hover:border-indigo-500/30 transition-all border border-transparent"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge color={statusColors[session.status] ?? 'slate'}>
                        {session.status}
                      </Badge>
                      <h3 className="font-medium text-slate-800 dark:text-slate-200 text-sm truncate">
                        {subjectMap[session.subject_id] ?? 'Unknown Subject'}
                      </h3>
                    </div>

                    {session.summary && (
                      <p className="text-slate-600 dark:text-slate-400 text-sm mt-1 line-clamp-2">{session.summary}</p>
                    )}

                    <div className="flex items-center gap-4 mt-2">
                      <span className="flex items-center gap-1 text-xs text-slate-600">
                        <Clock className="w-3 h-3" />{format(new Date(session.started_at), 'MMM d, yyyy · h:mm a')}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-slate-600">
                        <MessageSquare className="w-3 h-3" />{session.transcript.length} messages
                      </span>
                      <span className="flex items-center gap-1 text-xs text-slate-600">
                        <FileText className="w-3 h-3" />{session.documents_used.length} docs
                      </span>
                    </div>
                  </div>

                  <div className="flex-shrink-0 text-right">
                    <p className="text-xs text-slate-600">
                      {formatDistanceToNow(new Date(session.started_at), { addSuffix: true })}
                    </p>
                    {session.ended_at && (
                      <p className="text-xs text-slate-700 mt-0.5">
                        {Math.round((new Date(session.ended_at).getTime() - new Date(session.started_at).getTime()) / 60000)}min
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
