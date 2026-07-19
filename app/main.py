import os

import dotenv
from langchain.messages import HumanMessage

from graph.root.root_graph import root_graph

dotenv.load_dotenv()


def main():
    root_agent_graph = root_graph()
    thread_id = os.getenv("LANGGRAPH_THREAD_ID", "default-conversation")

    message = "O que eu tinha perguntado mesmo? Me lembra, por favor."
    messages = [HumanMessage(content=message)]

    result = root_agent_graph.invoke(
        {"messages": messages},
        {"configurable": {"thread_id": thread_id}},
    )

    for message in result["messages"]:
        message.pretty_print()


if __name__ == "__main__":
    main()
