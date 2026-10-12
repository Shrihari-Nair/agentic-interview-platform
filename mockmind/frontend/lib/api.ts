import type { SessionTokenData, EvaluationReport } from '../types/interview';

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function getSessionToken(
  sessionId: string,
  participantName = 'Candidate',
): Promise<SessionTokenData> {
  const res = await fetch(`${BACKEND_URL}/api/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      participant_name: participantName,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to get session token');
  }
  return res.json();
}

export type ReportResult =
  | { status: 'ready'; report: EvaluationReport }
  | { status: 'pending' }
  | { status: 'failed' };

/** 200 -> ready, 404 -> still generating, 502 -> generation failed (retryable). */
export async function getReport(sessionId: string): Promise<ReportResult> {
  const res = await fetch(`${BACKEND_URL}/api/report/${sessionId}`);
  if (res.status === 404) return { status: 'pending' };
  if (res.status === 502) return { status: 'failed' };
  if (!res.ok) throw new Error('Failed to fetch report');
  return { status: 'ready', report: await res.json() };
}

export async function retryReport(sessionId: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/report/${sessionId}/retry`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      typeof err.detail === 'string' ? err.detail : 'Could not retry the report',
    );
  }
}
