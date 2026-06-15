import { useVoiceAssistant, useConnectionState } from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';

export type AgentState = 'speaking' | 'listening' | 'thinking' | 'disconnected';

export function useInterviewSession() {
  const { state: rawState, audioTrack } = useVoiceAssistant();
  const connectionState = useConnectionState();

  const isConnected = connectionState === ConnectionState.Connected;

  const agentState: AgentState =
    !isConnected
      ? 'disconnected'
      : rawState === 'speaking'
        ? 'speaking'
        : rawState === 'thinking'
          ? 'thinking'
          : 'listening';

  return {
    agentState,
    audioTrack,
    isConnected,
  };
}
