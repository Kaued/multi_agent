import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class RootState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
