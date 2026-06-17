import { useState, useEffect, useRef } from 'react';

/**
 * A hook that progressively reveals text character-by-character to produce
 * a smooth typewriter / ChatGPT-style streaming effect.
 *
 * @param targetText  — the full (or partial) text that has arrived so far
 * @param isActive    — whether we are currently streaming (typewriter runs)
 * @param charsPerTick — how many characters to reveal per animation frame tick
 *                       (higher = faster typing; default 3 for a natural pace)
 */
export function useTypewriter(
  targetText: string,
  isActive: boolean,
  charsPerTick: number = 3,
) {
  const [displayedText, setDisplayedText] = useState('');
  const indexRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef(0);

  // Reset when text is cleared (new message)
  useEffect(() => {
    if (!targetText) {
      indexRef.current = 0;
      setDisplayedText('');
    }
  }, [targetText]);

  useEffect(() => {
    if (!isActive) {
      // When streaming ends, immediately show all remaining text
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      setDisplayedText(targetText);
      indexRef.current = targetText.length;
      return;
    }

    const tick = (timestamp: number) => {
      // Throttle to ~30ms per tick for a natural reading pace
      if (timestamp - lastTimeRef.current < 30) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      lastTimeRef.current = timestamp;

      const current = indexRef.current;
      if (current < targetText.length) {
        const next = Math.min(current + charsPerTick, targetText.length);
        indexRef.current = next;
        setDisplayedText(targetText.slice(0, next));
        rafRef.current = requestAnimationFrame(tick);
      } else {
        // Caught up — wait for more text
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [targetText, isActive, charsPerTick]);

  return displayedText;
}
