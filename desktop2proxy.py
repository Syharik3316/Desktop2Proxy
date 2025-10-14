import socket
import threading
import time
import subprocess
import platform
import os
import webbrowser
import json
import select
import sys
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_address
from datetime import datetime

class CrossPlatformConnectionManager:
    def __init__(self, target_ip, timeout=3, max_threads=100):
        self.target_ip = target_ip
        self.timeout = timeout
        self.max_threads = max_threads
        self.open_ports = []
        self.os_info = {}
        self.is_windows = platform.system().lower() == "windows"
        self.is_linux = platform.system().lower() == "linux"
        self.scan_results = {}
        self.start_time = time.time()
        
    def validate_ip(self):
        try:
            ip_address(self.target_ip)
            return True
        except ValueError:
            return False

    def check_port(self, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                result = sock.connect_ex((self.target_ip, port))
                return port, result == 0
        except Exception as e:
            return port, False

    def scan_common_ports(self):
        common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
            53: 'DNS', 80: 'HTTP', 110: 'POP3', 135: 'RPC',
            139: 'NetBIOS', 143: 'IMAP', 443: 'HTTPS',
            445: 'SMB', 993: 'IMAPS', 995: 'POP3S',
            1433: 'MSSQL', 1521: 'Oracle', 3306: 'MySQL',
            3389: 'RDP', 5432: 'PostgreSQL', 5900: 'VNC',
            5901: 'VNC-1', 5902: 'VNC-2', 8080: 'HTTP-Alt', 
            8443: 'HTTPS-Alt', 33890: 'RDP-Alt', 5985: 'WinRM',
            5986: 'WinRM-SSL', 8291: 'MikroTik WinBox',
            2000: 'Cisco Web Interface'
        }
        
        print("🔍 Сканирование портов для определения сервисов...")
        open_ports = []
        
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            results = executor.map(self.check_port, common_ports.keys())
            
            for port, is_open in results:
                if is_open:
                    service = common_ports[port]
                    open_ports.append((port, service))
                    print(f"✅ Порт {port} открыт ({service})")
        
        self.open_ports = open_ports
        return open_ports

    def ping_host(self):
        try:
            if self.is_windows:
                cmd = ["ping", "-n", "3", "-w", "3000", self.target_ip]
            else:
                cmd = ["ping", "-c", "3", "-W", "3", self.target_ip]
            
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=5,
                startupinfo=startupinfo
            )
            
            return result.returncode == 0
        except:
            return False

    def detect_os_by_ttl(self):
        try:
            if not self.ping_host():
                return "Хост недоступен для проверки TTL"
            
            if self.is_windows:
                cmd = ["ping", "-n", "2", self.target_ip]
            else:
                cmd = ["ping", "-c", "2", self.target_ip]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                ttl_values = []
                
                for line in lines:
                    line_lower = line.lower()
                    if "ttl=" in line_lower:
                        try:
                            ttl_part = line_lower.split("ttl=")[1]
                            ttl_str = ttl_part.split()[0]
                            if ttl_str.isdigit():
                                ttl_values.append(int(ttl_str))
                        except:
                            continue
                
                if ttl_values:
                    ttl_common = max(set(ttl_values), key=ttl_values.count)
                    
                    if ttl_common <= 64:
                        return f"Linux/Unix (TTL: {ttl_common})"
                    elif 65 <= ttl_common <= 128:
                        return f"Windows (TTL: {ttl_common})"
                    elif ttl_common == 255:
                        return f"Сетевое устройство Cisco (TTL: {ttl_common})"
                    elif ttl_common > 128:
                        return f"Другое сетевое устройство (TTL: {ttl_common})"
                    else:
                        return f"Неопределенная ОС (TTL: {ttl_common})"
            
            return "Не удалось определить по TTL"
            
        except Exception as e:
            return f"Ошибка определения: {str(e)}"

    def get_service_banner(self, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.target_ip, port))
                
                sock.setblocking(False)
                
                ready = select.select([sock], [], [], self.timeout)
                banner = ""
                
                if ready[0]:
                    try:
                        banner = sock.recv(1024).decode('utf-8', errors='ignore')
                        
                        if port in [80, 443, 8080, 8443, 8291]:
                            http_request = "HEAD / HTTP/1.1\r\nHost: {}\r\nUser-Agent: Mozilla/5.0\r\n\r\n".format(self.target_ip)
                            sock.send(http_request.encode())
                            time.sleep(0.5)
                            ready = select.select([sock], [], [], self.timeout)
                            if ready[0]:
                                additional_data = sock.recv(2048).decode('utf-8', errors='ignore')
                                banner += additional_data
                        elif port == 21:
                            sock.send(b"SYST\r\n")
                            time.sleep(0.5)
                            ready = select.select([sock], [], [], self.timeout)
                            if ready[0]:
                                additional_data = sock.recv(1024).decode('utf-8', errors='ignore')
                                banner += additional_data
                        elif port == 22:
                            time.sleep(1)
                            ready = select.select([sock], [], [], self.timeout)
                            if ready[0]:
                                additional_data = sock.recv(1024).decode('utf-8', errors='ignore')
                                banner += additional_data
                    except (BlockingIOError, socket.error):
                        pass
                
                return banner.strip() if banner else "Нет баннера"
                
        except Exception:
            return "Не удалось получить баннер"

    def detect_os_by_banner(self):
        banners = []
        
        for port, service in self.open_ports:
            try:
                banner = self.get_service_banner(port)
                if banner and "Не удалось получить баннер" not in banner and banner != "Нет баннера":
                    banners.append((service, port, banner))
                    print(f"🎯 Баннер {service}({port}): {banner[:150]}...")
            except:
                pass
        
        os_hints = []
        for service, port, banner in banners:
            banner_lower = banner.lower()
            
            if any(x in banner_lower for x in ['windows', 'microsoft', 'iis', 'asp.net']):
                os_hints.append(('Windows', 85))
            elif any(x in banner_lower for x in ['linux', 'unix', 'ubuntu', 'debian', 'centos', 'red hat', 'apache', 'nginx']):
                os_hints.append(('Linux/Unix', 80))
            elif any(x in banner_lower for x in ['cisco', 'router', 'switch', 'ios']):
                os_hints.append(('Сетевое устройство Cisco', 90))
            elif any(x in banner_lower for x in ['mikrotik', 'routeros']):
                os_hints.append(('MikroTik RouterOS', 95))
            elif any(x in banner_lower for x in ['freebsd', 'openbsd']):
                os_hints.append(('BSD', 75))
            elif 'solaris' in banner_lower:
                os_hints.append(('Solaris', 70))
        
        unique_hints = {}
        for os_name, confidence in os_hints:
            if os_name not in unique_hints or confidence > unique_hints[os_name]:
                unique_hints[os_name] = confidence
        
        return list(unique_hints.items()) if unique_hints else [('Не удалось определить по баннерам', 0)]

    def detect_os_by_ports(self):
        windows_ports = {135, 139, 445, 3389, 33890, 5985, 5986}
        linux_ports = {22, 111, 515, 631, 2049, 6000, 6001}
        network_ports = {23, 161, 162, 179}
        mikrotik_ports = {8291, 8728, 8729}
        cisco_ports = {2000, 23, 80, 443, 161, 162}
        
        found_ports = {port for port, _ in self.open_ports}
        
        os_probabilities = []
        
        windows_score = len(windows_ports.intersection(found_ports)) * 3
        linux_score = len(linux_ports.intersection(found_ports)) * 3
        network_score = len(network_ports.intersection(found_ports)) * 4
        mikrotik_score = len(mikrotik_ports.intersection(found_ports)) * 5
        cisco_score = len(cisco_ports.intersection(found_ports)) * 4
        
        if windows_score > 0:
            confidence = min(95, 50 + windows_score)
            os_probabilities.append(('Windows', confidence))
        
        if linux_score > 0:
            confidence = min(95, 50 + linux_score)
            os_probabilities.append(('Linux/Unix', confidence))
        
        if network_score > 0:
            confidence = min(95, 60 + network_score)
            os_probabilities.append(('Сетевое устройство', confidence))
            
        if mikrotik_score > 0:
            confidence = min(98, 80 + mikrotik_score)
            os_probabilities.append(('MikroTik RouterOS', confidence))
        
        if cisco_score > 0:
            confidence = min(95, 70 + cisco_score)
            os_probabilities.append(('Cisco Device', confidence))
        
        if 22 in found_ports and 3389 not in found_ports and 445 not in found_ports:
            os_probabilities.append(('Linux/Unix', 85))
        if 3389 in found_ports or 5985 in found_ports:
            os_probabilities.append(('Windows', 90))
        if 23 in found_ports and len(found_ports) <= 3:
            os_probabilities.append(('Сетевое устройство', 85))
        if 8291 in found_ports:
            os_probabilities.append(('MikroTik RouterOS', 98))
        if 2000 in found_ports:
            os_probabilities.append(('Cisco Device', 95))
        if 22 in found_ports and 3389 in found_ports:
            os_probabilities.append(('Windows (возможно с SSH сервером)', 70))
            os_probabilities.append(('Linux (возможно с xRDP)', 60))
        
        web_ports = {80, 443, 8080, 8443}
        if found_ports.issubset(web_ports) and found_ports:
            os_probabilities.append(('Веб-сервер (вероятно Linux)', 65))
        
        return os_probabilities if os_probabilities else [('Не удалось определить по портам', 0)]

    def analyze_os(self):
        print("\n🖥️  Анализ операционной системы...")
        
        ttl_os = self.detect_os_by_ttl()
        print(f"📡 По TTL: {ttl_os}")
        
        banner_os = self.detect_os_by_banner()
        if banner_os and banner_os[0][1] > 0:
            print(f"🎯 По баннерам:")
            for os_name, confidence in banner_os:
                print(f"   - {os_name} (вероятность: {confidence}%)")
        else:
            print(f"🎯 По баннерам: не удалось определить")
        
        port_os = self.detect_os_by_ports()
        print("📊 По портам:")
        for os_name, confidence in port_os:
            print(f"   - {os_name} (вероятность: {confidence}%)")
        
        all_detections = []
        
        if "Windows" in ttl_os:
            all_detections.append(("Windows", 70))
        if "Linux" in ttl_os or "Unix" in ttl_os:
            all_detections.append(("Linux/Unix", 70))
        if "MikroTik" in ttl_os:
            all_detections.append(("MikroTik RouterOS", 80))
            
        for os_name, confidence in banner_os:
            if confidence > 0:
                all_detections.append((os_name, confidence))
        
        for os_name, confidence in port_os:
            if confidence > 0:
                all_detections.append((os_name, confidence))
        
        os_scores = {}
        for os_name, confidence in all_detections:
            if os_name in os_scores:
                os_scores[os_name].append(confidence)
            else:
                os_scores[os_name] = [confidence]
        
        final_scores = []
        for os_name, scores in os_scores.items():
            avg_confidence = sum(scores) / len(scores)
            final_scores.append((os_name, avg_confidence))
        
        if final_scores:
            final_scores.sort(key=lambda x: x[1], reverse=True)
            most_likely_os = final_scores[0]
            
            self.os_info = {
                'name': most_likely_os[0],
                'confidence': round(most_likely_os[1]),
                'all_detections': final_scores,
                'details': {
                    'ttl': ttl_os,
                    'banners': banner_os,
                    'ports_analysis': port_os
                }
            }
        else:
            self.os_info = {
                'name': 'Неизвестно',
                'confidence': 0,
                'all_detections': [],
                'details': {
                    'ttl': ttl_os,
                    'banners': banner_os,
                    'ports_analysis': port_os
                }
            }
        
        return self.os_info

    def mikrotik_connect(self):
        print("🛠️  Обнаружен MikroTik RouterOS")
        
        web_interface = False
        for port, service in self.open_ports:
            if port in [80, 443, 8080]:
                web_interface = True
                break
        
        if self.is_windows:
            print("\n=== ДЛЯ WINDOWS ===")
            print("1. Используйте WinBox (рекомендуется):")
            print("   - Скачайте WinBox с официального сайта MikroTik")
            print(f"   - Подключитесь к {self.target_ip}:8291")
            print("   - Логин: admin (пароль по умолчанию: пустой)")
            
            if web_interface:
                print("\n2. Используйте веб-интерфейс:")
                url = f"http://{self.target_ip}"
                print(f"   - Откройте {url} в браузере")
                
                launch = input("   🚀 Открыть веб-интерфейс автоматически? (y/n): ").lower()
                if launch == 'y':
                    webbrowser.open(url)
            
            winbox_paths = [
                os.path.join(os.path.expanduser("~"), "Desktop", "winbox.exe"),
                "C:\\Program Files\\MikroTik\\WinBox.exe",
                "winbox.exe"
            ]
            
            winbox_found = False
            for path in winbox_paths:
                if os.path.exists(path):
                    winbox_found = True
                    print(f"\n✅ WinBox обнаружен: {path}")
                    launch_winbox = input("   🚀 Запустить WinBox? (y/n): ").lower()
                    if launch_winbox == 'y':
                        os.system(f'"{path}" {self.target_ip}:8291')
                    break
            
            if not winbox_found:
                print("\n❌ WinBox не обнаружен в системе")
                print("📥 Скачайте с: https://mikrotik.com/download")
                
        else:
            print("\n=== ДЛЯ LINUX ===")
            print("1. Используйте веб-интерфейс (рекомендуется):")
            if web_interface:
                url = f"http://{self.target_ip}"
                print(f"   - Откройте {url} в браузере")
                
                launch = input("   🚀 Открыть веб-интерфейс автоматически? (y/n): ").lower()
                if launch == 'y':
                    webbrowser.open(url)
            else:
                print("   - Веб-интерфейс не обнаружен")
            
            print("\n2. Используйте WinBox через Wine:")
            print("   - Установите Wine: sudo apt install wine")
            print("   - Скачайте WinBox для Windows")
            print(f"   - Запустите: wine winbox.exe {self.target_ip}:8291")
            
            print("\n3. Используйте SSH:")
            print(f"   - ssh admin@{self.target_ip}")
            print("   - Пароль по умолчанию: пустой")
            
            if 22 in [p for p, _ in self.open_ports]:
                ssh_connect = input("   🚀 Подключиться по SSH? (y/n): ").lower()
                if ssh_connect == 'y':
                    os.system(f"ssh admin@{self.target_ip}")
        
        print("\n🔧 Дополнительная информация:")
        print("   - Порт по умолчанию: 8291 (WinBox), 22 (SSH), 80 (WebFig)")
        print("   - Логин по умолчанию: admin")
        
        return True

    def cisco_connect(self):
        print("🌐 Обнаружено Cisco устройство")
        
        web_available = any(port in [80, 443, 2000] for port, _ in self.open_ports)
        ssh_available = 22 in [port for port, _ in self.open_ports]
        telnet_available = 23 in [port for port, _ in self.open_ports]
        
        print("\n🔧 Доступные методы подключения:")
        
        if web_available:
            print("1. Веб-интерфейс")
        if ssh_available:
            print("2. SSH подключение")
        if telnet_available:
            print("3. Telnet подключение")
        
        if not any([web_available, ssh_available, telnet_available]):
            print("❌ Нет доступных методов подключения")
            return False
        

        while True:
            try:
                if web_available and ssh_available and telnet_available:
                    choice = input("\nВыберите метод подключения (1-3): ").strip()
                elif web_available and ssh_available:
                    choice = input("\nВыберите метод подключения (1-2): ").strip()
                elif web_available and telnet_available:
                    choice = input("\nВыберите метод подключения (1-3, пропустив 2): ").strip()
                elif ssh_available and telnet_available:
                    choice = input("\nВыберите метод подключения (2-3): ").strip()
                else:
                    choice = "1" if web_available else "2" if ssh_available else "3"
                
                if choice == "1" and web_available:
                    self.cisco_web_connect()
                    break
                elif choice == "2" and ssh_available:
                    self.cisco_ssh_connect()
                    break
                elif choice == "3" and telnet_available:
                    self.cisco_telnet_connect()
                    break
                else:
                    print("❌ Неверный выбор, попробуйте снова")
            except KeyboardInterrupt:
                print("\n⏹️  Отмена подключения")
                return False
        
        return True
    
    def cisco_web_connect(self):

        print("\n🌐 ПОДКЛЮЧЕНИЕ К ВЕБ-ИНТЕРФЕЙСУ CISCO")
        print("=" * 50)
        
        web_port = None
        protocol = "http"
        
        if 2000 in [port for port, _ in self.open_ports]:
            web_port = 2000
            print("✅ Обнаружен порт 2000 (Cisco Web Interface)")
        elif 443 in [port for port, _ in self.open_ports]:
            web_port = 443
            protocol = "https"
            print("✅ Обнаружен порт 443 (HTTPS)")
        elif 80 in [port for port, _ in self.open_ports]:
            web_port = 80
            print("✅ Обнаружен порт 80 (HTTP)")
        
        if web_port:
            url = f"{protocol}://{self.target_ip}" + (f":{web_port}" if web_port not in [80, 443] else "")
            print(f"🔗 URL: {url}")
            
            
            print(f"\n🔍 Проверяем доступность веб-интерфейса...")
            try:
                import requests
                response = requests.get(url, timeout=5, verify=False)
                if response.status_code == 200:
                    print("✅ Веб-интерфейс доступен")
                else:
                    print(f"⚠️  Веб-интерфейс отвечает с кодом: {response.status_code}")
            except ImportError:
                print("⚠️  Модуль requests не установлен, пропускаем проверку")
            except Exception as e:
                print(f"⚠️  Веб-интерфейс может быть недоступен: {e}")
            
            launch = input(f"\n🚀 Открыть {url} в браузере? (y/n): ").lower()
            if launch == 'y':
                try:
                    webbrowser.open(url)
                    print("✅ Веб-интерфейс открыт в браузере")
                    print("💡 Если страница не загружается, попробуйте:")
                    print("   - Обновить страницу (F5)")
                    print("   - Попробовать другой браузер")
                    print("   - Использовать SSH или Telnet подключение")
                except Exception as e:
                    print(f"❌ Ошибка открытия браузера: {e}")
                    print(f"📝 Откройте браузер вручную и перейдите по адресу: {url}")
            else:
                print(f"📝 Откройте браузер и перейдите по адресу: {url}")
        else:
            print("❌ Веб-интерфейс недоступен")
            print("💡 Попробуйте SSH или Telnet подключение")
    
    def cisco_ssh_connect(self):

        print("\n🔒 SSH ПОДКЛЮЧЕНИЕ К CISCO")
        print("=" * 40)
        

        
        username = input("\nВведите имя пользователя SSH: ").strip()
        if not username:
            username = "admin"
            print(f"Используем логин по умолчанию: {username}")
        
        if self.is_linux:
            cmd = f"ssh {username}@{self.target_ip}"
            print(f"💻 Команда: {cmd}")
            
            launch = input("🚀 Запустить SSH подключение? (y/n): ").lower()
            if launch == 'y':
                print("🔗 Подключаемся по SSH...")
                os.system(cmd)
            else:
                print("📝 Выполните команду вручную:")
                print(f"   {cmd}")
        else:
            print("📝 Для Windows используйте:")
            print(f"   putty {self.target_ip} -ssh")
            print(f"   Или WSL: ssh {username}@{self.target_ip}")
    
    def cisco_telnet_connect(self):
        print("\n📡 TELNET ПОДКЛЮЧЕНИЕ К CISCO")
        print("=" * 40)
        
        
        username = input("\nВведите имя пользователя Telnet: ").strip()
        if not username:
            username = "admin"
            print(f"Используем логин по умолчанию: {username}")
        
        password = input("Введите пароль (или Enter для пустого): ").strip()
        
        print(f"🔗 Подключаемся к {self.target_ip}:23...")
        self.socket_telnet_connect(username, password)
    
    def socket_telnet_connect(self, username='', password=''):
        try:
            print(f"🔐 Подключаемся к Telnet ({self.target_ip}:23)...")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.target_ip, 23))
            
            def read_available_data(sock, timeout=3):
                data = b""
                start_time = time.time()
                sock.setblocking(False)
                
                while time.time() - start_time < timeout:
                    try:
                        ready = select.select([sock], [], [], 0.1)
                        if ready[0]:
                            chunk = sock.recv(1024)
                            if chunk:
                                data += chunk
                            else:
                                break
                    except (BlockingIOError, socket.error):
                        time.sleep(0.1)
                        continue
                
                sock.setblocking(True)
                return data.decode('utf-8', errors='ignore')
            
            welcome = read_available_data(sock, 3)
            if welcome:
                print(f"💬 Приветствие: {welcome[:200]}...")
            
            if not username:
                username = input("Введите имя пользователя Telnet: ")
            sock.send((username + "\r\n").encode())
            
            response = read_available_data(sock, 3)
            if "password" in response.lower() or "пароль" in response.lower():
                if not password:
                    password = input("Введите пароль Telnet: ")
                sock.send((password + "\r\n").encode())
            
            result = read_available_data(sock, 3)
            if "login incorrect" in result.lower() or "authentication failed" in result.lower():
                print("❌ Неверные учетные данные Telnet")
                sock.close()
                return False
            
            print("✅ Telnet подключение установлено!")
            self.interactive_socket_session(sock)
            sock.close()
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подключения Telnet: {e}")
            return False

    def interactive_socket_session(self, sock):
        print("\n💬 Интерактивный режим (для выхода введите 'exit')")
        
        stop_reading = False
        
        def read_thread():
            nonlocal stop_reading
            sock.setblocking(False)
            while not stop_reading:
                try:
                    ready = select.select([sock], [], [], 0.1)
                    if ready[0]:
                        data = sock.recv(1024)
                        if data:
                            print(data.decode('utf-8', errors='ignore'), end='', flush=True)
                    time.sleep(0.05)
                except (BlockingIOError, socket.error):
                    continue
                except:
                    break
        
        reader = threading.Thread(target=read_thread)
        reader.daemon = True
        reader.start()
        
        try:
            while True:
                try:
                    if self.is_windows:
                        try:
                            command = input()
                        except KeyboardInterrupt:
                            break
                    else:
                        command = input()
                    
                    if command.lower() in ['exit', 'quit']:
                        break
                    
                    sock.send((command + "\r\n").encode())
                except KeyboardInterrupt:
                    print("\n⏹️  Выход из сессии...")
                    break
                except Exception as e:
                    print(f"\n❌ Ошибка: {e}")
                    break
        finally:
            stop_reading = True
            sock.close()
            time.sleep(0.2)

    def vnc_connect(self):
        print("🔮 Обнаружен VNC сервер")
        
        vnc_port = 5900
        for port, service in self.open_ports:
            if 'VNC' in service:
                vnc_port = port
                break
        
        display_number = vnc_port - 5900 if vnc_port >= 5900 else 0
        
        if self.is_linux:
            print("\n=== ДЛЯ LINUX ===")
            
            vnc_viewer_installed = False
            try:
                result = subprocess.run(['which', 'vncviewer'], capture_output=True, text=True)
                vnc_viewer_installed = result.returncode == 0
            except:
                pass
            
            if vnc_viewer_installed:
                print("✅ VNC viewer обнаружен в системе")
                cmd = f"vncviewer {self.target_ip}:{display_number}"
                print(f"💻 Команда для подключения: {cmd}")
                
                launch = input("🚀 Запустить VNC подключение автоматически? (y/n): ").lower()
                if launch == 'y':
                    print(f"🔗 Подключаемся к {self.target_ip}:{display_number}...")
                    os.system(cmd)
                else:
                    print("📝 Вы можете запустить подключение позже командой:")
                    print(f"   {cmd}")
            else:
                print("❌ VNC viewer не установлен")
                print("📦 Установите пакет xtightvncviewer или similar:")
                print("   sudo apt install xtightvncviewer")
                print(f"   Затем выполните: vncviewer {self.target_ip}:{display_number}")
                
        elif self.is_windows:
            print("\n=== ДЛЯ WINDOWS ===")
            
            vnc_clients = []
            common_paths = [
                "C:\\Program Files\\TightVNC\\tvnviewer.exe",
                "C:\\Program Files\\RealVNC\\VNC Viewer\\vncviewer.exe",
                "C:\\Program Files\\UltraVNC\\vncviewer.exe"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    vnc_clients.append(path)
            
            if vnc_clients:
                client_name = os.path.basename(vnc_clients[0])
                print(f"✅ Обнаружен VNC клиент: {client_name}")
                
                launch = input("🚀 Запустить VNC подключение автоматически? (y/n): ").lower()
                if launch == 'y':
                    cmd = f'"{vnc_clients[0]}" {self.target_ip}:{display_number}'
                    print(f"🔗 Запускаем: {cmd}")
                    os.system(cmd)
                else:
                    print("📝 Используйте обнаруженный VNC клиент для подключения")
            else:
                print("❌ VNC клиенты не обнаружены")
                print("📦 Рекомендуется установить TightVNC или RealVNC")
        
        return True

    def rdp_connect(self):
        print(f"🖥️  Обнаружен RDP сервер ({self.target_ip}:3389)")
        
        if self.is_windows:
            cmd = f"mstsc /v:{self.target_ip}"
            print(f"🚀 Запускаем встроенный RDP клиент...")
            print(f"💻 Команда: {cmd}")
            os.system(cmd)
            return True
        else:
            print("\n=== ДЛЯ LINUX ===")
            
            xfreerdp_installed = False
            try:
                result = subprocess.run(['which', 'xfreerdp'], capture_output=True, text=True)
                xfreerdp_installed = result.returncode == 0
            except:
                pass
            
            if xfreerdp_installed:
                print("✅ xfreerdp обнаружен в системе")
                
                username = input("Введите имя пользователя RDP (или Enter для пропуска): ")
                password = input("Введите пароль (или Enter для пропуска): ")
                
                cmd_parts = ["xfreerdp", f"/v:{self.target_ip}"]
                if username:
                    cmd_parts.append(f"/u:{username}")
                if password:
                    cmd_parts.append(f"/p:{password}")
                cmd_parts.extend(["+fonts", "/compression", "/gfx"])
                
                cmd = " ".join(cmd_parts)
                print(f"💻 Команда для подключения: {cmd}")
                
                launch = input("🚀 Запустить RDP подключение автоматически? (y/n): ").lower()
                if launch == 'y':
                    print("🔗 Подключаемся...")
                    os.system(cmd)
            else:
                print("❌ xfreerdp не установлен")
                print("📦 Установите xfreerdp:")
                print("   Ubuntu/Debian: sudo apt install freerdp2-x11")
                print("   CentOS/RHEL: sudo yum install freerdp")
                print("   Arch: sudo pacman -S freerdp")
                print(f"   Затем выполните: xfreerdp /v:{self.target_ip} /u:username /p:password")
            
            return True

    def http_connect(self):
        try:
            web_ports = [80, 443, 8080, 8443, 8888]
            successful_urls = []
            
            for port in web_ports:
                if port in [p for p, _ in self.open_ports]:
                    protocol = "https" if port in [443, 8443] else "http"
                    url = f"{protocol}://{self.target_ip}" + (f":{port}" if port not in [80, 443] else "")
                    
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                            sock.settimeout(3)
                            if sock.connect_ex((self.target_ip, port)) == 0:
                                successful_urls.append(url)
                    except:
                        continue
            
            if successful_urls:
                print("🌐 Доступные веб-интерфейсы:")
                for i, url in enumerate(successful_urls, 1):
                    print(f"  {i}. {url}")
                
                if len(successful_urls) == 1:
                    choice = 1
                else:
                    try:
                        choice = int(input("Выберите номер для открытия: "))
                    except:
                        choice = 1
                
                if 1 <= choice <= len(successful_urls):
                    url = successful_urls[choice - 1]
                    print(f"🔗 Открываю: {url}")
                    
                    if self.is_linux:
                        try:
                            webbrowser.open(url)
                            subprocess.run(['xdg-open', url], check=False)
                            time.sleep(2)
                        except Exception as e:
                            print(f"⚠️  Не удалось открыть браузер автоматически: {e}")
                            print("📝 Откройте браузер вручную по указанному URL")
                    else:
                        webbrowser.open(url)
                    
                    return True
            else:
                print("❌ Веб-интерфейсы не обнаружены")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка HTTP подключения: {e}")
            return False

    def ftp_connect(self):
        print("📁 FTP сервер обнаружен")
        
        if self.is_linux:
            print("\n=== ДЛЯ LINUX ===")
            print("📝 Для подключения используйте:")
            print(f"   ftp {self.target_ip}")
            print(f"   lftp {self.target_ip}")
            print("   Или используйте FileZilla")
        else:
            print("\n=== ДЛЯ WINDOWS ===")
            print("📝 Для подключения используйте:")
            print(f"   ftp {self.target_ip}")
            print("   Или используйте FileZilla, WinSCP")
        
        print("👤 Стандартные учетные данные для тестирования: anonymous/anonymous")
        
        if self.is_linux:
            launch = input("🚀 Попробовать автоматическое подключение через ftp? (y/n): ").lower()
            if launch == 'y':
                try:
                    os.system(f"ftp {self.target_ip}")
                except:
                    print("❌ Не удалось запустить ftp клиент")
        
        return True

    def ssh_info(self):
        print("🔒 SSH сервер обнаружен")
        
        if self.is_linux:
            print("\n=== ДЛЯ LINUX ===")
            print("📝 Для подключения используйте:")
            print(f"   ssh username@{self.target_ip}")
            
            launch = input("🚀 Попробовать автоматическое подключение через SSH? (y/n): ").lower()
            if launch == 'y':
                username = input("Введите имя пользователя SSH: ")
                cmd = f"ssh {username}@{self.target_ip}"
                print(f"💻 Запускаем: {cmd}")
                os.system(cmd)
        else:
            print("\n=== ДЛЯ WINDOWS ===")
            print("📝 Для подключения используйте:")
            print(f"   putty {self.target_ip} -ssh")
            print(f"   Используйте WSL: ssh username@{self.target_ip}")
        
        return True

    def generate_beautiful_report(self):
        """Генерация красивого и подробного отчета"""
        scan_duration = round(time.time() - self.start_time, 2)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        report = {
            "Отчет о сетевом сканировании": {
                "Основная информация": {
                    "Целевой хост": self.target_ip,
                    "Дата и время сканирования": timestamp,
                    "Длительность сканирования": f"{scan_duration} сек.",
                    "Операционная система сканера": f"{platform.system()} {platform.release()}",
                    "Общее количество проверенных портов": 25
                },
                "Результаты сканирования портов": {
                    "Найдено открытых портов": len(self.open_ports),
                    "Открытые порты": [
                        {
                            "Порт": port,
                            "Служба": service,
                            "Статус": "Открыт",
                            "Рекомендация": self.get_port_recommendation(port)
                        }
                        for port, service in self.open_ports
                    ]
                },
                "Анализ операционной системы целевого хоста": {
                    "Предполагаемая ОС": self.os_info.get('name', 'Неизвестно'),
                    "Уровень уверенности": f"{self.os_info.get('confidence', 0)}%",
                    "Все методы определения": [
                        f"{os_name} ({confidence}%)" 
                        for os_name, confidence in self.os_info.get('all_detections', [])
                    ],
                    "Детали анализа": {
                        "По TTL": self.os_info.get('details', {}).get('ttl', 'N/A'),
                        "По баннерам": self.os_info.get('details', {}).get('banners', []),
                        "По портам": self.os_info.get('details', {}).get('ports_analysis', [])
                    }
                }
            }
        }
        
        return report, report_date

    def save_beautiful_report(self):
        try:
            report, report_date = self.generate_beautiful_report()
            
            safe_ip = self.target_ip.replace('.', '_')
            filename = f"Сетевой_аудит_{safe_ip}_{report_date}.json"
            
            if self.is_windows:
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                if os.path.exists(desktop_path):
                    filename = os.path.join(desktop_path, filename)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, sort_keys=True)
            
            txt_filename = filename.replace('.json', '.txt')
            self.create_text_report(txt_filename, report)
            
            print(f"\n💾 Отчеты сохранены:")
            print(f"   📄 JSON: {filename}")
            print(f"   📝 TXT:  {txt_filename}")
            
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения отчета: {e}")
            return False

    def create_text_report(self, filename, report):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("             ОТЧЕТ О СЕТЕВОМ СКАНИРОВАНИИ\n")
                f.write("=" * 70 + "\n\n")
                
                main_info = report["Отчет о сетевом сканировании"]["Основная информация"]
                f.write("ОСНОВНАЯ ИНФОРМАЦИЯ:\n")
                f.write("-" * 40 + "\n")
                for key, value in main_info.items():
                    f.write(f"  {key}: {value}\n")
                
                f.write("\nРЕЗУЛЬТАТЫ СКАНИРОВАНИЯ ПОРТОВ:\n")
                f.write("-" * 40 + "\n")
                ports_info = report["Отчет о сетевом сканировании"]["Результаты сканирования портов"]
                f.write(f"  Открыто портов: {ports_info['Найдено открытых портов']}\n")
                for port_info in ports_info["Открытые порты"]:
                    f.write(f"  • Порт {port_info['Порт']} ({port_info['Служба']}): {port_info['Рекомендация']}\n")
                
                f.write("\nАНАЛИЗ ОПЕРАЦИОННОЙ СИСТЕМЫ:\n")
                f.write("-" * 40 + "\n")
                os_info = report["Отчет о сетевом сканировании"]["Анализ операционной системы целевого хоста"]
                f.write(f"  Предполагаемая ОС: {os_info['Предполагаемая ОС']}\n")
                f.write(f"  Уверенность: {os_info['Уровень уверенности']}\n")
                
                f.write("\nРЕКОМЕНДАЦИИ ПО ПОДКЛЮЧЕНИЮ:\n")
                f.write("-" * 40 + "\n")
                for rec in report["Отчет о сетевом сканировании"]["Рекомендации по подключению"]:
                    if isinstance(rec, dict):
                        f.write(f"  {rec['Протокол']}:\n")
                        f.write(f"    • {rec['Рекомендация']}\n")
                        if 'Команда' in rec:
                            f.write(f"    • Команда: {rec['Команда']}\n")
                        if 'Автозапуск' in rec:
                            f.write(f"    • {rec['Автозапуск']}\n")
                    else:
                        f.write(f"  • {rec}\n")
                
                
                f.write("\n" + "=" * 70 + "\n")
                f.write("Отчет сгенерирован автоматически\n")
                f.write("=" * 70 + "\n")
                
        except Exception as e:
            print(f"❌ Ошибка создания текстового отчета: {e}")

    def generate_connection_recommendations(self):
        recommendations = []
        
        for port, service in self.open_ports:
            if port == 22:
                if self.is_linux:
                    recommendations.append({
                        "Протокол": "SSH",
                        "Рекомендация": "Наиболее безопасный метод удаленного доступа",
                        "Команда": f"ssh username@{self.target_ip}",
                        "Автозапуск": "Доступен через меню программы"
                    })
                else:
                    recommendations.append({
                        "Протокол": "SSH", 
                        "Рекомендация": "Используйте Putty или WSL",
                        "Команда": f"putty {self.target_ip} -ssh"
                    })
                    
            elif port == 3389:
                if self.is_windows:
                    recommendations.append({
                        "Протокол": "RDP",
                        "Рекомендация": "Встроенный клиент Windows",
                        "Команда": f"mstsc /v:{self.target_ip}",
                        "Автозапуск": "Доступен через меню программы"
                    })
                else:
                    recommendations.append({
                        "Протокол": "RDP",
                        "Рекомендация": "Используйте xfreerdp",
                        "Команда": f"xfreerdp /v:{self.target_ip} /u:username /p:password",
                        "Автозапуск": "Доступен через меню программы"
                    })
                    
            elif port == 5900:
                if self.is_linux:
                    recommendations.append({
                        "Протокол": "VNC",
                        "Рекомендация": "Используйте vncviewer",
                        "Команда": f"vncviewer {self.target_ip}:0",
                        "Автозапуск": "Доступен через меню программы"
                    })
                else:
                    recommendations.append({
                        "Протокол": "VNC",
                        "Рекомендация": "Используйте TightVNC или RealVNC",
                        "Действие": f"Подключитесь к {self.target_ip}:0"
                    })
                    
            elif port in [80, 443]:
                recommendations.append({
                    "Протокол": "HTTP/HTTPS",
                    "Рекомендация": "Веб-интерфейс управления",
                    "Действие": f"Откройте браузер: http{'s' if port == 443 else ''}://{self.target_ip}",
                    "Автозапуск": "Доступен через меню программы"
                })
        
        return recommendations if recommendations else ["Прямое подключение не рекомендуется"]


    def suggest_connection_methods(self):
        protocol_handlers = {
            21: ('FTP', self.ftp_connect),
            22: ('SSH', self.ssh_info),
            23: ('Telnet', self.socket_telnet_connect),
            80: ('HTTP', self.http_connect),
            443: ('HTTPS', self.http_connect),
            3389: ('RDP', self.rdp_connect),
            33890: ('RDP-Alt', self.rdp_connect),
            5900: ('VNC', self.vnc_connect),
            5901: ('VNC-1', self.vnc_connect),
            5902: ('VNC-2', self.vnc_connect),
            8080: ('HTTP-Alt', self.http_connect),
            8443: ('HTTPS-Alt', self.http_connect),
            8291: ('MikroTik', self.mikrotik_connect),
            2000: ('Cisco', self.cisco_connect)
        }
        
        available_methods = []
        for port, service in self.open_ports:
            if port in protocol_handlers:
                available_methods.append((port, protocol_handlers[port]))
        
        return available_methods

    def check_host_availability(self):
        print("🔍 Проверяем доступность хоста...")
        
        if self.ping_host():
            print("✅ Хост доступен (ping успешен)")
            return True
        else:
            print("⚠️  Хост не отвечает на ping")
            
            test_ports = [80, 443, 22, 23, 3389, 8291, 2000]
            for port in test_ports:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(2)
                        if sock.connect_ex((self.target_ip, port)) == 0:
                            print(f"✅ Хост доступен через порт {port}")
                            return True
                except:
                    continue
            
            print("❌ Хост недоступен по ping и основным портам")
            continue_anyway = input("Продолжить сканирование? (y/n): ").lower()
            return continue_anyway == 'y'

    def advanced_manual_connection(self):
        print("\n🔧 РАСШИРЕННЫЙ РУЧНОЙ ВЫБОР ПОДКЛЮЧЕНИЯ")
        print("=" * 60)
        
        print("📊 Открытые порты:")
        for i, (port, service) in enumerate(self.open_ports, 1):
            print(f"  {i}. Порт {port} ({service})")
        
        print("\n💡 Дополнительные опции:")
        print("  A. Произвольный порт (вручную)")
        print("  B. Полное сканирование портов (1-65535)")
        print("  C. Проверить конкретный порт")
        print("  D. Использовать альтернативный метод")
        print("  E. Назад к основному меню")
        
        choice = input("\nВыберите опцию: ").strip().upper()
        
        if choice == 'A':
            self.custom_port_connection()
        elif choice == 'B':
            self.full_port_scan()
        elif choice == 'C':
            self.check_specific_port()
        elif choice == 'D':
            self.alternative_connection_methods()
        elif choice == 'E':
            return False
        else:
            try:
                port_index = int(choice) - 1
                if 0 <= port_index < len(self.open_ports):
                    port, service = self.open_ports[port_index]
                    self.manual_port_connection(port, service)
                else:
                    print("❌ Неверный выбор")
            except ValueError:
                print("❌ Неверный ввод")
        
        return True

    def custom_port_connection(self):
        try:
            port = int(input("Введите номер порта: "))
            if 1 <= port <= 65535:
                print(f"🔍 Проверяем порт {port}...")
                result = self.check_port(port)
                if result[1]:
                    print(f"✅ Порт {port} открыт")
                    service = self.get_service_name(port)
                    print(f"💼 Предполагаемая служба: {service}")
                    self.manual_port_connection(port, service)
                else:
                    print(f"❌ Порт {port} закрыт или недоступен")
            else:
                print("❌ Неверный номер порта (1-65535)")
        except ValueError:
            print("❌ Введите число")

    def get_service_name(self, port):
        try:
            return socket.getservbyport(port)
        except:
            common_services = {
                21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
                53: 'DNS', 80: 'HTTP', 110: 'POP3', 443: 'HTTPS',
                3389: 'RDP', 5900: 'VNC', 8291: 'MikroTik WinBox'
            }
            return common_services.get(port, 'Unknown')

    def manual_port_connection(self, port, service):
        print(f"🔗 Подключение к порту {port} ({service})")
        
        if port in [80, 443, 8080, 8443, 8291]:
            protocol = "https" if port in [443, 8443] else "http"
            url = f"{protocol}://{self.target_ip}" + (f":{port}" if port not in [80, 443] else "")
            print(f"🌐 URL: {url}")
            
            launch = input("Открыть в браузере? (y/n): ").lower()
            if launch == 'y':
                webbrowser.open(url)
                
        elif port == 22:
            if self.is_linux:
                username = input("Введите имя пользователя SSH: ")
                cmd = f"ssh {username}@{self.target_ip}"
                print(f"💻 Команда: {cmd}")
                launch = input("Запустить? (y/n): ").lower()
                if launch == 'y':
                    os.system(cmd)
            else:
                print("📝 Используйте Putty или другой SSH клиент")
                
        elif port == 3389:
            if self.is_windows:
                cmd = f"mstsc /v:{self.target_ip}"
                print(f"💻 Команда: {cmd}")
                launch = input("Запустить? (y/n): ").lower()
                if launch == 'y':
                    os.system(cmd)
            else:
                print("📝 Используйте xfreerdp или rdesktop")
                
        elif port == 5900:
            self.vnc_connect()
            
        elif port == 8291:
            self.mikrotik_connect()
            
        else:
            print(f"📝 Для подключения к порту {port} используйте соответствующий клиент")
            print(f"💡 Служба: {service}")

    def full_port_scan(self):
        print("🔍 ЗАПУСК ПОЛНОГО СКАНИРОВАНИЯ ПОРТОВ (1-65535)")
        print("⚠️  Это может занять значительное время!")
        
        confirm = input("Продолжить? (y/n): ").lower()
        if confirm != 'y':
            return
        
        print("Сканирование запущено...")
        start_time = time.time()
        
        common_ports = list(range(1, 1001)) + [1433, 1521, 3306, 5432, 5900, 5901, 5902, 8080, 8443, 33890, 5985, 5986, 8291, 2000]
        
        open_ports = []
        with ThreadPoolExecutor(max_workers=200) as executor:
            results = executor.map(self.check_port, common_ports)
            
            for port, is_open in results:
                if is_open and port not in [p for p, _ in self.open_ports]:
                    service = self.get_service_name(port)
                    open_ports.append((port, service))
                    print(f"✅ Найден новый порт {port} ({service})")
        
        if open_ports:
            self.open_ports.extend(open_ports)
            print(f"🎯 Найдено {len(open_ports)} дополнительных открытых портов")
        else:
            print("❌ Дополнительные открытые порты не найдены")
        
        duration = time.time() - start_time
        print(f"⏱️  Сканирование завершено за {duration:.2f} секунд")

    def check_specific_port(self):
        try:
            port = int(input("Введите номер порта для проверки: "))
            if 1 <= port <= 65535:
                print(f"🔍 Проверяем порт {port}...")
                result = self.check_port(port)
                if result[1]:
                    service = self.get_service_name(port)
                    print(f"✅ Порт {port} открыт ({service})")
                    
                    if (port, service) not in self.open_ports:
                        add = input("Добавить в список доступных портов? (y/n): ").lower()
                        if add == 'y':
                            self.open_ports.append((port, service))
                            print("✅ Порт добавлен")
                else:
                    print(f"❌ Порт {port} закрыт")
            else:
                print("❌ Неверный номер порта")
        except ValueError:
            print("❌ Введите число")

    def alternative_connection_methods(self):
        print("\n🔧 АЛЬТЕРНАТИВНЫЕ МЕТОДЫ ПОДКЛЮЧЕНИЯ")
        print("=" * 50)
        
        print("1. Подключение через стандартные утилиты:")
        print(f"   - telnet {self.target_ip} [порт]")
        print(f"   - nc {self.target_ip} [порт]")
        print(f"   - curl http://{self.target_ip}:[порт]")
        
        print("\n2. Специализированные методы:")
        print("   - SNMP (порты 161/162)")
        print("   - IPMI (порт 623)")
        print("   - Сетевые протоколы (ICMP, ARP)")
        
        print("\n3. Собственные скрипты:")
        print("   - Python сокеты")
        print("   - PowerShell Remoting")
        print("   - WMI (Windows)")
        
        method = input("\nВыберите метод для подробной информации (1-3 или 0 для отмены): ")
        
        if method == '1':
            print("\n📝 Примеры использования стандартных утилит:")
            print(f"  telnet {self.target_ip} 23")
            print(f"  nc -v {self.target_ip} 80")
            print(f"  curl -I http://{self.target_ip}")
            
        elif method == '2':
            print("\n📝 Специализированные протоколы:")
            print("  SNMP: snmpwalk -v2c -c public {self.target_ip}")
            print("  IPMI: ipmitool -I lan -H {self.target_ip} -U admin -P password power status")
            
        elif method == '3':
            print("\n📝 Программные методы:")
            print("  Python: import socket; s = socket.socket(); s.connect(('{self.target_ip}', port))")
            print("  PowerShell: Enter-PSSession -ComputerName {self.target_ip}")

    def auto_connect(self):
        """Автоматическое подключение по доступным протоколам"""
        print("\n🚀 АВТОМАТИЧЕСКОЕ ПОДКЛЮЧЕНИЕ")
        print("=" * 60)
        
        if not self.check_host_availability():
            return
        
        open_ports = self.scan_common_ports()
        
        if not open_ports:
            print("❌ Нет открытых портов для подключения")
            expand = input("Выполнить расширенное сканирование? (y/n): ").lower()
            if expand == 'y':
                self.full_port_scan()
                open_ports = self.open_ports
                if not open_ports:
                    return
        
        os_info = self.analyze_os()
        print(f"\n🎯 Предполагаемая ОС: {os_info.get('name', 'Неизвестно')}")
        print(f"📊 Уверенность: {os_info.get('confidence', 0)}%")
        
        methods = self.suggest_connection_methods()
        
        if not methods:
            print("❌ Нет доступных методов подключения")
            manual = input("Перейти к ручному выбору портов? (y/n): ").lower()
            if manual == 'y':
                self.advanced_manual_connection()
            return
        
        print(f"\n💡 Доступные методы подключения:")
        for i, (port, (name, handler)) in enumerate(methods, 1):
            print(f"  {i}. {name} (порт {port})")
        
        preferred_order = [80, 443, 2000, 8291, 23, 3389, 5900, 22]
        
        for protocol in preferred_order:
            for port, (name, handler) in methods:
                if port == protocol:
                    print(f"\n🔗 Пытаемся подключиться через {name}...")
                    success = handler()
                    if success:
                        print(f"✅ Успешно подключено через {name}")
                        
                        continue_connect = input("\n🔄 Попробовать другой метод подключения? (y/n): ").lower()
                        if continue_connect == 'y':
                            self.advanced_manual_connection()
                        return
        
        print("\n❌ Автоматическое подключение не удалось")
        self.manual_connection_choice(methods)

    def manual_connection_choice(self, methods):
        """Ручной выбор метода подключения"""
        print(f"\n🤖 РУЧНОЙ ВЫБОР МЕТОДА ПОДКЛЮЧЕНИЯ")
        print("Выберите метод подключения:")
        
        for i, (port, (name, handler)) in enumerate(methods, 1):
            print(f"  {i}. {name} (порт {port})")
        
        print(f"  {len(methods) + 1}. 📋 Расширенные опции")
        print(f"  {len(methods) + 2}. ❌ Выход")
        
        try:
            choice = input("\nВаш выбор: ").strip()
            
            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(methods):
                    port, (name, handler) = methods[choice_num - 1]
                    print(f"🔗 Подключаемся через {name}...")
                    handler()
                elif choice_num == len(methods) + 1:
                    self.advanced_manual_connection()
                elif choice_num == len(methods) + 2:
                    return
                else:
                    print("❌ Неверный выбор")
            else:
                print("❌ Введите число")
                
        except ValueError:
            print("❌ Ошибка ввода")

def clear_screen():
    if platform.system().lower() == "windows":
        os.system('cls')
    else:
        os.system('clear')

def main():
    while True:
        clear_screen()
        print("🤖 SyharikDP")
        print("=" * 60)
        print(f"💻 Текущая ОС: {platform.system()} {platform.release()}")
        print("=" * 60)
        
        target_ip = input("Введите IP-адрес для подключения: ").strip()
        
        manager = CrossPlatformConnectionManager(target_ip)
        
        if not manager.validate_ip():
            print("❌ Неверный формат IP-адреса")
            input("\nНажмите Enter, чтобы продолжить...")
            continue
        
        manager.auto_connect()
        
        save_report = input("\n💾 Сохранить подробный отчет о сканировании? (y/n): ").lower()
        if save_report == 'y':
            try:
                manager.save_beautiful_report()
            except AttributeError:
                print("⚠️  Сохранение красивого отчета недоступно в этой версии.")
        
        again = input("\n🔁 Начать заново с другим IP? (y/n): ").lower()
        if again != 'y':
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
