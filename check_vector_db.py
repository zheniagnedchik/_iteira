#!/usr/bin/env python3
"""
Скрипт для проверки содержимого векторной базы данных
"""
import sys
sys.path.append('/root/iteira/_iteira')

from agent.vector_db import VectorDB

def check_vector_db():
    print("=== Проверка содержимого векторной базы данных ===")
    
    try:
        vector_db = VectorDB()
        vector_db.get_or_create_vector_store()
        
        # Получаем все документы
        results = vector_db.vector_store.get()
        
        print(f"Всего документов в базе: {len(results['ids']) if results['ids'] else 0}")
        
        if results['metadatas']:
            # Группируем по файлам
            files = {}
            for metadata in results['metadatas']:
                if metadata and 'filename' in metadata:
                    filename = metadata['filename']
                    files[filename] = files.get(filename, 0) + 1
            
            print("\nДокументы по файлам:")
            for filename, count in files.items():
                print(f"  - {filename}: {count} документов")
        
        # Показываем первые несколько документов
        if results['documents'] and len(results['documents']) > 0:
            print(f"\nПример документов:")
            for i, doc in enumerate(results['documents'][:3]):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                print(f"  {i+1}. Файл: {metadata.get('filename', 'неизвестно')}")
                print(f"     Содержимое: {doc[:100]}...")
                
    except Exception as e:
        print(f"Ошибка при проверке базы данных: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_vector_db()



