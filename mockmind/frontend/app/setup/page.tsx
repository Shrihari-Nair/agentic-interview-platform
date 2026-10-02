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
  type LucideIcon,
} from 'lucide-react';
import { usePreparation } from '../../hooks/usePreparation';
import { AuroraBackground } from '../../components/AuroraBackground';

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
    await startPreparation(resumeFile, jobDescription, useMemory, candidateEmail);
  };

  const handleBeginInterview = () => {
    if (sessionInfo) {
      router.push(`/interview/${sessionInfo.sessionId}`);
    }
  };

  const isReady = sessionInfo !== null;
  const canSubmit =
    !!resumeFile && jobDescription.trim().length > 50 && !isRunning;

  return (
    <main className="relative min-h-screen overflow-hidden flex items-center justify-center p-6">
      <AuroraBackground subtle />

      <div className="relative z-10 w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8 animate-fade-in-up">
          <h1 className="font-display text-4xl font-bold bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
            MockMind
          </h1>
          <p className="text-slate-400 mt-2">
            AI-powered mock interviews, personalized to your resume.
          </p>
        </div>

        <div
          className="bg-white/5 backdrop-blur-2xl border border-white/10 rounded-3xl shadow-2xl shadow-black/40 p-8 space-y-6 animate-fade-in-up"
          style={{ animationDelay: '0.1s' }}
        >
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
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
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
              {jobDescription.length} characters
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
              className="w-full py-4 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 disabled:from-white/10 disabled:to-white/10 disabled:text-slate-500 disabled:shadow-none disabled:cursor-not-allowed disabled:hover:scale-100 text-white font-bold text-lg rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] shadow-xl shadow-blue-600/20"
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
