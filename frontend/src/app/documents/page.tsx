'use client';
import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import Navbar from '@/components/Navbar';
import DropzoneUpload from '@/components/DropzoneUpload';
import DocumentList from '@/components/DocumentList';
import Button from '@/components/ui/Button';
import Spinner from '@/components/ui/Spinner';
import { useSubjects } from '@/lib/hooks/useSubjects';
import { useDocuments } from '@/lib/hooks/useDocuments';
import { useSessions } from '@/lib/hooks/useSessions';

function DocumentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initSubject = searchParams.get('subject') ?? 'all';
  const autoStart = searchParams.get('action') === 'start';

  const { subjects, loading: subjectsLoading } = useSubjects();
  const [activeTab, setActiveTab] = useState<string>(initSubject);
  const subjectIdFilter = activeTab === 'all' ? undefined : activeTab;
  const { documents, loading: docsLoading, uploadDocument, deleteDocument } = useDocuments(subjectIdFilter);
  const { startSession } = useSessions();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const [topicsInput, setTopicsInput] = useState('');

  // If redirected here to start a session, auto-focus the subject tab
  useEffect(() => {
    if (autoStart && initSubject !== 'all') setActiveTab(initSubject);
  }, [autoStart, initSubject]);

  // Reset selection when tab changes
  useEffect(() => { setSelectedIds(new Set()); }, [activeTab]);

  const toggleDoc = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleStartSession = async () => {
    if (selectedIds.size === 0) { setStartError('Select at least one document'); return; }
    const subjectId = activeTab === 'all' ? undefined : activeTab;
    if (!subjectId) { setStartError('Select a subject tab first'); return; }
    
    const topics = topicsInput.split(',').map(t => t.trim()).filter(t => t.length > 0);
    if (topics.length === 0) { setStartError('Please enter at least one topic'); return; }

    setStarting(true);
    setStartError('');
    try {
      const { session_id } = await startSession(subjectId, Array.from(selectedIds), topics);
      router.push(`/session/${session_id}`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setStartError(detail || 'Failed to start session');
      setStarting(false);
    }
  };

  const handleUpload = async (file: File, subjId?: string) => {
    await uploadDocument(file, subjId || subjectIdFilter);
  };

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-100">Documents</h1>
            <p className="text-slate-500 mt-1 text-sm">Upload study materials and start sessions</p>
          </div>

          {/* Start session button */}
          {activeTab !== 'all' && (
            <div className="flex items-center gap-3">
              {selectedIds.size > 0 && (
                <span className="text-sm text-slate-400">
                  {selectedIds.size} doc{selectedIds.size !== 1 ? 's' : ''} selected
                </span>
              )}
              <input
                type="text"
                placeholder="Topics to study (e.g. recursion, arrays)"
                value={topicsInput}
                onChange={(e) => setTopicsInput(e.target.value)}
                className="bg-[#161d2e] border border-[#1f2d4a] rounded-xl px-4 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500/50 w-64"
              />
              <Button
                onClick={handleStartSession}
                loading={starting}
                disabled={selectedIds.size === 0}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                </svg>
                Start Session
              </Button>
            </div>
          )}
        </div>

        {startError && (
          <div className="mb-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
            {startError}
          </div>
        )}

        {/* Subject tabs */}
        {subjectsLoading ? (
          <div className="h-10 skeleton w-64 mb-6" />
        ) : (
          <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                activeTab === 'all'
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-[#1e2640] border border-transparent'
              }`}
            >
              All Documents
            </button>
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveTab(s.id)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                  activeTab === s.id
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-[#1e2640] border border-transparent'
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}

        {/* Upload area */}
        <div className="mb-8 p-6 glass rounded-2xl">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-4">Upload Files</h2>
          {activeTab !== 'all' && (
            <p className="text-xs text-slate-600 mb-3">
              Uploading to: <span className="text-indigo-400">{subjects.find(s => s.id === activeTab)?.name ?? activeTab}</span>
            </p>
          )}
          <DropzoneUpload
            subjectId={subjectIdFilter}
            onUpload={handleUpload}
          />
        </div>

        {/* Document list with checkboxes */}
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              {activeTab === 'all' ? 'All Documents' : 'Documents in this subject'}
              <span className="ml-2 font-normal text-slate-600 normal-case">({documents.length})</span>
            </h2>
            {activeTab !== 'all' && documents.length > 0 && (
              <button
                onClick={() => setSelectedIds(selectedIds.size === documents.length ? new Set() : new Set(documents.map(d => d.id)))}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                {selectedIds.size === documents.length ? 'Deselect all' : 'Select all'}
              </button>
            )}
          </div>

          {docsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : (
            <DocumentList
              documents={documents}
              selectedIds={activeTab !== 'all' ? selectedIds : undefined}
              onToggle={activeTab !== 'all' ? toggleDoc : undefined}
              onDelete={deleteDocument}
              showCheckboxes={activeTab !== 'all'}
            />
          )}
        </div>
      </main>
    </>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Spinner size="lg" /></div>}>
      <DocumentsContent />
    </Suspense>
  );
}
