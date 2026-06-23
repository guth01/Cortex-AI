'use client';
import { FileText, File, FileCode, Folder } from 'lucide-react';
import type { Document } from '@/types';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

const typeColors: Record<string, 'red' | 'blue' | 'green' | 'yellow'> = {
  pdf: 'red', docx: 'blue', md: 'green', txt: 'yellow',
};

const typeIconMap: Record<string, React.ElementType> = {
  pdf: FileText, docx: File, md: FileCode, txt: FileText,
};

interface Props {
  documents: Document[];
  selectedIds?: Set<string>;
  onToggle?: (id: string) => void;
  onDelete?: (id: string) => void;
  showCheckboxes?: boolean;
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export default function DocumentList({ documents, selectedIds, onToggle, onDelete, showCheckboxes }: Props) {
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-slate-600 dark:text-slate-400">
        <Folder className="w-10 h-10 mx-auto mb-3 text-slate-600" />
        <p className="text-sm">No documents yet. Upload some files above.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const isSelected = selectedIds?.has(doc.id);
        return (
          <div
            key={doc.id}
            onClick={() => onToggle?.(doc.id)}
            className={`
              flex items-center gap-4 p-4 rounded-xl border transition-all
              ${showCheckboxes ? 'cursor-pointer' : ''}
              ${isSelected
                ? 'border-indigo-500/60 bg-indigo-500/10'
                : 'border-slate-200 dark:border-[#1f2d4a] bg-white dark:bg-[#161d2e] hover:border-slate-300 dark:hover:border-[#2a3a5c] hover:bg-slate-50 dark:hover:bg-transparent'
              }
            `}
          >
            {showCheckboxes && (
              <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all ${isSelected ? 'bg-indigo-600 border-indigo-600' : 'border-slate-600'}`}>
                {isSelected && (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            )}

            {/* Icon */}
            <div className="w-9 h-9 rounded-lg bg-slate-700/40 flex items-center justify-center flex-shrink-0">
              {(() => { const Icon = typeIconMap[doc.source_type] ?? File; return <Icon className="w-4 h-4 text-slate-400" />; })()}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <p className="text-slate-800 dark:text-slate-200 text-sm font-medium truncate">{doc.filename}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge color={typeColors[doc.source_type] ?? 'slate'}>
                  {doc.source_type.toUpperCase()}
                </Badge>
                <span className="text-xs text-slate-600">{formatBytes(doc.file_size)}</span>
                {doc.page_count && (
                  <span className="text-xs text-slate-600">{doc.page_count} pages</span>
                )}
                <span className="text-xs text-slate-600">
                  {new Date(doc.uploaded_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            {/* Delete */}
            {onDelete && (
              <Button
                variant="danger"
                size="sm"
                onClick={(e) => { e.stopPropagation(); onDelete(doc.id); }}
                className="flex-shrink-0 opacity-0 group-hover:opacity-100"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
}
