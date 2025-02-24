import time
import logging
from typing import Any, Optional, Dict
from pathlib import Path
import json

logger = logging.getLogger('AItuber.cache')

class CacheManager:
    def __init__(self, name: str, max_size: int = 100, ttl: int = 3600):
        self.name = name
        self.cache: Dict[str, Dict] = {}
        self.max_size = max_size
        self.ttl = ttl
        self.cache_file = Path(f"cache_{name}.json")
        self.backup_file = Path(f"cache_{name}_backup.json")
        self.load_cache()

    def load_cache(self) -> None:
        """キャッシュの読み込み"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                # 有効期限切れのエントリを除外
                now = time.time()
                self.cache = {
                    k: v for k, v in data.items()
                    if now - v['timestamp'] < self.ttl
                }
                logger.info(f"Loaded {len(self.cache)} valid cache entries for {self.name}")
        except Exception as e:
            logger.error(f"Error loading cache {self.name}: {e}")
            self.cache = {}

    def save_cache(self) -> None:
        """キャッシュの保存"""
        try:
            # バックアップを作成
            if self.cache_file.exists():
                self.cache_file.rename(self.backup_file)
            
            # 新しいキャッシュを保存
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
            logger.debug(f"Saved cache {self.name}")
        except Exception as e:
            logger.error(f"Error saving cache {self.name}: {e}")
            # バックアップから復元
            if self.backup_file.exists():
                self.backup_file.rename(self.cache_file)

    def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                logger.debug(f"Cache hit for {self.name}: {key}")
                return entry['value']
            del self.cache[key]
            logger.debug(f"Expired cache entry removed for {self.name}: {key}")
        return None

    def set(self, key: str, value: Any) -> None:
        """キャッシュに値を設定"""
        if len(self.cache) >= self.max_size:
            # 最も古いエントリを削除
            oldest = min(self.cache.items(), key=lambda x: x[1]['timestamp'])
            del self.cache[oldest[0]]
            logger.debug(f"Removed oldest cache entry for {self.name}: {oldest[0]}")

        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
        logger.debug(f"Added to cache {self.name}: {key}")
        self.save_cache()

    def clear_expired(self) -> None:
        """期限切れのキャッシュを削除"""
        now = time.time()
        expired = [k for k, v in self.cache.items() if now - v['timestamp'] >= self.ttl]
        for key in expired:
            del self.cache[key]
        if expired:
            logger.info(f"Cleared {len(expired)} expired entries from {self.name}")
            self.save_cache()