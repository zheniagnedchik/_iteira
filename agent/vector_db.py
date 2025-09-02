# agent/vector_db.py

import os
import sys
import pandas as pd
import time
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
import argparse  # Добавляем импорт argparse


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
                if filename.endswith((".xlsx", ".xls")):
                    engine = 'openpyxl' if filename.endswith('.xlsx') else 'xlrd'
                    df = pd.read_excel(file_path, engine=engine)
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

    def create_vector_store(self, data_path=None):
        """Recreate the vector database."""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                print(f"[CREATE_VECTOR_STORE] Попытка {attempt + 1}/{max_retries}")
                
                # Принудительно очищаем старую базу
                self._force_cleanup_chroma()
                
                # Use provided data_path or default DATA_PATH
                folder_path = data_path if data_path else DATA_PATH
                docs = self.load_documents(folder_path)
                
                if not docs:
                    print("[CREATE_VECTOR_STORE] Нет документов для обработки")
                    return
                
                # Создаем базу для первого батча
                batches = self.batch_documents(docs)
                print(f"[CREATE_VECTOR_STORE] Total batches: {len(batches)}")

                for i, batch in enumerate(batches):
                    uuids = [str(uuid4()) for _ in range(len(batch))]
                    
                    if i == 0:
                        # Создаем новую базу с первым батчем
                        # Используем уникальное имя коллекции для избежания конфликтов
                        collection_name = f"iteira_vector_db_{int(time.time())}"
                        self.vector_store = Chroma.from_documents(
                            documents=batch,
                            embedding=self.embedding_model,
                            ids=uuids,
                            collection_name=collection_name,
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
                return  # Успешно завершено
                
            except Exception as e:
                print(f"[CREATE_VECTOR_STORE] Ошибка на попытке {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    print(f"[CREATE_VECTOR_STORE] Повторная попытка через {retry_delay} секунд...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                else:
                    print("[CREATE_VECTOR_STORE] Все попытки исчерпаны")
                    raise e

    def _force_cleanup_chroma(self):
        """Принудительная очистка ChromaDB"""
        import time
        import stat
        
        try:
            # Закрываем текущее соединение если есть
            if hasattr(self, 'vector_store') and self.vector_store:
                try:
                    # Попытка корректно закрыть соединение
                    if hasattr(self.vector_store, '_client'):
                        self.vector_store._client.reset()
                except:
                    pass
                self.vector_store = None
            
            # Принудительно собираем мусор для освобождения ресурсов
            import gc
            gc.collect()
            
            # Удаляем директорию с базой данных
            if os.path.exists(self.persist_directory):
                print(f"[CREATE_VECTOR_STORE] Очистка директории: {self.persist_directory}")
                
                # Небольшая задержка для освобождения файлов
                time.sleep(1)
                
                # Рекурсивно устанавливаем права на запись для всех файлов
                self._fix_permissions(self.persist_directory)
                
                # Попытка удалить с повторами
                for i in range(5):
                    try:
                        shutil.rmtree(self.persist_directory)
                        print("[CREATE_VECTOR_STORE] ChromaDB directory removed.")
                        break
                    except (PermissionError, OSError) as e:
                        if i < 4:
                            print(f"[CREATE_VECTOR_STORE] Файлы заблокированы, попытка {i+1}/5...")
                            time.sleep(2)
                            # Повторно исправляем права доступа
                            self._fix_permissions(self.persist_directory)
                        else:
                            print(f"[CREATE_VECTOR_STORE] Не удалось удалить директорию: {e}")
                            # Попробуем переименовать директорию
                            backup_dir = f"{self.persist_directory}_backup_{int(time.time())}"
                            try:
                                os.rename(self.persist_directory, backup_dir)
                                print(f"[CREATE_VECTOR_STORE] Директория переименована в {backup_dir}")
                            except Exception as rename_error:
                                print(f"[CREATE_VECTOR_STORE] Не удалось переименовать: {rename_error}")
                                # В крайнем случае создаем новую директорию с другим именем
                                self.persist_directory = f"{self.persist_directory}_{int(time.time())}"
                                print(f"[CREATE_VECTOR_STORE] Используем новую директорию: {self.persist_directory}")
                            break
                            
        except Exception as e:
            print(f"[CREATE_VECTOR_STORE] Ошибка при очистке: {e}")

    def _fix_permissions(self, directory):
        """Исправляет права доступа для всех файлов в директории"""
        try:
            if not os.path.exists(directory):
                return
                
            for root, dirs, files in os.walk(directory):
                # Исправляем права для директорий
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                    except:
                        pass
                
                # Исправляем права для файлов
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
                    except:
                        pass
                        
        except Exception as e:
            print(f"[CREATE_VECTOR_STORE] Ошибка при исправлении прав доступа: {e}")


if __name__ == "__main__":
    # Используем путь к папке files
    files_path = os.path.join(BASE_DIR, "files")
    vector_db = VectorDB()
    vector_db.create_vector_store(files_path)
