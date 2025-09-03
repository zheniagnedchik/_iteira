#!/usr/bin/env python3
"""
Тест ChromaDB в контексте API
"""
import os
import sys
sys.path.append('/root/iteira/_iteira')

from agent.vector_db import VectorDB

def test_vector_db():
    print("=== Тест VectorDB класса ===")
    
    # Создаем экземпляр VectorDB
    vector_db = VectorDB()
    print(f"Persist directory: {vector_db.persist_directory}")
    
    # Проверяем права доступа к папке
    if os.path.exists(vector_db.persist_directory):
        stat_info = os.stat(vector_db.persist_directory)
        print(f"Права папки: {oct(stat_info.st_mode)[-3:]}")
    else:
        print("Папка не существует")
    
    # Пытаемся создать базу данных
    files_path = "/root/iteira/_iteira/files"
    print(f"Files path: {files_path}")
    
    try:
        vector_db.create_vector_store(files_path)
        print("✅ VectorDB создана успешно!")
    except Exception as e:
        print(f"❌ Ошибка создания VectorDB: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vector_db()



