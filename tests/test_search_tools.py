from unittest.mock import MagicMock

import pytest

from tools.search import search_web as search_module


def test_search_web_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = search_module.search_web.invoke({"query": "pytest"})

    assert result == "The TAVILY_API_KEY environment variable is not set."


def test_search_web_formats_results_and_source_urls(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    search = MagicMock()
    search.invoke.return_value = {
        "results": [
            {
                "title": "Pytest documentation",
                "url": "https://docs.pytest.org/",
                "content": "pytest makes it easy to write tests.",
            },
            {
                "title": "",
                "url": "https://example.com/fallback-title",
                "content": "Another result.",
            },
            {"title": "Result without URL", "content": "Ignored."},
            "invalid result",
        ]
    }
    tavily_search = MagicMock(return_value=search)
    monkeypatch.setattr(search_module, "TavilySearch", tavily_search)

    result = search_module.search_web.invoke({"query": "how to use pytest"})

    tavily_search.assert_called_once_with(
        api_key="tavily-key",
        search_engine="google",
        search_depth="basic",
        max_results=3,
    )
    search.invoke.assert_called_once_with({"query": "how to use pytest"})
    assert "Title: Pytest documentation" in result
    assert "URL: https://docs.pytest.org/" in result
    assert "Content: pytest makes it easy to write tests." in result
    assert "Title: https://example.com/fallback-title" in result
    assert "Result without URL" not in result
    assert result.endswith(
        "- Pytest documentation — https://docs.pytest.org/\n"
        "- https://example.com/fallback-title — "
        "https://example.com/fallback-title"
    )


@pytest.mark.parametrize(
    "search_results",
    [
        None,
        [],
        {"results": []},
        {"results": [{"title": "Missing URL"}]},
    ],
)
def test_search_web_reports_no_usable_results(monkeypatch, search_results):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    search = MagicMock()
    search.invoke.return_value = search_results
    monkeypatch.setattr(search_module, "TavilySearch", MagicMock(return_value=search))

    result = search_module.search_web.invoke({"query": "missing result"})

    assert result == "No search results found for query: missing result"
