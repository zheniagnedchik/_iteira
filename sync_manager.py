#!/usr/bin/env python3
"""
Менеджер синхронизации для координации перегенерации базы знаний
между API и файловым watcher
"""
import threading
import time
import os
from agent.vector_db import VectorDB

class RegenerationManager:
    """Менеджер для синхронизации перегенерации базы знаний"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.regeneration_lock = threading.Lock()
            self.is_regenerating = False
            self.last_regeneration = 0
            self.min_interval = 2  # Минимальный интервал между перегенерациями в секундах
            self.vector_db = VectorDB()
            self.initialized = True
    
    def regenerate(self, files_path, source="Unknown"):
        """
        Безопасная перегенерация базы знаний с синхронизацией
        
        Args:
            files_path: Путь к папке с файлами
            source: Источник запроса перегенерации (для логирования)
        
        Returns:
            dict: Результат операции
        """
        current_time = time.time()
        
        # Проверяем минимальный интервал
        if current_time - self.last_regeneration < self.min_interval:
            return {
                "status": "skipped", 
                "message": f"Перегенерация пропущена (слишком частые запросы от {source})"
            }
        
        # Проверяем, не идет ли уже перегенерация
        if self.is_regenerating:
            return {
                "status": "in_progress", 
                "message": f"Перегенерация уже выполняется, запрос от {source} пропущен"
            }
        
        with self.regeneration_lock:
            # Двойная проверка после получения лока
            if self.is_regenerating:
                return {
                    "status": "in_progress", 
                    "message": f"Перегенерация уже выполняется, запрос от {source} пропущен"
                }
            
            self.is_regenerating = True
            try:
                print(f"🔄 Начинаем перегенерацию базы знаний (источник: {source})")
                
                # Проверяем существование папки с файлами
                if not os.path.exists(files_path):
                    os.makedirs(files_path, exist_ok=True)
                
                # Обеспечиваем правильные права доступа
                self._ensure_permissions(files_path)
                
                # Выполняем мягкую перегенерацию (без удаления директории)
                self.vector_db.soft_regenerate_vector_store(files_path)
                self.last_regeneration = current_time
                
                print(f"✅ База знаний успешно обновлена в {time.strftime('%H:%M:%S')} (источник: {source})")
                
                return {
                    "status": "success", 
                    "message": "База знаний успешно обновлена"
                }
                
            except Exception as e:
                error_msg = f"Ошибка при перегенерации базы знаний (источник: {source}): {str(e)}"
                print(f"❌ {error_msg}")
                return {
                    "status": "error", 
                    "message": error_msg
                }
            finally:
                self.is_regenerating = False
    
    def is_busy(self):
        """Проверяет, выполняется ли сейчас перегенерация"""
        return self.is_regenerating
    
    def _ensure_permissions(self, files_path):
        """Обеспечивает правильные права доступа к папкам данных"""
        import stat
        
        # Получаем базовую директорию проекта
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        directories = [
            os.path.join(base_dir, "data"),
            os.path.join(base_dir, "data", "chroma_db"),
            os.path.join(base_dir, "data", "knowledge_base"),
            files_path
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                # Устанавливаем права доступа 777 для папки
                os.chmod(directory, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            except Exception as e:
                print(f"Предупреждение: не удалось установить права для {directory}: {e}")
    
    def get_status(self):
        """Возвращает текущий статус менеджера"""
        return {
            "is_regenerating": self.is_regenerating,
            "last_regeneration": self.last_regeneration,
            "last_regeneration_time": time.strftime('%H:%M:%S', time.localtime(self.last_regeneration)) if self.last_regeneration > 0 else "Никогда"
        }

# Глобальный экземпляр менеджера
regen_manager = RegenerationManager()