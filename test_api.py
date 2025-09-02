#!/usr/bin/env python3
"""
Скрипт для тестирования API
"""
import requests
import os

API_BASE = "http://localhost:8000"

def test_api():
    print("🧪 Тестирование Iteira Knowledge Base API")
    print("=" * 50)
    
    # Тест 1: Проверка статуса API
    print("1. Проверка статуса API...")
    try:
        response = requests.get(f"{API_BASE}/api")
        if response.status_code == 200:
            print("✅ API работает")
            print(f"   Ответ: {response.json()}")
        else:
            print("❌ API не отвечает")
            return
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return
    
    # Тест 2: Получение списка файлов
    print("\n2. Получение списка файлов...")
    try:
        response = requests.get(f"{API_BASE}/files")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Найдено файлов: {data['count']}")
            for file in data['files']:
                print(f"   - {file['name']} ({file['size']} байт)")
        else:
            print("❌ Ошибка получения списка файлов")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Тест 3: Статус базы знаний
    print("\n3. Проверка статуса базы знаний...")
    try:
        response = requests.get(f"{API_BASE}/knowledge-base/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ База знаний существует: {data['knowledge_base_exists']}")
            print(f"   Количество файлов: {data['files_count']}")
            print(f"   Путь к ChromaDB: {data['chroma_path']}")
        else:
            print("❌ Ошибка получения статуса базы знаний")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Тест 4: Перегенерация базы знаний
    print("\n4. Тестирование перегенерации базы знаний...")
    try:
        response = requests.post(f"{API_BASE}/knowledge-base/regenerate")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data['message']}")
        else:
            print("❌ Ошибка перегенерации базы знаний")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Тестирование завершено!")
    print(f"📖 Документация API: {API_BASE}/docs")
    print(f"🌐 Веб-интерфейс: {API_BASE}")

if __name__ == "__main__":
    test_api()