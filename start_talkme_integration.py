#!/usr/bin/env python3
"""
Скрипт для запуска TalkMe интеграции
Запускает основной API сервер с TalkMe webhook'ом
"""

import os
import sys
import time
import signal
import subprocess
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('talkme_integration.log')
    ]
)
logger = logging.getLogger(__name__)

def check_requirements():
    """Проверка наличия всех необходимых компонентов"""
    logger.info("🔍 Проверка требований...")
    
    # Проверяем Python пакеты
    required_packages = [
        'fastapi', 'uvicorn', 'pydantic', 'requests', 
        'langchain_core', 'python-dotenv'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"❌ Отсутствуют пакеты: {', '.join(missing_packages)}")
        logger.info("Установите их командой: pip install " + " ".join(missing_packages))
        return False
    
    # Проверяем конфигурацию
    try:
        from config import BASE_URL_TALKME, OPENAI_API_KEY
        if not BASE_URL_TALKME:
            logger.error("❌ Не настроен BASE_URL_TALKME в config.py")
            return False
        if not OPENAI_API_KEY:
            logger.error("❌ Не настроен OPENAI_API_KEY в config.py")
            return False
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта конфигурации: {e}")
        return False
    
    # Проверяем наличие агента
    try:
        from agent.consultation_agent import ConsultationAgent
        agent = ConsultationAgent()
        logger.info("✅ Консультационный агент инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации агента: {e}")
        return False
    
    logger.info("✅ Все требования выполнены")
    return True

def check_ports(ports=[8000]):
    """Проверка доступности портов"""
    import socket
    
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('localhost', port))
            if result == 0:
                logger.warning(f"⚠️  Порт {port} уже используется")
                return False
        finally:
            sock.close()
    
    logger.info(f"✅ Порты {ports} свободны")
    return True

def start_api_server():
    """Запуск API сервера с TalkMe интеграцией"""
    logger.info("🚀 Запуск API сервера с TalkMe интеграцией...")
    
    try:
        # Импортируем и запускаем
        import uvicorn
        from api import app
        
        # Выводим информацию
        print("\n" + "="*60)
        print("🎙️  TALKME ИНТЕГРАЦИЯ ДЛЯ ИТЕЙРА")
        print("="*60)
        print(f"🌐 API сервер: http://localhost:8000")
        print(f"📞 TalkMe Webhook: http://localhost:8000/webhook/talkme")
        print(f"🔍 Статистика: http://localhost:8000/webhook/talkme/stats")
        print(f"❤️  Проверка здоровья: http://localhost:8000/webhook/talkme/health")
        print(f"📊 API документация: http://localhost:8000/docs")
        print("="*60)
        print("💡 Для остановки нажмите Ctrl+C")
        print("="*60 + "\n")
        
        # Запускаем сервер
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False,
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка запуска сервера: {e}")
        return False

def show_config_info():
    """Показать информацию о конфигурации"""
    try:
        from config import BASE_URL_TALKME
        from services.talkme_api import get_api_status
        
        print("\n📋 КОНФИГУРАЦИЯ:")
        print(f"   TalkMe API URL: {BASE_URL_TALKME}")
        
        status = get_api_status()
        print("   Endpoints:")
        for name, url in status['endpoints'].items():
            print(f"     - {name}: {url}")
            
    except Exception as e:
        logger.warning(f"Не удалось показать конфигурацию: {e}")

def main():
    """Основная функция запуска"""
    print("🎙️  Запуск TalkMe интеграции для Итейра...")
    
    # Проверяем рабочую директорию
    if not os.path.exists('agent'):
        logger.error("❌ Запустите скрипт из корневой папки проекта")
        sys.exit(1)
    
    # Показываем конфигурацию
    show_config_info()
    
    # Проверяем требования
    if not check_requirements():
        logger.error("❌ Проверка требований не пройдена")
        sys.exit(1)
    
    # Проверяем порты
    if not check_ports([8000]):
        logger.error("❌ Порт 8000 занят. Остановите другие сервисы или измените порт")
        sys.exit(1)
    
    # Запускаем сервер
    try:
        success = start_api_server()
        if success:
            logger.info("✅ Сервер остановлен корректно")
        else:
            logger.error("❌ Сервер остановлен с ошибкой")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
