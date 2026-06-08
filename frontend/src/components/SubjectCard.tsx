'use client';
import { useRouter } from 'next/navigation';
import { differenceInDays, parseISO } from 'date-fns';
import type { Subject } from '@/types';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

interface Props {
  subject: Subject;
  onDelete?: (id: string) => void;
  onStartSession?: (id: string) => void;
}

export default function SubjectCard({ subject, onDelete, onStartSession }: Props) {
  const router = useRouter();

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
            <h3 className="font-semibold text-slate-100 text-lg truncate">{subject.name}</h3>
            {daysUntilExam !== null && (
              <p className="text-xs text-slate-500 mt-0.5">
                Exam: {new Date(subject.exam_date!).toLocaleDateString()}
              </p>
            )}
          </div>
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(subject.id); }}
              className="opacity-0 group-hover:opacity-100 ml-2 p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
              title="Delete subject"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>

        {/* Exam countdown */}
        <div className="flex items-center gap-2">
          {daysUntilExam !== null ? (
            <Badge color={examBadgeColor}>
              {daysUntilExam < 0
                ? `${Math.abs(daysUntilExam)}d overdue`
                : daysUntilExam === 0
                ? '🚨 Exam today!'
                : `📅 ${daysUntilExam}d to exam`
              }
            </Badge>
          ) : (
            <Badge color="slate">No exam date</Badge>
          )}
        </div>

        {/* Action */}
        <div className="mt-auto pt-2 border-t border-[#1f2d4a]">
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
