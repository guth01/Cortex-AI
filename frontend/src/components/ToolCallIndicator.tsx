'use client';
import type { SSEProgress } from '@/types';
import { Brain, BookOpen, Scale, Pause, Search, ScanSearch, LayoutList, CalendarDays, PenLine, Settings } from 'lucide-react';

const nodeMap: Record<string, { label: string; Icon: React.ElementType; color: string }> = {
  router:              { label: 'Understanding your question...', Icon: Brain,        color: 'text-purple-400' },
  retrieval:           { label: 'Searching your notes...',        Icon: BookOpen,     color: 'text-blue-400' },
  rag:                 { label: 'Searching your notes...',        Icon: BookOpen,     color: 'text-blue-400' },
  sufficiency_judge:   { label: 'Evaluating note coverage...',    Icon: Scale,        color: 'text-amber-400' },
  await_fallback_node: { label: 'Waiting for your choice...',     Icon: Pause,        color: 'text-slate-400' },
  tavily_search:       { label: 'Searching the web...',           Icon: Search,       color: 'text-emerald-400' },
  gap_analysis:        { label: 'Analyzing knowledge gaps...',    Icon: ScanSearch,   color: 'text-orange-400' },
  flashcard_node:      { label: 'Creating flashcards...',         Icon: LayoutList,   color: 'text-green-400' },
  flashcard_generator: { label: 'Creating flashcards...',         Icon: LayoutList,   color: 'text-green-400' },
  study_planning:      { label: 'Building study plan...',         Icon: CalendarDays, color: 'text-yellow-400' },
  study_plan_builder:  { label: 'Building study plan...',         Icon: CalendarDays, color: 'text-yellow-400' },
  synthesis:           { label: 'Composing answer...',            Icon: PenLine,      color: 'text-indigo-400' },
  calendar_node:       { label: 'Adding to Google Calendar...',   Icon: CalendarDays, color: 'text-pink-400' },
};

interface Props {
  events: SSEProgress[];
  isStreaming: boolean;
}

export default function ToolCallIndicator({ events, isStreaming }: Props) {
  if (events.length === 0 && !isStreaming) return null;

  return (
    <div className="flex flex-col gap-1.5 px-4 py-3">
      {events.map((ev, i) => {
        const info = nodeMap[ev.node] ?? { label: ev.node, Icon: Settings, color: 'text-slate-400' };
        const { Icon } = info;
        const isLast = i === events.length - 1;
        return (
          <div key={i} className={`flex items-center gap-2.5 slide-in ${isLast && isStreaming ? 'opacity-100' : 'opacity-60'}`}>
            <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${info.color}`} />
            <span className={`text-xs font-medium ${info.color}`}>{info.label}</span>

            {/* Extra context */}
            {ev.intent && <span className="text-xs text-slate-600 ml-1">· {ev.intent}</span>}
            {ev.chunks_found !== undefined && <span className="text-xs text-slate-600">· {ev.chunks_found} chunks</span>}
            {ev.judge_verdict && <span className="text-xs text-slate-600">· {ev.judge_verdict}</span>}
            {ev.web_results_count !== undefined && <span className="text-xs text-slate-600">· {ev.web_results_count} results</span>}
            {ev.flashcards_created !== undefined && <span className="text-xs text-slate-600">· {ev.flashcards_created} cards</span>}
            {ev.events_proposed !== undefined && <span className="text-xs text-slate-600">· {ev.events_proposed} events</span>}

            {isLast && isStreaming && (
              <div className="flex gap-0.5 ml-1">
                {[0, 1, 2].map((d) => (
                  <div
                    key={d}
                    className="w-1 h-1 rounded-full bg-current pulse-dot"
                    style={{ animationDelay: `${d * 0.2}s` }}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
