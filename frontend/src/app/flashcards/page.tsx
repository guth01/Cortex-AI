'use client';
import { useState } from 'react';
import Navbar from '@/components/Navbar';
import FlashCardComponent from '@/components/FlashCard';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { useSubjects } from '@/lib/hooks/useSubjects';
import { useFlashcards } from '@/lib/hooks/useFlashcards';

const PAGE_SIZE = 8;

function Pagination({
  total,
  page,
  onPage,
}: {
  total: number;
  page: number;
  onPage: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-200 dark:border-slate-800">
      <p className="text-xs text-slate-600 dark:text-slate-400">
        Page {page} of {totalPages} · {total} cards
      </p>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700
            text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e2640]
            disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          ← Prev
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
          <button
            key={p}
            onClick={() => onPage(p)}
            className={`w-8 h-8 text-xs rounded-lg transition-all ${
              p === page
                ? 'bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 font-semibold'
                : 'border border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e2640]'
            }`}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page === totalPages}
          className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700
            text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e2640]
            disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

export default function FlashcardsPage() {
  const { subjects, loading: subjectsLoading } = useSubjects();
  const [activeSubject, setActiveSubject] = useState<string>('all');
  const [upcomingPage, setUpcomingPage] = useState(1);
  const [donePage, setDonePage] = useState(1);

  const subjectIdFilter = activeSubject === 'all' ? undefined : activeSubject;
  const { flashcards, loading: cardsLoading, markDone } = useFlashcards(subjectIdFilter);

  const unreviewedCards = flashcards.filter((c) => c.status === 'upcoming');
  const reviewedCards = flashcards.filter((c) => c.status === 'done');

  const pagedUpcoming = unreviewedCards.slice((upcomingPage - 1) * PAGE_SIZE, upcomingPage * PAGE_SIZE);
  const pagedDone = reviewedCards.slice((donePage - 1) * PAGE_SIZE, donePage * PAGE_SIZE);

  // Reset page when subject filter changes
  const handleSubjectChange = (id: string) => {
    setActiveSubject(id);
    setUpcomingPage(1);
    setDonePage(1);
  };

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Flashcards</h1>
          </div>
          <div className="flex gap-3">
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{unreviewedCards.length}</p>
              <p className="text-xs text-slate-600">To Review</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-600 dark:text-slate-400">{reviewedCards.length}</p>
              <p className="text-xs text-slate-600">Done</p>
            </div>
          </div>
        </div>

        {/* Subject tabs */}
        {!subjectsLoading && (
          <div className="flex gap-2 mb-8 overflow-x-auto pb-1">
            <button
              onClick={() => handleSubjectChange('all')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                activeSubject === 'all'
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-700 dark:text-slate-300 hover:bg-[#1e2640] border border-transparent'
              }`}
            >
              All Subjects
            </button>
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSubjectChange(s.id)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                  activeSubject === s.id
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-700 dark:text-slate-300 hover:bg-[#1e2640] border border-transparent'
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}

        {cardsLoading ? (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        ) : flashcards.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🃏</div>
            <p className="text-slate-600 dark:text-slate-400 font-medium">No flashcards yet</p>
            <p className="text-slate-600 text-sm mt-2">
              Start a study session and ask the agent to create flashcards from your notes.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {/* To Review */}
            {unreviewedCards.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <h2 className="text-base font-semibold text-slate-700 dark:text-slate-300">To Review</h2>
                  <Badge color="yellow">{unreviewedCards.length}</Badge>
                </div>
                <div className="space-y-6">
                  {pagedUpcoming.map((card) => (
                    <div key={card.id} className="glass rounded-2xl p-5">
                      <FlashCardComponent card={card} onMarkDone={markDone} />
                    </div>
                  ))}
                </div>
                <Pagination total={unreviewedCards.length} page={upcomingPage} onPage={setUpcomingPage} />
              </section>
            )}

            {unreviewedCards.length === 0 && reviewedCards.length > 0 && (
              <div className="text-center py-12">
                <div className="text-5xl mb-4">🎉</div>
                <p className="text-slate-800 dark:text-slate-200 font-medium text-xl">All caught up!</p>
                <p className="text-slate-600 dark:text-slate-400 text-sm mt-2">
                  You have completed all your upcoming flashcards.
                </p>
              </div>
            )}

            {/* Done */}
            {reviewedCards.length > 0 && (
              <section className="mt-12 border-t border-slate-200 dark:border-slate-800 pt-8">
                <div className="flex items-center gap-2 mb-4">
                  <h2 className="text-base font-semibold text-slate-700 dark:text-slate-300">Done</h2>
                  <Badge color="green">{reviewedCards.length}</Badge>
                </div>
                <div className="space-y-6 opacity-80">
                  {pagedDone.map((card) => (
                    <div key={card.id} className="glass rounded-2xl p-5">
                      <FlashCardComponent card={card} onMarkDone={markDone} />
                    </div>
                  ))}
                </div>
                <Pagination total={reviewedCards.length} page={donePage} onPage={setDonePage} />
              </section>
            )}
          </div>
        )}
      </main>
    </>
  );
}
