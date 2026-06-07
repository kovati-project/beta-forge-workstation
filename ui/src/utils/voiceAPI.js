/**
 * Voice API Client
 * Wrapper for Whisper STT and Piper TTS endpoints
 */

export const voiceAPI = {
  async getStatus() {
    const res = await fetch('/api/voice/status');
    if (!res.ok) throw new Error(`Status: ${res.status}`);
    return res.json();
  },

  async transcribeAudio(audioBlob, filename = 'audio.wav') {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);

    const res = await fetch('/api/voice/transcribe', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error(`Transcribe: ${res.status}`);
    return res.json();
  },

  async synthesizeSpeech(text, voice = 'en_US-lessac-high') {
    const res = await fetch('/api/voice/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice }),
    });

    if (!res.ok) throw new Error(`Synthesize: ${res.status}`);
    return res.blob();
  },

  async getVoices() {
    const res = await fetch('/api/voice/voices');
    if (!res.ok) throw new Error(`Voices: ${res.status}`);
    return res.json();
  },

  async getModels() {
    const res = await fetch('/api/voice/models');
    if (!res.ok) throw new Error(`Models: ${res.status}`);
    return res.json();
  },

  /**
   * Record audio from user's microphone
   * Returns Blob when recording stops
   */
  startRecording() {
    return new Promise(async (resolve, reject) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        const chunks = [];

        mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
        mediaRecorder.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/wav' });
          stream.getTracks().forEach(track => track.stop());
          resolve({ blob, stop: () => mediaRecorder.stop() });
        };

        mediaRecorder.start();
        resolve({ recorder: mediaRecorder, stop: () => mediaRecorder.stop() });
      } catch (err) {
        reject(err);
      }
    });
  },

  /**
   * Play audio blob
   */
  playAudio(blob) {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
    return audio;
  },
};
