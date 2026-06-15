'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { usePreparation } from '../../hooks/usePreparation';

const STAGE_LABELS: Record<string, string> = {
  parsing: '📄 Parsing resume',
  resume_analysis: '🔍 Analyzing background',
  jd_analysis: '🎯 Analyzing job requirements',
  question_gen: '✏️ Crafting questions',
  complete: '✅ Ready',
  error: '❌ Error',
};

export default function SetupPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
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
    await startPreparation(resumeFile, jobDescription);
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
    <main className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-black text-white">MockMind</h1>
          <p className="text-slate-400 mt-2">
            AI-powered mock interviews, personalized to your resume.
          </p>
        </div>

        <div className="bg-white rounded-3xl shadow-2xl p-8 space-y-6">
          {/* Resume Upload */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Your Resume
            </label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                resumeFile
                  ? 'border-green-400 bg-green-50'
                  : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
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
                  <p className="text-green-700 font-semibold">
                    ✅ {resumeFile.name}
                  </p>
                  <p className="text-green-600 text-sm mt-1">
                    {(resumeFile.size / 1024).toFixed(0)} KB · Click to change
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-3xl mb-2">📎</p>
                  <p className="text-gray-600 font-medium">
                    Drop your resume here or click to browse
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    PDF, DOCX, or TXT
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Job Description */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Job Description
            </label>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the full job description here — include requirements, responsibilities, and company details for the most personalized interview."
              rows={8}
              className="w-full border-2 border-gray-200 rounded-xl p-4 text-sm focus:border-blue-400 outline-none resize-none text-gray-800 transition-colors"
              disabled={isRunning}
            />
            <p className="text-xs text-gray-400 mt-1">
              {jobDescription.length} characters
              {jobDescription.length < 50 && jobDescription.length > 0 && (
                <span className="text-amber-500 ml-2">
                  (paste a longer job description for best results)
                </span>
              )}
            </p>
          </div>

          {/* Preparation Progress */}
          {(isRunning || events.length > 0) && !error && (
            <div className="bg-slate-50 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-700">
                  {isRunning ? 'Preparing your interview...' : 'Preparation complete'}
                </span>
                <span className="text-sm font-bold text-blue-600">
                  {currentProgress}%
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-700"
                  style={{ width: `${currentProgress}%` }}
                />
              </div>
              {/* Stage log */}
              <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                {events.map((event, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-xs text-gray-600"
                  >
                    <span className="shrink-0 mt-0.5">
                      {STAGE_LABELS[event.stage]?.split(' ')[0] ?? '⟳'}
                    </span>
                    <span>{event.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
              <p className="font-semibold">Preparation failed</p>
              <p className="mt-1">{error}</p>
              <button
                onClick={() => {
                  setResumeFile(null);
                  setJobDescription('');
                }}
                className="mt-2 text-red-600 underline text-xs"
              >
                Start over
              </button>
            </div>
          )}

          {/* Session Ready Banner */}
          {isReady && sessionInfo && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-green-800 font-semibold">
                ✅ Interview ready — {sessionInfo.totalQuestions} personalized
                questions for{' '}
                <span className="italic">{sessionInfo.jobTitle}</span>
              </p>
              {sessionInfo.candidateName && (
                <p className="text-green-700 text-sm mt-1">
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
              className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold text-lg rounded-xl transition-colors"
            >
              {isRunning ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">⟳</span> Preparing...
                </span>
              ) : (
                'Prepare My Interview'
              )}
            </button>
          ) : (
            <button
              onClick={handleBeginInterview}
              className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-xl rounded-xl transition-colors shadow-lg shadow-green-600/20"
            >
              🎙️ Start Interview
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
