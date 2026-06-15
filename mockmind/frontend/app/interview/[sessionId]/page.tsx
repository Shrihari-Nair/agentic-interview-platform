'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useRoomContext,
} from '@livekit/components-react';
import '@livekit/components-styles';
import { getSessionToken } from '../../../lib/api';
import type { SessionTokenData } from '../../../types/interview';

export default function InterviewPage() {
  const { sessionId } = useParams() as { sessionId: string };
  const [tokenData, setTokenData] = useState<SessionTokenData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSessionToken(sessionId)
      .then(setTokenData)
      .catch((e) => setError(e.message));
  }, [sessionId]);

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-red-400">
        <div className="text-center">
          <p className="text-xl font-semibold mb-2">Connection error</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!tokenData) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-slate-400">
        <div className="text-center space-y-3">
          <div className="text-4xl animate-pulse">🎙️</div>
          <p>Connecting to interview room...</p>
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      token={tokenData.token}
      serverUrl={tokenData.ws_url}
      connect={true}
      audio={true}
      video={false}
      className="min-h-screen bg-slate-900"
    >
      {/* Required: attaches remote audio tracks to HTML audio elements so you can hear the agent */}
      <RoomAudioRenderer />
      <InterviewRoomUI sessionId={sessionId} />
    </LiveKitRoom>
  );
}

/* ─────────────────────────── Animated Orb ─────────────────────────── */

type OrbState = 'speaking' | 'listening' | 'thinking' | 'disconnected';

const ORB_CONFIG: Record<
  OrbState,
  {
    label: string;
    sublabel: string;
    pill: string;
    dot: string;
    gradient: string;
    ringColor: string;
    ringAnimation: string;
    orbAnimation: string;
  }
> = {
  speaking: {
    label: 'Alex is speaking',
    sublabel: 'Listen carefully.',
    pill: 'bg-blue-600/20 text-blue-300 border border-blue-500/30',
    dot: 'bg-blue-400',
    gradient: 'radial-gradient(circle at 35% 35%, #60a5fa, #2563eb, #1e3a8a)',
    ringColor: 'rgba(96,165,250,',
    ringAnimation: 'orb-ring-speak',
    orbAnimation: 'orb-speak',
  },
  listening: {
    label: 'Your turn to speak',
    sublabel: "Answer clearly — take your time.",
    pill: 'bg-green-600/20 text-green-300 border border-green-500/30',
    dot: 'bg-green-400',
    gradient: 'radial-gradient(circle at 35% 35%, #4ade80, #16a34a, #14532d)',
    ringColor: 'rgba(74,222,128,',
    ringAnimation: 'orb-ring-listen',
    orbAnimation: 'orb-listen',
  },
  thinking: {
    label: 'Processing…',
    sublabel: 'Analyzing your answer.',
    pill: 'bg-amber-600/20 text-amber-300 border border-amber-500/30',
    dot: 'bg-amber-400',
    gradient: 'radial-gradient(circle at 35% 35%, #fcd34d, #d97706, #78350f)',
    ringColor: 'rgba(252,211,77,',
    ringAnimation: 'orb-ring-think',
    orbAnimation: 'orb-think',
  },
  disconnected: {
    label: 'Connecting…',
    sublabel: 'Setting up your interview session.',
    pill: 'bg-slate-700 text-slate-400 border border-slate-600',
    dot: 'bg-slate-500',
    gradient: 'radial-gradient(circle at 35% 35%, #64748b, #334155, #0f172a)',
    ringColor: 'rgba(100,116,139,',
    ringAnimation: '',
    orbAnimation: '',
  },
};

function VoiceOrb({ state }: { state: OrbState }) {
  const cfg = ORB_CONFIG[state];
  const isSpeaking = state === 'speaking';
  const isListening = state === 'listening';
  const isThinking = state === 'thinking';
  const isActive = isSpeaking || isListening || isThinking;

  return (
    <>
      <style>{`
        @keyframes orb-speak {
          0%,100% { transform: scale(1);   filter: brightness(1); }
          25%      { transform: scale(1.07); filter: brightness(1.25); }
          50%      { transform: scale(1.12); filter: brightness(1.1); }
          75%      { transform: scale(1.05); filter: brightness(1.2); }
        }
        @keyframes orb-listen {
          0%,100% { transform: scale(1);    filter: brightness(1); }
          50%     { transform: scale(1.04); filter: brightness(1.1); }
        }
        @keyframes orb-think {
          0%   { transform: scale(1)    rotate(0deg);   filter: brightness(1); }
          50%  { transform: scale(1.05) rotate(180deg); filter: brightness(1.15); }
          100% { transform: scale(1)    rotate(360deg); filter: brightness(1); }
        }
        @keyframes orb-ring-speak {
          0%   { transform: scale(1);   opacity: 0.7; }
          100% { transform: scale(2.4); opacity: 0; }
        }
        @keyframes orb-ring-listen {
          0%   { transform: scale(1);   opacity: 0.45; }
          100% { transform: scale(1.9); opacity: 0; }
        }
        @keyframes orb-ring-think {
          0%   { transform: scale(1);   opacity: 0.35; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes orb-shimmer {
          0%   { background-position: 0%   50%; }
          50%  { background-position: 100% 50%; }
          100% { background-position: 0%   50%; }
        }
      `}</style>

      <div className="relative flex items-center justify-center" style={{ width: 240, height: 240 }}>
        {/* Expanding rings — 3 layers at different delays */}
        {isActive &&
          [0, 0.5, 1.0].map((delay) => (
            <div
              key={delay}
              style={{
                position: 'absolute',
                width: 200,
                height: 200,
                borderRadius: '50%',
                border: `2px solid ${cfg.ringColor}0.6)`,
                animation: `${cfg.ringAnimation} ${
                  isSpeaking ? '1.4s' : isListening ? '2.4s' : '2s'
                } ease-out infinite`,
                animationDelay: `${delay}s`,
                pointerEvents: 'none',
              }}
            />
          ))}

        {/* Orb core */}
        <div
          style={{
            width: 200,
            height: 200,
            borderRadius: '50%',
            background: cfg.gradient,
            boxShadow: isActive
              ? `0 0 60px 20px ${cfg.ringColor}0.35), 0 0 120px 40px ${cfg.ringColor}0.15)`
              : '0 4px 32px rgba(0,0,0,0.4)',
            animation: cfg.orbAnimation
              ? `${cfg.orbAnimation} ${
                  isSpeaking ? '0.9s' : isListening ? '3s' : '2.5s'
                } ease-in-out infinite`
              : undefined,
            transition: 'background 0.6s ease, box-shadow 0.6s ease',
            position: 'relative',
            zIndex: 1,
          }}
        >
          {/* Gloss overlay */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background:
                'radial-gradient(circle at 30% 28%, rgba(255,255,255,0.25) 0%, transparent 55%)',
              pointerEvents: 'none',
            }}
          />
          {/* Inner subtle shimmer for thinking */}
          {isThinking && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                background:
                  'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%, rgba(255,255,255,0.08) 100%)',
                backgroundSize: '200% 200%',
                animation: 'orb-shimmer 2s linear infinite',
                pointerEvents: 'none',
              }}
            />
          )}
        </div>

        {/* Microphone icon for listening state */}
        {isListening && (
          <div
            style={{
              position: 'absolute',
              zIndex: 2,
              color: 'rgba(255,255,255,0.85)',
              fontSize: 40,
              pointerEvents: 'none',
            }}
          >
            🎤
          </div>
        )}
      </div>
    </>
  );
}

/* ─────────────────────────── Room UI ─────────────────────────── */

function InterviewRoomUI({ sessionId }: { sessionId: string }) {
  const { state: agentState } = useVoiceAssistant();
  const room = useRoomContext();
  const router = useRouter();
  const [isEnded, setIsEnded] = useState(false);

  const orbState: OrbState =
    agentState === 'speaking' ||
    agentState === 'listening' ||
    agentState === 'thinking'
      ? agentState
      : 'disconnected';

  const cfg = ORB_CONFIG[orbState];

  const handleEndInterview = () => {
    setIsEnded(true);
    room.disconnect();
    setTimeout(() => {
      router.push(`/report/${sessionId}`);
    }, 2500);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight">MockMind</h1>
          <p className="text-slate-500 text-xs mt-0.5">
            Session · {sessionId.slice(0, 8)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* State pill */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${cfg.pill}`}>
            <span
              className={`w-2 h-2 rounded-full ${cfg.dot} ${
                orbState === 'speaking' ? 'animate-pulse' : ''
              }`}
            />
            {cfg.label}
          </div>
          <button
            onClick={handleEndInterview}
            disabled={isEnded}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors"
          >
            End Interview
          </button>
        </div>
      </header>

      {/* Main — orb centred */}
      <div className="flex-1 flex flex-col items-center justify-center gap-8 p-8">
        <VoiceOrb state={orbState} />

        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold">{cfg.label}</h2>
          <p className="text-slate-400">{cfg.sublabel}</p>
          {orbState === 'listening' && (
            <p className="text-slate-500 text-sm mt-1">
              Take your time — there&apos;s no rush.
            </p>
          )}
        </div>
      </div>

      {/* End overlay */}
      {isEnded && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-3xl p-10 text-gray-800 text-center max-w-sm mx-4 shadow-2xl">
            <div className="text-6xl mb-4">✅</div>
            <h2 className="text-2xl font-bold mb-2">Interview Complete!</h2>
            <p className="text-gray-500">
              Generating your evaluation report...
            </p>
            <div className="mt-4 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full animate-pulse w-3/4" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
