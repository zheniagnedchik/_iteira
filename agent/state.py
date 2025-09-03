# agent/state.py

from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated

# ---------- STATE ---------- #
def add_messages_custom(left: list[BaseMessage] | None, right: list[BaseMessage] | None) -> list[BaseMessage]:
    """
    A custom function for adding messages that takes into account the need to reset messages.
    If the first message in the right is summary, then replace all messages with new ones.
    """
    if not left:
        return right or []
    if not right:
        return left
    
    # Check if the first message in the right is summary message
    if (isinstance(right[0], HumanMessage) and 
        right[0].content and 
        right[0].content.startswith("Предыдущий диалог:")):
        # If this is a summary, replace all messages with new ones
        return right
    
    # Standard processing from langgraph
    return add_messages(left, right)


# ---------- STATE ---------- #
class ConsultationState(TypedDict):
    """
    TypedDict describing the consultation state
    """
    session_id: str
    need_rag: bool
    client_name: str
    gender: str
    messages: Annotated[list[AnyMessage], add_messages_custom]  # Message history
    # Поля для классификации сообщений
    is_irrelevant: int  # 0 - релевантное, 1 - нерелевантное
    asks_human_support: int  # 0 - нет, 1 - просит поддержку человека
    classification_response: str  # Ответ от классификатора
# ---------- END STATE ---------- #