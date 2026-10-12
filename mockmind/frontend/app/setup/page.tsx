'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
  FileSearch,
  Target,
  PenLine,
  CheckCircle2,
  XCircle,
  UploadCloud,
  Loader2,
  Mic,
  MessagesSquare,
  Code2,
  type LucideIcon,
} from 'lucide-react';
import { usePreparation, type PrepOptions } from '../../hooks/usePreparation';
import { AuroraBackground } from '../../components/AuroraBackground';

// Must match the limits enforced in backend/routers/prepare.py.
const MAX_RESUME_BYTES = 5 * 1024 * 1024;
const MAX_JD_CHARS = 15_000;
const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.txt'];

const LENGTH_OPTIONS: { value: PrepOptions['length']; label: string; hint: string }[] = [
  { value: 'quick', label: 'Quick', hint: '8 questions' },
  { value: 'standard', label: 'Standard', hint: '16 questions' },
];
const DIFFICULTY_OPTIONS: { value: PrepOptions['difficulty']; label: string; hint: string }[] = [
  { value: 'easier', label: 'Easier', hint: 'More fundamentals' },
  { value: 'balanced', label: 'Balanced', hint: 'Default mix' },
  { value: 'harder', label: 'Harder', hint: 'More architecture & trade-offs' },
];

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; hint: string }[];
  onChange: (v: T) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm font-semibold text-slate-300 mb-2">{label}</label>
      <div
        role="radiogroup"
        aria-label={label}
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      >
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            disabled={disabled}
            onClick={() => onChange(o.value)}
            className={`rounded-xl border px-3 py-2.5 text-left transition-all duration-300 disabled:opacity-60 ${
              value === o.value
                ? 'border-blue-400/50 bg-blue-500/10 text-blue-100'
                : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20'
            }`}
          >
            <span className="block text-sm font-semibold">{o.label}</span>
            <span className="block text-xs text-slate-500">{o.hint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

const STAGE_CONFIG: Record<string, { icon: LucideIcon; label: string }> = {
  parsing: { icon: FileText, label: 'Parsing resume' },
  resume_analysis: { icon: FileSearch, label: 'Analyzing background' },
  jd_analysis: { icon: Target, label: 'Analyzing job requirements' },
  question_gen: { icon: PenLine, label: 'Crafting questions' },
  complete: { icon: CheckCircle2, label: 'Ready' },
  error: { icon: XCircle, label: 'Error' },
};

export default function SetupPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const [useMemory, setUseMemory] = useState(false);
  const [candidateEmail, setCandidateEmail] = useState('');
  const [interviewType, setInterviewType] = useState<'standard' | 'coding'>('standard');
  const [length, setLength] = useState<PrepOptions['length']>('standard');
  const [difficulty, setDifficulty] = useState<PrepOptions['difficulty']>('balanced');
  const [focusWeakAreas, setFocusWeakAreas] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const {
    events,
    currentProgress,
    sessionInfo,
    error,
    isRunning,
    startPreparation,
  } = usePreparation();

  const handleStart = async () => {
    if (!resumeFile || !jobDescription.trim()) return;
    await startPreparation(resumeFile, jobDescription, useMemory, candidateEmail, interviewType, {
      difficulty,
      length,
      focusWeakAreas: useMemory && focusWeakAreas,
    });
  };

  const handleBeginInterview = () => {
    if (sessionInfo) {
      router.push(`/interview/${sessionInfo.sessionId}`);
    }
  };

  const isReady = sessionInfo !== null;
  const canSubmit =
    !!resumeFile &&
    !fileError &&
    jobDescription.trim().length > 50 &&
    jobDescription.length <= MAX_JD_CHARS &&
    !isRunning;

  const handleFile = (file: File | null) => {
    if (!file) {
      setResumeFile(null);
      setFileError(null);
      return;
    }
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      setResumeFile(null);
      setFileError('Unsupported file type — upload a PDF, DOCX or TXT resume.');
    } else if (file.size > MAX_RESUME_BYTES) {
      setResumeFile(null);
      setFileError('That file is too large — the limit is 5 MB.');
    } else {
      setResumeFile(file);
      setFileError(null);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden flex items-center justify-center p-6">
      <AuroraBackground subtle />
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10" aria-hidden />

      <div className="relative z-10 w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8 animate-fade-in-up">
          <h1 className="font-display text-4xl font-bold text-shimmer bg-gradient-to-r from-blue-400 via-cyan-300 to-violet-400 bg-clip-text text-transparent">
            MockMind
          </h1>
          <p className="text-slate-400 mt-2">
            AI-powered mock interviews, personalized to your resume.
          </p>
        </div>

        <div
          className="glow-border glow-border-always bg-slate-900/60 backdrop-blur-2xl border border-white/10 rounded-3xl shadow-2xl shadow-black/40 p-5 sm:p-8 space-y-6 animate-fade-in-up"
          style={{ animationDelay: '0.1s' }}
        >
          {/* Interview Type Toggle */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Interview Type
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setInterviewType('standard')}
                disabled={isRunning}
                className={`flex items-center justify-center gap-2 rounded-xl border p-4 text-sm font-semibold transition-all duration-300 ${
                  interviewType === 'standard'
                    ? 'border-blue-400/50 bg-blue-500/10 text-blue-200'
                    : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20'
                }`}
              >
                <MessagesSquare className="w-4 h-4" /> Standard interview
              </button>
              <button
                type="button"
                onClick={() => setInterviewType('coding')}
                disabled={isRunning}
                className={`flex items-center justify-center gap-2 rounded-xl border p-4 text-sm font-semibold transition-all duration-300 ${
                  interviewType === 'coding'
                    ? 'border-cyan-400/50 bg-cyan-500/10 text-cyan-200'
                    : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20'
                }`}
              >
                <Code2 className="w-4 h-4" /> Coding interview
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-1.5">
              {interviewType === 'standard'
                ? 'A full mixed interview — behavioral, situational, and technical questions tailored to your resume and the job.'
                : 'A short, code-focused interview — mostly live coding questions you solve in an in-browser editor.'}
            </p>
          </div>

          {/* Length (standard only — coding interviews have a fixed short format) + difficulty */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {interviewType === 'standard' && (
              <Segmented
                label="Length"
                value={length}
                options={LENGTH_OPTIONS}
                onChange={setLength}
                disabled={isRunning}
              />
            )}
            <div className={interviewType === 'standard' ? '' : 'sm:col-span-2'}>
              <Segmented
                label="Difficulty"
                value={difficulty}
                options={DIFFICULTY_OPTIONS}
                onChange={setDifficulty}
                disabled={isRunning}
              />
            </div>
          </div>

          {/* Resume Upload */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Your Resume
            </label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-300 ${
                resumeFile
                  ? 'border-emerald-400/50 bg-emerald-500/10'
                  : 'border-white/15 hover:border-blue-400/50 hover:bg-blue-500/5'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                onChange={(e) => handleFile(e.target.files?.[0] || null)}
                className="hidden"
              />
              {resumeFile ? (
                <div>
                  <CheckCircle2 className="w-7 h-7 text-emerald-400 mx-auto mb-2" />
                  <p className="text-emerald-300 font-semibold">
                    {resumeFile.name}
                  </p>
                  <p className="text-emerald-400/70 text-sm mt-1">
                    {(resumeFile.size / 1024).toFixed(0)} KB · Click to change
                  </p>
                </div>
              ) : (
                <div>
                  <UploadCloud className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-slate-300 font-medium">
                    Drop your resume here or click to browse
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    PDF, DOCX, or TXT
                  </p>
                </div>
              )}
            </div>
          </div>

          {fileError && (
            <p role="alert" className="text-sm text-red-300 -mt-3">
              {fileError}
            </p>
          )}

          {/* Job Description */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">
              Job Description
            </label>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the full job description here — include requirements, responsibilities, and company details for the most personalized interview."
              rows={8}
              className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-white placeholder:text-slate-500 focus:border-blue-400/50 outline-none resize-none transition-colors"
              disabled={isRunning}
            />
            <p className="text-xs text-slate-500 mt-1">
              {jobDescription.length.toLocaleString()} / {MAX_JD_CHARS.toLocaleString()} characters
              {jobDescription.length < 50 && jobDescription.length > 0 && (
                <span className="text-amber-400 ml-2">
                  (paste a longer job description for best results)
                </span>
              )}
            </p>
          </div>

          {/* Cross-session memory opt-in */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-3">
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={useMemory}
                onChange={(e) => setUseMemory(e.target.checked)}
                disabled={isRunning}
                className="mt-0.5 w-4 h-4 rounded border-white/20 bg-white/5 accent-blue-500"
              />
              <span className="text-sm text-slate-300">
                Remember my performance across sessions — future interviews
                will focus more on areas I&apos;ve historically struggled with.
              </span>
            </label>
            {useMemory && (
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={focusWeakAreas}
                  onChange={(e) => setFocusWeakAreas(e.target.checked)}
                  disabled={isRunning}
                  className="mt-0.5 w-4 h-4 rounded border-white/20 bg-white/5 accent-blue-500"
                />
                <span className="text-sm text-slate-300">
                  Practice mode — focus this interview on my weak areas.
                  <span className="block text-xs text-slate-500">
                    Needs at least one past session with this email; otherwise
                    you&apos;ll get a balanced interview.
                  </span>
                </span>
              </label>
            )}
            {useMemory && (
              <input
                type="email"
                value={candidateEmail}
                onChange={(e) => setCandidateEmail(e.target.value)}
                placeholder="your@email.com"
                disabled={isRunning}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-blue-400/50 outline-none transition-colors"
              />
            )}
          </div>

          {/* Preparation Progress */}
          {(isRunning || events.length > 0) && !error && (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-300">
                  {isRunning ? 'Preparing your interview...' : 'Preparation complete'}
                </span>
                <span className="text-sm font-bold text-cyan-300">
                  {currentProgress}%
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-700 shadow-[0_0_12px_0_rgba(56,189,248,0.6)]"
                  style={{ width: `${currentProgress}%` }}
                />
              </div>
              {/* Stage log */}
              <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                {events.map((event, i) => {
                  const cfg = STAGE_CONFIG[event.stage];
                  const Icon = cfg?.icon ?? Loader2;
                  return (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-xs text-slate-400"
                    >
                      <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-500" />
                      <span>{event.message}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-300 text-sm">
              <p className="font-semibold flex items-center gap-1.5">
                <XCircle className="w-4 h-4" /> Preparation failed
              </p>
              <p className="mt-1">{error}</p>
              <button
                onClick={() => {
                  setResumeFile(null);
                  setJobDescription('');
                }}
                className="mt-2 text-red-300 underline text-xs hover:text-red-200"
              >
                Start over
              </button>
            </div>
          )}

          {/* Session Ready Banner */}
          {isReady && sessionInfo && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4">
              <p className="text-emerald-300 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 shrink-0" /> Interview ready
                — {sessionInfo.totalQuestions} personalized questions for{' '}
                <span className="italic">{sessionInfo.jobTitle}</span>
              </p>
              {sessionInfo.candidateName && (
                <p className="text-emerald-400/80 text-sm mt-1">
                  Candidate: {sessionInfo.candidateName}
                </p>
              )}
            </div>
          )}

          {/* Action Button */}
          {!isReady ? (
            <button
              onClick={handleStart}
              disabled={!canSubmit}
              className="w-full py-4 bg-gradient-to-r from-blue-600 via-violet-600 to-cyan-500 hover:brightness-110 disabled:from-white/10 disabled:to-white/10 disabled:text-slate-500 disabled:shadow-none disabled:cursor-not-allowed disabled:hover:scale-100 text-white font-bold text-lg rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-xl shadow-violet-600/30"
            >
              {isRunning ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" /> Preparing...
                </span>
              ) : (
                'Prepare My Interview'
              )}
            </button>
          ) : (
            <button
              onClick={handleBeginInterview}
              className="w-full py-4 bg-gradient-to-r from-emerald-500 to-green-400 hover:from-emerald-400 hover:to-green-300 text-white font-bold text-xl rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-xl shadow-emerald-600/20 flex items-center justify-center gap-2"
            >
              <Mic className="w-5 h-5" /> Start Interview
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
