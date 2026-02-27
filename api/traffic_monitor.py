import time
import subprocess
import logging
from pymongo import MongoClient
from datetime import datetime, timezone
from api.config import Config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("traffic")

class TrafficMonitor:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.MONGO_DB]
        self.users = self.db.users
        self.connections = self.db.connections

        self.last_counters = {}   # port -> bytes

    def read_iptables(self):
        output = subprocess.check_output(
            ["iptables", "-nvx", "-L", "SS_TRAFFIC"],
            stderr=subprocess.DEVNULL
        ).decode()

        data = {}

        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 10:
                continue

            bytes_count = int(parts[1])
            rule = parts[-1]

            if "spt:" in rule:
                port = int(rule.split("spt:")[1])
                data[port] = bytes_count

        return data

    def update(self):
        current = self.read_iptables()
        now = datetime.now(timezone.utc)

        for port, total_bytes in current.items():
            last = self.last_counters.get(port, total_bytes)
            delta = total_bytes - last

            if delta <= 0:
                continue

            user = self.users.find_one({"port": port})
            if not user:
                continue

            self.users.update_one(
                {"_id": user["_id"]},
                {"$inc": {"traffic_used": delta}}
            )

            self.connections.insert_one({
                "user_id": user["_id"],
                "username": user.get("username"),
                "port": port,
                "bytes": delta,
                "timestamp": now
            })

            log.info(f"{user['username']} {port} +{delta/1024/1024:.2f} MB")

        self.last_counters = current

    def run(self):
        log.info("Traffic monitor started")
        while True:
            try:
                self.update()
                time.sleep(30)
            except Exception as e:
                log.error(e)
                time.sleep(10)

if __name__ == "__main__":
    TrafficMonitor().run()
