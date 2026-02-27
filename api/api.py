from flask import Flask, jsonify, request, send_file, Response, render_template
from flask_cors import CORS
from config_generator import ShadowsocksConfigManager
from config import Config
from pymongo import MongoClient
from datetime import datetime, timedelta
import psutil
import os
import json
import logging
import threading
import time
import subprocess
from bson import ObjectId
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

# Создаем Flask приложение с указанием путей к статическим файлам и шаблонам
app = Flask(__name__,
            static_folder='../static',
            static_url_path='/static',
            template_folder='../templates')

CORS(app)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация MongoDB и Config Manager
try:
    manager = ShadowsocksConfigManager()
    client = MongoClient(
        Config.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000
    )
    client.admin.command('ping')
    db = client[Config.MONGO_DB]
    logger.info("✓ Connected to MongoDB")
except Exception as e:
    logger.error(f"✗ MongoDB connection failed: {e}")
    db = None
    manager = None

# Хранилище для WebSocket (в реальности используйте Redis или подобное)
active_connections = []
traffic_history = []
notifications = []

# Кастомный JSONEncoder для обработки ObjectId и datetime
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = MongoJSONEncoder

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def update_shadowsocks_config_file():
    """Обновляет файл конфигурации shadowsocks-libev на хосте"""
    try:
        # Для гибридной системы эта функция не нужна
        # Конфиги управляются через service manager
        logger.info("Hybrid config mode: Each user has their own service + admin service")
        return True
        
    except Exception as e:
        logger.error(f"Error updating shadowsocks config: {e}")
        return False

# ==================== ОСНОВНЫЕ ENDPOINTS ====================

@app.route('/')
def index():
    return send_file('../templates/index.html')

@app.route('/favicon.ico')
def favicon():
    return send_file('../static/favicon.ico')

# Получить всех пользователей
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
            
        users = list(db.users.find({}, {'password': 0}))
        
        for user in users:
            # Рассчитываем оставшиеся дни
            expires_at = user.get('expires_at')
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                elif isinstance(expires_at, datetime):
                    pass
                
                remaining = (expires_at - datetime.utcnow()).days
                user['days_remaining'] = max(0, remaining)
                user['expires_at'] = expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at)
            
            # Трафик в GB
            user['traffic_used_gb'] = round(user.get('traffic_used', 0) / 1024**3, 2)
            user['traffic_limit_gb'] = round(user.get('traffic_limit', 0) / 1024**3, 2)
            
            if user['traffic_limit_gb'] > 0:
                user['traffic_percent'] = round((user['traffic_used_gb'] / user['traffic_limit_gb']) * 100, 1)
            else:
                user['traffic_percent'] = 0
            
            # Статус
            user['is_active'] = user.get('enable', True)
            
            # Добавляем информацию о службе
            username = user.get('username')
            if username:
                user['service_name'] = f"shadowsocks-{username}.service"
            
            # Преобразуем ObjectId в строку
            if '_id' in user:
                user['_id'] = str(user['_id'])
        
        return jsonify({"success": True, "users": users})
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Добавить пользователя
@app.route('/api/users', methods=['POST'])
def add_user():
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        if not request.is_json:
            return jsonify({"success": False, "message": "Missing JSON"}), 400
            
        data = request.json
        
        # Проверяем обязательные поля
        if not data.get('username'):
            return jsonify({"success": False, "message": "Username is required"}), 400
        
        result = manager.add_user(
            username=data.get('username'),
            email=data.get('email', ''),
            traffic_limit_gb=data.get('traffic_limit_gb', 10),
            duration_days=data.get('duration_days', 30),
            method=data.get('method', Config.SS_METHOD)
        )
        
        if result.get('success'):
            # Отправляем уведомление если есть email
            if data.get('email'):
                send_welcome_email(
                    email=data['email'],
                    username=data['username'],
                    server=Config.SS_SERVER_IP,
                    port=result.get('port'),
                    password=result.get('password'),
                    method=result.get('method'),
                    expires_days=data.get('duration_days', 30)
                )
            
            # Добавляем информацию о службе в ответ
            result['service_created'] = result.get('service_created', False)
            result['service_started'] = result.get('service_started', False)
            
            # Логируем создание
            if db is not None:
                db.logs.insert_one({
                    "type": "user_created",
                    "user_id": result.get('id'),
                    "username": data['username'],
                    "timestamp": datetime.utcnow(),
                    "details": f"User {data['username']} created with service {result.get('service_name', 'N/A')}"
                })
            
            return jsonify(result)
        else:
            return jsonify({"success": False, "message": result.get('error', 'Unknown error')}), 500
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Удалить пользователя
@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.delete_user(user_id)
        
        if result.get('success'):
            # Логируем удаление
            if db is not None:
                db.logs.insert_one({
                    "type": "user_deleted",
                    "user_id": user_id,
                    "username": result.get('username'),
                    "timestamp": datetime.utcnow(),
                    "details": f"User {result.get('username')} deleted with service {result.get('service_removed', False)}"
                })
            
            return jsonify(result)
        else:
            return jsonify({"success": False, "message": result.get('error', 'User not found')}), 404
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Получить конфиг пользователя
@app.route('/api/users/<user_id>/config', methods=['GET'])
def get_user_config(user_id):
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
            
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Формируем конфигурационную строку
        config_string = f"{user['method']}:{user['password']}@{Config.SS_SERVER_IP}:{user['port']}"
        
        # ПРАВИЛЬНОЕ Base64 кодирование для SS URL
        encoded_string = base64.b64encode(config_string.encode()).decode()
        
        # Формируем SS URL
        ss_url = f"ss://{encoded_string}"
        
        # Также создаем URL с комментарием
        ss_url_with_comment = f"ss://{encoded_string}#{user.get('username', 'user')}"
        
        return jsonify({
            "success": True,
            "config": {
                "server": Config.SS_SERVER_IP,
                "port": user['port'],
                "password": user['password'],
                "method": user['method'],
                "ss_url": ss_url,
                "ss_url_with_comment": ss_url_with_comment,
                "config_string": config_string,
                "base64_encoded": encoded_string,
                "username": user.get('username', ''),
                "expires_at": user.get('expires_at', ''),
                "traffic_used_gb": round(user.get('traffic_used', 0) / 1024**3, 2),
                "traffic_limit_gb": round(user.get('traffic_limit', 0) / 1024**3, 2)
            }
        })
    except Exception as e:
        logger.error(f"Error getting user config: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Сбросить трафик пользователя
@app.route('/api/users/<user_id>/reset-traffic', methods=['POST'])
def reset_user_traffic(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.reset_user_traffic(user_id)
        
        if result.get('success'):
            # Логируем сброс трафика
            if db is not None:
                db.logs.insert_one({
                    "type": "traffic_reset",
                    "user_id": user_id,
                    "timestamp": datetime.utcnow(),
                    "details": "Traffic usage reset to zero"
                })
            
            return jsonify({"success": True, "message": "Traffic reset"})
        else:
            return jsonify({"success": False, "message": result.get('error', 'User not found')}), 404
    except Exception as e:
        logger.error(f"Error resetting traffic: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Продлить срок пользователя
@app.route('/api/users/<user_id>/extend', methods=['POST'])
def extend_user(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        if not request.is_json:
            return jsonify({"success": False, "message": "Missing JSON"}), 400
            
        data = request.json
        additional_days = data.get('additional_days', 30)
        
        result = manager.extend_user_expiration(user_id, additional_days)
        
        if result.get('success'):
            # Логируем продление
            if db is not None:
                db.logs.insert_one({
                    "type": "user_extended",
                    "user_id": user_id,
                    "timestamp": datetime.utcnow(),
                    "details": f"User extended by {additional_days} days"
                })
            
            return jsonify({"success": True, "message": "User extended"})
        else:
            return jsonify({"success": False, "message": result.get('error', 'User not found')}), 404
    except Exception as e:
        logger.error(f"Error extending user: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== УПРАВЛЕНИЕ СЛУЖБАМИ ====================

# Инициализация admin и служб
@app.route('/api/admin/initialize', methods=['POST'])
def initialize_admin():
    """Инициализирует admin пользователя и службу"""
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.initialize_admin()
        
        if result.get('success'):
            # Логируем инициализацию
            if db is not None:
                db.logs.insert_one({
                    "type": "admin_initialized",
                    "timestamp": datetime.utcnow(),
                    "details": f"Admin service initialized with port {result.get('admin_port')}"
                })
            
            return jsonify(result)
        else:
            return jsonify({"success": False, "message": result.get('error', 'Initialization failed')}), 500
    except Exception as e:
        logger.error(f"Error initializing admin: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Получить статус всех служб
@app.route('/api/services/status', methods=['GET'])
def get_all_services_status():
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.get_all_services_status()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting services status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Перезапустить все службы
@app.route('/api/services/restart-all', methods=['POST'])
def restart_all_services():
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.restart_all_services()
        
        # Логируем
        if db is not None and result.get('success'):
            db.logs.insert_one({
                "type": "services_restarted",
                "timestamp": datetime.utcnow(),
                "details": f"Restarted {result.get('services_restarted', 0)} of {result.get('total_services', 0)} services"
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error restarting services: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Перезагрузить все службы
@app.route('/api/services/reload-all', methods=['POST'])
def reload_all_services():
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        # Перезагружаем службы через systemctl reload
        services = manager.service_manager.list_all_services()
        results = []
        
        for service in services:
            try:
                result = subprocess.run(
                    ["systemctl", "reload", service],
                    capture_output=True,
                    text=True
                )
                results.append({
                    "service": service,
                    "success": result.returncode == 0,
                    "output": result.stdout.strip(),
                    "error": result.stderr.strip()
                })
            except Exception as e:
                results.append({
                    "service": service,
                    "success": False,
                    "error": str(e)
                })
        
        # Логируем
        if db is not None:
            db.logs.insert_one({
                "type": "services_reloaded",
                "timestamp": datetime.utcnow(),
                "details": f"Reloaded {len([r for r in results if r['success']])} of {len(services)} services"
            })
        
        return jsonify({
            "success": True,
            "services_reloaded": len([r for r in results if r['success']]),
            "total_services": len(services),
            "results": results
        })
    except Exception as e:
        logger.error(f"Error reloading services: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Синхронизировать службы
@app.route('/api/services/sync', methods=['POST'])
def sync_services():
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        result = manager.sync_services()
        
        # Логируем
        if db is not None and result.get('success'):
            db.logs.insert_one({
                "type": "services_synced",
                "timestamp": datetime.utcnow(),
                "details": f"Created {result.get('services_created', 0)} services for {result.get('total_users', 0)} users"
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error syncing services: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Управление службой пользователя
@app.route('/api/users/<user_id>/service/toggle', methods=['POST'])
def toggle_user_service(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        data = request.json
        enable = data.get('enable', True)
        
        result = manager.toggle_user_service(user_id, enable)
        
        if result.get('success'):
            # Логируем
            if db is not None:
                db.logs.insert_one({
                    "type": "service_toggled",
                    "user_id": user_id,
                    "username": result.get('username'),
                    "timestamp": datetime.utcnow(),
                    "details": f"Service {result.get('service')} {result.get('action')}"
                })
            
            return jsonify(result)
        else:
            return jsonify({"success": False, "message": result.get('error', 'Failed to toggle service')}), 500
    except Exception as e:
        logger.error(f"Error toggling user service: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Управление отдельной службой (POST)
@app.route('/api/service/control', methods=['POST'])
def control_service_post():
    """Универсальный эндпоинт для управления службами через POST"""
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        data = request.json
        service_name = data.get('service')
        action = data.get('action', 'status')  # start, stop, restart, status
        
        if not service_name:
            return jsonify({"success": False, "message": "Service name is required"}), 400
        
        if action == 'status':
            result = manager.service_manager.get_service_status(service_name)
        else:
            result = manager.service_manager.manage_service(service_name, action)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error controlling service {service_name}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Управление отдельной службой (GET)
@app.route('/api/service/control', methods=['GET'])
def control_service_get():
    """Универсальный эндпоинт для управления службами через GET параметры"""
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
        
        service_name = request.args.get('service')
        action = request.args.get('action', 'status')
        
        if not service_name:
            return jsonify({"success": False, "message": "Service name is required"}), 400
        
        if action == 'status':
            result = manager.service_manager.get_service_status(service_name)
        else:
            result = manager.service_manager.manage_service(service_name, action)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error controlling service: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Получить логи службы
@app.route('/api/services/<service_name>/logs', methods=['GET'])
def get_service_logs(service_name):
    """Получает логи службы"""
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
        
        lines = int(request.args.get('lines', 100))
        
        # Получаем логи через journalctl
        try:
            # Пробуем через nsenter для доступа к хостовому journald
            cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'journalctl', '-u', service_name, '--no-pager', '-n', str(lines)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Если nsenter не сработал, пробуем прямой вызов
            if result.returncode != 0:
                result = subprocess.run(
                    ['journalctl', '-u', service_name, '--no-pager', '-n', str(lines)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode == 0:
                return jsonify({
                    "success": True,
                    "service": service_name,
                    "logs": result.stdout,
                    "lines": lines
                })
            else:
                # Если нет логов, возвращаем информативное сообщение
                return jsonify({
                    "success": True,
                    "service": service_name,
                    "logs": f"No logs available for {service_name} or service not found",
                    "lines": lines
                })
                
        except subprocess.TimeoutExpired:
            return jsonify({
                "success": False,
                "message": "Timeout while fetching logs"
            }), 504
        except Exception as e:
            logger.error(f"Error getting logs via journalctl: {e}")
            return jsonify({
                "success": False,
                "message": str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting service logs: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Альтернативный эндпоинт для логов (для обратной совместимости)
@app.route('/api/service/logs', methods=['GET'])
def get_service_logs_alt():
    """Альтернативный эндпоинт для получения логов службы"""
    service_name = request.args.get('service')
    if not service_name:
        return jsonify({"success": False, "message": "Service name is required"}), 400
    
    # Перенаправляем на основной эндпоинт
    return get_service_logs(service_name)

# Получить статус службы пользователя (GET версия)
@app.route('/api/users/<user_id>/service/status', methods=['GET'])
def get_user_service_status(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        from bson import ObjectId
        
        # Получаем пользователя
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
            
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        username = user.get('username')
        if not username:
            return jsonify({"success": False, "message": "Username not found"}), 400
        
        # Получаем статус службы
        service_name = f"shadowsocks-{username}.service"
        result = manager.service_manager.get_service_status(service_name)
        
        if result.get('success'):
            return jsonify({
                "success": True,
                "username": username,
                "service_name": service_name,
                "status": result
            })
        else:
            return jsonify({"success": False, "message": result.get('error', 'Service not found')}), 404
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Получить статус службы пользователя (POST версия для фронтенда)
@app.route('/api/users/service/status', methods=['POST'])
def get_user_service_status_post():
    """GET статуса службы пользователя через POST (для фронтенда)"""
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
            
        if not request.is_json:
            return jsonify({"success": False, "message": "Missing JSON"}), 400
        
        data = request.json
        username = data.get('username')
        
        if not username:
            return jsonify({"success": False, "message": "Username is required"}), 400
        
        # Получаем статус службы
        service_name = f"shadowsocks-{username}.service"
        result = manager.service_manager.get_service_status(service_name)
        
        if result.get('success'):
            return jsonify({
                "success": True,
                "username": username,
                "service_name": service_name,
                "status": result
            })
        else:
            return jsonify({"success": False, "message": result.get('error', 'Service not found')}), 404
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Перезапустить службу пользователя
@app.route('/api/users/<user_id>/service/restart', methods=['POST'])
def restart_user_service(user_id):
    try:
        if manager is None:
            return jsonify({"success": False, "message": "Manager not initialized"}), 500
        
        from bson import ObjectId
        
        # Получаем пользователя
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
            
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        username = user.get('username')
        if not username:
            return jsonify({"success": False, "message": "Username not found"}), 400
        
        # Перезапускаем службу
        service_name = f"shadowsocks-{username}.service"
        result = manager.service_manager.manage_service(service_name, "restart")
        
        if result.get('success'):
            # Логируем перезапуск
            if db is not None:
                db.logs.insert_one({
                    "type": "service_restarted",
                    "user_id": user_id,
                    "username": username,
                    "timestamp": datetime.utcnow(),
                    "details": f"Service {service_name} restarted"
                })
            
            return jsonify({
                "success": True,
                "message": f"Service {service_name} restarted",
                "service_name": service_name,
                "username": username
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Failed to restart service: {result.get('error', 'Unknown error')}"
            }), 500
            
    except Exception as e:
        logger.error(f"Error restarting service: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== СТАТИСТИКА СЕРВЕРА ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total_users = 0
        active_users = 0
        total_used = 0
        total_limit = 0
        
        if db is not None:
            # Статистика пользователей
            total_users = db.users.count_documents({})
            
            # Находим активных пользователей
            now = datetime.utcnow()
            active_users = db.users.count_documents({
                "enable": True,
                "$or": [
                    {"expires_at": {"$gt": now}},
                    {"expires_at": {"$exists": False}}
                ]
            })
            
            # Трафик
            pipeline = [
                {"$group": {
                    "_id": None,
                    "total_used": {"$sum": "$traffic_used"},
                    "total_limit": {"$sum": "$traffic_limit"}
                }}
            ]
            traffic_stats = list(db.users.aggregate(pipeline))
            
            if traffic_stats:
                total_used = traffic_stats[0]['total_used']
                total_limit = traffic_stats[0]['total_limit']
        
        # Системная статистика
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        
        # Статус служб
        services_status = {}
        if manager is not None:
            try:
                services_result = manager.get_all_services_status()
                if services_result.get('success'):
                    services_status = {
                        "total_services": services_result.get('total_services', 0),
                        "admin_service": manager.service_manager.admin_service,
                        "active_services": len([s for s in services_result.get('services_status', []) 
                                              if s.get('status', {}).get('active', False)])
                    }
            except:
                pass
        
        # Проверяем статус основной службы
        admin_service_status = "unknown"
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "shadowsocks.service"],
                capture_output=True,
                text=True
            )
            admin_service_status = "running" if result.returncode == 0 else "stopped"
        except:
            pass
        
        return jsonify({
            "success": True,
            "stats": {
                "server": {
                    "ip": Config.SS_SERVER_IP,
                    "hostname": os.uname().nodename if hasattr(os, 'uname') else "docker-container",
                    "db_status": "connected" if db is not None else "disconnected",
                    "manager_status": "connected" if manager is not None else "disconnected"
                },
                "users": {
                    "total": total_users,
                    "active": active_users
                },
                "traffic": {
                    "total_used_gb": round(total_used / 1024**3, 2),
                    "total_limit_gb": round(total_limit / 1024**3, 2)
                },
                "system": {
                    "cpu_usage": round(cpu_usage, 1),
                    "memory_usage": round(memory.percent, 1),
                    "memory_total_gb": round(memory.total / 1024**3, 2),
                    "memory_used_gb": round(memory.used / 1024**3, 2)
                },
                "services": services_status,
                "admin_service": admin_service_status
            }
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== МОНИТОРИНГ ТРАФИКА ====================

@app.route('/api/traffic-stream')
def traffic_stream():
    def generate():
        last_id = 0
        while True:
            try:
                # Получаем данные о трафике
                if db is not None:
                    users = list(db.users.find({}, {
                        'username': 1, 
                        'traffic_used': 1, 
                        'traffic_limit': 1,
                        'port': 1,
                        'enable': 1,
                        'updated_at': 1
                    }).sort('updated_at', -1).limit(10))
                    
                    traffic_data = []
                    for user in users:
                        traffic_data.append({
                            'user_id': str(user['_id']),
                            'username': user.get('username'),
                            'port': user.get('port'),
                            'enabled': user.get('enable', True),
                            'traffic_used_gb': round(user.get('traffic_used', 0) / 1024**3, 3),
                            'traffic_limit_gb': round(user.get('traffic_limit', 0) / 1024**3, 2),
                            'updated_at': user.get('updated_at', datetime.utcnow()).isoformat()
                        })
                    
                    # Получаем общий трафик
                    pipeline = [
                        {"$group": {
                            "_id": None,
                            "total_used": {"$sum": "$traffic_used"},
                            "total_limit": {"$sum": "$traffic_limit"}
                        }}
                    ]
                    total_stats = list(db.users.aggregate(pipeline))
                    
                    total_traffic = {
                        'total_used_gb': round(total_stats[0]['total_used'] / 1024**3, 2) if total_stats else 0,
                        'total_limit_gb': round(total_stats[0]['total_limit'] / 1024**3, 2) if total_stats else 0,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    # Сохраняем в историю
                    traffic_history.append({
                        'timestamp': datetime.utcnow(),
                        'total_used_gb': total_traffic['total_used_gb'],
                        'user_count': len(users)
                    })
                    
                    # Ограничиваем историю
                    if len(traffic_history) > 100:
                        traffic_history.pop(0)
                    
                    data = {
                        'type': 'traffic_update',
                        'data': {
                            'users': traffic_data,
                            'total': total_traffic,
                            'history': [{
                                'timestamp': h['timestamp'].isoformat(),
                                'total_used_gb': h['total_used_gb']
                            } for h in traffic_history[-20:]]  # Последние 20 записей
                        }
                    }
                    
                    yield f"data: {json.dumps(data, cls=MongoJSONEncoder)}\n\n"
                
                time.sleep(5)  # Обновление каждые 5 секунд
                
            except Exception as e:
                logger.error(f"Error in traffic stream: {e}")
                error_data = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                time.sleep(10)
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/api/traffic/history', methods=['GET'])
def get_traffic_history():
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
        
        days = int(request.args.get('days', 7))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Группируем по дням
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_date},
                    "type": "traffic_daily"
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$timestamp"
                        }
                    },
                    "total_used_gb": {"$sum": "$total_used_gb"},
                    "average_usage": {"$avg": "$average_usage"},
                    "user_count": {"$avg": "$user_count"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]
        
        history = list(db.logs.aggregate(pipeline))
        
        # Форматируем результат
        formatted_history = []
        for item in history:
            formatted_history.append({
                'date': item['_id'],
                'total_used_gb': round(item['total_used_gb'], 2),
                'average_usage': round(item['average_usage'], 1),
                'user_count': int(item['user_count'])
            })
        
        return jsonify({
            "success": True,
            "history": formatted_history,
            "days": days
        })
    except Exception as e:
        logger.error(f"Error getting traffic history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== УВЕДОМЛЕНИЯ ====================

@app.route('/api/notifications/check', methods=['POST'])
def check_notifications():
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
        
        notifications = []
        now = datetime.utcnow()
        
        # Проверяем пользователей с истекающим сроком
        users_expiring = list(db.users.find({
            "enable": True,
            "expires_at": {"$gt": now, "$lt": now + timedelta(days=3)},
            "notified_expire": {"$ne": True}
        }))
        
        for user in users_expiring:
            expires_at = user.get('expires_at')
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            days_left = (expires_at - now).days
            
            notification = {
                'type': 'expire_soon',
                'user_id': str(user['_id']),
                'username': user.get('username'),
                'email': user.get('email'),
                'days_left': days_left,
                'expires_at': expires_at.isoformat() if isinstance(expires_at, datetime) else str(expires_at),
                'message': f"User {user.get('username')} expires in {days_left} days"
            }
            notifications.append(notification)
            
            # Отправляем email если есть
            if user.get('email'):
                send_expiration_email(
                    email=user['email'],
                    username=user['username'],
                    days_left=days_left,
                    expires_at=expires_at
                )
            
            # Помечаем как уведомленного
            db.users.update_one(
                {"_id": user['_id']},
                {"$set": {"notified_expire": True}}
            )
        
        # Проверяем пользователей с почти исчерпанным трафиком (>90%)
        users_high_traffic = list(db.users.find({
            "enable": True,
            "traffic_limit": {"$gt": 0},
            "notified_traffic": {"$ne": True}
        }))
        
        for user in users_high_traffic:
            traffic_used = user.get('traffic_used', 0)
            traffic_limit = user.get('traffic_limit', 1)
            usage_percent = (traffic_used / traffic_limit) * 100
            
            if usage_percent > 90:
                notification = {
                    'type': 'traffic_high',
                    'user_id': str(user['_id']),
                    'username': user.get('username'),
                    'email': user.get('email'),
                    'usage_percent': round(usage_percent, 1),
                    'traffic_used_gb': round(traffic_used / 1024**3, 2),
                    'traffic_limit_gb': round(traffic_limit / 1024**3, 2),
                    'message': f"User {user.get('username')} has used {round(usage_percent, 1)}% of traffic"
                }
                notifications.append(notification)
                
                # Отправляем email если есть
                if user.get('email'):
                    send_traffic_warning_email(
                        email=user['email'],
                        username=user['username'],
                        usage_percent=round(usage_percent, 1),
                        traffic_used_gb=round(traffic_used / 1024**3, 2),
                        traffic_limit_gb=round(traffic_limit / 1024**3, 2)
                    )
                
                # Помечаем как уведомленного
                db.users.update_one(
                    {"_id": user['_id']},
                    {"$set": {"notified_traffic": True}}
                )
        
        # Проверяем истекших пользователей
        users_expired = list(db.users.find({
            "enable": True,
            "expires_at": {"$lt": now},
            "notified_expired": {"$ne": True}
        }))
        
        for user in users_expired:
            notification = {
                'type': 'expired',
                'user_id': str(user['_id']),
                'username': user.get('username'),
                'email': user.get('email'),
                'message': f"User {user.get('username')} has expired"
            }
            notifications.append(notification)
            
            # Отправляем email если есть
            if user.get('email'):
                send_expired_email(
                    email=user['email'],
                    username=user['username']
                )
            
            # Помечаем как уведомленного
            db.users.update_one(
                {"_id": user['_id']},
                {"$set": {"notified_expired": True}}
            )
        
        # Сохраняем уведомления в лог
        for notification in notifications:
            db.logs.insert_one({
                "type": "notification",
                "notification_type": notification['type'],
                "user_id": notification['user_id'],
                "username": notification['username'],
                "message": notification['message'],
                "timestamp": datetime.utcnow()
            })
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "count": len(notifications)
        })
        
    except Exception as e:
        logger.error(f"Error checking notifications: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/notifications/history', methods=['GET'])
def get_notifications_history():
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
        
        limit = int(request.args.get('limit', 50))
        notifications = list(db.logs.find(
            {"type": "notification"},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
        
        # Преобразуем ObjectId и datetime
        for notif in notifications:
            if 'timestamp' in notif and isinstance(notif['timestamp'], datetime):
                notif['timestamp'] = notif['timestamp'].isoformat()
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "count": len(notifications)
        })
    except Exception as e:
        logger.error(f"Error getting notifications history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== ЭКСПОРТ КОНФИГОВ ====================

@app.route('/api/users/<user_id>/download', methods=['GET'])
def download_config(user_id):
    try:
        if db is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
            
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Формируем правильный SS URI
        config_string = f"{user['method']}:{user['password']}@{Config.SS_SERVER_IP}:{user['port']}"
        encoded_string = base64.b64encode(config_string.encode()).decode()
        correct_ss_uri = f"ss://{encoded_string}"
        
        config_content = f"""# Shadowsocks Configuration
server={Config.SS_SERVER_IP}
server_port={user['port']}
password={user['password']}
method={user['method']}
timeout=300
mode=tcp_and_udp

# Generated by Shadowsocks Manager
# Username: {user.get('username', 'N/A')}
# Email: {user.get('email', 'N/A')}
# Created: {user.get('created_at', 'N/A')}
# Expires: {user.get('expires_at', 'Never')}
# Traffic Used: {round(user.get('traffic_used', 0) / 1024**3, 2)} GB / {round(user.get('traffic_limit', 0) / 1024**3, 2)} GB
# Service: shadowsocks-{user.get('username', 'N/A')}.service

# For quick import: {correct_ss_uri}
# Configuration string: {config_string}
# Base64 encoded: {encoded_string}
"""
        
        from io import BytesIO
        buffer = BytesIO()
        buffer.write(config_content.encode('utf-8'))
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"shadowsocks_{user.get('username', user_id)}.conf",
            mimetype='text/plain'
        )
    except Exception as e:
        logger.error(f"Error downloading config: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        db_status = "connected" if db is not None else "disconnected"
        if db is not None:
            try:
                db.command('ping')
                db_status = "connected"
            except:
                db_status = "disconnected"
        
        manager_status = "connected" if manager is not None else "disconnected"
        
        # Проверяем доступность systemd
        systemd_available = False
        try:
            result = subprocess.run(["systemctl", "--version"], capture_output=True, text=True)
            systemd_available = result.returncode == 0
        except:
            pass
        
        # Проверяем основную службу
        admin_service_status = "unknown"
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "shadowsocks.service"],
                capture_output=True,
                text=True
            )
            admin_service_status = "running" if result.returncode == 0 else "stopped"
        except:
            pass
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "mongodb": db_status,
                "config_manager": manager_status,
                "api": "running",
                "notifications": "running" if db is not None else "stopped",
                "traffic_stream": "available",
                "systemd": "available" if systemd_available else "unavailable",
                "admin_service": admin_service_status
            },
            "version": "4.0.0",
            "features": [
                "user_management",
                "hybrid_services",
                "admin_service",
                "individual_services",
                "traffic_monitoring",
                "notifications",
                "config_export",
                "real_time_updates",
                "service_management",
                "systemd_integration"
            ]
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }), 500

# ==================== EMAIL ФУНКЦИИ ====================

def send_welcome_email(email, username, server, port, password, method, expires_days):
    """Отправка приветственного email с конфигурацией"""
    try:
        smtp_config = {
            'host': os.getenv('SMTP_HOST', ''),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        }
        
        # Если SMTP не настроен, просто логируем
        if not smtp_config['username']:
            logger.info(f"Would send welcome email to {email} for user {username}")
            return
        
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = smtp_config['username']
        msg['To'] = email
        msg['Subject'] = f"Your Shadowsocks Configuration - {username}"
        
        # Формируем правильный SS URI
        config_string = f"{method}:{password}@{server}:{port}"
        encoded_string = base64.b64encode(config_string.encode()).decode()
        ss_url = f"ss://{encoded_string}"
        ss_url_with_comment = f"ss://{encoded_string}#{username}"
        
        body = f"""
        <h2>Welcome to Shadowsocks Service!</h2>
        <p>Your account has been created successfully.</p>
        
        <h3>Account Details:</h3>
        <ul>
            <li><strong>Username:</strong> {username}</li>
            <li><strong>Server:</strong> {server}</li>
            <li><strong>Port:</strong> {port}</li>
            <li><strong>Password:</strong> {password}</li>
            <li><strong>Encryption:</strong> {method}</li>
            <li><strong>Validity:</strong> {expires_days} days</li>
            <li><strong>Service Name:</strong> shadowsocks-{username}.service</li>
        </ul>
        
        <h3>Quick Connect URL:</h3>
        <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; word-break: break-all;">
            {ss_url_with_comment}
        </p>
        
        <h3>Configuration String:</h3>
        <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; word-break: break-all;">
            {config_string}
        </p>
        
        <h3>Base64 Encoded:</h3>
        <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; word-break: break-all;">
            {encoded_string}
        </p>
        
        <p>You can download the full configuration file from the Shadowsocks Manager panel.</p>
        
        <p>Best regards,<br>
        Shadowsocks Manager</p>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Отправляем email
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config['use_tls']:
                server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        logger.info(f"Welcome email sent to {email}")
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")

def send_expiration_email(email, username, days_left, expires_at):
    """Уведомление о скором истечении срока"""
    try:
        smtp_config = {
            'host': os.getenv('SMTP_HOST', ''),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        }
        
        if not smtp_config['username']:
            logger.info(f"Would send expiration email to {email} for user {username}")
            return
        
        msg = MIMEMultipart()
        msg['From'] = smtp_config['username']
        msg['To'] = email
        msg['Subject'] = f"Shadowsocks Account Expiring Soon - {username}"
        
        body = f"""
        <h2>Account Expiration Notice</h2>
        
        <p>Your Shadowsocks account <strong>{username}</strong> will expire in <strong>{days_left} days</strong>.</p>
        
        <p><strong>Expiration Date:</strong> {expires_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(expires_at, datetime) else expires_at}</p>
        
        <p>Please renew your account to avoid service interruption.</p>
        
        <p>You can extend your account from the Shadowsocks Manager panel.</p>
        
        <p>Best regards,<br>
        Shadowsocks Manager</p>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config['use_tls']:
                server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        logger.info(f"Expiration email sent to {email}")
        
    except Exception as e:
        logger.error(f"Error sending expiration email: {e}")

def send_traffic_warning_email(email, username, usage_percent, traffic_used_gb, traffic_limit_gb):
    """Уведомление о высоком использовании трафика"""
    try:
        smtp_config = {
            'host': os.getenv('SMTP_HOST', ''),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        }
        
        if not smtp_config['username']:
            logger.info(f"Would send traffic warning to {email} for user {username}")
            return
        
        msg = MIMEMultipart()
        msg['From'] = smtp_config['username']
        msg['To'] = email
        msg['Subject'] = f"High Traffic Usage Alert - {username}"
        
        body = f"""
        <h2>High Traffic Usage Alert</h2>
        
        <p>Your Shadowsocks account <strong>{username}</strong> has used <strong>{usage_percent}%</strong> of its allocated traffic.</p>
        
        <h3>Usage Details:</h3>
        <ul>
            <li><strong>Traffic Used:</strong> {traffic_used_gb} GB</li>
            <li><strong>Traffic Limit:</strong> {traffic_limit_gb} GB</li>
            <li><strong>Remaining:</strong> {traffic_limit_gb - traffic_used_gb:.2f} GB</li>
            <li><strong>Usage Percentage:</strong> {usage_percent}%</li>
        </ul>
        
        <p>When you reach 100% usage, your account will be temporarily suspended until the next billing cycle or until you purchase additional traffic.</p>
        
        <p>You can monitor your usage and purchase additional traffic from the Shadowsocks Manager panel.</p>
        
        <p>Best regards,<br>
        Shadowsocks Manager</p>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config['use_tls']:
                server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        logger.info(f"Traffic warning email sent to {email}")
        
    except Exception as e:
        logger.error(f"Error sending traffic warning email: {e}")

def send_expired_email(email, username):
    """Уведомление об истечении срока"""
    try:
        smtp_config = {
            'host': os.getenv('SMTP_HOST', ''),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        }
        
        if not smtp_config['username']:
            logger.info(f"Would send expired email to {email} for user {username}")
            return
        
        msg = MIMEMultipart()
        msg['From'] = smtp_config['username']
        msg['To'] = email
        msg['Subject'] = f"Account Expired - {username}"
        
        body = f"""
        <h2>Account Expired</h2>
        
        <p>Your Shadowsocks account <strong>{username}</strong> has expired.</p>
        
        <p>Your access to the service has been suspended. To restore access, please renew your account.</p>
        
        <p>You can renew your account from the Shadowsocks Manager panel.</p>
        
        <p>Best regards,<br>
        Shadowsocks Manager</p>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            if smtp_config['use_tls']:
                server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        logger.info(f"Expired email sent to {email}")
        
    except Exception as e:
        logger.error(f"Error sending expired email: {e}")

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================

def background_notifications_check():
    """Периодическая проверка уведомлений"""
    while True:
        try:
            if db is not None:
                # Проверяем каждые 15 минут
                time.sleep(900)
                
                # Выполняем проверку
                now = datetime.utcnow()
                
                # Проверяем пользователей с истекающим сроком
                users_expiring = list(db.users.find({
                    "enable": True,
                    "expires_at": {"$gt": now, "$lt": now + timedelta(days=3)},
                    "notified_expire": {"$ne": True}
                }))
                
                for user in users_expiring:
                    # Логируем но не отправляем email в фоновом режиме
                    logger.info(f"User {user.get('username')} expires soon")
                    
                    # Помечаем как уведомленного
                    db.users.update_one(
                        {"_id": user['_id']},
                        {"$set": {"notified_expire": True}}
                    )
                
                # Ежедневная статистика
                if now.hour == 0 and now.minute < 5:  # Полночь
                    # Сохраняем ежедневную статистику
                    pipeline = [
                        {"$group": {
                            "_id": None,
                            "total_used": {"$sum": "$traffic_used"},
                            "total_limit": {"$sum": "$traffic_limit"},
                            "avg_usage": {"$avg": {"$divide": ["$traffic_used", "$traffic_limit"]}},
                            "user_count": {"$sum": 1}
                        }}
                    ]
                    
                    stats = list(db.users.aggregate(pipeline))
                    if stats:
                        db.logs.insert_one({
                            "type": "traffic_daily",
                            "timestamp": now,
                            "total_used_gb": round(stats[0]['total_used'] / 1024**3, 2),
                            "total_limit_gb": round(stats[0]['total_limit'] / 1024**3, 2),
                            "average_usage": round(stats[0].get('avg_usage', 0) * 100, 1),
                            "user_count": stats[0]['user_count']
                        })
                        logger.info(f"Daily traffic stats saved")
                
        except Exception as e:
            logger.error(f"Error in background notifications: {e}")
            time.sleep(60)

# Запускаем фоновые задачи
if db is not None:
    notification_thread = threading.Thread(target=background_notifications_check, daemon=True)
    notification_thread.start()
    logger.info("Background notifications thread started")

# ==================== ОБРАБОТЧИКИ ОШИБОК ====================

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server Error: {error}")
    return jsonify({"success": False, "message": "Internal server error"}), 500

# ==================== ЗАПУСК СЕРВЕРА ====================

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    
    logger.info(f"Starting API server on {host}:{port}")
    logger.info(f"Features enabled: Hybrid services (Admin + Individual)")
    
    # Инициализация при запуске
    if manager is not None and db is not None:
        try:
            logger.info("Initializing admin service...")
            init_result = manager.initialize_admin()
            if init_result.get('success'):
                logger.info(f"✓ Admin service initialized: {manager.service_manager.admin_service}")
            else:
                logger.warning(f"✗ Admin initialization failed: {init_result.get('error', 'Unknown error')}")
            
            logger.info("Syncing existing users to services...")
            sync_result = manager.sync_services()
            if sync_result.get('success'):
                logger.info(f"✓ Synced {sync_result.get('services_created', 0)} services")
            else:
                logger.warning(f"✗ Service sync failed: {sync_result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error during startup initialization: {e}")
    
    app.run(host=host, port=port, debug=False, threaded=True)