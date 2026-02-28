from flask import Blueprint, jsonify, request
from bson import ObjectId
import subprocess

from api.common import manager, db

services_bp = Blueprint('services', __name__)


@services_bp.route('/api/admin/initialize', methods=['POST'])
def initialize_admin():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    return jsonify(manager.initialize_admin())


@services_bp.route('/api/services/status', methods=['GET'])
def services_status():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    return jsonify(manager.get_all_services_status())


@services_bp.route('/api/services/restart-all', methods=['POST'])
def restart_all():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    return jsonify(manager.restart_all_services())


@services_bp.route('/api/services/reload-all', methods=['POST'])
def reload_all():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    services = manager.service_manager.list_all_services()
    results = []
    for service in services:
        result = subprocess.run(['systemctl', 'reload', service], capture_output=True, text=True)
        results.append({'service': service, 'success': result.returncode == 0, 'output': result.stdout.strip(), 'error': result.stderr.strip()})
    return jsonify({'success': True, 'services_reloaded': len([r for r in results if r['success']]), 'total_services': len(services), 'results': results})


@services_bp.route('/api/services/sync', methods=['POST'])
def sync_services():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    return jsonify(manager.sync_services())


@services_bp.route('/api/users/<user_id>/service/toggle', methods=['POST'])
def toggle_service(user_id):
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    enable = (request.json or {}).get('enable', True)
    result = manager.toggle_user_service(user_id, enable)
    # Всегда возвращаем 200, чтобы фронтенд мог показать сообщение об ошибке
    return jsonify(result)


@services_bp.route('/api/users/<user_id>/service/restart', methods=['POST'])
def restart_user_service(user_id):
    if manager is None or db is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    username = user.get('username')
    service_name = manager.service_manager.admin_service if username == 'admin' else f"shadowsocks-{username}.service"
    result = manager.service_manager.manage_service(service_name, 'restart')
    return jsonify({'success': result.get('success', False), 'service_name': service_name, 'username': username, 'message': result.get('error', 'ok')})


@services_bp.route('/api/service/control', methods=['POST'])
def control_service():
    """Универсальный эндпоинт для управления службами (start, stop, restart, enable, disable, reload, status)"""
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    
    data = request.json or {}
    service_name = data.get('service')
    action = data.get('action')
    
    if not service_name:
        return jsonify({'success': False, 'message': 'Service name is required'}), 400
    
    if not action:
        return jsonify({'success': False, 'message': 'Action is required'}), 400
    
    # Валидация действия
    valid_actions = ['start', 'stop', 'restart', 'enable', 'disable', 'reload', 'status']
    if action not in valid_actions:
        return jsonify({'success': False, 'message': f'Invalid action. Must be one of: {", ".join(valid_actions)}'}), 400
    
    # Выполняем действие
    if action == 'status':
        result = manager.service_manager.get_service_status(service_name)
    else:
        result = manager.service_manager.manage_service(service_name, action)
    
    return jsonify(result)
