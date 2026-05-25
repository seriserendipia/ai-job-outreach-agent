"""Web search tool for the Recruiter Finder ReAct loop, backed by Tavily."""
from langchain_core.tools import tool
from tavily import TavilyClient

from app import config


@tool
def web_search(query: str) -> str:
    """Search the web. Use this to find a recruiter's email, a company careers /
    contact page, or recruiter LinkedIn profiles for a given company and role.
    Returns the top results as text (title, url, snippet)."""
    client = TavilyClient(api_key=config.TAVILY_API_KEY)
    resp = client.search(query=query, max_results=5, search_depth="basic")
    results = resp.get("results", [])
    if not results:
        return "No results found."
    blocks = []
    for r in results:
        snippet = (r.get("content") or "")[:300]
        blocks.append(
            f"- {r.get('title', '(no title)')}\n"
            f"  url: {r.get('url', '')}\n"
            f"  {snippet}"
        )
    return "\n".join(blocks)
