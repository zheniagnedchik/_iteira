# agent/vector_db.py

import os
import sys
import pandas as pd
from typing import List
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)
from config import DATA_PATH, CHROMA_PATH, OPENAI_API_KEY
from langchain.docstore.document import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import shutil
from uuid import uuid4
import tiktoken

class VectorDB:
    def __init__(self, persist_directory=CHROMA_PATH):
        self.persist_directory = persist_directory
        self.embedding_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        self.vector_store = None
        # Инициализируем токенизатор
        self.tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

    def count_tokens(self, text: str) -> int:
        """Подсчет токенов в тексте"""
        return len(self.tokenizer.encode(text))

    def batch_documents(self, docs: List[Document], max_tokens: int = 250000) -> List[List[Document]]:
        """Разбивает документы на батчи с учетом ограничения токенов"""
        batches = []
        current_batch = []
        current_tokens = 0

        for doc in docs:
            doc_tokens = self.count_tokens(doc.page_content)
            
            if current_tokens + doc_tokens > max_tokens:
                batches.append(current_batch)
                current_batch = [doc]
                current_tokens = doc_tokens
            else:
                current_batch.append(doc)
                current_tokens += doc_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def load_documents(self, folder_path):
        """Load documents from a directory, supporting txt, md, docx, and json."""
        try:
            docs = []
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if filename.endswith(".xlsx"):
                    df = pd.read_excel(file_path)
                    for _, row in df.iterrows():
                        content_parts = [
                            f"{col}: {v}"
                            for col, v in row.items() 
                        ]
                        text = "\n".join(content_parts)
                        doc = Document(
                            page_content=text,
                            metadata={"source": file_path}
                        )
                        docs.append(doc)
                else:
                    print(f"[LOAD_DOCUMENTS] Unsupported file type: {filename}")
                    continue

            return docs

        except Exception as e:
            print(f"[LOAD_DOCUMENTS] error: {e}")
            raise e

    def create_vector_store(self):
        """Recreate the vector database."""
        try:
            # Remove the existing ChromaDB
            if os.path.exists(CHROMA_PATH):
                shutil.rmtree(CHROMA_PATH)
                print("[CREATE_VECTOR_STORE] The existing ChromaDB is removed.")

            docs = self.load_documents(DATA_PATH)
            
            # Создаем базу для первого батча
            batches = self.batch_documents(docs)
            print(f"[CREATE_VECTOR_STORE] Total batches: {len(batches)}")

            for i, batch in enumerate(batches):
                uuids = [str(uuid4()) for _ in range(len(batch))]
                
                if i == 0:
                    # Создаем новую базу с первым батчем
                    self.vector_store = Chroma.from_documents(
                        documents=batch,
                        embedding=self.embedding_model,
                        ids=uuids,
                        collection_name="iteira_vector_db",
                        persist_directory=self.persist_directory
                    )
                else:
                    # Добавляем остальные батчи в существующую базу
                    self.vector_store.add_documents(
                        documents=batch,
                        ids=uuids
                    )
                
                print(f"[CREATE_VECTOR_STORE] Processed batch {i+1}/{len(batches)}")

            print("[CREATE_VECTOR_STORE] Vector database successfully created.")
            
        except Exception as e:
            print(f"[CREATE_VECTOR_STORE] error: {e}")


if __name__ == "__main__":
    vector_db = VectorDB()
    vector_db.create_vector_store()