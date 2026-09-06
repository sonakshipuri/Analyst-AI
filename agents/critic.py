# agents/critic.py
import json
import logging
from models import CriticResponse
from pydantic import ValidationError
from utils.llm_utils import get_llm
from orchestrator.utils import safe_llm_call

logger = logging.getLogger("datalyze.critic")
llm = get_llm("critic")


def _summarize_chart(chart_json: str) -> str:
    if not chart_json:
        return "No chart generated."
    try:
        fig = json.loads(chart_json)
        layout = fig.get("layout", {})
        data = fig.get("data", [{}])
        return (
            f"Chart type: {data[0].get('type', 'unknown')}, "
            f"Title: {layout.get('title', {}).get('text', 'none')}, "
            f"X: {layout.get('xaxis', {}).get('title', {}).get('text', 'none')}, "
            f"Y: {layout.get('yaxis', {}).get('title', {}).get('text', 'none')}"
        )
    except Exception:
        return "Chart JSON present but could not be parsed."


def _prepare_code_for_critic(code: str, max_chars: int = 8000) -> str:
    """Keep beginning and end of code for critic evaluation."""
    if len(code) <= max_chars:
        return code
    split_point = int(max_chars * 0.6)
    omitted = len(code) - max_chars
    return (
        code[:split_point] +
        f"\n\n# ... [SKIPPED {omitted} characters] ...\n\n" +
        code[-(max_chars - split_point):]
    )


def validate_insight(
    question: str,
    answer: str,
    code: str,
    chart_json: str,
    execution_metadata: dict,
) -> dict:
    chart_summary = _summarize_chart(chart_json)
    code_prepared = _prepare_code_for_critic(code)

    prompt = f"""
You are an expert data science critic. Analyze the following question, code, output, and chart summary to evaluate the quality and correctness of the insight generated.Keep your reasoning in 400 characters

Question asked:
{question}

Answer provided:
{answer}
Code executed:
{code_prepared}

Chart description:
{chart_summary}

Your job is to evaluate if this is a high-quality insight that directly and correctly answers the question.
You must return one of the following verdicts:
1. "verdict": "accept" - The insight is correct, deep, and fully answers the question.
2. "verdict": "weak_accept" - The insight is valid but slightly trivial or has low business value.
3. "verdict": "regenerate" - The code executed, but the logic is wrong, incomplete, or the chart does not match/support the answer. Give specific feedback on what is wrong.
4. "verdict": "skip" - The question cannot be answered cleanly or correctly with the available data/schema.

Return ONLY a valid JSON object.
Do NOT use markdown.
Do NOT use code fences.

Example JSON response format:
{{
    "verdict": "regenerate",
    "reason": "The code filters the dataset but does not calculate the actual mean, resulting in a misleading general summary answer."
}}
"""
    try:
        response = safe_llm_call(llm, prompt, execution_metadata)
        cleaned = response.content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Try to parse JSON
        raw = json.loads(cleaned)
        # Validate with Pydantic
        validated = CriticResponse(**raw)
        return {"verdict": validated.verdict, "reason": validated.reason}

    except json.JSONDecodeError as e:
        logger.warning(f"Critic returned malformed JSON: {e}")
        return {
            "verdict": "weak_accept",
            "reason": "Critic response could not be parsed as JSON. Defaulting to weak_accept."
        }
    except ValidationError as e:
        logger.warning(f"Critic response failed validation: {e}")
        return {
            "verdict": "weak_accept",
            "reason": "Critic response validation failed. Defaulting to weak_accept."
        }
    except Exception as e:
        if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
            raise
        logger.error(f"Unexpected critic error: {e}")
        return {
            "verdict": "weak_accept",
            "reason": f"Critic unavailable, insight unvalidated: {str(e)}"
        }