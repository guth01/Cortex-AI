'use client';
import { useState } from 'react';
import Navbar from '@/components/Navbar';
import FlashCardComponent from '@/components/FlashCard';
import Spinner from '@/components/ui/Spinner';
import Badge from '@/components/ui/Badge';
import { useSubjects } from '@/lib/hooks/useSubjects';
import { useFlashcards } from '@/lib/hooks/useFlashcards';

export default function FlashcardsPage() {
  const { subjects, loading: subjectsLoading } = useSubjects();
  const [activeSubject, setActiveSubject] = useState<string>('all');

  const subjectIdFilter = activeSubject === 'all' ? undefined : activeSubject;
  const { flashcards, loading: cardsLoading, reviewCard } = useFlashcards(subjectIdFilter);

  const unreviewedCards = flashcards.filter((c) => c.repetitions === 0);
  const reviewedCards = flashcards.filter((c) => c.repetitions > 0);

  return (
    <>
      <Navbar />
      <main className="pt-24 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-100">Flashcards</h1>
          </div>
          <div className="flex gap-3">
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{unreviewedCards.length}</p>
              <p className="text-xs text-slate-600">To Review</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-400">{reviewedCards.length}</p>
              <p className="text-xs text-slate-600">Done</p>
            </div>
          </div>
        </div>

        {/* Subject tabs */}
        {!subjectsLoading && (
          <div className="flex gap-2 mb-8 overflow-x-auto pb-1">
            <button
              onClick={() => setActiveSubject('all')}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                activeSubject === 'all'
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-[#1e2640] border border-transparent'
              }`}
            >
              All Subjects
            </button>
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSubject(s.id)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                  activeSubject === s.id
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-[#1e2640] border border-transparent'
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
            <p className="text-slate-400 font-medium">No flashcards yet</p>
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
                  <h2 className="text-base font-semibold text-slate-300">To Review</h2>
                  <Badge color="yellow">{unreviewedCards.length}</Badge>
                </div>
                <div className="space-y-6">
                  {unreviewedCards.map((card) => (
                    <div key={card.id} className="glass rounded-2xl p-5">
                      <FlashCardComponent card={card} onReview={reviewCard} />
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Note: Reviewed cards are intentionally hidden from this view to keep it clean */}
            {unreviewedCards.length === 0 && reviewedCards.length > 0 && (
              <div className="text-center py-16">
                <div className="text-5xl mb-4">🎉</div>
                <p className="text-slate-200 font-medium text-xl">All caught up!</p>
                <p className="text-slate-500 text-sm mt-2">
                  You have reviewed all {reviewedCards.length} flashcards for this subject.
                </p>
              </div>
            )}
          </div>
        )}
      </main>
    </>
  );
}
