import base64
from io import BytesIO
from flask import Blueprint, jsonify, send_file
from bson import ObjectId

from api.common import db
from api.config import Config

config_export_bp = Blueprint('config_export', __name__)


@config_export_bp.route('/api/users/<user_id>/download', methods=['GET'])
def download_config(user_id):
    if db is None:
        return jsonify({'success': False, 'message': 'Database not connected'}), 500
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    config_string = f"{user['method']}:{user['password']}@{Config.SS_SERVER_IP}:{user['port']}"
    encoded = base64.b64encode(config_string.encode()).decode()
    uri = f"ss://{encoded}"

    content = f"""# Shadowsocks Configuration
server={Config.SS_SERVER_IP}
server_port={user['port']}
password={user['password']}
method={user['method']}
# For quick import: {uri}
"""
    buffer = BytesIO(content.encode('utf-8'))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"shadowsocks_{user.get('username', user_id)}.conf", mimetype='text/plain')
