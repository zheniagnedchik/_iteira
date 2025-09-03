#!/usr/bin/env python3
"""
Тест с точно тем же путем, что использует API
"""
import os
import sys
sys.path.append('/root/iteira/_iteira')

from config import CHROMA_PATH, OPENAI_API_KEY
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document

def test_exact_path():
    print(f"=== Тест с путем {CHROMA_PATH} ===")
    
    # Удаляем старую базу
    if os.path.exists(CHROMA_PATH):
        import shutil
        shutil.rmtree(CHROMA_PATH)
    
    # Создаем папку
    os.makedirs(CHROMA_PATH, exist_ok=True)
    os.chmod(CHROMA_PATH, 0o777)
    print(f"Папка создана: {CHROMA_PATH}")
    
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
                persist_directory=CHROMA_PATH,
                collection_name=f"test_{int(__import__('time').time())}"
            )
            print("✅ ChromaDB создана успешно!")
            
        finally:
            os.umask(old_umask)
            
    except Exception as e:
        print(f"❌ Ошибка создания ChromaDB: {e}")
        import traceback
        traceback.print_exc()
    
    # Проверяем созданные файлы
    print("\nСозданные файлы:")
    for root, dirs, files in os.walk(CHROMA_PATH):
        for file in files:
            file_path = os.path.join(root, file)
            stat_info = os.stat(file_path)
            print(f"  {file_path} - права: {oct(stat_info.st_mode)[-3:]}")

if __name__ == "__main__":
    test_exact_path()



