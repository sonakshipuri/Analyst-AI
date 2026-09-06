# orchestrator/utils.py
from types import SimpleNamespace
from utils.llm_utils import (
    invoke_llm_with_backoff,
    increment_llm_counter,
    budget_available,
    budget_message,
)
from config import MAX_LLM_CALLS_PER_RUN


def safe_llm_call(
    llm,
    prompt: str,
    execution_metadata: dict,
    max_calls: int = MAX_LLM_CALLS_PER_RUN,
) -> SimpleNamespace:
    """
    Centralized orchestration wrapper for LLM calls.

    Handles:
        - Budget enforcement (via MAX_LLM_CALLS_PER_RUN)
        - LLM usage tracking
        - Retry/backoff invocation

    Returns:
        A SimpleNamespace with a `.content` attribute containing the response text.
    """
    if not budget_available(execution_metadata, max_calls):
        raise RuntimeError(budget_message())

    increment_llm_counter(execution_metadata)

    return invoke_llm_with_backoff(llm, prompt)