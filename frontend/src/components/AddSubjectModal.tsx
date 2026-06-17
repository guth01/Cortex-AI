'use client';
import { useState } from 'react';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, examDate?: string) => Promise<unknown>;
}

export default function AddSubjectModal({ open, onClose, onCreate }: Props) {
  const [name, setName] = useState('');
  const [examDate, setExamDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorKey, setErrorKey] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { 
      setError('Subject name is required'); 
      setErrorKey(prev => prev + 1);
      return; 
    }
    setLoading(true);
    try {
      await onCreate(name.trim(), examDate || undefined);
      setError('');
      setName('');
      setExamDate('');
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create subject');
      setErrorKey(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Add New Subject">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-700 dark:text-slate-300 mb-2">
            Subject Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => { setName(e.target.value); setError(''); }}
            placeholder="e.g. Organic Chemistry, Data Structures..."
            className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a] text-slate-900 dark:text-slate-100 placeholder-slate-600 text-sm transition-all focus:ring-2 focus:ring-indigo-500/50 outline-none"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-700 dark:text-slate-300 mb-2">
            Exam Date <span className="text-slate-600 dark:text-slate-400">(optional)</span>
          </label>
          <input
            type="date"
            value={examDate}
            onChange={(e) => { setExamDate(e.target.value); setError(''); }}
            min={new Date().toISOString().split('T')[0]}
            className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a] text-slate-900 dark:text-slate-100 text-sm transition-all [color-scheme:dark] focus:ring-2 focus:ring-indigo-500/50 outline-none"
          />
        </div>

        <div className="min-h-[2.5rem]">
          {error && (
            <p key={errorKey} className="animate-shake text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="button" variant="ghost" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={loading} className="flex-1">
            Create Subject
          </Button>
        </div>
      </form>
    </Modal>
  );
}
