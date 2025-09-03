from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import shutil
import threading
import asyncio
from pathlib import Path
from agent.vector_db import VectorDB
from sync_manager import regen_manager
from integrations.talkme_integration import handle_talkme_webhook, get_talkme_stats, clear_talkme_session, clear_all_talkme_sessions
import uvicorn

app = FastAPI(title="Iteira Knowledge Base API", version="1.0.0")

# Добавляем CORS middleware для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Путь к папке с файлами
FILES_DIR = "files"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_PATH = os.path.join(BASE_DIR, FILES_DIR)

# Создаем папку files если её нет
os.makedirs(FILES_PATH, exist_ok=True)

# Инициализируем VectorDB
vector_db = VectorDB()

# Запускаем API при старте приложения
@app.on_event("startup")
async def startup_event():
    print("🚀 API сервер запущен")
    # Обеспечиваем правильные права доступа при старте
    ensure_data_directories()

def refresh_rag_cache_internal():
    """Внутренняя функция для обновления RAG кэша"""
    try:
        # Очищаем кэш импортов Python для модуля tools
        import sys
        if 'agent.tools' in sys.modules:
            import importlib
            importlib.reload(sys.modules['agent.tools'])
        
        from agent.tools import get_vector_store
        import chromadb
        from config import CHROMA_PATH
        
        # Создаем новое подключение к векторной базе
        vector_store = get_vector_store()
        
        # Проверяем количество документов
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        langchain_col = client.get_collection('langchain')
        doc_count = langchain_col.count()
        
        return {
            "success": True,
            "message": "RAG кэш обновлен (с перезагрузкой модуля)",
            "documents_count": doc_count
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Ошибка обновления RAG кэша: {str(e)}",
            "documents_count": 0
        }

def ensure_data_directories():
    """Обеспечивает существование и правильные права доступа к папкам данных"""
    import stat
    
    directories = [
        os.path.join(BASE_DIR, "data"),
        os.path.join(BASE_DIR, "data", "chroma_db"),
        os.path.join(BASE_DIR, "data", "knowledge_base"),
        FILES_PATH
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            # Устанавливаем права доступа 777 для папки
            os.chmod(directory, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except Exception as e:
            print(f"Предупреждение: не удалось установить права для {directory}: {e}")

def update_knowledge_base_incremental(source="API"):
    """Инкрементальное обновление базы знаний"""
    try:
        # Обеспечиваем правильные права доступа
        ensure_data_directories()
        
        print(f"🔄 Начинаем инкрементальное обновление базы знаний (источник: {source})")
        
        # Используем инкрементальное обновление
        result = vector_db.update_knowledge_base_incrementally(FILES_PATH)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        print(f"✅ База знаний успешно обновлена (источник: {source})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении базы знаний: {str(e)}")

def add_file_to_knowledge_base(file_path, source="API"):
    """Добавить конкретный файл в базу знаний"""
    try:
        ensure_data_directories()
        
        print(f"➕ Добавляем файл в базу знаний: {os.path.basename(file_path)} (источник: {source})")
        
        result = vector_db.add_file_to_knowledge_base(file_path)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        print(f"✅ Файл успешно добавлен в базу знаний (источник: {source})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при добавлении файла в базу знаний: {str(e)}")

def remove_file_from_knowledge_base(filename, source="API"):
    """Удалить конкретный файл из базы знаний"""
    try:
        ensure_data_directories()
        
        print(f"➖ Удаляем файл из базы знаний: {filename} (источник: {source})")
        
        result = vector_db.remove_file_from_knowledge_base(filename)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        print(f"✅ Файл успешно удален из базы знаний (источник: {source})")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении файла из базы знаний: {str(e)}")

def regenerate_knowledge_base(source="API"):
    """Полная перегенерация базы знаний из файлов (для обратной совместимости)"""
    try:
        # Обеспечиваем правильные права доступа перед перегенерацией
        ensure_data_directories()
        
        result = regen_manager.regenerate(FILES_PATH, source)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении базы знаний: {str(e)}")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api")
async def api_info():
    return {"message": "Iteira Knowledge Base API", "version": "1.0.0"}

@app.get("/files")
async def get_files():
    """Получить список всех файлов"""
    try:
        files = []
        for filename in os.listdir(FILES_PATH):
            file_path = os.path.join(FILES_PATH, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                files.append({
                    "name": filename,
                    "size": file_size,
                    "path": f"/files/{filename}"
                })
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении списка файлов: {str(e)}")

@app.get("/files/{filename}")
async def download_file(filename: str):
    """Скачать конкретный файл"""
    file_path = os.path.join(FILES_PATH, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )

@app.post("/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Загрузить один или несколько файлов"""
    uploaded_files = []
    
    try:
        for file in files:
            # Проверяем расширение файла
            if not file.filename.endswith(('.xlsx', '.xls')):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Неподдерживаемый тип файла: {file.filename}. Поддерживаются только .xlsx и .xls файлы"
                )
            
            file_path = os.path.join(FILES_PATH, file.filename)
            
            # Сохраняем файл
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded_files.append({
                "name": file.filename,
                "size": os.path.getsize(file_path),
                "status": "uploaded"
            })
        
        # Добавляем файлы в базу знаний инкрементально
        knowledge_base_results = []
        for file_info in uploaded_files:
            file_path = os.path.join(FILES_PATH, file_info["name"])
            kb_result = add_file_to_knowledge_base(file_path)
            knowledge_base_results.append({
                "filename": file_info["name"],
                "knowledge_base_result": kb_result
            })
        
        return {
            "uploaded_files": uploaded_files,
            "knowledge_base_updates": knowledge_base_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке файлов: {str(e)}")

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """Удалить конкретный файл"""
    file_path = os.path.join(FILES_PATH, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    try:
        # Сначала удаляем из базы знаний
        kb_result = remove_file_from_knowledge_base(filename)
        
        # Затем удаляем физический файл
        os.remove(file_path)
        
        return {
            "message": f"Файл {filename} успешно удален",
            "knowledge_base_result": kb_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении файла: {str(e)}")

@app.delete("/files")
async def delete_all_files():
    """Удалить все файлы"""
    try:
        deleted_files = []
        for filename in os.listdir(FILES_PATH):
            file_path = os.path.join(FILES_PATH, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                deleted_files.append(filename)
        
        # Перегенерируем базу знаний (она будет пустой)
        regenerate_result = regenerate_knowledge_base()
        
        return {
            "message": f"Удалено {len(deleted_files)} файлов",
            "deleted_files": deleted_files,
            "knowledge_base": regenerate_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении файлов: {str(e)}")

@app.post("/knowledge-base/regenerate")
async def regenerate_kb():
    """Принудительно перегенерировать базу знаний (полная перегенерация)"""
    result = regenerate_knowledge_base()
    return result

@app.post("/knowledge-base/update")
async def update_kb():
    """Инкрементально обновить базу знаний"""
    result = update_knowledge_base_incremental()
    return result

@app.get("/knowledge-base/status")
async def get_kb_status():
    """Получить статус базы знаний"""
    try:
        chroma_path = vector_db.persist_directory
        kb_exists = os.path.exists(chroma_path)
        
        files_count = len([f for f in os.listdir(FILES_PATH) if os.path.isfile(os.path.join(FILES_PATH, f))])
        
        return {
            "knowledge_base_exists": kb_exists,
            "files_count": files_count,
            "chroma_path": chroma_path
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статуса: {str(e)}")



@app.post("/knowledge-base/refresh-cache")
async def refresh_rag_cache():
    """Обновить кэш RAG без перезапуска сервера"""
    result = refresh_rag_cache_internal()
    if result["success"]:
        result["timestamp"] = __import__('datetime').datetime.now().isoformat()
        return result
    else:
        raise HTTPException(status_code=500, detail=result["message"])


@app.get("/knowledge-base/regeneration/status")
async def get_regeneration_status():
    """Получить статус менеджера перегенерации"""
    status = regen_manager.get_status()
    return {
        "is_regenerating": status["is_regenerating"],
        "last_regeneration_time": status["last_regeneration_time"],
        "manager_status": "Активен" if not status["is_regenerating"] else "Выполняется перегенерация"
    }

# ========== TALK ME WEBHOOK ENDPOINTS ==========

@app.post("/webhook/talkme")
async def talkme_webhook_endpoint(request: Request):
    """Обработчик webhook от Talk Me"""
    return await handle_talkme_webhook(request)

@app.get("/webhook/talkme/health")
async def talkme_health_check():
    """Проверка здоровья Talk Me webhook"""
    return {"status": "ok", "service": "talkme_webhook"}

@app.get("/webhook/talkme/stats")
async def talkme_get_stats():
    """Статистика активных Talk Me сессий"""
    return await get_talkme_stats()

@app.delete("/webhook/talkme/session/{user_id}")
async def talkme_clear_session_endpoint(user_id: str):
    """Очистка Talk Me сессии пользователя"""
    return await clear_talkme_session(user_id)

@app.delete("/webhook/talkme/sessions")
async def talkme_clear_all_sessions():
    """Очистка всех Talk Me сессий"""
    return await clear_all_talkme_sessions()

@app.post("/webhook/talkme/debug")
async def talkme_debug_endpoint(request: Request):
    """DEBUG: Показать все данные от TalkMe"""
    body = await request.body()
    return {
        "headers": dict(request.headers),
        "body_raw": body.decode('utf-8', errors='replace'),
        "body_size": len(body),
        "url": str(request.url),
        "method": request.method,
        "query_params": dict(request.query_params)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)