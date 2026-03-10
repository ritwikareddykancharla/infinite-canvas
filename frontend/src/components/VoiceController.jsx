import React, { useEffect, useCallback, useState } from 'react';
import useGeminiLive from '../hooks/useGeminiLive';
import './VoiceController.css';

export default function VoiceController({
  onIntentReceived,
  onListeningChange,
  onConnectionChange,
  currentGenre,
  currentBeat,
}) {
  const [permissionGranted, setPermissionGranted] = useState(null);
  const [micError, setMicError] = useState(null);

  const handleIntent = useCallback(
    (intent) => {
      onIntentReceived?.(intent);
    },
    [onIntentReceived]
  );

  const { startCapture, stopCapture, isCapturing, connect } = useGeminiLive({
    onIntent: handleIntent,
    onListeningChange,
    onConnectionChange,
  });

  const requestMicAndStart = useCallback(async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      setPermissionGranted(true);
      setMicError(null);
      await startCapture();
    } catch (err) {
      setPermissionGranted(false);
      setMicError('Microphone access is required for voice control.');
    }
  }, [startCapture]);

  // Auto-request mic on mount
  useEffect(() => {
    requestMicAndStart();
    return () => stopCapture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (micError) {
    return (
      <div className="voice-error">
        <span>{micError}</span>
        <button onClick={requestMicAndStart}>Grant Access</button>
      </div>
    );
  }

  return (
    <div className="voice-controller" data-active={isCapturing}>
      <div className="mic-indicator" data-active={isCapturing} aria-label="Microphone active">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
      </div>
    </div>
  );
}
