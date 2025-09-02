# 🎙️ TalkMe Интеграция для Итейра - Полное руководство

## 📋 Обзор

Оптимизированная интеграция с платформой TalkMe для обработки голосовых звонков и предоставления консультаций через телефонный канал с использованием AI-агента Итейра.

## ✨ Возможности

- 🎙️ **Обработка голосовых звонков** через TalkMe
- 🤖 **AI-консультант** с базой знаний Итейра
- 📞 **Поддержка номеров телефонов** клиентов
- 💾 **Управление состоянием** разговоров
- 🔄 **Retry логика** для надежности
- 📊 **Детальная статистика** и мониторинг
- 🛡️ **Обработка ошибок** и валидация
- ⚡ **Высокая производительность** и параллельная обработка

## 🚀 Быстрый запуск

### 1. Запуск интеграции

```bash
# Простой способ
python start_talkme_integration.py

# Или через основной API
python api.py
```

### 2. Проверка работоспособности

```bash
# Тест интеграции
python test_talkme_integration_new.py

# Проверка здоровья
curl http://localhost:8000/webhook/talkme/health
```

### 3. Настройка в TalkMe

Укажите webhook URL в панели TalkMe:
```
https://your-domain.com/webhook/talkme
```

## 📡 API Endpoints

### Основные endpoints

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/webhook/talkme` | Основной webhook для приема сообщений |
| `GET` | `/webhook/talkme/health` | Проверка здоровья сервиса |
| `GET` | `/webhook/talkme/stats` | Статистика активных сессий |
| `DELETE` | `/webhook/talkme/session/{user_id}` | Очистка конкретной сессии |
| `DELETE` | `/webhook/talkme/sessions` | Очистка всех сессий |

### Формат webhook запроса

```json
{
  "token": "your_api_token",
  "session_id": "unique_session_id",
  "user_id": "caller_id_or_user_id", 
  "client": {
    "clientId": "client_12345",
    "phone": "+1234567890"
  },
  "message": {
    "text": "текст сообщения от пользователя"
  },
  "originalOnlineChatMessage": {
    "dialogId": "dialog_001"
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {}
}
```

### Формат ответа

```json
{
  "success": true,
  "session_id": "unique_session_id",
  "message": "Сообщение отправлено",
  "end_conversation": false
}
```

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env`:

```env
# TalkMe API
BASE_URL_TALKME=https://api.talkme.ru/

# OpenAI для AI-агента
OPENAI_API_KEY=your_openai_api_key
```

### Настройка config.py

```python
# Talk Me API
BASE_URL_TALKME = os.getenv("BASE_URL_TALKME", "https://api.talkme.ru/")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

## 🏗️ Архитектура

### Компоненты системы

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   TalkMe API    │───▶│  Webhook Handler │───▶│  AI Agent       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  State Manager   │    │  Knowledge Base │
                       └──────────────────┘    └─────────────────┘
```

### Основные модули

- **`integrations/talkme_integration.py`** - Основная логика интеграции
- **`services/talkme_api.py`** - Клиент TalkMe API с retry логикой
- **`agent/consultation_agent.py`** - AI-агент консультант
- **`start_talkme_integration.py`** - Скрипт запуска

## 🔍 Мониторинг и отладка

### Статистика

```bash
curl http://localhost:8000/webhook/talkme/stats
```

Ответ:
```json
{
  "total_sessions": 45,
  "active_sessions": 3,
  "messages_processed": 127,
  "errors": 2,
  "active_sessions_details": [
    {
      "user_id": "user_12345...",
      "messages_count": 5,
      "client_name": "Анна",
      "phone_number": "+1234567890",
      "created_at": "2024-01-01T12:00:00",
      "last_activity": "2024-01-01T12:05:00"
    }
  ]
}
```

### Логирование

Логи сохраняются в:
- `talkme_integration.log` - логи интеграции
- `api.log` - общие логи API

Уровни логирования:
- `INFO` - обычные операции
- `WARNING` - предупреждения (не критичные ошибки)
- `ERROR` - критичные ошибки

### Очистка сессий

```bash
# Очистить конкретную сессию
curl -X DELETE http://localhost:8000/webhook/talkme/session/user_12345

# Очистить все сессии
curl -X DELETE http://localhost:8000/webhook/talkme/sessions
```

## 🧪 Тестирование

### Автоматические тесты

```bash
python test_talkme_integration_new.py
```

Тесты включают:
- ✅ Проверка здоровья сервиса
- ✅ Первое сообщение (приветствие)
- ✅ Продолжение разговора
- ✅ Обработка невалидных данных
- ✅ Параллельные запросы
- ✅ Длинные сообщения
- ✅ Статистика

### Ручное тестирование

```bash
# Тест webhook
curl -X POST http://localhost:8000/webhook/talkme \
  -H "Content-Type: application/json" \
  -d '{
    "token": "test_token_12345",
    "session_id": "test_session_123",
    "user_id": "test_user_456",
    "client": {"phone": "+1234567890"},
    "message": {"text": "Привет, расскажите о ваших услугах"}
  }'
```

### Mock сервер для разработки

```bash
python mock_talkme_server.py
```

Запускает mock TalkMe API на порту 5001 для тестирования.

## 🚀 Развертывание

### Production настройки

1. **Используйте HTTPS** для webhook URL
2. **Настройте reverse proxy** (nginx/Apache)
3. **Используйте Redis** для состояний вместо памяти
4. **Настройте мониторинг** (Prometheus/Grafana)
5. **Настройте логирование** в файлы с ротацией

### Docker развертывание

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "start_talkme_integration.py"]
```

### Systemd сервис

```ini
[Unit]
Description=TalkMe Integration for Iteira
After=network.target

[Service]
Type=simple
User=iteira
WorkingDirectory=/opt/iteira
ExecStart=/opt/iteira/venv/bin/python start_talkme_integration.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 🔧 Настройка производительности

### Оптимизация

```python
# В start_talkme_integration.py
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8000,
    workers=4,  # Количество worker процессов
    loop="uvloop",  # Быстрый event loop
    http="httptools"  # Быстрый HTTP парсер
)
```

### Limits и timeouts

- **Message timeout**: 30 секунд
- **API timeout**: 10 секунд
- **Typing timeout**: 15 секунд
- **Max message length**: 4000 символов
- **Max retries**: 3 попытки

## 🛠️ Устранение неполадок

### Частые проблемы

**1. Сервер не отвечает**
```bash
# Проверьте порт
lsof -i :8000
# Проверьте логи
tail -f talkme_integration.log
```

**2. TalkMe API недоступен**
```bash
# Проверьте конфигурацию
python -c "from config import BASE_URL_TALKME; print(BASE_URL_TALKME)"
```

**3. Агент не отвечает**
```bash
# Проверьте базу знаний
curl http://localhost:8000/knowledge-base/status
```

**4. Высокая нагрузка**
- Увеличьте количество workers
- Используйте Redis для состояний
- Оптимизируйте запросы к базе знаний

### Диагностические команды

```bash
# Статус сервиса
curl http://localhost:8000/webhook/talkme/health

# Статистика
curl http://localhost:8000/webhook/talkme/stats

# Полный тест
python test_talkme_integration_new.py
```

## 📚 Дополнительная информация

### Безопасность

- Валидация всех входящих данных
- Ограничение размера сообщений
- Rate limiting (рекомендуется)
- HTTPS для webhook URL

### Масштабирование

- Горизонтальное масштабирование с load balancer
- Redis для shared state
- Separate worker processes
- Message queue для обработки

### Мониторинг метрик

- Количество активных сессий
- Время обработки запросов
- Количество ошибок
- Использование памяти и CPU

---

## 🎯 Заключение

Интеграция готова к использованию и предоставляет надежный канал связи между TalkMe и AI-агентом Итейра. Система спроектирована для высокой производительности, надежности и простоты обслуживания.

Для получения поддержки обращайтесь к документации или проверьте логи системы.
