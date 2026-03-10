import React, { useState } from 'react';
import './GenreOverlay.css';

const GENRES = [
  { id: 'noir', label: 'NOIR', emoji: '🎭', hint: 'shadows & secrets' },
  { id: 'romcom', label: 'ROM-COM', emoji: '💕', hint: 'hearts collide' },
  { id: 'horror', label: 'HORROR', emoji: '👁', hint: 'something watches' },
  { id: 'scifi', label: 'SCI-FI', emoji: '🛸', hint: 'futures bleed in' },
];

const BEAT_LABELS = ['Opening', 'Confrontation', 'Climax'];

export default function GenreOverlay({
  currentGenre,
  currentBeat,
  isTransitioning,
  isListening,
  statusMessage,
  onGenreSelect,
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      {/* Top status bar */}
      <div className="status-bar" data-listening={isListening}>
        <div className="beat-indicator">
          {BEAT_LABELS.map((label, i) => (
            <span
              key={label}
              className="beat-dot"
              data-active={i === currentBeat}
              data-past={i < currentBeat}
            />
          ))}
          <span className="beat-label">{BEAT_LABELS[currentBeat]}</span>
        </div>
        <div className="status-message" data-transitioning={isTransitioning}>
          {isListening ? (
            <span className="listening-indicator">
              <span className="dot" />
              Listening...
            </span>
          ) : (
            statusMessage
          )}
        </div>
      </div>

      {/* Genre selector panel */}
      <div className="genre-panel" data-expanded={expanded}>
        <button
          className="genre-toggle"
          onClick={() => setExpanded((e) => !e)}
          aria-label="Toggle genre selector"
        >
          <span className="current-genre-label" data-genre={currentGenre}>
            {GENRES.find((g) => g.id === currentGenre)?.label ?? 'GENRE'}
          </span>
          <span className="toggle-arrow">{expanded ? '▼' : '▲'}</span>
        </button>

        {expanded && (
          <div className="genre-list">
            {GENRES.map(({ id, label, emoji, hint }) => (
              <button
                key={id}
                className="genre-btn"
                data-active={id === currentGenre}
                data-genre={id}
                onClick={() => {
                  onGenreSelect(id);
                  setExpanded(false);
                }}
                disabled={isTransitioning}
              >
                <span className="genre-emoji">{emoji}</span>
                <span className="genre-name">{label}</span>
                <span className="genre-hint">{hint}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Voice command hints */}
      <div className="voice-hints">
        <p>Say: "make it noir" · "she's the villain" · "cyberpunk now" · "reset"</p>
      </div>
    </>
  );
}
