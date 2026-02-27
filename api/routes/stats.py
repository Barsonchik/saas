from datetime import datetime
import os
import psutil
import subprocess
from flask import Blueprint, jsonify

from api.common import db, manager
from api.config import Config
from api.services.traffic_service import stream_response, get_history

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats', methods=['GET'])
def stats():
    total_users = db.users.count_documents({}) if db is not None else 0
    active_users = 0
    total_used = total_limit = 0

    if db is not None:
        now = datetime.utcnow()
        active_users = db.users.count_documents({'enable': True, '$or': [{'expires_at': {'$gt': now}}, {'expires_at': {'$exists': False}}]})
        traffic_stats = list(db.users.aggregate([{'$group': {'_id': None, 'total_used': {'$sum': '$traffic_used'}, 'total_limit': {'$sum': '$traffic_limit'}}}]))
        if traffic_stats:
            total_used = traffic_stats[0]['total_used']
            total_limit = traffic_stats[0]['total_limit']

    cpu_usage = psutil.cpu_percent(interval=0.2)
    memory = psutil.virtual_memory()

    admin_service_status = 'unknown'
    try:
        result = subprocess.run(['systemctl', 'is-active', 'shadowsocks.service'], capture_output=True, text=True)
        admin_service_status = 'running' if result.returncode == 0 else 'stopped'
    except Exception:
        pass

    return jsonify({'success': True, 'stats': {
        'server': {'ip': Config.SS_SERVER_IP, 'hostname': os.uname().nodename if hasattr(os, 'uname') else 'docker-container', 'db_status': 'connected' if db is not None else 'disconnected', 'manager_status': 'connected' if manager is not None else 'disconnected'},
        'users': {'total': total_users, 'active': active_users},
        'traffic': {'total_used_gb': round(total_used / 1024**3, 2), 'total_limit_gb': round(total_limit / 1024**3, 2)},
        'system': {'cpu_usage': round(cpu_usage, 1), 'memory_usage': round(memory.percent, 1)},
        'admin_service': admin_service_status,
    }})


@stats_bp.route('/api/traffic-stream')
def traffic_stream():
    return stream_response()


@stats_bp.route('/api/traffic/history', methods=['GET'])
def traffic_history():
    from flask import request
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    days = int(request.args.get('days', 7))
    return jsonify({'success': True, 'history': get_history(days), 'days': days})


@stats_bp.route('/api/health', methods=['GET'])
def health():
    db_status = 'connected' if db is not None else 'disconnected'
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat(), 'services': {'mongodb': db_status, 'manager': 'connected' if manager is not None else 'disconnected'}})
