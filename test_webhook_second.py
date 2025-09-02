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
        # Первое сообщение
        test_msg1 = TalkMeMessage(
            session_id="test_session_123",
            user_id="test_user_456",
            message="Привет",
            phone_number="+1234567890"
        )
        
        print("Отправляем первое сообщение...")
        response1 = await process_talkme_message(test_msg1)
        print(f"Первый ответ: {response1.message[:100]}...")
        
        # Второе сообщение
        test_msg2 = TalkMeMessage(
            session_id="test_session_123",
            user_id="test_user_456",
            message="Меня зовут Анна",
            phone_number="+1234567890"
        )
        
        print("Отправляем второе сообщение...")
        response2 = await process_talkme_message(test_msg2)
        print(f"Второй ответ: {response2.message[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"Ошибка при тестировании webhook: {e}")
        logger.error(f"Ошибка при тестировании webhook: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_webhook())
    print(f"Тест завершен. Успех: {success}")