#!/bin/bash

# Bot control script for iteira_prototype
# Usage: ./bot_control.sh {start|stop|restart|status|logs}

# Путь к проекту
PROJECT_DIR="/Users/yauheni/Desktop/PLUG/iteira_prototype"
BOT_SCRIPT="main.py"
PID_FILE="$PROJECT_DIR/bot.pid"
LOG_FILE="$PROJECT_DIR/logs/bot.log"

# Создаем директорию для логов, если она не существует
mkdir -p "$PROJECT_DIR/logs"

# Функция для проверки, запущен ли бот
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            return 0
        else
            # Процесс не существует, удаляем файл PID
            rm -f "$PID_FILE"
            return 1
        fi
    else
        # Проверяем, есть ли другие процессы Python с main.py
        if pgrep -f "python.*$BOT_SCRIPT" > /dev/null; then
            return 0
        else
            return 1
        fi
    fi
}

# Функция для получения всех PID бота
get_bot_pids() {
    pgrep -f "python.*$BOT_SCRIPT"
}

# Функция для запуска бота
start() {
    if is_running; then
        echo "Бот уже запущен (PID: $(get_bot_pids))"
        return 1
    fi

    echo "Запуск бота..."
    
    # Активируем виртуальное окружение и запускаем бота в фоновом режиме
    cd "$PROJECT_DIR"
    source venv/bin/activate
    nohup python "$BOT_SCRIPT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    # Ждем немного, чтобы убедиться, что бот запустился
    sleep 2
    
    if is_running; then
        echo "Бот успешно запущен (PID: $(get_bot_pids))"
    else
        echo "Ошибка запуска бота. Проверьте логи: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Функция для остановки бота
stop() {
    echo "Остановка всех процессов бота..."
    
    # Получаем все PID процессов бота
    BOT_PIDS=$(get_bot_pids)
    
    if [ -n "$BOT_PIDS" ]; then
        echo "Найдены процессы бота: $BOT_PIDS"
        
        # Останавливаем все процессы
        for PID in $BOT_PIDS; do
            echo "Остановка процесса $PID..."
            kill "$PID" 2>/dev/null || echo "Не удалось остановить процесс $PID"
        done
        
        # Ждем немного, чтобы процессы завершились
        sleep 3
        
        # Проверяем, остались ли процессы, и убиваем их принудительно если нужно
        BOT_PIDS=$(get_bot_pids)
        if [ -n "$BOT_PIDS" ]; then
            echo "Принудительная остановка оставшихся процессов..."
            for PID in $BOT_PIDS; do
                echo "Принудительная остановка процесса $PID..."
                kill -9 "$PID" 2>/dev/null || echo "Не удалось остановить процесс $PID"
            done
        fi
        
        echo "Все процессы бота остановлены"
    else
        echo "Нет активных процессов бота"
    fi
    
    # Удаляем файл PID
    rm -f "$PID_FILE"
}

# Функция для перезапуска бота
restart() {
    stop
    # Ждем немного перед запуском
    sleep 2
    start
}

# Функция для проверки статуса бота
status() {
    if is_running; then
        echo "Бот запущен (PID: $(get_bot_pids))"
    else
        echo "Бот не запущен"
    fi
}

# Функция для просмотра логов
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "Файл логов не найден: $LOG_FILE"
    fi
}

# Основная логика
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0