'use client';
import ReactMarkdown from 'react-markdown';
import { useTypewriter } from '@/lib/hooks/useTypewriter';
import Spinner from '@/components/ui/Spinner';

interface StreamingMessageProps {
  content: string;
  streaming: boolean;
  revisionSheet: boolean;
  exporting: boolean;
  onExportPDF: (text: string) => void;
}

/**
 * A single assistant chat message that uses the typewriter hook
 * to progressively reveal text, producing a ChatGPT-like streaming effect.
 */
export default function StreamingMessage({
  content,
  streaming,
  revisionSheet,
  exporting,
  onExportPDF,
}: StreamingMessageProps) {
  const displayedText = useTypewriter(content, streaming, 1);

  // When streaming and no content yet, show the thinking indicator
  if (streaming && !content) {
    return (
      <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
        <Spinner size="sm" />
        <span>Thinking...</span>
      </span>
    );
  }

  return (
    <div className="prose dark:prose-invert prose-sm max-w-none leading-relaxed text-slate-800 dark:text-slate-200">
      <ReactMarkdown>{streaming ? displayedText : content}</ReactMarkdown>
      {streaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-indigo-400 rounded-sm animate-pulse align-middle" />
      )}
      {/* Download button — only on messages with a revision sheet */}
      {revisionSheet && (
        <button
          id="download-revision-sheet-btn"
          onClick={() => onExportPDF(content)}
          disabled={exporting}
          className="mt-3 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30 transition-all disabled:opacity-50"
        >
          {exporting ? (
            <Spinner size="sm" />
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
          Download as PDF
        </button>
      )}
    </div>
  );
}
