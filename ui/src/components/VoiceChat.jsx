/**
 * Voice Chat Panel - Speech-to-Text & Text-to-Speech
 */

import { useState, useEffect } from 'react';
import { voiceAPI } from '../utils/voiceAPI';
import './VoiceChat.css';

export function VoiceChat() {
  const [status, setStatus] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recorder, setRecorder] = useState(null);
  const [transcript, setTranscript] = useState('');
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('en_US-lessac-high');
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [playingId, setPlayingId] = useState(null);

  // Initialize voice services
  useEffect(() => {
    const init = async () => {
      try {
        const voiceStatus = await voiceAPI.getStatus();
        setStatus(voiceStatus);

        const availableVoices = await voiceAPI.getVoices();
        if (availableVoices && typeof availableVoices === 'object') {
          const voiceList = Object.keys(availableVoices).slice(0, 5);
          setVoices(voiceList);
        }
      } catch (err) {
        setError(`Voice init failed: ${err.message}`);
      }
    };

    init();
  }, []);

  const startRecording = async () => {
    try {
      setError(null);
      const { recorder: rec } = await voiceAPI.startRecording();
      setRecorder(rec);
      setIsRecording(true);
    } catch (err) {
      setError(`Mic access denied: ${err.message}`);
    }
  };

  const stopRecording = async () => {
    if (!recorder) return;

    setIsRecording(false);
    setIsLoading(true);

    try {
      recorder.stop();

      // Wait for ondataavailable event
      await new Promise(resolve => {
        const checkComplete = setInterval(() => {
          if (recorder.state === 'inactive') {
            clearInterval(checkComplete);
            resolve();
          }
        }, 100);
      });

      // Get audio blob and transcribe
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];

      mediaRecorder.ondataavailable = async (e) => {
        chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/wav' });
        stream.getTracks().forEach(track => track.stop());

        try {
          const result = await voiceAPI.transcribeAudio(audioBlob);
          const text = result.text || '';
          setTranscript(text);

          // Add to history
          setHistory(prev => [...prev, {
            id: Date.now(),
            type: 'user',
            text,
            timestamp: new Date().toLocaleTimeString(),
          }]);

          setIsLoading(false);
        } catch (err) {
          setError(`Transcription failed: ${err.message}`);
          setIsLoading(false);
        }
      };

      mediaRecorder.start();
      mediaRecorder.stop();
    } catch (err) {
      setError(`Recording error: ${err.message}`);
      setIsLoading(false);
    }
  };

  const speakText = async (text, id) => {
    try {
      setError(null);
      setPlayingId(id);
      const audioBlob = await voiceAPI.synthesizeSpeech(text, selectedVoice);
      voiceAPI.playAudio(audioBlob);
      setTimeout(() => setPlayingId(null), 3000);
    } catch (err) {
      setError(`TTS failed: ${err.message}`);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    setTranscript('');
  };

  return (
    <div className="voice-chat-container">
      <div className="voice-header">
        <h2>Voice Chat</h2>
        <div className="voice-status">
          <span className={`status-badge ${status?.whisper === 'ready' ? 'ready' : 'error'}`}>
            STT: {status?.whisper === 'ready' ? 'Ready' : 'Offline'}
          </span>
          <span className={`status-badge ${status?.piper === 'ready' ? 'ready' : 'error'}`}>
            TTS: {status?.piper === 'ready' ? 'Ready' : 'Offline'}
          </span>
        </div>
      </div>

      {error && <div className="voice-error">{error}</div>}

      <div className="voice-controls">
        <button
          className={`btn-record ${isRecording ? 'recording' : ''}`}
          onClick={isRecording ? stopRecording : startRecording}
          disabled={status?.whisper !== 'ready' || isLoading}
        >
          {isRecording ? (
            <>
              <span className="recording-dot"></span>
              Recording...
            </>
          ) : (
            <>
              🎤 Start
            </>
          )}
        </button>

        <select
          value={selectedVoice}
          onChange={(e) => setSelectedVoice(e.target.value)}
          className="voice-select"
          disabled={status?.piper !== 'ready'}
        >
          {voices.length > 0 ? (
            voices.map(v => <option key={v} value={v}>{v.replace('en_US-', '')}</option>)
          ) : (
            <option value="en_US-lessac-high">Default</option>
          )}
        </select>

        <button
          className="btn-clear"
          onClick={clearHistory}
          disabled={history.length === 0}
        >
          Clear
        </button>
      </div>

      {transcript && (
        <div className="voice-transcript">
          <label>Transcribed Text</label>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Your speech will appear here..."
            rows="3"
          />
        </div>
      )}

      <div className="voice-history">
        <h3>History</h3>
        {history.length === 0 ? (
          <p className="empty">Start recording to begin voice chat...</p>
        ) : (
          history.map(item => (
            <div key={item.id} className={`history-item ${item.type}`}>
              <span className="timestamp">{item.timestamp}</span>
              <p>{item.text}</p>
              {item.type === 'user' && (
                <button
                  className="btn-speak"
                  onClick={() => speakText(item.text, item.id)}
                  disabled={status?.piper !== 'ready' || playingId === item.id}
                >
                  {playingId === item.id ? '🔊 Playing...' : '🔊 Speak'}
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {isLoading && (
        <div className="voice-loading">
          <div className="spinner"></div>
          <p>Processing audio...</p>
        </div>
      )}
    </div>
  );
}
