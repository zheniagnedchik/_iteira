#!/usr/bin/env python3
"""
Утилита для очистки заблокированных баз данных ChromaDB
"""
import os
import shutil
import time
from config import CHROMA_PATH

def cleanup_chroma_db():
    """Принудительная очистка ChromaDB"""
    print("🧹 Очистка ChromaDB...")
    
    try:
        if os.path.exists(CHROMA_PATH):
            print(f"📁 Найдена база данных: {CHROMA_PATH}")
            
            # Попытка удалить с повторами
            for i in range(5):
                try:
                    shutil.rmtree(CHROMA_PATH)
                    print("✅ База данных успешно удалена")
                    return True
                except PermissionError as e:
                    if i < 4:
                        print(f"⏳ Файлы заблокированы, попытка {i+1}/5...")
                        time.sleep(2)
                    else:
                        print(f"❌ Не удалось удалить директорию: {e}")
                        # Попробуем переименовать директорию
                        backup_dir = f"{CHROMA_PATH}_backup_{int(time.time())}"
                        try:
                            os.rename(CHROMA_PATH, backup_dir)
                            print(f"📦 Директория переименована в {backup_dir}")
                            return True
                        except Exception as rename_error:
                            print(f"❌ Не удалось переименовать: {rename_error}")
                            return False
        else:
            print("ℹ️ База данных не найдена")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при очистке: {e}")
        return False

def cleanup_backup_dirs():
    """Очистка старых backup директорий"""
    print("🧹 Очистка старых backup директорий...")
    
    base_dir = os.path.dirname(CHROMA_PATH)
    if not os.path.exists(base_dir):
        return
    
    backup_count = 0
    for item in os.listdir(base_dir):
        if item.startswith("chroma_db_backup_"):
            backup_path = os.path.join(base_dir, item)
            try:
                shutil.rmtree(backup_path)
                backup_count += 1
                print(f"🗑️ Удален backup: {item}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить backup {item}: {e}")
    
    if backup_count > 0:
        print(f"✅ Удалено {backup_count} backup директорий")
    else:
        print("ℹ️ Backup директории не найдены")

def main():
    print("🔧 Утилита очистки ChromaDB")
    print("=" * 40)
    
    # Очистка основной базы
    if cleanup_chroma_db():
        print("✅ Основная база данных очищена")
    else:
        print("❌ Не удалось очистить основную базу данных")
    
    print()
    
    # Очистка backup директорий
    cleanup_backup_dirs()
    
    print()
    print("🎉 Очистка завершена!")
    print("💡 Теперь можно перезапустить API или перегенерировать базу знаний")

if __name__ == "__main__":
    main()