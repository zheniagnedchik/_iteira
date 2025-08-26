from config import CHROMA_PATH, OPENAI_API_KEY
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field
import logs.logging_config
import logging


# Initialize the logger
logger = logging.getLogger(__name__)

# ---------- TOOLS ---------- #
# Vector storage initialization
vector_store = Chroma(
    persist_directory=CHROMA_PATH,
    embedding_function=OpenAIEmbeddings(api_key=OPENAI_API_KEY),
    collection_name="iteira_vector_db"
)

class RAGSearchInput(BaseModel):
    user_query: str = Field(..., title="User Query", description="User query for rag search")

@tool(args_schema=RAGSearchInput)
def rag_search(user_query: str) -> str:
    """
    Search for relevant information based on a user's query in a vector store.

    Args:
        user_query (str): content of user query

    Returns: str: A string containing the contents of the three most relevant
    documents or a message about missing data.
    """
    try:
        logger.info(f"[CONSULTATION_AGENT][RAG_SEARCH] Starting RAG search for user query: '{user_query}'")
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        subqueries = [q.strip() for q in user_query.split(";") if q.strip()]
        results = []

        for subquery in subqueries:
            relevant_docs = vector_retriever.invoke(subquery)
            retrieved_texts = "\n\n".join(
                [f"[Source: {doc.metadata.get('source', 'N/A')}]\n{doc.page_content}"
                for doc in relevant_docs]
            )
            results.append(retrieved_texts or f"Нет информации по запросу: {subquery}")
        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"[CONSULTATION_AGENT][RAG_SEARCH] ❌ Error during RAG search: {e}")
        return "Произошла ошибка при поиске документов."
