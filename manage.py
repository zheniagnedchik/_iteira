#!/usr/bin/env python3
"""
Скрипт управления системой Iteira
"""
import sys
import subprocess
import os
import signal
import time

def start_bot():
    """Запуск Telegram бота"""
    print("🤖 Запуск Telegram бота...")
    subprocess.Popen([sys.executable, "main.py"])
    print("✅ Telegram бот запущен")

def start_api():
    """Запуск API сервера"""
    print("🚀 Запуск API сервера...")
    subprocess.Popen(["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"])
    print("✅ API сервер запущен на http://localhost:8000")
    print("🔄 Автоматическое отслеживание файлов включено")

def stop_services():
    """Остановка всех сервисов"""
    print("🛑 Остановка сервисов...")
    
    # Остановка процессов Python
    try:
        subprocess.run(["pkill", "-f", "main.py"], check=False)
        subprocess.run(["pkill", "-f", "uvicorn"], check=False)
        print("✅ Сервисы остановлены")
    except Exception as e:
        print(f"⚠️ Ошибка при остановке: {e}")

def status():
    """Проверка статуса сервисов"""
    print("📊 Статус сервисов:")
    
    # Проверка Telegram бота
    result = subprocess.run(["pgrep", "-f", "main.py"], capture_output=True)
    if result.returncode == 0:
        print("✅ Telegram бот: работает")
    else:
        print("❌ Telegram бот: не запущен")
    
    # Проверка API
    result = subprocess.run(["pgrep", "-f", "uvicorn"], capture_output=True)
    if result.returncode == 0:
        print("✅ API сервер: работает (включает автоотслеживание файлов)")
    else:
        print("❌ API сервер: не запущен")
    
    # Проверка файлового watcher (отдельного процесса)
    result = subprocess.run(["pgrep", "-f", "file_watcher.py"], capture_output=True)
    if result.returncode == 0:
        print("✅ Файловый watcher: работает (отдельный процесс)")
    else:
        print("ℹ️ Файловый watcher: не запущен как отдельный процесс")

def regenerate_kb():
    """Перегенерация базы знаний"""
    print("🔄 Перегенерация базы знаний...")
    try:
        from agent.vector_db import VectorDB
        vector_db = VectorDB()
        files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")
        vector_db.create_vector_store(files_path)
        print("✅ База знаний успешно перегенерирована")
    except Exception as e:
        print(f"❌ Ошибка при перегенерации: {e}")

def start_watcher():
    """Запуск файлового watcher"""
    print("👀 Запуск файлового watcher...")
    subprocess.Popen([sys.executable, "file_watcher.py"])
    print("✅ Файловый watcher запущен")

def show_help():
    """Показать справку"""
    print("""
🔧 Система управления Iteira

Команды:
  start-bot     Запустить Telegram бота
  start-api     Запустить API сервер (включает автоотслеживание файлов)
  start-watcher Запустить только файловый watcher
  start-all     Запустить все сервисы
  stop          Остановить все сервисы
  restart       Перезапустить все сервисы
  status        Показать статус сервисов
  regen-kb      Перегенерировать базу знаний
  test          Тестировать API
  help          Показать эту справку

Примеры:
  python manage.py start-all
  python manage.py status
  python manage.py stop

Примечание:
  При запуске API сервера автоматическое отслеживание файлов включается автоматически.
  База знаний будет перегенерироваться при любых изменениях в папке files/
""")

def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1]
    
    if command == "start-bot":
        start_bot()
    elif command == "start-api":
        start_api()
    elif command == "start-watcher":
        start_watcher()
    elif command == "start-all":
        start_bot()
        time.sleep(1)
        start_api()
        print("\n🎉 Все сервисы запущены!")
        print("🤖 Telegram бот: работает")
        print("🌐 API: http://localhost:8000")
        print("📖 Документация: http://localhost:8000/docs")
    elif command == "stop":
        stop_services()
    elif command == "restart":
        stop_services()
        time.sleep(2)
        start_bot()
        time.sleep(1)
        start_api()
        print("🔄 Сервисы перезапущены")
    elif command == "status":
        status()
    elif command == "regen-kb":
        regenerate_kb()
    elif command == "test":
        subprocess.run([sys.executable, "test_api.py"])
    elif command == "help":
        show_help()
    else:
        print(f"❌ Неизвестная команда: {command}")
        show_help()

if __name__ == "__main__":
    main()