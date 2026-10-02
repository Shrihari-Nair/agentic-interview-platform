import os
from contextlib import contextmanager

from langfuse import get_client, propagate_attributes

DEFAULT_MODEL = "gemini-2.5-flash"


def is_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


class _GenerationHandle:
    def __init__(self, generation):
        self._generation = generation

    def record_response(self, response, output=None):
        usage = getattr(response, "usage_metadata", None)
        usage_details = None
        if usage is not None:
            usage_details = {
                "input": usage.prompt_token_count,
                "output": usage.candidates_token_count,
                "total": usage.total_token_count,
            }
        self._generation.update(
            output=output if output is not None else getattr(response, "text", None),
            usage_details=usage_details,
        )

    def record_error(self, error: Exception):
        self._generation.update(level="ERROR", status_message=str(error))


class _NoopGenerationHandle:
    def record_response(self, *args, **kwargs):
        pass

    def record_error(self, *args, **kwargs):
        pass


@contextmanager
def traced_generation(name: str, *, session_id: str, input_data, model: str = DEFAULT_MODEL):
    """
    Wraps a single Gemini call as a Langfuse "generation" observation grouped
    under `session_id`, so the whole prepare -> interview -> report chain for
    one candidate shows up as one session in the Langfuse UI. A no-op when
    Langfuse isn't configured (LANGFUSE_PUBLIC_KEY/SECRET_KEY unset) — tracing
    is observability, never a hard dependency for the app to function.

    Usage:
        with traced_generation("resume_analysis", session_id=session_id, input_data=prompt) as gen:
            response = await client.aio.models.generate_content(...)
            gen.record_response(response)
            ... (anything else inside this block that raises is recorded as an error)
    """
    if not is_enabled():
        yield _NoopGenerationHandle()
        return

    client = get_client()
    with propagate_attributes(session_id=session_id):
        with client.start_as_current_observation(
            as_type="generation", name=name, model=model, input=input_data
        ) as generation:
            handle = _GenerationHandle(generation)
            try:
                yield handle
            except Exception as e:
                handle.record_error(e)
                raise
