#!/usr/bin/env python3

import asyncio
import json
from talkme_handler import talkme_webhook
from fastapi import Request

class MockRequest:
    def __init__(self, body_data):
        self.body_data = json.dumps(body_data).encode('utf-8')
    
    async def body(self):
        return self.body_data

async def test_talkme_format():
    print("Тестируем формат Talk Me...")
    
    # Реальные данные от Talk Me (упрощенные)
    talkme_data = {
        "site": {"id": "2a5r5tv99b0nr4hkeo36ep1tw1x7tztr", "domain": "iteira"},
        "client": {
            "searchId": 33538,
            "login": "1_posetitel_v_sentyabre_2025_goda_143198132163__xi4bd2a",
            "clientId": "xI4WylKDvtas8rgfe7n6BJMfPRlTZnpA",
            "name": "1 посетитель в сентябре 2025 года",
            "phone": None
        },
        "message": {"text": "Привет"},
        "originalOnlineChatMessage": {
            "id": 33688,
            "text": "Привет",
            "dialogId": 3120
        }
    }
    
    try:
        mock_request = MockRequest(talkme_data)
        response = await talkme_webhook(mock_request)
        print(f"Успех! Ответ: {response.body}")
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_talkme_format())
    print(f"Тест завершен. Успех: {success}")