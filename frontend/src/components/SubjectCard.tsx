'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { differenceInDays, parseISO } from 'date-fns';
import { AlertTriangle, Calendar } from 'lucide-react';
import type { Subject } from '@/types';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

interface Props {
  subject: Subject;
  onDelete?: (id: string) => Promise<void> | void;
  onStartSession?: (id: string) => void;
}

export default function SubjectCard({ subject, onDelete, onStartSession }: Props) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);

  const daysUntilExam = subject.exam_date
    ? differenceInDays(parseISO(subject.exam_date), new Date())
    : null;

  const examBadgeColor =
    daysUntilExam === null ? 'slate'
    : daysUntilExam < 7 ? 'red'
    : daysUntilExam < 14 ? 'yellow'
    : 'green';

  const handleStartSession = () => {
    if (onStartSession) {
      onStartSession(subject.id);
    } else {
      router.push(`/documents?subject=${subject.id}&action=start`);
    }
  };

  return (
    <div className="gradient-border group cursor-pointer p-px rounded-xl">
      <div className="bg-[#161d2e] rounded-xl p-5 h-full flex flex-col gap-4 transition-colors group-hover:bg-[#1a2235]">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-lg truncate">{subject.name}</h3>
            {daysUntilExam !== null && (
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                Exam: {new Date(subject.exam_date!).toLocaleDateString()}
              </p>
            )}
          </div>
          {onDelete && (
            <button
              disabled={isDeleting}
              onClick={async (e) => { 
                e.stopPropagation(); 
                if (isDeleting) return;
                setIsDeleting(true);
                try {
                  await onDelete(subject.id); 
                } catch (_err) {
                  setIsDeleting(false);
                }
              }}
              className={`opacity-0 group-hover:opacity-100 ml-2 p-1.5 text-slate-600 dark:text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all ${isDeleting ? 'opacity-100 cursor-wait' : ''}`}
              title="Delete subject"
            >
              {isDeleting ? (
                <svg className="w-4 h-4 animate-spin text-red-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              )}
            </button>
          )}
        </div>

        {/* Exam countdown */}
        <div className="flex items-center gap-2">
          {daysUntilExam !== null ? (
            <Badge color={examBadgeColor}>
              <span className="flex items-center gap-1">
                {daysUntilExam < 0
                  ? `${Math.abs(daysUntilExam)}d overdue`
                  : daysUntilExam === 0
                  ? <><AlertTriangle className="w-3 h-3" /> Exam today!</>
                  : <><Calendar className="w-3 h-3" /> {daysUntilExam}d to exam</>
                }
              </span>
            </Badge>
          ) : (
            <Badge color="slate">No exam date</Badge>
          )}
        </div>

        {/* Action */}
        <div className="mt-auto pt-2 border-t border-slate-200 dark:border-[#1f2d4a]">
          <Button
            variant="primary"
            size="sm"
            className="w-full"
            onClick={handleStartSession}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Start Session
          </Button>
        </div>
      </div>
    </div>
  );
}
