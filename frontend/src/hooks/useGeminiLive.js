/**
 * useGeminiLive — connects to backend WebSocket which proxies Gemini Live API.
 * The backend handles the actual Gemini Live session; this hook manages
 * the browser-side audio capture and intent parsing communication.
 */
import { useRef, useCallback, useEffect, useState } from 'react';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/voice';
const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

export default function useGeminiLive({ onIntent, onListeningChange, onConnectionChange }) {
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const [isCapturing, setIsCapturing] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      onConnectionChange?.(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'listening_start') {
          onListeningChange?.(true);
        } else if (data.type === 'listening_end') {
          onListeningChange?.(false);
        } else if (data.type === 'intent') {
          onIntent?.(data.intent);
        }
      } catch {
        // non-JSON message, ignore
      }
    };

    ws.onclose = () => {
      onConnectionChange?.(false);
      onListeningChange?.(false);
      attemptReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onIntent, onListeningChange, onConnectionChange]);

  const attemptReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) return;
    reconnectAttemptsRef.current += 1;
    const delay = RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current - 1);
    reconnectTimerRef.current = setTimeout(connect, delay);
  }, [connect]);

  const startCapture = useCallback(async () => {
    if (isCapturing) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
      });
      streamRef.current = stream;

      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        // Convert float32 to int16 PCM
        const pcm = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcm[i] = Math.max(-32768, Math.min(32767, Math.round(inputData[i] * 32767)));
        }
        wsRef.current.send(pcm.buffer);
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setIsCapturing(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  }, [isCapturing]);

  const stopCapture = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsCapturing(false);
  }, []);

  const disconnect = useCallback(() => {
    stopCapture();
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS; // prevent reconnect
    wsRef.current?.close();
  }, [stopCapture]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { startCapture, stopCapture, isCapturing, connect };
}
