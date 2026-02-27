from pymongo import MongoClient
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from config import Config
import secrets
import base64
import subprocess
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HostSystemctlManager:
    """Менеджер для работы с systemctl на хосте"""
    
    @staticmethod
    def execute_on_host(cmd_args, timeout=30):
        """Выполняет команду на хосте"""
        try:
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
                'returncode': result.returncode
            }
        except FileNotFoundError as e:
            return {
                'success': False,
                'error': f'Command not found: {e}',
                'returncode': 127
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'returncode': 1
            }
    
    @staticmethod
    def systemctl(action, service_name=None):
        """Выполняет systemctl команду на хосте"""
        cmd = ['systemctl']
        
        if action == 'daemon-reload':
            cmd.append('daemon-reload')
        elif service_name:
            cmd.extend([action, service_name])
        else:
            cmd.append(action)
        
        return HostSystemctlManager.execute_on_host(cmd)


class ShadowsocksServiceManager:
    def __init__(self):
        self.config_dir = Path("/etc/shadowsocks-libev")
        self.service_dir = Path("/etc/systemd/system")
        self.admin_service = "shadowsocks.service"
        
        # Конфигурация для admin (основной сервис)
        self.admin_config = {
            "server": "0.0.0.0",
            "port_password": {},  # Будет заполняться динамически
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
    
    def setup_admin_service(self, admin_port=8388, admin_password=None):
        """
        Настраивает основную службу admin
        """
        try:
            if admin_password is None:
                admin_password = secrets.token_urlsafe(12)
            
            # Создаем конфиг для admin
            admin_config = self.admin_config.copy()
            admin_config["port_password"] = {str(admin_port): admin_password}
            
            # Сохраняем конфиг admin
            self.config_dir.mkdir(parents=True, exist_ok=True)
            admin_config_path = self.config_dir / "config.json"
            
            with open(admin_config_path, 'w') as f:
                json.dump(admin_config, f, indent=2)
            
            # Устанавливаем правильные права (644 - читаемый всеми)
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
            
            # Устанавливаем права для файла службы
            os.chmod(service_path, 0o644)
            
            logger.info(f"✓ Admin service created at {service_path}")
            logger.info(f"✓ Admin config: port={admin_port}, password={admin_password}")
            
            return {
                "success": True,
                "admin_port": admin_port,
                "admin_password": admin_password,
                "service_name": self.admin_service,
                "config_path": str(admin_config_path)
            }
            
        except Exception as e:
            logger.error(f"✗ Error setting up admin service: {e}")
            return {"success": False, "error": str(e)}
    
    def create_user_service(self, user_data: Dict) -> Dict:
        """
        Создает отдельную службу для пользователя
        """
        try:
            username = user_data.get('username')
            port = user_data.get('port', 8389)
            password = user_data.get('password', '')
            method = user_data.get('method', Config.SS_METHOD)
            
            if not username:
                return {"success": False, "error": "Username is required"}
            
            # Создаем конфиг для пользователя
            user_config = self.single_user_template.copy()
            user_config.update({
                "server_port": port,
                "password": password,
                "method": method
            })
            
            # Сохраняем конфиг пользователя
            config_filename = f"config-{username}.json"
            config_path = self.config_dir / config_filename
            
            with open(config_path, 'w') as f:
                json.dump(user_config, f, indent=2)
            
            # Правильные права: 644 (читаем для всех)
            os.chmod(config_path, 0o644)
            
            # Создаем службу для пользователя
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
            
            # Права для файла службы
            os.chmod(service_path, 0o644)
            
            logger.info(f"✓ User service created: {service_name}")
            logger.info(f"✓ User config saved: {config_path}")
            
            # Сразу включаем и запускаем службу НА ХОСТЕ
            self.manage_service(service_name, "enable")
            start_result = self.manage_service(service_name, "start")
            
            return {
                "success": True,
                "username": username,
                "port": port,
                "service_name": service_name,
                "config_path": str(config_path),
                "config": user_config,
                "service_enabled": True,
                "service_started": start_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"✗ Error creating user service: {e}")
            return {"success": False, "error": str(e)}
    
    def update_admin_config(self, users: List[Dict]) -> Dict:
        """
        Обновляет основной конфиг admin с портами всех пользователей
        """
        try:
            admin_config_path = self.config_dir / "config.json"
            
            if not admin_config_path.exists():
                # Создаем новый конфиг
                config = self.admin_config.copy()
            else:
                # Загружаем существующий конфиг
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
            
            # Сохраняем обновленный конфиг
            with open(admin_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Обновляем права
            os.chmod(admin_config_path, 0o644)
            
            logger.info(f"✓ Admin config updated with {len(port_password)} users")
            
            return {
                "success": True,
                "port_count": len(port_password),
                "ports": list(port_password.keys()),
                "config_path": str(admin_config_path)
            }
            
        except Exception as e:
            logger.error(f"✗ Error updating admin config: {e}")
            return {"success": False, "error": str(e)}
    
    def manage_service(self, service_name: str, action: str) -> Dict:
        """
        Управляет службой (start/stop/restart/enable/disable) НА ХОСТЕ
        """
        try:
            # Для daemon-reload используем отдельную команду
            if action == "daemon-reload":
                result = HostSystemctlManager.systemctl('daemon-reload')
                return {
                    "success": result['success'],
                    "service": "systemd",
                    "action": action,
                    "message": "Systemd daemon reloaded" if result['success'] else "Failed to reload systemd",
                    "output": result.get('stdout', ''),
                    "error": result.get('stderr', '') if not result['success'] else None
                }
            
            # Определяем команду systemctl
            actions_map = {
                "start": "start",
                "stop": "stop",
                "restart": "restart",
                "enable": "enable",
                "disable": "disable",
                "reload": "reload",
                "status": "status"
            }
            
            if action not in actions_map:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            # Выполняем команду НА ХОСТЕ
            result = HostSystemctlManager.systemctl(actions_map[action], service_name)
            
            if result['success']:
                return {
                    "success": True,
                    "service": service_name,
                    "action": action,
                    "message": f"Service {service_name} {action}ed successfully",
                    "output": result.get('stdout', '')
                }
            else:
                return {
                    "success": False,
                    "service": service_name,
                    "action": action,
                    "error": result.get('stderr') or result.get('error') or f"Failed to {action} service",
                    "output": result.get('stdout', '')
                }
                
        except Exception as e:
            logger.error(f"✗ Error managing service {service_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_service_status(self, service_name: str) -> Dict:
        """
        Получает статус службы НА ХОСТЕ
        """
        try:
            # Сначала проверяем существование файла службы
            service_path = self.service_dir / f"{service_name}"
            exists = service_path.exists()
            
            if not exists:
                return {"success": True, "exists": False, "status": "not_found"}
            
            # Получаем статус активности НА ХОСТЕ
            is_active_result = HostSystemctlManager.execute_on_host(['systemctl', 'is-active', service_name])
            
            # Получаем статус enabled НА ХОСТЕ
            is_enabled_result = HostSystemctlManager.execute_on_host(['systemctl', 'is-enabled', service_name])
            
            # Получаем подробный статус НА ХОСТЕ
            status_result = HostSystemctlManager.execute_on_host(['systemctl', 'status', service_name, '--no-pager'])
            
            active_status = "active" if is_active_result['success'] else "inactive"
            enabled_status = "enabled" if is_enabled_result['success'] else "disabled"
            
            return {
                "success": True,
                "exists": True,
                "service_name": service_name,
                "active": is_active_result['success'],
                "enabled": is_enabled_result['success'],
                "status": active_status,
                "status_output": status_result.get('stdout', ''),
                "detailed": {
                    "active_status": active_status,
                    "enabled_status": enabled_status,
                    "is_active_output": is_active_result.get('stdout', ''),
                    "is_enabled_output": is_enabled_result.get('stdout', '')
                }
            }
            
        except Exception as e:
            logger.error(f"✗ Error getting service status: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_user_service(self, username: str) -> Dict:
        """
        Удаляет службу и конфиг пользователя
        """
        try:
            service_name = f"shadowsocks-{username}.service"
            config_path = self.config_dir / f"config-{username}.json"
            
            # Останавливаем и отключаем службу НА ХОСТЕ
            stop_result = self.manage_service(service_name, "stop")
            disable_result = self.manage_service(service_name, "disable")
            
            # Удаляем файл службы
            service_file = self.service_dir / service_name
            if service_file.exists():
                service_file.unlink()
                logger.info(f"✓ Service file removed: {service_file}")
            
            # Удаляем конфиг
            if config_path.exists():
                config_path.unlink()
                logger.info(f"✓ Config file removed: {config_path}")
            
            # Перезагружаем systemd НА ХОСТЕ
            reload_result = HostSystemctlManager.systemctl('daemon-reload')
            
            return {
                "success": True,
                "username": username,
                "service_removed": service_file.exists() == False,
                "config_removed": config_path.exists() == False,
                "service_stopped": stop_result.get('success', False),
                "service_disabled": disable_result.get('success', False),
                "daemon_reloaded": reload_result.get('success', False)
            }
            
        except Exception as e:
            logger.error(f"✗ Error deleting user service: {e}")
            return {"success": False, "error": str(e)}
    
    def list_all_services(self) -> List[str]:
        """
        Возвращает список всех служб shadowsocks
        """
        try:
            # Ищем все файлы служб shadowsocks в каталоге
            services = []
            for service_file in self.service_dir.glob("shadowsocks-*.service"):
                services.append(service_file.name)
            
            # Добавляем основную службу если существует
            admin_service_path = self.service_dir / self.admin_service
            if admin_service_path.exists():
                services.append(self.admin_service)
            
            return sorted(services)
            
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return []


class ShadowsocksConfigManager:
    def __init__(self):
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
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
        """
        Инициализирует admin пользователя и службу
        """
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            # Проверяем, есть ли уже admin
            existing_admin = self.users_collection.find_one({"username": "admin"})
            
            if existing_admin:
                logger.info("✓ Admin user already exists")
                
                # Проверяем, существует ли служба
                status = self.service_manager.get_service_status(self.service_manager.admin_service)
                if not status['exists']:
                    # Создаем службу admin
                    service_result = self.service_manager.setup_admin_service(
                        admin_port=existing_admin.get('port', admin_port),
                        admin_password=existing_admin.get('password')
                    )
                    
                    if service_result['success']:
                        # Включаем и запускаем службу
                        self.service_manager.manage_service(
                            self.service_manager.admin_service,
                            "enable"
                        )
                        self.service_manager.manage_service(
                            self.service_manager.admin_service,
                            "start"
                        )
                
                return {
                    "success": True,
                    "message": "Admin already exists",
                    "admin_port": existing_admin.get('port'),
                    "exists": True,
                    "service_exists": True
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
                "traffic_limit": 100 * 1024**3,  # 100 GB
                "traffic_used": 0,
                "expires_at": None,  # Never expires
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "role": "admin",
                "service_name": self.service_manager.admin_service,
                "notified_expire": False,
                "notified_traffic": False,
                "notified_expired": False
            }
            
            # Сохраняем в базу
            result = self.users_collection.insert_one(admin_user)
            admin_id = str(result.inserted_id)
            
            # Настраиваем службу admin
            service_result = self.service_manager.setup_admin_service(
                admin_port=admin_port,
                admin_password=admin_password
            )
            
            if service_result['success']:
                # Включаем и запускаем службу
                enable_result = self.service_manager.manage_service(
                    self.service_manager.admin_service,
                    "enable"
                )
                start_result = self.service_manager.manage_service(
                    self.service_manager.admin_service,
                    "start"
                )
                
                logger.info(f"✓ Admin service enabled: {enable_result.get('success')}")
                logger.info(f"✓ Admin service started: {start_result.get('success')}")
            
            return {
                "success": True,
                "admin_id": admin_id,
                "admin_port": admin_port,
                "admin_password": admin_password,
                "service_created": service_result.get('success', False),
                "service_name": self.service_manager.admin_service,
                "service_enabled": enable_result.get('success', False) if 'enable_result' in locals() else False,
                "service_started": start_result.get('success', False) if 'start_result' in locals() else False
            }
            
        except Exception as e:
            logger.error(f"✗ Error initializing admin: {e}")
            return {"success": False, "error": str(e)}
    
    def add_user(self, username, email=None, traffic_limit_gb=10, duration_days=30, method=None):
        """Добавляет нового пользователя с отдельной службой"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            # Проверяем, не существует ли уже пользователь
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
                "role": "user",
                "service_name": f"shadowsocks-{username}.service",
                "notified_expire": False,
                "notified_traffic": False,
                "notified_expired": False
            }
            
            # Сохраняем в MongoDB
            result = self.users_collection.insert_one(user)
            user_id = str(result.inserted_id)
            
            # Создаем службу для пользователя
            service_result = self.service_manager.create_user_service(user)
            
            if service_result['success']:
                # Обновляем основной конфиг admin
                users = list(self.users_collection.find({"enable": True}))
                self.service_manager.update_admin_config(users)
                
                # Перезапускаем основной сервис чтобы применить изменения
                self.service_manager.manage_service(
                    self.service_manager.admin_service,
                    "reload"
                )
            
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
                "service_name": service_result.get('service_name', f"shadowsocks-{username}.service"),
                "service_started": service_result.get('service_started', False)
            }
            
        except Exception as e:
            logger.error(f"✗ Error adding user: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_user(self, user_id):
        """Удаляет пользователя и его службу"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            # Получаем информацию о пользователе
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            username = user.get('username')
            
            # Удаляем службу пользователя
            if username and username != 'admin':
                service_result = self.service_manager.delete_user_service(username)
            
            # Удаляем из MongoDB
            result = self.users_collection.delete_one({"_id": ObjectId(user_id)})
            
            if result.deleted_count > 0:
                # Обновляем основной конфиг admin
                users = list(self.users_collection.find({"enable": True}))
                self.service_manager.update_admin_config(users)
                
                # Перезапускаем основной сервис
                self.service_manager.manage_service(
                    self.service_manager.admin_service,
                    "reload"
                )
                
                return {
                    "success": True,
                    "message": f"User {username} deleted",
                    "username": username,
                    "port": user.get('port'),
                    "service_removed": service_result.get('success', False) if 'service_result' in locals() else False
                }
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            logger.error(f"✗ Error deleting user: {e}")
            return {"success": False, "error": str(e)}
    
    def update_user(self, user_id, updates):
        """Обновляет данные пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            # Получаем пользователя
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            username = user.get('username')
            
            # Добавляем timestamp обновления
            updates['updated_at'] = datetime.utcnow()
            
            # Обновляем в базе
            result = self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                # Если изменились порт/пароль/метод, обновляем конфиг
                if any(key in updates for key in ['port', 'password', 'method']):
                    # Обновляем конфиг пользователя
                    updated_user = {**user, **updates}
                    service_result = self.service_manager.create_user_service(updated_user)
                    
                    if service_result['success']:
                        # Обновляем основной конфиг
                        users = list(self.users_collection.find({"enable": True}))
                        self.service_manager.update_admin_config(users)
                        
                        # Перезапускаем основной сервис
                        self.service_manager.manage_service(
                            self.service_manager.admin_service,
                            "reload"
                        )
                
                return {"success": True, "message": "User updated"}
            else:
                return {"success": False, "error": "User not found or no changes"}
                
        except Exception as e:
            logger.error(f"✗ Error updating user: {e}")
            return {"success": False, "error": str(e)}
    
    def toggle_user_service(self, user_id, enable=True):
        """Включает/выключает службу пользователя"""
        try:
            if self.users_collection is None:
                return {"success": False, "error": "Database not connected"}
            
            from bson import ObjectId
            
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"success": False, "error": "User not found"}
            
            username = user.get('username')
            
            # Для admin используем основную службу
            if username == 'admin':
                service_name = self.service_manager.admin_service
            else:
                service_name = f"shadowsocks-{username}.service"
            
            if enable:
                result = self.service_manager.manage_service(service_name, "start")
                # Обновляем статус в БД
                self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"enable": True, "updated_at": datetime.utcnow()}}
                )
                action = "started"
            else:
                result = self.service_manager.manage_service(service_name, "stop")
                # Обновляем статус в БД
                self.users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"enable": False, "updated_at": datetime.utcnow()}}
                )
                action = "stopped"
            
            if result['success']:
                # Обновляем основной конфиг
                users = list(self.users_collection.find({"enable": True}))
                self.service_manager.update_admin_config(users)
                
                # Перезапускаем основной сервис
                self.service_manager.manage_service(
                    self.service_manager.admin_service,
                    "reload"
                )
                
                return {
                    "success": True,
                    "message": f"User service {action}",
                    "username": username,
                    "service": service_name,
                    "action": action
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', f'Failed to {action} service')
                }
                
        except Exception as e:
            logger.error(f"✗ Error toggling user service: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_services_status(self):
        """Получает статус всех служб"""
        try:
            all_services = self.service_manager.list_all_services()
            
            services_status = []
            user_services = []
            
            for service in all_services:
                status = self.service_manager.get_service_status(service)
                if status['success']:
                    services_status.append({
                        "service_name": service,
                        "status": status.get('status', 'unknown'),
                        "active": status.get('active', False),
                        "enabled": status.get('enabled', False),
                        "exists": status.get('exists', False)
                    })
                    
                    # Определяем username из имени службы
                    if service == self.service_manager.admin_service:
                        username = "admin"
                    else:
                        username = service.replace("shadowsocks-", "").replace(".service", "")
                    
                    # Ищем пользователя в БД
                    user = self.users_collection.find_one({"username": username}) if self.users_collection is not None else None
                    
                    user_services.append({
                        "service_name": service,
                        "username": username,
                        "port": user.get('port') if user else None,
                        "enable": user.get('enable', True) if user else None,
                        "status": status.get('status', 'unknown'),
                        "active": status.get('active', False),
                        "enabled": status.get('enabled', False)
                    })
            
            return {
                "success": True,
                "all_services": all_services,
                "services_status": services_status,
                "user_services": user_services,
                "total_services": len(all_services)
            }
            
        except Exception as e:
            logger.error(f"✗ Error getting services status: {e}")
            return {"success": False, "error": str(e)}
    
    def restart_all_services(self):
        """Перезапускает все службы shadowsocks"""
        try:
            services = self.service_manager.list_all_services()
            results = []
            
            for service in services:
                result = self.service_manager.manage_service(service, "restart")
                results.append({
                    "service": service,
                    "success": result.get('success', False),
                    "message": result.get('message', ''),
                    "error": result.get('error', '')
                })
            
            return {
                "success": True,
                "services_restarted": len([r for r in results if r['success']]),
                "total_services": len(services),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"✗ Error restarting all services: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_services(self):
        """Создает службы для существующих пользователей"""
        try:
            users = list(self.users_collection.find({}))
            created_count = 0
            errors = []
            
            for user in users:
                username = user.get('username')
                if username:  # Для всех пользователей включая admin
                    if username == 'admin':
                        service_name = self.service_manager.admin_service
                    else:
                        service_name = f"shadowsocks-{username}.service"
                    
                    # Проверяем, существует ли уже служба
                    status = self.service_manager.get_service_status(service_name)
                    
                    if not status['exists']:
                        # Создаем службу
                        service_result = self.service_manager.create_user_service(user)
                        
                        if service_result['success']:
                            created_count += 1
                        else:
                            errors.append(f"Failed to create service for {username}: {service_result.get('error')}")
            
            # Обновляем основной конфиг
            active_users = list(self.users_collection.find({"enable": True}))
            self.service_manager.update_admin_config(active_users)
            
            # Перезапускаем основной сервис
            self.service_manager.manage_service(
                self.service_manager.admin_service,
                "reload"
            )
            
            return {
                "success": True,
                "services_created": created_count,
                "total_users": len(users),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"✗ Error syncing services: {e}")
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
        
        # Инициализируем admin
        result = manager.initialize_admin()
        if result['success']:
            print("✓ Admin initialized")
            print(f"  Admin service: {manager.service_manager.admin_service}")
            
            # Проверяем статус служб
            services_status = manager.get_all_services_status()
            if services_status['success']:
                print(f"  Total services: {services_status['total_services']}")
                for service in services_status['user_services']:
                    print(f"  - {service['service_name']}: {service['status']}")
            
            # Создаем тестового пользователя
            user_result = manager.add_user(
                username="testuser",
                email="test@example.com",
                traffic_limit_gb=10,
                duration_days=30,
                method="chacha20-ietf-poly1305"
            )
            
            if user_result['success']:
                print("✓ Test user created")
                print(f"  Username: {user_result['username']}")
                print(f"  Port: {user_result['port']}")
                print(f"  Service: {user_result.get('service_name')}")
            else:
                print(f"✗ Error: {user_result.get('error')}")
        else:
            print(f"✗ Error initializing admin: {result.get('error')}")
    else:
        print("✗ Failed to connect to MongoDB")