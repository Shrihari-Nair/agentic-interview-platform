'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { BarChart3, CheckCircle2, Target, RotateCcw } from 'lucide-react';
import { getReport } from '../../../lib/api';
import type { EvaluationReport } from '../../../types/interview';
import { AuroraBackground } from '../../../components/AuroraBackground';

const RECOMMENDATION_CONFIG = {
  strong_yes: { label: 'Strong Hire', color: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  yes: { label: 'Hire', color: 'text-green-300', bg: 'bg-green-500/10', border: 'border-green-500/30' },
  maybe: { label: 'Maybe', color: 'text-amber-300', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
  no: { label: 'No Hire', color: 'text-red-300', bg: 'bg-red-500/10', border: 'border-red-500/30' },
} as const;

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round((score / 10) * 100);
  const gradient =
    score >= 7
      ? 'from-emerald-500 to-green-400'
      : score >= 5
        ? 'from-amber-500 to-yellow-400'
        : 'from-red-500 to-rose-400';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="capitalize text-slate-400">
          {label.replace('_', ' ')}
        </span>
        <span className="font-semibold text-white">{score.toFixed(1)}</span>
      </div>
      <div className="h-2.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${gradient} rounded-full transition-all duration-700`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function ReportPage() {
  const { sessionId } = useParams() as { sessionId: string };
  const router = useRouter();
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [polling, setPolling] = useState(true);
  const [pollCount, setPollCount] = useState(0);

  const fetchReport = useCallback(async () => {
    try {
      const data = await getReport(sessionId);
      if (data) {
        setReport(data);
        setPolling(false);
      }
    } catch {
      // keep polling
    }
    setPollCount((n) => n + 1);
  }, [sessionId]);

  useEffect(() => {
    // Initial fetch
    fetchReport();
  }, [fetchReport]);

  useEffect(() => {
    if (!polling) return;
    // Poll every 4 seconds, stop after 30 attempts (~2 min)
    if (pollCount >= 30) {
      setPolling(false);
      return;
    }
    const timer = setTimeout(fetchReport, 4000);
    return () => clearTimeout(timer);
  }, [polling, pollCount, fetchReport]);

  const recommendation = report
    ? RECOMMENDATION_CONFIG[report.hiring_recommendation]
    : null;

  if (!report) {
    return (
      <div className="relative min-h-screen overflow-hidden flex items-center justify-center">
        <AuroraBackground subtle />
        <div className="relative z-10 text-center space-y-4 max-w-sm p-8">
          <BarChart3 className="w-12 h-12 mx-auto text-blue-400 animate-bounce" />
          <h2 className="font-display text-2xl font-bold text-white">
            Generating Your Report
          </h2>
          <p className="text-slate-400">
            Our AI is analyzing your interview. This takes about 15–30 seconds.
          </p>
          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full animate-pulse w-2/3" />
          </div>
          {!polling && pollCount >= 30 && (
            <p className="text-red-400 text-sm">
              Report is taking longer than expected. Please refresh the page in
              a moment.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden py-10 px-4">
      <AuroraBackground subtle />

      <div className="relative z-10 max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between animate-fade-in-up">
          <h1 className="font-display text-3xl font-bold text-white">
            Interview Report
          </h1>
          <button
            onClick={() => router.push('/setup')}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white text-sm font-semibold rounded-xl transition-all duration-300 hover:scale-[1.03] active:scale-[0.98] shadow-lg shadow-blue-600/20"
          >
            <RotateCcw className="w-4 h-4" /> New Interview
          </button>
        </div>

        {/* Overall Score + Recommendation */}
        <div
          className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/30 p-6 flex flex-col sm:flex-row items-start sm:items-center gap-6 animate-fade-in-up"
          style={{ animationDelay: '0.05s' }}
        >
          {/* Score circle */}
          <div className="flex flex-col items-center justify-center w-28 h-28 rounded-full border-4 border-blue-500/60 shrink-0 mx-auto sm:mx-0 shadow-[0_0_30px_-6px_rgba(59,130,246,0.5)]">
            <span className="font-display text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              {report.overall_score.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">/10</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <h2 className="text-xl font-bold text-white">Overall Score</h2>
              {recommendation && (
                <span
                  className={`px-3 py-1 rounded-full text-sm font-semibold border ${recommendation.color} ${recommendation.bg} ${recommendation.border}`}
                >
                  {recommendation.label}
                </span>
              )}
            </div>
            <p className="text-slate-400 text-sm leading-relaxed">
              {report.summary}
            </p>
          </div>
        </div>

        {/* Category Scores */}
        <div
          className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/30 p-6 space-y-4 animate-fade-in-up"
          style={{ animationDelay: '0.1s' }}
        >
          <h3 className="font-display font-bold text-white text-lg">Category Scores</h3>
          {Object.entries(report.category_scores).map(([cat, score]) => (
            <ScoreBar key={cat} label={cat} score={score} />
          ))}
        </div>

        {/* Strengths + Improvements */}
        <div
          className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-fade-in-up"
          style={{ animationDelay: '0.15s' }}
        >
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/30 p-6 space-y-3">
            <h3 className="font-display font-bold text-emerald-300 text-lg flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5" /> Strengths
            </h3>
            <ul className="space-y-2">
              {report.strengths.map((s, i) => (
                <li key={i} className="text-sm text-slate-300 flex gap-2">
                  <span className="text-emerald-400 mt-0.5 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/30 p-6 space-y-3">
            <h3 className="font-display font-bold text-amber-300 text-lg flex items-center gap-2">
              <Target className="w-5 h-5" /> Areas to Improve
            </h3>
            <ul className="space-y-2">
              {report.improvements.map((s, i) => (
                <li key={i} className="text-sm text-slate-300 flex gap-2">
                  <span className="text-amber-400 mt-0.5 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Per-Question Feedback */}
        <div
          className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl shadow-black/30 p-6 space-y-5 animate-fade-in-up"
          style={{ animationDelay: '0.2s' }}
        >
          <h3 className="font-display font-bold text-white text-lg">
            Question-by-Question Feedback
          </h3>
          {report.question_feedback.map((qf, i) => {
            const qScore = qf.score;
            const scoreColor =
              qScore >= 7
                ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
                : qScore >= 5
                  ? 'text-amber-300 bg-amber-500/10 border-amber-500/30'
                  : 'text-red-300 bg-red-500/10 border-red-500/30';
            return (
              <div
                key={i}
                className="border border-white/10 rounded-xl p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-slate-200 text-sm leading-snug">
                    Q{i + 1}: {qf.question}
                  </p>
                  <span
                    className={`shrink-0 px-2.5 py-0.5 rounded-full text-sm font-bold border ${scoreColor}`}
                  >
                    {qf.score}/10
                  </span>
                </div>
                {qf.candidate_answer && qf.candidate_answer !== 'Not answered' && (
                  <div className="bg-white/5 rounded-lg p-3">
                    <p className="text-xs font-semibold text-slate-500 mb-1">
                      Your answer
                    </p>
                    <p className="text-sm text-slate-300 italic leading-relaxed">
                      &ldquo;{qf.candidate_answer}&rdquo;
                    </p>
                  </div>
                )}
                <p className="text-sm text-slate-400">{qf.feedback}</p>
                {qf.missed_points.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 mb-1">
                      Could have mentioned:
                    </p>
                    <ul className="space-y-0.5">
                      {qf.missed_points.map((mp, j) => (
                        <li key={j} className="text-xs text-slate-500 flex gap-1.5">
                          <span className="text-amber-400">•</span>
                          <span>{mp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-center text-slate-600 text-xs pb-8">
          Session ID: {sessionId}
        </p>
      </div>
    </main>
  );
}
