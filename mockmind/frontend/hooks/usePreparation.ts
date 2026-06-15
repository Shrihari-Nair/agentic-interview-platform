import { useState, useCallback, useRef } from 'react';
import type { PrepProgressEvent, SessionInfo } from '../types/interview';

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export function usePreparation() {
  const [events, setEvents] = useState<PrepProgressEvent[]>([]);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const startPreparation = useCallback(
    async (resumeFile: File, jobDescription: string) => {
      setIsRunning(true);
      setEvents([]);
      setError(null);
      setSessionInfo(null);
      setCurrentProgress(0);

      const formData = new FormData();
      formData.append('resume', resumeFile);
      formData.append('job_description', jobDescription);

      abortRef.current = new AbortController();

      try {
        const response = await fetch(`${BACKEND_URL}/api/prepare`, {
          method: 'POST',
          body: formData,
          signal: abortRef.current.signal,
        });

        if (!response.ok) throw new Error('Preparation request failed');
        if (!response.body) throw new Error('No response stream');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const event: PrepProgressEvent = JSON.parse(line.slice(6));
              setEvents((prev) => [...prev, event]);
              setCurrentProgress(event.progress);

              if (event.stage === 'complete' && event.data) {
                setSessionInfo({
                  sessionId: event.session_id,
                  totalQuestions: event.data.total_questions as number,
                  jobTitle: event.data.job_title as string,
                  candidateName: (event.data.candidate_name as string) || null,
                });
              }

              if (event.stage === 'error') {
                setError(event.message);
              }
            } catch {
              // skip malformed SSE lines
            }
          }
        }
      } catch (err: unknown) {
        const e = err as Error;
        if (e.name !== 'AbortError') {
          setError(e.message || 'Unknown error during preparation');
        }
      } finally {
        setIsRunning(false);
      }
    },
    [],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    events,
    currentProgress,
    sessionInfo,
    error,
    isRunning,
    startPreparation,
    cancel,
  };
}
