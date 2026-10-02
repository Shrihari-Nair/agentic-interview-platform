import os

from google import genai
from google.genai import types

from backend.services.tracing import traced_generation
from evals.personas import PERSONAS


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
        with traced_generation(
            f"candidate_simulator[{self.persona}]",
            session_id=self.session_id,
            input_data=interviewer_message,
        ) as gen:
            response = await self._chat.send_message(interviewer_message)
            gen.record_response(response)
            return response.text or "(no response)"
