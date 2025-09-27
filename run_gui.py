#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import platform

def check_dependencies():
    try:
        import tkinter
        print("✅ tkinter доступен")
    except ImportError:
        print("❌ tkinter не найден")
        if platform.system().lower() == "linux":
            print("💡 Установите tkinter: sudo apt install python3-tk")
        return False
    
    try:
        from desktop2proxy import CrossPlatformConnectionManager
        print("✅ Основной модуль найден")
    except ImportError:
        print("❌ Файл desktop2proxy.py не найден в текущей директории")
        return False
    
    return True

def main():
    print("🤖 Артеллерийское точное подключение 42x САУ")
    print("=" * 60)
    print(f"💻 Платформа: {platform.system()} {platform.release()}")
    print(f"🐍 Python: {sys.version}")
    print("=" * 60)
    
    if not check_dependencies():
        print("\n❌ Не все зависимости установлены")
        input("Нажмите Enter для выхода...")
        return
    
    print("\n🚀 Запуск графического интерфейса...")
    
    try:
        from gui_connection_manager import main as gui_main
        gui_main()
    except Exception as e:
        print(f"\n❌ Ошибка запуска GUI: {e}")
        print("\n💡 Попробуйте запустить версию для терминала:")
        print("   python desktop2proxy.py")
        input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()

