'use client';
import { useState } from 'react';
import type { Flashcard } from '@/types';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface Props {
  card: Flashcard;
  onReview: (id: string, quality: number) => Promise<void>;
}

export default function FlashCardComponent({ card, onReview }: Props) {
  const [flipped, setFlipped] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [done, setDone] = useState(false);

  const isDue = new Date(card.next_review) <= new Date();

  const handleReview = async (quality: number) => {
    setReviewing(true);
    try {
      await onReview(card.id, quality);
      setDone(true);
    } finally {
      setReviewing(false);
    }
  };

  if (done) {
    return (
      <div className="h-56 flex items-center justify-center rounded-2xl border border-[#1f2d4a] bg-[#161d2e]">
        <div className="text-center text-slate-500">
          <div className="text-3xl mb-2">✓</div>
          <p className="text-sm">Reviewed</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Due badge */}
      <div className="flex items-center gap-2">
        {isDue && <Badge color="yellow">Due now</Badge>}
        {card.topic && <Badge color="slate">{card.topic}</Badge>}
        <Badge color="indigo">{card.card_type}</Badge>
        <span className="text-xs text-slate-600 ml-auto">
          Rep #{card.repetitions} · EF {card.easiness_factor.toFixed(2)}
        </span>
      </div>

      {/* Card */}
      <div
        className={`flip-card h-56 cursor-pointer ${flipped ? 'flipped' : ''}`}
        onClick={() => setFlipped(!flipped)}
      >
        <div className="flip-card-inner">
          {/* Front — question */}
          <div className="flip-card-front bg-[#161d2e] border border-[#1f2d4a] p-6 flex flex-col items-center justify-center text-center">
            <p className="text-xs text-indigo-400 font-medium mb-3 uppercase tracking-wide">Question</p>
            <p className="text-slate-100 text-base font-medium leading-relaxed">{card.question}</p>
            <p className="text-xs text-slate-600 mt-4">Click to reveal answer</p>
          </div>

          {/* Back — answer */}
          <div className="flip-card-back bg-gradient-to-br from-indigo-900/40 to-purple-900/30 border border-indigo-500/30 p-6 flex flex-col items-center justify-center text-center">
            <p className="text-xs text-purple-400 font-medium mb-3 uppercase tracking-wide">Answer</p>
            <p className="text-slate-100 text-base leading-relaxed">{card.answer}</p>
          </div>
        </div>
      </div>

      {/* Review buttons — only after flip */}
      {flipped && (
        <div className="flex gap-3 fade-in">
          <Button
            variant="danger"
            loading={reviewing}
            onClick={() => handleReview(1)}
            className="flex-1"
          >
            ✗ Didn&apos;t Know
          </Button>
          <Button
            variant="secondary"
            loading={reviewing}
            onClick={() => handleReview(3)}
            className="flex-1"
          >
            ~ Kinda Knew
          </Button>
          <Button
            variant="success"
            loading={reviewing}
            onClick={() => handleReview(5)}
            className="flex-1"
          >
            ✓ Knew It
          </Button>
        </div>
      )}
    </div>
  );
}
