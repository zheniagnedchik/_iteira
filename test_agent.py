#!/usr/bin/env python3

import sys
import logging
from agent.consultation_agent import ConsultationAgent
from agent.state import ConsultationState
from langchain_core.messages import HumanMessage

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_agent():
    print("Начинаем тест агента...")
    try:
        print("Инициализация агента...")
        logger.info("Инициализация агента...")
        agent = ConsultationAgent()
        print("Агент инициализирован успешно")
        logger.info("Агент инициализирован успешно")
        
        # Создаем тестовое состояние
        print("Создание тестового состояния...")
        logger.info("Создание тестового состояния...")
        state = {
            "session_id": "test_session",
            "need_rag": True,
            "client_name": None,
            "gender": None,
            "messages": [HumanMessage(content="Привет")]
        }
        print("Тестовое состояние создано")
        logger.info("Тестовое состояние создано")
        
        # Запускаем агента
        print("Запуск агента...")
        logger.info("Запуск агента...")
        result = agent.run("test_session", state)
        print(f"Агент выполнен успешно. Результат: {type(result)}")
        logger.info(f"Агент выполнен успешно. Результат: {type(result)}")
        
        if hasattr(result, 'messages') and result.messages:
            print(f"Количество сообщений: {len(result.messages)}")
            logger.info(f"Количество сообщений: {len(result.messages)}")
            for i, msg in enumerate(result.messages):
                print(f"Сообщение {i}: {type(msg)} - {msg.content[:100]}...")
                logger.info(f"Сообщение {i}: {type(msg)} - {msg.content[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"Ошибка при тестировании агента: {e}")
        logger.error(f"Ошибка при тестировании агента: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_agent()
    print(f"Тест завершен. Успех: {success}")
    sys.exit(0 if success else 1)