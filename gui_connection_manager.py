#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import queue
import time
import os
import webbrowser
import subprocess
import platform
from datetime import datetime
import json

from d import CrossPlatformConnectionManager

class CancellableConnectionManager(CrossPlatformConnectionManager):
    
    def __init__(self, target_ip, timeout=3, max_threads=50, cancel_callback=None):
        super().__init__(target_ip, timeout, max_threads)
        self.cancel_callback = cancel_callback
        self.is_cancelled = False
    
    def check_cancelled(self):
        if self.cancel_callback and self.cancel_callback():
            self.is_cancelled = True
            return True
        return False
    
    def check_host_availability(self):
        if self.check_cancelled():
            return False
            
        result = super().check_host_availability()
        
        if not result and not self.is_cancelled:
            return self.show_ping_failed_dialog()
        
        return result
    
    def show_ping_failed_dialog(self):
        return False

class ConnectionManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Артеллерийское точное подключение 42x САУ")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        self.current_theme = "default"
        self.themes = {
            "default": {"bg": "#f0f0f0", "fg": "#000000"},
        }
        
        self.setup_styles()
        
        self.connection_manager = None
        self.scan_thread = None
        self.is_scanning = False
        self.should_cancel = False
        self.message_queue = queue.Queue()
        self.open_ports_info = []
        
        self.create_widgets()
        
        self.process_queue()
        
        self.center_window()
        
        self.root.bind('<Escape>', lambda e: self.cancel_scan())
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="⚙️ Настройки", menu=settings_menu)
        
        settings_menu.add_separator()
        settings_menu.add_command(label="ℹ️ О программе", command=self.show_about)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Справка", menu=help_menu)
        help_menu.add_command(label="📖 Настройки сканирования", command=self.show_settings_help)
        help_menu.add_command(label="🔧 Ручное подключение", command=self.show_manual_help)
    
    def setup_styles(self):
        style = ttk.Style()
        
        if platform.system().lower() == "windows":
            style.theme_use('winnative')
        else:
            style.theme_use('clam')
        
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')
        style.configure('Info.TLabel', foreground='blue')
        
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        style.configure('Scan.TButton', font=('Arial', 11, 'bold'))
        
        style.configure('Active.TButton', 
                       font=('Arial', 10, 'bold'),
                       foreground='white',
                       background='#0078d4')
        style.configure('Inactive.TButton', 
                       font=('Arial', 10),
                       foreground='#666666',
                       background='#f0f0f0')
        
        style.map('Active.TButton',
                 background=[('active', '#106ebe'),
                            ('pressed', '#005a9e')])
        style.map('Inactive.TButton',
                 background=[('active', '#e0e0e0')])
    
    def create_widgets(self):
        self.create_menu()
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        title_label = ttk.Label(main_frame, text="🤖 Артеллерийское точное подключение 42x САУ", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        system_info = f"💻 Текущая ОС: {platform.system()} {platform.release()}"
        system_label = ttk.Label(main_frame, text=system_info)
        system_label.grid(row=1, column=0, columnspan=3, pady=(0, 15))
        
        self.create_input_section(main_frame, row=2)
        
        self.create_host_info_section(main_frame, row=3)
        
        self.create_results_section(main_frame, row=4)
        
        self.create_action_buttons(main_frame, row=5)
        
        self.create_status_bar(main_frame, row=6)
    
    def create_input_section(self, parent, row):
        input_frame = ttk.LabelFrame(parent, text="📡 Ввод параметров", padding="10")
        input_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="IP-адрес:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.ip_entry = ttk.Entry(input_frame, width=20, font=('Arial', 11))
        self.ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.ip_entry.bind('<Return>', lambda e: self.start_scan())
        
        self.scan_button = ttk.Button(input_frame, text="🔍 Сканировать", 
                                    command=self.start_scan, style='Scan.TButton')
        self.scan_button.grid(row=0, column=2, padx=(0, 5))
        
        self.cancel_button = ttk.Button(input_frame, text="⏹️ Отменить", 
                                      command=self.cancel_scan, style='Action.TButton',
                                      state='disabled')
        self.cancel_button.grid(row=0, column=3)
        
        settings_frame = ttk.Frame(input_frame)
        settings_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(settings_frame, text="Таймаут:").grid(row=0, column=0, padx=(0, 5))
        self.timeout_var = tk.StringVar(value="3")
        timeout_spin = ttk.Spinbox(settings_frame, from_=1, to=10, width=5, 
                                 textvariable=self.timeout_var)
        timeout_spin.grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(settings_frame, text="Потоки:").grid(row=0, column=2, padx=(0, 5))
        self.threads_var = tk.StringVar(value="100")
        threads_spin = ttk.Spinbox(settings_frame, from_=10, to=500, width=5, 
                                 textvariable=self.threads_var)
        threads_spin.grid(row=0, column=3)
    
    def create_host_info_section(self, parent, row):
        info_frame = ttk.LabelFrame(parent, text="🖥️ Информация о хосте", padding="10")
        info_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        
        ttk.Label(info_frame, text="Операционная система:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.os_label = ttk.Label(info_frame, text="Не определено", style='Info.TLabel')
        self.os_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(info_frame, text="Открытые порты:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.ports_label = ttk.Label(info_frame, text="Не сканировано", style='Info.TLabel')
        self.ports_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        ttk.Label(info_frame, text="Рекомендуемые методы:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.methods_label = ttk.Label(info_frame, text="Сначала выполните сканирование", style='Info.TLabel')
        self.methods_label.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))
    
    def create_results_section(self, parent, row):
        results_frame = ttk.LabelFrame(parent, text="📊 Результаты сканирования", padding="10")
        results_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        
        self.progress_var = tk.StringVar(value="Готов к сканированию")
        self.progress_label = ttk.Label(results_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(results_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(0, 5))
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15, width=80, 
                                                    font=('Consolas', 9))
        self.results_text.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), 
                              pady=(0, 10))
        
        results_buttons_frame = ttk.Frame(results_frame)
        results_buttons_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Button(results_buttons_frame, text="🗑️ Очистить", 
                 command=self.clear_results).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(results_buttons_frame, text="💾 Сохранить отчет", 
                 command=self.save_report).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(results_buttons_frame, text="📋 Копировать", 
                 command=self.copy_results).pack(side=tk.LEFT)
    
    def create_action_buttons(self, parent, row):
        actions_frame = ttk.LabelFrame(parent, text="🔗 Методы подключения", padding="10")
        actions_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.connection_buttons = {}
        
        buttons_data = [
            ("🌐 HTTP/HTTPS", self.connect_http, "Подключение к веб-интерфейсу"),
            ("🔒 SSH", self.connect_ssh, "Подключение по SSH"),
            ("🖥️ RDP", self.connect_rdp, "Подключение по RDP"),
            ("🔮 VNC", self.connect_vnc, "Подключение по VNC"),
            ("📁 FTP", self.connect_ftp, "Подключение по FTP"),
            ("📡 Telnet", self.connect_telnet, "Подключение по Telnet"),
            ("🛠️ MikroTik", self.connect_mikrotik, "Подключение к MikroTik"),
            ("🌐 Cisco", self.connect_cisco, "Подключение к Cisco"),
            ("🔧 Ручной выбор", self.manual_connection, "Расширенные опции подключения")
        ]
        
        for i, (text, command, tooltip) in enumerate(buttons_data):
            if text == "🔧 Ручной выбор":
                btn = ttk.Button(actions_frame, text=text, command=command, 
                               style='Active.TButton', state='normal')
            else:
                btn = ttk.Button(actions_frame, text=text, command=command, 
                               style='Inactive.TButton', state='disabled')
            btn.grid(row=i//4, column=i%4, padx=5, pady=5, sticky=(tk.W, tk.E))
            self.connection_buttons[text] = btn
        
        for i in range(4):
            actions_frame.columnconfigure(i, weight=1)
    
    def create_status_bar(self, parent, row):
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, 
                             anchor=tk.W, padding="5")
        status_bar.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def log_message(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        if level == "ERROR":
            formatted_message = f"❌ {formatted_message}"
        elif level == "SUCCESS":
            formatted_message = f"✅ {formatted_message}"
        elif level == "WARNING":
            formatted_message = f"⚠️ {formatted_message}"
        elif level == "INFO":
            formatted_message = f"ℹ️ {formatted_message}"
        
        self.message_queue.put(formatted_message)
    
    def show_yes_no_dialog(self, title, message):
        result = messagebox.askyesno(title, message)
        return result
    
    def show_input_dialog(self, title, message, default=""):
        result = simpledialog.askstring(title, message, initialvalue=default)
        return result if result is not None else ""
    
    def show_ping_failed_dialog(self):
        result_queue = queue.Queue()
        
        def show_dialog():
            try:
                result = messagebox.askyesno(
                    "Хост недоступен", 
                    f"Хост {self.connection_manager.target_ip} не отвечает на ping.\n\n"
                    "Продолжить сканирование портов? (может занять больше времени)"
                )
                result_queue.put(result)
            except Exception as e:
                print(f"Ошибка диалога: {e}")
                result_queue.put(False)
        
        self.root.after(0, show_dialog)
        
        try:
            result = result_queue.get(timeout=30)
            return result
        except queue.Empty:
            self.log_message("Таймаут диалога, прерываем сканирование", "WARNING")
            return False
    
    def process_queue(self):
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.results_text.insert(tk.END, message + "\n")
                self.results_text.see(tk.END)
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def start_scan(self):
        if self.is_scanning:
            return
        
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Ошибка", "Введите IP-адрес")
            return
        
        try:
            from ipaddress import ip_address
            ip_address(ip)
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат IP-адреса")
            return
        
        self.is_scanning = True
        self.should_cancel = False
        self.scan_button.config(state='disabled', text="⏳ Сканирование...")
        self.cancel_button.config(state='normal')
        self.progress_bar.start()
        self.progress_var.set("Сканирование запущено...")
        
        self.results_text.delete(1.0, tk.END)
        self.clear_connection_buttons()
        
        self.scan_thread = threading.Thread(target=self.scan_target, args=(ip,))
        self.scan_thread.daemon = True
        self.scan_thread.start()
    
    def cancel_scan(self):
        if not self.is_scanning:
            return
        
        if messagebox.askyesno("Отмена сканирования", 
                              "Вы уверены, что хотите отменить текущее сканирование?"):
            self.should_cancel = True
            self.log_message("Отмена сканирования...", "WARNING")
            self.progress_var.set("Отмена сканирования...")
            
            if self.scan_thread and self.scan_thread.is_alive():
                self.scan_thread.join(timeout=2.0)
            
            self.scan_complete()
            self.log_message("Сканирование отменено", "WARNING")
    
    def scan_target(self, ip):
        try:
            timeout = int(self.timeout_var.get())
            max_threads = int(self.threads_var.get())
            
            self.log_message(f"Начинаем сканирование {ip}")
            self.log_message(f"Параметры: таймаут={timeout}с, потоки={max_threads}")
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                return
            
            self.connection_manager = CancellableConnectionManager(
                ip, timeout, max_threads, 
                cancel_callback=lambda: self.should_cancel
            )
            self.connection_manager.show_ping_failed_dialog = self.show_ping_failed_dialog
            
            self.log_message("Проверяем доступность хоста...")
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                self.scan_complete()
                return
                
            host_available = self.connection_manager.check_host_availability()
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                self.scan_complete()
                return
                
            if not host_available:
                self.log_message("Хост недоступен", "WARNING")
                self.scan_complete()
                return
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                return
            
            self.log_message("Сканируем порты...")
            open_ports = self.scan_ports_with_cancel()
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                return
            
            if open_ports:
                self.log_message(f"Найдено {len(open_ports)} открытых портов", "SUCCESS")
                for port, service in open_ports:
                    self.log_message(f"Порт {port} ({service}) - открыт", "SUCCESS")
            else:
                self.log_message("Открытые порты не найдены", "WARNING")
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                return
            
            self.log_message("Анализируем операционную систему...")
            os_info = self.connection_manager.analyze_os()
            
            if self.should_cancel:
                self.log_message("Сканирование отменено пользователем", "WARNING")
                return
            
            if os_info:
                self.log_message(f"Предполагаемая ОС: {os_info.get('name', 'Неизвестно')}", "SUCCESS")
                self.log_message(f"Уверенность: {os_info.get('confidence', 0)}%", "INFO")
                
                self.update_host_info(os_info, open_ports)
            
            self.enable_connection_buttons(open_ports)
            
            if not self.should_cancel:
                self.log_message("Сканирование завершено", "SUCCESS")
            
        except Exception as e:
            if not self.should_cancel:
                self.log_message(f"Ошибка при сканировании: {str(e)}", "ERROR")
        finally:
            self.scan_complete()
    
    def scan_ports_with_cancel(self):
        try:
            common_ports = {
                21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
                53: 'DNS', 80: 'HTTP', 110: 'POP3', 135: 'RPC',
                139: 'NetBIOS', 143: 'IMAP', 443: 'HTTPS',
                445: 'SMB', 993: 'IMAPS', 995: 'POP3S',
                1433: 'MSSQL', 1521: 'Oracle', 3306: 'MySQL',
                3389: 'RDP', 5432: 'PostgreSQL', 5900: 'VNC',
                5901: 'VNC-1', 5902: 'VNC-2', 8080: 'HTTP-Alt', 
                8443: 'HTTPS-Alt', 33890: 'RDP-Alt', 5985: 'WinRM',
                5986: 'WinRM-SSL', 8291: 'MikroTik WinBox'
            }
            
            open_ports = []
            ports_to_scan = list(common_ports.keys())
            
            for i, port in enumerate(ports_to_scan):
                if self.should_cancel:
                    break
                
                progress = (i + 1) / len(ports_to_scan) * 100
                self.progress_var.set(f"Сканирование портов... {progress:.0f}%")
                
                result = self.connection_manager.check_port(port)
                if result[1]: 
                    service = common_ports[port]
                    open_ports.append((port, service))
                
                time.sleep(0.01)
            
            return open_ports
            
        except Exception as e:
            self.log_message(f"Ошибка при сканировании портов: {str(e)}", "ERROR")
            return []
    
    def update_host_info(self, os_info, open_ports):
        try:
            os_name = os_info.get('name', 'Неизвестно')
            confidence = os_info.get('confidence', 0)
            
            if 'MikroTik' in os_name or 'RouterOS' in os_name:
                os_name = "MikroTik RouterOS"
                confidence = max(confidence, 95)
            
            self.os_label.config(text=f"{os_name} (уверенность: {confidence}%)")
            
            if open_ports:
                ports_text = ", ".join([f"{port} ({service})" for port, service in open_ports])
                self.ports_label.config(text=ports_text)
                
                recommended_methods = []
                port_numbers = [port for port, _ in open_ports]
                
                if 80 in port_numbers or 443 in port_numbers:
                    recommended_methods.append("🌐 Веб-интерфейс")
                if 22 in port_numbers:
                    recommended_methods.append("🔒 SSH")
                if 3389 in port_numbers:
                    recommended_methods.append("🖥️ RDP")
                if 5900 in port_numbers or 5901 in port_numbers:
                    recommended_methods.append("🔮 VNC")
                if 21 in port_numbers:
                    recommended_methods.append("📁 FTP")
                if 23 in port_numbers:
                    recommended_methods.append("📡 Telnet")
                if 8291 in port_numbers:
                    recommended_methods.append("🛠️ MikroTik WinBox")
                
                if recommended_methods:
                    self.methods_label.config(text=", ".join(recommended_methods))
                else:
                    self.methods_label.config(text="Используйте ручной выбор")
            else:
                self.ports_label.config(text="Открытые порты не найдены")
                self.methods_label.config(text="Попробуйте ручной выбор")
                
        except Exception as e:
            self.log_message(f"Ошибка обновления информации о хосте: {str(e)}", "ERROR")
    
    def scan_complete(self):
        was_cancelled = self.should_cancel
        self.is_scanning = False
        self.should_cancel = False
        self.progress_bar.stop()
        
        if was_cancelled:
            self.progress_var.set("Сканирование отменено")
        else:
            self.progress_var.set("Сканирование завершено")
        
        self.scan_button.config(state='normal', text="🔍 Сканировать")
        self.cancel_button.config(state='disabled')
        self.status_var.set("Готов к работе")
        
        if "🔧 Ручной выбор" in self.connection_buttons:
            self.connection_buttons["🔧 Ручной выбор"].config(state='normal', style='Active.TButton')
    
    def clear_connection_buttons(self):
        for button_text, btn in self.connection_buttons.items():
            if button_text != "🔧 Ручной выбор":
                btn.config(state='disabled', style='Inactive.TButton')
    
    def enable_connection_buttons(self, open_ports):
        port_numbers = [port for port, _ in open_ports] if open_ports else []
        
        button_mapping = {
            "🌐 HTTP/HTTPS": [80, 443, 8080, 8443],
            "🔒 SSH": [22],
            "🖥️ RDP": [3389, 33890],
            "🔮 VNC": [5900, 5901, 5902],
            "📁 FTP": [21],
            "📡 Telnet": [23],
            "🛠️ MikroTik": [8291],
            "🌐 Cisco": [2000, 80, 443, 22, 23],
            "🔧 Ручной выбор": []
        }
        
        for button_text, required_ports in button_mapping.items():
            if button_text == "🔧 Ручной выбор" or any(port in port_numbers for port in required_ports):
                self.connection_buttons[button_text].config(state='normal', style='Active.TButton')
    
    def connect_http(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("Подключаемся к веб-интерфейсу...")
            self.connection_manager.http_connect()
        except Exception as e:
            self.log_message(f"Ошибка HTTP подключения: {str(e)}", "ERROR")
    
    def connect_ssh(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("🔒 SSH сервер обнаружен", "SUCCESS")
            self.show_ssh_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка SSH подключения: {str(e)}", "ERROR")
    
    def show_ssh_connection_info(self):
        if platform.system().lower() == "linux":
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message(f"📝 Для подключения используйте:", "INFO")
            self.log_message(f"   ssh username@{self.connection_manager.target_ip}", "INFO")
            
            if messagebox.askyesno("SSH подключение", "Попробовать автоматическое подключение через SSH?"):
                username = simpledialog.askstring("SSH подключение", "Введите имя пользователя SSH:", initialvalue="admin")
                if username:
                    cmd = f"ssh {username}@{self.connection_manager.target_ip}"
                    self.log_message(f"💻 Запускаем: {cmd}", "INFO")
                    try:
                        subprocess.Popen(cmd, shell=True)
                        self.log_message("SSH подключение запущено", "SUCCESS")
                    except Exception as e:
                        self.log_message(f"Ошибка запуска SSH: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ WINDOWS ===", "INFO")
            self.log_message(f"📝 Для подключения используйте:", "INFO")
            self.log_message(f"   putty {self.connection_manager.target_ip} -ssh", "INFO")
            self.log_message(f"   Используйте WSL: ssh username@{self.connection_manager.target_ip}", "INFO")
            
            info_text = f"""Для Windows используйте:
• putty {self.connection_manager.target_ip} -ssh
• Или WSL: ssh username@{self.connection_manager.target_ip}

Запустить putty?"""
            
            if messagebox.askyesno("SSH подключение", info_text):
                try:
                    subprocess.Popen(f"putty {self.connection_manager.target_ip} -ssh", shell=True)
                    self.log_message("Putty запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска Putty: {e}", "ERROR")
    
    def connect_rdp(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message(f"🖥️  Обнаружен RDP сервер ({self.connection_manager.target_ip}:3389)", "SUCCESS")
            self.show_rdp_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка RDP подключения: {str(e)}", "ERROR")
    
    def show_rdp_connection_info(self):
        if platform.system().lower() == "windows":
            cmd = f"mstsc /v:{self.connection_manager.target_ip}"
            self.log_message(f"🚀 Запускаем встроенный RDP клиент...", "INFO")
            self.log_message(f"💻 Команда: {cmd}", "INFO")
            
            if messagebox.askyesno("RDP подключение", f"Запустить RDP подключение к {self.connection_manager.target_ip}?"):
                try:
                    subprocess.Popen(cmd, shell=True)
                    self.log_message("RDP клиент запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска RDP: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   xfreerdp /v:IP /u:username /p:password", "INFO")
            self.log_message("   или rdesktop IP", "INFO")
            
            info_text = f"""Для Linux используйте:
• xfreerdp /v:{self.connection_manager.target_ip} /u:username /p:password
• или rdesktop {self.connection_manager.target_ip}

Попробовать автоматическое подключение?"""
            
            if messagebox.askyesno("RDP подключение", info_text):
                username = simpledialog.askstring("RDP подключение", "Введите имя пользователя:", initialvalue="administrator")
                if username:
                    try:
                        result = subprocess.run(['which', 'xfreerdp'], capture_output=True, text=True)
                        if result.returncode == 0:
                            cmd = f"xfreerdp /v:{self.connection_manager.target_ip} /u:{username}"
                            self.log_message(f"💻 Запускаем: {cmd}", "INFO")
                            subprocess.Popen(cmd, shell=True)
                            self.log_message("xfreerdp запущен", "SUCCESS")
                        else:
                            self.log_message("xfreerdp не найден. Установите: sudo apt install freerdp2-x11", "WARNING")
                    except Exception as e:
                        self.log_message(f"Ошибка запуска xfreerdp: {e}", "ERROR")
    
    def connect_vnc(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("🔮 Обнаружен VNC сервер", "SUCCESS")
            self.show_vnc_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка VNC подключения: {str(e)}", "ERROR")
    
    def show_vnc_connection_info(self):
        if platform.system().lower() == "linux":
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   vncviewer IP:5900", "INFO")
            self.log_message("   или vinagre IP:5900", "INFO")
            
            if messagebox.askyesno("VNC подключение", f"Попробовать автоматическое подключение к VNC серверу {self.connection_manager.target_ip}?"):
                try:
                    result = subprocess.run(['which', 'vncviewer'], capture_output=True, text=True)
                    if result.returncode == 0:
                        cmd = f"vncviewer {self.connection_manager.target_ip}:5900"
                        self.log_message(f"💻 Запускаем: {cmd}", "INFO")
                        subprocess.Popen(cmd, shell=True)
                        self.log_message("vncviewer запущен", "SUCCESS")
                    else:
                        self.log_message("vncviewer не найден. Установите: sudo apt install tigervnc-viewer", "WARNING")
                except Exception as e:
                    self.log_message(f"Ошибка запуска vncviewer: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ WINDOWS ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   TightVNC Viewer", "INFO")
            self.log_message("   RealVNC Viewer", "INFO")
            self.log_message("   UltraVNC Viewer", "INFO")
            
            info_text = f"""Для Windows используйте:
• TightVNC Viewer: {self.connection_manager.target_ip}:5900
• RealVNC Viewer: {self.connection_manager.target_ip}:5900
• UltraVNC Viewer: {self.connection_manager.target_ip}:5900

Открыть в браузере?"""
            
            if messagebox.askyesno("VNC подключение", info_text):
                try:
                    webbrowser.open(f"vnc://{self.connection_manager.target_ip}:5900")
                    self.log_message("VNC подключение открыто в браузере", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка открытия VNC: {e}", "ERROR")
    
    def connect_ftp(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("📁 Обнаружен FTP сервер", "SUCCESS")
            self.show_ftp_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка FTP подключения: {str(e)}", "ERROR")
    
    def show_ftp_connection_info(self):
        if platform.system().lower() == "linux":
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   ftp IP", "INFO")
            self.log_message("   или lftp IP", "INFO")
            
            if messagebox.askyesno("FTP подключение", f"Попробовать автоматическое подключение к FTP серверу {self.connection_manager.target_ip}?"):
                try:
                    cmd = f"ftp {self.connection_manager.target_ip}"
                    self.log_message(f"💻 Запускаем: {cmd}", "INFO")
                    subprocess.Popen(cmd, shell=True)
                    self.log_message("FTP клиент запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска FTP: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ WINDOWS ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   ftp IP", "INFO")
            self.log_message("   FileZilla", "INFO")
            self.log_message("   WinSCP", "INFO")
            
            info_text = f"""Для Windows используйте:
• ftp {self.connection_manager.target_ip}
• FileZilla: {self.connection_manager.target_ip}
• WinSCP: {self.connection_manager.target_ip}

Запустить командную строку FTP?"""
            
            if messagebox.askyesno("FTP подключение", info_text):
                try:
                    subprocess.Popen(f"ftp {self.connection_manager.target_ip}", shell=True)
                    self.log_message("FTP клиент запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска FTP: {e}", "ERROR")
    
    def connect_telnet(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("📡 Обнаружен Telnet сервер", "SUCCESS")
            self.show_telnet_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка Telnet подключения: {str(e)}", "ERROR")
    
    def show_telnet_connection_info(self):
        if platform.system().lower() == "linux":
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   telnet IP", "INFO")
            
            if messagebox.askyesno("Telnet подключение", f"Попробовать автоматическое подключение к Telnet серверу {self.connection_manager.target_ip}?"):
                try:
                    cmd = f"telnet {self.connection_manager.target_ip}"
                    self.log_message(f"💻 Запускаем: {cmd}", "INFO")
                    subprocess.Popen(cmd, shell=True)
                    self.log_message("Telnet клиент запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска Telnet: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ WINDOWS ===", "INFO")
            self.log_message("📝 Для подключения используйте:", "INFO")
            self.log_message("   telnet IP", "INFO")
            self.log_message("   PuTTY", "INFO")
            
            info_text = f"""Для Windows используйте:
• telnet {self.connection_manager.target_ip}
• PuTTY: {self.connection_manager.target_ip} -telnet

Запустить командную строку Telnet?"""
            
            if messagebox.askyesno("Telnet подключение", info_text):
                try:
                    subprocess.Popen(f"telnet {self.connection_manager.target_ip}", shell=True)
                    self.log_message("Telnet клиент запущен", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска Telnet: {e}", "ERROR")
    
    def connect_mikrotik(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("🛠️  Обнаружен MikroTik RouterOS", "SUCCESS")
            self.show_mikrotik_connection_info()
        except Exception as e:
            self.log_message(f"Ошибка MikroTik подключения: {str(e)}", "ERROR")
    
    def show_mikrotik_connection_info(self):
        web_interface = False
        open_port_numbers = [port for port, _ in self.connection_manager.open_ports] if self.connection_manager.open_ports else []
        
        for port in open_port_numbers:
            if port in [80, 443, 8080]:
                web_interface = True
                break
        
        if platform.system().lower() == "windows":
            self.log_message("=== ДЛЯ WINDOWS ===", "INFO")
            self.log_message("1. Используйте WinBox (рекомендуется):", "INFO")
            self.log_message("   - Скачайте WinBox с официального сайта MikroTik", "INFO")
            self.log_message(f"   - Подключитесь к {self.connection_manager.target_ip}:8291", "INFO")
            self.log_message("   - Логин: admin (пароль по умолчанию: пустой)", "INFO")
            
            if web_interface:
                self.log_message("2. Используйте веб-интерфейс:", "INFO")
                url = f"http://{self.connection_manager.target_ip}"
                self.log_message(f"   - Откройте: {url}", "INFO")
                
                info_text = f"""MikroTik RouterOS обнаружен!

Для Windows:
1. WinBox (рекомендуется):
   • Скачайте WinBox с официального сайта MikroTik
   • Подключитесь к {self.connection_manager.target_ip}:8291
   • Логин: admin (пароль по умолчанию: пустой)

2. Веб-интерфейс:
   • Откройте: {url}

Открыть веб-интерфейс в браузере?"""
                
                if messagebox.askyesno("MikroTik подключение", info_text):
                    try:
                        webbrowser.open(url)
                        self.log_message("Веб-интерфейс MikroTik открыт в браузере", "SUCCESS")
                    except Exception as e:
                        self.log_message(f"Ошибка открытия браузера: {e}", "ERROR")
            else:
                info_text = f"""MikroTik RouterOS обнаружен!

Для Windows:
• Скачайте WinBox с официального сайта MikroTik
• Подключитесь к {self.connection_manager.target_ip}:8291
• Логин: admin (пароль по умолчанию: пустой)

Открыть сайт MikroTik для скачивания WinBox?"""
                
                if messagebox.askyesno("MikroTik подключение", info_text):
                    try:
                        webbrowser.open("https://mikrotik.com/download")
                        self.log_message("Сайт MikroTik открыт в браузере", "SUCCESS")
                    except Exception as e:
                        self.log_message(f"Ошибка открытия браузера: {e}", "ERROR")
        else:
            self.log_message("=== ДЛЯ LINUX ===", "INFO")
            self.log_message("1. Используйте веб-интерфейс:", "INFO")
            if web_interface:
                url = f"http://{self.connection_manager.target_ip}"
                self.log_message(f"   - Откройте: {url}", "INFO")
                
                info_text = f"""MikroTik RouterOS обнаружен!

Для Linux:
• Веб-интерфейс: {url}
• Логин: admin (пароль по умолчанию: пустой)

Открыть веб-интерфейс в браузере?"""
                
                if messagebox.askyesno("MikroTik подключение", info_text):
                    try:
                        webbrowser.open(url)
                        self.log_message("Веб-интерфейс MikroTik открыт в браузере", "SUCCESS")
                    except Exception as e:
                        self.log_message(f"Ошибка открытия браузера: {e}", "ERROR")
            else:
                self.log_message("Веб-интерфейс недоступен", "WARNING")
                self.log_message("Попробуйте подключиться через WinBox на Windows", "INFO")
    
    def connect_cisco(self):
        if not self.connection_manager:
            return
        
        try:
            self.log_message("Подключаемся к Cisco...")
            self.cisco_gui_connect()
        except Exception as e:
            self.log_message(f"Ошибка Cisco подключения: {str(e)}", "ERROR")
    
    def cisco_gui_connect(self):
        open_port_numbers = [port for port, _ in self.connection_manager.open_ports] if self.connection_manager.open_ports else []
        
        web_available = any(port in open_port_numbers for port in [80, 443, 2000])
        ssh_available = 22 in open_port_numbers
        telnet_available = 23 in open_port_numbers
        
        if not any([web_available, ssh_available, telnet_available]):
            messagebox.showerror("Ошибка", "Нет доступных методов подключения к Cisco.\n\nПроверьте, что порты 2000, 80, 443, 22 или 23 открыты.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Выбор метода подключения Cisco")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        ttk.Label(dialog, text="🌐 Обнаружено Cisco устройство", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        ttk.Label(dialog, text="Выберите метод подключения:", 
                 font=('Arial', 10)).pack(pady=5)
        
        selected_method = tk.StringVar()
        
        if web_available:
            ttk.Radiobutton(dialog, text="1. Веб-интерфейс (рекомендуется)", 
                           variable=selected_method, value="web").pack(anchor=tk.W, padx=20, pady=5)
        
        if ssh_available:
            ttk.Radiobutton(dialog, text="2. SSH подключение", 
                           variable=selected_method, value="ssh").pack(anchor=tk.W, padx=20, pady=5)
        
        if telnet_available:
            ttk.Radiobutton(dialog, text="3. Telnet подключение", 
                           variable=selected_method, value="telnet").pack(anchor=tk.W, padx=20, pady=5)
        
        if web_available:
            selected_method.set("web")
        elif ssh_available:
            selected_method.set("ssh")
        elif telnet_available:
            selected_method.set("telnet")
        
        def on_connect():
            method = selected_method.get()
            dialog.destroy()
            
            if method == "web":
                self.cisco_web_gui_connect()
            elif method == "ssh":
                self.cisco_ssh_gui_connect()
            elif method == "telnet":
                self.cisco_telnet_gui_connect()
        
        ttk.Button(dialog, text="Подключиться", command=on_connect).pack(pady=20)
        ttk.Button(dialog, text="Отмена", command=dialog.destroy).pack()
    
    def cisco_web_gui_connect(self):
        web_port = None
        protocol = "http"
        
        if 2000 in [port for port, _ in self.connection_manager.open_ports]:
            web_port = 2000
        elif 443 in [port for port, _ in self.connection_manager.open_ports]:
            web_port = 443
            protocol = "https"
        elif 80 in [port for port, _ in self.connection_manager.open_ports]:
            web_port = 80
        
        if web_port:
            url = f"{protocol}://{self.connection_manager.target_ip}" + (f":{web_port}" if web_port not in [80, 443] else "")
            
            info_text = f"""URL: {url}

Стандартные учетные данные Cisco:
• Логин: admin, Пароль: admin
• Логин: cisco, Пароль: cisco
• Логин: enable, Пароль: enable
• Логин: admin, Пароль: (пустой)"""
            
            messagebox.showinfo("Информация о подключении", info_text)
            
            if messagebox.askyesno("Открыть браузер", f"Открыть {url} в браузере?"):
                try:
                    webbrowser.open(url)
                    self.log_message("Веб-интерфейс Cisco открыт в браузере", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка открытия браузера: {e}", "ERROR")
                    messagebox.showinfo("Информация", f"Откройте браузер и перейдите по адресу: {url}")
        else:
            messagebox.showerror("Ошибка", "Веб-интерфейс недоступен")
    
    def cisco_ssh_gui_connect(self):
        """GUI версия SSH подключения к Cisco"""
        username = simpledialog.askstring("SSH подключение", "Введите имя пользователя SSH:", initialvalue="admin")
        if not username:
            username = "admin"
        
        if platform.system().lower() == "linux":
            cmd = f"ssh {username}@{self.connection_manager.target_ip}"
            self.log_message(f"Команда SSH: {cmd}", "INFO")
            
            if messagebox.askyesno("Запуск SSH", f"Запустить SSH подключение?\n\nКоманда: {cmd}"):
                try:
                    subprocess.Popen(cmd, shell=True)
                    self.log_message("SSH подключение запущено", "SUCCESS")
                except Exception as e:
                    self.log_message(f"Ошибка запуска SSH: {e}", "ERROR")
        else:
            info_text = f"""Для Windows используйте:
• putty {self.connection_manager.target_ip} -ssh
• Или WSL: ssh {username}@{self.connection_manager.target_ip}"""
            messagebox.showinfo("SSH подключение", info_text)
    
    def cisco_telnet_gui_connect(self):
        """GUI версия Telnet подключения к Cisco"""
        username = simpledialog.askstring("Telnet подключение", "Введите имя пользователя Telnet:", initialvalue="admin")
        if not username:
            username = "admin"
        
        password = simpledialog.askstring("Telnet подключение", "Введите пароль (или оставьте пустым):", show='*')
        
        self.log_message(f"Подключаемся к {self.connection_manager.target_ip}:23...", "INFO")
        
        def telnet_thread():
            try:
                self.connection_manager.socket_telnet_connect(username, password)
            except Exception as e:
                self.log_message(f"Ошибка Telnet подключения: {e}", "ERROR")
        
        threading.Thread(target=telnet_thread, daemon=True).start()
    
    def manual_connection(self):
        if not self.connection_manager:
            messagebox.showwarning("Предупреждение", "Сначала выполните сканирование")
            return
        
        self.show_manual_connection_dialog()
    
    def show_manual_connection_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("🔧 Ручное подключение")
        dialog.geometry("600x500")
        dialog.resizable(False, False)
        
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="🔧 РУЧНОЕ ПОДКЛЮЧЕНИЕ", 
                               style='Header.TLabel')
        title_label.pack(pady=(0, 20))
        
        ports_frame = ttk.LabelFrame(main_frame, text="📊 Открытые порты", padding="10")
        ports_frame.pack(fill=tk.X, pady=(0, 15))
        
        if self.connection_manager.open_ports:
            for i, (port, service) in enumerate(self.connection_manager.open_ports, 1):
                port_frame = ttk.Frame(ports_frame)
                port_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(port_frame, text=f"{i}. Порт {port} ({service})").pack(side=tk.LEFT)
                ttk.Button(port_frame, text="Подключиться", 
                          command=lambda p=port, s=service: self.connect_to_port(p, s)).pack(side=tk.RIGHT)
        else:
            ttk.Label(ports_frame, text="Открытые порты не найдены").pack()
        
        options_frame = ttk.LabelFrame(main_frame, text="💡 Дополнительные опции", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(options_frame, text="🔍 Проверить конкретный порт", 
                  command=self.check_specific_port_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="📡 Полное сканирование портов", 
                  command=self.full_port_scan_dialog).pack(fill=tk.X, pady=2)
        ttk.Button(options_frame, text="🌐 Произвольный веб-порт", 
                  command=self.custom_web_port_dialog).pack(fill=tk.X, pady=2)
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(buttons_frame, text="❌ Закрыть", 
                  command=dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(buttons_frame, text="🔄 Обновить сканирование", 
                  command=lambda: [dialog.destroy(), self.start_scan()]).pack(side=tk.RIGHT)
    
    def connect_to_port(self, port, service):
        try:
            if port in [80, 443, 8080, 8443, 8291]:
                protocol = "https" if port in [443, 8443] else "http"
                url = f"{protocol}://{self.connection_manager.target_ip}" + (f":{port}" if port not in [80, 443] else "")
                
                if messagebox.askyesno("Открыть веб-интерфейс", f"Открыть {url} в браузере?"):
                    webbrowser.open(url)
                    self.log_message(f"Открыт веб-интерфейс: {url}", "SUCCESS")
                    
            elif port == 22:
                if platform.system().lower() == "linux":
                    username = tk.simpledialog.askstring("SSH подключение", "Введите имя пользователя:")
                    if username:
                        cmd = f"ssh {username}@{self.connection_manager.target_ip}"
                        self.log_message(f"Команда SSH: {cmd}", "INFO")
                        os.system(f"gnome-terminal -- bash -c '{cmd}; exec bash'" if os.system("which gnome-terminal") == 0 else cmd)
                else:
                    messagebox.showinfo("SSH подключение", f"Используйте Putty или другой SSH клиент для подключения к {self.connection_manager.target_ip}:22")
                    
            elif port == 3389:
                if platform.system().lower() == "windows":
                    cmd = f"mstsc /v:{self.connection_manager.target_ip}"
                    os.system(cmd)
                    self.log_message(f"Запущен RDP клиент: {cmd}", "SUCCESS")
                else:
                    messagebox.showinfo("RDP подключение", f"Используйте xfreerdp или rdesktop для подключения к {self.connection_manager.target_ip}:3389")
                    
            elif port == 8291:
                self.connection_manager.mikrotik_connect()
                
            else:
                messagebox.showinfo("Подключение", f"Для подключения к порту {port} ({service}) используйте соответствующий клиент")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {str(e)}")
    
    def check_specific_port_dialog(self):
        port = tk.simpledialog.askinteger("Проверка порта", "Введите номер порта (1-65535):", minvalue=1, maxvalue=65535)
        if port:
            self.log_message(f"Проверяем порт {port}...", "INFO")
            result = self.connection_manager.check_port(port)
            if result[1]:
                service = self.get_service_name(port)
                self.log_message(f"✅ Порт {port} открыт ({service})", "SUCCESS")
                if messagebox.askyesno("Порт открыт", f"Порт {port} ({service}) открыт. Подключиться?"):
                    self.connect_to_port(port, service)
            else:
                self.log_message(f"❌ Порт {port} закрыт", "WARNING")
                messagebox.showinfo("Результат", f"Порт {port} закрыт или недоступен")
    
    def get_service_name(self, port):
        try:
            import socket
            return socket.getservbyport(port)
        except:
            common_services = {
                21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
                53: 'DNS', 80: 'HTTP', 110: 'POP3', 443: 'HTTPS',
                3389: 'RDP', 5900: 'VNC', 8291: 'MikroTik WinBox'
            }
            return common_services.get(port, 'Unknown')
    
    def full_port_scan_dialog(self):
        if messagebox.askyesno("Полное сканирование", 
                              "Полное сканирование портов (1-65535) может занять значительное время. Продолжить?"):
            self.log_message("Запуск полного сканирования портов...", "INFO")
            messagebox.showinfo("Информация", "Полное сканирование будет реализовано в следующей версии")
    
    def custom_web_port_dialog(self):
        port = tk.simpledialog.askinteger("Веб-порт", "Введите номер порта для веб-подключения:", minvalue=1, maxvalue=65535)
        if port:
            protocol = tk.simpledialog.askstring("Протокол", "Использовать HTTPS? (y/n):", initialvalue="n").lower() == 'y'
            proto = "https" if protocol else "http"
            url = f"{proto}://{self.connection_manager.target_ip}:{port}"
            
            if messagebox.askyesno("Открыть URL", f"Открыть {url} в браузере?"):
                webbrowser.open(url)
                self.log_message(f"Открыт веб-интерфейс: {url}", "SUCCESS")
    
    def clear_results(self):
        self.results_text.delete(1.0, tk.END)
        self.clear_connection_buttons()
        self.progress_var.set("Готов к сканированию")
        self.cancel_button.config(state='disabled')
    
    def copy_results(self):
        try:
            text = self.results_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Результаты скопированы в буфер обмена")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось скопировать: {str(e)}")
    
    def save_report(self):
        if not self.connection_manager:
            messagebox.showwarning("Предупреждение", "Сначала выполните сканирование")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")],
                title="Сохранить отчет"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("ОТЧЕТ О СКАНИРОВАНИИ\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Цель: {self.connection_manager.target_ip}\n")
                    f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"ОС: {platform.system()} {platform.release()}\n\n")
                    
                    f.write("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ:\n")
                    f.write("-" * 30 + "\n")
                    f.write(self.results_text.get(1.0, tk.END))
                    
                    if hasattr(self.connection_manager, 'os_info') and self.connection_manager.os_info:
                        f.write("\n\nАНАЛИЗ ОС:\n")
                        f.write("-" * 15 + "\n")
                        f.write(f"Предполагаемая ОС: {self.connection_manager.os_info.get('name', 'Неизвестно')}\n")
                        f.write(f"Уверенность: {self.connection_manager.os_info.get('confidence', 0)}%\n")
                
                self.status_var.set(f"Отчет сохранен: {os.path.basename(filename)}")
                messagebox.showinfo("Успех", f"Отчет сохранен в файл:\n{filename}")
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить отчет: {str(e)}")
    
    def change_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            
            self.root.configure(bg=theme["bg"])
            
            style = ttk.Style()
            style.configure('TLabel', background=theme["bg"], foreground=theme["fg"])
            style.configure('TFrame', background=theme["bg"])
            style.configure('TLabelFrame', background=theme["bg"], foreground=theme["fg"])
            
            self.log_message(f"Тема изменена на: {theme_name}", "INFO")
    
    def show_about(self):
        about_text = """
🤖 Артеллерийское точное подключение 42x САУ

Версия: 1.0 Beta
Авторы: 42x САУ

Возможности:
• Определение операционной системы
• Сканирование портов
• Автоматическое подключение к сервисам
• Кроссплатформенность (Windows/Linux)
• Графический интерфейс

Внимание!
Данный проект находится на стадии тестирования и разработки.
В данном интерфейсе могут быть не реализованы некоторые методы
Для использования полной версии проекта, используйте терминал.

Используйте только для тестирования собственных систем!
@Защищено авторским правом. 2025г. РКСИ love
        """
        messagebox.showinfo("О программе", about_text)
    
    def show_settings_help(self):
        """Показать справку по настройкам"""
        help_text = """
📖 НАСТРОЙКИ СКАНИРОВАНИЯ

🔧 Таймаут (1-10 секунд):
• Определяет время ожидания ответа от порта
• Меньше значение = быстрее сканирование, но может пропустить медленные порты
• Больше значение = надежнее, но медленнее
• Рекомендуется: 3 секунды

🧵 Потоки (10-500):
• Количество одновременных подключений
• Больше потоков = быстрее сканирование
• Слишком много потоков может перегрузить сеть
• Рекомендуется: 100 потоков

💡 Советы:
• Для быстрого сканирования: таймаут=1, потоки=200
• Для надежного сканирования: таймаут=5, потоки=50
• Для медленных сетей: таймаут=10, потоки=20
        """
        messagebox.showinfo("Настройки сканирования", help_text)
    
    def show_manual_help(self):
        """Показать справку по ручному подключению"""
        help_text = """
🔧 РУЧНОЕ ПОДКЛЮЧЕНИЕ

📊 Открытые порты:
• Показывает все найденные открытые порты
• Кнопка "Подключиться" для каждого порта
• Автоматическое определение типа подключения

💡 Дополнительные опции:
• Проверить конкретный порт - проверка любого порта
• Полное сканирование - сканирование всех 65535 портов
• Произвольный веб-порт - подключение к любому веб-сервису

🌐 Поддерживаемые протоколы:
• HTTP/HTTPS - автоматическое открытие в браузере
• SSH - запуск SSH клиента (Linux) или инструкции (Windows)
• RDP - запуск Remote Desktop (Windows) или инструкции (Linux)
• MikroTik - специальная поддержка WinBox
• Другие - инструкции по подключению
        """
        messagebox.showinfo("Ручное подключение", help_text)

def main():
    root = tk.Tk()
    app = ConnectionManagerGUI(root)
    
    def on_closing():
        if app.is_scanning:
            if messagebox.askokcancel("Выход", "Сканирование выполняется. Завершить?"):
                app.should_cancel = True
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
