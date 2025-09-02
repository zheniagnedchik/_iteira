# services/talkme/api_requests.py

import asyncio
from config import BASE_URL_TALKME
import httpx
import logs.logging_config
import logging
import requests

logger = logging.getLogger(__name__)


def send_message_to_client(token: str, message: str):
    """
    Send a message to the client in the chat.
    """
    url = f"{BASE_URL_TALKME}customBot/send"
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "content":
            {"text": message}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        if not data.get("success"):
            logger.error(f"[SEND_MESSAGE_TO_CLIENT] TalkMe API error: {data}")
    except Exception as e:
        logger.error(f"[SEND_MESSAGE_TO_CLIENT] Exception during API call: {str(e)}")

def simulate_typing(token: str, ttl: int = 30):
    """
    Simulate typing in the chat.
    """
    url = f"{BASE_URL_TALKME}customBot/simulateTyping"
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "ttl": ttl
    }
    try:
        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        if not data.get("success"):
            logger.error(f"[SIMULATE_TYPING] TalkMe API error: {data}")
    except Exception as e:
        logger.error(f"[SIMULATE_TYPING] Exception during API call: {str(e)}")

def finish_custom_bot(token: str, code: str):
    """
    Finish the bot.
    """
    url = f"{BASE_URL_TALKME}customBot/finish"
    headers = {"X-Token": token, "Content-Type": "application/json"}
    payload = {
        "code": code
    }
    try:
        resp = requests.post(url, headers=headers, json=payload)
        data = resp.json()
        if not data.get("success"):
            logger.error(f"[FINISH_CUSTOM_BOT] TalkMe API error: {data}")
    except Exception as e:
        logger.error(f"[FINISH_CUSTOM_BOT] Exception during API call: {str(e)}")