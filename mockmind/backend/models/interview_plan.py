from pydantic import BaseModel
from typing import Literal, Optional
from enum import Enum


class QuestionCategory(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SITUATIONAL = "situational"
    RESUME_DEEP_DIVE = "resume_deep_dive"
    CULTURE_FIT = "culture_fit"
    CLOSING = "closing"


class FollowUp(BaseModel):
    trigger: str
    question: str


class CodingTestCase(BaseModel):
    input: str = ""  # passed to the program's stdin
    expected_output: str = ""  # compared against stdout, stripped
    description: str = ""


class CodingSpec(BaseModel):
    language: str = "python"
    problem_statement: str
    starter_code: str = ""
    test_cases: list[CodingTestCase] = []


class InterviewQuestion(BaseModel):
    id: str
    category: QuestionCategory
    question: str
    intent: str
    ideal_answer_points: list[str] = []
    follow_ups: list[FollowUp] = []
    difficulty: int = 2
    source: str = "general"
    question_type: Literal["conversational", "coding"] = "conversational"
    coding_spec: Optional[CodingSpec] = None


class CandidateProfile(BaseModel):
    name: Optional[str] = None
    current_role: Optional[str] = None
    years_of_experience: int = 0
    skills: list[str] = []
    notable_projects: list[str] = []
    education: list[str] = []
    career_gaps: list[str] = []
    key_achievements: list[str] = []


class JobProfile(BaseModel):
    title: str
    company: Optional[str] = None
    required_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    responsibilities: list[str] = []
    seniority_level: str = "mid"
    red_flags_to_probe: list[str] = []


class InterviewPlan(BaseModel):
    session_id: str
    candidate: CandidateProfile
    job: JobProfile
    questions: list[InterviewQuestion]
    opening_message: str
    interview_style: str = "conversational"
    total_duration_minutes: int = 30
    created_at: float
    # Normalized {"basic": x, "intermediate": y, "advanced": z} weights used to
    # select each question's difficulty level at generation time (traceability
    # only — the live interview just reads plan.questions as before).
    level_weights: Optional[dict] = None
    # Set only when the candidate opted in to cross-session memory at setup.
    # Read by agent/session_state.py's generate_and_store_report() to decide
    # whether to update candidate memory after this session.
    candidate_email: Optional[str] = None


class SessionState(BaseModel):
    session_id: str
    plan: InterviewPlan
    current_question_index: int = 0
    asked_questions: list[str] = []
    transcript: list[dict] = []
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    evaluation: Optional[dict] = None
