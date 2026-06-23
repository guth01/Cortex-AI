'use client';
import { useState } from 'react';
import type { Flashcard } from '@/types';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface Props {
  card: Flashcard;
  onMarkDone: (id: string) => Promise<void>;
}

export default function FlashCardComponent({ card, onMarkDone }: Props) {
  const [flipped, setFlipped] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const handleMarkDone = async () => {
    setReviewing(true);
    try {
      await onMarkDone(card.id);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Due badge */}
      <div className="flex items-center gap-2">
        {card.topic && <Badge color="slate">{card.topic}</Badge>}
        <Badge color="indigo">{card.card_type}</Badge>
        {card.status === 'done' && <Badge color="green">Done</Badge>}
      </div>

      {/* Card */}
      <div
        className={`flip-card h-56 cursor-pointer ${flipped ? 'flipped' : ''}`}
        onClick={() => setFlipped(!flipped)}
      >
        <div className="flip-card-inner">
          {/* Front — question */}
          <div className="flip-card-front bg-white dark:bg-[#161d2e] border border-slate-200 dark:border-[#1f2d4a] p-6 flex flex-col items-center justify-center text-center">
            <p className="text-xs text-indigo-400 font-medium mb-3 uppercase tracking-wide">Question</p>
            <p className="text-slate-900 dark:text-slate-100 text-base font-medium leading-relaxed">{card.question}</p>
            <p className="text-xs text-slate-600 mt-4">Click to reveal answer</p>
          </div>

          {/* Back — answer */}
          <div className="flip-card-back bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/40 dark:to-purple-900/30 border border-indigo-200 dark:border-indigo-500/30 p-6 flex flex-col items-center justify-center text-center">
            <p className="text-xs text-purple-400 font-medium mb-3 uppercase tracking-wide">Answer</p>
            <p className="text-slate-900 dark:text-slate-100 text-base leading-relaxed">{card.answer}</p>
          </div>
        </div>
      </div>

      {/* Review buttons — only after flip */}
      {flipped && card.status === 'upcoming' && (
        <div className="flex gap-3 fade-in mt-4">
          <Button
            variant="success"
            loading={reviewing}
            onClick={handleMarkDone}
            className="w-full"
          >
            ✓ Mark as Done
          </Button>
        </div>
      )}
    </div>
  );
}
