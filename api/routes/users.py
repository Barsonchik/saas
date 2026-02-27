from datetime import datetime
from flask import Blueprint, jsonify, request
from bson import ObjectId

from api.common import db, manager
from api.config import Config
from api.services.email_service import send_welcome_email

users_bp = Blueprint('users', __name__)


@users_bp.route('/api/users', methods=['GET'])
def get_users():
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    users = list(db.users.find({}, {'password': 0}))
    for user in users:
        expires_at = user.get('expires_at')
        if isinstance(expires_at, datetime):
            user['days_remaining'] = max(0, (expires_at - datetime.utcnow()).days)
            user['expires_at'] = expires_at.isoformat()
        user['traffic_used_gb'] = round(user.get('traffic_used', 0) / 1024**3, 2)
        user['traffic_limit_gb'] = round(user.get('traffic_limit', 0) / 1024**3, 2)
        user['traffic_percent'] = round((user['traffic_used_gb'] / user['traffic_limit_gb']) * 100, 1) if user['traffic_limit_gb'] > 0 else 0
        user['is_active'] = user.get('enable', True)
        if user.get('username'):
            user['service_name'] = f"shadowsocks-{user['username']}.service"
        user['_id'] = str(user['_id'])
    return jsonify({'success': True, 'users': users})


@users_bp.route('/api/users', methods=['POST'])
def add_user():
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    data = request.json or {}
    if not data.get('username'):
        return jsonify({'success': False, 'message': 'Username is required'}), 400

    result = manager.add_user(
        username=data.get('username'),
        email=data.get('email', ''),
        traffic_limit_gb=data.get('traffic_limit_gb', 10),
        duration_days=data.get('duration_days', 30),
        method=data.get('method', Config.SS_METHOD),
    )
    if result.get('success') and data.get('email'):
        send_welcome_email(data['email'], data['username'], Config.SS_SERVER_IP, result.get('port'), result.get('password'), result.get('method'), data.get('duration_days', 30))
    return jsonify(result), (200 if result.get('success') else 500)


@users_bp.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    result = manager.delete_user(user_id)
    return jsonify(result), (200 if result.get('success') else 404)


@users_bp.route('/api/users/<user_id>/reset-traffic', methods=['POST'])
def reset_traffic(user_id):
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    result = manager.reset_user_traffic(user_id)
    return jsonify(result), (200 if result.get('success') else 404)


@users_bp.route('/api/users/<user_id>/extend', methods=['POST'])
def extend_user(user_id):
    if manager is None:
        return jsonify({'success': False, 'message': 'Manager not initialized'}), 500
    additional_days = (request.json or {}).get('additional_days', 30)
    result = manager.extend_user_expiration(user_id, additional_days)
    return jsonify(result), (200 if result.get('success') else 404)


@users_bp.route('/api/users/<user_id>/config', methods=['GET'])
def get_user_config(user_id):
    import base64
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    config_string = f"{user['method']}:{user['password']}@{Config.SS_SERVER_IP}:{user['port']}"
    encoded = base64.b64encode(config_string.encode()).decode()
    return jsonify({'success': True, 'config': {
        'server': Config.SS_SERVER_IP,
        'port': user['port'],
        'password': user['password'],
        'method': user['method'],
        'ss_url': f'ss://{encoded}',
        'ss_url_with_comment': f"ss://{encoded}#{user.get('username', 'user')}",
    }})
