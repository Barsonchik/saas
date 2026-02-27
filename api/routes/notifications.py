from datetime import datetime
from flask import Blueprint, jsonify

from api.common import db
from api.services.notification_service import check_notifications_logic

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/notifications/check', methods=['POST'])
def check_notifications():
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    notifications = check_notifications_logic()
    return jsonify({'success': True, 'notifications': notifications, 'count': len(notifications)})


@notifications_bp.route('/api/notifications/history', methods=['GET'])
def notifications_history():
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    from flask import request
    limit = int(request.args.get('limit', 50))
    items = list(db.logs.find({'type': 'notification'}, {'_id': 0}).sort('timestamp', -1).limit(limit))
    for item in items:
        if 'timestamp' in item and isinstance(item['timestamp'], datetime):
            item['timestamp'] = item['timestamp'].isoformat()
    return jsonify({'success': True, 'notifications': items, 'count': len(items)})
