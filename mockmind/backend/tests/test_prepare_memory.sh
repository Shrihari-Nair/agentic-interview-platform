#!/usr/bin/env bash
# Run: cd mockmind && bash backend/tests/test_prepare_memory.sh
# Requires: backend running on :8000 (backend/.venv/bin/uvicorn backend.main:app --port 8000),
# a real Redis, and GOOGLE_API_KEY set.
set -euo pipefail

RESUME_FILE=$(mktemp /tmp/resume-XXXX.txt)
echo "Priya Sharma. Backend Engineer. 4 years. Python, FastAPI, Docker." > "$RESUME_FILE"

echo "--- Request WITHOUT use_memory (should work exactly as before) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  | tee /tmp/prepare_no_memory.sse
grep -q '"stage": "complete"' /tmp/prepare_no_memory.sse && echo "no-memory request completed: PASS"

echo ""
echo "--- Request WITH use_memory=true and a blank email (Review Focus #2 — must not error) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  -F "use_memory=true" \
  -F "candidate_email=" \
  | tee /tmp/prepare_blank_email.sse
grep -q '"stage": "complete"' /tmp/prepare_blank_email.sse && echo "use_memory with blank email still completes: PASS"

echo ""
echo "--- Request WITH use_memory=true and a real email (should complete normally) ---"
curl -sS -X POST http://localhost:8000/api/prepare \
  -F "resume=@${RESUME_FILE}" \
  -F "job_description=AI Engineer role requiring Python, LLMs, Docker, Kubernetes, and strong system design skills for a growing startup." \
  -F "use_memory=true" \
  -F "candidate_email=prepare-test@example.com" \
  | tee /tmp/prepare_with_email.sse
grep -q '"stage": "complete"' /tmp/prepare_with_email.sse && echo "use_memory with real email completes: PASS"

rm -f "$RESUME_FILE"
