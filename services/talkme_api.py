# services/talkme_api.py

import asyncio
import httpx
import logging
import requests
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# TalkMe API endpoints через прокси
PROXY_BASE_URL = "https://oyster-app-9l6qa.ondigitalocean.app/"
BASE_URL_TALKME = f"{PROXY_BASE_URL}https://lcab.talk-me.ru/json/v1.0/"
URL_BOT_MESSAGE = f"{BASE_URL_TALKME}customBot/send"
URL_BOT_SIMULATE_TYPING = f"{BASE_URL_TALKME}customBot/simulateTyping"
URL_BOT_FINISH = f"{BASE_URL_TALKME}customBot/finish"


def send_message_to_client(token: str, message: str, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
    """
    Send a message to the client in the chat with retry logic.
    
    Args:
        token: API token
        message: Message text to send
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    url = URL_BOT_MESSAGE
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "content": {
            "text": message[:4000]  # Ограничиваем длину сообщения
        }
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"[SEND_MESSAGE] Попытка {attempt + 1}/{max_retries} отправки сообщения")
            
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            
            # Проверяем статус код
            if resp.status_code != 200:
                logger.error(f"[SEND_MESSAGE] HTTP {resp.status_code}: {resp.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Экспоненциальная задержка
                    continue
                return False
            
            try:
                data = resp.json()
            except ValueError as e:
                logger.error(f"[SEND_MESSAGE] Ошибка парсинга JSON ответа: {e}")
                logger.error(f"[SEND_MESSAGE] Ответ: {resp.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return False
            
            if not data.get("success"):
                logger.error(f"[SEND_MESSAGE] TalkMe API ошибка: {data}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return False
            
            logger.info(f"[SEND_MESSAGE] Сообщение отправлено успешно")
            return True
            
        except requests.exceptions.Timeout:
            logger.error(f"[SEND_MESSAGE] Timeout при отправке сообщения (попытка {attempt + 1})")
        except requests.exceptions.ConnectionError:
            logger.error(f"[SEND_MESSAGE] Ошибка соединения (попытка {attempt + 1})")
        except Exception as e:
            logger.error(f"[SEND_MESSAGE] Неожиданная ошибка: {str(e)} (попытка {attempt + 1})")
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (attempt + 1))
    
    logger.error(f"[SEND_MESSAGE] Не удалось отправить сообщение после {max_retries} попыток")
    return False


def simulate_typing(token: str, ttl: int = 30, max_retries: int = 2) -> bool:
    """
    Simulate typing in the chat.
    
    Args:
        token: API token
        ttl: Time to live for typing indicator in seconds
        max_retries: Maximum retry attempts
        
    Returns:
        bool: True if typing simulation started successfully
    """
    url = URL_BOT_SIMULATE_TYPING
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "ttl": min(ttl, 60)  # Ограничиваем максимальное время
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            
            if resp.status_code != 200:
                logger.warning(f"[SIMULATE_TYPING] HTTP {resp.status_code} (попытка {attempt + 1})")
                continue
            
            try:
                data = resp.json()
            except ValueError:
                logger.warning(f"[SIMULATE_TYPING] Ошибка парсинга ответа (попытка {attempt + 1})")
                continue
                
            if not data.get("success"):
                logger.warning(f"[SIMULATE_TYPING] API ошибка: {data} (попытка {attempt + 1})")
                continue
            
            logger.info(f"[SIMULATE_TYPING] Индикатор печати запущен на {ttl}с")
            return True
            
        except Exception as e:
            logger.warning(f"[SIMULATE_TYPING] Ошибка: {str(e)} (попытка {attempt + 1})")
    
    logger.warning(f"[SIMULATE_TYPING] Не удалось запустить индикатор печати")
    return False  # Не критично, если не получилось


def finish_custom_bot(token: str, code: str = "SUCCESS", max_retries: int = 2) -> bool:
    """
    Finish the bot session.
    
    Args:
        token: API token
        code: Completion code (SUCCESS, ERROR, etc.)
        max_retries: Maximum retry attempts
        
    Returns:
        bool: True if session finished successfully
    """
    url = URL_BOT_FINISH
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "code": code
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if resp.status_code != 200:
                logger.warning(f"[FINISH_BOT] HTTP {resp.status_code} (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue
            
            try:
                data = resp.json()
            except ValueError:
                logger.warning(f"[FINISH_BOT] Ошибка парсинга ответа (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue
                
            if not data.get("success"):
                logger.warning(f"[FINISH_BOT] API ошибка: {data} (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue
            
            logger.info(f"[FINISH_BOT] Сессия завершена с кодом: {code}")
            return True
            
        except Exception as e:
            logger.warning(f"[FINISH_BOT] Ошибка: {str(e)} (попытка {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    logger.error(f"[FINISH_BOT] Не удалось завершить сессию после {max_retries} попыток")
    return False


# Дополнительные утилиты для работы с TalkMe API

def validate_token(token: str) -> bool:
    """Проверка валидности токена"""
    if not token or len(token.strip()) < 10:
        logger.error("[VALIDATE_TOKEN] Токен слишком короткий или пустой")
        return False
    return True


def prepare_message_for_talkme(message: str) -> str:
    """Подготовка сообщения для отправки в TalkMe"""
    if not message:
        return "Пустое сообщение"
    
    # Обрезаем слишком длинные сообщения
    if len(message) > 4000:
        message = message[:3950] + "... (сообщение обрезано)"
    
    # Убираем лишние пробелы и переносы
    message = " ".join(message.split())
    
    return message


def get_api_status() -> Dict[str, Any]:
    """Получить статус TalkMe API"""
    return {
        "base_url": BASE_URL_TALKME,
        "endpoints": {
            "send": URL_BOT_MESSAGE,
            "typing": URL_BOT_SIMULATE_TYPING,
            "finish": URL_BOT_FINISH
        },
        "status": "configured"
    }