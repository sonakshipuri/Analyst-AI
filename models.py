# models.py

from typing import Literal, Optional
from pydantic import BaseModel, Field


class CriticResponse(BaseModel):
    """Validated response from the Critic agent."""
    verdict: Literal["accept", "weak_accept", "regenerate", "skip"] = Field(
        ..., description="The critic's decision on the insight quality."
    )
    reason: str = Field(..., max_length=500, description="Explanation for the verdict.")


class QuestionResponse(BaseModel):
    """Validated response from the Analyst's question generator."""
    question: Optional[str] = Field(None, max_length=500, description="The generated question.")
    stop: bool = Field(False, description="Whether the agent decided to stop.")

    @classmethod
    def from_raw(cls, raw: str):
        """Parse raw LLM output (either a question or 'STOP')."""
        cleaned = raw.strip().replace('"', '').replace("'", "")
        if cleaned.upper() == "STOP":
            return cls(question=None, stop=True)
        return cls(question=cleaned, stop=False)


class NarratorResponse(BaseModel):
    """Validated response from the Narrator agent."""
    summary: str = Field(..., max_length=2000, description="Executive summary.")