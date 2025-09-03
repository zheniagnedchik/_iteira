# agent/vector_db.py

import os
import sys
import stat

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
                            metadata={"source": file_path, "filename": filename}
                        )
                        docs.append(doc)
                else:
                    print(f"[LOAD_DOCUMENTS] Unsupported file type: {filename}")
                    continue

            return docs

        except Exception as e:
            print(f"[LOAD_DOCUMENTS] error: {e}")
            raise e

    def load_single_file(self, file_path):
        """Load documents from a single file."""
        try:
            docs = []
            filename = os.path.basename(file_path)
            
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
                        metadata={"source": file_path, "filename": filename}
                    )
                    docs.append(doc)
            else:
                print(f"[LOAD_SINGLE_FILE] Unsupported file type: {filename}")
                return []

            return docs

        except Exception as e:
            print(f"[LOAD_SINGLE_FILE] error: {e}")
            raise e

    def create_vector_store(self, data_path=None):
        """Recreate the vector database."""
        # Устанавливаем umask для создания файлов с полными правами
        old_umask = os.umask(0o000)
        
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
                        
                        # Обеспечиваем права доступа перед созданием базы
                        os.makedirs(self.persist_directory, exist_ok=True)
                        os.chmod(self.persist_directory, 0o777)
                        
                        # Устанавливаем umask для создания файлов с правильными правами
                        old_umask = os.umask(0o000)
                        
                        try:
                            # Создаем файловую базу данных стандартным способом
                            self.vector_store = Chroma.from_documents(
                                documents=batch,
                                embedding=self.embedding_model,
                                ids=uuids,
                                collection_name=collection_name,
                                persist_directory=self.persist_directory
                            )
                            print(f"[CREATE_VECTOR_STORE] Создана файловая база данных в {self.persist_directory}")
                        finally:
                            # Восстанавливаем старый umask
                            os.umask(old_umask)
                        
                        # Исправляем права доступа к созданным файлам базы данных
                        self._fix_database_permissions()
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

    def _prepare_sqlite_database(self):
        """Предварительно подготавливает SQLite базу данных с правильными правами"""
        import sqlite3
        try:
            # Создаем основную SQLite базу данных ChromaDB
            chroma_db_path = os.path.join(self.persist_directory, "chroma.sqlite3")
            
            # Создаем пустую базу данных
            conn = sqlite3.connect(chroma_db_path)
            conn.close()
            
            # Устанавливаем права доступа
            os.chmod(chroma_db_path, 0o666)
            print(f"[PREPARE_SQLITE] Создана SQLite база данных: {chroma_db_path}")
            
        except Exception as e:
            print(f"[PREPARE_SQLITE] Ошибка при подготовке SQLite: {e}")

    def _fix_database_permissions(self):
        """Исправляет права доступа к файлам базы данных ChromaDB"""
        import stat
        try:
            for root, dirs, files in os.walk(self.persist_directory):
                # Исправляем права для всех директорий
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        os.chmod(dir_path, 0o777)
                    except Exception as e:
                        print(f"[DATABASE_PERMISSIONS] Не удалось изменить права директории {dir_path}: {e}")
                
                # Исправляем права для всех файлов, особенно SQLite базы
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        os.chmod(file_path, 0o666)  # Читать/писать для всех
                        print(f"[DATABASE_PERMISSIONS] Установлены права для {file_path}")
                    except Exception as e:
                        print(f"[DATABASE_PERMISSIONS] Не удалось изменить права файла {file_path}: {e}")
                        
        except Exception as e:
            print(f"[DATABASE_PERMISSIONS] Общая ошибка при исправлении прав: {e}")

    def get_or_create_vector_store(self):
        """Получить существующую или создать новую базу знаний"""
        try:
            if os.path.exists(self.persist_directory) and os.listdir(self.persist_directory):
                # База данных существует, загружаем её
                print(f"[VECTOR_STORE] Загружаем существующую базу из {self.persist_directory}")
                self.vector_store = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embedding_model
                )
                return self.vector_store
            else:
                # База данных не существует, создаем пустую
                print(f"[VECTOR_STORE] Создаем новую базу в {self.persist_directory}")
                os.makedirs(self.persist_directory, exist_ok=True)
                os.chmod(self.persist_directory, 0o777)
                
                # Создаем пустую базу данных
                self.vector_store = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embedding_model
                )
                return self.vector_store
        except Exception as e:
            print(f"[VECTOR_STORE] Ошибка при инициализации: {e}")
            raise e

    def add_file_to_knowledge_base(self, file_path):
        """Добавить один файл в базу знаний"""
        try:
            print(f"[ADD_FILE] Добавляем файл: {file_path}")
            
            # Получаем или создаем базу знаний
            if not self.vector_store:
                self.get_or_create_vector_store()
            
            # Загружаем документы из файла
            docs = self.load_single_file(file_path)
            if not docs:
                print(f"[ADD_FILE] Нет документов в файле {file_path}")
                return {"status": "success", "message": "Файл пуст", "added_docs": 0}
            
            # Добавляем документы в базу знаний
            uuids = [str(uuid4()) for _ in range(len(docs))]
            self.vector_store.add_documents(documents=docs, ids=uuids)
            
            print(f"[ADD_FILE] Добавлено {len(docs)} документов из файла {os.path.basename(file_path)}")
            return {"status": "success", "message": f"Добавлено {len(docs)} документов", "added_docs": len(docs)}
            
        except Exception as e:
            print(f"[ADD_FILE] Ошибка при добавлении файла {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def remove_file_from_knowledge_base(self, filename):
        """Удалить файл из базы знаний"""
        try:
            print(f"[REMOVE_FILE] Удаляем файл: {filename}")
            
            # Получаем или создаем базу знаний
            if not self.vector_store:
                self.get_or_create_vector_store()
            
            # Получаем все документы
            try:
                # Ищем документы по метаданным
                results = self.vector_store.get(where={"filename": filename})
                if results and results['ids']:
                    # Удаляем найденные документы
                    self.vector_store.delete(ids=results['ids'])
                    print(f"[REMOVE_FILE] Удалено {len(results['ids'])} документов файла {filename}")
                    return {"status": "success", "message": f"Удалено {len(results['ids'])} документов", "removed_docs": len(results['ids'])}
                else:
                    print(f"[REMOVE_FILE] Документы файла {filename} не найдены в базе знаний")
                    return {"status": "success", "message": "Документы не найдены", "removed_docs": 0}
            except Exception as e:
                print(f"[REMOVE_FILE] Не удалось найти документы для удаления: {e}")
                return {"status": "warning", "message": f"Не удалось найти документы: {str(e)}"}
            
        except Exception as e:
            print(f"[REMOVE_FILE] Ошибка при удалении файла {filename}: {e}")
            return {"status": "error", "message": str(e)}

    def update_knowledge_base_incrementally(self, files_path):
        """Инкрементально обновить базу знаний"""
        try:
            print(f"[INCREMENTAL_UPDATE] Обновляем базу знаний из {files_path}")
            
            # Получаем или создаем базу знаний
            if not self.vector_store:
                self.get_or_create_vector_store()
            
            # Получаем список файлов в папке
            current_files = set()
            if os.path.exists(files_path):
                current_files = {f for f in os.listdir(files_path) 
                               if f.endswith(('.xlsx', '.xls')) and os.path.isfile(os.path.join(files_path, f))}
            
            # Получаем список файлов в базе знаний
            try:
                existing_results = self.vector_store.get()
                existing_files = set()
                if existing_results and existing_results['metadatas']:
                    for metadata in existing_results['metadatas']:
                        if metadata and 'filename' in metadata:
                            existing_files.add(metadata['filename'])
            except:
                existing_files = set()
            
            # Файлы для добавления (есть в папке, но нет в базе)
            files_to_add = current_files - existing_files
            
            # Файлы для удаления (есть в базе, но нет в папке)
            files_to_remove = existing_files - current_files
            
            added_count = 0
            removed_count = 0
            
            # Добавляем новые файлы
            for filename in files_to_add:
                file_path = os.path.join(files_path, filename)
                result = self.add_file_to_knowledge_base(file_path)
                if result['status'] == 'success':
                    added_count += result.get('added_docs', 0)
            
            # Удаляем отсутствующие файлы
            for filename in files_to_remove:
                result = self.remove_file_from_knowledge_base(filename)
                if result['status'] == 'success':
                    removed_count += result.get('removed_docs', 0)
            
            print(f"[INCREMENTAL_UPDATE] Обновление завершено: добавлено {added_count}, удалено {removed_count}")
            
            return {
                "status": "success",
                "message": f"База знаний обновлена: добавлено {added_count} документов, удалено {removed_count}",
                "added_docs": added_count,
                "removed_docs": removed_count,
                "files_added": list(files_to_add),
                "files_removed": list(files_to_remove)
            }
            
        except Exception as e:
            print(f"[INCREMENTAL_UPDATE] Ошибка при инкрементальном обновлении: {e}")
            return {"status": "error", "message": str(e)}

    def soft_regenerate_vector_store(self, data_path=None):
        """Мягкая перегенерация: очистка коллекции без удаления файлов базы данных"""
        try:
            import os
            from uuid import uuid4
            
            # Устанавливаем umask для правильных прав доступа
            old_umask = os.umask(0o000)
            
            print("[SOFT_REGENERATE] Начинаем мягкую перегенерацию базы знаний")
            
            # Получаем или создаем векторное хранилище
            vector_store = self.get_or_create_vector_store()
            
            # Очищаем коллекцию (удаляем все документы)
            try:
                collection = vector_store._collection
                # Получаем все ID документов и удаляем их
                all_docs = collection.get()
                if all_docs['ids']:
                    print(f"[SOFT_REGENERATE] Удаляем {len(all_docs['ids'])} существующих документов")
                    collection.delete(ids=all_docs['ids'])
                else:
                    print("[SOFT_REGENERATE] Коллекция уже пустая")
            except Exception as e:
                print(f"[SOFT_REGENERATE] Ошибка при очистке коллекции: {e}")
            
            # Загружаем документы заново
            folder_path = data_path if data_path else DATA_PATH
            docs = self.load_documents(folder_path)
            
            if not docs:
                print("[SOFT_REGENERATE] Нет документов для добавления")
                return
            
            # Добавляем документы батчами
            batches = self.batch_documents(docs)
            print(f"[SOFT_REGENERATE] Добавляем {len(docs)} документов в {len(batches)} батчах")
            
            total_added = 0
            for i, batch in enumerate(batches):
                try:
                    uuids = [str(uuid4()) for _ in range(len(batch))]
                    vector_store.add_documents(documents=batch, ids=uuids)
                    total_added += len(batch)
                    print(f"[SOFT_REGENERATE] Батч {i+1}/{len(batches)}: добавлено {len(batch)} документов")
                except Exception as e:
                    print(f"[SOFT_REGENERATE] Ошибка в батче {i+1}: {e}")
            
            print(f"[SOFT_REGENERATE] ✅ Мягкая перегенерация завершена. Добавлено {total_added} документов")
            
        except Exception as e:
            print(f"[SOFT_REGENERATE] ❌ Ошибка при мягкой перегенерации: {e}")
            raise
        finally:
            # Восстанавливаем старый umask
            try:
                os.umask(old_umask)
            except:
                pass


if __name__ == "__main__":
    # Используем путь к папке files
    files_path = os.path.join(BASE_DIR, "files")
    vector_db = VectorDB()
    vector_db.create_vector_store(files_path)
