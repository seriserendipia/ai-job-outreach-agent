"""ChatOpenAI factory. One place to construct LLM clients."""
from langchain_openai import ChatOpenAI

from app import config


def make_llm(model: str | None = None, temperature: float = 0.3) -> ChatOpenAI:
    """Build a ChatOpenAI client.

    temperature defaults low-ish: these are extraction/drafting tasks, not
    creative writing, and lower temperature makes the reflection loop converge.
    """
    return ChatOpenAI(
        model=model or config.MODEL_FAST,
        temperature=temperature,
        api_key=config.OPENAI_API_KEY,
    )
