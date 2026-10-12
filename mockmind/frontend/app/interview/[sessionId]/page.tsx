'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useVoiceAssistant,
  useRoomContext,
  useConnectionState,
} from '@livekit/components-react';
import { ConnectionState } from 'livekit-client';
import '@livekit/components-styles';
import { Mic, MicOff, CheckCircle2, AlertTriangle } from 'lucide-react';
import { getSessionToken } from '../../../lib/api';
import type { SessionTokenData } from '../../../types/interview';
import { AuroraBackground } from '../../../components/AuroraBackground';
import { CodeEditorPanel, type CodingChallenge } from '../../../components/CodeEditorPanel';

type MicState = 'checking' | 'granted' | 'denied' | 'unsupported';

/** Ask for the mic *before* joining the room, so a blocked/missing microphone
 * shows a clear fix instead of an interview that silently can't hear you. */
async function checkMicrophone(): Promise<MicState> {
  if (!navigator.mediaDevices?.getUserMedia) return 'unsupported';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
    return 'granted';
  } catch {
    return 'denied';
  }
}

export default function InterviewPage() {
  const { sessionId } = useParams() as { sessionId: string };
  const [tokenData, setTokenData] = useState<SessionTokenData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mic, setMic] = useState<MicState>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setMic('checking');
    setError(null);
    checkMicrophone().then((result) => {
      if (cancelled) return;
      setMic(result);
      if (result !== 'granted') return;
      getSessionToken(sessionId)
        .then((t) => !cancelled && setTokenData(t))
        .catch((e) => !cancelled && setError(e.message));
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId, attempt]);

  if (mic === 'denied' || mic === 'unsupported') {
    return (
      <div className="relative flex items-center justify-center min-h-screen bg-slate-900 text-white overflow-hidden p-6">
        <AuroraBackground subtle />
        <div className="relative z-10 text-center space-y-4 max-w-md">
          <MicOff className="w-12 h-12 mx-auto text-amber-400" />
          <h2 className="font-display text-2xl font-bold">
            {mic === 'denied' ? 'Microphone access is blocked' : 'Microphone not available'}
          </h2>
          <p className="text-slate-400">
            {mic === 'denied'
              ? 'MockMind is a voice interview, so it needs your microphone. Click the lock or camera icon in your browser’s address bar, allow the microphone for this site, then try again.'
              : 'This browser can’t access a microphone here. Use a current version of Chrome, Edge, Safari or Firefox, and open the site over HTTPS (or localhost).'}
          </p>
          <button
            onClick={() => setAttempt((n) => n + 1)}
            className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold rounded-xl transition-all duration-300 hover:scale-[1.03] active:scale-[0.98]"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-red-400">
        <div className="text-center">
          <p className="text-xl font-semibold mb-2">Connection error</p>
          <p className="text-sm">{error}</p>
          <button
            onClick={() => setAttempt((n) => n + 1)}
            className="mt-4 px-4 py-2 border border-white/15 text-slate-200 rounded-xl text-sm hover:bg-white/5"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!tokenData) {
    return (
      <div className="relative flex items-center justify-center min-h-screen bg-slate-900 text-slate-400 overflow-hidden">
        <AuroraBackground subtle />
        <div className="relative z-10 text-center space-y-3">
          <Mic className="w-10 h-10 mx-auto animate-pulse text-blue-400" />
          <p>{mic === 'checking' ? 'Checking your microphone...' : 'Connecting to interview room...'}</p>
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
          <Mic
            style={{ position: 'absolute', zIndex: 2, pointerEvents: 'none' }}
            className="w-10 h-10 text-white/85"
          />
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
  const [challenge, setChallenge] = useState<CodingChallenge | null>(null);
  const connectionState = useConnectionState();
  const [agentTimedOut, setAgentTimedOut] = useState(false);
  const [wasConnected, setWasConnected] = useState(false);

  useDataChannel('coding_challenge', (msg) => {
    try {
      const payload = JSON.parse(new TextDecoder().decode(msg.payload));
      if (payload.type === 'show_editor') {
        setChallenge(payload as CodingChallenge);
      }
    } catch {
      // ignore malformed data messages
    }
  });

  const { send: sendCodeSubmission } = useDataChannel('code_submission');

  const handleSubmitCode = useCallback(
    (code: string) => {
      if (!challenge) return;
      const payload = JSON.stringify({ question_id: challenge.question_id, code });
      sendCodeSubmission(new TextEncoder().encode(payload), { reliable: true });
      // Hide the editor once submitted — Alex reacts out loud next (the
      // voice orb's "thinking" state covers the review time), same as any
      // other answer. Agent sends a fresh "show_editor" for the next one.
      setChallenge(null);
    },
    [challenge, sendCodeSubmission],
  );

  const orbState: OrbState =
    agentState === 'speaking' ||
    agentState === 'listening' ||
    agentState === 'thinking'
      ? agentState
      : 'disconnected';

  const cfg = ORB_CONFIG[orbState];

  // If the interviewer agent never joins (e.g. the agent worker is down), say
  // so after a grace period instead of showing "Connecting…" forever.
  useEffect(() => {
    if (orbState !== 'disconnected') {
      setAgentTimedOut(false);
      return;
    }
    const t = setTimeout(() => setAgentTimedOut(true), 25_000);
    return () => clearTimeout(t);
  }, [orbState]);

  useEffect(() => {
    if (connectionState === ConnectionState.Connected) setWasConnected(true);
  }, [connectionState]);

  const connectionLost =
    wasConnected && !isEnded && connectionState === ConnectionState.Disconnected;

  const handleEndInterview = () => {
    setIsEnded(true);
    room.disconnect();
    setTimeout(() => {
      router.push(`/report/${sessionId}`);
    }, 2500);
  };

  return (
    <div className="relative min-h-screen bg-slate-900 text-white flex flex-col overflow-hidden">
      <AuroraBackground subtle />

      {/* Header */}
      <header className="relative z-10 flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-white/10">
        <div>
          <h1 className="font-display text-xl font-bold tracking-tight">MockMind</h1>
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
            className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-xl text-sm font-semibold transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] shadow-lg shadow-red-600/20"
          >
            End Interview
          </button>
        </div>
      </header>

      {/* Main — orb centred */}
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center gap-8 p-8">
        <VoiceOrb state={orbState} />

        <div className="text-center space-y-2">
          <h2 className="font-display text-2xl font-bold">{cfg.label}</h2>
          <p className="text-slate-400">{cfg.sublabel}</p>
          {orbState === 'listening' && (
            <p className="text-slate-500 text-sm mt-1">
              Take your time — there&apos;s no rush.
            </p>
          )}
        </div>
      </div>

      {/* Interviewer never showed up / connection dropped */}
      {!isEnded && (agentTimedOut || connectionLost) && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900/90 border border-white/10 rounded-3xl p-8 text-center max-w-sm space-y-4">
            <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto" />
            <h2 className="font-display text-xl font-bold">
              {connectionLost ? 'Connection lost' : 'The interviewer is taking too long to join'}
            </h2>
            <p className="text-slate-400 text-sm">
              {connectionLost
                ? 'You were disconnected. Your answers so far are saved.'
                : 'Something went wrong starting your interview. Please try again.'}
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold rounded-xl text-sm"
              >
                Reconnect
              </button>
              {connectionLost && (
                <button
                  onClick={() => router.push(`/report/${sessionId}`)}
                  className="px-4 py-2 border border-white/15 text-slate-200 rounded-xl text-sm hover:bg-white/5"
                >
                  Get my report
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Live coding editor */}
      {challenge && <CodeEditorPanel challenge={challenge} onSubmit={handleSubmitCode} />}

      {/* End overlay */}
      {isEnded && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900/90 backdrop-blur-xl border border-white/10 rounded-3xl p-10 text-white text-center max-w-sm mx-4 shadow-2xl animate-fade-in-up">
            <CheckCircle2 className="w-14 h-14 text-emerald-400 mx-auto mb-4" />
            <h2 className="font-display text-2xl font-bold mb-2">Interview Complete!</h2>
            <p className="text-slate-400">
              Generating your evaluation report...
            </p>
            <div className="mt-4 h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-emerald-500 to-green-400 rounded-full animate-pulse w-3/4 shadow-[0_0_12px_0_rgba(52,211,153,0.6)]" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
