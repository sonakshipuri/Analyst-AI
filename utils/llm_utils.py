# utils/llm_utils.py
import os
import re
import time
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_cerebras import ChatCerebras
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from pydantic import SecretStr

from config import (
    REQUEST_TIMEOUT,
    LIGHT_AGENTS,
    HEAVY_AGENTS,
    LIGHT_CHAIN,
    HEAVY_CHAIN,
    MAX_LLM_RETRIES,
    INITIAL_BACKOFF_DELAY,
)

load_dotenv()


def strip_code_fences(code: str) -> str:
    """Remove markdown code fences."""
    if not code:
        return ""
    code = re.sub(r"^```(?:python)?\s*", "", code.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", code).strip()


def coerce_text_content(value: Any) -> str:
    """Convert a variety of LLM SDK response payloads into a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text") or item.get("content")
                if isinstance(text_value, str):
                    parts.append(text_value)
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(value, dict):
        for key in ("text", "content", "output_text"):
            if isinstance(value.get(key), str):
                return value[key]
        return str(value)
    return str(value)


def normalize_llm_response(response: Any) -> SimpleNamespace:
    """Wrap LLM responses in a small object with a stable .content attribute."""
    content = getattr(response, "content", response)
    return SimpleNamespace(content=coerce_text_content(content), raw=response)


def increment_llm_counter(execution_metadata: dict) -> None:
    """Increment the LLM call counter inside the execution metadata."""
    execution_metadata.setdefault("llm_call_count", 0)
    execution_metadata.setdefault("llm_budget_exceeded", False)
    execution_metadata["llm_call_count"] += 1


def budget_available(execution_metadata: dict, max_calls: int) -> bool:
    """Check if the current LLM calls are within the allowed budget limit."""
    current = execution_metadata.get("llm_call_count", 0)
    if current >= max_calls:
        execution_metadata["llm_budget_exceeded"] = True
        return False
    return True


def budget_message() -> str:
    """Return the warning message for when the LLM budget is exceeded."""
    return (
        "LLM budget exceeded. Returning available insights."
    )


def create_llm(provider: str, model: str):
    """Factory method to initialize the requested LLM client."""
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        return ChatGroq(
            model=model,
            api_key=SecretStr(api_key) if api_key else None,
        )
        
    if provider == "cerebras":
        api_key = os.getenv("CEREBRAS_API_KEY")
        return ChatCerebras(
            model=model,
            api_key=SecretStr(api_key) if api_key else None,
        )
        
    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            request_timeout=REQUEST_TIMEOUT,
        )
    
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key) if api_key else None,
            base_url="https://api.deepseek.com/v1",
            timeout=REQUEST_TIMEOUT,
        )

            
    raise ValueError(f"Unsupported provider: {provider}")


@lru_cache(maxsize=32)
def get_llm(agent_name: str) -> dict:
    """Returns a cached configuration dictionary for the requesting agent."""
    return {
        "agent": agent_name
    }


def invoke_llm_with_backoff(
    llm: dict,
    prompt: str,
) -> SimpleNamespace:
    """
    Invoke the LLM using a cascading failover chain with exponential backoff.
    Returns a SimpleNamespace with .content attribute.
    """
    agent_name = llm["agent"]
    chain = LIGHT_CHAIN if agent_name in LIGHT_AGENTS else HEAVY_CHAIN if agent_name in HEAVY_AGENTS else None
    if chain is None:
        raise ValueError(f"Unknown agent type: {agent_name}")

    last_exception = None

    for provider, model in chain:
        # Retry on the same provider up to MAX_LLM_RETRIES times with backoff
        for attempt in range(MAX_LLM_RETRIES):
            try:
                client = create_llm(provider, model)
                response = client.invoke(prompt)
                return normalize_llm_response(response)
            except Exception as e:
                last_exception = e
                # Non-retryable errors: authentication, missing API key, invalid model
                error_lower = str(e).lower()
                if any(x in error_lower for x in ["authentication", "api key", "invalid model", "permission"]):
                    print(f"[LLM] Non-retryable error on {provider}: {e}")
                    break  # break retry loop, move to next provider

                # Exponential backoff with cap at 30 seconds
                delay = min(INITIAL_BACKOFF_DELAY * (2 ** attempt), 16.0)
                print(f"[RETRY] {provider}:{model} attempt {attempt+1}/{MAX_LLM_RETRIES} failed: {e}")
                print(f"[RETRY] Waiting {delay:.1f}s...")
                time.sleep(delay)
        # If we exhaust all retries for this provider, move to next in chain
        print(f"[FAILOVER] All retries exhausted for {provider}:{model}. Moving to next provider.")

    raise RuntimeError(f"All providers failed. Last error: {last_exception}")