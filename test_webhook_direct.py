#!/usr/bin/env python3

import asyncio
import logging
from talkme_handler import process_talkme_message, TalkMeMessage

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_webhook():
    print("Начинаем тест webhook...")
    try:
        # Создаем тестовое сообщение
        test_msg = TalkMeMessage(
            session_id="test_session_123",
            user_id="test_user_456",
            message="Привет",
            phone_number="+1234567890"
        )
        
        print("Вызываем process_talkme_message...")
        response = await process_talkme_message(test_msg)
        
        print(f"Получен ответ: {response}")
        print(f"Сообщение: {response.message}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка при тестировании webhook: {e}")
        logger.error(f"Ошибка при тестировании webhook: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_webhook())
    print(f"Тест завершен. Успех: {success}")