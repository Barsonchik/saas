#!/bin/bash
set -e

echo "=========================================="
echo "Shadowsocks Manager Starting..."
echo "=========================================="

# Проверяем наличие nsenter
if command -v nsenter >/dev/null 2>&1; then
    echo "✓ nsenter установлен: $(nsenter --version | head -1)"
else
    echo "✗ nsenter не найден"
    echo "Установка util-linux для nsenter..."
    apt-get update && apt-get install -y util-linux
fi

# Создаем обертку с chroot для доступа к библиотекам хоста
cat > /usr/local/bin/hostctl << 'EOF'
#!/bin/bash
# Обертка для выполнения systemctl на хосте через chroot
# Используем chroot с доступом к хостовой файловой системе

# Пути к библиотекам хоста
HOST_ROOT="/host"
SYSTEMCTL_PATH="/usr/bin/systemctl"

# Проверяем доступность chroot пути
if [ ! -d "$HOST_ROOT" ]; then
    echo "ERROR: Host root not mounted at $HOST_ROOT" >&2
    echo "Please mount host filesystem with: -v /:/host:ro" >&2
    exit 127
fi

if [ ! -x "$HOST_ROOT$SYSTEMCTL_PATH" ]; then
    echo "ERROR: systemctl not found in host root" >&2
    exit 127
fi

# Выполняем команду через chroot
chroot "$HOST_ROOT" $SYSTEMCTL_PATH "$@"
EOF

chmod +x /usr/local/bin/hostctl

echo "✓ Created hostctl wrapper for systemctl"

# Инициализация базы данных
python3 -c "
import sys
import os
import time
import json
from pymongo import MongoClient
from datetime import datetime, timedelta

# URI для подключения к вашему контейнеру MongoDB
mongo_uri = os.getenv('MONGO_URI', 'mongodb://admin:firefly2007@155.212.224.2:27017/admin?authSource=admin&directConnection=true')
db_name = os.getenv('MONGO_DB', 'shadowsocks_db')
config_path = os.getenv('SHADOWSOCKS_CONFIG', '/etc/shadowsocks-libev/config.json')

print(f'Connecting to MongoDB: {mongo_uri}')
print(f'Database: {db_name}')
print(f'Shadowsocks config: {config_path}')

# Пробуем подключиться несколько раз
for i in range(30):
    try:
        # Подключение к MongoDB
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[db_name]
        print('✓ Connected to MongoDB')
        break
    except Exception as e:
        if i == 29:
            print(f'✗ MongoDB connection failed: {e}')
            print('⚠ Starting without MongoDB connection')
            sys.exit(1)
        print(f'Waiting for MongoDB... ({i+1}/30)')
        time.sleep(2)

# Создаем коллекции если не существуют
collections = ['users', 'connections', 'logs']
for coll in collections:
    if coll not in db.list_collection_names():
        db.create_collection(coll)
        print(f'✓ Created collection: {coll}')

# СИНХРОНИЗАЦИЯ: Загружаем пользователей из shadowsocks конфига
try:
    print(f'Loading users from {config_path}...')
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            ss_config = json.load(f)
        
        # Получаем порты и пароли
        port_password = {}
        if 'port_password' in ss_config:
            port_password = ss_config['port_password']
        elif 'password' in ss_config and 'server_port' in ss_config:
            # Один пользователь в старом формате
            port_password = {str(ss_config['server_port']): ss_config['password']}
        
        method = ss_config.get('method', 'aes-256-gcm')
        
        print(f'Found {len(port_password)} user(s) in config')
        
        # Синхронизируем с MongoDB
        users_updated = 0
        users_created = 0
        
        for port_str, password in port_password.items():
            port = int(port_str)
            
            # Проверяем существует ли пользователь с таким портом
            existing_user = db.users.find_one({'port': port})
            
            if existing_user:
                # Обновляем существующего пользователя
                db.users.update_one(
                    {'port': port},
                    {
                        '\$set': {
                            'password': password,
                            'method': method,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                users_updated += 1
                print(f'  ✓ Updated user on port {port}')
            else:
                # Создаем нового пользователя
                username = f'user_{port}'
                if port == 8388:
                    username = 'admin'
                
                user = {
                    'username': username,
                    'email': f'{username}@localhost',
                    'port': port,
                    'password': password,
                    'method': method,
                    'enable': True,
                    'traffic_limit': 100 * 1024**3,  # 100 GB
                    'traffic_used': 0,
                    'expires_at': datetime.utcnow() + timedelta(days=365),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                    'role': 'admin' if port == 8388 else 'user',
                    'notes': 'Imported from /etc/shadowsocks-libev/config.json',
                    'notified_expire': False,
                    'notified_traffic': False,
                    'notified_expired': False
                }
                
                db.users.insert_one(user)
                users_created += 1
                print(f'  ✓ Created user {username} on port {port}')
        
        user_count = db.users.count_documents({})
        print(f'✓ Database synchronization complete')
        print(f'  Total users in DB: {user_count}')
        print(f'  Created: {users_created}, Updated: {users_updated}')
        
    else:
        print(f'⚠ Config file not found: {config_path}')
        print('⚠ Starting with empty database')
        
except Exception as e:
    print(f'✗ Error loading users from config: {e}')
    print('⚠ Starting with existing database data')

print('✓ Database initialization complete')
"

echo ""
echo "=========================================="
echo "Shadowsocks Manager Ready!"
echo "=========================================="
echo "Web Interface:  http://localhost:5000"
echo "API Endpoint:   http://localhost:5000/api"
echo "Systemctl:      hostctl wrapper available"
echo "Note:           Mount host root with -v /:/host:ro"
echo "=========================================="
echo ""

# Запускаем Flask приложение напрямую
echo "Starting Flask application..."
cd /app
exec python api/api.py