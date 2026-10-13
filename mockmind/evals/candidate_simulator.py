import os

from google import genai
from google.genai import types

from backend.services.tracing import traced_generation
from backend.services.llm_retry import retry_async
from evals.personas import CODING_STYLE, DEFAULT_CODING_STYLE, PERSONAS


class CandidateSimulator:
    """Plays the candidate side of a simulated interview using a persona
    system prompt. Owns its own Gemini chat session (no tools — it only
    ever replies in character)."""

    def __init__(self, persona: str, session_id: str, model: str = "gemini-2.5-flash"):
        if persona not in PERSONAS:
            raise ValueError(f"Unknown persona '{persona}'. Options: {list(PERSONAS)}")
        self.persona = persona
        self.session_id = session_id
        self._client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self._chat = self._client.aio.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=PERSONAS[persona],
                temperature=0.8,
            ),
        )

    async def respond(self, interviewer_message: str) -> str:
        # Idempotent: a failed send leaves the chat history untouched, so retrying is safe.
        return await retry_async(
            lambda: self._respond_once(interviewer_message), label=f"simulator[{self.persona}]"
        )

    async def write_code(self, problem_statement: str, starter_code: str = "") -> str:
        """The code this persona would submit for a live-coding problem."""
        prompt = (
            f"{PERSONAS[self.persona]}\n\nYou were just shown this coding problem:\n"
            f"{problem_statement}\n\nStarter code:\n{starter_code}\n\n"
            f"{CODING_STYLE.get(self.persona, DEFAULT_CODING_STYLE)}\n"
            "Return ONLY the complete Python code, no explanation, no markdown fences."
        )

        async def once() -> str:
            with traced_generation(
                f"candidate_code[{self.persona}]", session_id=self.session_id, input_data=prompt
            ) as gen:
                response = await self._client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=4096),
                )
                gen.record_response(response)
                text = (response.text or "").strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("python"):
                        text = text[len("python"):]
                if not text.strip():
                    raise ValueError("empty code from candidate simulator")
                return text.strip()

        return await retry_async(once, label=f"simulator_code[{self.persona}]")

    async def _respond_once(self, interviewer_message: str) -> str:
        with traced_generation(
            f"candidate_simulator[{self.persona}]",
            session_id=self.session_id,
            input_data=interviewer_message,
        ) as gen:
            response = await self._chat.send_message(interviewer_message)
            gen.record_response(response)
            return response.text or "(no response)"
