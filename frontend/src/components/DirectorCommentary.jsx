import React, { useMemo } from 'react';
import './DirectorCommentary.css';

const GENRE_LABELS = { noir: 'Noir', romcom: 'Rom-Com', horror: 'Horror', scifi: 'Sci-Fi' };
const BEAT_LABELS = { opening: 'Opening', confrontation: 'Confrontation', climax: 'Climax' };

export default function DirectorCommentary({ narrativeHistory, onClose, onRestart }) {
  const stats = useMemo(() => {
    const counts = { noir: 0, romcom: 0, horror: 0, scifi: 0 };
    narrativeHistory.forEach(({ genre }) => {
      if (genre in counts) counts[genre]++;
    });
    const total = narrativeHistory.length || 1;
    const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return { counts, total, dominant };
  }, [narrativeHistory]);

  const personalityLine = useMemo(() => {
    const [genre] = stats.dominant;
    const lines = {
      noir: 'You gravitate toward shadows. A storyteller of moral ambiguity.',
      romcom: 'You believe in connection. Every story is a love story.',
      horror: 'You stare into the dark. The tension is your natural habitat.',
      scifi: 'You reach for the impossible. The future is your canvas.',
    };
    return lines[genre] || 'Your narrative path was singular.';
  }, [stats]);

  return (
    <div className="commentary-overlay">
      <div className="commentary-panel">
        <div className="commentary-header">
          <h2>DIRECTOR'S COMMENTARY</h2>
          <p className="subtitle">Your unique path through the possibility space</p>
        </div>

        <div className="narrative-path">
          <h3>YOUR NARRATIVE PATH</h3>
          <div className="path-timeline">
            {narrativeHistory.map(({ genre, beat, timestamp }, i) => (
              <div key={timestamp} className="path-node" data-genre={genre}>
                <span className="path-index">{i + 1}</span>
                <span className="path-genre">{GENRE_LABELS[genre]}</span>
                <span className="path-beat">· {BEAT_LABELS[beat]}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="genre-stats">
          <h3>GENRE DISTRIBUTION</h3>
          <div className="stats-bars">
            {Object.entries(stats.counts).map(([genre, count]) => (
              <div key={genre} className="stat-row">
                <span className="stat-label" data-genre={genre}>
                  {GENRE_LABELS[genre]}
                </span>
                <div className="stat-bar-track">
                  <div
                    className="stat-bar-fill"
                    data-genre={genre}
                    style={{ width: `${(count / stats.total) * 100}%` }}
                  />
                </div>
                <span className="stat-pct">
                  {Math.round((count / stats.total) * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="personality-read">
          <p>{personalityLine}</p>
        </div>

        <div className="commentary-actions">
          <button className="btn-restart" onClick={onRestart}>
            RESHAPE REALITY
          </button>
          <button className="btn-close" onClick={onClose}>
            CLOSE
          </button>
        </div>
      </div>
    </div>
  );
}
