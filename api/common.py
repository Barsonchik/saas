from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import json
import logging

from api.config_generator import ShadowsocksConfigManager
from api.config import Config

app = Flask(
    __name__,
    static_folder='../static',
    static_url_path='/static',
    template_folder='../templates',
)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


app.json_encoder = MongoJSONEncoder

try:
    manager = ShadowsocksConfigManager()
    client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    client.admin.command('ping')
    db = client[Config.MONGO_DB]
    logger.info("✓ Connected to MongoDB")
except Exception as e:
    logger.error(f"✗ MongoDB connection failed: {e}")
    manager = None
    db = None
