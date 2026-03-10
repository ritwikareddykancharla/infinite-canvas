import { useState, useCallback, useRef } from 'react';

const GENRES = ['noir', 'romcom', 'horror', 'scifi'];
const BEATS = ['opening', 'confrontation', 'climax'];

export default function useSceneState() {
  const [currentGenre, setCurrentGenre] = useState('noir');
  const [currentBeat, setCurrentBeat] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [narrativeHistory, setNarrativeHistory] = useState([]);
  const transitionTimer = useRef(null);

  const recordHistory = useCallback((genre, beat) => {
    setNarrativeHistory((prev) => [
      ...prev,
      { genre, beat: BEATS[beat], timestamp: Date.now() },
    ]);
  }, []);

  const setGenre = useCallback(
    (newGenre) => {
      if (!GENRES.includes(newGenre) || newGenre === currentGenre) return;
      if (transitionTimer.current) clearTimeout(transitionTimer.current);

      recordHistory(currentGenre, currentBeat);
      setIsTransitioning(true);

      transitionTimer.current = setTimeout(() => {
        setCurrentGenre(newGenre);
        setIsTransitioning(false);
      }, 800);
    },
    [currentGenre, currentBeat, recordHistory]
  );

  const nextBeat = useCallback(() => {
    setCurrentBeat((prev) => {
      const next = Math.min(prev + 1, BEATS.length - 1);
      recordHistory(currentGenre, prev);
      return next;
    });
  }, [currentGenre, recordHistory]);

  const resetScene = useCallback(() => {
    setNarrativeHistory((prev) => [
      ...prev,
      { genre: currentGenre, beat: BEATS[currentBeat], timestamp: Date.now() },
    ]);
    setCurrentGenre('noir');
    setCurrentBeat(0);
    setIsTransitioning(false);
  }, [currentGenre, currentBeat]);

  return {
    currentGenre,
    currentBeat,
    beatName: BEATS[currentBeat],
    isTransitioning,
    narrativeHistory,
    setGenre,
    nextBeat,
    resetScene,
    GENRES,
    BEATS,
  };
}
