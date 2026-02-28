from pymongo import MongoClient
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from api.config import Config
import secrets
import base64
import subprocess
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HostSystemctlManager:
    """Менеджер для работы с systemctl на хосте через chroot с поддержкой D-Bus"""
    
    @staticmethod
    def systemctl(action, service_name=None):
        """Выполняет systemctl команду на хосте через chroot"""
        try:
            # Проверяем, смонтирована ли корневая ФС хоста
            if not os.path.exists('/host'):
                logger.error("/host directory not mounted")
                return {
                    'success': False,
                    'error': '/host directory not mounted. Please mount host root with -v /:/host:ro',
                    'returncode': 1
                }
            
            # Путь к systemctl на хосте
            systemctl_path = '/usr/bin/systemctl'
            
            # Проверяем наличие D-Bus сокетов
            dbus_socket_paths = [
                '/run/systemd/private',
                '/run/dbus/system_bus_socket',
                '/var/run/dbus/system_bus_socket'
            ]
            
            dbus_available = False
            for socket_path in dbus_socket_paths:
                check_cmd = ['chroot', '/host', 'test', '-e', socket_path]
                check_result = subprocess.run(check_cmd, capture_output=True)
                if check_result.returncode == 0:
                    dbus_available = True
                    logger.info(f"D-Bus socket found at: {socket_path}")
                    break
            
            if not dbus_available:
                logger.warning("No D-Bus sockets found, trying alternative methods")
            
            # Формируем команду
            if action == 'daemon-reload':
                cmd = ['chroot', '/host', systemctl_path, 'daemon-reload']
            elif service_name:
                cmd = ['chroot', '/host', systemctl_path, action, service_name]
            else:
                cmd = ['chroot', '/host', systemctl_path, action]
            
            logger.info(f"Executing on host: {' '.join(cmd)}")
            
            # Добавляем переменные окружения для D-Bus
            env = os.environ.copy()
            
            # Пробуем разные возможные пути к D-Bus сокету
            dbus_addresses = [
                'unix:path=/host/run/systemd/private',
                'unix:path=/host/run/dbus/system_bus_socket',
                'unix:path=/host/var/run/dbus/system_bus_socket'
            ]
            
            for addr in dbus_addresses:
                if os.path.exists(addr.replace('/host', '')):
                    env['DBUS_SYSTEM_BUS_ADDRESS'] = addr
                    logger.info(f"Setting DBUS_SYSTEM_BUS_ADDRESS={addr}")
                    break
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                logger.info(f"Command successful: {action} {service_name if service_name else ''}")
                return {
                    'success': True,
                    'stdout': result.stdout.strip(),
                    'stderr': result.stderr.strip(),
                    'returncode': result.returncode
                }
            else:
                logger.warning(f"Command failed with code {result.returncode}: {result.stderr}")
                
                # Если ошибка связана с D-Bus, пробуем альтернативные методы
                if "Failed to connect to bus" in result.stderr:
                    logger.info("Trying alternative method 1: Using nsenter without D-Bus...")
                    
                    # Метод 1: nsenter (может работать без D-Bus в некоторых случаях)
                    try:
                        if action == 'daemon-reload':
                            alt_cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 
                                      'sh', '-c', 'systemctl daemon-reload']
                        elif service_name:
                            alt_cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 
                                      'sh', '-c', f'systemctl {action} {service_name}']
                        else:
                            alt_cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 
                                      'sh', '-c', f'systemctl {action}']
                        
                        logger.info(f"Trying nsenter: {' '.join(alt_cmd)}")
                        alt_result = subprocess.run(
                            alt_cmd,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        if alt_result.returncode == 0:
                            logger.info("nsenter method successful")
                            return {
                                'success': True,
                                'stdout': alt_result.stdout.strip(),
                                'stderr': alt_result.stderr.strip(),
                                'returncode': alt_result.returncode
                            }
                    except Exception as e:
                        logger.warning(f"nsenter method failed: {e}")
                    
                    logger.info("Trying alternative method 2: Direct service file manipulation...")
                    
                    # Метод 2: Прямая манипуляция службой через файлы
                    if action in ['start', 'stop', 'restart']:
                        try:
                            if action == 'start':
                                # Для запуска используем systemctl с --no-block
                                start_cmd = ['chroot', '/host', systemctl_path, 'start', '--no-block', service_name]
                                start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
                                if start_result.returncode == 0:
                                    return {
                                        'success': True,
                                        'stdout': start_result.stdout,
                                        'stderr': start_result.stderr,
                                        'returncode': 0
                                    }
                            elif action == 'stop':
                                # Для остановки используем kill
                                pid_cmd = ['chroot', '/host', 'pgrep', '-f', f'ss-server.*{service_name}']
                                pid_result = subprocess.run(pid_cmd, capture_output=True, text=True)
                                if pid_result.returncode == 0 and pid_result.stdout.strip():
                                    pid = pid_result.stdout.strip().split('\n')[0]
                                    kill_cmd = ['chroot', '/host', 'kill', pid]
                                    subprocess.run(kill_cmd, capture_output=True)
                                    return {'success': True, 'message': f'Sent kill signal to PID {pid}'}
                        except Exception as e:
                            logger.warning(f"Direct manipulation failed: {e}")
                
                return {
                    'success': False,
                    'stdout': result.stdout.strip(),
                    'stderr': result.stderr.strip(),
                    'returncode': result.returncode
                }
                
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return {
                'success': False,
                'error': f'Command not found: {e}',
                'returncode': 127
            }
        except subprocess.TimeoutExpired:
            logger.error("Command timed out")
            return {
                'success': False,
                'error': 'Command timed out',
                'returncode': 124
            }
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'returncode': 1
            }
    
    @staticmethod
    def check_service_status(service_name):
        """Проверяет статус службы на хосте"""
        try:
            # Проверяем существование файла службы
            service_file = f"/host/etc/systemd/system/{service_name}"
            if not os.path.exists(service_file):
                return {
                    'success': True,
                    'exists': False,
                    'active': False,
                    'enabled': False,
                    'status': 'not_found'
                }
            
            # Проверяем активность через pgrep
            # Извлекаем username из имени сервиса: shadowsocks-murzik.service -> murzik
            username = service_name.replace("shadowsocks-", "").replace(".service", "")
            
            # Для admin используем config.json, для других - config-{username}.json
            if username == "shadowsocks":
                config_pattern = "config.json"
            else:
                config_pattern = f"config-{username}.json"
            
            pgrep_cmd = ['chroot', '/host', 'pgrep', '-f', f'ss-server.*{config_pattern}']
            pgrep_result = subprocess.run(pgrep_cmd, capture_output=True, text=True)
            is_active = pgrep_result.returncode == 0
            
            # Проверяем включенность через symlink
            wants_dir = f"/host/etc/systemd/system/multi-user.target.wants/{service_name}"
            is_enabled = os.path.exists(wants_dir)
            
            # Получаем статус через systemctl если возможно
            status_output = ""
            status_result = HostSystemctlManager.systemctl('status', service_name)
            if status_result['success']:
                status_output = status_result['stdout']
            
            return {
                'success': True,
                'exists': True,
                'active': is_active,
                'enabled': is_enabled,
                'status': 'active' if is_active else 'inactive',
                'status_output': status_output,
                'pid': pgrep_result.stdout.strip() if is_active else None
            }
            
        except Exception as e:
            logger.error(f"Error checking service status: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class ShadowsocksServiceManager:
    def __init__(self):
        self.config_dir = Path("/etc/shadowsocks-libev")
        self.service_dir = Path("/etc/systemd/system")
        self.admin_service = "shadowsocks.service"
        
        # Создаем директории если их нет
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.service_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Config directory: {self.config_dir}")
            logger.info(f"Service directory: {self.service_dir}")
        except Exception as e:
            logger.error(f"Error creating directories: {e}")
        
        # Конфигурация для admin
        self.admin_config = {
            "server": "0.0.0.0",
            "port_password": {},
            "method": Config.SS_METHOD,
            "timeout": 300,
            "fast_open": False,
            "mode": "tcp_and_udp"
        }
        
        # Шаблон для индивидуальных служб
        self.single_user_template = {
            "server": "0.0.0.0",
            "server_port": 8388,
            "password": "",
            "method": Config.SS_METHOD,
            "timeout": 300,
            "fast_open": False,
            "mode": "tcp_and_udp"
        }
    
    def manage_service(self, service_name: str, action: str) -> Dict:
        """Управляет службой на хосте"""
        try:
            logger.info(f"Managing service {service_name} with action {action}")
            
            # Проверяем существование файла службы
            service_path = self.service_dir / service_name
            if not service_path.exists():
                logger.error(f"Service file not found: {service_path}")
                return {
                    "success": False,
                    "error": f"Service file {service_name} not found"
                }
            
            # Выполняем действие
            if action in ['start', 'stop', 'restart', 'enable', 'disable', 'reload']:
                result = HostSystemctlManager.systemctl(action, service_name)
            elif action == 'status':
                return self.get_service_status(service_name)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}"
                }
            
            # Если команда не удалась, пробуем перезагрузить systemd и повторить
            if not result['success'] and action in ['start', 'stop', 'restart']:
                logger.warning(f"First attempt failed, reloading systemd and retrying...")
                HostSystemctlManager.systemctl('daemon-reload')
                time.sleep(2)
                result = HostSystemctlManager.systemctl(action, service_name)
            
            return {
                "success": result['success'],
                "service": service_name,
                "action": action,
                "message": f"Service {service_name} {action}ed",
                "error": result.get('stderr') or result.get('error'),
                "output": result.get('stdout', '')
            }
            
        except Exception as e:
            logger.error(f"Error managing service {service_name}: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def get_service_status(self, service_name: str) -> Dict:
        """Получает статус службы на хосте"""
        try:
            # Проверяем существование файла службы
            service_path = self.service_dir / service_name
            exists = service_path.exists()
            
            if not exists:
                logger.warning(f"Service file not found: {service_path}")
                return {
                    "success": True,
                    "exists": False,
                    "active": False,
                    "enabled": False,
                    "status": "not_found"
                }
            
            # Получаем статус
            status_result = HostSystemctlManager.check_service_status(service_name)
            
            if not status_result['success']:
                return {
                    "success": False,
                    "error": status_result.get('error', 'Failed to get service status'),
                    "exists": True
                }
            
            return {
                "success": True,
                "exists": True,
                "service_name": service_name,
                "active": status_result.get('active', False),
                "enabled": status_result.get('enabled', False),
                "status": status_result.get('status', 'unknown'),
                "status_output": status_result.get('status_output', ''),
                "pid": status_result.get('pid')
            }
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_admin_service(self, admin_port=8388, admin_password=None):
        """Настраивает основную службу admin"""
        try:
            if admin_password is None:
                admin_password = secrets.token_urlsafe(12)
            
            # Создаем конфиг для admin
            admin_config = self.admin_config.copy()
            admin_config["port_password"] = {str(admin_port): admin_password}
            
            # Сохраняем конфиг admin
            admin_config_path = self.config_dir / "config.json"
            
            with open(admin_config_path, 'w') as f:
                json.dump(admin_config, f, indent=2)
            
            os.chmod(admin_config_path, 0o644)
            
            # Создаем службу admin
            service_content = f"""[Unit]
Description=Shadowsocks Server (Multi-user)
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/bin/ss-server -c {admin_config_path} -u
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10s
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""
            
            service_path = self.service_dir / self.admin_service
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            os.chmod(service_path, 0o644)
            
            logger.info(f"✓ Admin service created at {service_path}")
            
            # Перезагружаем systemd
            HostSystemctlManager.systemctl('daemon-reload')
            time.sleep(2)
            
            # Включаем и запускаем службу
            enable_result = self.manage_service(self.admin_service, "enable")
            start_result = self.manage_service(self.admin_service, "start")
            
            return {
                "success": True,
                "admin_port": admin_port,
                "admin_password": admin_password,
                "service_name": self.admin_service,
                "config_path": str(admin_config_path),
                "service_enabled": enable_result.get('success', False),
                "service_started": start_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"Error setting up admin service: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def create_user_service(self, user_data: Dict) -> Dict:
        """Создает службу для пользователя"""
        try:
            username = user_data.get('username')
            port = user_data.get('port')
            password = user_data.get('password')
            method = user_data.get('method', Config.SS_METHOD)
            
            if not all([username, port, password]):
                return {"success": False, "error": "Missing required user data"}
            
            logger.info(f"Creating service for user: {username}, port: {port}")
            
            # Создаем конфиг
            user_config = self.single_user_template.copy()
            user_config.update({
                "server_port": port,
                "password": password,
                "method": method
            })
            
            config_path = self.config_dir / f"config-{username}.json"
            with open(config_path, 'w') as f:
                json.dump(user_config, f, indent=2)
            os.chmod(config_path, 0o644)
            
            # Создаем службу
            service_name = f"shadowsocks-{username}.service"
            service_path = self.service_dir / service_name
            
            service_content = f"""[Unit]
Description=Shadowsocks Server for {username} (Port: {port})
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/bin/ss-server -c "{config_path}" -u
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10s
LimitNOFILE=32768

[Install]
WantedBy=multi-user.target
"""
            
            with open(service_path, 'w') as f:
                f.write(service_content)
            os.chmod(service_path, 0o644)
            
            logger.info(f"✓ Created service: {service_name}")
            
            # Перезагружаем systemd
            HostSystemctlManager.systemctl('daemon-reload')
            time.sleep(2)
            
            # Включаем и запускаем
            enable_result = self.manage_service(service_name, "enable")
            start_result = self.manage_service(service_name, "start")
            
            return {
                "success": True,
                "username": username,
                "port": port,
                "service_name": service_name,
                "service_enabled": enable_result.get('success', False),
                "service_started": start_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"Error creating user service: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def delete_user_service(self, username: str) -> Dict:
        """Удаляет службу пользователя"""
        try:
            service_name = f"shadowsocks-{username}.service"
            config_path = self.config_dir / f"config-{username}.json"
            
            logger.info(f"Deleting service for user: {username}")
            
            # Останавливаем и отключаем
            self.manage_service(service_name, "stop")
            self.manage_service(service_name, "disable")
            
            # Удаляем файлы
            service_removed = False
            service_file = self.service_dir / service_name
            if service_file.exists():
                service_file.unlink()
                service_removed = True
                logger.info(f"✓ Removed service file: {service_file}")
            
            config_removed = False
            if config_path.exists():
                config_path.unlink()
                config_removed = True
                logger.info(f"✓ Removed config file: {config_path}")
            
            # Перезагружаем systemd
            HostSystemctlManager.systemctl('daemon-reload')
            
            return {
                "success": True,
                "username": username,
                "service_removed": service_removed,
                "config_removed": config_removed
            }
            
        except Exception as e:
            logger.error(f"Error deleting user service: {e}")
            return {"success": False, "error": str(e)}
    
    def update_admin_config(self, users: List[Dict]) -> Dict:
        """Обновляет конфиг admin с портами всех пользователей"""
        try:
            admin_config_path = self.config_dir / "config.json"
            
            if not admin_config_path.exists():
                config = self.admin_config.copy()
            else:
                with open(admin_config_path, 'r') as f:
                    config = json.load(f)
            
            # Собираем порты всех активных пользователей
            port_password = {}
            for user in users:
                if user.get('enable', True):
                    port = user.get('port')
                    password = user.get('password')
                    if port and password:
                        port_password[str(port)] = password
            
            config["port_password"] = port_password
            
            with open(admin_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            os.chmod(admin_config_path, 0o644)
            
            logger.info(f"✓ Admin config updated with {len(port_password)} users")
            
            return {
                "success": True,
                "port_count": len(port_password),
                "ports": list(port_password.keys()),
                "config_path": str(admin_config_path)
            }
            
        except Exception as e:
            logger.error(f"Error updating admin config: {e}")
            return {"success": False, "error": str(e)}
    
    def list_all_services(self) -> List[str]:
        """Возвращает список всех служб"""
        try:
            services = []
            for service_file in self.service_dir.glob("shadowsocks*.service"):
                services.append(service_file.name)
            logger.info(f"Found {len(services)} services: {services}")
            return sorted(services)
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return []


class ShadowsocksConfigManager:
    def __init__(self):
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[Config.MONGO_DB]
            self.users_collection = self.db['users']
            self.service_manager = ShadowsocksServiceManager()
            logger.info("✓ Config manager initialized")
        except Exception as e:
            logger.error(f"✗ Config manager connection failed: {e}")
            self.users_collection = None
            self.service_manager = None
    
    def initialize_admin(self, admin_port=8388) -> Dict:
        """Инициализирует admin пользователя и службу"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            # Проверяем, есть ли уже admin
            existing_admin = self.users_collection.find_one({"username": "admin"})
            
            if existing_admin:
                logger.info("✓ Admin user already exists")
                
                # Проверяем, существует ли служба
                status = self.service_manager.get_service_status(self.service_manager.admin_service)
                if not status.get('exists'):
                    logger.info("Admin service not found, creating...")
                    # Создаем службу admin
                    service_result = self.service_manager.setup_admin_service(
                        admin_port=existing_admin.get('port', admin_port),
                        admin_password=existing_admin.get('password')
                    )
                    
                    if service_result['success']:
                        logger.info("✓ Admin service created")
                
                return {
                    "success": True,
                    "message": "Admin already exists",
                    "admin_port": existing_admin.get('port'),
                    "exists": True,
                    "service_exists": status.get('exists', False)
                }
            
            # Создаем admin пользователя
            admin_password = secrets.token_urlsafe(12)
            
            admin_user = {
                "username": "admin",
                "email": "admin@localhost",
                "port": admin_port,
                "password": admin_password,
                "method": Config.SS_METHOD,
                "enable": True,
                "traffic_limit": 100 * 1024**3,
                "traffic_used": 0,
                "expires_at": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "role": "admin"
            }
            
            result = self.users_collection.insert_one(admin_user)
            admin_id = str(result.inserted_id)
            
            # Настраиваем службу admin
            service_result = self.service_manager.setup_admin_service(
                admin_port=admin_port,
                admin_password=admin_password
            )
            
            return {
                "success": True,
                "admin_id": admin_id,
                "admin_port": admin_port,
                "admin_password": admin_password,
                "service_created": service_result.get('success', False),
                "service_name": self.service_manager.admin_service
            }
            
        except Exception as e:
            logger.error(f"Error initializing admin: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def add_user(self, username, email=None, traffic_limit_gb=10, duration_days=30, method=None):
        """Добавляет нового пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            # Проверяем существование пользователя
            existing_user = self.users_collection.find_one({"username": username})
            if existing_user:
                return {"success": False, "error": f"User '{username}' already exists"}
            
            # Генерируем порт
            used_ports = [u.get('port') for u in self.users_collection.find({}, {'port': 1})]
            port = Config.SS_PORT_RANGE_START
            
            while port <= Config.SS_PORT_RANGE_END:
                if port not in used_ports:
                    break
                port += 1
            
            if port > Config.SS_PORT_RANGE_END:
                return {"success": False, "error": "No available ports"}
            
            # Генерируем пароль
            password = secrets.token_urlsafe(12)
            
            # Создаем пользователя
            user = {
                "username": username,
                "email": email or "",
                "port": port,
                "password": password,
                "method": method or Config.SS_METHOD,
                "enable": True,
                "traffic_limit": traffic_limit_gb * 1024**3,
                "traffic_used": 0,
                "expires_at": datetime.utcnow() + timedelta(days=duration_days),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "role": "user"
            }
            
            result = self.users_collection.insert_one(user)
            user_id = str(result.inserted_id)
            
            # Создаем службу для пользователя
            service_result = self.service_manager.create_user_service(user)
            
            # Обновляем основной конфиг admin
            users = list(self.users_collection.find({"enable": True}))
            self.service_manager.update_admin_config(users)
            
            # Создаем конфигурационные строки
            config_string = f"{user['method']}:{password}@{Config.SS_SERVER_IP}:{port}"
            ss_url = f"ss://{base64.b64encode(config_string.encode()).decode()}"
            
            return {
                "success": True,
                "id": user_id,
                "username": username,
                "port": port,
                "password": password,
                "server": Config.SS_SERVER_IP,
                "method": user['method'],
                "config_string": config_string,
                "ss_url": ss_url,
                "expires_at": user['expires_at'].isoformat(),
                "service_created": service_result.get('success', False),
                "service_name": service_result.get('service_name', f"shadowsocks-{username}.service")
            }
            
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def toggle_user_service(self, user_id, enable=True):
        """Включает/выключает службу пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            logger.info(f"Toggle service for user_id: {user_id}, enable: {enable}")
            
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            username = user.get('username')
            if username == 'admin':
                service_name = self.service_manager.admin_service
            else:
                service_name = f"shadowsocks-{username}.service"
            
            if enable:
                result = self.service_manager.manage_service(service_name, "start")
                self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"enable": True, "updated_at": datetime.utcnow()}}
                )
                action = "started"
            else:
                result = self.service_manager.manage_service(service_name, "stop")
                self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"enable": False, "updated_at": datetime.utcnow()}}
                )
                action = "stopped"
            
            if result.get('success'):
                # Обновляем основной конфиг
                users = list(self.users_collection.find({"enable": True}))
                self.service_manager.update_admin_config(users)
                
                # Перезапускаем основной сервис для применения изменений
                self.service_manager.manage_service(self.service_manager.admin_service, "reload")
                
                return {
                    "success": True,
                    "message": f"Service {action}",
                    "username": username,
                    "service": service_name
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', f'Failed to {action} service')
                }
                
        except Exception as e:
            logger.error(f"Error toggling user service: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def get_all_services_status(self):
        """Получает статус всех служб"""
        try:
            all_services = self.service_manager.list_all_services()
            user_services = []
            
            for service in all_services:
                status = self.service_manager.get_service_status(service)
                if status.get('success'):
                    # Определяем username
                    if service == self.service_manager.admin_service:
                        username = "admin"
                    else:
                        username = service.replace("shadowsocks-", "").replace(".service", "")
                    
                    user_services.append({
                        "service_name": service,
                        "username": username,
                        "active": status.get('active', False),
                        "enabled": status.get('enabled', False),
                        "exists": status.get('exists', True),
                        "pid": status.get('pid')
                    })
            
            return {
                "success": True,
                "user_services": user_services,
                "total_services": len(all_services)
            }
            
        except Exception as e:
            logger.error(f"Error getting services status: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_user(self, user_id):
        """Удаляет пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            username = user.get('username')
            
            # Удаляем службу (кроме admin)
            service_removed = False
            if username and username != 'admin':
                service_result = self.service_manager.delete_user_service(username)
                service_removed = service_result.get('service_removed', False)
            
            # Удаляем из БД
            result = self.users_collection.delete_one({"_id": ObjectId(user_id)})
            
            if result.deleted_count > 0:
                # Обновляем основной конфиг
                users = list(self.users_collection.find({"enable": True}))
                self.service_manager.update_admin_config(users)
                
                return {
                    "success": True,
                    "message": f"User {username} deleted",
                    "username": username,
                    "service_removed": service_removed
                }
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return {"success": False, "error": str(e)}
    
    def reset_user_traffic(self, user_id):
        """Сбрасывает трафик пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            result = self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"traffic_used": 0, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                return {"success": True, "message": "Traffic reset"}
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            logger.error(f"Error resetting traffic: {e}")
            return {"success": False, "error": str(e)}
    
    def extend_user_expiration(self, user_id, additional_days):
        """Продлевает срок пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            current_expires = user.get('expires_at')
            if current_expires:
                if isinstance(current_expires, str):
                    current_expires = datetime.fromisoformat(current_expires.replace('Z', '+00:00'))
                new_expires = current_expires + timedelta(days=additional_days)
            else:
                new_expires = datetime.utcnow() + timedelta(days=additional_days)
            
            result = self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"expires_at": new_expires, "updated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                return {"success": True, "message": "User extended"}
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            logger.error(f"Error extending user: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_services(self):
        """Синхронизирует службы с пользователями"""
        try:
            users = list(self.users_collection.find({}))
            created_count = 0
            errors = []
            
            for user in users:
                username = user.get('username')
                if username:
                    if username == 'admin':
                        service_name = self.service_manager.admin_service
                    else:
                        service_name = f"shadowsocks-{username}.service"
                    
                    # Проверяем существование службы
                    status = self.service_manager.get_service_status(service_name)
                    
                    if not status.get('exists'):
                        logger.info(f"Creating service for {username}...")
                        service_result = self.service_manager.create_user_service(user)
                        
                        if service_result['success']:
                            created_count += 1
                        else:
                            errors.append(f"Failed to create service for {username}: {service_result.get('error')}")
            
            # Обновляем основной конфиг
            active_users = list(self.users_collection.find({"enable": True}))
            self.service_manager.update_admin_config(active_users)
            
            return {
                "success": True,
                "services_created": created_count,
                "total_users": len(users),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"Error syncing services: {e}")
            return {"success": False, "error": str(e)}
    
    def restart_all_services(self):
        """Перезапускает все службы"""
        try:
            services = self.service_manager.list_all_services()
            results = []
            
            for service in services:
                result = self.service_manager.manage_service(service, "restart")
                results.append({
                    "service": service,
                    "success": result.get('success', False),
                    "error": result.get('error', '')
                })
            
            return {
                "success": True,
                "services_restarted": len([r for r in results if r['success']]),
                "total_services": len(services),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error restarting all services: {e}")
            return {"success": False, "error": str(e)}


# Утилитарные функции
def get_user_config_string(user):
    """Генерирует строку конфигурации для пользователя"""
    try:
        config_string = f"{user['method']}:{user['password']}@{Config.SS_SERVER_IP}:{user['port']}"
        encoded = base64.b64encode(config_string.encode()).decode()
        ss_url = f"ss://{encoded}"
        
        return {
            "success": True,
            "config_string": config_string,
            "ss_url": ss_url,
            "ss_url_with_comment": f"{ss_url}#{user.get('username', 'user')}",
            "base64": encoded
        }
    except Exception as e:
        logger.error(f"Error generating config string: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Тестирование
    manager = ShadowsocksConfigManager()
    
    if manager.users_collection is not None:
        print("✓ Connected to MongoDB")
        print("✓ Config manager initialized")
        
        # Проверяем статус служб
        services_status = manager.get_all_services_status()
        if services_status['success']:
            print(f"  Total services: {services_status['total_services']}")
            for service in services_status['user_services']:
                status = "active" if service['active'] else "inactive"
                print(f"  - {service['service_name']}: {status}")
    else:
        print("✗ Failed to connect to MongoDB")