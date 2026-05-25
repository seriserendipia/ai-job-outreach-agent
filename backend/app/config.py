"""Central configuration, loaded from environment / .env."""
import os

from dotenv import load_dotenv

load_dotenv()

# ---- LLM ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_FAST = os.getenv("MODEL_FAST", "gpt-4o-mini")      # default for most nodes
MODEL_CRITIC = os.getenv("MODEL_CRITIC", "gpt-4o-mini")  # critic; can be set stronger

# ---- Web search (Recruiter Finder tool) ----
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ---- Loop guards ----
# Max reason-act-observe iterations inside the Recruiter Finder ReAct loop.
MAX_SEARCHES = int(os.getenv("MAX_SEARCHES", "4"))
# Max critic-driven revisions in the Writer<->Critic reflection loop.
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))

# ---- Email constraints (shared by Writer and Critic) ----
EMAIL_MIN_WORDS = 110
EMAIL_MAX_WORDS = 220

# ---- Server ----
PORT = int(os.getenv("PORT", "8000"))
