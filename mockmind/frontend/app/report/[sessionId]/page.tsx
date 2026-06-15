'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getReport } from '../../../lib/api';
import type { EvaluationReport } from '../../../types/interview';

const RECOMMENDATION_CONFIG = {
  strong_yes: { label: 'Strong Hire', color: 'text-green-600', bg: 'bg-green-100', border: 'border-green-300' },
  yes: { label: 'Hire', color: 'text-emerald-600', bg: 'bg-emerald-100', border: 'border-emerald-300' },
  maybe: { label: 'Maybe', color: 'text-amber-600', bg: 'bg-amber-100', border: 'border-amber-300' },
  no: { label: 'No Hire', color: 'text-red-600', bg: 'bg-red-100', border: 'border-red-300' },
} as const;

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round((score / 10) * 100);
  const color =
    score >= 7 ? 'bg-green-500' : score >= 5 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="capitalize text-gray-600">
          {label.replace('_', ' ')}
        </span>
        <span className="font-semibold text-gray-800">{score.toFixed(1)}</span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-700`}
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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center space-y-4 max-w-sm p-8">
          <div className="text-5xl animate-bounce">📊</div>
          <h2 className="text-2xl font-bold text-gray-800">
            Generating Your Report
          </h2>
          <p className="text-gray-500">
            Our AI is analyzing your interview. This takes about 15–30 seconds.
          </p>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-pulse w-2/3" />
          </div>
          {!polling && pollCount >= 30 && (
            <p className="text-red-500 text-sm">
              Report is taking longer than expected. Please refresh the page in
              a moment.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-black text-gray-900">
            Interview Report
          </h1>
          <button
            onClick={() => router.push('/setup')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            New Interview
          </button>
        </div>

        {/* Overall Score + Recommendation */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col sm:flex-row items-start sm:items-center gap-6">
          {/* Score circle */}
          <div className="flex flex-col items-center justify-center w-28 h-28 rounded-full border-4 border-blue-500 shrink-0 mx-auto sm:mx-0">
            <span className="text-3xl font-black text-blue-600">
              {report.overall_score.toFixed(1)}
            </span>
            <span className="text-xs text-gray-400">/10</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <h2 className="text-xl font-bold text-gray-900">Overall Score</h2>
              {recommendation && (
                <span
                  className={`px-3 py-1 rounded-full text-sm font-semibold border ${recommendation.color} ${recommendation.bg} ${recommendation.border}`}
                >
                  {recommendation.label}
                </span>
              )}
            </div>
            <p className="text-gray-600 text-sm leading-relaxed">
              {report.summary}
            </p>
          </div>
        </div>

        {/* Category Scores */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">
          <h3 className="font-bold text-gray-800 text-lg">Category Scores</h3>
          {Object.entries(report.category_scores).map(([cat, score]) => (
            <ScoreBar key={cat} label={cat} score={score} />
          ))}
        </div>

        {/* Strengths + Improvements */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-3">
            <h3 className="font-bold text-green-700 text-lg flex items-center gap-2">
              <span>✅</span> Strengths
            </h3>
            <ul className="space-y-2">
              {report.strengths.map((s, i) => (
                <li key={i} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-3">
            <h3 className="font-bold text-amber-700 text-lg flex items-center gap-2">
              <span>🎯</span> Areas to Improve
            </h3>
            <ul className="space-y-2">
              {report.improvements.map((s, i) => (
                <li key={i} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-amber-500 mt-0.5 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Per-Question Feedback */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5">
          <h3 className="font-bold text-gray-800 text-lg">
            Question-by-Question Feedback
          </h3>
          {report.question_feedback.map((qf, i) => {
            const qScore = qf.score;
            const scoreColor =
              qScore >= 7
                ? 'text-green-600 bg-green-50 border-green-200'
                : qScore >= 5
                  ? 'text-amber-600 bg-amber-50 border-amber-200'
                  : 'text-red-600 bg-red-50 border-red-200';
            return (
              <div
                key={i}
                className="border border-gray-100 rounded-xl p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-gray-800 text-sm leading-snug">
                    Q{i + 1}: {qf.question}
                  </p>
                  <span
                    className={`shrink-0 px-2.5 py-0.5 rounded-full text-sm font-bold border ${scoreColor}`}
                  >
                    {qf.score}/10
                  </span>
                </div>
                {qf.candidate_answer && qf.candidate_answer !== 'Not answered' && (
                  <div className="bg-slate-50 rounded-lg p-3">
                    <p className="text-xs font-semibold text-slate-500 mb-1">
                      Your answer
                    </p>
                    <p className="text-sm text-slate-700 italic leading-relaxed">
                      "{qf.candidate_answer}"
                    </p>
                  </div>
                )}
                <p className="text-sm text-gray-600">{qf.feedback}</p>
                {qf.missed_points.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">
                      Could have mentioned:
                    </p>
                    <ul className="space-y-0.5">
                      {qf.missed_points.map((mp, j) => (
                        <li key={j} className="text-xs text-gray-500 flex gap-1.5">
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

        <p className="text-center text-gray-400 text-xs pb-8">
          Session ID: {sessionId}
        </p>
      </div>
    </main>
  );
}
