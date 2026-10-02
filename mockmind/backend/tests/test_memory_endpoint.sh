#!/usr/bin/env bash
# Run: cd mockmind && bash backend/tests/test_memory_endpoint.sh
# Requires: backend running on :8000, a real Redis.
set -euo pipefail

echo "--- Delete an email that was never stored (Review Focus #5 — must be a clean success) ---"
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/candidate-memory \
  -H "Content-Type: application/json" \
  -d '{"email": "never-stored-via-api@example.com"}')
[ "$STATUS" = "204" ] && echo "delete on non-existent email returns 204: PASS" || (echo "got $STATUS"; exit 1)

echo ""
echo "--- Missing email in body must be a 400, not a 500 ---"
STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/candidate-memory \
  -H "Content-Type: application/json" \
  -d '{"email": ""}')
[ "$STATUS" = "400" ] && echo "blank email returns 400: PASS" || (echo "got $STATUS"; exit 1)
