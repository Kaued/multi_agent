import os

from langchain.tools import tool
from langchain_tavily import TavilySearch


@tool
def search_web(query: str) -> str:
    """Run a live web search and return evidence with explicit source URLs.

    Args:
        query: The query string to search for.

    Returns:
        Search-result titles, content excerpts, and a separate list containing
        each complete source URL. Final answers must cite the URLs from that
        list in a trailing ``Sources`` section.
    """

    api_key = os.getenv("TAVILY_API_KEY")

    if api_key is None or not api_key.strip():
        return "The TAVILY_API_KEY environment variable is not set."

    search = TavilySearch(
        api_key=api_key,
        search_engine="google",
        search_depth="basic",
        max_results=3,
    )

    search_results = search.invoke(
        {
            "query": query,
        }
    )

    if not isinstance(search_results, dict):
        return f"No search results found for query: {query}"

    results = search_results.get("results", [])
    results = [
        result
        for result in results
        if isinstance(result, dict) and result.get("url")
    ]
    if not results:
        return f"No search results found for query: {query}"

    result_strings = [
        f"Title: {result.get('title') or result['url']}\n"
        f"URL: {result['url']}\n"
        f"Content: {result.get('content', '')}"
        for result in results
    ]
    source_strings = [
        f"- {result.get('title') or result['url']} — {result['url']}"
        for result in results
    ]

    return (
        "Search results:\n\n"
        + "\n\n".join(result_strings)
        + "\n\nSource URLs returned by the search tool:\n"
        + "\n".join(source_strings)
    )
