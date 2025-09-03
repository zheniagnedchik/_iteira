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
# Vector storage initialization function
def get_vector_store():
    """Get vector store instance - creates new connection each time to ensure fresh data"""
    import chromadb
    import time
    
    # Создаем новый клиент каждый раз для обеспечения свежих данных
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    try:
        # Проверяем количество документов для логирования
        collection = client.get_collection("langchain")
        doc_count = collection.count()
        logger.info(f"[RAG] Подключение к ChromaDB: {doc_count} документов в коллекции langchain")
        
        # Создаем Chroma wrapper с новым клиентом
        vector_store = Chroma(
            client=client,
            collection_name="langchain",
            embedding_function=OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        )
        
        return vector_store
        
    except Exception as e:
        logger.error(f"[RAG] Ошибка при подключении к ChromaDB: {e}")
        # Fallback к старому способу
        return Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=OpenAIEmbeddings(api_key=OPENAI_API_KEY),
            collection_name="langchain"
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
        # Get fresh vector store instance to ensure latest data
        vector_store = get_vector_store()
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        subqueries = [q.strip() for q in user_query.split(";") if q.strip()]
        results = []

        for subquery in subqueries:
            relevant_docs = vector_retriever.invoke(subquery)
            retrieved_texts = "\n\n".join(
                [f"[Source: {doc.metadata.get('source', 'N/A')}]\n{doc.page_content or 'Пустой документ'}"
                for doc in relevant_docs if doc.page_content is not None]
            )
            results.append(retrieved_texts or f"Нет информации по запросу: {subquery}")
        return "\n\n".join(results)
    except Exception as e:
        logger.error(f"[CONSULTATION_AGENT][RAG_SEARCH] ❌ Error during RAG search: {e}")
        return "Произошла ошибка при поиске документов."
