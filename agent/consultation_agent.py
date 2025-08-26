# agent/consultation_agent.py

from agent.prompts import IDENTIFICATION_PROMPT, NEEDS_RAG_PROMPT, RAG_PROMPT, CONSULTATION_PROMPT, SUMMARIZE_CONVERSATION_PROMPT
from agent.state import ConsultationState
from agent.tools import rag_search
from config import OPENAI_API_KEY
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
import logs.logging_config
import logging


logger = logging.getLogger(__name__)


class ConsultationAgent:
    """
    Handles user consultations about medical services.
    """

    def __init__(self):
        """
        Initialization of the agent.
        """
        # Create LLM
        self.llm = ChatOpenAI(model="gpt-4.1", temperature=0.2, api_key=OPENAI_API_KEY)

        # Set up the state storage
        self.checkpointer = MemorySaver()

        # Tools
        self.tools = [rag_search]

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Create and compile a dialog graph (StateGraph) using LangGraph.
        """
        workflow = StateGraph(ConsultationState)

        workflow.add_node("get_user_info", self._get_user_info)
        workflow.add_node("needs_rag", self._needs_rag_node)
        workflow.add_node("llm_response", self._llm_response_node)        
        workflow.add_node("tool", ToolNode(self.tools))
        workflow.add_node("check_reset", self._check_reset_node)
        workflow.add_node("reset_state", self._reset_state_with_summary)

        # Начинаем с узла уточнения
        workflow.set_entry_point("get_user_info")

        # Добавляем условные переходы после уточнения
        workflow.add_conditional_edges(
            "get_user_info",
            self._route_after_aftorization,
            {
                "has_client_name": "needs_rag",
                "need_client_name": END,
                "get_client_name": END
            }
        )

        workflow.add_edge("needs_rag", "llm_response")

        workflow.add_conditional_edges(
            "llm_response",
            self._route_after_agent,
            {
                "use_tool": "tool",              
                "no_tool": "check_reset"
            }
        )

        workflow.add_edge("tool", "llm_response")

        # After check_reset, either reset or end
        workflow.add_conditional_edges(
            "check_reset",
            self._should_reset_conversation,
            {
                "reset_state": "reset_state",
                "finish": END
            }
        )
        workflow.add_edge("reset_state", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _get_user_info(self, state: ConsultationState) -> ConsultationState:

        try:
            messages = state.get("messages", [])
            if not messages or not isinstance(messages[-1], HumanMessage):
                return state
        
            # Если у нас уже есть ФИО и программа, пропускаем этот узел
            if state.get("client_name") != None and state.get("gender") != None:
                return state
            
            # Если последнее сообщение от пользователя
            if isinstance(messages[-1], HumanMessage):

                user_query = messages[-1].content

                chat_history = [
                    msg for msg in messages
                    if isinstance(msg, (AIMessage, HumanMessage)) and not msg.additional_kwargs.get("tool_calls")
                ]

                identification_prompt = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(IDENTIFICATION_PROMPT),
                    MessagesPlaceholder("chat_history"),
                    HumanMessagePromptTemplate.from_template(
                        "Ответ пользователя: '{user_query}'\n\n"
                    )
                ])
                
                # Use the usual model (without tools)
                model = self.llm
                chain = identification_prompt | model
                
                # Invoke model to generate final response
                response = chain.invoke({
                    "chat_history": chat_history,
                    "user_query": user_query or "последний запрос",
                })

                # Пытаемся извлечь JSON
                import json
                import re
                
                json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if json_match:
                    try:
                        response_json = json.loads(json_match.group())
                        if "response" in response_json:
                            state["client_name"] = response_json.get("client_name", None)
                            state["gender"] = response_json.get("gender", None)
                            state["messages"].append(AIMessage(content=response_json["response"]))
                                
                    except json.JSONDecodeError:
                        logger.warning(f"Ошибка JSONDecode. Ответ модели: {response.content}")
                        pass
                return state
            
        except Exception as e:
            logger.error(f"[CONSULTATION_AGENT] Ошибка при уточнении запроса: {e}")
            state["messages"].append(AIMessage(content="Извините, возникла ошибка. Попробуйте позже."))

        return state


    def _route_after_aftorization(self, state: ConsultationState) -> str:
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if (
                isinstance(last_message, AIMessage) and 
                "расскажите, какая процедура вас интересует?" in last_message.content
            ):

                return "get_client_name"

        if state.get("client_name") and state.get("gender"):
            return "has_client_name"
        else:
            return "need_client_name"
        
    def _needs_rag_node(self, state: ConsultationState) -> ConsultationState:
        """
        Classifies user's message as requiring rag or not requiring rag
        """
        try:
            # Get the messages
            messages = state.get("messages", [])
            if not messages or not isinstance(messages[-1], HumanMessage):
                return state
                
            # Get the last user message
            last_message = messages[-1]
            user_query = last_message.content
            
            # Create needs_rag_prompt
            needs_rag_prompt = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(NEEDS_RAG_PROMPT),
                HumanMessagePromptTemplate.from_template("{query}")
            ])
            
            # Get classification
            chain = needs_rag_prompt | self.llm
            response = chain.invoke({"query": user_query})
            
            if "YES" in response.content:
                state["need_rag"] = True
            else:
                state["need_rag"] = False
            
        except Exception as e:
            logger.error(f"[CONSULTATION_AGENT] Error in routing: {e}")
            state["needs_rag"] = True
  

    # ---------- AGENT NODE ----------
    def _llm_response_node(self, state: ConsultationState) -> ConsultationState:
        """
        Process messages in the consultation state using the LLMin two phases: 
        1. For user messages: Force RAG tool usage to retrieve information
        2. For tool responses: Generate final answer using retrieved data

        Args:
            state (ConsultationState): The current сonsultation state.

        Returns:
            ConsultationState: The updated state after processing the LLM response.
        """
        try:    
            # If there are no messages or the last message is not from the user, just return the current state
            messages = state.get("messages", [])
            if not messages or not isinstance(messages[-1], (HumanMessage, ToolMessage)):
                return state

            need_rag = state.get("need_rag", True)

            last_message = messages[-1]

            # Case 1: Processing user's message
            if isinstance(last_message, HumanMessage) and need_rag == True:


                # Get chat history
                chat_history = [
                    msg for msg in messages
                    if isinstance(msg, (AIMessage, HumanMessage)) and not msg.additional_kwargs.get("tool_calls")
                ]

                # Rag prompt with tools
                rag_prompt = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(RAG_PROMPT),
                    MessagesPlaceholder("chat_history"),
                    HumanMessagePromptTemplate.from_template("Выполни поиск по запросу пользователя")  
                ])

                # Force the model to use the tool
                model_with_tools = self.llm.bind_tools(
                    self.tools,
                    tool_choice={"type": "function", "function": {"name": "rag_search"}}
                    )
                chain = rag_prompt | model_with_tools
                
                # Invoke model - return tool calls
                response = chain.invoke({
                    "chat_history": chat_history
                })
                state["messages"].append(response)

            # Case 2: Processing tool response
            if (isinstance(last_message, ToolMessage) and need_rag == True) or (isinstance(last_message, HumanMessage) and need_rag == False):
                # Get chat history (excluding tool messages and tool calls)
                chat_history = [
                    msg for msg in messages
                    if isinstance(msg, (AIMessage, HumanMessage)) and not (
                        isinstance(msg, AIMessage) and msg.additional_kwargs.get("tool_calls")
                    )
                ]

                gender = state.get("gender", None)
                client_name = state.get("client_name", None)
                # Get the user's last query
                user_query = None
                for msg in reversed(chat_history):
                    if isinstance(msg, HumanMessage):
                        user_query = msg.content
                        break
                        
                # Get tool search result
                if isinstance(last_message, ToolMessage):
                    retrieved_info = last_message.content
                else:
                    retrieved_info = "Для данного запроса не требовался поиск в базе знаний."
                
                # Prompt for a final response
                consultation_prompt = ChatPromptTemplate.from_messages([
                    SystemMessagePromptTemplate.from_template(CONSULTATION_PROMPT),
                    MessagesPlaceholder("chat_history"),
                    HumanMessagePromptTemplate.from_template(
                        "Запрос пользователя: '{user_query}'\n\n" +
                        "Релевантная информация:\n{retrieved_texts}\n\n" +
                        "Сформулируй финальный ответ пользователю на основе этой информации."
                    )
                ])
                
                # Use the usual model (without tools)
                model = self.llm
                chain = consultation_prompt | model
                
                # Invoke model to generate final response
                response = chain.invoke({
                    "chat_history": chat_history,
                    "retrieved_texts": retrieved_info,
                    "user_query": user_query or "последний запрос",
                    "gender": gender or "неизвестен",
                    "client_name": client_name or "клиент"
                })
                state["messages"].append(response)

        except Exception as e:
            logger.error(f"[CONSULTATION_AGENT] Ошибка при запросе к LLM: {e}")
            state["messages"].append(AIMessage(content="Извините, возникла ошибка. Попробуйте позже."))

        return state

    def _route_after_agent(self, state: ConsultationState) -> str:
        """
        Determine whether to use tools based on the last message from LLM.

        Args:
            state: The current state of the dialog

        Returns:
            str: "use_tools" or "no_tools"
        """
        messages = state.get("messages", [])

        if not messages:
            return "no_tool"

        last_message = messages[-1]
        if hasattr(last_message, 'additional_kwargs') and last_message.additional_kwargs.get('tool_calls'):
            return "use_tool"
        else:
            return "no_tool"
        
    def _should_reset_conversation(self, state: ConsultationState) -> bool:
        """Determine if we should reset the conversation state"""
        messages = state.get("messages", [])
        final_ai_messages = [
            msg for msg in messages 
            if isinstance(msg, AIMessage) and not msg.additional_kwargs.get("tool_calls")
            ]
        return "reset_state" if len(final_ai_messages) >= 10 else "finish"
    
    # ---------- CHECK RESET NODE ----------
    def _check_reset_node(self, state: ConsultationState) -> ConsultationState:
        """Node that passes through state without modifying it"""
        return state

    def _summarize_conversation(self, state: ConsultationState) -> HumanMessage:
        """Summarize the conversation and add the summary to the messages."""

        conversation_for_summary = []
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                conversation_for_summary.append(f"Пользователь: {msg.content}")
            elif isinstance(msg, AIMessage) and not msg.additional_kwargs.get("tool_calls"):
                conversation_for_summary.append(f"Ассистент: {msg.content}")
        
        prompt = [
            SystemMessage(content=SUMMARIZE_CONVERSATION_PROMPT),
            HumanMessage(content=f"Вот диалог для обобщения:\n\n{chr(10).join(conversation_for_summary)}")
        ]

        try:
            summary_response = self.llm.invoke(prompt)

            return HumanMessage(content=summary_response.content)

        except Exception as e:
            logger.error(f"[CONSULTATION_AGENT] Ошибка при суммаризации: {e}")
            return HumanMessage(content="Извините, произошла ошибка при суммаризации.")

    def _reset_state_with_summary(self, state: ConsultationState) -> ConsultationState:
        # Save the session_id for updating the checkpointer
        session_id = state.get("session_id")

        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                # Skip messages with tool calls
                has_tool_calls = (hasattr(msg, 'additional_kwargs') and 
                                'tool_calls' in msg.additional_kwargs and 
                                msg.additional_kwargs['tool_calls'])
                if not has_tool_calls:
                    final_ai_message = msg
                    break        

        # Create a summary of the dialog before resetting
        conversation_summary = self._summarize_conversation(state)

        client_name = state.get("client_name", None)
        gender = state.get("gender", None)

        # Create a completely new state object
        new_state = {
            "session_id": session_id,
            "need_rag": True,
            "client_name": client_name,
            "gender": gender,
            "messages": [conversation_summary, final_ai_message]
        }
        return new_state

        
    # ---------- RUN ----------
    def run(self, session_id: str, state: ConsultationState = None) -> ConsultationState:
        """
        Run the consultation agent graph.

        Args:
            session_id (str): Session ID for tracking conversation. 
            state (ConsultationState): The current state of the dialog

        Returns:
            ConsultationState: The updated state after processing the user_query.
        """
        if not state:
            try:
                checkpoint_data = self.checkpointer.get(
                    {"configurable": {"thread_id": session_id}}
                )
                if checkpoint_data and isinstance(checkpoint_data, dict) and 'channel_values' in checkpoint_data:
                    state = checkpoint_data['channel_values']
                else:
                    state = None
            except Exception as e:
                logger.error(f"[CONSULTATION_AGENT][RUN] Error loading state: {e}")
                state = None

            if state is None:
                state = {
                    "session_id": session_id,
                    "need_rag": True,
                    "client_name": None,
                    "gender": None,
                    "messages": []
                }         

        try:
            updated_state = self.graph.invoke(
                state,
                {"configurable": {"thread_id": session_id, "recursion_limit": 10}}
            )
            print("---------Updated_state---------")
            print(updated_state)
            return updated_state
        except Exception as e:
            logger.error(f"[CONSULTATION_AGENT][RUN] Error in run method: {str(e)}")
            state["messages"].append(AIMessage(content="Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз."))
            return state