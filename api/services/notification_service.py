from datetime import datetime, timedelta
import time

from api.common import db, logger
from api.services.email_service import send_expiration_email, send_traffic_warning_email, send_expired_email


def check_notifications_logic():
    if db is None:
        return []

    notifications = []
    now = datetime.utcnow()

    users_expiring = list(db.users.find({
        'enable': True,
        'expires_at': {'$gt': now, '$lt': now + timedelta(days=3)},
        'notified_expire': {'$ne': True},
    }))
    for user in users_expiring:
        expires_at = user.get('expires_at')
        days_left = (expires_at - now).days if isinstance(expires_at, datetime) else 0
        notifications.append({
            'type': 'expire_soon',
            'user_id': str(user['_id']),
            'username': user.get('username'),
            'days_left': days_left,
            'expires_at': str(expires_at),
            'message': f"User {user.get('username')} expires in {days_left} days",
        })
        if user.get('email'):
            send_expiration_email(user['email'], user['username'], days_left, expires_at)
        db.users.update_one({'_id': user['_id']}, {'$set': {'notified_expire': True}})

    users_high_traffic = list(db.users.find({'enable': True, 'traffic_limit': {'$gt': 0}, 'notified_traffic': {'$ne': True}}))
    for user in users_high_traffic:
        used = user.get('traffic_used', 0)
        limit = user.get('traffic_limit', 1)
        usage_percent = (used / limit) * 100
        if usage_percent > 90:
            used_gb = round(used / 1024**3, 2)
            limit_gb = round(limit / 1024**3, 2)
            notifications.append({
                'type': 'traffic_high',
                'user_id': str(user['_id']),
                'username': user.get('username'),
                'usage_percent': round(usage_percent, 1),
                'message': f"User {user.get('username')} used {usage_percent:.1f}% traffic",
            })
            if user.get('email'):
                send_traffic_warning_email(user['email'], user['username'], usage_percent, used_gb, limit_gb)
            db.users.update_one({'_id': user['_id']}, {'$set': {'notified_traffic': True}})

    return notifications


def background_notifications_check():
    while True:
        try:
            if db is None:
                time.sleep(60)
                continue

            now = datetime.utcnow()
            check_notifications_logic()

            expired_users = list(db.users.find({'enable': True, 'expires_at': {'$lte': now}, 'notified_expired': {'$ne': True}}))
            for user in expired_users:
                db.users.update_one({'_id': user['_id']}, {'$set': {'enable': False, 'notified_expired': True}})
                if user.get('email'):
                    send_expired_email(user['email'], user.get('username', 'user'))

            if now.hour == 0 and now.minute < 5:
                stats = list(db.users.aggregate([{'$group': {
                    '_id': None,
                    'total_used': {'$sum': '$traffic_used'},
                    'total_limit': {'$sum': '$traffic_limit'},
                    'avg_usage': {'$avg': {'$divide': ['$traffic_used', '$traffic_limit']}},
                    'user_count': {'$sum': 1},
                }}]))
                if stats:
                    db.logs.insert_one({
                        'type': 'traffic_daily',
                        'timestamp': now,
                        'total_used_gb': round(stats[0]['total_used'] / 1024**3, 2),
                        'total_limit_gb': round(stats[0]['total_limit'] / 1024**3, 2),
                        'average_usage': round(stats[0].get('avg_usage', 0) * 100, 1),
                        'user_count': stats[0]['user_count'],
                    })
            time.sleep(300)
        except Exception as e:
            logger.error(f"Error in background notifications: {e}")
            time.sleep(60)
