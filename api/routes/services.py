from flask import Blueprint, jsonify, request
from bson import ObjectId
import subprocess

from api.common import manager, db, logger

services_bp = Blueprint('services', __name__)


def _service_action_result(service_name: str, action: str):
    if action == 'status':
        return manager.service_manager.get_service_status(service_name)
    return manager.service_manager.manage_service(service_name, action)


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
    return jsonify(result), (200 if result.get('success') else 500)


@services_bp.route('/api/service/control', methods=['POST'])
def control_service_post():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500

    data = request.json or {}
    service_name = data.get('service')
    action = data.get('action', 'status')

    if not service_name:
        return jsonify({'success': False, 'message': 'Service name is required'}), 400

    return jsonify(_service_action_result(service_name, action))


@services_bp.route('/api/service/control', methods=['GET'])
def control_service_get():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500

    service_name = request.args.get('service')
    action = request.args.get('action', 'status')

    if not service_name:
        return jsonify({'success': False, 'message': 'Service name is required'}), 400

    return jsonify(_service_action_result(service_name, action))


@services_bp.route('/api/services/<service_name>/logs', methods=['GET'])
def get_service_logs(service_name):
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500

    try:
        lines = int(request.args.get('lines', 100))
    except ValueError:
        return jsonify({'success': False, 'message': 'lines must be an integer'}), 400

    try:
        cmd = ['nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'journalctl', '-u', service_name, '--no-pager', '-n', str(lines)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            result = subprocess.run(['journalctl', '-u', service_name, '--no-pager', '-n', str(lines)], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return jsonify({'success': True, 'service': service_name, 'logs': result.stdout, 'lines': lines})

        return jsonify({'success': True, 'service': service_name, 'logs': f'No logs available for {service_name} or service not found', 'lines': lines})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Timeout while fetching logs'}), 504
    except Exception as exc:
        logger.error(f'Error getting service logs for {service_name}: {exc}')
        return jsonify({'success': False, 'message': str(exc)}), 500


@services_bp.route('/api/service/logs', methods=['GET'])
def get_service_logs_alias():
    service_name = request.args.get('service')
    if not service_name:
        return jsonify({'success': False, 'message': 'Service name is required'}), 400
    return get_service_logs(service_name)


@services_bp.route('/api/users/<user_id>/service/status', methods=['GET'])
def get_user_service_status(user_id):
    if manager is None or db is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500

    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    username = user.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Username not found'}), 400

    service_name = manager.service_manager.admin_service if username == 'admin' else f'shadowsocks-{username}.service'
    result = manager.service_manager.get_service_status(service_name)

    if result.get('success'):
        return jsonify({'success': True, 'username': username, 'service_name': service_name, 'status': result})
    return jsonify({'success': False, 'message': result.get('error', 'Service not found')}), 404


@services_bp.route('/api/users/service/status', methods=['POST'])
def get_user_service_status_post():
    if manager is None or db is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500

    data = request.json or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id is required'}), 400

    return get_user_service_status(user_id)


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
