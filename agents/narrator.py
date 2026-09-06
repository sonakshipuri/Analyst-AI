# agents/narrator.py

from utils.llm_utils import get_llm
from orchestrator.utils import safe_llm_call

# Centralized LLM initialization
llm = get_llm("narrator")

def run_narrator(description: str, insights: list[dict], execution_metadata: dict) -> dict:
    """
    Takes dataset description + list of insights + execution metadata.
    Returns: { "summary": str, "flagged_insights": list, "error_detail": dict | None }
    """
    flagged = [insight for insight in insights if insight.get("confidence") == "low"]
    
    insight_text = "\n".join([
        f"- {i.get('question', 'Unknown Question')}: {str(i.get('answer', ''))[:500]} "
        f"({i.get('confidence', 'unknown')} confidence)"
        for i in insights
    ])
    flag_text = f"NOTE: {len(flagged)} finding(s) have low confidence." if flagged else ""
    
    prompt = f"""You are a business intelligence writer.
Summarize the following data analysis into a professional executive summary paragraph of 4–6 sentences.
Dataset:
{description}
Key Findings:
{insight_text}
{flag_text}
Requirements:
- Write for a non-technical executive audience
- Mention the most important finding first
- If any findings had low confidence, acknowledge uncertainty
- Do not use bullet points
- Keep the summary concise and professional
"""
    error_detail = None
    try:
        response = safe_llm_call(llm, prompt, execution_metadata)
        summary = str(getattr(response, "content", response) or "").strip()
        if not summary:
            raise ValueError("Empty summary returned")
    except Exception as e:
        # Graceful fallback when budget is exceeded
        if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded", False):
            summary = (
                f"Analysis was truncated because the LLM budget was reached. "
                f"The dataset was successfully analysed and {len(insights)} insight(s) were generated. "
                f"{len(flagged)} finding(s) were flagged as low confidence. "
                f"Consider increasing MAX_LLM_CALLS_PER_RUN in config.py for a full analysis."
            )
        else:
            summary = f"Narrator unavailable: {str(e)}"
            error_detail = {"error_type": type(e).__name__, "error_message": str(e)}
    return {"summary": summary, "flagged_insights": flagged, "error_detail": error_detail}