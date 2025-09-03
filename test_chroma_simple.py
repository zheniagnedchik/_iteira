#!/usr/bin/env python3
"""
Простой тест ChromaDB для диагностики проблемы
"""
import os
import tempfile
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from config import OPENAI_API_KEY

def test_chroma_creation():
    print("=== Тест создания ChromaDB ===")
    
    # Создаем временную папку
    test_dir = "/tmp/test_chroma_db"
    os.makedirs(test_dir, exist_ok=True)
    os.chmod(test_dir, 0o777)
    print(f"Тестовая папка: {test_dir}")
    
    # Создаем тестовые документы
    docs = [
        Document(page_content="Тест документ 1", metadata={"source": "test1"}),
        Document(page_content="Тест документ 2", metadata={"source": "test2"})
    ]
    
    # Инициализируем embedding
    embedding_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
    
    try:
        print("Создаем ChromaDB...")
        
        # Устанавливаем umask
        old_umask = os.umask(0o000)
        
        try:
            vector_store = Chroma.from_documents(
                documents=docs,
                embedding=embedding_model,
                persist_directory=test_dir
            )
            print("✅ ChromaDB создана успешно!")
            
            # Проверяем поиск
            results = vector_store.similarity_search("тест", k=1)
            print(f"✅ Поиск работает: найдено {len(results)} документов")
            
        finally:
            os.umask(old_umask)
            
    except Exception as e:
        print(f"❌ Ошибка создания ChromaDB: {e}")
        import traceback
        traceback.print_exc()
    
    # Проверяем созданные файлы
    print("\nСозданные файлы:")
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            file_path = os.path.join(root, file)
            stat_info = os.stat(file_path)
            print(f"  {file_path} - права: {oct(stat_info.st_mode)[-3:]}")

if __name__ == "__main__":
    test_chroma_creation()



