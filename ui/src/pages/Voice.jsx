/**
 * Voice Page - Speech-to-Text & Text-to-Speech Integration
 * Routes to /#/voice in the main dashboard
 */

import { VoiceChat } from '../components/VoiceChat';
import './Voice.css';

export function Voice() {
  return (
    <div className="voice-page">
      <VoiceChat />
    </div>
  );
}
