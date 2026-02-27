from datetime import datetime, timedelta
import json
import time

from flask import Response

from api.common import db, logger, MongoJSONEncoder

traffic_history = []


def stream_response():
    def generate():
        while True:
            try:
                if db is not None:
                    users = list(db.users.find({}, {
                        'username': 1,
                        'traffic_used': 1,
                        'traffic_limit': 1,
                        'port': 1,
                        'enable': 1,
                        'updated_at': 1,
                    }).sort('updated_at', -1).limit(10))

                    traffic_data = [{
                        'user_id': str(user['_id']),
                        'username': user.get('username'),
                        'port': user.get('port'),
                        'enabled': user.get('enable', True),
                        'traffic_used_gb': round(user.get('traffic_used', 0) / 1024**3, 3),
                        'traffic_limit_gb': round(user.get('traffic_limit', 0) / 1024**3, 2),
                        'updated_at': user.get('updated_at', datetime.utcnow()).isoformat(),
                    } for user in users]

                    total_stats = list(db.users.aggregate([
                        {'$group': {
                            '_id': None,
                            'total_used': {'$sum': '$traffic_used'},
                            'total_limit': {'$sum': '$traffic_limit'},
                        }}
                    ]))

                    total_traffic = {
                        'total_used_gb': round(total_stats[0]['total_used'] / 1024**3, 2) if total_stats else 0,
                        'total_limit_gb': round(total_stats[0]['total_limit'] / 1024**3, 2) if total_stats else 0,
                        'timestamp': datetime.utcnow().isoformat(),
                    }

                    traffic_history.append({
                        'timestamp': datetime.utcnow(),
                        'total_used_gb': total_traffic['total_used_gb'],
                    })
                    if len(traffic_history) > 100:
                        traffic_history.pop(0)

                    payload = {
                        'type': 'traffic_update',
                        'data': {
                            'users': traffic_data,
                            'total': total_traffic,
                            'history': [{'timestamp': h['timestamp'].isoformat(), 'total_used_gb': h['total_used_gb']} for h in traffic_history[-20:]],
                        },
                    }
                    yield f"data: {json.dumps(payload, cls=MongoJSONEncoder)}\n\n"

                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in traffic stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                time.sleep(10)

    return Response(generate(), mimetype='text/event-stream')


def get_history(days: int):
    start_date = datetime.utcnow() - timedelta(days=days)
    pipeline = [
        {'$match': {'timestamp': {'$gte': start_date}, 'type': 'traffic_daily'}},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp'}},
            'total_used_gb': {'$sum': '$total_used_gb'},
            'average_usage': {'$avg': '$average_usage'},
            'user_count': {'$avg': '$user_count'},
        }},
        {'$sort': {'_id': 1}},
    ]
    history = list(db.logs.aggregate(pipeline)) if db is not None else []
    return [{
        'date': item['_id'],
        'total_used_gb': round(item['total_used_gb'], 2),
        'average_usage': round(item['average_usage'], 1),
        'user_count': int(item['user_count']),
    } for item in history]
