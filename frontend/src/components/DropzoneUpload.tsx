'use client';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import Spinner from '@/components/ui/Spinner';

interface Props {
  subjectId?: string;
  onUpload: (file: File, subjectId?: string) => Promise<void>;
}

const ALLOWED = { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'text/markdown': ['.md'], 'text/plain': ['.txt'] };

export default function DropzoneUpload({ subjectId, onUpload }: Props) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const onDrop = useCallback(async (accepted: File[]) => {
    setUploading(true);
    setProgress([]);
    setErrors([]);
    const errs: string[] = [];
    const prog: string[] = [];
    for (const file of accepted) {
      try {
        prog.push(`Uploading ${file.name}...`);
        setProgress([...prog]);
        await onUpload(file, subjectId);
        prog[prog.length - 1] = `✓ ${file.name}`;
        setProgress([...prog]);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Upload failed';
        errs.push(`${file.name}: ${msg}`);
      }
    }
    setErrors(errs);
    setUploading(false);
  }, [onUpload, subjectId]);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ALLOWED,
    maxSize: 20 * 1024 * 1024,
    disabled: uploading,
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`
          relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all
          ${isDragReject
            ? 'border-red-500 bg-red-500/5'
            : isDragActive
            ? 'border-indigo-500 bg-indigo-500/10 scale-[1.01]'
            : 'border-slate-200 dark:border-[#1f2d4a] bg-slate-50 dark:bg-[#0f1623] hover:border-indigo-500/50 hover:bg-[#111827]'
          }
        `}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <Spinner size="md" />
            <p className="text-slate-600 dark:text-slate-400 text-sm">Uploading...</p>
          </div>
        ) : isDragActive ? (
          <div className="flex flex-col items-center gap-3">
            <div className="text-4xl">📥</div>
            <p className="text-indigo-400 font-medium">Drop files here</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-xl">
              📤
            </div>
            <div>
              <p className="text-slate-700 dark:text-slate-700 dark:text-slate-300 font-medium">Drag & drop files here</p>
              <p className="text-slate-500 text-sm mt-1">or click to browse</p>
            </div>
            <p className="text-xs text-slate-600">PDF, DOCX, MD, TXT · up to 20MB each</p>
          </div>
        )}
      </div>

      {/* Progress */}
      {progress.length > 0 && (
        <div className="space-y-1">
          {progress.map((msg, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
              {msg.startsWith('✓') ? (
                <span className="text-emerald-400">✓</span>
              ) : (
                <Spinner size="sm" />
              )}
              <span>{msg.replace('✓ ', '')}</span>
            </div>
          ))}
        </div>
      )}

      {/* Errors */}
      {errors.length > 0 && (
        <div key={errors.length} className="space-y-1 animate-shake">
          {errors.map((err, i) => (
            <p key={i} className="text-sm text-red-400 bg-red-500/10 px-3 py-1.5 rounded-lg border border-red-500/20">
              ⚠ {err}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
