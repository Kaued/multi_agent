from typing import Annotated

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from graph.prompts.search_prompt import system_prompt
from graph.search.search_graph import search_graph
from tools.root.delegation import invoke_specialist


@tool
def call_search_agent(
    messages: Annotated[list[AnyMessage], InjectedState("messages")],
    config: RunnableConfig = None,
) -> str:
    """Use live web research only as the root agent's final fallback.

    Do not call this agent before the appropriate non-search agent. You MUST call
    it when that agent returns an empty, irrelevant, incomplete, unsupported,
    erroneous, out-of-scope, unknown, or not-found result and the answer can be
    researched publicly. It searches live sources, answers only from supported
    findings, and includes the titles and URLs of the sources it used. Whenever
    this tool is called, the root agent's final response must end with the
    returned `Sources` section and nothing may appear after it.

    Returns:
        The search agent's final, source-supported response.
    """
    graph = search_graph()
    result = invoke_specialist(messages, graph, system_prompt, "search", config)

    return str(result["messages"][-1].content)
