import os
from pathlib import Path

# Загружаем .env файл если существует
env_path = Path('.env')
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv()

class Config:
    # MongoDB настройки
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://admin:firefly2007@localhost:27017/shadowsocks_db?authSource=admin&directConnection=true')
    MONGO_DB = os.getenv('MONGO_DB', 'shadowsocks_db')
    
    # Shadowsocks настройки
    SS_SERVER_IP = os.getenv('SS_SERVER_IP', '155.212.224.2')
    SS_PORT_RANGE_START = int(os.getenv('SS_PORT_RANGE_START', 8388))
    SS_PORT_RANGE_END = int(os.getenv('SS_PORT_RANGE_END', 8488))
    SS_METHOD = os.getenv('SS_METHOD', 'aes-256-gcm')
    
    # Конфиг файл shadowsocks-libev
    SS_CONFIG_PATH = os.getenv('SS_CONFIG_PATH', '/etc/shadowsocks-libev/config.json')
    
    # API настройки
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', 5000))
    
    # Email настройки (опционально)
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Валидация конфигурации"""
        errors = []
        
        # Проверяем MongoDB URI
        if not cls.MONGO_URI:
            errors.append("MONGO_URI is required")
        
        # Проверяем IP сервера
        if not cls.SS_SERVER_IP or cls.SS_SERVER_IP == '0.0.0.0':
            errors.append("SS_SERVER_IP must be set to your public IP address")
        
        # Проверяем порты
        if cls.SS_PORT_RANGE_START >= cls.SS_PORT_RANGE_END:
            errors.append("SS_PORT_RANGE_START must be less than SS_PORT_RANGE_END")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True