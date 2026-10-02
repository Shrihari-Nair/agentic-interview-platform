from pydantic import BaseModel


class QuestionHistoryEntry(BaseModel):
    session_id: str
    question: str
    category: str  # QuestionCategory value, as a plain string
    asked_at: float


class CandidateMemory(BaseModel):
    email: str
    sessions: list[str] = []
    category_scores_history: dict[str, list[float]] = {}
    weak_categories: list[str] = []
    asked_questions: list[QuestionHistoryEntry] = []
    interviewer_notes: str = ""
    updated_at: float
