import React, { useState, useEffect, useCallback } from 'react';
import VideoPlayer from './components/VideoPlayer';
import VoiceController from './components/VoiceController';
import GenreOverlay from './components/GenreOverlay';
import DirectorCommentary from './components/DirectorCommentary';
import useSceneState from './hooks/useSceneState';
import './styles/App.css';

export default function App() {
  const {
    currentGenre,
    currentBeat,
    isTransitioning,
    narrativeHistory,
    setGenre,
    nextBeat,
    resetScene,
  } = useSceneState();

  const [isListening, setIsListening] = useState(false);
  const [showCommentary, setShowCommentary] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Speak to reshape reality');
  const [wsConnected, setWsConnected] = useState(false);

  const handleIntentReceived = useCallback(
    (intent) => {
      if (intent.genre && intent.genre !== currentGenre) {
        setStatusMessage(`Morphing to ${intent.genre.toUpperCase()}...`);
        setGenre(intent.genre);
      } else if (intent.action === 'next_beat') {
        nextBeat();
      } else if (intent.action === 'reset') {
        resetScene();
        setStatusMessage('Reality reset. A new story begins.');
      } else if (intent.feedback) {
        setStatusMessage(intent.feedback);
      }
    },
    [currentGenre, setGenre, nextBeat, resetScene]
  );

  const handleSceneEnd = useCallback(() => {
    if (currentBeat < 2) {
      nextBeat();
    } else {
      setShowCommentary(true);
    }
  }, [currentBeat, nextBeat]);

  useEffect(() => {
    if (!isTransitioning) {
      const genreLabels = {
        noir: 'Shadows and secrets...',
        romcom: 'Hearts collide...',
        horror: 'Something watches...',
        scifi: 'The future bleeds in...',
      };
      setStatusMessage(genreLabels[currentGenre] || 'Speak to reshape reality');
    }
  }, [currentGenre, isTransitioning]);

  return (
    <div className="canvas-container" data-genre={currentGenre}>
      <VideoPlayer
        genre={currentGenre}
        beat={currentBeat}
        isTransitioning={isTransitioning}
        onSceneEnd={handleSceneEnd}
      />

      <GenreOverlay
        currentGenre={currentGenre}
        currentBeat={currentBeat}
        isTransitioning={isTransitioning}
        isListening={isListening}
        statusMessage={statusMessage}
        onGenreSelect={setGenre}
      />

      <VoiceController
        onIntentReceived={handleIntentReceived}
        onListeningChange={setIsListening}
        onConnectionChange={setWsConnected}
        currentGenre={currentGenre}
        currentBeat={currentBeat}
      />

      {showCommentary && (
        <DirectorCommentary
          narrativeHistory={narrativeHistory}
          onClose={() => setShowCommentary(false)}
          onRestart={resetScene}
        />
      )}

      <div className="ws-status" data-connected={wsConnected}>
        {wsConnected ? '● LIVE' : '○ CONNECTING'}
      </div>
    </div>
  );
}
