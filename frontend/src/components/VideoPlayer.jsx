import React, { useRef, useEffect, useState, useCallback } from 'react';
import { WebGLTransitionEngine } from '../utils/webgl-transitions';
import './VideoPlayer.css';

const ASSET_BASE = process.env.REACT_APP_ASSET_BASE_URL || '/assets/video';
const BEAT_NAMES = ['opening', 'confrontation', 'climax'];

function getVideoUrl(genre, beat) {
  return `${ASSET_BASE}/${genre}_${BEAT_NAMES[beat]}.mp4`;
}

export default function VideoPlayer({ genre, beat, isTransitioning, onSceneEnd }) {
  const canvasRef = useRef(null);
  const currentVideoRef = useRef(null);
  const nextVideoRef = useRef(null);
  const engineRef = useRef(null);
  const rafRef = useRef(null);
  const [currentSrc, setCurrentSrc] = useState(null);
  const prevGenreRef = useRef(genre);
  const prevBeatRef = useRef(beat);

  // Initialize WebGL engine
  useEffect(() => {
    if (!canvasRef.current) return;
    engineRef.current = new WebGLTransitionEngine(canvasRef.current);
    return () => engineRef.current?.destroy();
  }, []);

  // Render loop — draws current video frame to canvas
  const startRenderLoop = useCallback((videoEl) => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const render = () => {
      if (videoEl && !videoEl.paused && !videoEl.ended) {
        engineRef.current?.drawFrame(videoEl);
      }
      rafRef.current = requestAnimationFrame(render);
    };
    rafRef.current = requestAnimationFrame(render);
  }, []);

  // Load new video source
  const loadVideo = useCallback((src, videoEl) => {
    return new Promise((resolve) => {
      videoEl.src = src;
      videoEl.load();
      videoEl.oncanplay = () => resolve(videoEl);
      videoEl.onerror = () => resolve(videoEl); // graceful fallback
    });
  }, []);

  // Initial load
  useEffect(() => {
    const src = getVideoUrl(genre, beat);
    setCurrentSrc(src);
    const video = currentVideoRef.current;
    if (!video) return;
    loadVideo(src, video).then(() => {
      video.play().catch(() => {});
      startRenderLoop(video);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle genre/beat changes — perform WebGL transition
  useEffect(() => {
    const genreChanged = genre !== prevGenreRef.current;
    const beatChanged = beat !== prevBeatRef.current;
    if (!genreChanged && !beatChanged) return;

    const fromGenre = prevGenreRef.current;
    const newSrc = getVideoUrl(genre, beat);
    prevGenreRef.current = genre;
    prevBeatRef.current = beat;

    const fromVideo = currentVideoRef.current;
    const toVideo = nextVideoRef.current;
    if (!fromVideo || !toVideo) return;

    loadVideo(newSrc, toVideo).then(() => {
      toVideo.play().catch(() => {});
      if (rafRef.current) cancelAnimationFrame(rafRef.current);

      engineRef.current
        ?.transition(fromVideo, toVideo, fromGenre, genre, 800)
        .then(() => {
          // Swap refs after transition
          fromVideo.pause();
          fromVideo.src = newSrc;
          setCurrentSrc(newSrc);
          startRenderLoop(toVideo);
          // swap DOM roles
          const tmp = currentVideoRef.current;
          currentVideoRef.current = nextVideoRef.current;
          nextVideoRef.current = tmp;
        });
    });
  }, [genre, beat, loadVideo, startRenderLoop]);

  const handleVideoEnd = useCallback(() => {
    onSceneEnd?.();
  }, [onSceneEnd]);

  return (
    <div className="video-player">
      <canvas
        ref={canvasRef}
        className="video-canvas"
        width={1280}
        height={720}
      />
      {/* Hidden video elements used as WebGL texture sources */}
      <video
        ref={currentVideoRef}
        className="video-source"
        onEnded={handleVideoEnd}
        playsInline
        muted
        crossOrigin="anonymous"
      />
      <video
        ref={nextVideoRef}
        className="video-source"
        playsInline
        muted
        crossOrigin="anonymous"
      />
      {isTransitioning && <div className="transition-flash" />}
    </div>
  );
}
