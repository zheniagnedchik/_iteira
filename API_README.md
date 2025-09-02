# Iteira Knowledge Base API

API для управления файлами и базой знаний проекта Iteira.

## Запуск API

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск API сервера
python run_api.py
```

API будет доступно по адресу: http://localhost:8000

## Веб-интерфейс

Откройте http://localhost:8000 в браузере для доступа к веб-интерфейсу управления файлами.

## API Эндпоинты

### Управление файлами

#### GET /files
Получить список всех файлов в базе знаний.

**Ответ:**
```json
{
  "files": [
    {
      "name": "example.xlsx",
      "size": 12345,
      "path": "/files/example.xlsx"
    }
  ],
  "count": 1
}
```

#### GET /files/{filename}
Скачать конкретный файл.

#### POST /files/upload
Загрузить один или несколько файлов. После загрузки база знаний автоматически перегенерируется.

**Параметры:**
- `files`: Список файлов (поддерживаются .xlsx и .xls)

**Ответ:**
```json
{
  "uploaded_files": [
    {
      "name": "example.xlsx",
      "size": 12345,
      "status": "uploaded"
    }
  ],
  "knowledge_base": {
    "status": "success",
    "message": "База знаний успешно обновлена"
  }
}
```

#### DELETE /files/{filename}
Удалить конкретный файл. После удаления база знаний автоматически перегенерируется.

**Ответ:**
```json
{
  "message": "Файл example.xlsx успешно удален",
  "knowledge_base": {
    "status": "success",
    "message": "База знаний успешно обновлена"
  }
}
```

#### DELETE /files
Удалить все файлы. После удаления база знаний автоматически перегенерируется.

### Управление базой знаний

#### POST /knowledge-base/regenerate
Принудительно перегенерировать базу знаний из текущих файлов.

**Ответ:**
```json
{
  "status": "success",
  "message": "База знаний успешно обновлена"
}
```

#### GET /knowledge-base/status
Получить статус базы знаний.

**Ответ:**
```json
{
  "knowledge_base_exists": true,
  "files_count": 5,
  "chroma_path": "/path/to/chroma_db"
}
```

## Автоматическая документация

FastAPI автоматически генерирует интерактивную документацию:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Примеры использования

### Загрузка файла через curl

```bash
curl -X POST "http://localhost:8000/files/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@example.xlsx"
```

### Получение списка файлов

```bash
curl -X GET "http://localhost:8000/files" \
  -H "accept: application/json"
```

### Удаление файла

```bash
curl -X DELETE "http://localhost:8000/files/example.xlsx" \
  -H "accept: application/json"
```

### Перегенерация базы знаний

```bash
curl -X POST "http://localhost:8000/knowledge-base/regenerate" \
  -H "accept: application/json"
```

## Интеграция с Telegram ботом

API работает независимо от Telegram бота. После изменения файлов через API, бот автоматически будет использовать обновленную базу знаний при следующих запросах.

## Безопасность

В текущей версии API не имеет аутентификации. Для продакшена рекомендуется:
- Добавить аутентификацию (JWT токены)
- Ограничить CORS origins
- Добавить rate limiting
- Валидацию размера файлов