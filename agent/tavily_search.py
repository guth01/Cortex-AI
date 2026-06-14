"""
Tavily Search — web search provider for the study agent fallback pipeline.

Uses the official Tavily Python SDK with the TAVILY_KEY environment variable.
Designed with a clean interface so alternative search providers (Serper, Brave,
Exa, etc.) can be plugged in later by implementing the same return shape.

Return shape (list of dicts):
    [
        {
            "title":   str,   # Page / article title
            "url":     str,   # Source URL
            "content": str,   # Extracted text snippet
        },
        ...
    ]
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Provider interface — swap provider by replacing this function
# ---------------------------------------------------------------------------

async def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Perform a web search via Tavily and return structured results.

    Args:
        query:       Natural language search query.
        max_results: Maximum number of results to return (1–10).

    Returns:
        List of {"title": str, "url": str, "content": str} dicts.
        Returns an empty list on failure (never raises — errors are logged).
    """
    api_key = os.getenv("TAVILY_KEY", "").strip()

    if not api_key:
        raise ValueError("TAVILY_KEY not set in environment. Web search is unavailable.")

    print(f"[TAVILY] query='{query[:120]}', max_results={max_results}")

    try:
        from tavily import TavilyClient  # type: ignore

        client = TavilyClient(api_key=api_key)

        # Run the blocking SDK call in the default executor to keep async clean
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",        # "basic" is faster; use "advanced" for deeper content
                include_answer=False,        # We synthesise the answer ourselves via Gemini
                include_raw_content=False,   # Snippets are sufficient; full pages are too large
            ),
        )

        raw_results = response.get("results", [])

        results = []
        for item in raw_results:
            results.append({
                "title":   item.get("title", "Untitled"),
                "url":     item.get("url", ""),
                "content": item.get("content", ""),
            })

        print(f"[TAVILY] returned {len(results)} results")
        return results

    except ImportError:
        raise ImportError("tavily-python package not installed. Run: pip install tavily-python")

    except Exception as exc:
        raise RuntimeError(f"Tavily search failed: {exc}")


# ---------------------------------------------------------------------------
# Utility — format results for injection into a prompt
# ---------------------------------------------------------------------------

def format_web_results_for_prompt(results: list[dict]) -> str:
    """
    Convert a list of Tavily result dicts into a clean prompt-ready string.

    Each result is formatted as:

        [1] Title
        URL: https://...
        Content:
        <snippet text>

    Returns an empty string if results is empty.
    """
    if not results:
        return "No web results available."

    parts = []
    for i, r in enumerate(results, start=1):
        part = (
            f"[{i}] {r.get('title', 'Untitled')}\n"
            f"URL: {r.get('url', '')}\n"
            f"Content:\n{r.get('content', '').strip()}"
        )
        parts.append(part)

    return "\n\n---\n\n".join(parts)
