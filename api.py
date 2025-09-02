from fastapi import FastAPI, UploadFile, File, HTTPException
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

def regenerate_knowledge_base(source="API"):
    """Перегенерация базы знаний из файлов"""
    try:
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
        
        # Перегенерируем базу знаний
        regenerate_result = regenerate_knowledge_base()
        
        return {
            "uploaded_files": uploaded_files,
            "knowledge_base": regenerate_result
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
        os.remove(file_path)
        
        # Перегенерируем базу знаний
        regenerate_result = regenerate_knowledge_base()
        
        return {
            "message": f"Файл {filename} успешно удален",
            "knowledge_base": regenerate_result
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
    """Принудительно перегенерировать базу знаний"""
    return regenerate_knowledge_base()

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



@app.get("/knowledge-base/regeneration/status")
async def get_regeneration_status():
    """Получить статус менеджера перегенерации"""
    status = regen_manager.get_status()
    return {
        "is_regenerating": status["is_regenerating"],
        "last_regeneration_time": status["last_regeneration_time"],
        "manager_status": "Активен" if not status["is_regenerating"] else "Выполняется перегенерация"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)