#!/usr/bin/env python3
"""
Файловый watcher для автоматической перегенерации базы знаний
при изменении файлов в папке files/
"""
import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sync_manager import regen_manager

class KnowledgeBaseHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы"""
    
    def __init__(self, files_path):
        self.files_path = files_path
        self.regeneration_delay = 2  # Задержка в секундах перед перегенерацией
        self.regeneration_timer = None
        
    def should_process_file(self, file_path):
        """Проверяет, нужно ли обрабатывать файл"""
        if not file_path:
            return False
            
        # Обрабатываем только .xlsx и .xls файлы
        return file_path.lower().endswith(('.xlsx', '.xls'))
    
    def schedule_regeneration(self):
        """Планирует перегенерацию с задержкой"""
        # Отменяем предыдущий таймер если он есть
        if self.regeneration_timer:
            self.regeneration_timer.cancel()
        
        # Создаем новый таймер
        self.regeneration_timer = threading.Timer(
            self.regeneration_delay, 
            self.regenerate_knowledge_base
        )
        self.regeneration_timer.start()
    
    def regenerate_knowledge_base(self):
        """Перегенерирует базу знаний"""
        result = regen_manager.regenerate(self.files_path, "FileWatcher")
        
        if result["status"] in ["skipped", "in_progress"]:
            print(f"ℹ️ {result['message']}")
        elif result["status"] == "error":
            print(f"❌ {result['message']}")
        # Успешные результаты уже логируются в менеджере
    
    def on_created(self, event):
        """Вызывается при создании файла"""
        if not event.is_directory and self.should_process_file(event.src_path):
            print(f"📁 Добавлен файл: {os.path.basename(event.src_path)}")
            self.schedule_regeneration()
    
    def on_deleted(self, event):
        """Вызывается при удалении файла"""
        if not event.is_directory and self.should_process_file(event.src_path):
            print(f"🗑️ Удален файл: {os.path.basename(event.src_path)}")
            self.schedule_regeneration()
    
    def on_modified(self, event):
        """Вызывается при изменении файла"""
        if not event.is_directory and self.should_process_file(event.src_path):
            print(f"✏️ Изменен файл: {os.path.basename(event.src_path)}")
            self.schedule_regeneration()
    
    def on_moved(self, event):
        """Вызывается при перемещении файла"""
        if not event.is_directory:
            if self.should_process_file(event.src_path) or self.should_process_file(event.dest_path):
                print(f"📦 Перемещен файл: {os.path.basename(event.src_path)} -> {os.path.basename(event.dest_path)}")
                self.schedule_regeneration()

class FileWatcher:
    """Класс для отслеживания изменений в папке files"""
    
    def __init__(self, files_path):
        self.files_path = files_path
        self.observer = Observer()
        self.handler = KnowledgeBaseHandler(files_path)
        
        # Создаем папку если её нет
        os.makedirs(files_path, exist_ok=True)
    
    def start(self):
        """Запускает отслеживание файлов"""
        print(f"👀 Запуск отслеживания изменений в папке: {self.files_path}")
        
        self.observer.schedule(
            self.handler, 
            self.files_path, 
            recursive=False
        )
        
        self.observer.start()
        print("✅ Файловый watcher запущен")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Останавливает отслеживание файлов"""
        print("🛑 Остановка файлового watcher...")
        self.observer.stop()
        self.observer.join()
        
        # Отменяем активный таймер если есть
        if self.handler.regeneration_timer:
            self.handler.regeneration_timer.cancel()
        
        print("✅ Файловый watcher остановлен")

def main():
    """Основная функция для запуска watcher как отдельного процесса"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files_path = os.path.join(base_dir, "files")
    
    watcher = FileWatcher(files_path)
    
    try:
        watcher.start()
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки")
        watcher.stop()

if __name__ == "__main__":
    main()