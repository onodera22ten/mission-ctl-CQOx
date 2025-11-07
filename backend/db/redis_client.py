# backend/db/redis_client.py
import os
import json
import redis
from typing import Optional, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class RedisClient:
    def __init__(self):
        self.client = redis.from_url(REDIS_URL, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        try:
            return self.client.get(key)
        except Exception as e:
            print(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiration"""
        try:
            return self.client.set(key, value, ex=ex)
        except Exception as e:
            print(f"Redis SET error: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON object from Redis"""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set JSON object in Redis"""
        try:
            json_str = json.dumps(value, ensure_ascii=False)
            return self.set(key, json_str, ex=ex)
        except Exception as e:
            print(f"Redis SET JSON error: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Delete keys from Redis"""
        try:
            return self.client.delete(*keys)
        except Exception as e:
            print(f"Redis DELETE error: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        try:
            return self.client.exists(*keys)
        except Exception as e:
            print(f"Redis EXISTS error: {e}")
            return 0

    def ttl(self, key: str) -> int:
        """Get time to live for key"""
        try:
            return self.client.ttl(key)
        except Exception as e:
            print(f"Redis TTL error: {e}")
            return -2

# Global instance
redis_client = RedisClient()
