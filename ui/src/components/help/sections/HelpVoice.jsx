import { Panel } from '../../Panel';

export function HelpVoice() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Voice</h2>
        <p className="help-section-subtitle">
          The Voice page provides in-browser speech-to-text (STT) via Whisper and text-to-speech (TTS) via Piper. Use it to transcribe audio or synthesize spoken output from any text.
        </p>
      </div>

      <Panel title="Prerequisites">
        <div className="help-body">
          <p>Both services must be running before the Voice page is functional:</p>
          <ul>
            <li><strong>Whisper STT</strong> (port 9099) — for speech-to-text transcription</li>
            <li><strong>Piper TTS</strong> (port 5000) — for text-to-speech synthesis</li>
          </ul>
          <p>Go to <span className="help-code">/#/tools</span> → Voice I/O group and start both services if the status indicators on the Voice page show them as offline.</p>
          <div className="help-tip">
            <strong>Tip:</strong> Whisper uses the GPU for inference. Ensure a loadout with at least one free GPU is active — Whisper works on GPU 0 even while <span className="help-code">inference-pair-a</span> is active (since pair-a uses GPU 0+3 but Whisper can share GPU 0 via time-slicing).
          </div>
        </div>
      </Panel>

      <Panel title="Recording Audio (Speech-to-Text)">
        <ol className="help-steps">
          <li className="help-step">
            <span className="help-step-number">1</span>
            <div className="help-step-body">
              <strong>Allow microphone access</strong>
              The first time you use Voice, your browser will prompt for microphone permission. Click Allow. If you accidentally deny it, go to browser site settings and reset the permission.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">2</span>
            <div className="help-step-body">
              <strong>Click Record</strong>
              The button changes to a red Stop button while recording. Speak clearly into your microphone.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">3</span>
            <div className="help-step-body">
              <strong>Click Stop</strong>
              The audio is sent to Whisper for transcription. The resulting text appears in the Voice History below.
            </div>
          </li>
        </ol>
      </Panel>

      <Panel title="Text-to-Speech">
        <div className="help-body">
          <p>Each transcribed entry in the Voice History has a <strong>Speak</strong> button. Clicking it sends the text to Piper TTS and plays the audio through your browser.</p>
          <p>Use the <strong>Voice selection dropdown</strong> to change the TTS voice before playback. Available voices depend on which Piper voice models are installed (e.g., <span className="help-code">en_US-lessac-high</span>, <span className="help-code">en_US-ryan-high</span>).</p>
        </div>
      </Panel>

      <Panel title="Voice History">
        <div className="help-body">
          <p>A chronological list of all transcribed interactions in the current session. Each entry shows:</p>
          <ul>
            <li>Timestamp of the recording</li>
            <li>Transcribed text</li>
            <li>Speak button (re-synthesizes the text)</li>
          </ul>
          <p>Click <strong>Clear History</strong> to wipe the transcript log. History is not persisted across page reloads.</p>
        </div>
      </Panel>
    </div>
  );
}
