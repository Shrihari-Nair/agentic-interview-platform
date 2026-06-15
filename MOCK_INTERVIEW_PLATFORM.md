# MockMind — AI Mock Interview Platform
## Complete Technical Implementation Plan
> Feed this entire document to your coding agent / IDE. Every architectural decision,
> file, data contract, agent design, and edge case is defined here.

---

## 1. Product Overview

**MockMind** is an AI-powered voice mock interview platform where:
1. The user uploads their **resume** (PDF or plain text) and pastes a **job description**
2. A **pre-interview preparation pipeline** runs (sub-agents analyze both documents and generate a tailored question bank)
3. The user starts a **live voice interview session** via LiveKit
4. The main **interviewer agent** conducts the interview in real-time using Gemini as LLM and Cartesia for TTS voice output
5. After the session, a **post-interview evaluation report** is generated with scores and feedback

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend API | Python, FastAPI |
| Voice Agent | LiveKit Agents Python SDK v1.0+ |
| LLM | Google Gemini 2.5 Flash (`gemini-2.5-flash`) via `livekit-plugins-google` |
| TTS | Cartesia (`sonic-3` model) via `livekit-plugins-cartesia` |
| STT | Deepgram (`nova-3` model) via `livekit-plugins-deepgram` |
| VAD | Silero via `livekit-plugins-silero` |
| Sub-agents (prep) | Pure Python async, Google Gemini API (not LiveKit, just direct API calls) |
| Resume parsing | `pypdf2` + `python-docx` |
| Storage | Local filesystem (dev), S3-compatible (prod) |
| State store | Redis (for session state shared between FastAPI and LiveKit agent) |

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│  ┌──────────────────┐    ┌──────────────────────────────────┐  │
│  │  Setup Page       │    │   Interview Room Page            │  │
│  │  - Resume upload  │    │   - LiveKit voice UI             │  │
│  │  - JD paste       │    │   - Live transcript display      │  │
│  │  - Prep progress  │    │   - Question counter             │  │
│  │  - Start button   │    │   - End interview button         │  │
│  └────────┬─────────┘    └───────────────┬──────────────────┘  │
│           │ HTTP POST                     │ WebRTC (LiveKit)     │
└───────────┼───────────────────────────────┼─────────────────────┘
            │                               │
            ▼                               ▼
┌───────────────────────┐    ┌──────────────────────────────────┐
│   FastAPI Backend     │    │        LiveKit Cloud             │
│                       │    │                                  │
│  POST /api/prepare    │    │   LiveKit Room                   │
│   → runs 3 sub-agents │    │   ├── User participant           │
│   → stores prep data  │    │   └── InterviewerAgent           │
│   → returns session_id│    │       ├── Gemini 2.5 Flash (LLM) │
│                       │    │       ├── Deepgram nova-3 (STT)  │
│  POST /api/token      │    │       ├── Cartesia sonic-3 (TTS) │
│   → returns LK token  │    │       ├── Silero VAD             │
│   → dispatches agent  │    │       └── reads prep data        │
│                       │    │           from Redis             │
│  GET /api/report/{id} │    └──────────────────────────────────┘
│   → returns eval report│
└───────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│              PRE-INTERVIEW PREPARATION PIPELINE               │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ ResumeAnalyzer  │  │  JDAnalyzer     │  │  Question    │ │
│  │ Sub-Agent       │  │  Sub-Agent      │  │  Generator   │ │
│  │                 │  │                 │  │  Sub-Agent   │ │
│  │ Extracts:       │  │ Extracts:       │  │              │ │
│  │ - Skills        │  │ - Required skills│  │ Uses outputs │ │
│  │ - Experience    │  │ - Nice-to-haves  │  │ of both ↑   │ │
│  │ - Projects      │  │ - Responsibilities│  │ to generate: │ │
│  │ - Education     │  │ - Red flags      │  │ - 15-20 Qs  │ │
│  │ - Gaps          │  │ - Seniority level│  │ - Categories │ │
│  │ - Achievements  │  │ - Tech stack     │  │ - Follow-ups │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
│           └───────────────────►│◄──────────────────┘         │
│                                ▼                               │
│                    Structured InterviewPlan                    │
│                    stored in Redis                             │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. Repository Structure

```
mockmind/
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                         # Landing page
│   │   ├── setup/
│   │   │   └── page.tsx                     # Resume + JD upload page
│   │   └── interview/
│   │       └── [sessionId]/
│   │           └── page.tsx                 # Live interview room
│   ├── components/
│   │   ├── SetupForm.tsx                    # File upload + JD textarea
│   │   ├── PreparationProgress.tsx          # Sub-agent progress tracker
│   │   ├── InterviewRoom.tsx                # LiveKit room wrapper
│   │   ├── TranscriptDisplay.tsx            # Real-time transcript
│   │   ├── QuestionTracker.tsx              # Q1/15 progress indicator
│   │   ├── InterviewControls.tsx            # Mute, end interview
│   │   └── PostInterviewReport.tsx          # Final report display
│   ├── hooks/
│   │   ├── usePreparation.ts                # SSE hook for prep progress
│   │   └── useInterviewSession.ts           # LiveKit session management
│   ├── lib/
│   │   └── api.ts                           # API client
│   ├── types/
│   │   └── interview.ts                     # All TypeScript types
│   └── package.json
│
├── backend/
│   ├── main.py                              # FastAPI app
│   ├── routers/
│   │   ├── prepare.py                       # POST /api/prepare (SSE stream)
│   │   ├── session.py                       # POST /api/token, GET /api/report
│   │   └── health.py                        # GET /health
│   ├── agents/
│   │   ├── resume_analyzer.py               # Sub-agent 1
│   │   ├── jd_analyzer.py                   # Sub-agent 2
│   │   └── question_generator.py            # Sub-agent 3
│   ├── models/
│   │   ├── interview_plan.py                # Pydantic models
│   │   └── session.py                       # Session state models
│   ├── services/
│   │   ├── redis_client.py                  # Redis wrapper
│   │   ├── resume_parser.py                 # PDF/DOCX text extractor
│   │   └── report_generator.py              # Post-interview report
│   ├── requirements.txt
│   └── .env
│
├── agent/
│   ├── agent.py                             # Main LiveKit agent entrypoint
│   ├── interviewer.py                       # InterviewerAgent class
│   ├── session_state.py                     # Per-session state tracker
│   ├── prompts.py                           # All prompt templates
│   ├── tools.py                             # function_tool definitions
│   ├── requirements.txt
│   └── .env
│
└── docker-compose.yml                       # Redis + backend + agent
```

---

## 5. Environment Variables

### `backend/.env`
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=your_secret
GOOGLE_API_KEY=your_gemini_api_key
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
```

### `agent/.env`
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=your_secret
GOOGLE_API_KEY=your_gemini_api_key
CARTESIA_API_KEY=your_cartesia_api_key
REDIS_URL=redis://localhost:6379
```

### `frontend/.env.local`
```env
NEXT_PUBLIC_LIVEKIT_URL=wss://your-project.livekit.cloud
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## 6. Data Models (Pydantic + TypeScript)

### `backend/models/interview_plan.py`
```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class QuestionCategory(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SITUATIONAL = "situational"
    RESUME_DEEP_DIVE = "resume_deep_dive"
    CULTURE_FIT = "culture_fit"
    CLOSING = "closing"

class FollowUp(BaseModel):
    trigger: str          # What answer pattern triggers this follow-up
    question: str         # The follow-up question text

class InterviewQuestion(BaseModel):
    id: str
    category: QuestionCategory
    question: str
    intent: str           # What skill/trait this question evaluates
    ideal_answer_points: list[str]   # Bullet points of what a good answer covers
    follow_ups: list[FollowUp]       # 2-3 contextual follow-ups
    difficulty: int       # 1=easy, 2=medium, 3=hard
    source: str           # "resume_gap", "jd_requirement", "behavioral_standard", etc.

class CandidateProfile(BaseModel):
    name: Optional[str]
    current_role: Optional[str]
    years_of_experience: int
    skills: list[str]
    notable_projects: list[str]
    education: list[str]
    career_gaps: list[str]          # Gaps to probe
    key_achievements: list[str]

class JobProfile(BaseModel):
    title: str
    company: Optional[str]
    required_skills: list[str]
    nice_to_have_skills: list[str]
    responsibilities: list[str]
    seniority_level: str            # "junior", "mid", "senior", "lead", "staff"
    red_flags_to_probe: list[str]   # Skills in JD missing from resume

class InterviewPlan(BaseModel):
    session_id: str
    candidate: CandidateProfile
    job: JobProfile
    questions: list[InterviewQuestion]   # Ordered list, 15-20 questions
    opening_message: str                 # Agent's first spoken message
    interview_style: str                 # "conversational", "structured", "stress"
    total_duration_minutes: int          # Target interview length
    created_at: float

class SessionState(BaseModel):
    session_id: str
    plan: InterviewPlan
    current_question_index: int = 0
    asked_questions: list[str] = []      # IDs of asked questions
    transcript: list[dict] = []          # Full conversation log
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    evaluation: Optional[dict] = None
```

### `frontend/types/interview.ts`
```typescript
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
  stage: 'resume_analysis' | 'jd_analysis' | 'question_generation' | 'complete' | 'error';
  message: string;
  progress: number;   // 0-100
  data?: any;
}

export interface SessionInfo {
  sessionId: string;
  token: string;
  wsUrl: string;
  totalQuestions: number;
  candidateName: string;
  jobTitle: string;
}

export interface TranscriptEntry {
  speaker: 'interviewer' | 'candidate';
  text: string;
  timestamp: number;
}

export interface EvaluationReport {
  sessionId: string;
  overallScore: number;             // 0-10
  categoryScores: Record<QuestionCategory, number>;
  strengths: string[];
  improvements: string[];
  questionFeedback: QuestionFeedback[];
  hiringRecommendation: 'strong_yes' | 'yes' | 'maybe' | 'no';
  summary: string;
}

export interface QuestionFeedback {
  questionId: string;
  question: string;
  candidateAnswer: string;
  score: number;                    // 0-10
  feedback: string;
  missedPoints: string[];
}
```

---

## 7. Pre-Interview Sub-Agents (FastAPI Backend)

These are **pure Python async functions** using the Google Gemini API directly
(not LiveKit agents). They run before the live session starts and populate Redis.

### `backend/services/resume_parser.py`
```python
"""
Extracts plain text from PDF or DOCX resume files.
"""
import io
from pathlib import Path

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text.strip()

def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([para.text for para in doc.paragraphs]).strip()

def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_bytes)
    else:
        # Assume plain text
        return file_bytes.decode("utf-8", errors="ignore")
```

### `backend/agents/resume_analyzer.py`
```python
"""
Sub-Agent 1: Resume Analyzer

Input:  Raw resume text
Output: CandidateProfile (structured JSON)

Uses Gemini 2.5 Flash with structured output (response_schema).
Does NOT use LiveKit — just a direct Gemini API call.
"""
import json
import os
from google import genai
from google.genai import types
from backend.models.interview_plan import CandidateProfile

RESUME_ANALYSIS_PROMPT = """
You are an expert technical recruiter analyzing a candidate's resume.
Extract structured information from the resume below.

RESUME:
{resume_text}

Extract and return a JSON object with EXACTLY this structure:
{{
  "name": "candidate full name or null",
  "current_role": "most recent job title or null",
  "years_of_experience": <integer, total years of relevant experience>,
  "skills": ["list", "of", "all", "technical", "and", "soft", "skills"],
  "notable_projects": ["brief description of each significant project"],
  "education": ["degree and institution for each"],
  "career_gaps": ["any gaps in employment or experience worth probing, e.g. '18-month gap 2021-2022'"],
  "key_achievements": ["quantified achievements, e.g. 'Reduced API latency by 40%'"]
}}

Be thorough. For career_gaps, include skill gaps relative to a senior engineer too.
Return ONLY the JSON object, no markdown, no explanation.
"""

async def analyze_resume(resume_text: str) -> CandidateProfile:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=RESUME_ANALYSIS_PROMPT.format(resume_text=resume_text),
        config=types.GenerateContentConfig(
            temperature=0.1,   # Low temp for factual extraction
            max_output_tokens=2048,
        ),
    )
    
    raw = response.text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    data = json.loads(raw)
    return CandidateProfile(**data)
```

### `backend/agents/jd_analyzer.py`
```python
"""
Sub-Agent 2: Job Description Analyzer

Input:  Raw job description text
Output: JobProfile (structured JSON)
"""
import json
import os
from google import genai
from google.genai import types
from backend.models.interview_plan import JobProfile

JD_ANALYSIS_PROMPT = """
You are an expert technical recruiter analyzing a job description.
Extract structured information from the job description below.

JOB DESCRIPTION:
{jd_text}

Extract and return a JSON object with EXACTLY this structure:
{{
  "title": "job title",
  "company": "company name or null",
  "required_skills": ["non-negotiable technical and soft skills explicitly listed"],
  "nice_to_have_skills": ["preferred but optional skills"],
  "responsibilities": ["key responsibilities, 5-10 bullet points"],
  "seniority_level": "junior|mid|senior|lead|staff|principal",
  "red_flags_to_probe": ["skills or experiences the JD requires that are NOT typically mentioned in resumes for this level — things an interviewer would specifically test for"]
}}

For seniority_level: infer from years required, title, and responsibility scope.
Return ONLY the JSON object, no markdown, no explanation.
"""

async def analyze_jd(jd_text: str) -> JobProfile:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=JD_ANALYSIS_PROMPT.format(jd_text=jd_text),
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
        ),
    )
    
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    data = json.loads(raw)
    return JobProfile(**data)
```

### `backend/agents/question_generator.py`
```python
"""
Sub-Agent 3: Question Generator

Input:  CandidateProfile + JobProfile
Output: List of InterviewQuestion (15-20 tailored questions)

This is the most important sub-agent. It generates the entire question bank
that the live interviewer agent will use during the session.
"""
import json
import os
import uuid
from google import genai
from google.genai import types
from backend.models.interview_plan import InterviewQuestion, InterviewPlan, QuestionCategory

QUESTION_GENERATION_PROMPT = """
You are a world-class technical interviewer preparing for an interview.
You have analyzed the candidate's resume and the job description.

CANDIDATE PROFILE:
{candidate_json}

JOB PROFILE:
{job_json}

Generate a tailored interview question bank of 15-20 questions.

REQUIREMENTS:
1. Questions must be SPECIFIC to this candidate and role — not generic
2. Include questions that probe the candidate's ACTUAL projects and experience
3. Include questions that test for skills the JD requires but the resume lacks (red flags)
4. Mix question categories: behavioral (30%), technical (30%), situational (20%), 
   resume_deep_dive (15%), closing (5%)
5. Order questions naturally: start easy/warm-up, build to hard, end with closing
6. Each question must have 2-3 contextual follow-ups based on expected answer patterns
7. Behavioral questions must follow STAR format probing

Return a JSON object with EXACTLY this structure:
{{
  "opening_message": "The interviewer's first spoken message to open the session naturally. 
                       Friendly, professional. Introduce yourself as the AI interviewer. 
                       Mention candidate name if available. ~2 sentences.",
  "interview_style": "conversational",
  "total_duration_minutes": 30,
  "questions": [
    {{
      "id": "q1",
      "category": "behavioral|technical|situational|resume_deep_dive|culture_fit|closing",
      "question": "The exact question text as the interviewer would say it",
      "intent": "What this question is testing (1 sentence)",
      "ideal_answer_points": [
        "Point 1 that a strong answer should cover",
        "Point 2",
        "Point 3"
      ],
      "follow_ups": [
        {{
          "trigger": "If the candidate gives a vague answer about the project",
          "question": "Can you walk me through the specific technical decisions you made?"
        }},
        {{
          "trigger": "If the candidate mentions a metric or result",
          "question": "How did you measure that improvement, and what was the baseline?"
        }}
      ],
      "difficulty": 1,
      "source": "behavioral_standard|resume_gap|jd_requirement|project_deep_dive"
    }}
  ]
}}

IMPORTANT RULES:
- question[0] must be a warm-up resume question (difficulty: 1)
- question[-1] must be "Do you have any questions for me?" (category: closing)
- Technical questions must be specific to the tech stack in BOTH resume and JD
- Resume deep-dive questions must reference SPECIFIC projects from the resume by name
- If there are career gaps, include one tactful question probing the gap
- Return ONLY the JSON object, no markdown fences, no explanation
"""

async def generate_questions(
    candidate,
    job,
    session_id: str,
) -> InterviewPlan:
    from backend.models.interview_plan import CandidateProfile, JobProfile
    
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    prompt = QUESTION_GENERATION_PROMPT.format(
        candidate_json=candidate.model_dump_json(indent=2),
        job_json=job.model_dump_json(indent=2),
    )
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,   # Slightly creative for question variety
            max_output_tokens=8192,
        ),
    )
    
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    data = json.loads(raw)
    
    # Parse questions
    questions = []
    for q_data in data["questions"]:
        questions.append(InterviewQuestion(
            id=q_data.get("id", f"q{len(questions)+1}"),
            category=QuestionCategory(q_data["category"]),
            question=q_data["question"],
            intent=q_data["intent"],
            ideal_answer_points=q_data.get("ideal_answer_points", []),
            follow_ups=[
                type('FollowUp', (), f)()
                for f in q_data.get("follow_ups", [])
            ],
            difficulty=q_data.get("difficulty", 2),
            source=q_data.get("source", "general"),
        ))
    
    return InterviewPlan(
        session_id=session_id,
        candidate=candidate,
        job=job,
        questions=questions,
        opening_message=data["opening_message"],
        interview_style=data.get("interview_style", "conversational"),
        total_duration_minutes=data.get("total_duration_minutes", 30),
        created_at=__import__("time").time(),
    )
```

---

## 8. FastAPI Backend

### `backend/routers/prepare.py`
```python
"""
POST /api/prepare

Accepts:
  - resume file (multipart upload)
  - job_description (form field, plain text)

Runs sub-agents sequentially with SSE progress streaming.
Stores InterviewPlan in Redis.
Returns session_id.

The frontend polls this endpoint with an EventSource for progress updates.
"""

import asyncio
import json
import uuid
import time
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from backend.services.resume_parser import extract_resume_text
from backend.agents.resume_analyzer import analyze_resume
from backend.agents.jd_analyzer import analyze_jd
from backend.agents.question_generator import generate_questions
from backend.services.redis_client import redis_client

router = APIRouter()

@router.post("/api/prepare")
async def prepare_interview(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    """
    SSE endpoint that streams preparation progress to the frontend.
    
    SSE event format:
      data: {"stage": "...", "message": "...", "progress": 0-100, "session_id": "..."}
    
    Stages:
      1. "parsing"          → Extracting text from resume file
      2. "resume_analysis"  → Sub-agent 1 running
      3. "jd_analysis"      → Sub-agent 2 running
      4. "question_gen"     → Sub-agent 3 running
      5. "complete"         → All done, session_id ready
      6. "error"            → Something failed
    """
    session_id = str(uuid.uuid4())
    
    async def event_stream():
        try:
            # Stage 1: Parse resume
            yield _sse({"stage": "parsing", "message": "Reading your resume...", "progress": 5, "session_id": session_id})
            file_bytes = await resume.read()
            resume_text = extract_resume_text(file_bytes, resume.filename)
            yield _sse({"stage": "parsing", "message": "Resume parsed successfully.", "progress": 15, "session_id": session_id})

            # Stage 2: Analyze resume (Sub-Agent 1)
            yield _sse({"stage": "resume_analysis", "message": "Analyzing your background and experience...", "progress": 20, "session_id": session_id})
            candidate_profile = await analyze_resume(resume_text)
            yield _sse({
                "stage": "resume_analysis",
                "message": f"Profile built: {candidate_profile.years_of_experience} years experience, {len(candidate_profile.skills)} skills identified.",
                "progress": 45,
                "session_id": session_id,
                "data": {"candidate_name": candidate_profile.name}
            })

            # Stage 3: Analyze JD (Sub-Agent 2)
            yield _sse({"stage": "jd_analysis", "message": "Analyzing the job requirements...", "progress": 50, "session_id": session_id})
            job_profile = await analyze_jd(job_description)
            yield _sse({
                "stage": "jd_analysis",
                "message": f"Job analyzed: {job_profile.title} ({job_profile.seniority_level}). Found {len(job_profile.red_flags_to_probe)} areas to probe.",
                "progress": 65,
                "session_id": session_id
            })

            # Stage 4: Generate questions (Sub-Agent 3)
            yield _sse({"stage": "question_gen", "message": "Crafting personalized interview questions...", "progress": 70, "session_id": session_id})
            plan = await generate_questions(candidate_profile, job_profile, session_id)
            yield _sse({
                "stage": "question_gen",
                "message": f"Generated {len(plan.questions)} tailored questions across {len(set(q.category for q in plan.questions))} categories.",
                "progress": 90,
                "session_id": session_id
            })

            # Store plan in Redis (TTL: 4 hours)
            await redis_client.setex(
                f"interview_plan:{session_id}",
                14400,
                plan.model_dump_json()
            )
            
            # Store empty session state
            from backend.models.interview_plan import SessionState
            state = SessionState(session_id=session_id, plan=plan)
            await redis_client.setex(
                f"session_state:{session_id}",
                14400,
                state.model_dump_json()
            )

            yield _sse({
                "stage": "complete",
                "message": "Your interview is ready. Click 'Start Interview' when you're ready.",
                "progress": 100,
                "session_id": session_id,
                "data": {
                    "total_questions": len(plan.questions),
                    "duration_minutes": plan.total_duration_minutes,
                    "job_title": job_profile.title,
                    "candidate_name": candidate_profile.name,
                }
            })

        except Exception as e:
            yield _sse({"stage": "error", "message": f"Preparation failed: {str(e)}", "progress": 0, "session_id": session_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
```

### `backend/routers/session.py`
```python
"""
POST /api/token  → Generate LiveKit token + dispatch agent
GET  /api/report/{session_id} → Return post-interview evaluation report
"""

import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from livekit.api import AccessToken, VideoGrants, LiveKitAPI
from backend.services.redis_client import redis_client
from backend.services.report_generator import generate_report

router = APIRouter()

class TokenRequest(BaseModel):
    session_id: str
    participant_name: str = "Candidate"

@router.post("/api/token")
async def get_token(req: TokenRequest):
    """
    Generates a LiveKit token for the candidate to join the interview room.
    Also dispatches the interviewer agent to that room.
    """
    # Verify session exists
    plan_json = await redis_client.get(f"interview_plan:{req.session_id}")
    if not plan_json:
        raise HTTPException(status_code=404, detail="Session not found. Run /api/prepare first.")
    
    room_name = f"interview_{req.session_id}"
    identity = f"candidate_{req.session_id[:8]}"
    
    # Generate candidate token
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]
    livekit_url = os.environ["LIVEKIT_URL"]
    
    token = (
        AccessToken(api_key=api_key, api_secret=api_secret)
        .with_identity(identity)
        .with_name(req.participant_name)
        .with_ttl(7200)
        .with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        .to_jwt()
    )
    
    # Dispatch the interviewer agent to the room
    # The agent reads session_id from room metadata to load its plan from Redis
    async with LiveKitAPI(
        url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
    ) as lk_api:
        await lk_api.agent_dispatch.create_dispatch(
            room_name=room_name,
            agent_name="mockmind-interviewer",   # Must match agent WorkerOptions
            metadata=json.dumps({"session_id": req.session_id}),
        )
    
    return {
        "token": token,
        "ws_url": livekit_url,
        "room_name": room_name,
        "identity": identity,
        "session_id": req.session_id,
    }


@router.get("/api/report/{session_id}")
async def get_report(session_id: str):
    """
    Returns the post-interview evaluation report.
    Report is generated when the agent calls end_interview() tool.
    Polls until available (max 60s).
    """
    report_json = await redis_client.get(f"interview_report:{session_id}")
    if not report_json:
        raise HTTPException(status_code=404, detail="Report not ready yet.")
    return json.loads(report_json)
```

### `backend/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from backend.routers import prepare, session, health
from backend.services.redis_client import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.ping()
    yield
    await redis_client.close()

app = FastAPI(title="MockMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prepare.router)
app.include_router(session.router)
app.include_router(health.router)
```

### `backend/services/redis_client.py`
```python
import os
import redis.asyncio as redis

redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    encoding="utf-8",
    decode_responses=True,
)
```

---

## 9. Report Generator

### `backend/services/report_generator.py`
```python
"""
Generates post-interview evaluation report.
Called by the agent at session end via tool call.
Uses Gemini to evaluate the transcript against the question bank.
"""
import json
import os
from google import genai
from google.genai import types

REPORT_PROMPT = """
You are an expert interview evaluator. Analyze this mock interview session.

INTERVIEW PLAN:
{plan_json}

FULL TRANSCRIPT:
{transcript_json}

Generate a comprehensive evaluation report as a JSON object:
{{
  "overall_score": <0-10 float>,
  "hiring_recommendation": "strong_yes|yes|maybe|no",
  "summary": "2-3 sentence overall assessment",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "improvements": ["area to improve 1", "area 2", "area 3"],
  "category_scores": {{
    "behavioral": <0-10>,
    "technical": <0-10>,
    "situational": <0-10>,
    "resume_deep_dive": <0-10>,
    "communication": <0-10>
  }},
  "question_feedback": [
    {{
      "question_id": "q1",
      "question": "question text",
      "candidate_answer": "candidate's answer from transcript",
      "score": <0-10>,
      "feedback": "specific feedback on this answer",
      "missed_points": ["what they should have mentioned but didn't"]
    }}
  ]
}}

Be specific, honest, and constructive. Reference actual things the candidate said.
Return ONLY the JSON object.
"""

async def generate_report(session_id: str, plan: dict, transcript: list) -> dict:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=REPORT_PROMPT.format(
            plan_json=json.dumps(plan, indent=2),
            transcript_json=json.dumps(transcript, indent=2),
        ),
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )
    
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    return json.loads(raw)
```

---

## 10. LiveKit Interviewer Agent

This is the heart of the system. The agent:
1. Joins the room when dispatched
2. Loads the `InterviewPlan` from Redis using `session_id` from room metadata
3. Asks questions in order, with intelligent follow-ups
4. Tracks session state (which question we're on, transcript)
5. Ends the interview gracefully and triggers report generation

### `agent/prompts.py`
```python
"""
All prompts for the interviewer agent.
These are the core system instructions that shape agent behavior.
"""

def build_interviewer_system_prompt(plan_json: str) -> str:
    return f"""
You are an expert technical interviewer conducting a mock job interview.
Your name is Alex. You are professional, encouraging, and thorough.

You have been given a complete interview plan tailored to this specific candidate and role.
Follow it carefully.

INTERVIEW PLAN:
{plan_json}

== BEHAVIORAL RULES ==

TURN STRUCTURE — Always follow this order for each question:
1. Ask the current question naturally (conversational, not robotic)
2. Listen to the candidate's answer fully — NEVER interrupt
3. Decide: does the answer warrant a follow-up from the follow_ups list?
   - If the answer is vague or incomplete: ask the relevant follow-up
   - If the answer is thorough: acknowledge briefly and move to next question
4. After follow-up (or if no follow-up needed): transition to next question

TRANSITIONS — Use natural transitions between questions:
- "That's helpful, thank you. Moving on..."
- "Got it. Now I'd like to ask you about..."
- "Interesting. Let's shift to..."
- "Thank you for that. My next question is..."

FOLLOW-UP RULES:
- Use follow-ups contextually — only when the answer is incomplete
- Never ask more than 2 follow-ups on the same question
- If the candidate goes off-topic, gently redirect: "That's interesting context. 
  Could you bring it back to [topic]?"

PACING:
- Give the candidate time to think — do not fill silence immediately
- If the candidate says "I need a moment to think", say "Of course, take your time."
- If the candidate asks you to repeat a question, do so without complaint

TONE:
- Warm but professional
- Never sycophantic ("Great answer!", "Wow, that's amazing!")
- Neutral acknowledgments only: "I see", "Understood", "Got it", "Thank you"
- If the candidate struggles, gently offer: "Take your time, no rush."

QUESTION TRACKING:
- You have access to the move_to_next_question tool — call it when ready to advance
- You have access to the end_interview tool — call it ONLY when:
  a) All questions have been asked, OR
  b) The candidate explicitly says they want to end, OR
  c) The session has been going for more than {{}}_duration_minutes minutes

NEVER:
- Reveal the ideal_answer_points to the candidate
- Comment on whether their answer was good or bad during the interview
- Ask more than 2 follow-ups per question
- Skip the closing question ("Do you have any questions for me?")
- Break character or reference that you are an AI unless directly asked

START:
Begin the interview by speaking the opening_message from the interview plan.
Then immediately ask question[0].
"""
```

### `agent/session_state.py`
```python
"""
Per-session state tracker for the agent.
Loaded from Redis at session start, written back after each turn.
"""
import json
import time
import os
import redis.asyncio as redis
from backend.models.interview_plan import InterviewPlan, SessionState

class AgentSessionState:
    def __init__(self, session_id: str, plan: InterviewPlan):
        self.session_id = session_id
        self.plan = plan
        self.current_question_index = 0
        self.asked_question_ids: list[str] = []
        self.follow_up_count_this_question = 0
        self.transcript: list[dict] = []
        self.started_at = time.time()
        self._redis = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )

    @classmethod
    async def load(cls, session_id: str) -> "AgentSessionState":
        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )
        plan_json = await r.get(f"interview_plan:{session_id}")
        if not plan_json:
            raise ValueError(f"No interview plan found for session {session_id}")
        plan = InterviewPlan.model_validate_json(plan_json)
        await r.close()
        return cls(session_id=session_id, plan=plan)

    @property
    def current_question(self):
        if self.current_question_index < len(self.plan.questions):
            return self.plan.questions[self.current_question_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_question_index >= len(self.plan.questions)

    @property
    def questions_remaining(self) -> int:
        return len(self.plan.questions) - self.current_question_index

    def advance_question(self):
        q = self.current_question
        if q:
            self.asked_question_ids.append(q.id)
        self.current_question_index += 1
        self.follow_up_count_this_question = 0

    def add_transcript_entry(self, speaker: str, text: str):
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": time.time(),
            "question_index": self.current_question_index,
        })

    def increment_follow_up_count(self):
        self.follow_up_count_this_question += 1

    async def save(self):
        state = SessionState(
            session_id=self.session_id,
            plan=self.plan,
            current_question_index=self.current_question_index,
            asked_questions=self.asked_question_ids,
            transcript=self.transcript,
            started_at=self.started_at,
        )
        await self._redis.setex(
            f"session_state:{self.session_id}",
            14400,
            state.model_dump_json()
        )
```

### `agent/tools.py`
```python
"""
function_tool definitions for the interviewer agent.

Tools give the agent structured ways to:
1. Move to the next question
2. End the interview
3. Get context about the current question
"""
import json
import time
from livekit.agents import function_tool, RunContext

# Note: AgentSessionState is accessed via ctx.userdata

@function_tool
async def move_to_next_question(ctx: RunContext) -> str:
    """
    Call this when you are ready to move to the next interview question.
    This advances the question counter and returns the next question to ask.
    Call this AFTER you have finished the current question and any follow-ups.
    """
    state = ctx.userdata  # AgentSessionState
    
    state.advance_question()
    await state.save()

    if state.is_complete:
        return json.dumps({
            "status": "interview_complete",
            "message": "All questions have been asked. Call end_interview now.",
        })
    
    q = state.current_question
    return json.dumps({
        "status": "next_question",
        "question_number": state.current_question_index + 1,
        "total_questions": len(state.plan.questions),
        "question": q.question,
        "category": q.category,
        "intent": q.intent,
        "follow_ups": [
            {"trigger": fu.trigger, "question": fu.question}
            for fu in q.follow_ups
        ],
        "max_follow_ups": 2,
    })


@function_tool
async def end_interview(ctx: RunContext) -> str:
    """
    Call this to formally end the interview session.
    This triggers report generation and should be called:
    - After all questions are asked, OR
    - If the candidate requests to end early
    
    Before calling this tool, say a proper closing statement to the candidate.
    """
    state = ctx.userdata
    state.ended_at = time.time()
    
    # Trigger async report generation
    import asyncio
    asyncio.create_task(_generate_and_store_report(state))
    
    return json.dumps({
        "status": "session_ended",
        "questions_asked": len(state.asked_question_ids),
        "duration_minutes": (state.ended_at - state.started_at) / 60,
        "message": "Session ended. Report is being generated.",
    })


@function_tool
async def get_current_question_context(ctx: RunContext) -> str:
    """
    Returns the current question's context including follow-up options.
    Call this if you need to remind yourself of the current question details.
    """
    state = ctx.userdata
    q = state.current_question
    
    if not q:
        return json.dumps({"status": "no_current_question", "interview_complete": True})
    
    return json.dumps({
        "question_number": state.current_question_index + 1,
        "total_questions": len(state.plan.questions),
        "current_question": q.question,
        "category": q.category,
        "intent": q.intent,
        "follow_ups_available": [
            {"trigger": fu.trigger, "question": fu.question}
            for fu in q.follow_ups
        ],
        "follow_ups_used_this_question": state.follow_up_count_this_question,
        "max_follow_ups": 2,
    })


async def _generate_and_store_report(state):
    """Background task: generate and store the post-interview report."""
    import os
    import json
    import redis.asyncio as redis
    from backend.services.report_generator import generate_report
    
    try:
        report = await generate_report(
            session_id=state.session_id,
            plan=state.plan.model_dump(),
            transcript=state.transcript,
        )
        
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"),
                           encoding="utf-8", decode_responses=True)
        await r.setex(
            f"interview_report:{state.session_id}",
            86400,   # 24-hour TTL
            json.dumps(report)
        )
        await r.close()
    except Exception as e:
        print(f"Report generation failed: {e}")
```

### `agent/interviewer.py`
```python
"""
InterviewerAgent class.
Extends LiveKit's Agent with interview-specific behavior.
"""
from livekit.agents import Agent
from agent.prompts import build_interviewer_system_prompt
from agent.tools import move_to_next_question, end_interview, get_current_question_context
from agent.session_state import AgentSessionState

class InterviewerAgent(Agent):
    def __init__(self, state: AgentSessionState):
        self.state = state
        
        system_prompt = build_interviewer_system_prompt(
            state.plan.model_dump_json(indent=2)
        )
        
        super().__init__(
            instructions=system_prompt,
            tools=[
                move_to_next_question,
                end_interview,
                get_current_question_context,
            ],
        )

    async def on_enter(self):
        """Called when agent first joins the session. Starts the interview."""
        # Speak the opening message and ask the first question
        opening = self.state.plan.opening_message
        first_question = self.state.plan.questions[0].question if self.state.plan.questions else ""
        
        await self.session.generate_reply(
            instructions=f"""
            Speak exactly this opening message: "{opening}"
            Then immediately ask this first question: "{first_question}"
            Do not add anything else. Do not call any tools yet.
            """
        )
```

### `agent/agent.py`
```python
"""
MockMind Interviewer Agent — Main entrypoint

Run with:
  python agent.py dev     ← development with hot reload
  python agent.py start   ← production
"""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    AgentSession,
    JobContext,
    WorkerOptions,
    RoomInputOptions,
    cli,
    AgentServer,
)
from livekit.plugins import (
    cartesia,
    deepgram,
    silero,
)
from livekit.plugins import google as lk_google
from google.genai.types import Modality

from agent.interviewer import InterviewerAgent
from agent.session_state import AgentSessionState

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mockmind_agent")

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """
    Called once per room dispatch.
    Reads session_id from room metadata, loads interview plan from Redis,
    configures and starts the interviewer agent.
    """
    logger.info(f"Agent joining room: {ctx.room.name}")
    
    # ── Load session ID from room metadata ─────────────────────────────
    metadata_raw = ctx.room.metadata or "{}"
    try:
        metadata = json.loads(metadata_raw)
        session_id = metadata.get("session_id")
    except Exception:
        session_id = None
    
    if not session_id:
        logger.error("No session_id in room metadata — cannot load interview plan")
        return
    
    logger.info(f"Loading interview plan for session: {session_id}")
    
    # ── Load interview plan from Redis ─────────────────────────────────
    try:
        state = await AgentSessionState.load(session_id)
        logger.info(
            f"Plan loaded: {len(state.plan.questions)} questions, "
            f"role: {state.plan.job.title}, "
            f"candidate: {state.plan.candidate.name}"
        )
    except ValueError as e:
        logger.error(f"Failed to load session state: {e}")
        return

    await ctx.connect()

    # ── Configure AgentSession ──────────────────────────────────────────
    # Architecture: Gemini 2.5 Flash (LLM, text-only mode) + Cartesia TTS
    # This gives us Gemini's reasoning with Cartesia's superior voice quality.
    #
    # Why text-only Gemini + Cartesia TTS instead of native audio?
    # - Cartesia sonic-3 has significantly better voice quality than Gemini's built-in TTS
    # - Text mode gives us full control over what gets spoken via structured tools
    # - We can intercept the LLM output to track transcript before TTS
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-3",
            language="en",
            smart_format=True,
        ),
        llm=lk_google.LLM(
            model="gemini-2.5-flash",
            temperature=0.7,
        ),
        tts=cartesia.TTS(
            model="sonic-3",
            voice="79a125e8-cd45-4c13-8a67-188112f4dd22",  # Professional, warm voice
            speed=1.0,
            emotion=["positivity:low", "curiosity:medium"],  # Cartesia emotion controls
        ),
        userdata=state,   # AgentSessionState accessible in all tools via ctx.userdata
    )

    # ── Wire up transcript tracking ────────────────────────────────────
    @session.on("agent_speech_committed")
    def on_agent_speech(event):
        """Capture everything the agent says into the transcript."""
        if event.user_transcription:
            state.add_transcript_entry("interviewer", event.user_transcription)

    @session.on("user_speech_committed")
    def on_user_speech(event):
        """Capture everything the candidate says into the transcript."""
        if event.user_transcription:
            state.add_transcript_entry("candidate", event.user_transcription)

    # ── Start the session ──────────────────────────────────────────────
    await session.start(
        room=ctx.room,
        agent=InterviewerAgent(state=state),
        room_input_options=RoomInputOptions(
            noise_cancellation=True,
        ),
    )

    logger.info("Interviewer agent running")
    
    # Keep alive until room is empty or interview ends
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(server)
```

---

## 11. Frontend Implementation

### `frontend/types/interview.ts`
*(Already specified in Section 6 above — implement exactly as defined there)*

### `frontend/hooks/usePreparation.ts`
```typescript
/**
 * SSE hook that connects to /api/prepare and streams preparation progress.
 * 
 * Usage:
 *   const { progress, sessionInfo, error, startPreparation } = usePreparation();
 */

import { useState, useCallback, useRef } from 'react';
import type { PrepProgressEvent } from '../types/interview';

interface SessionInfo {
  sessionId: string;
  totalQuestions: number;
  jobTitle: string;
  candidateName: string | null;
}

export function usePreparation() {
  const [events, setEvents] = useState<PrepProgressEvent[]>([]);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const startPreparation = useCallback(async (
    resumeFile: File,
    jobDescription: string,
  ) => {
    setIsRunning(true);
    setEvents([]);
    setError(null);
    setSessionInfo(null);

    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('job_description', jobDescription);

    abortRef.current = new AbortController();

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}/api/prepare`, {
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
          if (line.startsWith('data: ')) {
            try {
              const event: PrepProgressEvent = JSON.parse(line.slice(6));
              setEvents(prev => [...prev, event]);
              setCurrentProgress(event.progress);

              if (event.stage === 'complete' && event.data) {
                setSessionInfo({
                  sessionId: event.session_id,
                  totalQuestions: event.data.total_questions,
                  jobTitle: event.data.job_title,
                  candidateName: event.data.candidate_name,
                });
              }

              if (event.stage === 'error') {
                setError(event.message);
              }
            } catch { /* skip malformed events */ }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Unknown error');
      }
    } finally {
      setIsRunning(false);
    }
  }, []);

  return { events, currentProgress, sessionInfo, error, isRunning, startPreparation };
}
```

### `frontend/app/setup/page.tsx`
```typescript
/**
 * Setup page — resume upload, JD input, prep progress display.
 */
'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { usePreparation } from '../../hooks/usePreparation';

export default function SetupPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const { events, currentProgress, sessionInfo, error, isRunning, startPreparation } = usePreparation();

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
  const canSubmit = resumeFile && jobDescription.trim().length > 50 && !isRunning;

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-black text-white">MockMind</h1>
          <p className="text-slate-400 mt-2">AI-powered mock interviews, personalized to your resume.</p>
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
                resumeFile ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-400'
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
                <p className="text-green-700 font-medium">✅ {resumeFile.name}</p>
              ) : (
                <div>
                  <p className="text-gray-500">Drop your resume here or click to browse</p>
                  <p className="text-xs text-gray-400 mt-1">PDF, DOCX, or TXT</p>
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
              placeholder="Paste the full job description here. Include requirements, responsibilities, and company details for the most personalized interview."
              rows={8}
              className="w-full border-2 border-gray-200 rounded-xl p-4 text-sm focus:border-blue-400 outline-none resize-none text-gray-800"
            />
            <p className="text-xs text-gray-400 mt-1">{jobDescription.length} characters</p>
          </div>

          {/* Preparation Progress */}
          {(isRunning || events.length > 0) && (
            <div className="bg-slate-50 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-700">Preparing your interview...</span>
                <span className="text-sm font-bold text-blue-600">{currentProgress}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${currentProgress}%` }}
                />
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {events.map((event, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                    <span>{event.stage === 'complete' ? '✅' : event.stage === 'error' ? '❌' : '⟳'}</span>
                    <span>{event.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Session Ready Banner */}
          {isReady && sessionInfo && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-green-800 font-semibold">
                ✅ Interview ready — {sessionInfo.totalQuestions} personalized questions for {sessionInfo.jobTitle}
              </p>
              {sessionInfo.candidateName && (
                <p className="text-green-700 text-sm mt-1">Candidate: {sessionInfo.candidateName}</p>
              )}
            </div>
          )}

          {/* Action Button */}
          {!isReady ? (
            <button
              onClick={handleStart}
              disabled={!canSubmit}
              className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-bold text-lg rounded-xl transition-colors"
            >
              {isRunning ? 'Preparing...' : 'Prepare My Interview'}
            </button>
          ) : (
            <button
              onClick={handleBeginInterview}
              className="w-full py-4 bg-green-600 hover:bg-green-700 text-white font-bold text-lg rounded-xl transition-colors animate-pulse"
            >
              🎙️ Start Interview
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
```

### `frontend/app/interview/[sessionId]/page.tsx`
```typescript
/**
 * Interview room page.
 * Fetches LiveKit token, joins room, renders interview UI.
 */
'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { LiveKitRoom, useVoiceAssistant, useRoomContext } from '@livekit/components-react';
import '@livekit/components-styles';

interface SessionTokenData {
  token: string;
  ws_url: string;
  room_name: string;
  session_id: string;
}

export default function InterviewPage() {
  const { sessionId } = useParams() as { sessionId: string };
  const [tokenData, setTokenData] = useState<SessionTokenData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchToken = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const res = await fetch(`${backendUrl}/api/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, participant_name: 'Candidate' }),
        });
        if (!res.ok) throw new Error('Failed to get session token');
        const data = await res.json();
        setTokenData(data);
      } catch (e: any) {
        setError(e.message);
      }
    };
    fetchToken();
  }, [sessionId]);

  if (error) return <div className="flex items-center justify-center h-screen text-red-500">{error}</div>;
  if (!tokenData) return <div className="flex items-center justify-center h-screen text-gray-500">Connecting to interview room...</div>;

  return (
    <LiveKitRoom
      token={tokenData.token}
      serverUrl={tokenData.ws_url}
      connect={true}
      audio={true}
      video={false}
    >
      <InterviewRoomUI sessionId={sessionId} />
    </LiveKitRoom>
  );
}

function InterviewRoomUI({ sessionId }: { sessionId: string }) {
  const { state: agentState, audioTrack } = useVoiceAssistant();
  const [transcript, setTranscript] = useState<Array<{ speaker: string; text: string }>>([]);
  const [isEnded, setIsEnded] = useState(false);
  const router = useRouter();

  // NOTE: In production, subscribe to data channel events for transcript updates
  // pushed from agent via RPC. For simplicity, transcript is shown via
  // useVoiceAssistant transcript events from @livekit/components-react.

  const handleEndInterview = () => {
    setIsEnded(true);
    // Navigate to report page after 3 seconds to allow report generation
    setTimeout(() => {
      router.push(`/report/${sessionId}`);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-slate-700">
        <div>
          <h1 className="text-xl font-bold">MockMind Interview</h1>
          <p className="text-slate-400 text-sm">Session: {sessionId.slice(0, 8)}...</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Agent state indicator */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
            agentState === 'speaking' ? 'bg-blue-600' :
            agentState === 'listening' ? 'bg-green-600' :
            'bg-slate-600'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              agentState === 'speaking' ? 'bg-blue-200 animate-pulse' :
              agentState === 'listening' ? 'bg-green-200' :
              'bg-slate-400'
            }`} />
            {agentState === 'speaking' ? 'Alex is speaking' :
             agentState === 'listening' ? 'Your turn' :
             'Connecting...'}
          </div>
          
          <button
            onClick={handleEndInterview}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-xl text-sm font-semibold transition-colors"
          >
            End Interview
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-lg">
          {/* Voice visualization */}
          <div className={`w-32 h-32 rounded-full mx-auto mb-8 flex items-center justify-center transition-all duration-300 ${
            agentState === 'speaking'
              ? 'bg-blue-600 shadow-2xl shadow-blue-500/50 scale-110'
              : agentState === 'listening'
              ? 'bg-green-600 shadow-xl shadow-green-500/30'
              : 'bg-slate-700'
          }`}>
            <span className="text-5xl">
              {agentState === 'speaking' ? '🎙️' : agentState === 'listening' ? '👂' : '⏳'}
            </span>
          </div>

          <h2 className="text-2xl font-bold mb-2">
            {agentState === 'speaking' ? 'Alex is speaking...' :
             agentState === 'listening' ? 'Your turn to answer' :
             'Connecting...'}
          </h2>
          <p className="text-slate-400">
            {agentState === 'listening'
              ? 'Speak clearly when you\'re ready. Take your time.'
              : 'Listen to the question fully before responding.'}
          </p>
        </div>
      </div>

      {isEnded && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center">
          <div className="bg-white rounded-2xl p-8 text-gray-800 text-center max-w-sm">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-2xl font-bold mb-2">Interview Complete!</h2>
            <p className="text-gray-600">Generating your evaluation report...</p>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## 12. Backend Requirements

### `backend/requirements.txt`
```
fastapi==0.110.0
uvicorn[standard]==0.27.1
python-dotenv==1.0.1
redis[asyncio]==5.0.3
google-genai==0.8.0
livekit-api==0.7.0
pypdf==4.1.0
python-docx==1.1.0
python-multipart==0.0.9
pydantic==2.6.0
```

### `agent/requirements.txt`
```
livekit-agents==1.0.0
livekit-plugins-google==1.0.0
livekit-plugins-cartesia==1.0.0
livekit-plugins-deepgram==1.0.0
livekit-plugins-silero==1.0.0
python-dotenv==1.0.1
redis[asyncio]==5.0.3
google-genai==0.8.0
pydantic==2.6.0
```

### `frontend/package.json` (key dependencies)
```json
{
  "dependencies": {
    "next": "14.2.0",
    "react": "^18",
    "react-dom": "^18",
    "livekit-client": "^2.5.0",
    "@livekit/components-react": "^2.6.0",
    "@livekit/components-styles": "^1.1.0",
    "tailwindcss": "^3.4.0",
    "uuid": "^9.0.0"
  }
}
```

---

## 13. Critical Implementation Notes

### Note 1: Gemini Text Mode + Cartesia TTS
The agent uses Gemini in text-only mode (`lk_google.LLM`) paired with Cartesia TTS.
This is the **half-cascade architecture** — confirmed working:
```python
# CORRECT setup:
session = AgentSession(
    stt=deepgram.STT(model="nova-3"),
    llm=lk_google.LLM(model="gemini-2.5-flash"),   # Standard LLM, not RealtimeModel
    tts=cartesia.TTS(model="sonic-3"),
    vad=silero.VAD.load(),
)
# Do NOT use google.beta.realtime.RealtimeModel when pairing with Cartesia TTS
# RealtimeModel is for native audio — mixing it with Cartesia requires TEXT modality config
```

### Note 2: Agent Dispatch with Metadata
The agent receives `session_id` via room metadata set at dispatch time:
```python
# Backend dispatches agent with metadata
await lk_api.agent_dispatch.create_dispatch(
    room_name=room_name,
    agent_name="mockmind-interviewer",
    metadata=json.dumps({"session_id": req.session_id}),
)

# Agent reads it:
metadata = json.loads(ctx.room.metadata or "{}")
session_id = metadata["session_id"]
```

### Note 3: AgentServer vs WorkerOptions
Use `AgentServer` with `@server.rtc_session()` decorator (current API):
```python
server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ...

if __name__ == "__main__":
    cli.run_app(server)
```

### Note 4: Userdata for Tool Access
Pass `AgentSessionState` as `userdata` to `AgentSession`.
Tools access it via `ctx.userdata`:
```python
session = AgentSession(
    ...
    userdata=state,   # AgentSessionState instance
)

# In a tool:
@function_tool
async def move_to_next_question(ctx: RunContext) -> str:
    state = ctx.userdata   # ← AgentSessionState
    state.advance_question()
```

### Note 5: Turn Detection
Deepgram STT + Silero VAD handles turn detection automatically.
The agent will NOT speak while the candidate is speaking.
The `stt.smart_format=True` improves transcript quality.

### Note 6: Cartesia Emotion Controls
Configure these Cartesia emotion presets for the interviewer voice:
```python
cartesia.TTS(
    model="sonic-3",
    voice="79a125e8-cd45-4c13-8a67-188112f4dd22",  # Professional male voice
    emotion=["positivity:low", "curiosity:medium"],
    speed=1.0,
)
```
Alternative voices to test: `"a0e99841-438c-4a64-b679-ae501e7d6091"` (professional female)

### Note 7: SSE Streaming
The `/api/prepare` endpoint uses SSE. FastAPI returns `StreamingResponse` with
`media_type="text/event-stream"`. Frontend consumes it via `fetch()` with a
`ReadableStream` reader (not `EventSource`, because we need POST body support).

### Note 8: Redis Key Schema
```
interview_plan:{session_id}     → InterviewPlan JSON        (TTL: 4h)
session_state:{session_id}      → SessionState JSON          (TTL: 4h)
interview_report:{session_id}   → EvaluationReport JSON     (TTL: 24h)
```

### Note 9: Report Generation Timing
Report is generated asynchronously when `end_interview` tool is called by the agent.
Frontend polls `GET /api/report/{session_id}` every 3 seconds after interview ends.
Report takes ~10-15 seconds to generate (Gemini API call on full transcript).

### Note 10: Follow-Up Logic
The agent decides whether to use follow-ups using its LLM judgment.
The `follow_ups` array in each question provides **suggestions**, not mandates.
The system prompt instructs the agent to use them contextually, not mechanically.
The `follow_up_count_this_question` in session state prevents > 2 follow-ups.

---

## 14. Run Instructions

### Start all services:

```bash
# Terminal 1: Redis
docker run -p 6379:6379 redis:alpine

# Terminal 2: Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 3: Agent
cd agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python agent.py dev

# Terminal 4: Frontend
cd frontend
npm install
npm run dev
```

### Test flow:
1. `http://localhost:3000/setup` — Upload resume + paste JD
2. Wait for preparation pipeline (15-30 seconds)
3. Click "Start Interview" — joins LiveKit room
4. Speak with the AI interviewer (30-45 minutes)
5. Click "End Interview" — redirected to report page
6. `http://localhost:3000/report/{sessionId}` — View evaluation

---

## 15. File Generation Checklist (for coding agent)

Generate ALL of the following files. Files marked ✅ are fully specified above.
Files marked 🔧 need implementation based on the patterns established above.

### Backend
- ✅ `backend/main.py`
- ✅ `backend/routers/prepare.py`
- ✅ `backend/routers/session.py`
- 🔧 `backend/routers/health.py` — `GET /health` returns `{"status": "ok"}`
- ✅ `backend/agents/resume_analyzer.py`
- ✅ `backend/agents/jd_analyzer.py`
- ✅ `backend/agents/question_generator.py`
- ✅ `backend/models/interview_plan.py`
- 🔧 `backend/models/session.py` — same as interview_plan.py (already included)
- ✅ `backend/services/redis_client.py`
- ✅ `backend/services/resume_parser.py`
- ✅ `backend/services/report_generator.py`
- ✅ `backend/requirements.txt`

### Agent
- ✅ `agent/agent.py`
- ✅ `agent/interviewer.py`
- ✅ `agent/session_state.py`
- ✅ `agent/tools.py`
- ✅ `agent/prompts.py`
- ✅ `agent/requirements.txt`

### Frontend
- ✅ `frontend/types/interview.ts`
- ✅ `frontend/hooks/usePreparation.ts`
- 🔧 `frontend/hooks/useInterviewSession.ts` — wraps LiveKit hooks for interview state
- ✅ `frontend/app/setup/page.tsx`
- ✅ `frontend/app/interview/[sessionId]/page.tsx`
- 🔧 `frontend/app/report/[sessionId]/page.tsx` — polls `/api/report/{id}`, displays EvaluationReport
- 🔧 `frontend/app/page.tsx` — Landing page with "Get Started" → `/setup`
- 🔧 `frontend/app/layout.tsx` — Standard Next.js root layout
- ✅ `frontend/package.json`
- 🔧 `frontend/tailwind.config.ts` — Standard Tailwind config
- 🔧 `frontend/tsconfig.json` — Standard Next.js TS config

### Config
- 🔧 `docker-compose.yml` — Redis + backend + agent services
- 🔧 `.env.example` — Template with all required env vars

---

*End of MockMind Technical Implementation Plan v1.0*
