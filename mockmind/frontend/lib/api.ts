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

export async function getReport(
  sessionId: string,
): Promise<EvaluationReport | null> {
  const res = await fetch(`${BACKEND_URL}/api/report/${sessionId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}
