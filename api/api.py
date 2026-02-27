import os
import threading
from flask import jsonify, send_file

from api.common import app, db, manager, logger
from api.routes.users import users_bp
from api.routes.services import services_bp
from api.routes.stats import stats_bp
from api.routes.notifications import notifications_bp
from api.routes.config_export import config_export_bp
from api.services.notification_service import background_notifications_check


@app.route('/')
def index():
    return send_file('../templates/index.html')


@app.route('/favicon.ico')
def favicon():
    return send_file('../static/favicon.ico')


app.register_blueprint(users_bp)
app.register_blueprint(services_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(config_export_bp)


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'success': False, 'message': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Server Error: {error}')
    return jsonify({'success': False, 'message': 'Internal server error'}), 500


if db is not None:
    notification_thread = threading.Thread(target=background_notifications_check, daemon=True)
    notification_thread.start()
    logger.info('Background notifications thread started')


if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')

    logger.info(f'Starting API server on {host}:{port}')
    if manager is not None and db is not None:
        try:
            manager.initialize_admin()
            manager.sync_services()
        except Exception as e:
            logger.error(f'Error during startup initialization: {e}')

    app.run(host=host, port=port, debug=False, threaded=True)
