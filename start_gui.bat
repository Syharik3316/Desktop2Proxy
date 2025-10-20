@echo off
chcp 65001 >nul
echo 🤖 SyharikDP
echo ================================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден в системе
    echo 💡 Установите Python с https://python.org
    pause
    exit /b 1
)

REM Проверка наличия файлов
if not exist "desktop2proxy.py" (
    echo ❌ Файл desktop2proxy.py не найден
    echo 💡 Убедитесь, что все файлы находятся в одной папке
    pause
    exit /b 1
)

if not exist "gui_connection_manager.py" (
    echo ❌ Файл gui_connection_manager.py не найден
    echo 💡 Убедитесь, что все файлы находятся в одной папке
    pause
    exit /b 1
)

echo ✅ Все файлы найдены
echo 🚀 Запуск графического интерфейса...
echo.

python gui_connection_manager.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска
    echo 💡 Попробуйте запустить консольную версию: python desktop2proxy.py
    pause
)

