#!/usr/bin/env python3
"""
Скрипт для запуска API сервера
"""
import uvicorn
from api import app

if __name__ == "__main__":
    print("Запуск Iteira Knowledge Base API...")
    print("API будет доступно по адресу: http://localhost:8000")
    print("Документация API: http://localhost:8000/docs")
    
    uvicorn.run(
        "api:app", 
        host="0.0.0.0", 
        port=8000,
        reload=True  # Автоперезагрузка при изменении кода
    )