'use client';
import { useState } from 'react';
import { CalendarDays, Check, X } from 'lucide-react';
import type { StudyPlanEvent } from '@/types';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface Props {
  events: StudyPlanEvent[];
  sessionId: string;
  onConfirm: () => void;
  onReject: () => void;
  loading?: boolean;
}

const coverageColors: Record<string, 'red' | 'yellow' | 'green'> = {
  missing: 'red',
  shallow: 'yellow',
  well_covered: 'green',
};

export default function StudyPlanConfirm({ events, onConfirm, onReject, loading }: Props) {
  const [expanded, setExpanded] = useState(true);

  const totalHours = events.reduce((sum, e) => sum + e.duration_minutes, 0) / 60;

  return (
    <div className="mx-4 my-2 rounded-2xl border border-indigo-500/30 bg-indigo-500/5 overflow-hidden fade-in">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-indigo-500/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/30 flex items-center justify-center">
            <CalendarDays className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-left">
            <p className="font-semibold text-slate-800 dark:text-slate-200 text-sm">Study Plan Ready</p>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {events.length} sessions · {totalHours.toFixed(1)}h total
            </p>
          </div>
        </div>
        <svg
          className={`w-5 h-5 text-slate-600 dark:text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Events table */}
      {expanded && (
        <div className="border-t border-indigo-500/20">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-[#1f2d4a]">
                  <th className="text-left text-slate-600 dark:text-slate-400 font-medium px-4 py-2">Date</th>
                  <th className="text-left text-slate-600 dark:text-slate-400 font-medium px-4 py-2">Topic</th>
                  <th className="text-left text-slate-600 dark:text-slate-400 font-medium px-4 py-2">Duration</th>
                  <th className="text-left text-slate-600 dark:text-slate-400 font-medium px-4 py-2">Coverage</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev, i) => (
                  <tr key={i} className="border-b border-slate-200 dark:border-[#1f2d4a]/50 hover:bg-[#1e2640]/30">
                    <td className="px-4 py-2 text-slate-700 dark:text-slate-300 whitespace-nowrap">{ev.date}</td>
                    <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{ev.topic}</td>
                    <td className="px-4 py-2 text-slate-600 dark:text-slate-400 whitespace-nowrap">{ev.duration_minutes}min</td>
                    <td className="px-4 py-2">
                      <Badge color={ev.coverage_level ? coverageColors[ev.coverage_level] ?? 'slate' : 'slate'}>
                        {ev.coverage_level ? ev.coverage_level.replace('_', ' ') : 'Manual'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Actions */}
          <div className="flex gap-3 p-4 border-t border-indigo-500/20">
            <Button variant="success" loading={loading} onClick={onConfirm} className="flex-1 flex items-center justify-center gap-2">
              <Check className="w-4 h-4" /> Add to Google Calendar
            </Button>
            <Button variant="danger" onClick={onReject} disabled={loading} className="flex-1 flex items-center justify-center gap-2">
              <X className="w-4 h-4" /> Reject Plan
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
