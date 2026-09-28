# MockMind

MockMind is an AI-powered voice mock-interview platform. A candidate uploads their resume and pastes a job description, an LLM pipeline generates a tailored interview question bank, the candidate then does a live spoken interview with an AI interviewer over LiveKit, and finally receives a scored feedback report.

The application lives in [`mockmind/`](mockmind); this repo also contains the original design spec, [`MOCK_INTERVIEW_PLATFORM.md`](MOCK_INTERVIEW_PLATFORM.md).

## How it works

1. **Setup** — The candidate uploads a resume and pastes a job description. The backend runs three Gemini-based sub-agents in sequence (resume analysis → job description analysis → question generation) and streams progress to the frontend over SSE. The resulting interview plan is stored in Redis.
2. **Interview** — The candidate joins a LiveKit room. LiveKit auto-dispatches an AI interviewer agent, which loads the interview plan from Redis and conducts a real-time voice interview: it asks the generated questions, asks natural follow-ups, and advances through the question bank.
3. **Report** — When the interview ends, the transcript and plan are sent to Gemini to generate a scored evaluation (overall score, category breakdown, strengths, per-question feedback, hiring recommendation), which the frontend polls for and displays.

## Architecture

```
Browser (Next.js) ──HTTP──> FastAPI backend ──> Redis (interview plan, session state, report)
Browser (Next.js) ──WebRTC/LiveKit──> LiveKit Cloud room <── agent dispatch ("mockmind-interviewer")
LiveKit Agent (Python) ──reads/writes state──> Redis
```

The FastAPI backend and the LiveKit agent are separate processes that never call each other directly — they communicate only through shared state in Redis (interview plan, live session state, final report).

### Components

| Component | Path | Description |
|---|---|---|
| Frontend | [`mockmind/frontend/`](mockmind/frontend) | Next.js 14 (App Router) app — landing page, resume/JD setup, live interview room, report view |
| Backend API | [`mockmind/backend/`](mockmind/backend) | FastAPI service — resume/JD analysis, question generation, LiveKit token minting, report polling |
| Voice agent | [`mockmind/agent/`](mockmind/agent) | LiveKit Agents Python worker — runs the interviewer, drives the interview via STT/LLM/TTS |
| Design doc | [`MOCK_INTERVIEW_PLATFORM.md`](MOCK_INTERVIEW_PLATFORM.md) | Original design spec for the platform |

### Backend API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/prepare` | SSE endpoint — analyzes resume + JD and generates the interview plan |
| `POST` | `/api/token` | Mints a LiveKit access token and dispatches the interviewer agent to the room |
| `GET` | `/api/report/{session_id}` | Polls for the generated evaluation report |
| `GET` | `/health` | Health check |

## Tech stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, `livekit-client`, `@livekit/components-react`
- **Backend**: Python, FastAPI, Uvicorn
- **Voice agent**: LiveKit Agents SDK — Soniox (STT), Gemini 2.5 Flash (LLM), Cartesia (TTS), Silero (VAD)
- **LLM**: Google Gemini 2.5 Flash (`google-genai`) for resume/JD analysis, question generation, and report generation
- **State store**: Redis
- **Resume parsing**: `pypdf`, `python-docx`

## Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (for Redis, or to run the whole stack)
- API keys: [LiveKit Cloud](https://cloud.livekit.io), [Google Gemini](https://aistudio.google.com/apikey), [Cartesia](https://play.cartesia.ai/keys), [Soniox](https://console.soniox.com)

## Configuration

Copy the env templates and fill in your keys:

```bash
cp mockmind/.env.example mockmind/.env
cp mockmind/frontend/.env.local.example mockmind/frontend/.env.local
```

`mockmind/.env` (used by the backend and agent):

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | LiveKit Cloud project URL (`wss://...`) |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit Cloud credentials |
| `GOOGLE_API_KEY` | Gemini API key |
| `CARTESIA_API_KEY` | Cartesia TTS API key |
| `SONIOX_API_KEY` | Soniox STT API key |
| `REDIS_URL` | Redis connection string |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the backend |

`mockmind/frontend/.env.local` (used by the Next.js app, exposed to the browser):

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_LIVEKIT_URL` | Same LiveKit Cloud project URL |
| `NEXT_PUBLIC_BACKEND_URL` | Backend URL, e.g. `http://localhost:8000` |

## Running with Docker Compose

```bash
cd mockmind
docker compose up --build
```

This starts Redis, the backend (`:8000`), the agent, and the frontend (`:3000`). Open **http://localhost:3000**.

## Running locally without Docker

```bash
cd mockmind

# Redis
docker run -d --name mockmind-redis -p 6379:6379 redis:7-alpine

# Backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/uvicorn backend.main:app --reload --port 8000

# Agent (separate terminal)
python3 -m venv agent/.venv
agent/.venv/bin/pip install -r agent/requirements.txt
agent/.venv/bin/python agent/agent.py dev

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000**.

## Project structure

```
agentic-interview-platform/
├── MOCK_INTERVIEW_PLATFORM.md   # Design spec
└── mockmind/
    ├── agent/            # LiveKit voice agent (interviewer)
    ├── backend/          # FastAPI backend (analysis, question generation, tokens)
    ├── frontend/         # Next.js app
    ├── docker-compose.yml
    └── .env.example
```
