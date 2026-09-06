# config.py

# ============================================================
# Provider & Retry Configuration
# ============================================================

REQUEST_TIMEOUT = 60

MAX_LLM_RETRIES = 5

INITIAL_BACKOFF_DELAY = 2.0


# ============================================================
# Agent Routing
# ============================================================

LIGHT_AGENTS = {
    "ingestion",
    "cleaner",
    "narrator",
    "app",
}

HEAVY_AGENTS = {
    "analyst",
    "critic",
}


# ============================================================
# Provider Chains
# ============================================================


LIGHT_CHAIN = [
    ("groq", "openai/gpt-oss-20b"),
    ("cerebras", "gpt-oss-120b"),
    ("deepseek", "deepseek-v4-flash"),
    ("google", "gemini-2.5-flash"),
]

HEAVY_CHAIN = [
    ("groq", "openai/gpt-oss-120b"),
    ("cerebras", "gpt-oss-120b"),
    ("deepseek", "deepseek-v4-flash"),
    ("google", "gemini-2.5-flash"),
]


# ============================================================
# Analyst Configuration
# ============================================================

MAX_ANALYST_QUESTIONS = 3

MAX_ANALYST_RETRIES = 2

MAX_LLM_CALLS_PER_RUN = 25