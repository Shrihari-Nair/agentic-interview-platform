export type QuestionCategory =
  | 'behavioral'
  | 'technical'
  | 'situational'
  | 'resume_deep_dive'
  | 'culture_fit'
  | 'closing';

export interface InterviewQuestion {
  id: string;
  category: QuestionCategory;
  question: string;
  intent: string;
  difficulty: 1 | 2 | 3;
}

export interface PrepProgressEvent {
  stage:
    | 'parsing'
    | 'resume_analysis'
    | 'jd_analysis'
    | 'question_gen'
    | 'complete'
    | 'error';
  message: string;
  progress: number;
  session_id: string;
  data?: Record<string, unknown>;
}

export interface SessionInfo {
  sessionId: string;
  totalQuestions: number;
  jobTitle: string;
  candidateName: string | null;
}

export interface SessionTokenData {
  token: string;
  ws_url: string;
  room_name: string;
  session_id: string;
  identity: string;
}

export interface TranscriptEntry {
  speaker: 'interviewer' | 'candidate';
  text: string;
  timestamp: number;
}

export interface QuestionFeedback {
  question_id: string;
  question: string;
  candidate_answer: string;
  score: number;
  feedback: string;
  missed_points: string[];
}

export interface EvaluationReport {
  overall_score: number;
  hiring_recommendation: 'strong_yes' | 'yes' | 'maybe' | 'no';
  summary: string;
  strengths: string[];
  improvements: string[];
  category_scores: Record<string, number>;
  question_feedback: QuestionFeedback[];
}
