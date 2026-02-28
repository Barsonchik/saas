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
    total_users = 0
    active_users = 0
    total_used = 0
    total_limit = 0

    try:
        if db is not None:
            total_users = db.users.count_documents({})
            now = datetime.utcnow()
            active_users = db.users.count_documents({'enable': True, '$or': [{'expires_at': {'$gt': now}}, {'expires_at': {'$exists': False}}]})
            traffic_stats = list(db.users.aggregate([{'$group': {'_id': None, 'total_used': {'$sum': '$traffic_used'}, 'total_limit': {'$sum': '$traffic_limit'}}}]))
            if traffic_stats:
                total_used = traffic_stats[0].get('total_used', 0)
                total_limit = traffic_stats[0].get('total_limit', 0)
    except Exception:
        pass

    cpu_usage = 0
    memory_usage = 0
    hostname = 'unknown'
    
    try:
        cpu_usage = psutil.cpu_percent(interval=0.2)
    except Exception:
        pass
    
    try:
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
    except Exception:
        pass

    try:
        hostname = os.uname().nodename if hasattr(os, 'uname') else 'docker-container'
    except Exception:
        hostname = 'docker-container'

    admin_service_status = 'unknown'
    active_services = 0
    total_services = 0
    
    try:
        if manager and hasattr(manager, 'get_all_services_status'):
            services_result = manager.get_all_services_status()
            if services_result.get('success'):
                total_services = services_result.get('total_services', 0)
                user_services = services_result.get('user_services', [])
                active_services = sum(1 for s in user_services if s.get('active', False))
    except Exception:
        pass
    
    try:
        result = subprocess.run(['systemctl', 'is-active', 'shadowsocks.service'], capture_output=True, text=True, timeout=5)
        admin_service_status = 'running' if result.returncode == 0 else 'stopped'
    except Exception:
        admin_service_status = 'unavailable'

    return jsonify({'success': True, 'stats': {
        'server': {'ip': Config.SS_SERVER_IP, 'hostname': hostname, 'db_status': 'connected' if db is not None else 'disconnected', 'manager_status': 'connected' if manager is not None else 'disconnected'},
        'users': {'total': total_users, 'active': active_users},
        'traffic': {'total_used_gb': round(total_used / 1024**3, 2), 'total_limit_gb': round(total_limit / 1024**3, 2)},
        'system': {'cpu_usage': round(cpu_usage, 1), 'memory_usage': round(memory_usage, 1)},
        'services': {'total_services': total_services, 'active_services': active_services},
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
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat(), 'services': {'mongodb': db_status, 'manager': 'connected' if manager else 'disconnected'}})
